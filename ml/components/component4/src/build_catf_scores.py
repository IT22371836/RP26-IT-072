"""Build deterministic CATF review-fusion and provider-score artifacts.

This Phase 5 job treats Phase 1-4 files as immutable inputs. It applies the saved
ABSA and credibility models to all mapped reviews, aggregates review evidence by
the real Component 1 provider ID, and adds category-prior fallbacks for providers
without Component 4 review evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import tensorflow as tf

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from absa_inference import ABSAInference
from category_prior import category_prior, load_category_priors
from catf_ranking import CATFRanker
from catf_service import (
    ASPECTS,
    LABEL_ORDER,
    evidence_status,
    load_catf_config,
    load_weight_profiles,
    weights_for_category,
)
from credibility_inference import CredibilityInference
from train_credibility import (
    DEFAULT_CREDIBILITY,
    DEFAULT_REVIEWS,
    load_dataset,
)


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = COMPONENT_ROOT.parents[2]
DEFAULT_PROVIDERS = (
    REPOSITORY_ROOT
    / "packages"
    / "backend"
    / "app"
    / "components"
    / "component1"
    / "artifacts"
    / "providers.json"
)
DEFAULT_PRIORS = COMPONENT_ROOT / "data" / "processed" / "category_priors.json"
DEFAULT_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "catf-v1"
DEFAULT_REPORT_DIR = COMPONENT_ROOT / "reports" / "catf-v1"
ABSA_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "absa-v1"
CREDIBILITY_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "credibility-v1"


class CATFBuildError(ValueError):
    """Raised when Phase 5 inputs, preservation checks, or outputs are invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CATFBuildError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def file_metadata(path: Path) -> dict[str, Any]:
    return {
        "path": relative_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_component1_providers(path: Path) -> pd.DataFrame:
    require(path.is_file(), f"Component 1 provider dataset is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, list) and payload, "Component 1 providers must be a non-empty list")
    providers = pd.DataFrame(payload)
    required = {
        "provider_id",
        "provider_name",
        "category",
        "district",
        "city",
        "rating",
        "review_count",
    }
    require(
        required.issubset(providers.columns),
        f"Component 1 providers lack columns: {sorted(required - set(providers.columns))}",
    )
    require(providers["provider_id"].is_unique, "Component 1 provider IDs must be unique")
    require(providers[list(required)].notna().all().all(), "Component 1 provider fields cannot be null")
    return providers.sort_values("provider_id", kind="stable").reset_index(drop=True)


def predict_review_fusion(
    reviews: pd.DataFrame,
    *,
    absa: ABSAInference,
    credibility: CredibilityInference,
    batch_size: int,
) -> pd.DataFrame:
    texts = reviews["review_text"].astype(str).str.strip()
    require(texts.ne("").all(), "review text cannot be empty")
    absa_predictions = absa.model.predict(
        tf.constant(texts.tolist(), dtype=tf.string),
        batch_size=batch_size,
        verbose=0,
    )
    require(isinstance(absa_predictions, dict), "ABSA prediction must be a mapping")
    require(set(absa_predictions) == set(ASPECTS), "ABSA output heads differ from CATF aspects")

    credibility_predictions = credibility.predict(reviews)
    require(
        credibility_predictions["review_id"].tolist() == reviews["review_id"].tolist(),
        "credibility inference changed review order",
    )
    fusion = reviews[
        [
            "review_id",
            "provider_id",
            "source_provider_id",
            "service_type",
            "dataset_split",
            "rating",
        ]
    ].copy()
    fusion["credibility_score"] = credibility_predictions[
        "predicted_credibility_score"
    ].to_numpy(dtype=np.float64)
    fusion["predicted_is_fake_review"] = credibility_predictions[
        "predicted_is_fake_review"
    ].to_numpy(dtype=np.int8)

    credibility_values = fusion["credibility_score"].to_numpy(dtype=np.float64)
    for aspect in ASPECTS:
        probabilities = np.asarray(absa_predictions[aspect], dtype=np.float64)
        require(
            probabilities.shape == (len(fusion), len(LABEL_ORDER)),
            f"unexpected {aspect} probability shape: {probabilities.shape}",
        )
        require(np.isfinite(probabilities).all(), f"{aspect} probabilities must be finite")
        require(
            np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-4),
            f"{aspect} probabilities must sum to one",
        )
        fusion[f"{aspect}_positive_probability"] = probabilities[:, 0]
        fusion[f"{aspect}_neutral_probability"] = probabilities[:, 1]
        fusion[f"{aspect}_negative_probability"] = probabilities[:, 2]
        fusion[f"{aspect}_sentiment_score"] = probabilities[:, 0] - probabilities[:, 2]
        fusion[f"{aspect}_confidence"] = probabilities.max(axis=1)
        fusion[f"{aspect}_review_weight"] = (
            fusion[f"{aspect}_confidence"].to_numpy(dtype=np.float64)
            * credibility_values
        )

    require(len(fusion) == len(reviews), "review fusion changed the review count")
    require(fusion["review_id"].tolist() == reviews["review_id"].tolist(), "review order changed")
    require(fusion["provider_id"].tolist() == reviews["provider_id"].tolist(), "provider IDs changed")
    require(
        fusion["source_provider_id"].tolist() == reviews["source_provider_id"].tolist(),
        "source provider IDs changed",
    )
    return fusion


def aggregate_provider_evidence(
    fusion: pd.DataFrame,
    providers: pd.DataFrame,
    priors: dict[str, Any],
    profiles: dict[str, Any],
    config: dict[str, Any],
) -> pd.DataFrame:
    provider_categories = providers.set_index("provider_id")["category"]
    mapped_categories = fusion["provider_id"].map(provider_categories)
    require(mapped_categories.notna().all(), "a mapped review provider is absent from Component 1")
    require(
        mapped_categories.eq(fusion["service_type"]).all(),
        "mapped review categories differ from Component 1 provider categories",
    )

    working = fusion[["provider_id", "credibility_score"]].copy()
    for aspect in ASPECTS:
        working[f"{aspect}_numerator"] = (
            fusion[f"{aspect}_sentiment_score"] * fusion[f"{aspect}_review_weight"]
        )
        working[f"{aspect}_weight_sum"] = fusion[f"{aspect}_review_weight"]
    aggregation = {
        "credibility_score": ["count", "sum", "mean"],
        **{
            f"{aspect}_{suffix}": "sum"
            for aspect in ASPECTS
            for suffix in ("numerator", "weight_sum")
        },
    }
    grouped = working.groupby("provider_id", sort=True).agg(aggregation)
    grouped.columns = [
        "review_count",
        "effective_review_count",
        "mean_credibility",
        *[
            f"{aspect}_{suffix}"
            for aspect in ASPECTS
            for suffix in ("numerator", "weight_sum")
        ],
    ]
    grouped = grouped.reset_index()

    output = providers[
        [
            "provider_id",
            "provider_name",
            "category",
            "district",
            "city",
            "rating",
            "review_count",
        ]
    ].rename(
        columns={
            "rating": "component1_rating",
            "review_count": "component1_review_count",
        }
    )
    output = output.merge(grouped, on="provider_id", how="left", validate="one_to_one", sort=False)
    evidence_columns = [
        "review_count",
        "effective_review_count",
        "mean_credibility",
        *[
            f"{aspect}_{suffix}"
            for aspect in ASPECTS
            for suffix in ("numerator", "weight_sum")
        ],
    ]
    output[evidence_columns] = output[evidence_columns].fillna(0.0)
    output["review_count"] = output["review_count"].astype(np.int64)

    epsilon = float(config["epsilon"])
    for aspect in ASPECTS:
        output[f"{aspect}_score"] = output[f"{aspect}_numerator"] / (
            output[f"{aspect}_weight_sum"] + epsilon
        )
        output.drop(columns=f"{aspect}_numerator", inplace=True)

    category_weights = {
        category: weights_for_category(category, profiles)[0]
        for category in output["category"].unique()
    }
    for aspect in ASPECTS:
        output[f"{aspect}_category_weight"] = output["category"].map(
            {category: weights[aspect] for category, weights in category_weights.items()}
        )
    output["base_score"] = sum(
        output[f"{aspect}_score"] * output[f"{aspect}_category_weight"]
        for aspect in ASPECTS
    )
    output["normalized_base_score"] = ((output["base_score"] + 1.0) / 2.0).clip(0, 1)
    reliability_m = float(config["reliability_m"])
    output["reliability_factor"] = output["effective_review_count"] / (
        output["effective_review_count"] + reliability_m
    )
    output["category_prior"] = output["category"].map(
        lambda value: category_prior(str(value), priors)
    )
    output["final_catf_score"] = (
        output["reliability_factor"] * output["normalized_base_score"]
        + (1.0 - output["reliability_factor"]) * output["category_prior"]
    )
    output["evidence_status"] = [
        evidence_status(float(effective), int(count), config)
        for effective, count in zip(
            output["effective_review_count"],
            output["review_count"],
            strict=True,
        )
    ]
    output["score_source"] = np.where(
        output["review_count"].eq(0),
        "category_prior",
        "catf_evidence",
    )
    output["catf_version"] = config["version"]
    output["weight_version"] = profiles["version"]
    output["category_prior_version"] = priors["version"]

    require(len(output) == len(providers), "provider aggregation changed Component 1 count")
    require(output["provider_id"].tolist() == providers["provider_id"].tolist(), "provider order changed")
    require(output["provider_id"].is_unique, "provider aggregation introduced duplicate IDs")
    require(output["final_catf_score"].between(0, 1).all(), "final CATF scores out of range")
    require(
        output[[f"{aspect}_score" for aspect in ASPECTS]].apply(
            lambda column: column.between(-1, 1)
        ).all().all(),
        "provider aspect scores out of range",
    )
    numeric = output.select_dtypes(include=[np.number]).to_numpy(dtype=np.float64)
    require(np.isfinite(numeric).all(), "provider score output contains non-finite values")
    no_reviews = output["review_count"].eq(0)
    require(
        np.allclose(
            output.loc[no_reviews, "final_catf_score"],
            output.loc[no_reviews, "category_prior"],
        ),
        "no-review provider score differs from its category prior",
    )
    return output


def save_plots(scores: pd.DataFrame, report_dir: Path, reliability_m: float) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    score_distribution = report_dir / "provider_score_distribution.png"
    reliability_curve = report_dir / "reliability_curve.png"
    demo_ranking = report_dir / "demo_top5_ranking.png"

    fig, axis = plt.subplots(figsize=(9, 5.5))
    reviewed = scores["review_count"].gt(0)
    axis.hist(
        scores.loc[reviewed, "final_catf_score"],
        bins=30,
        alpha=0.78,
        label="CATF evidence",
        color="#2563eb",
    )
    axis.hist(
        scores.loc[~reviewed, "final_catf_score"],
        bins=20,
        alpha=0.65,
        label="Category-prior fallback",
        color="#f59e0b",
    )
    axis.set(title="Component 4 Provider CATF Score Distribution", xlabel="Final CATF score", ylabel="Providers")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(score_distribution, dpi=160)
    plt.close(fig)

    effective = np.linspace(0, 100, 501)
    reliability = effective / (effective + reliability_m)
    fig, axis = plt.subplots(figsize=(9, 5.5))
    axis.plot(effective, reliability, color="#0f766e", linewidth=2.5)
    axis.scatter(
        [reliability_m],
        [0.5],
        color="#dc2626",
        s=70,
        zorder=3,
        label=f"m = {reliability_m:g} gives reliability = 0.5",
    )
    axis.set(
        title="CATF Evidence Reliability Curve",
        xlabel="Effective review count (sum of credibility)",
        ylabel="Reliability factor",
        xlim=(0, 100),
        ylim=(0, 1),
    )
    axis.legend()
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(reliability_curve, dpi=160)
    plt.close(fig)

    top_reviewed = scores[scores["review_count"].gt(0)].nlargest(
        5,
        ["final_catf_score", "effective_review_count", "mean_credibility"],
    )
    require(not top_reviewed.empty, "at least one reviewed provider is required for the demo plot")
    fig, axis = plt.subplots(figsize=(9, 5.5))
    labels = top_reviewed["provider_id"].tolist()[::-1]
    values = top_reviewed["final_catf_score"].tolist()[::-1]
    bars = axis.barh(labels, values, color="#7c3aed")
    axis.bar_label(bars, fmt="%.4f", padding=4)
    axis.set(
        title="Deterministic Phase 5 Demo: CATF Top-5",
        xlabel="Final CATF score",
        ylabel="Provider ID",
        xlim=(0, max(values) * 1.12),
    )
    axis.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(demo_ranking, dpi=160)
    plt.close(fig)
    return {
        "provider_score_distribution": score_distribution,
        "reliability_curve": reliability_curve,
        "demo_top5_ranking": demo_ranking,
    }


def build_manifest(
    *,
    inputs: dict[str, Path],
    artifacts: dict[str, Path],
    reports: dict[str, Path],
    versions: dict[str, str],
    audit_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "catf_version": versions["catf_version"],
        "weight_version": versions["weight_version"],
        "category_prior_version": versions["category_prior_version"],
        "absa_model_version": versions["absa_model_version"],
        "credibility_model_version": versions["credibility_model_version"],
        "framework": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "tensorflow": tf.__version__,
            "platform": platform.platform(),
        },
        "inputs": {name: file_metadata(path) for name, path in inputs.items()},
        "artifacts": {name: file_metadata(path) for name, path in artifacts.items()},
        "reports": {name: file_metadata(path) for name, path in reports.items()},
        "preservation": audit_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--credibility-features", type=Path, default=DEFAULT_CREDIBILITY)
    parser.add_argument("--providers", type=Path, default=DEFAULT_PROVIDERS)
    parser.add_argument("--priors", type=Path, default=DEFAULT_PRIORS)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--batch-size", type=int, default=256)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(args.batch_size > 0, "batch size must be positive")
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    reviews = load_dataset(args.reviews, args.credibility_features)
    mapped_reviews = pd.read_csv(args.reviews)
    reviews["review_text"] = mapped_reviews["review_text"]
    require(
        reviews["review_id"].tolist() == mapped_reviews["review_id"].tolist(),
        "review text attachment changed review order",
    )
    providers = load_component1_providers(args.providers)
    priors = load_category_priors(args.priors)
    profiles = load_weight_profiles(args.artifact_dir / "category_aspect_weights.json")
    config = load_catf_config(args.artifact_dir / "catf_config.json")
    require(
        set(providers["category"]) == set(profiles["categories"]),
        "category weight profiles must cover every Component 1 category exactly",
    )
    require(
        set(providers["category"]) == set(priors["categories"]),
        "category priors must cover every Component 1 category exactly",
    )

    absa = ABSAInference(ABSA_ARTIFACT_DIR)
    credibility = CredibilityInference(CREDIBILITY_ARTIFACT_DIR)
    fusion = predict_review_fusion(
        reviews,
        absa=absa,
        credibility=credibility,
        batch_size=args.batch_size,
    )
    scores = aggregate_provider_evidence(fusion, providers, priors, profiles, config)

    review_fusion_path = args.report_dir / "review_fusion_predictions.csv"
    provider_scores_path = args.artifact_dir / "provider_catf_scores.csv"
    fusion.to_csv(review_fusion_path, index=False, lineterminator="\n", float_format="%.10g")
    scores.to_csv(provider_scores_path, index=False, lineterminator="\n", float_format="%.10g")

    reviewed_provider_count = int(scores["review_count"].gt(0).sum())
    no_review_provider_count = int(scores["review_count"].eq(0).sum())
    audit_summary = {
        "total_reviews": int(len(fusion)),
        "unique_source_providers": int(fusion["source_provider_id"].nunique()),
        "unique_mapped_review_providers": int(fusion["provider_id"].nunique()),
        "component1_providers": int(len(providers)),
        "providers_with_reviews": reviewed_provider_count,
        "providers_with_no_reviews": no_review_provider_count,
        "unmapped_review_records": 0,
        "category_mismatches": 0,
        "review_count_preserved": len(fusion) == len(reviews),
        "review_id_order_preserved": fusion["review_id"].tolist() == reviews["review_id"].tolist(),
        "mapped_provider_ids_preserved": fusion["provider_id"].tolist()
        == reviews["provider_id"].tolist(),
        "source_provider_ids_preserved": fusion["source_provider_id"].tolist()
        == reviews["source_provider_id"].tolist(),
        "all_provider_scores_finite_and_bounded": True,
        "all_no_review_providers_use_category_prior": True,
    }
    audit = {
        "phase": 5,
        "status": "passed",
        "summary": audit_summary,
        "evidence_status_counts": {
            str(key): int(value)
            for key, value in scores["evidence_status"].value_counts().sort_index().items()
        },
        "score_source_counts": {
            str(key): int(value)
            for key, value in scores["score_source"].value_counts().sort_index().items()
        },
        "score_statistics": {
            "minimum": float(scores["final_catf_score"].min()),
            "mean": float(scores["final_catf_score"].mean()),
            "maximum": float(scores["final_catf_score"].max()),
        },
        "weight_validation_status": profiles["validation_status"],
        "ranking_ground_truth_validation": "pending_phase8",
    }
    audit_path = args.report_dir / "catf_audit.json"
    write_json(audit_path, audit)
    plot_paths = save_plots(scores, args.report_dir, float(config["reliability_m"]))

    absa_manifest = absa.manifest
    credibility_manifest = credibility.manifest
    versions = {
        "catf_version": str(config["version"]),
        "weight_version": str(profiles["version"]),
        "category_prior_version": str(priors["version"]),
        "absa_model_version": str(absa_manifest["model_version"]),
        "credibility_model_version": str(credibility_manifest["model_version"]),
    }
    manifest_path = args.artifact_dir / "manifest.json"
    preliminary_manifest = {
        **versions,
        "status": "building_demo_contract",
    }
    write_json(manifest_path, preliminary_manifest)

    reviewed = scores[scores["review_count"].gt(0)].nlargest(
        5, ["final_catf_score", "effective_review_count"]
    )
    fallback = (
        scores[scores["review_count"].eq(0)]
        .sort_values("provider_id", kind="stable")
        .head(5)
    )
    demo_candidates = pd.concat([reviewed, fallback], ignore_index=True)[
        "provider_id"
    ].tolist()
    demo = CATFRanker(provider_scores_path, manifest_path).rank(
        demo_candidates,
        request_id="PHASE5-DETERMINISTIC-FIXTURE",
        top_k=5,
    )
    demo["candidate_source"] = "deterministic_phase5_fixture_not_component2"
    demo["integration_note"] = (
        "Replace this fixture with the Component 2 Top-10 provider IDs during Phase 6."
    )
    demo_path = args.report_dir / "demo_top10_to_top5.json"
    write_json(demo_path, demo)

    artifact_paths = {
        "provider_scores": provider_scores_path,
        "category_aspect_weights": args.artifact_dir / "category_aspect_weights.json",
        "catf_config": args.artifact_dir / "catf_config.json",
    }
    report_paths = {
        "audit": audit_path,
        "demo_top10_to_top5": demo_path,
        "review_fusion_predictions": review_fusion_path,
        **plot_paths,
    }
    input_paths = {
        "mapped_reviews": args.reviews,
        "credibility_features": args.credibility_features,
        "component1_providers": args.providers,
        "category_priors": args.priors,
        "absa_manifest": ABSA_ARTIFACT_DIR / "manifest.json",
        "credibility_manifest": CREDIBILITY_ARTIFACT_DIR / "manifest.json",
    }
    manifest = build_manifest(
        inputs=input_paths,
        artifacts=artifact_paths,
        reports=report_paths,
        versions=versions,
        audit_summary=audit_summary,
    )
    write_json(manifest_path, manifest)

    reranked = CATFRanker(provider_scores_path, manifest_path).rank(
        demo_candidates,
        request_id="PHASE5-DETERMINISTIC-FIXTURE",
        top_k=5,
    )
    require(
        reranked["providers"] == demo["providers"],
        "final manifest changed deterministic demo ranking",
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"Provider scores: {provider_scores_path.resolve()}")
    print(f"Review fusion: {review_fusion_path.resolve()}")
    print(f"Manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
