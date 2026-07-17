"""Export deployable Component 1 artifacts from the research datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

WEIGHTS = {"tfidf": 0.30, "bert": 0.35, "cf": 0.35}
SEMANTIC_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).lower().strip()


def normalize(values: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(values.astype(np.float32), nan=0.0)
    minimum = float(values.min())
    maximum = float(values.max())
    if maximum == minimum:
        return np.full_like(values, 0.5)
    return (values - minimum) / (maximum - minimum)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_prepare(
    provider_path: Path, interaction_path: Path
) -> tuple[pd.DataFrame, dict]:
    providers = pd.read_json(provider_path)
    interactions = pd.read_csv(interaction_path)

    provider_columns = {
        "provider_id",
        "provider_name",
        "category",
        "district",
        "city",
        "experience_years",
        "rating",
        "review_count",
        "booking_success_rate",
        "interaction_count",
        "skills",
        "description",
    }
    interaction_columns = {
        "interaction_id",
        "user_id",
        "provider_id",
        "rating",
        "booking_status",
    }
    if missing := provider_columns - set(providers.columns):
        raise ValueError(f"Provider dataset is missing columns: {sorted(missing)}")
    if missing := interaction_columns - set(interactions.columns):
        raise ValueError(f"Interaction dataset is missing columns: {sorted(missing)}")

    providers["combined_text"] = (
        providers["category"].map(clean_text)
        + " "
        + providers["skills"].map(clean_text)
        + " "
        + providers["description"].map(clean_text)
    )

    interactions["booking_status"] = (
        interactions["booking_status"].fillna("").astype(str).str.lower()
    )
    interactions["rating"] = pd.to_numeric(interactions["rating"], errors="coerce")
    interactions["booking_success_binary"] = (
        interactions["booking_status"] == "completed"
    ).astype(int)
    metrics = (
        interactions.groupby("provider_id")
        .agg(
            avg_rating=("rating", "mean"),
            derived_interaction_count=("interaction_id", "count"),
            derived_booking_success_rate=("booking_success_binary", "mean"),
        )
        .reset_index()
    )
    providers = providers.merge(metrics, on="provider_id", how="left")
    providers["avg_rating"] = providers["avg_rating"].fillna(providers["rating"])
    providers["interaction_count"] = providers["derived_interaction_count"].fillna(0)
    providers["booking_success_rate"] = providers[
        "derived_booking_success_rate"
    ].fillna(0)
    providers = providers.drop(
        columns=["derived_interaction_count", "derived_booking_success_rate"]
    )

    credibility = (
        (providers["avg_rating"].to_numpy(dtype=np.float32) / 5.0) * 0.50
        + providers["booking_success_rate"].to_numpy(dtype=np.float32) * 0.30
        + np.tanh(providers["interaction_count"].to_numpy(dtype=np.float32) / 100.0)
        * 0.20
    )
    providers["credibility_score"] = normalize(credibility)

    preferences: defaultdict[str, list[str]] = defaultdict(list)
    for row in interactions[["user_id", "provider_id"]].itertuples(index=False):
        preferences[str(row.user_id)].append(str(row.provider_id))
    return providers, dict(preferences)


def export_artifacts(
    provider_path: Path,
    interaction_path: Path,
    output_dir: Path,
    model_name: str = SEMANTIC_MODEL,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    providers, preferences = load_and_prepare(provider_path, interaction_path)

    vectorizer = TfidfVectorizer(
        max_features=5000,
        min_df=1,
        max_df=0.95,
        ngram_range=(1, 2),
        stop_words="english",
    )
    tfidf_matrix = vectorizer.fit_transform(providers["combined_text"])

    semantic_model = SentenceTransformer(model_name)
    embeddings = semantic_model.encode(
        providers["combined_text"].tolist(),
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    provider_columns = [
        "provider_id",
        "provider_name",
        "category",
        "district",
        "city",
        "skills",
        "description",
        "experience_years",
        "rating",
        "review_count",
        "booking_success_rate",
        "interaction_count",
    ]
    providers[provider_columns].to_json(
        output_dir / "providers.json", orient="records", force_ascii=False
    )
    joblib.dump(vectorizer, output_dir / "tfidf_vectorizer.joblib")
    sparse.save_npz(output_dir / "tfidf_matrix.npz", tfidf_matrix)
    np.save(output_dir / "provider_embeddings.npy", embeddings)
    np.save(
        output_dir / "credibility_scores.npy",
        providers["credibility_score"].to_numpy(dtype=np.float32),
    )
    (output_dir / "user_preferences.json").write_text(
        json.dumps(preferences, separators=(",", ":")), encoding="utf-8"
    )
    semantic_model.save(str(output_dir / "semantic_model"))

    artifact_files = [
        "providers.json",
        "tfidf_vectorizer.joblib",
        "tfidf_matrix.npz",
        "provider_embeddings.npy",
        "credibility_scores.npy",
        "user_preferences.json",
    ]
    semantic_files = [
        path.relative_to(output_dir).as_posix()
        for path in (output_dir / "semantic_model").rglob("*")
        if path.is_file()
    ]
    manifest = {
        "schema_version": 1,
        "component_version": "1.0.0",
        "model_version": datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.now(UTC).isoformat(),
        "semantic_model": model_name,
        "provider_count": len(providers),
        "embedding_dimension": int(embeddings.shape[1]),
        "weights": WEIGHTS,
        "source_files": {
            "providers": provider_path.name,
            "interactions": interaction_path.name,
        },
        "checksums": {
            name: sha256(output_dir / name) for name in artifact_files + semantic_files
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[4]
    data_dir = repository_root / "ml" / "components" / "component1" / "data" / "raw"
    default_output = (
        repository_root
        / "packages"
        / "backend"
        / "app"
        / "components"
        / "component1"
        / "artifacts"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers",
        type=Path,
        default=data_dir / "SL_Provider_Dataset_10000_Research_Grade.json",
    )
    parser.add_argument(
        "--interactions",
        type=Path,
        default=data_dir / "SL_User_Interaction_Dataset_100000.csv",
    )
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--model", default=SEMANTIC_MODEL)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    export_artifacts(
        arguments.providers,
        arguments.interactions,
        arguments.output,
        arguments.model,
    )
