"""Train and evaluate the Component 4 review-credibility model.

The Phase 4 pipeline fits its scaler and Isolation Forest only on the training split,
calibrates the fake-review threshold only on validation labels, and evaluates once on the
held-out test split. Phase 1-3 data and artifacts are read-only inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
import matplotlib.pyplot as plt


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = COMPONENT_ROOT.parents[2]
DEFAULT_REVIEWS = COMPONENT_ROOT / "data" / "processed" / "customer_reviews_mapped.csv"
DEFAULT_CREDIBILITY = (
    COMPONENT_ROOT / "data" / "processed" / "review_credibility_clean.csv"
)
DEFAULT_ARTIFACT_DIR = COMPONENT_ROOT / "artifacts" / "credibility-v1"
DEFAULT_REPORT_DIR = COMPONENT_ROOT / "reports" / "credibility-v1"

MODEL_VERSION = "credibility-v1"
FEATURE_CONTRACT_VERSION = "credibility-features-v1"
THRESHOLD_VERSION = "validation-f1-threshold-v1"
NORMALIZATION_VERSION = "train-quantile-minmax-v1"
SEED = 42

FEATURE_COLUMNS = (
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
    "rating",
)
LEAKAGE_COLUMNS = (
    "is_fake_review",
    "credibility_score",
    "dataset_split",
    "review_id",
    "provider_id",
    "source_provider_id",
)
OUTPUT_COLUMNS = (
    "isolation_normality_score",
    "predicted_credibility_score",
    "predicted_is_fake_review",
)


class CredibilityTrainingError(ValueError):
    """Raised when a Phase 4 data or training contract is invalid."""


@dataclass(frozen=True)
class CredibilityConfig:
    seed: int = SEED
    n_estimators: int = 300
    contamination: str = "auto"
    max_samples: str = "auto"
    max_features: float = 1.0
    bootstrap: bool = False
    normalization_lower_quantile: float = 0.01
    normalization_upper_quantile: float = 0.99
    max_train_samples: int | None = None
    max_validation_samples: int | None = None
    max_test_samples: int | None = None
    smoke_test: bool = False


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CredibilityTrainingError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    try:
        display_path = path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        display_path = str(path.resolve())
    return {
        "path": display_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_reproducibility(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def load_dataset(reviews_path: Path, credibility_path: Path) -> pd.DataFrame:
    require(reviews_path.is_file(), f"mapped review dataset is missing: {reviews_path}")
    require(credibility_path.is_file(), f"credibility dataset is missing: {credibility_path}")
    reviews = pd.read_csv(reviews_path)
    credibility = pd.read_csv(credibility_path)

    required_reviews = {
        "review_id",
        "provider_id",
        "source_provider_id",
        "service_type",
        "rating",
        "review_text_group_id",
        "dataset_split",
        "verified_booking",
    }
    required_credibility = {
        "review_id",
        "is_fake_review",
        "credibility_score",
        *[column for column in FEATURE_COLUMNS if column != "rating"],
    }
    require(
        required_reviews.issubset(reviews.columns),
        f"reviews lack columns: {sorted(required_reviews - set(reviews.columns))}",
    )
    require(
        required_credibility.issubset(credibility.columns),
        f"credibility data lack columns: "
        f"{sorted(required_credibility - set(credibility.columns))}",
    )
    require(reviews["review_id"].is_unique, "review IDs must be unique")
    require(credibility["review_id"].is_unique, "credibility review IDs must be unique")
    require(
        set(reviews["review_id"]) == set(credibility["review_id"]),
        "review and credibility ID sets differ",
    )
    require(
        reviews.groupby("review_text_group_id")["dataset_split"].nunique().max() == 1,
        "a normalized text group crosses dataset splits",
    )
    require(
        set(reviews["dataset_split"]) == {"train", "validation", "test"},
        "train, validation, and test splits are required",
    )

    review_columns = [
        "review_id",
        "provider_id",
        "source_provider_id",
        "service_type",
        "rating",
        "review_text_group_id",
        "dataset_split",
        "verified_booking",
    ]
    merged = reviews[review_columns].merge(
        credibility,
        on="review_id",
        how="inner",
        validate="one_to_one",
        sort=False,
        suffixes=("_review", "_credibility"),
    )
    require(
        merged["review_id"].tolist() == reviews["review_id"].tolist(),
        "merged credibility rows no longer follow mapped-review order",
    )
    require(
        merged["verified_booking_review"].eq(
            merged["verified_booking_credibility"]
        ).all(),
        "verified_booking differs between reviews and credibility features",
    )
    merged = merged.rename(
        columns={"verified_booking_credibility": "verified_booking"}
    ).drop(columns=["verified_booking_review"])

    require(len(merged) == len(reviews), "credibility merge changed the review count")
    require(merged[list(FEATURE_COLUMNS)].notna().all().all(), "feature values cannot be null")
    feature_values = merged[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)
    require(np.isfinite(feature_values).all(), "feature values must be finite")
    require(
        set(merged["is_fake_review"].unique()) == {0, 1},
        "is_fake_review must contain exactly 0 and 1",
    )
    require(
        merged["credibility_score"].between(0, 1).all(),
        "source credibility scores must be bounded by 0 and 1",
    )
    require(
        not set(FEATURE_COLUMNS).intersection(LEAKAGE_COLUMNS),
        "the feature contract contains leakage columns",
    )
    return merged


def limit_split(frame: pd.DataFrame, maximum: int | None) -> pd.DataFrame:
    if maximum is None or len(frame) <= maximum:
        return frame.reset_index(drop=True)
    return frame.sort_values("review_id", kind="stable").head(maximum).reset_index(drop=True)


def split_dataset(
    frame: pd.DataFrame,
    config: CredibilityConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = limit_split(
        frame[frame["dataset_split"].eq("train")],
        config.max_train_samples,
    )
    validation = limit_split(
        frame[frame["dataset_split"].eq("validation")],
        config.max_validation_samples,
    )
    test = limit_split(
        frame[frame["dataset_split"].eq("test")],
        config.max_test_samples,
    )
    require(not train.empty and not validation.empty and not test.empty, "all splits must be non-empty")
    for name, split in (("train", train), ("validation", validation), ("test", test)):
        require(
            set(split["is_fake_review"]) == {0, 1},
            f"{name} split must contain both real and fake reviews",
        )
    return train, validation, test


def fit_pipeline(
    train: pd.DataFrame,
    config: CredibilityConfig,
) -> tuple[StandardScaler, IsolationForest, np.ndarray]:
    scaler = StandardScaler()
    train_features = scaler.fit_transform(train[list(FEATURE_COLUMNS)])
    model = IsolationForest(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        max_samples=config.max_samples,
        max_features=config.max_features,
        bootstrap=config.bootstrap,
        random_state=config.seed,
        n_jobs=1,
    )
    model.fit(train_features)
    train_normality = model.score_samples(train_features)
    require(np.isfinite(train_normality).all(), "training normality scores must be finite")
    return scaler, model, train_normality


def predict_normality(
    frame: pd.DataFrame,
    scaler: StandardScaler,
    model: IsolationForest,
) -> np.ndarray:
    features = scaler.transform(frame[list(FEATURE_COLUMNS)])
    scores = model.score_samples(features)
    require(np.isfinite(scores).all(), "normality scores must be finite")
    return scores


def select_fake_threshold(
    actual_fake: np.ndarray,
    normality_scores: np.ndarray,
) -> tuple[float, dict[str, Any], dict[str, np.ndarray]]:
    require(set(np.unique(actual_fake)) == {0, 1}, "threshold labels must contain 0 and 1")
    anomaly_scores = -np.asarray(normality_scores, dtype=np.float64)
    precision, recall, thresholds = precision_recall_curve(actual_fake, anomaly_scores)
    require(len(thresholds) > 0, "validation produced no threshold candidates")
    f1_values = (
        2
        * precision[:-1]
        * recall[:-1]
        / np.maximum(precision[:-1] + recall[:-1], np.finfo(float).eps)
    )
    maximum_f1 = float(np.max(f1_values))
    candidate_indices = np.flatnonzero(np.isclose(f1_values, maximum_f1, atol=1e-12))

    candidates: list[dict[str, float | int]] = []
    for index in candidate_indices:
        anomaly_threshold = float(thresholds[index])
        predicted = (anomaly_scores >= anomaly_threshold).astype(np.int32)
        candidates.append(
            {
                "index": int(index),
                "anomaly_threshold": anomaly_threshold,
                "normality_threshold": -anomaly_threshold,
                "f1": float(f1_values[index]),
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "balanced_accuracy": float(
                    balanced_accuracy_score(actual_fake, predicted)
                ),
            }
        )
    best = max(
        candidates,
        key=lambda item: (
            round(float(item["f1"]), 12),
            round(float(item["balanced_accuracy"]), 12),
            round(float(item["precision"]), 12),
            float(item["anomaly_threshold"]),
        ),
    )
    threshold = float(best["normality_threshold"])
    report = {
        **best,
        "selection_split": "validation",
        "objective": "fake_class_f1",
        "tie_breakers": ["balanced_accuracy", "precision", "higher_anomaly_threshold"],
        "candidate_count": int(len(thresholds)),
        "maximum_f1_candidate_count": int(len(candidate_indices)),
    }
    curve = {
        "anomaly_thresholds": thresholds,
        "precision": precision[:-1],
        "recall": recall[:-1],
        "f1": f1_values,
    }
    return threshold, report, curve


def normalization_bounds(
    train_normality: np.ndarray,
    config: CredibilityConfig,
) -> tuple[float, float]:
    lower = float(
        np.quantile(train_normality, config.normalization_lower_quantile)
    )
    upper = float(
        np.quantile(train_normality, config.normalization_upper_quantile)
    )
    require(np.isfinite(lower) and np.isfinite(upper), "normalization bounds must be finite")
    require(upper > lower, "normalization upper bound must exceed lower bound")
    return lower, upper


def normality_to_credibility(
    normality_scores: np.ndarray,
    lower_bound: float,
    upper_bound: float,
) -> np.ndarray:
    require(upper_bound > lower_bound, "invalid credibility normalization bounds")
    normalized = (np.asarray(normality_scores) - lower_bound) / (
        upper_bound - lower_bound
    )
    return np.clip(normalized, 0.0, 1.0)


def predict_fake(normality_scores: np.ndarray, normality_threshold: float) -> np.ndarray:
    return (np.asarray(normality_scores) <= normality_threshold).astype(np.int32)


def evaluate_split(
    frame: pd.DataFrame,
    normality_scores: np.ndarray,
    normality_threshold: float,
    lower_bound: float,
    upper_bound: float,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    actual = frame["is_fake_review"].to_numpy(dtype=np.int32)
    predicted = predict_fake(normality_scores, normality_threshold)
    predicted_credibility = normality_to_credibility(
        normality_scores,
        lower_bound,
        upper_bound,
    )
    precision, recall, f1, support = precision_recall_fscore_support(
        actual,
        predicted,
        labels=[0, 1],
        zero_division=0,
    )
    report = {
        "rows": int(len(frame)),
        "actual_fake_rate": float(actual.mean()),
        "predicted_fake_rate": float(predicted.mean()),
        "accuracy": float(accuracy_score(actual, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, predicted)),
        "fake_precision": float(precision[1]),
        "fake_recall": float(recall[1]),
        "fake_f1": float(f1[1]),
        "macro_f1": float(f1_score(actual, predicted, average="macro")),
        "roc_auc": float(roc_auc_score(actual, -normality_scores)),
        "average_precision": float(
            average_precision_score(actual, -normality_scores)
        ),
        "confusion_matrix": confusion_matrix(actual, predicted, labels=[0, 1]).tolist(),
        "per_class": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(("real", "fake"))
        },
        "classification_report": classification_report(
            actual,
            predicted,
            labels=[0, 1],
            target_names=["real", "fake"],
            output_dict=True,
            zero_division=0,
        ),
        "predicted_credibility": {
            "minimum": float(predicted_credibility.min()),
            "maximum": float(predicted_credibility.max()),
            "mean": float(predicted_credibility.mean()),
            "source_score_mae": float(
                np.mean(
                    np.abs(
                        predicted_credibility
                        - frame["credibility_score"].to_numpy(dtype=np.float64)
                    )
                )
            ),
            "source_score_spearman": float(
                pd.Series(predicted_credibility).corr(
                    frame["credibility_score"].reset_index(drop=True),
                    method="spearman",
                )
            ),
        },
    }
    return report, predicted, predicted_credibility


def prediction_frame(
    frame: pd.DataFrame,
    normality_scores: np.ndarray,
    predicted_fake: np.ndarray,
    predicted_credibility: np.ndarray,
) -> pd.DataFrame:
    output = frame[
        [
            "review_id",
            "provider_id",
            "source_provider_id",
            "service_type",
            "dataset_split",
            "is_fake_review",
            "credibility_score",
        ]
    ].copy()
    output["isolation_normality_score"] = normality_scores
    output["predicted_credibility_score"] = predicted_credibility
    output["predicted_is_fake_review"] = predicted_fake
    return output


def plot_confusion_matrix(matrix: np.ndarray, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(6.5, 5.5))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_title("Phase 4 fake-review detection — test split")
    axis.set_xlabel("Predicted")
    axis.set_ylabel("Actual")
    axis.set_xticks([0, 1], ["Real", "Fake"])
    axis.set_yticks([0, 1], ["Real", "Fake"])
    for row in range(2):
        for column in range(2):
            axis.text(
                column,
                row,
                str(int(matrix[row, column])),
                ha="center",
                va="center",
                fontsize=12,
            )
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.tight_layout()
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_score_distribution(
    frame: pd.DataFrame,
    predicted_credibility: np.ndarray,
    path: Path,
) -> None:
    actual = frame["is_fake_review"].to_numpy(dtype=np.int32)
    figure, axis = plt.subplots(figsize=(9, 5.5))
    bins = np.linspace(0, 1, 31)
    axis.hist(
        predicted_credibility[actual == 0],
        bins=bins,
        alpha=0.68,
        density=True,
        label="Actual real",
        color="#2E86AB",
    )
    axis.hist(
        predicted_credibility[actual == 1],
        bins=bins,
        alpha=0.68,
        density=True,
        label="Actual fake",
        color="#D1495B",
    )
    axis.set_title("Predicted credibility distribution — held-out test split")
    axis.set_xlabel("Predicted credibility score")
    axis.set_ylabel("Density")
    axis.set_xlim(0, 1)
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_threshold_curve(
    curve: dict[str, np.ndarray],
    selected_report: dict[str, Any],
    path: Path,
) -> None:
    thresholds = curve["anomaly_thresholds"]
    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.plot(thresholds, curve["precision"], label="Fake precision")
    axis.plot(thresholds, curve["recall"], label="Fake recall")
    axis.plot(thresholds, curve["f1"], label="Fake F1", linewidth=2)
    axis.axvline(
        float(selected_report["anomaly_threshold"]),
        color="black",
        linestyle="--",
        label="Selected validation threshold",
    )
    axis.set_title("Validation-only fake-review threshold calibration")
    axis.set_xlabel("Isolation anomaly score threshold (higher = more anomalous)")
    axis.set_ylabel("Metric")
    axis.set_ylim(0, 1.02)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=170)
    plt.close(figure)


def save_model_summary(
    path: Path,
    config: CredibilityConfig,
    threshold_report: dict[str, Any],
    lower_bound: float,
    upper_bound: float,
    split_counts: dict[str, int],
) -> None:
    lines = [
        "Component 4 Phase 4 Review Credibility Model",
        f"model_version: {MODEL_VERSION}",
        "pipeline: StandardScaler -> IsolationForest -> validation-calibrated threshold",
        f"features ({len(FEATURE_COLUMNS)}): {', '.join(FEATURE_COLUMNS)}",
        f"excluded leakage columns: {', '.join(LEAKAGE_COLUMNS)}",
        f"n_estimators: {config.n_estimators}",
        f"random_seed: {config.seed}",
        f"normality_threshold: {threshold_report['normality_threshold']:.12f}",
        f"validation_fake_f1: {threshold_report['f1']:.12f}",
        f"normalization_lower_bound: {lower_bound:.12f}",
        f"normalization_upper_bound: {upper_bound:.12f}",
        f"split_counts: {split_counts}",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def train(
    reviews_path: Path,
    credibility_path: Path,
    artifact_dir: Path,
    report_dir: Path,
    config: CredibilityConfig,
) -> dict[str, Any]:
    set_reproducibility(config.seed)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    data = load_dataset(reviews_path, credibility_path)
    train_frame, validation_frame, test_frame = split_dataset(data, config)
    scaler, model, train_normality = fit_pipeline(train_frame, config)
    validation_normality = predict_normality(validation_frame, scaler, model)
    test_normality = predict_normality(test_frame, scaler, model)
    threshold, threshold_report, threshold_curve = select_fake_threshold(
        validation_frame["is_fake_review"].to_numpy(dtype=np.int32),
        validation_normality,
    )
    lower_bound, upper_bound = normalization_bounds(train_normality, config)

    train_metrics, train_fake, train_credibility = evaluate_split(
        train_frame,
        train_normality,
        threshold,
        lower_bound,
        upper_bound,
    )
    validation_metrics, validation_fake, validation_credibility = evaluate_split(
        validation_frame,
        validation_normality,
        threshold,
        lower_bound,
        upper_bound,
    )
    test_metrics, test_fake, test_credibility = evaluate_split(
        test_frame,
        test_normality,
        threshold,
        lower_bound,
        upper_bound,
    )

    predictions = pd.concat(
        [
            prediction_frame(
                train_frame,
                train_normality,
                train_fake,
                train_credibility,
            ),
            prediction_frame(
                validation_frame,
                validation_normality,
                validation_fake,
                validation_credibility,
            ),
            prediction_frame(
                test_frame,
                test_normality,
                test_fake,
                test_credibility,
            ),
        ],
        ignore_index=True,
    )
    selected_review_ids = set(predictions["review_id"])
    selected_input_order = data.loc[
        data["review_id"].isin(selected_review_ids),
        ["review_id"],
    ]
    predictions = (
        selected_input_order
        .merge(predictions, on="review_id", validate="one_to_one", sort=False)
    )
    expected_prediction_rows = len(train_frame) + len(validation_frame) + len(test_frame)
    require(
        len(predictions) == expected_prediction_rows,
        "prediction output changed the modeled review count",
    )
    require(
        predictions["review_id"].tolist() == selected_input_order["review_id"].tolist(),
        "prediction output changed review order",
    )

    model_path = artifact_dir / "credibility_pipeline.joblib"
    feature_contract_path = artifact_dir / "feature_contract.json"
    training_config_path = artifact_dir / "training_config.json"
    metrics_path = report_dir / "credibility_metrics.json"
    predictions_path = report_dir / "credibility_predictions.csv"
    confusion_path = report_dir / "credibility_confusion_matrix.png"
    distribution_path = report_dir / "credibility_score_distribution.png"
    threshold_curve_path = report_dir / "credibility_threshold_curve.png"
    model_summary_path = report_dir / "credibility_model_summary.txt"

    bundle = {
        "model_version": MODEL_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "threshold_version": THRESHOLD_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "feature_columns": list(FEATURE_COLUMNS),
        "scaler": scaler,
        "isolation_forest": model,
        "normality_threshold": threshold,
        "normalization_lower_bound": lower_bound,
        "normalization_upper_bound": upper_bound,
    }
    joblib.dump(bundle, model_path, compress=3)
    write_json(
        feature_contract_path,
        {
            "version": FEATURE_CONTRACT_VERSION,
            "input_features": list(FEATURE_COLUMNS),
            "input_dtype": "finite numeric",
            "excluded_leakage_columns": list(LEAKAGE_COLUMNS),
            "outputs": list(OUTPUT_COLUMNS),
            "fake_label": {"real": 0, "fake": 1},
            "score_semantics": {
                "isolation_normality_score": "higher means more normal",
                "predicted_credibility_score": "bounded 0..1; higher means more credible",
                "predicted_is_fake_review": "1 when normality <= validation threshold",
            },
        },
    )
    split_counts = {
        "train": int(len(train_frame)),
        "validation": int(len(validation_frame)),
        "test": int(len(test_frame)),
    }
    write_json(
        training_config_path,
        {
            **asdict(config),
            "model_version": MODEL_VERSION,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "threshold_version": THRESHOLD_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
            "split_counts": split_counts,
            "normality_threshold": threshold,
            "normalization_bounds": {
                "lower": lower_bound,
                "upper": upper_bound,
            },
            "threshold_selection": threshold_report,
        },
    )
    metrics = {
        "model_version": MODEL_VERSION,
        "headline_split": "test",
        "test": test_metrics,
        "validation": validation_metrics,
        "train": train_metrics,
        "threshold_selection": threshold_report,
        "normalization": {
            "version": NORMALIZATION_VERSION,
            "fit_split": "train",
            "lower_quantile": config.normalization_lower_quantile,
            "upper_quantile": config.normalization_upper_quantile,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
        },
        "feature_columns": list(FEATURE_COLUMNS),
        "leakage_columns_excluded": list(LEAKAGE_COLUMNS),
    }
    fake_rate_shift = (
        test_metrics["actual_fake_rate"] - validation_metrics["actual_fake_rate"]
    )
    fake_f1_change = test_metrics["fake_f1"] - validation_metrics["fake_f1"]
    distribution_shift_audit = {
        "actual_fake_rate_by_split": {
            "train": train_metrics["actual_fake_rate"],
            "validation": validation_metrics["actual_fake_rate"],
            "test": test_metrics["actual_fake_rate"],
        },
        "test_minus_validation_fake_rate": float(fake_rate_shift),
        "test_minus_validation_fake_f1": float(fake_f1_change),
        "flagged": bool(abs(fake_rate_shift) > 0.05 or fake_f1_change < -0.15),
        "flag_rules": {
            "absolute_fake_rate_change": "> 0.05",
            "fake_f1_drop": "< -0.15",
        },
        "action": (
            "Report held-out performance without retuning on test. Preserve continuous "
            "credibility scores for downstream CATF and recalibrate only with future "
            "non-test production labels."
        ),
    }
    metrics["distribution_shift_audit"] = distribution_shift_audit
    write_json(metrics_path, metrics)
    predictions.to_csv(predictions_path, index=False, lineterminator="\n")
    plot_confusion_matrix(np.asarray(test_metrics["confusion_matrix"]), confusion_path)
    plot_score_distribution(test_frame, test_credibility, distribution_path)
    plot_threshold_curve(threshold_curve, threshold_report, threshold_curve_path)
    save_model_summary(
        model_summary_path,
        config,
        threshold_report,
        lower_bound,
        upper_bound,
        split_counts,
    )

    manifest = {
        "model_version": MODEL_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "threshold_version": THRESHOLD_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "framework": {
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "method": {
            "scaler": "StandardScaler",
            "detector": "IsolationForest",
            "fit_split": "train",
            "threshold_selection_split": "validation",
            "evaluation_split": "test",
            "n_estimators": config.n_estimators,
            "random_seed": config.seed,
            "features": list(FEATURE_COLUMNS),
        },
        "inputs": {
            "mapped_reviews": file_metadata(reviews_path),
            "credibility_features": file_metadata(credibility_path),
        },
        "artifacts": {
            "pipeline": file_metadata(model_path),
            "feature_contract": file_metadata(feature_contract_path),
            "training_config": file_metadata(training_config_path),
        },
        "reports": {
            "metrics": file_metadata(metrics_path),
            "predictions": file_metadata(predictions_path),
            "confusion_matrix": file_metadata(confusion_path),
            "score_distribution": file_metadata(distribution_path),
            "threshold_curve": file_metadata(threshold_curve_path),
            "model_summary": file_metadata(model_summary_path),
        },
        "metrics_summary": {
            "test_accuracy": test_metrics["accuracy"],
            "test_balanced_accuracy": test_metrics["balanced_accuracy"],
            "test_fake_precision": test_metrics["fake_precision"],
            "test_fake_recall": test_metrics["fake_recall"],
            "test_fake_f1": test_metrics["fake_f1"],
            "test_roc_auc": test_metrics["roc_auc"],
            "test_average_precision": test_metrics["average_precision"],
            "distribution_shift_flagged": distribution_shift_audit["flagged"],
        },
        "preservation": {
            "input_reviews": int(len(data)),
            "modeled_reviews": int(expected_prediction_rows),
            "output_predictions": int(len(predictions)),
            "review_id_order_preserved": True,
            "provider_ids_preserved": True,
            "source_provider_ids_preserved": True,
        },
        "smoke_test": config.smoke_test,
    }
    manifest_path = artifact_dir / "manifest.json"
    write_json(manifest_path, manifest)

    print("Component 4 Phase 4 credibility training completed.")
    print(f"Pipeline: {model_path}")
    print(f"Test fake-review F1: {test_metrics['fake_f1']:.4f}")
    print(f"Test ROC-AUC: {test_metrics['roc_auc']:.4f}")
    print(f"Metrics: {metrics_path}")
    return manifest


def smoke_config(base: CredibilityConfig) -> CredibilityConfig:
    values = asdict(base)
    values.update(
        {
            "n_estimators": 50,
            "max_train_samples": 1_000,
            "max_validation_samples": 300,
            "max_test_samples": 300,
            "smoke_test": True,
        }
    )
    return CredibilityConfig(**values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--credibility", type=Path, default=DEFAULT_CREDIBILITY)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--smoke-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CredibilityConfig(n_estimators=args.n_estimators)
    if args.smoke_test:
        config = smoke_config(config)
    train(
        reviews_path=args.reviews.resolve(),
        credibility_path=args.credibility.resolve(),
        artifact_dir=args.artifact_dir.resolve(),
        report_dir=args.report_dir.resolve(),
        config=config,
    )


if __name__ == "__main__":
    main()
