from app.core.config import Settings, get_settings


def test_defaults() -> None:
    s = Settings()
    assert s.app_env == "development"
    assert s.database_url == "sqlite:///./aec.db"
    assert s.cors_origins == ["http://localhost:3000"]
    assert s.log_level == "INFO"


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
    s = Settings()
    assert s.database_url == "sqlite:///:memory:"
    assert s.app_env == "test"


def test_cors_comma_separated() -> None:
    s = Settings(cors_origins="http://a.test,http://b.test")
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_settings_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()