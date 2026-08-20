from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["db"] in {"ok", "unavailable"}


def test_root() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"