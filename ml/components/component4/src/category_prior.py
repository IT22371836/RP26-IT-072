"""Category-prior fallback used when a Component 1 provider has no review evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class CategoryPriorError(ValueError):
    """Raised when a category-prior artifact is missing or invalid."""


def validate_category_priors(payload: Mapping[str, Any]) -> None:
    if not payload.get("version"):
        raise CategoryPriorError("category-prior version is required")
    default_prior = float(payload.get("default_prior", -1))
    if not 0 <= default_prior <= 1:
        raise CategoryPriorError("default category prior must be between 0 and 1")

    categories = payload.get("categories")
    if not isinstance(categories, Mapping) or not categories:
        raise CategoryPriorError("at least one category-prior profile is required")
    for category, profile in categories.items():
        if not str(category).strip() or not isinstance(profile, Mapping):
            raise CategoryPriorError("category-prior profiles must be named mappings")
        prior = float(profile.get("prior", -1))
        if not 0 <= prior <= 1:
            raise CategoryPriorError(f"category prior for {category!r} must be between 0 and 1")


def load_category_priors(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CategoryPriorError(f"category-prior artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_category_priors(payload)
    return payload


def category_prior(category: str, payload: Mapping[str, Any]) -> float:
    validate_category_priors(payload)
    profile = payload["categories"].get(category)
    if profile is None:
        return float(payload["default_prior"])
    return float(profile["prior"])


def build_no_review_fallback(
    provider_id: str,
    category: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the deterministic CATF-compatible zero-evidence fallback shape."""

    prior = category_prior(category, payload)
    return {
        "provider_id": provider_id,
        "category": category,
        "aspect_scores": {
            "quality": 0.0,
            "punctuality": 0.0,
            "communication": 0.0,
            "professionalism": 0.0,
        },
        "effective_review_count": 0.0,
        "reliability_factor": 0.0,
        "final_score": prior,
        "evidence_status": "insufficient",
        "score_source": "category_prior",
        "prior_version": str(payload["version"]),
    }
