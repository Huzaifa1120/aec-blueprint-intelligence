from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", enable_decoding=False
    )

    app_env: str = "development"
    database_url: str  # Required — set DATABASE_URL in .env (Supabase PostgreSQL)
    cors_origins: list[str] = ["http://localhost:3000", "https://aec-blueprint-intelligence.vercel.app"]
    log_level: str = "INFO"

    degraded_min_ocgs: int = 3
    degraded_max_untagged_fraction: float = 0.9
    degraded_confidence_multiplier: float = 0.8
    review_time_target_min: float = 10.0

    fitting_bend_angle_deg: float = 30.0
    fitting_min_segment_pt: float = 2.0
    fitting_junction_tol_pt: float = 6.0
    fu_corridor_pt: float = 24.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
