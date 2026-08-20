from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine


def test_health_reports_db_ok(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()
    get_engine.cache_clear()
    from app.main import app

    resp = TestClient(app).get("/health")
    assert resp.json()["db"] == "ok"