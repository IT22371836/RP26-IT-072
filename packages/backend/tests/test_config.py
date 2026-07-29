import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_are_parsed() -> None:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_database",
        cors_origins="http://localhost:5173, https://example.com ",
    )

    assert settings.cors_origin_list == ["http://localhost:5173", "https://example.com"]


def test_production_rejects_development_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be configured"):
        Settings(
            app_env="production",
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test_database",
            jwt_secret_key="development-only-change-me-32-bytes",
        )
