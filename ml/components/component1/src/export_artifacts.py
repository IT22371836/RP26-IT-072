"""Export deployable Component 1 artifacts from the research datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
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
SELECTION_VERSION = "research-balanced-category-location-v1"


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


def _selection_key(provider_id: str) -> str:
    return hashlib.sha256(f"{SELECTION_VERSION}:{provider_id}".encode()).hexdigest()


def balanced_provider_sample(
    providers: pd.DataFrame,
    limit: int,
    eligible_provider_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Select a deterministic category and location-balanced provider subset."""

    if eligible_provider_ids is not None:
        providers = providers[providers["provider_id"].astype(str).isin(eligible_provider_ids)]
    if limit < 1 or limit > len(providers):
        raise ValueError(f"Provider limit must be between 1 and {len(providers)}")

    categories = sorted(str(value) for value in providers["category"].dropna().unique())
    if not categories:
        raise ValueError("Provider dataset contains no categories")
    base, remainder = divmod(limit, len(categories))
    selected_indices: list[int] = []
    quotas: dict[str, int] = {}
    for index, category in enumerate(categories):
        category_rows = providers[providers["category"].astype(str) == category].copy()
        quota = base + int(index < remainder)
        if len(category_rows) < quota:
            raise ValueError(f"Category {category} cannot supply its quota of {quota}")
        quotas[category] = quota
        category_rows["_selection_key"] = category_rows["provider_id"].map(
            lambda value: _selection_key(str(value))
        )
        category_rows = category_rows.sort_values(
            ["district", "city", "_selection_key"], kind="stable"
        )
        locations = {
            key: group.sort_values("_selection_key", kind="stable").index.tolist()
            for key, group in category_rows.groupby(["district", "city"], sort=True)
        }
        offsets = {key: 0 for key in locations}
        category_selected: list[int] = []
        while len(category_selected) < quota:
            for key in sorted(locations):
                offset = offsets[key]
                if offset >= len(locations[key]):
                    continue
                category_selected.append(locations[key][offset])
                offsets[key] += 1
                if len(category_selected) == quota:
                    break
        selected_indices.extend(category_selected)

    selected = providers.loc[selected_indices].copy()
    counts = Counter(selected["category"].astype(str))
    if len(selected) != limit or set(counts) != set(categories):
        raise RuntimeError("Balanced provider selection did not satisfy its contract")
    return selected.reset_index(drop=True)


def load_provider_ids(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    with path.open(encoding="utf-8", newline="") as source:
        return {
            str(row["provider_id"]).strip()
            for row in csv.DictReader(source)
            if str(row.get("provider_id") or "").strip()
        }


def load_and_prepare(
    provider_path: Path,
    interaction_path: Path,
    *,
    provider_limit: int | None = None,
    eligible_provider_ids: set[str] | None = None,
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

    if provider_limit is not None:
        providers = balanced_provider_sample(
            providers,
            provider_limit,
            eligible_provider_ids,
        )
        selected_ids = set(providers["provider_id"].astype(str))
        interactions = interactions[
            interactions["provider_id"].astype(str).isin(selected_ids)
        ].copy()

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
    provider_limit: int | None = None,
    provider_map_path: Path | None = None,
    model_source: str | Path | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    providers, preferences = load_and_prepare(
        provider_path,
        interaction_path,
        provider_limit=provider_limit,
        eligible_provider_ids=load_provider_ids(provider_map_path),
    )

    vectorizer = TfidfVectorizer(
        max_features=5000,
        min_df=1,
        max_df=0.95,
        ngram_range=(1, 2),
        stop_words="english",
    )
    tfidf_matrix = vectorizer.fit_transform(providers["combined_text"])

    semantic_model = SentenceTransformer(str(model_source or model_name))
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
    semantic_output = output_dir / "semantic_model"
    if model_source is not None and Path(model_source).is_dir():
        shutil.copytree(Path(model_source), semantic_output, dirs_exist_ok=True)
    else:
        semantic_model.save(str(semantic_output))

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
        "provider_selection": {
            "limit": provider_limit,
            "strategy": SELECTION_VERSION if provider_limit is not None else "full_dataset",
            "eligible_provider_map": provider_map_path.name if provider_map_path else None,
            "category_counts": dict(sorted(Counter(providers["category"]).items())),
        },
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
    parser.add_argument(
        "--model-source",
        type=Path,
        help="Optional local Sentence Transformer directory for offline artifact export",
    )
    parser.add_argument("--provider-limit", type=int, default=500)
    parser.add_argument(
        "--provider-map",
        type=Path,
        default=(
            repository_root
            / "ml"
            / "components"
            / "component4"
            / "data"
            / "processed"
            / "provider_id_map.csv"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    export_artifacts(
        arguments.providers,
        arguments.interactions,
        arguments.output,
        arguments.model,
        arguments.provider_limit,
        arguments.provider_map,
        arguments.model_source,
    )
