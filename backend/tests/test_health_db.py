from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine


def test_health_reports_db_ok(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        from app.main import app

        resp = TestClient(app).get("/health")
        assert resp.json()["db"] == "ok"
    finally:
        # Rebuild-from-env hygiene: the caches were cleared while DATABASE_URL
        # pointed at a throwaway in-memory DB. Clearing again here (after the
        # body, before monkeypatch restores the real env at teardown) forces
        # every later test to rebind to the configured database instead of
        # inheriting this test's throwaway engine.
        get_settings.cache_clear()
        get_engine.cache_clear()