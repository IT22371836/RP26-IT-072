import asyncio
from datetime import UTC, datetime
from typing import Any

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_interaction_repository, get_provider_repository
from app.api.providers import component1_engine_dependency, component4_engine_dependency
from app.components.component4.provider_trust import ProviderTrustProfileService
from app.main import app


class FakeComponent1:
    providers = [
        {
            "provider_id": "P00001",
            "provider_name": "Trusted Electrician",
            "category": "Electricians",
            "district": "Colombo",
            "city": "Kottawa",
            "description": "Residential electrical repairs and safety inspections.",
            "skills": "wiring, safety inspection",
            "experience_years": 8,
        }
    ]


class FakeComponent4:
    def provider_trust_snapshot(
        self,
        provider_id: str,
        _live_provider: dict[str, Any] | None,
    ) -> dict[str, Any]:
        assert provider_id == "P00001"
        return {
            "platform_rating": 4.7,
            "platform_review_count": 42,
            "final_score": 0.88,
            "aspect_scores": {
                "quality": 0.8,
                "communication": 0.6,
                "professionalism": 0.7,
                "punctuality": 0.5,
            },
            "mean_credibility": 0.91,
            "review_count": 7,
            "evidence_status": "sufficient",
            "score_source": "catf_evidence",
        }


class FakeProviders:
    async def find_by_id(self, _provider_id: str) -> None:
        return None


class FakeInteractions:
    async def list_reviews_for_provider(
        self,
        _provider_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        assert limit == 50
        return [
            {
                "rating": 5,
                "review_text": "Excellent work and clear communication.",
                "timestamp": datetime(2026, 7, 1, tzinfo=UTC),
            }
        ]


class FakeResearchReviews:
    def for_provider(self, _provider_id: str, limit: int = 10) -> list[dict[str, Any]]:
        assert limit == 20
        return [
            {
                "rating": 4,
                "review_text": "Arrived on time and completed the repair.",
                "reviewed_at": datetime(2026, 6, 1, tzinfo=UTC),
                "verified_booking": True,
                "source": "research_dataset",
                "credibility_score": 0.86,
            }
        ]


def test_profile_combines_provider_trust_aspects_and_reviews() -> None:
    async def run_test() -> None:
        profile = await ProviderTrustProfileService(
            FakeComponent1(),  # type: ignore[arg-type]
            FakeComponent4(),  # type: ignore[arg-type]
            FakeInteractions(),  # type: ignore[arg-type]
            FakeResearchReviews(),  # type: ignore[arg-type]
        ).build("P00001", None)

        assert profile.average_rating == 4.7
        assert profile.review_count == 42
        assert profile.overall_trust_score == 0.88
        assert profile.aspect_performance.quality == 0.9
        assert profile.aspect_performance.communication == 0.8
        assert profile.aspect_performance.professionalism == 0.85
        assert profile.aspect_performance.punctuality == 0.75
        assert profile.analyzed_review_count == 7
        assert profile.customer_reviews[0].source == "platform"
        assert profile.customer_reviews[1].source == "research_dataset"
        assert not hasattr(profile.customer_reviews[0], "user_id")

    asyncio.run(run_test())


def test_customer_can_fetch_a_provider_trust_profile() -> None:
    async def run_test() -> None:
        app.dependency_overrides[get_provider_repository] = FakeProviders
        app.dependency_overrides[get_interaction_repository] = FakeInteractions
        app.dependency_overrides[component1_engine_dependency] = FakeComponent1
        app.dependency_overrides[component4_engine_dependency] = FakeComponent4
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/v1/providers/P00001/trust-profile")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["provider_id"] == "P00001"
        assert response.json()["overall_trust_score"] == 0.88
        assert response.json()["aspect_performance"]["quality"] == 0.9
        assert len(response.json()["customer_reviews"]) >= 1
        assert response.json()["customer_reviews"][0]["source"] == "platform"

    asyncio.run(run_test())
