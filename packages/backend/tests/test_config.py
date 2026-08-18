import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_DIR, Settings


def test_cors_origins_are_parsed() -> None:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_database",
        cors_origins="http://localhost:5173, https://example.com ",
    )

    assert settings.cors_origin_list == ["http://localhost:5173", "https://example.com"]


def test_production_requires_firebase_configuration() -> None:
    with pytest.raises(ValidationError, match="FIREBASE_PROJECT_ID"):
        Settings(
            app_env="production",
            firebase_project_id=None,
            firebase_storage_bucket=None,
        )


def test_component_artifact_paths_resolve_from_backend_directory() -> None:
    settings = Settings(
        component1_artifact_dir="app/components/component1/artifacts",
        component4_artifact_dir="../../ml/components/component4/artifacts/catf-v1",
        component4_category_priors_path=(
            "../../ml/components/component4/data/processed/category_priors.json"
        ),
    )

    assert settings.component1_artifact_dir == (
        BACKEND_DIR / "app/components/component1/artifacts"
    ).resolve()
    assert settings.component4_artifact_dir == (
        BACKEND_DIR / "../../ml/components/component4/artifacts/catf-v1"
    ).resolve()
