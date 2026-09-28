"""Tests for the shared, tiered rate limiter."""

import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import settings
from app.core.rate_limit import RateLimiter, Rule, client_key, rate_limiter, rules_for
from app.main import app


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def test_limit_is_shared_between_workers(tmp_path):
    # Two limiters on one file stand in for two worker processes.
    database = tmp_path / "limits.sqlite3"
    first, second = RateLimiter(database), RateLimiter(database)
    rules = (Rule(4, 60),)

    for worker in (first, second, first, second):
        assert worker.check("203.0.113.9", "write", rules) is None
    assert first.check("203.0.113.9", "write", rules) is not None
    assert second.check("203.0.113.9", "write", rules) is not None
    assert second.check("203.0.113.10", "write", rules) is None


def test_rejected_requests_are_not_counted(tmp_path):
    limiter = RateLimiter(tmp_path / "limits.sqlite3")
    strict, loose = Rule(1, 60), Rule(100, 3600)

    assert limiter.check("client", "heavy", (strict, loose)) is None
    for _ in range(5):
        assert limiter.check("client", "heavy", (strict, loose)) is not None
    # Only the first request was charged to the hourly rule.
    assert limiter.check("client", "heavy", (Rule(2, 3600),)) is None


def test_previous_window_still_counts(tmp_path, monkeypatch):
    limiter = RateLimiter(tmp_path / "limits.sqlite3")
    rules = (Rule(10, 60),)
    clock = {"now": 60_000.0 + 59}
    monkeypatch.setattr(rate_limit.time, "time", lambda: clock["now"])

    for _ in range(10):
        assert limiter.check("client", "write", rules) is None
    # Two seconds later a new window has begun, but almost all of the
    # previous one still overlaps the last 60 seconds: a fixed window
    # would hand out ten more requests here.
    clock["now"] += 2
    assert limiter.check("client", "write", rules) is None
    assert limiter.check("client", "write", rules) is not None
    clock["now"] += 120
    assert limiter.check("client", "write", rules) is None


def test_store_failure_allows_the_request(tmp_path):
    limiter = RateLimiter(tmp_path / "missing" / "nested")
    (tmp_path / "missing").write_text("not a directory")
    assert limiter.check("client", "write", (Rule(1, 60),)) is None


@pytest.mark.parametrize(
    ("method", "path", "tier"),
    [
        ("GET", "/", "read"),
        ("GET", "/static/assets/js/api.js", "read"),
        ("GET", "/api/v1/jobs/abc", "read"),
        ("GET", "/api/v1/tools/video/download/clip.mp4", "read"),
        ("POST", "/api/v1/tools/pdf/merge", "write"),
        ("DELETE", "/api/v1/jobs/abc", "write"),
        ("POST", "/api/v1/background/start", "heavy"),
        ("POST", "/api/v1/images/compress", "heavy"),
        ("POST", "/api/v1/tools/video/download", "heavy"),
        ("POST", "/api/v1/tools/text/text-to-speech", "heavy"),
        ("POST", "/api/v1/relay/0123/chunk", "transfer"),
        ("GET", "/api/v1/relay/0123", "transfer"),
    ],
)
def test_every_request_has_a_tier(method, path, tier):
    name, rules = rules_for(method, path)
    assert name == tier
    assert rules and all(rule.limit > 0 for rule in rules)


def test_forwarding_headers_are_ignored_by_default(monkeypatch):
    monkeypatch.setattr(settings, "storage_driver", "local")
    monkeypatch.setattr(settings, "trusted_proxy_header", "")
    spoofed = {
        "x-forwarded-for": "198.51.100.1",
        "x-real-ip": "198.51.100.2",
        "x-vercel-forwarded-for": "198.51.100.3",
    }
    assert client_key("203.0.113.9", spoofed) == "203.0.113.9"


def test_trusted_proxy_header_is_used_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_header", "X-Forwarded-For")
    headers = {"x-forwarded-for": "198.51.100.1, 10.0.0.1"}
    assert client_key("10.0.0.1", headers) == "198.51.100.1"


def test_ipv6_clients_are_grouped_by_network():
    first = client_key("2001:db8:1:2:aaaa::1", {})
    second = client_key("2001:db8:1:2:bbbb::2", {})
    assert first == second == "2001:db8:1:2::"
    assert client_key("2001:db8:1:3::1", {}) != first


def test_reads_are_limited_separately_from_writes(production, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_max_requests", 2)
    monkeypatch.setattr(settings, "rate_limit_read_max_requests", 3)
    client = TestClient(app)

    for _ in range(3):
        assert client.get("/api/v1/health").status_code == 200
    limited = client.get("/api/v1/health")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert 1 <= int(limited.headers["Retry-After"]) <= 60

    # Pages and assets draw on the same read budget.
    assert client.get("/about", headers={"Accept": "text/html"}).status_code == 429
    # Writes have a budget of their own.
    payload = {"text": "hello world"}
    assert client.post("/api/v1/tools/text/word-counter", json=payload).status_code == 200


def test_spoofed_header_does_not_buy_a_new_budget(production, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_max_requests", 2)
    client = TestClient(app)
    payload = {"text": "hello world"}

    for attempt in range(2):
        response = client.post("/api/v1/tools/text/word-counter", json=payload)
        assert response.status_code == 200
    for attempt in range(3):
        response = client.post(
            "/api/v1/tools/text/word-counter",
            json=payload,
            headers={"X-Real-IP": f"198.51.100.{attempt}"},
        )
        assert response.status_code == 429


def test_heavy_tools_have_a_stricter_limit(production, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_heavy_max_requests", 1)
    client = TestClient(app)
    payload = {"text": "hello"}

    first = client.post("/api/v1/tools/text/text-to-speech", json={"text": ""})
    assert first.status_code != 429
    second = client.post("/api/v1/tools/text/text-to-speech", json={"text": ""})
    assert second.status_code == 429
    assert client.post("/api/v1/tools/text/word-counter", json=payload).status_code == 200


def test_limits_are_off_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "rate_limit_read_max_requests", 1)
    rate_limiter.reset()
    client = TestClient(app)
    for _ in range(3):
        assert client.get("/api/v1/health").status_code == 200
