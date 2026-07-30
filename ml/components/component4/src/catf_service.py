"""Pure Category-Adaptive Trust Fusion (CATF) equations for Component 4."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHT_PROFILES = (
    COMPONENT_ROOT / "artifacts" / "catf-v1" / "category_aspect_weights.json"
)
DEFAULT_CATF_CONFIG = COMPONENT_ROOT / "artifacts" / "catf-v1" / "catf_config.json"

ASPECTS = ("quality", "punctuality", "communication", "professionalism")
LABEL_ORDER = ("Positive", "Neutral", "Negative")


class CATFError(ValueError):
    """Raised when CATF inputs or versioned configuration are invalid."""


@dataclass(frozen=True)
class ReviewPrediction:
    probabilities: Mapping[str, Sequence[float]]
    credibility: float


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CATFError(message)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"CATF artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"CATF artifact must be a JSON object: {path}")
    return payload


def validate_probability_vector(probabilities: Sequence[float]) -> tuple[float, float, float]:
    require(len(probabilities) == 3, "sentiment probability vectors must have length three")
    values = tuple(float(value) for value in probabilities)
    require(all(math.isfinite(value) for value in values), "probabilities must be finite")
    require(all(0 <= value <= 1 for value in values), "probabilities must be bounded 0..1")
    require(abs(sum(values) - 1.0) <= 1e-4, "sentiment probabilities must sum to one")
    return values


def signed_sentiment(probabilities: Sequence[float]) -> float:
    positive, _, negative = validate_probability_vector(probabilities)
    return positive - negative


def prediction_confidence(probabilities: Sequence[float]) -> float:
    return max(validate_probability_vector(probabilities))


def validate_aspect_weights(weights: Mapping[str, float]) -> dict[str, float]:
    require(set(weights) == set(ASPECTS), f"weights must contain exactly {list(ASPECTS)}")
    normalized = {aspect: float(weights[aspect]) for aspect in ASPECTS}
    require(
        all(math.isfinite(value) and 0 <= value <= 1 for value in normalized.values()),
        "aspect weights must be finite and bounded 0..1",
    )
    require(abs(sum(normalized.values()) - 1.0) <= 1e-8, "aspect weights must sum to one")
    return normalized


def validate_weight_profiles(payload: Mapping[str, Any]) -> None:
    require(bool(payload.get("version")), "weight profile version is required")
    require(isinstance(payload.get("categories"), Mapping), "category profiles are required")
    validate_aspect_weights(payload.get("default", {}))
    for category, weights in payload["categories"].items():
        require(bool(str(category).strip()), "category profile names cannot be empty")
        require(isinstance(weights, Mapping), f"weights for {category!r} must be a mapping")
        validate_aspect_weights(weights)


def load_weight_profiles(path: Path = DEFAULT_WEIGHT_PROFILES) -> dict[str, Any]:
    payload = load_json(path)
    validate_weight_profiles(payload)
    return payload


def weights_for_category(
    category: str,
    profiles: Mapping[str, Any],
) -> tuple[dict[str, float], str]:
    validate_weight_profiles(profiles)
    category_profiles = profiles["categories"]
    if category in category_profiles:
        return validate_aspect_weights(category_profiles[category]), "category_profile"
    return validate_aspect_weights(profiles["default"]), "default_profile"


def validate_catf_config(payload: Mapping[str, Any]) -> None:
    require(bool(payload.get("version")), "CATF version is required")
    reliability_m = float(payload.get("reliability_m", -1))
    epsilon = float(payload.get("epsilon", -1))
    require(math.isfinite(reliability_m) and reliability_m > 0, "reliability_m must be positive")
    require(math.isfinite(epsilon) and epsilon > 0, "epsilon must be positive")
    require(int(payload.get("maximum_candidates", 0)) == 10, "maximum candidates must be ten")
    require(int(payload.get("maximum_top_k", 0)) == 5, "maximum top_k must be five")
    thresholds = payload.get("evidence_thresholds", {})
    insufficient = float(thresholds.get("insufficient_effective_reviews_below", -1))
    sufficient = float(thresholds.get("sufficient_effective_reviews_at_least", -1))
    require(0 <= insufficient < sufficient, "evidence thresholds are invalid")


def load_catf_config(path: Path = DEFAULT_CATF_CONFIG) -> dict[str, Any]:
    payload = load_json(path)
    validate_catf_config(payload)
    return payload


def evidence_status(
    effective_review_count: float,
    review_count: int,
    config: Mapping[str, Any],
) -> str:
    validate_catf_config(config)
    if review_count == 0:
        return "insufficient"
    thresholds = config["evidence_thresholds"]
    if effective_review_count < float(
        thresholds["insufficient_effective_reviews_below"]
    ):
        return "insufficient"
    if effective_review_count < float(
        thresholds["sufficient_effective_reviews_at_least"]
    ):
        return "limited"
    return "sufficient"


def calculate_provider_score(
    predictions: Sequence[ReviewPrediction],
    category_weights: Mapping[str, float],
    category_prior: float,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate the PDF-specified CATF score with confidence and credibility weighting."""

    weights = validate_aspect_weights(category_weights)
    validate_catf_config(config)
    prior = float(category_prior)
    require(math.isfinite(prior) and 0 <= prior <= 1, "category prior must be bounded 0..1")
    epsilon = float(config["epsilon"])
    reliability_m = float(config["reliability_m"])

    if not predictions:
        return {
            "aspect_scores": {aspect: 0.0 for aspect in ASPECTS},
            "aspect_weight_sums": {aspect: 0.0 for aspect in ASPECTS},
            "review_count": 0,
            "mean_credibility": 0.0,
            "effective_review_count": 0.0,
            "reliability_factor": 0.0,
            "base_score": 0.0,
            "normalized_base_score": 0.5,
            "category_prior": prior,
            "final_catf_score": prior,
            "evidence_status": "insufficient",
            "score_source": "category_prior",
        }

    numerators = {aspect: 0.0 for aspect in ASPECTS}
    denominators = {aspect: 0.0 for aspect in ASPECTS}
    effective_count = 0.0
    credibility_sum = 0.0

    for item in predictions:
        credibility = float(item.credibility)
        require(math.isfinite(credibility), "credibility must be finite")
        credibility = min(1.0, max(0.0, credibility))
        credibility_sum += credibility
        effective_count += credibility
        require(
            set(item.probabilities) == set(ASPECTS),
            f"review probabilities must contain exactly {list(ASPECTS)}",
        )
        for aspect in ASPECTS:
            probabilities = item.probabilities[aspect]
            sentiment = signed_sentiment(probabilities)
            confidence = prediction_confidence(probabilities)
            review_weight = confidence * credibility
            numerators[aspect] += sentiment * review_weight
            denominators[aspect] += review_weight

    aspect_scores = {
        aspect: numerators[aspect] / (denominators[aspect] + epsilon)
        for aspect in ASPECTS
    }
    base_score = sum(weights[aspect] * aspect_scores[aspect] for aspect in ASPECTS)
    normalized_base = min(1.0, max(0.0, (base_score + 1.0) / 2.0))
    reliability = effective_count / (effective_count + reliability_m)
    final_score = reliability * normalized_base + (1.0 - reliability) * prior
    status = evidence_status(effective_count, len(predictions), config)

    require(all(-1 <= score <= 1 for score in aspect_scores.values()), "aspect score out of range")
    require(0 <= reliability <= 1, "reliability factor out of range")
    require(0 <= final_score <= 1, "final CATF score out of range")
    return {
        "aspect_scores": aspect_scores,
        "aspect_weight_sums": denominators,
        "review_count": int(len(predictions)),
        "mean_credibility": credibility_sum / len(predictions),
        "effective_review_count": effective_count,
        "reliability_factor": reliability,
        "base_score": base_score,
        "normalized_base_score": normalized_base,
        "category_prior": prior,
        "final_catf_score": final_score,
        "evidence_status": status,
        "score_source": "catf_evidence",
    }
