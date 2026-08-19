import asyncio
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_component1_repository,
    get_firebase_rtdb_client,
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
)
from app.components.component1.router import customer_user, engine_dependency
from app.components.component1.schemas import ProviderRecommendation
from app.main import app
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole


class ScoredEngine:
    manifest = {"component_version": "1.2.3", "model_version": "hybrid-v2"}
    providers: list[dict[str, object]] = []

    def recommend(self, **_kwargs: object) -> list[ProviderRecommendation]:
        return [
            ProviderRecommendation(
                provider_id="P001",
                provider_name="Test Provider",
                category="Electricians",
                district="Colombo",
                city="Colombo",
                skills="wiring, repairs",
                description="Electrical repair provider",
                experience_years=5,
                rating=4.5,
                review_count=10,
                booking_success_rate=0.9,
                interaction_count=20,
                cf_score=0.7,
                tfidf_score=0.8,
                bert_score=0.9,
                hybrid_score=0.83,
            )
        ]


class Providers:
    async def list_pipeline_eligible(
        self, limit: int = 20_000, *, cache_seconds: float = 300.0
    ) -> list[object]:
        del limit, cache_seconds
        return []


class Interactions:
    async def click_preference_provider_ids(self, _user_id: str) -> list[str]:
        return []

    async def create_many(self, _documents: list[object]) -> None:
        return None


class LinkedUsers:
    async def find_by_id(self, _user_id: str) -> dict[str, object]:
        return {"legacy": {"firebase_uid": "firebase-customer"}}


class EmptyFirebaseBookingHistory:
    async def get_customer_booking_history(
        self, _firebase_uid: str
    ) -> dict[str, dict[str, object]]:
        return {}


class Requests:
    async def find_by_id(self, request_id: str) -> dict[str, str]:
        return {"request_id": request_id, "user_id": "UABC123"}


class Recorder:
    def __init__(self) -> None:
        self.run: dict[str, object] | None = None
        self.scores: list[dict[str, object]] = []

    async def persist_completed(
        self,
        run_document: dict[str, object],
        provider_documents: list[dict[str, object]],
    ) -> None:
        self.run = run_document
        self.scores = provider_documents


def test_recommendation_scores_are_persisted_with_run_metadata() -> None:
    async def run_test() -> None:
        recorder = Recorder()
        customer = UserPublic(
            user_id="UABC123",
            email="customer@example.com",
            full_name="Test Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = ScoredEngine
        app.dependency_overrides[get_provider_repository] = Providers
        app.dependency_overrides[get_interaction_repository] = Interactions
        app.dependency_overrides[get_user_repository] = LinkedUsers
        app.dependency_overrides[get_firebase_rtdb_client] = EmptyFirebaseBookingHistory
        app.dependency_overrides[get_service_request_repository] = Requests
        app.dependency_overrides[get_component1_repository] = lambda: recorder
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/component1/recommend",
                    json={"request_id": "RABC123", "query": "need an electrician"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert recorder.run is not None
        assert recorder.run["request_id"] == "RABC123"
        assert recorder.run["model_version"] == "hybrid-v2"
        assert recorder.run["output_count"] == 1
        assert len(recorder.scores) == 1
        score = recorder.scores[0]
        assert score["run_id"] == recorder.run["run_id"]
        assert score["rank"] == 1
        assert score["cf_score"] == 0.7
        assert score["tfidf_score"] == 0.8
        assert score["bert_score"] == 0.9
        assert score["hybrid_score"] == 0.83

    asyncio.run(run_test())
