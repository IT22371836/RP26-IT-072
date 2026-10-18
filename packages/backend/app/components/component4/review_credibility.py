from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.components.component4.service import REPOSITORY_ROOT


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
ARTIFACT_PATH = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "artifacts"
    / "credibility-v1"
    / "credibility_pipeline.joblib"
)
WORD_PATTERN = re.compile(r"\b[\w']+\b", re.UNICODE)
URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{2,}", re.IGNORECASE)


@lru_cache
def _model_bundle() -> dict[str, Any]:
    bundle = joblib.load(ARTIFACT_PATH)
    if tuple(bundle.get("feature_columns", ())) != FEATURE_COLUMNS:
        raise ValueError("Component 4 credibility feature contract mismatch")
    return bundle


def score_platform_review(
    review_text: str | None,
    rating: int,
    *,
    duplicate_pattern: bool = False,
    reviewer_review_count_24h: int = 1,
) -> dict[str, Any]:
    """Score a verified platform review with the trained credibility-v1 model."""

    text = review_text or ""
    words = WORD_PATTERN.findall(text)
    normalized_words = [word.casefold() for word in words]
    features = {
        "word_count": len(words),
        "exclamation_count": text.count("!"),
        "caps_word_count": sum(word.isupper() and len(word) > 1 for word in words),
        "repeated_char_count": len(REPEATED_CHAR_PATTERN.findall(text)),
        "unique_word_ratio": (
            len(set(normalized_words)) / len(normalized_words) if normalized_words else 0.0
        ),
        "url_count": len(URL_PATTERN.findall(text)),
        "duplicate_pattern": int(duplicate_pattern),
        "extreme_rating": int(rating in (1, 5)),
        "verified_booking": 1,
        "reviewer_review_count_24h": max(1, int(reviewer_review_count_24h)),
        "rating": int(rating),
    }
    bundle = _model_bundle()
    values = pd.DataFrame(
        [[features[name] for name in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS
    ).astype(np.float64)
    scaled = bundle["scaler"].transform(values)
    normality = float(bundle["isolation_forest"].score_samples(scaled)[0])
    lower = float(bundle["normalization_lower_bound"])
    upper = float(bundle["normalization_upper_bound"])
    credibility = float(np.clip((normality - lower) / (upper - lower), 0.0, 1.0))
    return {
        "credibility_score": credibility,
        "predicted_is_fake_review": normality <= float(bundle["normality_threshold"]),
        "credibility_normality_score": normality,
        "credibility_model_version": str(bundle["model_version"]),
        "credibility_features": features,
    }
