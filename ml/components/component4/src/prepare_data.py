"""Freeze, validate, and prepare Component 4 research data.

This module implements Phase 1 only. It never maps provider IDs, seeds MongoDB, trains models,
or changes the frozen raw files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = COMPONENT_ROOT / "data" / "raw"
DEFAULT_PROCESSED_DIR = COMPONENT_ROOT / "data" / "processed"
DEFAULT_REPORTS_DIR = COMPONENT_ROOT / "reports"
DEFAULT_NOTEBOOK = COMPONENT_ROOT / "notebooks" / "component4_pp2_full_notebook_with_visualizations.ipynb"

DATASET_VERSION = "component4-data-v1"
SPLIT_VERSION = "normalized-text-sha256-v1"
SPLIT_SEED = "component4-phase1-v1"
SPLIT_THRESHOLDS = (("train", 0.70), ("validation", 0.85), ("test", 1.0))
MAX_LABEL_DISTRIBUTION_DELTA_PERCENTAGE_POINTS = 3.0

RAW_FILENAMES = {
    "reviews": "customer_reviews_25k.csv",
    "labels": "aspect_sentiment_labels_25k.csv",
    "credibility": "review_credibility_25k.csv",
    "providers": "provider_review_summary_5k.csv",
}

PROCESSED_FILENAMES = {
    "reviews": "customer_reviews_clean.csv",
    "labels": "aspect_sentiment_labels_clean.csv",
    "credibility": "review_credibility_clean.csv",
    "providers": "provider_review_summary_clean.csv",
}

EXPECTED_COLUMNS = {
    "reviews": [
        "review_id",
        "booking_id",
        "provider_id",
        "user_id",
        "service_type",
        "district",
        "rating",
        "review_text",
        "review_date",
        "verified_booking",
        "dataset_split",
    ],
    "labels": [
        "review_id",
        "quality_label",
        "punctuality_label",
        "communication_label",
        "professionalism_label",
        "overall_sentiment_label",
    ],
    "credibility": [
        "review_id",
        "word_count",
        "exclamation_count",
        "caps_word_count",
        "repeated_char_count",
        "unique_word_ratio",
        "url_count",
        "duplicate_pattern",
        "extreme_rating",
        "verified_booking",
        "reviewer_review_count_24h",
        "is_fake_review",
        "credibility_score",
    ],
    "providers": [
        "provider_id",
        "service_type",
        "district",
        "total_reviews",
        "average_rating",
        "quality_score",
        "punctuality_score",
        "communication_score",
        "professionalism_score",
        "fake_review_ratio",
        "average_credibility_score",
        "trust_sentiment_score",
        "provider_tier",
    ],
}

ASPECT_LABEL_COLUMNS = [
    "quality_label",
    "punctuality_label",
    "communication_label",
    "professionalism_label",
]
ALLOWED_SENTIMENT_LABELS = {"Positive", "Neutral", "Negative"}

CATEGORY_ALIASES = {
    "A/C Technicians": "A/C",
    "CCTV Technicians": "CCTV",
    "Ceiling Works": "Ceiling",
    "Tile Workers": "Tile",
    "Well Services": "Wells",
}


class DataValidationError(ValueError):
    """Raised when a Phase 1 data contract is violated."""


@dataclass(frozen=True)
class Phase1Paths:
    raw_dir: Path
    processed_dir: Path
    reports_dir: Path
    notebook: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_review_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def review_text_group_id(value: object) -> str:
    normalized = normalize_review_text(value)
    return "TXT-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def deterministic_split(group_id: str) -> str:
    digest = hashlib.sha256(f"{SPLIT_SEED}:{group_id}".encode("utf-8")).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    for name, threshold in SPLIT_THRESHOLDS:
        if fraction < threshold:
            return name
    raise AssertionError("split threshold configuration does not cover [0, 1)")


def canonical_service_type(value: object) -> str:
    text = " ".join(str(value).split())
    return CATEGORY_ALIASES.get(text, text)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DataValidationError(message)


def load_csvs(raw_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in RAW_FILENAMES.items():
        path = raw_dir / filename
        require(path.is_file(), f"Missing raw dataset: {path}")
        frame = pd.read_csv(path)
        require(
            list(frame.columns) == EXPECTED_COLUMNS[name],
            f"Unexpected {name} schema: {list(frame.columns)}",
        )
        frames[name] = frame
    return frames


def validate_raw(frames: dict[str, pd.DataFrame], notebook: Path) -> None:
    require(notebook.is_file(), f"Missing frozen notebook: {notebook}")
    for name, frame in frames.items():
        require(not frame.empty, f"{name} dataset is empty")
        require(not frame.isna().any().any(), f"{name} contains missing values")
        require(not frame.duplicated().any(), f"{name} contains duplicate rows")

    reviews = frames["reviews"]
    labels = frames["labels"]
    credibility = frames["credibility"]
    providers = frames["providers"]

    for name, frame in (("reviews", reviews), ("labels", labels), ("credibility", credibility)):
        require(frame["review_id"].is_unique, f"{name}.review_id must be unique")
    require(providers["provider_id"].is_unique, "providers.provider_id must be unique")

    review_ids = set(reviews["review_id"])
    require(review_ids == set(labels["review_id"]), "review and label ID sets differ")
    require(review_ids == set(credibility["review_id"]), "review and credibility ID sets differ")
    require(
        set(reviews["provider_id"]).issubset(set(providers["provider_id"])),
        "a review references a provider absent from the provider summary",
    )

    require(reviews["rating"].between(1, 5).all(), "ratings must be between 1 and 5")
    require(
        reviews["verified_booking"].isin([0, 1]).all(),
        "reviews.verified_booking must be binary",
    )
    require(
        credibility["verified_booking"].isin([0, 1]).all(),
        "credibility.verified_booking must be binary",
    )
    require(
        credibility["is_fake_review"].isin([0, 1]).all(),
        "credibility.is_fake_review must be binary",
    )
    require(
        credibility["credibility_score"].between(0, 1).all(),
        "credibility scores must be bounded by 0 and 1",
    )

    for column in ASPECT_LABEL_COLUMNS + ["overall_sentiment_label"]:
        require(
            set(labels[column]) == ALLOWED_SENTIMENT_LABELS,
            f"{column} must contain exactly {sorted(ALLOWED_SENTIMENT_LABELS)}",
        )

    joined = reviews[["review_id", "verified_booking"]].merge(
        credibility[["review_id", "verified_booking"]],
        on="review_id",
        suffixes=("_review", "_credibility"),
        validate="one_to_one",
    )
    require(
        joined["verified_booking_review"].eq(joined["verified_booking_credibility"]).all(),
        "verified_booking differs between review and credibility records",
    )

    require(
        pd.to_datetime(reviews["review_date"], errors="coerce").notna().all(),
        "review_date contains invalid dates",
    )
    require(
        reviews["review_text"].astype(str).str.strip().ne("").all(),
        "review_text contains empty values",
    )

    provider_groups = reviews.groupby("provider_id").agg(
        review_count=("review_id", "size"),
        average_rating=("rating", "mean"),
        service_type_count=("service_type", "nunique"),
        district_count=("district", "nunique"),
        service_type=("service_type", "first"),
        district=("district", "first"),
    )
    require(
        provider_groups["service_type_count"].eq(1).all(),
        "a provider has reviews from multiple service types",
    )
    require(
        provider_groups["district_count"].eq(1).all(),
        "a provider has reviews from multiple districts",
    )
    provider_check = providers.set_index("provider_id").join(provider_groups, how="left", rsuffix="_raw")
    provider_check["review_count"] = provider_check["review_count"].fillna(0)
    require(
        provider_check["total_reviews"].eq(provider_check["review_count"]).all(),
        "provider summary review counts do not match raw reviews",
    )
    with_reviews = provider_check["review_count"].gt(0)
    require(
        provider_check.loc[with_reviews, "average_rating"]
        .sub(provider_check.loc[with_reviews, "average_rating_raw"])
        .abs()
        .le(0.011)
        .all(),
        "provider summary average ratings do not match raw reviews",
    )
    require(
        provider_check.loc[with_reviews, "service_type"]
        .eq(provider_check.loc[with_reviews, "service_type_raw"])
        .all(),
        "provider summary service types do not match raw reviews",
    )
    require(
        provider_check.loc[with_reviews, "district"]
        .eq(provider_check.loc[with_reviews, "district_raw"])
        .all(),
        "provider summary districts do not match raw reviews",
    )


def prepare_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    prepared = reviews.copy()
    prepared.insert(
        prepared.columns.get_loc("booking_id") + 1,
        "source_booking_id",
        prepared["booking_id"].astype(str),
    )
    prepared["booking_id"] = "C4B-" + prepared["review_id"].astype(str)

    service_position = prepared.columns.get_loc("service_type") + 1
    prepared.insert(service_position, "source_service_type", prepared["service_type"].astype(str))
    prepared["service_type"] = prepared["service_type"].map(canonical_service_type)

    split_position = prepared.columns.get_loc("dataset_split")
    prepared.insert(
        split_position,
        "source_dataset_split",
        prepared["dataset_split"].astype(str),
    )
    prepared.insert(
        prepared.columns.get_loc("review_text") + 1,
        "review_text_group_id",
        prepared["review_text"].map(review_text_group_id),
    )
    prepared["dataset_split"] = prepared["review_text_group_id"].map(deterministic_split)
    return prepared


def prepare_providers(providers: pd.DataFrame) -> pd.DataFrame:
    prepared = providers.copy()
    prepared.insert(
        prepared.columns.get_loc("service_type") + 1,
        "source_service_type",
        prepared["service_type"].astype(str),
    )
    prepared["service_type"] = prepared["service_type"].map(canonical_service_type)
    return prepared


def validate_processed(frames: dict[str, pd.DataFrame]) -> None:
    reviews = frames["reviews"]
    labels = frames["labels"]
    credibility = frames["credibility"]
    providers = frames["providers"]

    require(reviews["booking_id"].is_unique, "processed booking IDs are not unique")
    require(reviews["review_text_group_id"].notna().all(), "text group IDs are missing")
    require(
        reviews.groupby("review_text_group_id")["dataset_split"].nunique().max() == 1,
        "a normalized review text group crosses dataset splits",
    )
    require(
        set(reviews["dataset_split"]) == {"train", "validation", "test"},
        "processed data must contain train, validation, and test splits",
    )
    require(
        set(reviews["service_type"]) == set(providers["service_type"]),
        "processed review and provider category sets differ",
    )
    require(
        reviews["review_id"].tolist() == labels["review_id"].tolist(),
        "label row order no longer matches reviews",
    )
    require(
        reviews["review_id"].tolist() == credibility["review_id"].tolist(),
        "credibility row order no longer matches reviews",
    )

    joined_labels = reviews[["review_id", "dataset_split"]].merge(
        labels,
        on="review_id",
        validate="one_to_one",
    )
    max_delta = 0.0
    for column in ASPECT_LABEL_COLUMNS:
        overall = labels[column].value_counts(normalize=True).mul(100)
        for _, split_labels in joined_labels.groupby("dataset_split"):
            split_distribution = split_labels[column].value_counts(normalize=True).mul(100)
            delta = overall.sub(split_distribution, fill_value=0).abs().max()
            max_delta = max(max_delta, float(delta))
    require(
        max_delta <= MAX_LABEL_DISTRIBUTION_DELTA_PERCENTAGE_POINTS,
        "processed split aspect-label balance exceeds the allowed percentage-point delta",
    )


def file_metadata(path: Path, frame: pd.DataFrame | None = None) -> dict[str, Any]:
    try:
        display_path = path.relative_to(COMPONENT_ROOT).as_posix()
    except ValueError:
        display_path = str(path.resolve())
    metadata: dict[str, Any] = {
        "path": display_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if frame is not None:
        metadata["rows"] = int(len(frame))
        metadata["columns"] = list(frame.columns)
    return metadata


def distribution(series: pd.Series) -> dict[str, dict[str, float | int]]:
    counts = series.value_counts(dropna=False)
    total = len(series)
    return {
        str(value): {"count": int(count), "percent": round(float(count / total * 100), 4)}
        for value, count in counts.items()
    }


def build_audit(
    raw: dict[str, pd.DataFrame],
    processed: dict[str, pd.DataFrame],
    frozen_at_utc: str,
) -> dict[str, Any]:
    raw_reviews = raw["reviews"]
    clean_reviews = processed["reviews"]
    labels = raw["labels"]
    providers = raw["providers"]

    normalized = raw_reviews["review_text"].map(normalize_review_text)
    duplicated_mask = normalized.duplicated(keep=False)
    raw_booking_counts = raw_reviews["booking_id"].value_counts()

    provider_counts = raw_reviews.groupby("provider_id").size()
    zero_review_providers = int((~providers["provider_id"].isin(provider_counts.index)).sum())

    label_distributions = {
        column: distribution(labels[column]) for column in ASPECT_LABEL_COLUMNS
    }
    split_label_distributions: dict[str, dict[str, Any]] = {}
    max_label_delta = 0.0
    label_lookup = labels.set_index("review_id")
    for split, split_reviews in clean_reviews.groupby("dataset_split"):
        split_labels = label_lookup.loc[split_reviews["review_id"]]
        split_label_distributions[str(split)] = {
            column: distribution(split_labels[column]) for column in ASPECT_LABEL_COLUMNS
        }
        for column in ASPECT_LABEL_COLUMNS:
            for label, values in split_label_distributions[str(split)][column].items():
                max_label_delta = max(
                    max_label_delta,
                    abs(values["percent"] - label_distributions[column][label]["percent"]),
                )

    category_changes = int(
        raw_reviews["service_type"].ne(clean_reviews["service_type"]).sum()
    )

    return {
        "dataset_version": DATASET_VERSION,
        "phase": 1,
        "generated_at_utc": frozen_at_utc,
        "status": "passed",
        "raw": {
            "rows": {name: int(len(frame)) for name, frame in raw.items()},
            "duplicate_normalized_text_rows": int(duplicated_mask.sum()),
            "duplicate_normalized_text_groups": int(normalized[duplicated_mask].nunique()),
            "duplicate_booking_id_groups": int((raw_booking_counts > 1).sum()),
            "duplicate_booking_id_extra_rows": int(raw_reviews["booking_id"].duplicated().sum()),
            "zero_review_providers": zero_review_providers,
            "source_split_distribution": distribution(raw_reviews["dataset_split"]),
            "aspect_label_distribution": label_distributions,
        },
        "processed": {
            "rows": {name: int(len(frame)) for name, frame in processed.items()},
            "unique_booking_ids": int(clean_reviews["booking_id"].nunique()),
            "unique_review_text_groups": int(clean_reviews["review_text_group_id"].nunique()),
            "cross_split_text_groups": int(
                clean_reviews.groupby("review_text_group_id")["dataset_split"].nunique().gt(1).sum()
            ),
            "split_distribution": distribution(clean_reviews["dataset_split"]),
            "aspect_label_distribution_by_split": split_label_distributions,
            "max_aspect_label_delta_percentage_points": round(max_label_delta, 4),
            "category_values": sorted(clean_reviews["service_type"].unique().tolist()),
            "category_rows_normalized": category_changes,
        },
        "phase2_not_started": True,
        "phase2_gate": "Provider-ID mapping requires explicit approval after Phase 1.",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def freeze_raw_manifest(path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        write_json(path, candidate)
        return candidate

    existing = json.loads(path.read_text(encoding="utf-8"))
    require(
        existing.get("dataset_version") == candidate["dataset_version"],
        "the frozen raw manifest has a different dataset version",
    )
    require(
        existing.get("files") == candidate["files"],
        "a frozen raw dataset changed after its manifest was created",
    )
    require(
        existing.get("notebook") == candidate["notebook"],
        "the frozen source notebook changed after its manifest was created",
    )
    return existing


def write_processed_csvs(
    processed_dir: Path, frames: dict[str, pd.DataFrame]
) -> dict[str, Path]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, frame in frames.items():
        path = processed_dir / PROCESSED_FILENAMES[name]
        frame.to_csv(path, index=False, lineterminator="\n")
        paths[name] = path
    return paths


def run(paths: Phase1Paths) -> None:
    raw = load_csvs(paths.raw_dir)
    validate_raw(raw, paths.notebook)

    prepared_reviews = prepare_reviews(raw["reviews"])
    review_order = prepared_reviews["review_id"]
    processed = {
        "reviews": prepared_reviews,
        "labels": raw["labels"].set_index("review_id").loc[review_order].reset_index(),
        "credibility": raw["credibility"].set_index("review_id").loc[review_order].reset_index(),
        "providers": prepare_providers(raw["providers"]),
    }
    validate_processed(processed)

    raw_manifest_candidate = {
        "dataset_version": DATASET_VERSION,
        "phase": 1,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "policy": "Raw files are immutable. All transformations occur in data/processed.",
        "files": {
            name: file_metadata(paths.raw_dir / RAW_FILENAMES[name], frame)
            for name, frame in raw.items()
        },
        "notebook": file_metadata(paths.notebook),
    }
    raw_manifest_path = paths.raw_dir / "manifest.json"
    raw_manifest = freeze_raw_manifest(raw_manifest_path, raw_manifest_candidate)
    frozen_at_utc = str(raw_manifest["frozen_at_utc"])

    output_paths = write_processed_csvs(paths.processed_dir, processed)
    audit = build_audit(raw, processed, frozen_at_utc)
    audit_path = paths.reports_dir / "phase1_audit.json"
    write_json(audit_path, audit)

    processed_manifest = {
        "dataset_version": DATASET_VERSION,
        "phase": 1,
        "generated_at_utc": frozen_at_utc,
        "input_manifest_sha256": sha256_file(raw_manifest_path),
        "split": {
            "version": SPLIT_VERSION,
            "seed": SPLIT_SEED,
            "target_ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
            "group_key": "SHA-256 of NFKC-normalized, whitespace-collapsed, case-folded review text",
        },
        "transformations": [
            "preserve source booking ID and generate unique booking ID from review ID",
            "normalize service categories to the active Component 1 vocabulary",
            "preserve original split and deterministically split by normalized-text group",
            "preserve original review text, labels, and credibility values",
        ],
        "files": {
            name: file_metadata(output_paths[name], frame)
            for name, frame in processed.items()
        },
        "audit": file_metadata(audit_path),
        "phase2_not_started": True,
    }
    write_json(paths.processed_dir / "manifest.json", processed_manifest)

    print("Component 4 Phase 1 data preparation passed.")
    print(f"Processed reviews: {len(processed['reviews'])}")
    print(f"Cross-split normalized text groups: {audit['processed']['cross_split_text_groups']}")
    print(f"Audit report: {audit_path}")
    print("Phase 2 provider-ID mapping has not started.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        Phase1Paths(
            raw_dir=args.raw_dir.resolve(),
            processed_dir=args.processed_dir.resolve(),
            reports_dir=args.reports_dir.resolve(),
            notebook=args.notebook.resolve(),
        )
    )


if __name__ == "__main__":
    main()
