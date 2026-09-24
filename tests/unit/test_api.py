"""API-level tests for the unified error format and public endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_is_under_api_v1():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["application"] == "Utils-tool"


def test_capabilities_endpoint_is_public_and_safe():
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["app"]["name"] == "Utils-tool"
    assert body["storage_driver"] == "local"
    assert len(body["tools"]) == 52
    serialized = str(body).lower()
    assert "token" not in serialized


def test_unknown_route_returns_unified_error():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"]
    assert body["error"]["request_id"]
    assert response.headers.get("X-Request-ID") == body["error"]["request_id"]


def test_missing_parameters_returns_validation_error():
    response = client.post("/api/v1/background/start")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_error_responses_never_leak_internals():
    response = client.get("/api/v1/does-not-exist")
    serialized = str(response.json()).lower()
    for forbidden in (
        "/home/",
        "traceback",
        "environ",
        "secret",
        "token",
        "storage/",
    ):
        assert forbidden not in serialized
