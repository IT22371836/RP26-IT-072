"""Evaluate Component 4 ranking against a leakage-safe held-out proxy target.

Phase 8 never treats its deterministic candidate groups as Component 2 output and
never claims that the rating/credibility proxy is production ground truth. Ranking
evidence comes only from train/validation reviews; proxy relevance comes only from
the test split.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = COMPONENT_ROOT.parents[2]
DEFAULT_REVIEWS = COMPONENT_ROOT / "data" / "processed" / "customer_reviews_mapped.csv"
DEFAULT_CREDIBILITY = COMPONENT_ROOT / "data" / "processed" / "review_credibility_clean.csv"
DEFAULT_FUSION = COMPONENT_ROOT / "reports" / "catf-v1" / "review_fusion_predictions.csv"
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
DEFAULT_CATF_DIR = COMPONENT_ROOT / "artifacts" / "catf-v1"
DEFAULT_CONFIG = COMPONENT_ROOT / "artifacts" / "evaluation-v1" / "evaluation_config.json"
DEFAULT_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "evaluation-v1"
DEFAULT_REPORT_DIR = COMPONENT_ROOT / "reports" / "evaluation-v1"

ASPECTS = ("quality", "punctuality", "communication", "professionalism")
METHODS = (
    "catf",
    "average_rating",
    "catf_no_credibility",
    "catf_uniform_weights",
)
METRICS = ("ndcg_at_5", "precision_at_5", "recall_at_5", "map_at_5")
EVALUATION_VERSION = "ranking-evaluation-v1"


class RankingEvaluationError(ValueError):
    """Raised when the Phase 8 evaluation contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RankingEvaluationError(message)


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


def load_json(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file(), f"{label} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{label} must be a JSON object")
    return payload


def load_evaluation_config(path: Path) -> dict[str, Any]:
    payload = load_json(path, "Phase 8 evaluation config")
    require(payload.get("version") == EVALUATION_VERSION, "evaluation version changed")
    split = payload.get("split_contract", {})
    require(split.get("ranking_evidence") == ["train", "validation"], "evidence split changed")
    require(split.get("proxy_ground_truth") == "test", "proxy split must be test")
    require(split.get("overlap_allowed") is False, "split overlap cannot be allowed")
    fixture = payload.get("candidate_fixture", {})
    require(int(fixture.get("candidate_count", 0)) == 10, "candidate count must be ten")
    require(int(fixture.get("top_k", 0)) == 5, "top_k must be five")
    require(fixture.get("category_consistent") is True, "fixtures must be category-consistent")
    require(fixture.get("real_component2_output") is False, "fixtures cannot claim Component 2")
    require(tuple(payload.get("methods", [])) == METHODS, "evaluation methods changed")
    require(tuple(payload.get("metrics", [])) == METRICS, "evaluation metrics changed")
    return payload


def load_provider_frame(path: Path) -> pd.DataFrame:
    require(path.is_file(), f"Component 1 provider dataset is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, list) and payload, "Component 1 providers must be a list")
    providers = pd.DataFrame(payload)
    required = {"provider_id", "category"}
    require(required.issubset(providers.columns), "Component 1 provider fields are missing")
    require(providers["provider_id"].is_unique, "Component 1 provider IDs must be unique")
    require(providers[list(required)].notna().all().all(), "provider fields cannot be null")
    return providers[["provider_id", "category"]].sort_values(
        "provider_id", kind="stable"
    ).reset_index(drop=True)


def load_weight_profiles(path: Path) -> dict[str, Any]:
    payload = load_json(path, "CATF category weight profiles")
    require(bool(payload.get("version")), "weight profile version is missing")
    categories = payload.get("categories")
    require(isinstance(categories, dict) and categories, "category weight profiles are missing")
    for category, weights in categories.items():
        require(set(weights) == set(ASPECTS), f"aspect weights changed for {category}")
        values = [float(weights[aspect]) for aspect in ASPECTS]
        require(all(math.isfinite(value) and 0 <= value <= 1 for value in values), "bad weights")
        require(math.isclose(sum(values), 1.0, abs_tol=1e-8), "aspect weights must sum to one")
    return payload


def validate_input_frames(
    reviews: pd.DataFrame,
    credibility: pd.DataFrame,
    fusion: pd.DataFrame,
    providers: pd.DataFrame,
) -> None:
    review_columns = {"review_id", "provider_id", "service_type", "dataset_split", "rating"}
    credibility_columns = {"review_id", "credibility_score", "is_fake_review"}
    fusion_columns = {
        "review_id",
        "provider_id",
        "service_type",
        "dataset_split",
        "credibility_score",
        *{
            f"{aspect}_{suffix}"
            for aspect in ASPECTS
            for suffix in ("sentiment_score", "confidence")
        },
    }
    require(review_columns.issubset(reviews.columns), "mapped review columns are missing")
    require(credibility_columns.issubset(credibility.columns), "credibility columns are missing")
    require(fusion_columns.issubset(fusion.columns), "review fusion columns are missing")
    for name, frame in (
        ("mapped reviews", reviews),
        ("credibility labels", credibility),
        ("fusion predictions", fusion),
    ):
        require(frame["review_id"].is_unique, f"{name} review IDs must be unique")
    require(set(reviews["dataset_split"]) == {"train", "validation", "test"}, "bad splits")
    require(set(fusion["review_id"]) == set(reviews["review_id"]), "fusion review IDs changed")

    review_contract = reviews.set_index("review_id")[
        ["provider_id", "service_type", "dataset_split"]
    ].sort_index()
    fusion_contract = fusion.set_index("review_id")[
        ["provider_id", "service_type", "dataset_split"]
    ].sort_index()
    require(review_contract.equals(fusion_contract), "fusion changed review identity or split")

    provider_categories = providers.set_index("provider_id")["category"]
    mapped_categories = reviews["provider_id"].map(provider_categories)
    require(mapped_categories.notna().all(), "a mapped provider is absent from Component 1")
    require(mapped_categories.eq(reviews["service_type"]).all(), "provider category mismatch")
    require(
        set(credibility["review_id"]) == set(reviews["review_id"]),
        "credibility review IDs changed",
    )


def build_proxy_ground_truth(
    reviews: pd.DataFrame,
    credibility: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate independent test rating and actual credibility into proxy relevance."""

    test_reviews = reviews.loc[
        reviews["dataset_split"].eq("test"),
        ["review_id", "provider_id", "service_type", "rating"],
    ].copy()
    test_reviews = test_reviews.merge(
        credibility[["review_id", "credibility_score", "is_fake_review"]],
        on="review_id",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    require(test_reviews[["credibility_score", "is_fake_review"]].notna().all().all(), "join failed")
    require(test_reviews["rating"].between(1, 5).all(), "test ratings must be in 1..5")
    require(
        test_reviews["credibility_score"].between(0, 1).all(),
        "actual credibility must be in 0..1",
    )
    test_reviews["review_proxy_relevance"] = (
        test_reviews["rating"].astype(float) / 5.0
    ) * test_reviews["credibility_score"].astype(float)

    proxy = (
        test_reviews.groupby(["provider_id", "service_type"], sort=True)
        .agg(
            proxy_relevance=("review_proxy_relevance", "mean"),
            test_review_count=("review_id", "count"),
            mean_test_rating=("rating", "mean"),
            mean_actual_credibility=("credibility_score", "mean"),
            actual_fake_review_rate=("is_fake_review", "mean"),
        )
        .reset_index()
        .rename(columns={"service_type": "category"})
    )
    require(proxy["provider_id"].is_unique, "proxy providers must be unique")
    require(proxy["proxy_relevance"].between(0, 1).all(), "proxy relevance out of range")
    numeric = proxy.select_dtypes(include=[np.number]).to_numpy(dtype=np.float64)
    require(np.isfinite(numeric).all(), "proxy contains non-finite values")
    return proxy.sort_values(["category", "provider_id"], kind="stable").reset_index(drop=True)


def _category_weight_columns(
    frame: pd.DataFrame,
    profiles: Mapping[str, Any],
    *,
    uniform: bool,
) -> pd.DataFrame:
    output = frame.copy()
    for aspect in ASPECTS:
        if uniform:
            output[f"{aspect}_category_weight"] = 1.0 / len(ASPECTS)
        else:
            mapping = {
                category: float(weights[aspect])
                for category, weights in profiles["categories"].items()
            }
            output[f"{aspect}_category_weight"] = output["category"].map(mapping)
            require(
                output[f"{aspect}_category_weight"].notna().all(),
                f"missing {aspect} category weight",
            )
    return output


def build_aspect_method_scores(
    fusion_evidence: pd.DataFrame,
    providers: pd.DataFrame,
    profiles: Mapping[str, Any],
    *,
    method: str,
    use_credibility: bool,
    uniform_weights: bool,
    reliability_m: float,
    epsilon: float,
) -> pd.DataFrame:
    require(method in METHODS, f"unknown method: {method}")
    require(not fusion_evidence["dataset_split"].eq("test").any(), "test leakage in evidence")
    working = fusion_evidence[["provider_id", "credibility_score"]].copy()
    working["evidence_value"] = (
        fusion_evidence["credibility_score"].astype(float) if use_credibility else 1.0
    )
    for aspect in ASPECTS:
        review_weight = fusion_evidence[f"{aspect}_confidence"].astype(float)
        if use_credibility:
            review_weight = review_weight * fusion_evidence["credibility_score"].astype(float)
        working[f"{aspect}_numerator"] = (
            fusion_evidence[f"{aspect}_sentiment_score"].astype(float) * review_weight
        )
        working[f"{aspect}_denominator"] = review_weight

    aggregation = {
        "credibility_score": ["count", "mean"],
        "evidence_value": "sum",
        **{
            f"{aspect}_{suffix}": "sum"
            for aspect in ASPECTS
            for suffix in ("numerator", "denominator")
        },
    }
    grouped = working.groupby("provider_id", sort=True).agg(aggregation)
    grouped.columns = [
        "review_count",
        "mean_predicted_credibility",
        "evidence_count",
        *[
            f"{aspect}_{suffix}"
            for aspect in ASPECTS
            for suffix in ("numerator", "denominator")
        ],
    ]
    grouped = grouped.reset_index()
    output = providers.merge(grouped, on="provider_id", how="left", validate="one_to_one")
    numeric_columns = [column for column in grouped.columns if column != "provider_id"]
    output[numeric_columns] = output[numeric_columns].fillna(0.0)
    output["review_count"] = output["review_count"].astype(int)
    for aspect in ASPECTS:
        output[f"{aspect}_score"] = output[f"{aspect}_numerator"] / (
            output[f"{aspect}_denominator"] + epsilon
        )

    output = _category_weight_columns(output, profiles, uniform=uniform_weights)
    output["normalized_base_score"] = (
        (
            sum(
                output[f"{aspect}_score"] * output[f"{aspect}_category_weight"]
                for aspect in ASPECTS
            )
            + 1.0
        )
        / 2.0
    ).clip(0, 1)
    reviewed = output["review_count"].gt(0)
    priors = (
        output.loc[reviewed]
        .groupby("category", sort=True)["normalized_base_score"]
        .mean()
        .to_dict()
    )
    require(set(priors) == set(providers["category"]), f"{method} priors lack a category")
    output["evaluation_category_prior"] = output["category"].map(priors)
    output["reliability_factor"] = output["evidence_count"] / (
        output["evidence_count"] + reliability_m
    )
    output["score"] = (
        output["reliability_factor"] * output["normalized_base_score"]
        + (1.0 - output["reliability_factor"]) * output["evaluation_category_prior"]
    )
    output["method"] = method
    require(output["score"].between(0, 1).all(), f"{method} score out of range")
    return output[
        ["provider_id", "category", "method", "score", "evidence_count", "review_count"]
    ].copy()


def build_average_rating_scores(
    review_evidence: pd.DataFrame,
    providers: pd.DataFrame,
    *,
    reliability_m: float,
) -> pd.DataFrame:
    require(not review_evidence["dataset_split"].eq("test").any(), "test leakage in evidence")
    working = review_evidence[["provider_id", "rating"]].copy()
    require(working["rating"].between(1, 5).all(), "evidence ratings must be in 1..5")
    working["normalized_rating"] = working["rating"].astype(float) / 5.0
    grouped = (
        working.groupby("provider_id", sort=True)
        .agg(
            normalized_base_score=("normalized_rating", "mean"),
            review_count=("normalized_rating", "count"),
        )
        .reset_index()
    )
    output = providers.merge(grouped, on="provider_id", how="left", validate="one_to_one")
    reviewed = output["review_count"].notna()
    priors = (
        output.loc[reviewed]
        .groupby("category", sort=True)["normalized_base_score"]
        .mean()
        .to_dict()
    )
    require(set(priors) == set(providers["category"]), "rating priors lack a category")
    output["evaluation_category_prior"] = output["category"].map(priors)
    output["review_count"] = output["review_count"].fillna(0).astype(int)
    output["normalized_base_score"] = output["normalized_base_score"].fillna(
        output["evaluation_category_prior"]
    )
    output["evidence_count"] = output["review_count"].astype(float)
    output["reliability_factor"] = output["evidence_count"] / (
        output["evidence_count"] + reliability_m
    )
    output["score"] = (
        output["reliability_factor"] * output["normalized_base_score"]
        + (1.0 - output["reliability_factor"]) * output["evaluation_category_prior"]
    )
    output["method"] = "average_rating"
    require(output["score"].between(0, 1).all(), "rating score out of range")
    return output[
        ["provider_id", "category", "method", "score", "evidence_count", "review_count"]
    ].copy()


def build_method_scores(
    reviews: pd.DataFrame,
    fusion: pd.DataFrame,
    providers: pd.DataFrame,
    profiles: Mapping[str, Any],
    catf_config: Mapping[str, Any],
) -> pd.DataFrame:
    evidence_splits = {"train", "validation"}
    review_evidence = reviews[reviews["dataset_split"].isin(evidence_splits)].copy()
    fusion_evidence = fusion[fusion["dataset_split"].isin(evidence_splits)].copy()
    require(
        not set(review_evidence["review_id"]) & set(reviews.loc[
            reviews["dataset_split"].eq("test"), "review_id"
        ]),
        "ranking evidence overlaps the test proxy split",
    )
    require(
        set(review_evidence["review_id"]) == set(fusion_evidence["review_id"]),
        "review and fusion evidence IDs differ",
    )
    reliability_m = float(catf_config["reliability_m"])
    epsilon = float(catf_config["epsilon"])
    frames = [
        build_aspect_method_scores(
            fusion_evidence,
            providers,
            profiles,
            method="catf",
            use_credibility=True,
            uniform_weights=False,
            reliability_m=reliability_m,
            epsilon=epsilon,
        ),
        build_average_rating_scores(
            review_evidence,
            providers,
            reliability_m=reliability_m,
        ),
        build_aspect_method_scores(
            fusion_evidence,
            providers,
            profiles,
            method="catf_no_credibility",
            use_credibility=False,
            uniform_weights=False,
            reliability_m=reliability_m,
            epsilon=epsilon,
        ),
        build_aspect_method_scores(
            fusion_evidence,
            providers,
            profiles,
            method="catf_uniform_weights",
            use_credibility=True,
            uniform_weights=True,
            reliability_m=reliability_m,
            epsilon=epsilon,
        ),
    ]
    scores = pd.concat(frames, ignore_index=True)
    require(
        len(scores) == len(providers) * len(METHODS),
        "method score count changed",
    )
    require(
        not scores.duplicated(["method", "provider_id"]).any(),
        "method scores contain duplicates",
    )
    return scores


def stable_candidate_key(seed: str, category: str, provider_id: str) -> str:
    value = f"{seed}|{category}|{provider_id}".encode()
    return hashlib.sha256(value).hexdigest()


def build_candidate_queries(
    proxy: pd.DataFrame,
    *,
    seed: str,
    candidate_count: int = 10,
) -> pd.DataFrame:
    require(candidate_count == 10, "Phase 8 fixtures require ten candidates")
    rows: list[dict[str, Any]] = []
    for category, category_proxy in proxy.groupby("category", sort=True):
        provider_ids = category_proxy["provider_id"].astype(str).tolist()
        require(
            len(provider_ids) >= candidate_count,
            f"category {category!r} has fewer than ten held-out providers",
        )
        ordered = sorted(
            provider_ids,
            key=lambda provider_id: (
                stable_candidate_key(seed, str(category), provider_id),
                provider_id,
            ),
        )
        category_token = hashlib.sha256(str(category).encode()).hexdigest()[:8].upper()
        for group_index, start in enumerate(range(0, len(ordered), candidate_count), start=1):
            primary = ordered[start : start + candidate_count]
            supplement_count = candidate_count - len(primary)
            candidates = primary + ordered[:supplement_count]
            query_id = f"EVAL-{category_token}-{group_index:03d}"
            for position, provider_id in enumerate(candidates, start=1):
                rows.append(
                    {
                        "query_id": query_id,
                        "category": category,
                        "candidate_position": position,
                        "provider_id": provider_id,
                        "is_supplement": position > len(primary),
                    }
                )

    queries = pd.DataFrame(rows)
    require(not queries.empty, "no evaluation queries were produced")
    require(
        queries.groupby("query_id").size().eq(candidate_count).all(),
        "every query must contain exactly ten candidates",
    )
    require(
        queries.groupby("query_id")["provider_id"].nunique().eq(candidate_count).all(),
        "query candidates must be unique",
    )
    require(
        queries.groupby("query_id")["category"].nunique().eq(1).all(),
        "query candidates must be category-consistent",
    )
    require(
        set(queries.loc[~queries["is_supplement"], "provider_id"]) == set(proxy["provider_id"]),
        "primary query assignments must cover every proxy provider exactly once",
    )
    require(
        not queries.loc[~queries["is_supplement"], "provider_id"].duplicated().any(),
        "a proxy provider has multiple primary query assignments",
    )
    return queries


def dcg_at_k(relevance: Sequence[float], k: int) -> float:
    values = np.asarray(list(relevance)[:k], dtype=np.float64)
    require(np.isfinite(values).all(), "relevance must be finite")
    require((values >= 0).all(), "relevance cannot be negative")
    if len(values) == 0:
        return 0.0
    discounts = np.log2(np.arange(2, len(values) + 2, dtype=np.float64))
    return float(np.sum(np.expm1(np.log(2.0) * values) / discounts))


def ndcg_at_k(ranked_relevance: Sequence[float], ideal_relevance: Sequence[float], k: int) -> float:
    ideal = dcg_at_k(ideal_relevance, k)
    if ideal == 0:
        return 1.0
    return dcg_at_k(ranked_relevance, k) / ideal


def binary_top_k_metrics(
    ranked_provider_ids: Sequence[str],
    relevant_provider_ids: Sequence[str],
    k: int,
) -> tuple[float, float, float]:
    ranked = list(ranked_provider_ids)[:k]
    relevant = set(relevant_provider_ids)
    require(len(relevant) >= k, "binary relevance must define at least k providers")
    hits = 0
    precision_sum = 0.0
    for rank, provider_id in enumerate(ranked, start=1):
        if provider_id in relevant:
            hits += 1
            precision_sum += hits / rank
    precision = hits / k
    recall = hits / len(relevant)
    average_precision = precision_sum / min(k, len(relevant))
    return precision, recall, average_precision


def evaluate_queries(
    queries: pd.DataFrame,
    proxy: pd.DataFrame,
    method_scores: pd.DataFrame,
    *,
    top_k: int,
) -> pd.DataFrame:
    proxy_index = proxy.set_index("provider_id")
    score_indexes = {
        method: method_scores[method_scores["method"].eq(method)].set_index("provider_id")
        for method in METHODS
    }
    rows: list[dict[str, Any]] = []
    for query_id, query in queries.groupby("query_id", sort=True):
        category = str(query["category"].iloc[0])
        candidate_ids = query.sort_values("candidate_position")["provider_id"].tolist()
        truth = proxy_index.loc[candidate_ids].reset_index()
        require(truth["category"].eq(category).all(), "proxy category mismatch")
        ideal = truth.sort_values(
            ["proxy_relevance", "test_review_count", "provider_id"],
            ascending=[False, False, True],
            kind="stable",
        )
        ideal_top_ids = ideal["provider_id"].head(top_k).tolist()
        ideal_relevance = ideal["proxy_relevance"].tolist()

        for method in METHODS:
            method_frame = score_indexes[method].loc[candidate_ids].reset_index()
            require(len(method_frame) == len(candidate_ids), f"{method} candidate score missing")
            require(method_frame["category"].eq(category).all(), f"{method} category mismatch")
            ranked = method_frame.sort_values(
                ["score", "evidence_count", "provider_id"],
                ascending=[False, False, True],
                kind="stable",
            )
            ranked_ids = ranked["provider_id"].tolist()
            relevance = proxy_index.loc[ranked_ids, "proxy_relevance"].astype(float).tolist()
            precision, recall, average_precision = binary_top_k_metrics(
                ranked_ids,
                ideal_top_ids,
                top_k,
            )
            rows.append(
                {
                    "query_id": query_id,
                    "category": category,
                    "method": method,
                    "candidate_count": len(candidate_ids),
                    "top_k": top_k,
                    "ndcg_at_5": ndcg_at_k(relevance, ideal_relevance, top_k),
                    "precision_at_5": precision,
                    "recall_at_5": recall,
                    "map_at_5": average_precision,
                    "selected_mean_proxy_relevance": float(
                        np.mean(relevance[:top_k])
                    ),
                    "ideal_mean_proxy_relevance": float(
                        ideal["proxy_relevance"].head(top_k).mean()
                    ),
                    "cold_start_candidates": int(ranked["review_count"].eq(0).sum()),
                    "ranked_provider_ids": "|".join(ranked_ids[:top_k]),
                    "ideal_provider_ids": "|".join(ideal_top_ids),
                }
            )
    metrics = pd.DataFrame(rows)
    require(
        len(metrics) == queries["query_id"].nunique() * len(METHODS),
        "query metric count changed",
    )
    require(metrics[list(METRICS)].apply(lambda column: column.between(0, 1)).all().all(), "bad metrics")
    return metrics.sort_values(["query_id", "method"], kind="stable").reset_index(drop=True)


def summarize_methods(query_metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for method in METHODS:
        frame = query_metrics[query_metrics["method"].eq(method)]
        row: dict[str, Any] = {
            "method": method,
            "query_count": len(frame),
        }
        for metric in METRICS:
            values = frame[metric].astype(float)
            mean = float(values.mean())
            standard_error = float(values.std(ddof=1) / math.sqrt(len(values)))
            row[metric] = mean
            row[f"{metric}_ci95_low"] = max(0.0, mean - 1.96 * standard_error)
            row[f"{metric}_ci95_high"] = min(1.0, mean + 1.96 * standard_error)
        row["selected_mean_proxy_relevance"] = float(
            frame["selected_mean_proxy_relevance"].mean()
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_categories(query_metrics: pd.DataFrame) -> pd.DataFrame:
    aggregations = {
        "query_id": "count",
        **{metric: "mean" for metric in METRICS},
        "selected_mean_proxy_relevance": "mean",
    }
    return query_metrics.groupby(["category", "method"], sort=True).agg(
        aggregations
    ).rename(columns={"query_id": "query_count"}).reset_index()


def paired_catf_deltas(query_metrics: pd.DataFrame) -> dict[str, dict[str, float]]:
    pivot = query_metrics.pivot(index="query_id", columns="method", values=list(METRICS))
    output: dict[str, dict[str, float]] = {}
    for baseline in METHODS:
        if baseline == "catf":
            continue
        output[baseline] = {
            metric: float((pivot[metric]["catf"] - pivot[metric][baseline]).mean())
            for metric in METRICS
        }
    return output


def save_plots(
    method_summary: pd.DataFrame,
    category_summary: pd.DataFrame,
    report_dir: Path,
) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    method_plot = report_dir / "ranking_method_comparison.png"
    category_plot = report_dir / "category_ndcg_at_5.png"

    positions = np.arange(len(method_summary))
    width = 0.19
    fig, axis = plt.subplots(figsize=(11, 6))
    for index, metric in enumerate(METRICS):
        axis.bar(
            positions + (index - 1.5) * width,
            method_summary[metric],
            width,
            label=metric.replace("_", " ").upper(),
        )
    axis.set(
        title="Phase 8 Held-out Proxy Ranking Evaluation",
        ylabel="Mean query score",
        ylim=(0, 1),
        xticks=positions,
        xticklabels=method_summary["method"].str.replace("_", " "),
    )
    axis.legend(ncol=2)
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(method_plot, dpi=160)
    plt.close(fig)

    ndcg = category_summary.pivot(index="category", columns="method", values="ndcg_at_5")
    ndcg = ndcg.loc[:, list(METHODS)]
    fig, axis = plt.subplots(figsize=(12, 7))
    image = axis.imshow(ndcg.to_numpy(), aspect="auto", vmin=0, vmax=1, cmap="viridis")
    axis.set(
        title="NDCG@5 by Service Category and Ranking Method",
        xlabel="Method",
        ylabel="Category",
        xticks=np.arange(len(ndcg.columns)),
        xticklabels=[value.replace("_", " ") for value in ndcg.columns],
        yticks=np.arange(len(ndcg.index)),
        yticklabels=ndcg.index,
    )
    fig.colorbar(image, ax=axis, label="Mean NDCG@5")
    fig.tight_layout()
    fig.savefig(category_plot, dpi=160)
    plt.close(fig)
    return {
        "ranking_method_comparison": method_plot,
        "category_ndcg_at_5": category_plot,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--credibility", type=Path, default=DEFAULT_CREDIBILITY)
    parser.add_argument("--fusion", type=Path, default=DEFAULT_FUSION)
    parser.add_argument("--providers", type=Path, default=DEFAULT_PROVIDERS)
    parser.add_argument("--catf-dir", type=Path, default=DEFAULT_CATF_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    evaluation_config = load_evaluation_config(args.config)
    catf_config_path = args.catf_dir / "catf_config.json"
    weight_profiles_path = args.catf_dir / "category_aspect_weights.json"
    phase5_manifest_path = args.catf_dir / "manifest.json"
    catf_config = load_json(catf_config_path, "CATF config")
    profiles = load_weight_profiles(weight_profiles_path)
    require(float(catf_config.get("reliability_m", 0)) > 0, "bad CATF reliability_m")
    require(float(catf_config.get("epsilon", 0)) > 0, "bad CATF epsilon")
    require(phase5_manifest_path.is_file(), "Phase 5 manifest is missing")

    for path, label in (
        (args.reviews, "mapped reviews"),
        (args.credibility, "actual credibility labels"),
        (args.fusion, "Phase 5 review fusion predictions"),
    ):
        require(path.is_file(), f"{label} are missing: {path}")
    reviews = pd.read_csv(args.reviews)
    credibility = pd.read_csv(args.credibility)
    fusion = pd.read_csv(args.fusion)
    providers = load_provider_frame(args.providers)
    validate_input_frames(reviews, credibility, fusion, providers)
    require(
        set(providers["category"]) == set(profiles["categories"]),
        "weight profiles must cover Component 1 categories exactly",
    )

    proxy = build_proxy_ground_truth(reviews, credibility)
    method_scores = build_method_scores(reviews, fusion, providers, profiles, catf_config)
    fixture = evaluation_config["candidate_fixture"]
    queries = build_candidate_queries(
        proxy,
        seed=str(fixture["seed"]),
        candidate_count=int(fixture["candidate_count"]),
    )
    query_metrics = evaluate_queries(
        queries,
        proxy,
        method_scores,
        top_k=int(fixture["top_k"]),
    )
    method_summary = summarize_methods(query_metrics)
    category_summary = summarize_categories(query_metrics)

    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    proxy_path = args.report_dir / "proxy_ground_truth.csv"
    queries_path = args.report_dir / "evaluation_queries.csv"
    query_metrics_path = args.report_dir / "query_metrics.csv"
    method_summary_path = args.report_dir / "method_metrics.csv"
    category_summary_path = args.report_dir / "category_metrics.csv"
    for frame, path in (
        (proxy, proxy_path),
        (queries, queries_path),
        (query_metrics, query_metrics_path),
        (method_summary, method_summary_path),
        (category_summary, category_summary_path),
    ):
        frame.to_csv(path, index=False, lineterminator="\n", float_format="%.10g")
    plot_paths = save_plots(method_summary, category_summary, args.report_dir)

    evidence_ids = set(reviews.loc[reviews["dataset_split"].ne("test"), "review_id"])
    proxy_ids = set(reviews.loc[reviews["dataset_split"].eq("test"), "review_id"])
    category_mismatches = int(
        (
            proxy["category"]
            != proxy["provider_id"].map(providers.set_index("provider_id")["category"])
        ).sum()
    )
    audit = {
        "phase": 8,
        "evaluation_version": EVALUATION_VERSION,
        "status": "passed",
        "validation_scope": evaluation_config["validation_scope"],
        "ranking_ground_truth_validation": "held_out_proxy_validated_phase8",
        "production_ground_truth_validation": (
            "pending_real_component2_and_independent_relevance_judgements"
        ),
        "candidate_source": "deterministic_category_fixture_not_component2",
        "proxy_definition": evaluation_config["proxy_relevance"],
        "summary": {
            "total_reviews": int(len(reviews)),
            "ranking_evidence_reviews": int(len(evidence_ids)),
            "heldout_proxy_reviews": int(len(proxy_ids)),
            "split_overlap_records": int(len(evidence_ids & proxy_ids)),
            "heldout_proxy_providers": int(proxy["provider_id"].nunique()),
            "component1_providers": int(len(providers)),
            "categories": int(proxy["category"].nunique()),
            "evaluation_queries": int(queries["query_id"].nunique()),
            "candidate_assignments": int(len(queries)),
            "unique_candidate_providers": int(queries["provider_id"].nunique()),
            "supplemental_assignments": int(queries["is_supplement"].sum()),
            "category_mismatches": category_mismatches,
            "candidate_count_per_query": int(fixture["candidate_count"]),
            "top_k": int(fixture["top_k"]),
            "methods_evaluated": len(METHODS),
        },
        "method_metrics": {
            str(row["method"]): {
                metric: float(row[metric])
                for metric in (*METRICS, "selected_mean_proxy_relevance")
            }
            for _, row in method_summary.iterrows()
        },
        "paired_catf_mean_deltas": paired_catf_deltas(query_metrics),
        "limitations": [
            "The held-out rating/actual-credibility target is a proxy, not human relevance ground truth.",
            "Candidate groups are category-consistent offline fixtures, not Component 2 output.",
            "Production validation requires real Component 2 candidates and independent judgements.",
        ],
    }
    require(audit["summary"]["split_overlap_records"] == 0, "evaluation split leakage")
    require(category_mismatches == 0, "proxy category mismatch")
    require(
        audit["summary"]["unique_candidate_providers"]
        == audit["summary"]["heldout_proxy_providers"],
        "candidate fixtures do not cover every held-out provider",
    )
    audit_path = args.report_dir / "ranking_evaluation.json"
    write_json(audit_path, audit)

    report_paths = {
        "ranking_evaluation": audit_path,
        "proxy_ground_truth": proxy_path,
        "evaluation_queries": queries_path,
        "query_metrics": query_metrics_path,
        "method_metrics": method_summary_path,
        "category_metrics": category_summary_path,
        **plot_paths,
    }
    input_paths = {
        "mapped_reviews": args.reviews,
        "actual_credibility_labels": args.credibility,
        "phase5_review_fusion_predictions": args.fusion,
        "component1_providers": args.providers,
        "phase5_manifest": phase5_manifest_path,
        "catf_config": catf_config_path,
        "category_aspect_weights": weight_profiles_path,
    }
    manifest = {
        "evaluation_version": EVALUATION_VERSION,
        "status": "passed",
        "validation_scope": evaluation_config["validation_scope"],
        "ranking_ground_truth_validation": audit["ranking_ground_truth_validation"],
        "production_ground_truth_validation": audit["production_ground_truth_validation"],
        "candidate_source": audit["candidate_source"],
        "framework": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "matplotlib": matplotlib.__version__,
            "platform": platform.platform(),
        },
        "inputs": {name: file_metadata(path) for name, path in input_paths.items()},
        "artifacts": {
            "evaluation_config": file_metadata(args.config),
        },
        "reports": {name: file_metadata(path) for name, path in report_paths.items()},
        "summary": audit["summary"],
    }
    manifest_path = args.artifact_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"Evaluation manifest: {manifest_path.resolve()}")
    return audit


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
