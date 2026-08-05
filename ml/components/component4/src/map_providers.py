"""Map Component 4 providers to Component 1 provider IDs for Phase 2.

The mapping is category-consistent, deterministic, collision-free, and frozen once created.
This script reads Component 1 artifacts but never modifies them or any Phase 1 source file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from category_prior import build_no_review_fallback, validate_category_priors


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = COMPONENT_ROOT.parents[2]
DEFAULT_PROCESSED_DIR = COMPONENT_ROOT / "data" / "processed"
DEFAULT_REPORTS_DIR = COMPONENT_ROOT / "reports"
DEFAULT_C1_PROVIDERS = (
    REPOSITORY_ROOT
    / "packages"
    / "backend"
    / "app"
    / "components"
    / "component1"
    / "artifacts"
    / "providers.json"
)

MAPPING_VERSION = "provider-map-v1"
MAPPING_ALGORITHM = "category-sorted-bijection-v1"
CATEGORY_PRIOR_VERSION = "category-priors-v1"
DEFAULT_CATEGORY_PRIOR = 0.5

PHASE1_FILENAMES = {
    "reviews": "customer_reviews_clean.csv",
    "labels": "aspect_sentiment_labels_clean.csv",
    "credibility": "review_credibility_clean.csv",
    "providers": "provider_review_summary_clean.csv",
}

OUTPUT_FILENAMES = {
    "mapping": "provider_id_map.csv",
    "reviews": "customer_reviews_mapped.csv",
    "providers": "provider_review_summary_mapped.csv",
    "fallbacks": "provider_no_review_fallbacks.csv",
    "priors": "category_priors.json",
    "manifest": "phase2_manifest.json",
}

MAPPING_COLUMNS = [
    "source_provider_id",
    "provider_id",
    "source_category",
    "category",
    "source_district",
    "mapped_district",
    "mapping_algorithm",
    "mapping_version",
]


class ProviderMappingError(ValueError):
    """Raised when the Phase 2 mapping contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProviderMappingError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def file_metadata(path: Path, frame: pd.DataFrame | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "path": display_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if frame is not None:
        metadata["rows"] = int(len(frame))
        metadata["columns"] = list(frame.columns)
    return metadata


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_phase1_frames(processed_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in PHASE1_FILENAMES.items():
        path = processed_dir / filename
        require(path.is_file(), f"Phase 1 output is missing: {path}")
        frames[name] = pd.read_csv(path)
    return frames


def load_component1_providers(path: Path) -> pd.DataFrame:
    require(path.is_file(), f"Component 1 provider artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, list) and payload, "Component 1 provider artifact must be a list")
    providers = pd.DataFrame(payload)
    required_columns = {"provider_id", "provider_name", "category", "district"}
    require(
        required_columns.issubset(providers.columns),
        f"Component 1 provider artifact lacks columns: {sorted(required_columns - set(providers.columns))}",
    )
    require(providers["provider_id"].is_unique, "Component 1 provider IDs must be unique")
    require(not providers[list(required_columns)].isna().any().any(), "C1 provider keys are missing")
    return providers


def build_provider_mapping(
    source_providers: pd.DataFrame,
    component1_providers: pd.DataFrame,
) -> pd.DataFrame:
    required_source = {"provider_id", "service_type", "district"}
    require(
        required_source.issubset(source_providers.columns),
        f"source provider summary lacks columns: {sorted(required_source - set(source_providers.columns))}",
    )
    require(source_providers["provider_id"].is_unique, "source provider IDs must be unique")

    source_categories = set(source_providers["service_type"])
    target_categories = set(component1_providers["category"])
    require(
        source_categories.issubset(target_categories),
        f"C1 lacks source categories: {sorted(source_categories - target_categories)}",
    )

    rows: list[dict[str, str]] = []
    for category in sorted(source_categories):
        sources = source_providers[source_providers["service_type"].eq(category)].sort_values(
            "provider_id", kind="stable"
        )
        targets = component1_providers[component1_providers["category"].eq(category)].sort_values(
            "provider_id", kind="stable"
        )
        require(
            len(targets) >= len(sources),
            f"category {category!r} has {len(sources)} sources but only {len(targets)} C1 targets",
        )
        for source, target in zip(
            sources.itertuples(index=False),
            targets.head(len(sources)).itertuples(index=False),
            strict=True,
        ):
            rows.append(
                {
                    "source_provider_id": str(source.provider_id),
                    "provider_id": str(target.provider_id),
                    "source_category": str(source.service_type),
                    "category": str(target.category),
                    "source_district": str(source.district),
                    "mapped_district": str(target.district),
                    "mapping_algorithm": MAPPING_ALGORITHM,
                    "mapping_version": MAPPING_VERSION,
                }
            )

    mapping = pd.DataFrame(rows, columns=MAPPING_COLUMNS).sort_values(
        "source_provider_id", kind="stable"
    )
    mapping = mapping.reset_index(drop=True)
    require(len(mapping) == len(source_providers), "not all source providers were mapped")
    require(mapping["source_provider_id"].is_unique, "source provider mapping is not one-to-one")
    require(mapping["provider_id"].is_unique, "mapped provider IDs contain collisions")
    require(
        mapping["source_category"].eq(mapping["category"]).all(),
        "the generated provider mapping contains category mismatches",
    )
    return mapping


def freeze_mapping(path: Path, mapping: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path, dtype=str, keep_default_na=False)
        require(list(existing.columns) == MAPPING_COLUMNS, "frozen mapping schema changed")
        require(
            existing.equals(mapping.astype(str)),
            "deterministic mapping differs from the frozen provider_id_map.csv",
        )
        return
    mapping.to_csv(path, index=False, lineterminator="\n")


def map_reviews(reviews: pd.DataFrame, mapping: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    source_to_target = mapping.set_index("source_provider_id")["provider_id"]
    mapped = reviews.copy()
    source_ids = mapped["provider_id"].astype(str)
    mapped.insert(mapped.columns.get_loc("provider_id") + 1, "source_provider_id", source_ids)
    mapped["provider_id"] = source_ids.map(source_to_target)
    unmapped = int(mapped["provider_id"].isna().sum())
    return mapped, unmapped


def map_provider_summary(providers: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    source_to_target = mapping.set_index("source_provider_id")["provider_id"]
    mapped = providers.copy()
    source_ids = mapped["provider_id"].astype(str)
    mapped.insert(mapped.columns.get_loc("provider_id") + 1, "source_provider_id", source_ids)
    mapped["provider_id"] = source_ids.map(source_to_target)
    require(mapped["provider_id"].notna().all(), "a provider-summary row was not mapped")
    return mapped


def build_category_priors(source_providers: pd.DataFrame) -> dict[str, Any]:
    evidence = source_providers[source_providers["total_reviews"].gt(0)]
    categories: dict[str, Any] = {}
    for category in sorted(source_providers["service_type"].unique()):
        category_evidence = evidence[evidence["service_type"].eq(category)]
        require(not category_evidence.empty, f"category {category!r} has no reviewed providers")
        prior = round(float(category_evidence["trust_sentiment_score"].mean()), 6)
        categories[str(category)] = {
            "prior": prior,
            "source_provider_count": int(len(category_evidence)),
            "source_review_count": int(category_evidence["total_reviews"].sum()),
        }
    payload = {
        "version": CATEGORY_PRIOR_VERSION,
        "method": "mean_trust_sentiment_score_for_source_providers_with_reviews",
        "default_prior": DEFAULT_CATEGORY_PRIOR,
        "categories": categories,
    }
    validate_category_priors(payload)
    return payload


def build_fallback_frame(
    component1_providers: pd.DataFrame,
    reviewed_provider_ids: set[str],
    priors: dict[str, Any],
) -> pd.DataFrame:
    no_review = component1_providers[
        ~component1_providers["provider_id"].astype(str).isin(reviewed_provider_ids)
    ].sort_values("provider_id", kind="stable")
    rows: list[dict[str, Any]] = []
    for provider in no_review.itertuples(index=False):
        fallback = build_no_review_fallback(str(provider.provider_id), str(provider.category), priors)
        rows.append(
            {
                "provider_id": fallback["provider_id"],
                "category": fallback["category"],
                "quality_score": fallback["aspect_scores"]["quality"],
                "punctuality_score": fallback["aspect_scores"]["punctuality"],
                "communication_score": fallback["aspect_scores"]["communication"],
                "professionalism_score": fallback["aspect_scores"]["professionalism"],
                "effective_review_count": fallback["effective_review_count"],
                "reliability_factor": fallback["reliability_factor"],
                "final_score": fallback["final_score"],
                "evidence_status": fallback["evidence_status"],
                "score_source": fallback["score_source"],
                "prior_version": fallback["prior_version"],
            }
        )
    return pd.DataFrame(rows)


def validate_preservation(
    original_reviews: pd.DataFrame,
    mapped_reviews: pd.DataFrame,
    original_providers: pd.DataFrame,
    mapped_providers: pd.DataFrame,
) -> dict[str, bool]:
    require(len(original_reviews) == len(mapped_reviews), "review count changed during mapping")
    require(
        mapped_reviews["source_provider_id"].astype(str).equals(
            original_reviews["provider_id"].astype(str)
        ),
        "source_provider_id does not preserve the original review provider ID",
    )
    preserved_review_columns = [column for column in original_reviews if column != "provider_id"]
    review_fields_preserved = original_reviews[preserved_review_columns].equals(
        mapped_reviews[preserved_review_columns]
    )
    require(review_fields_preserved, "review text, rating, or another review field changed")

    require(len(original_providers) == len(mapped_providers), "provider-summary count changed")
    require(
        mapped_providers["source_provider_id"].astype(str).equals(
            original_providers["provider_id"].astype(str)
        ),
        "source_provider_id does not preserve the original summary provider ID",
    )
    preserved_provider_columns = [column for column in original_providers if column != "provider_id"]
    provider_fields_preserved = original_providers[preserved_provider_columns].equals(
        mapped_providers[preserved_provider_columns]
    )
    require(provider_fields_preserved, "review counts or provider summary fields changed")

    original_counts = original_reviews.groupby("provider_id").size().sort_index()
    mapped_counts = mapped_reviews.groupby("source_provider_id").size().sort_index()
    review_counts_preserved = original_counts.equals(mapped_counts)
    require(review_counts_preserved, "per-provider review counts changed")
    return {
        "review_fields_preserved": review_fields_preserved,
        "provider_summary_fields_preserved": provider_fields_preserved,
        "per_provider_review_counts_preserved": review_counts_preserved,
    }


def category_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    return {
        str(category): int(count)
        for category, count in frame[column].value_counts().sort_index().items()
    }


def run(processed_dir: Path, reports_dir: Path, component1_path: Path) -> None:
    phase1 = load_phase1_frames(processed_dir)
    component1_hash_before = sha256_file(component1_path)
    component1 = load_component1_providers(component1_path)

    mapping = build_provider_mapping(phase1["providers"], component1)
    mapping_path = processed_dir / OUTPUT_FILENAMES["mapping"]
    freeze_mapping(mapping_path, mapping)

    mapped_reviews, unmapped_records = map_reviews(phase1["reviews"], mapping)
    mapped_providers = map_provider_summary(phase1["providers"], mapping)
    require(unmapped_records == 0, f"{unmapped_records} review records were not mapped")

    c1_ids = set(component1["provider_id"].astype(str))
    missing_mapped_ids = set(mapping["provider_id"]) - c1_ids
    require(not missing_mapped_ids, "mapped provider IDs are missing from Component 1")

    c1_category_by_id = component1.set_index("provider_id")["category"].astype(str)
    mapped_category = mapped_reviews["provider_id"].map(c1_category_by_id)
    review_category_mismatches = int(mapped_reviews["service_type"].ne(mapped_category).sum())
    mapping_category_mismatches = int(mapping["source_category"].ne(mapping["category"]).sum())
    category_mismatches = review_category_mismatches + mapping_category_mismatches
    require(category_mismatches == 0, "mapped review-provider categories do not match")

    preservation = validate_preservation(
        phase1["reviews"], mapped_reviews, phase1["providers"], mapped_providers
    )
    label_hash_before = sha256_file(processed_dir / PHASE1_FILENAMES["labels"])
    credibility_hash_before = sha256_file(processed_dir / PHASE1_FILENAMES["credibility"])

    priors = build_category_priors(phase1["providers"])
    priors_path = processed_dir / OUTPUT_FILENAMES["priors"]
    write_json(priors_path, priors)

    reviewed_mapped_ids = set(mapped_reviews["provider_id"].astype(str))
    fallbacks = build_fallback_frame(component1, reviewed_mapped_ids, priors)
    require(fallbacks["provider_id"].is_unique, "no-review fallback provider IDs are duplicated")
    require(
        set(fallbacks["provider_id"]).issubset(c1_ids),
        "a no-review fallback references a provider absent from Component 1",
    )
    require(
        len(fallbacks) == len(component1) - len(reviewed_mapped_ids),
        "the no-review fallback set does not cover every C1 provider without mapped reviews",
    )
    require(
        set(fallbacks["provider_id"]).isdisjoint(reviewed_mapped_ids),
        "a reviewed provider received a no-review fallback",
    )
    require(
        fallbacks["evidence_status"].eq("insufficient").all(),
        "no-review fallbacks must be marked insufficient",
    )
    require(
        fallbacks["effective_review_count"].eq(0).all()
        and fallbacks["reliability_factor"].eq(0).all(),
        "no-review fallback evidence and reliability must be zero",
    )
    expected_fallback_scores = fallbacks["category"].map(
        {category: profile["prior"] for category, profile in priors["categories"].items()}
    )
    require(
        fallbacks["final_score"].eq(expected_fallback_scores).all(),
        "a no-review fallback does not use its category prior",
    )

    mapped_reviews_path = processed_dir / OUTPUT_FILENAMES["reviews"]
    mapped_providers_path = processed_dir / OUTPUT_FILENAMES["providers"]
    fallbacks_path = processed_dir / OUTPUT_FILENAMES["fallbacks"]
    mapped_reviews.to_csv(mapped_reviews_path, index=False, lineterminator="\n")
    mapped_providers.to_csv(mapped_providers_path, index=False, lineterminator="\n")
    fallbacks.to_csv(fallbacks_path, index=False, lineterminator="\n")

    label_hash_after = sha256_file(processed_dir / PHASE1_FILENAMES["labels"])
    credibility_hash_after = sha256_file(processed_dir / PHASE1_FILENAMES["credibility"])
    component1_hash_after = sha256_file(component1_path)
    require(component1_hash_before == component1_hash_after, "Component 1 provider source changed")
    require(label_hash_before == label_hash_after, "aspect label data changed during mapping")
    require(
        credibility_hash_before == credibility_hash_after,
        "review credibility features changed during mapping",
    )

    source_providers_with_reviews = int(phase1["reviews"]["provider_id"].nunique())
    mapped_providers_with_reviews = int(mapped_reviews["provider_id"].nunique())
    mapped_providers_without_reviews = int(
        (~mapping["provider_id"].isin(reviewed_mapped_ids)).sum()
    )
    unused_c1_providers = len(component1) - len(mapping)

    fallback_category_counts = category_counts(fallbacks, "category")
    audit = {
        "phase": 2,
        "status": "passed",
        "mapping_version": MAPPING_VERSION,
        "mapping_algorithm": MAPPING_ALGORITHM,
        "total_component1_providers": int(len(component1)),
        "total_reviews": int(len(mapped_reviews)),
        "unique_source_providers": int(len(mapping)),
        "unique_source_providers_with_reviews": source_providers_with_reviews,
        "unique_mapped_providers": int(mapping["provider_id"].nunique()),
        "unique_mapped_providers_with_reviews": mapped_providers_with_reviews,
        "unmapped_records": unmapped_records,
        "unmapped_source_providers": int(
            len(set(phase1["providers"]["provider_id"]) - set(mapping["source_provider_id"]))
        ),
        "mapped_provider_ids_missing_in_component1": len(missing_mapped_ids),
        "category_mismatches": category_mismatches,
        "providers_with_no_reviews": int(len(fallbacks)),
        "mapped_providers_with_no_reviews": mapped_providers_without_reviews,
        "component1_providers_not_used_in_mapping": int(unused_c1_providers),
        "preservation": {
            **preservation,
            "review_text_preserved": bool(
                phase1["reviews"]["review_text"].equals(mapped_reviews["review_text"])
            ),
            "ratings_preserved": bool(
                phase1["reviews"]["rating"].equals(mapped_reviews["rating"])
            ),
            "labels_preserved": label_hash_before == label_hash_after,
            "credibility_features_preserved": credibility_hash_before == credibility_hash_after,
            "component1_source_unchanged": component1_hash_before == component1_hash_after,
        },
        "category_mapping_counts": category_counts(mapping, "category"),
        "no_review_fallback_counts_by_category": fallback_category_counts,
        "category_prior_version": CATEGORY_PRIOR_VERSION,
        "category_priors": {
            category: profile["prior"] for category, profile in priors["categories"].items()
        },
    }
    audit_path = reports_dir / "phase2_mapping_audit.json"
    write_json(audit_path, audit)

    phase1_manifest_path = processed_dir / "manifest.json"
    require(phase1_manifest_path.is_file(), "Phase 1 processed manifest is missing")
    manifest = {
        "phase": 2,
        "mapping_version": MAPPING_VERSION,
        "mapping_algorithm": MAPPING_ALGORITHM,
        "category_prior_version": CATEGORY_PRIOR_VERSION,
        "inputs": {
            "component1_providers": file_metadata(component1_path, component1),
            "phase1_manifest": file_metadata(phase1_manifest_path),
            **{
                f"phase1_{name}": file_metadata(
                    processed_dir / PHASE1_FILENAMES[name], frame
                )
                for name, frame in phase1.items()
            },
        },
        "outputs": {
            "provider_mapping": file_metadata(mapping_path, mapping),
            "mapped_reviews": file_metadata(mapped_reviews_path, mapped_reviews),
            "mapped_provider_summary": file_metadata(mapped_providers_path, mapped_providers),
            "provider_no_review_fallbacks": file_metadata(fallbacks_path, fallbacks),
            "category_priors": file_metadata(priors_path),
            "audit": file_metadata(audit_path),
        },
        "component1_source_unchanged": True,
        "phase3_not_started": True,
    }
    write_json(processed_dir / OUTPUT_FILENAMES["manifest"], manifest)

    print("Component 4 Phase 2 provider mapping passed.")
    print(f"Total reviews: {audit['total_reviews']}")
    print(f"Unique source providers: {audit['unique_source_providers']}")
    print(f"Unique mapped providers: {audit['unique_mapped_providers']}")
    print(f"Unmapped records: {audit['unmapped_records']}")
    print(f"Category mismatches: {audit['category_mismatches']}")
    print(f"Providers with no reviews: {audit['providers_with_no_reviews']}")
    print(f"Mapping: {mapping_path}")
    print(f"Audit: {audit_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--component1-providers", type=Path, default=DEFAULT_C1_PROVIDERS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        processed_dir=args.processed_dir.resolve(),
        reports_dir=args.reports_dir.resolve(),
        component1_path=args.component1_providers.resolve(),
    )


if __name__ == "__main__":
    main()
