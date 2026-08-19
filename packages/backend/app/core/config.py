from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = BACKEND_DIR.parents[1]


class Settings(BaseSettings):
    """Environment-backed application settings.

    Secrets are loaded from ``packages/backend/.env`` for local development and
    from process environment variables in deployed environments.
    """

    app_name: str = "weda.lk API"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    component1_artifact_dir: Path = (
        BACKEND_DIR / "app" / "components" / "component1" / "artifacts"
    )
    component4_artifact_dir: Path = (
        REPOSITORY_DIR / "ml" / "components" / "component4" / "artifacts" / "catf-v1"
    )
    component4_category_priors_path: Path = (
        REPOSITORY_DIR
        / "ml"
        / "components"
        / "component4"
        / "data"
        / "processed"
        / "category_priors.json"
    )

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    jwt_secret_key: str = Field(default="development-only-change-me-32-bytes", min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5, le=10080)
    auth_cookie_enabled: bool = False
    auth_cookie_name: str = Field(default="weda_access_token", min_length=1, max_length=100)
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict"] = "lax"

    firebase_project_id: str | None = None
    firebase_database_url: str | None = None
    firebase_credentials_path: Path | None = None
    firebase_storage_bucket: str | None = None
    firebase_check_revoked: bool = True
    document_upload_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    pipeline_worker_id: str = "weda-pipeline-worker-1"
    pipeline_poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)
    pipeline_lease_seconds: int = Field(default=90, ge=30, le=3600)
    pipeline_weather_timeout_seconds: float = Field(default=10.0, ge=1, le=60)
    pipeline_weather_retries: int = Field(default=3, ge=1, le=5)
    pipeline_provider_cache_seconds: float = Field(default=300.0, ge=0, le=600)
    pipeline_component2_version: str = "firebase-filter-v1"
    pipeline_component2_model_version: str = "distance-hours-weather-v1"
    research_provider_password: str | None = Field(default=None, min_length=8, max_length=128)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator(
        "component1_artifact_dir",
        "component4_artifact_dir",
        "component4_category_priors_path",
        "firebase_credentials_path",
    )
    @classmethod
    def resolve_backend_relative_paths(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        if value.is_absolute():
            return value
        return (BACKEND_DIR / value).resolve()

    @model_validator(mode="after")
    def require_firebase_in_production(self) -> "Settings":
        if self.app_env.lower() == "production" and not self.firebase_project_id:
            raise ValueError("FIREBASE_PROJECT_ID must be configured in production")
        if self.app_env.lower() == "production" and not self.firebase_storage_bucket:
            raise ValueError("FIREBASE_STORAGE_BUCKET must be configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
