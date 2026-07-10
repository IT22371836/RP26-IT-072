from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent


def _find_repo_root(start_dir: Path) -> Path:
    current = start_dir
    for _ in range(8):
        if (current / "packages").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return start_dir


def _resolve_training_dir() -> Path:
    env_value = os.getenv("COMPONENT1_TRAINING_DIR")
    if env_value:
        return Path(env_value)

    local_dir = BASE_DIR / "training"
    if local_dir.exists():
        return local_dir

    repo_root = _find_repo_root(BASE_DIR)
    legacy_dir = repo_root / "model-test"
    return legacy_dir


def _resolve_artifacts_dir(training_dir: Path) -> Path:
    env_value = os.getenv("COMPONENT1_ARTIFACTS_DIR")
    if env_value:
        return Path(env_value)

    local_dir = BASE_DIR / "artifacts"
    if local_dir.exists():
        return local_dir

    return training_dir / "artifacts"


@dataclass(frozen=True)
class Component1Paths:
    training_dir: Path
    artifacts_dir: Path
    models_dir: Path
    bert_model_dir: Path
    provider_dataset: Path
    interaction_dataset: Path
    embeddings_cache: Path
    tfidf_vectorizer_path: Path
    tfidf_matrix_path: Path
    provider_df_path: Path
    provider_credibility_path: Path
    user_preferences_path: Path
    weights_path: Path


def get_paths() -> Component1Paths:
    training_dir = _resolve_training_dir()
    artifacts_dir = _resolve_artifacts_dir(training_dir)
    models_dir = training_dir / "models"
    bert_model_dir = Path(
        os.getenv("COMPONENT1_BERT_MODEL_DIR", str(artifacts_dir / "bert_model"))
    )

    provider_dataset = Path(
        os.getenv("COMPONENT1_PROVIDER_DATASET", str(training_dir / "provider_dataset_100k.xlsx"))
    )
    interaction_dataset = Path(
        os.getenv(
            "COMPONENT1_INTERACTION_DATASET",
            str(training_dir / "user_interaction_dataset_120k.xlsx"),
        )
    )
    embeddings_cache = Path(
        os.getenv(
            "COMPONENT1_EMBEDDINGS_CACHE",
            str(artifacts_dir / "provider_embeddings.npy"),
        )
    )

    tfidf_vectorizer_path = Path(
        os.getenv(
            "COMPONENT1_TFIDF_VECTORIZER",
            str(artifacts_dir / "tfidf_vectorizer.joblib"),
        )
    )
    tfidf_matrix_path = Path(
        os.getenv(
            "COMPONENT1_TFIDF_MATRIX",
            str(artifacts_dir / "tfidf_matrix.joblib"),
        )
    )
    provider_df_path = Path(
        os.getenv(
            "COMPONENT1_PROVIDER_ARTIFACT",
            str(artifacts_dir / "provider_df.pkl"),
        )
    )
    provider_credibility_path = Path(
        os.getenv(
            "COMPONENT1_PROVIDER_CREDIBILITY",
            str(artifacts_dir / "provider_credibility.pkl"),
        )
    )
    user_preferences_path = Path(
        os.getenv(
            "COMPONENT1_USER_PREFERENCES",
            str(artifacts_dir / "user_preferences.joblib"),
        )
    )
    weights_path = Path(
        os.getenv("COMPONENT1_WEIGHTS", str(artifacts_dir / "weights.json"))
    )

    return Component1Paths(
        training_dir=training_dir,
        artifacts_dir=artifacts_dir,
        models_dir=models_dir,
        bert_model_dir=bert_model_dir,
        provider_dataset=provider_dataset,
        interaction_dataset=interaction_dataset,
        embeddings_cache=embeddings_cache,
        tfidf_vectorizer_path=tfidf_vectorizer_path,
        tfidf_matrix_path=tfidf_matrix_path,
        provider_df_path=provider_df_path,
        provider_credibility_path=provider_credibility_path,
        user_preferences_path=user_preferences_path,
        weights_path=weights_path,
    )
