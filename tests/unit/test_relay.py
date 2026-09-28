"""Tests for the relay: chunked uploads and detached processing."""

import io
import os
import time
import uuid

import pikepdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.main import app
from app.modules.relay import relay_service as relay_module
from app.modules.relay.relay_service import relay_service

client = TestClient(app)

BOUNDARY = "relay-test-boundary"
MULTIPART = f"multipart/form-data; boundary={BOUNDARY}"


def new_session() -> str:
    return uuid.uuid4().hex


def sample_pdf(pages: int = 3) -> bytes:
    document = pikepdf.new()
    for _ in range(pages):
        document.add_blank_page(page_size=(595, 842))
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def multipart(name: str, filename: str, data: bytes, content_type: str) -> bytes:
    head = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    return head + data + f"\r\n--{BOUNDARY}--\r\n".encode()


def send_chunk(session: str, body: bytes, start: int, end: int, content_type=MULTIPART):
    return client.post(
        f"/api/v1/relay/{session}/chunk",
        params={"offset": start, "size": len(body), "type": content_type},
        content=body[start:end],
    )


def collect(session: str, timeout: float = 10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/relay/{session}", params={"wait": 1})
        if response.status_code != 202:
            return response
    raise AssertionError("relayed request did not finish")


def test_chunked_upload_gives_the_same_answer_as_a_direct_request():
    pdf = sample_pdf()
    body = multipart("file", "sample.pdf", pdf, "application/pdf")
    direct = client.post(
        "/api/v1/tools/pdf/info",
        files={"file": ("sample.pdf", pdf, "application/pdf")},
    )
    assert direct.status_code == 200

    session = new_session()
    third = len(body) // 3
    # Out of order, as parallel uploads arrive.
    assert send_chunk(session, body, third, 2 * third).json()["staged"] == 0
    assert send_chunk(session, body, 0, third).json()["staged"] == 2 * third
    assert send_chunk(session, body, 2 * third, len(body)).json()["staged"] == len(body)

    relayed = client.post(
        f"/api/v1/relay/{session}/run",
        params={"path": "/api/v1/tools/pdf/info", "wait": 10},
    )
    assert relayed.status_code == 200
    assert relayed.headers["content-type"].startswith("application/json")
    assert relayed.json() == direct.json()


def test_a_body_sent_with_run_is_the_whole_request():
    relayed = client.post(
        f"/api/v1/relay/{new_session()}/run",
        params={"path": "/api/v1/tools/text/word-counter", "wait": 10},
        json={"text": "one two three"},
    )
    direct = client.post(
        "/api/v1/tools/text/word-counter",
        json={"text": "one two three"},
    )
    assert relayed.status_code == 200
    assert relayed.json() == direct.json()


def test_a_request_can_be_collected_later_and_more_than_once():
    session = new_session()
    started = client.post(
        f"/api/v1/relay/{session}/run",
        params={"path": "/api/v1/tools/text/word-counter?unused=1"},
        json={"text": "one two"},
    )
    assert started.status_code in {200, 202}
    first = collect(session)
    assert first.status_code == 200
    assert collect(session).json() == first.json()
    # Starting again, with or without the body, is not a second run.
    for body in ({"text": "a different request"}, None):
        again = client.post(
            f"/api/v1/relay/{session}/run",
            params={"path": "/api/v1/tools/text/word-counter", "wait": 5},
            json=body,
        )
        assert again.json() == first.json()


def test_errors_are_replayed_with_their_status():
    relayed = client.post(
        f"/api/v1/relay/{new_session()}/run",
        params={"path": "/api/v1/tools/dev/json-format", "wait": 10},
        json={"json_text": "{not json"},
    )
    direct = client.post("/api/v1/tools/dev/json-format", json={"json_text": "{not json"})
    assert direct.status_code >= 400
    assert relayed.status_code == direct.status_code
    assert relayed.json()["error"]["code"] == direct.json()["error"]["code"]


def test_file_responses_keep_their_headers():
    relayed = client.post(
        f"/api/v1/relay/{new_session()}/run",
        params={"path": "/api/v1/tools/dev/barcode", "wait": 10},
        content=b"content=123456789012",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    direct = client.post("/api/v1/tools/dev/barcode", data={"content": "123456789012"})
    assert relayed.status_code == direct.status_code == 200
    assert relayed.headers["content-type"] == direct.headers["content-type"]
    assert relayed.headers["content-disposition"] == direct.headers["content-disposition"]
    assert relayed.content == direct.content


def test_an_incomplete_upload_cannot_be_started():
    body = multipart("file", "sample.pdf", sample_pdf(), "application/pdf")
    session = new_session()
    send_chunk(session, body, 0, 100)
    response = client.post(
        f"/api/v1/relay/{session}/run",
        params={"path": "/api/v1/tools/pdf/info"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RELAY_CONFLICT"


def test_chunks_must_belong_to_the_same_upload():
    body = multipart("file", "sample.pdf", sample_pdf(), "application/pdf")
    session = new_session()
    assert send_chunk(session, body, 0, 100).status_code == 200
    mismatch = client.post(
        f"/api/v1/relay/{session}/chunk",
        params={"offset": 100, "size": len(body) + 1, "type": MULTIPART},
        content=body[100:200],
    )
    assert mismatch.status_code == 409
    beyond = client.post(
        f"/api/v1/relay/{session}/chunk",
        params={"offset": len(body) - 10, "size": len(body), "type": MULTIPART},
        content=b"x" * 50,
    )
    assert beyond.status_code == 400


def test_uploads_over_the_request_limit_are_refused(monkeypatch):
    monkeypatch.setattr(settings, "max_request_body_mb", 1)
    response = client.post(
        f"/api/v1/relay/{new_session()}/chunk",
        params={"offset": 0, "size": 2 * 1024 * 1024, "type": MULTIPART},
        content=b"x" * 10,
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/relay/0123456789abcdef0123456789abcdef/run?path=/api/v1/health"),
        ("POST", "/about"),
        ("POST", "https://example.com/api/v1/tools/text/word-counter"),
        ("POST", "//example.com/api/v1/tools/text/word-counter"),
        ("POST", "/api/v1/../errors/404"),
        ("GET", "/api/v1/health"),
        ("DELETE", "/api/v1/jobs/abc"),
    ],
)
def test_only_api_posts_can_be_relayed(method, path):
    response = client.post(
        f"/api/v1/relay/{new_session()}/run",
        params={"path": path, "method": method},
        json={"text": "hello"},
    )
    assert response.status_code == 400


def test_session_ids_are_validated():
    response = client.get("/api/v1/relay/not-a-session")
    assert response.status_code == 422
    unknown = client.get(f"/api/v1/relay/{new_session()}")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "RELAY_NOT_STARTED"


def test_a_dead_worker_is_reported_instead_of_waited_for():
    session_id = new_session()
    session = relay_service.session(session_id)
    session.directory.mkdir(parents=True)
    session.state.write_text("{}")
    session.heartbeat.touch()
    stale = time.time() - relay_module.STALLED_AFTER_SECONDS - 5
    os.utime(session.heartbeat, (stale, stale))

    response = client.get(f"/api/v1/relay/{session_id}", params={"wait": 5})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PROCESSING_INTERRUPTED"


def test_the_relay_is_off_without_a_shared_disk(monkeypatch):
    monkeypatch.setattr(settings, "storage_driver", "vercel")
    response = client.post(
        f"/api/v1/relay/{new_session()}/run",
        params={"path": "/api/v1/tools/text/word-counter"},
        json={"text": "hello"},
    )
    assert response.status_code == 404


def test_the_upload_is_removed_once_the_request_has_run():
    session_id = new_session()
    client.post(
        f"/api/v1/relay/{session_id}/run",
        params={"path": "/api/v1/tools/text/word-counter", "wait": 10},
        json={"text": "hello"},
    )
    session = relay_service.session(session_id)
    deadline = time.monotonic() + 5
    while session.body.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not session.body.exists()
    assert not session.parts.exists()
    assert session.response_meta.exists()


def test_relayed_requests_are_charged_to_the_tool(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "rate_limit_max_requests", 1)
    rate_limiter.reset()
    try:
        results = [
            client.post(
                f"/api/v1/relay/{new_session()}/run",
                params={"path": "/api/v1/tools/text/word-counter", "wait": 10},
                json={"text": "hello"},
            ).status_code
            for _ in range(2)
        ]
        assert results == [200, 429]
    finally:
        rate_limiter.reset()
