from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", enable_decoding=False
    )

    app_env: str = "development"
    database_url: str = "sqlite:///./aec.db"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()