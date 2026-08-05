from __future__ import annotations

import csv
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.components.component1.service import HybridRecommendationEngine
from app.components.component4.service import (
    REPOSITORY_ROOT,
    Component4RankingEngine,
    UnknownProviderError,
)
from app.repositories.interactions import InteractionRepository
from app.schemas.provider import ProviderTrustProfile

DEFAULT_RAW_REVIEWS = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "data"
    / "raw"
    / "customer_reviews_25k.csv"
)
DEFAULT_PROVIDER_MAP = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "data"
    / "processed"
    / "provider_id_map.csv"
)
DEFAULT_CREDIBILITY = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "data"
    / "raw"
    / "review_credibility_25k.csv"
)


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


class ResearchReviewIndex:
    """Privacy-safe credible review samples indexed by canonical Component 1 provider ID."""

    def __init__(
        self,
        reviews_path: Path = DEFAULT_RAW_REVIEWS,
        provider_map_path: Path = DEFAULT_PROVIDER_MAP,
        credibility_path: Path = DEFAULT_CREDIBILITY,
    ) -> None:
        self.reviews_path = reviews_path
        self.provider_map_path = provider_map_path
        self.credibility_path = credibility_path
        self._reviews: dict[str, list[dict[str, Any]]] = {}

    def load(self) -> None:
        source_to_provider: dict[str, str] = {}
        with self.provider_map_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                source_to_provider[row["source_provider_id"]] = row["provider_id"]

        credibility: dict[str, tuple[bool, float]] = {}
        with self.credibility_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                credibility[row["review_id"]] = (
                    row["is_fake_review"].strip() == "1",
                    float(row["credibility_score"]),
                )

        indexed: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        with self.reviews_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                provider_id = source_to_provider.get(row["provider_id"])
                credibility_record = credibility.get(row["review_id"])
                if provider_id is None or credibility_record is None:
                    continue
                is_fake, credibility_score = credibility_record
                if is_fake:
                    continue
                indexed[provider_id].append(
                    {
                        "rating": int(row["rating"]),
                        "review_text": row["review_text"].strip() or None,
                        "reviewed_at": _utc_datetime(row["review_date"]),
                        "verified_booking": row["verified_booking"].strip() == "1",
                        "source": "research_dataset",
                        "credibility_score": credibility_score,
                    }
                )
        self._reviews = {
            provider_id: sorted(
                reviews,
                key=lambda review: review["reviewed_at"],
                reverse=True,
            )
            for provider_id, reviews in indexed.items()
        }

    def for_provider(self, provider_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return list(self._reviews.get(provider_id, ()))[:limit]


@lru_cache
def get_research_review_index() -> ResearchReviewIndex:
    index = ResearchReviewIndex()
    index.load()
    return index


class ProviderTrustProfileService:
    def __init__(
        self,
        component1: HybridRecommendationEngine,
        component4: Component4RankingEngine,
        interactions: InteractionRepository,
        research_reviews: ResearchReviewIndex | None = None,
    ) -> None:
        self.component1 = component1
        self.component4 = component4
        self.interactions = interactions
        self.research_reviews = research_reviews or get_research_review_index()

    async def build(
        self,
        provider_id: str,
        live_provider: dict[str, Any] | None,
    ) -> ProviderTrustProfile:
        provider = live_provider or next(
            (
                candidate
                for candidate in self.component1.providers
                if candidate.get("provider_id") == provider_id
            ),
            None,
        )
        if provider is None:
            raise UnknownProviderError([provider_id])

        trust = self.component4.provider_trust_snapshot(provider_id, live_provider)
        platform_reviews = [
            {
                "rating": int(review["rating"]),
                "review_text": review.get("review_text"),
                "reviewed_at": _utc_datetime(review["timestamp"]),
                "verified_booking": True,
                "source": "platform",
                "credibility_score": None,
            }
            for review in await self.interactions.list_reviews_for_provider(
                provider_id,
                limit=50,
            )
        ]
        research_reviews = self.research_reviews.for_provider(provider_id, limit=20)
        reviews = sorted(
            [*platform_reviews, *research_reviews],
            key=lambda review: review["reviewed_at"],
            reverse=True,
        )[:10]
        raw_skills = provider.get("skills", [])
        skills = (
            [skill.strip() for skill in raw_skills.split(",") if skill.strip()]
            if isinstance(raw_skills, str)
            else [str(skill) for skill in raw_skills]
        )
        aspect_scores = trust["aspect_scores"]
        return ProviderTrustProfile.model_validate(
            {
                "provider_id": provider_id,
                "provider_name": provider.get("provider_name", provider_id),
                "category": provider.get("category", ""),
                "district": provider.get("district", ""),
                "city": provider.get("city", ""),
                "description": provider.get("description", ""),
                "skills": skills,
                "experience_years": int(provider.get("experience_years", 0)),
                "average_rating": float(trust["platform_rating"]),
                "review_count": int(trust["platform_review_count"]),
                "overall_trust_score": float(trust["final_score"]),
                "aspect_performance": {
                    aspect: (float(aspect_scores[aspect]) + 1.0) / 2.0
                    for aspect in (
                        "quality",
                        "communication",
                        "professionalism",
                        "punctuality",
                    )
                },
                "mean_review_credibility": float(trust["mean_credibility"]),
                "analyzed_review_count": int(trust["review_count"]),
                "evidence_status": trust["evidence_status"],
                "score_source": trust["score_source"],
                "customer_reviews": reviews,
            }
        )
