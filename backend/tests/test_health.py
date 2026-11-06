from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_has_the_api_md_shape():
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert set(body) == {"status", "hindsight", "llm", "db"}
    assert body["status"] in {"ok", "degraded"}
    for dependency in ("hindsight", "llm", "db"):
        assert body[dependency] in {"ok", "down"}

    # status must agree with the dependencies.
    expected = "ok" if all(body[d] == "ok" for d in ("hindsight", "llm", "db")) else "degraded"
    assert body["status"] == expected


def test_unknown_route_uses_the_api_error_shape():
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "That resource doesn't exist.",
        }
    }


def test_cors_allows_the_vite_dev_server():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
