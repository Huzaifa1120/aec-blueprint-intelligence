from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_frontend_origin() -> None:
    resp = TestClient(app).options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"