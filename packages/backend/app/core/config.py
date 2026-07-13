from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-backed application settings.

    Secrets are loaded from ``packages/backend/.env`` for local development and
    from process environment variables in deployed environments.
    """

    app_name: str = "weda.lk API"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    mongodb_uri: str = Field(default="mongodb://localhost:27017", min_length=1)
    mongodb_database: str = Field(default="weda_platform_renew_dev", min_length=1)
    mongodb_server_selection_timeout_ms: int = Field(default=5000, ge=1000, le=30000)

    cors_origins: str = "http://localhost:5173"

    jwt_secret_key: str = Field(default="development-only-change-me-32-bytes", min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5, le=10080)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def reject_development_secret_in_production(self) -> "Settings":
        if self.app_env.lower() == "production" and self.jwt_secret_key.startswith(
            "development-only"
        ):
            raise ValueError("JWT_SECRET_KEY must be configured for production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
