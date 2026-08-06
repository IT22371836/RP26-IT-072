import asyncio
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_component1_repository,
    get_interaction_repository,
    get_provider_repository,
    get_service_request_repository,
)
from app.components.component1.router import customer_user, engine_dependency
from app.main import app
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole


class ReadyEngine:
    ready = True
    manifest = {"component_version": "1.0.0", "model_version": "test-model"}

    def status(self) -> dict[str, object]:
        return {
            "ready": True,
            "component_version": "1.0.0",
            "model_version": "test-model",
            "provider_count": 10_000,
        }

    def recommend(self, **_kwargs: object) -> list[object]:
        return []


class EmptyProviderRepository:
    async def list_all(self) -> list[object]:
        return []


class EmptyInteractionRepository:
    async def preferred_provider_ids(self, _user_id: str) -> list[str]:
        return []

    async def create_many(self, _documents: list[object]) -> None:
        return None


class RecordingComponent1Repository:
    def __init__(self) -> None:
        self.run_document: dict[str, object] | None = None
        self.provider_documents: list[dict[str, object]] = []

    async def persist_completed(
        self,
        run_document: dict[str, object],
        provider_documents: list[dict[str, object]],
    ) -> None:
        self.run_document = run_document
        self.provider_documents = provider_documents


class OwnedServiceRequestRepository:
    async def find_by_id(self, request_id: str) -> dict[str, str] | None:
        return {"request_id": request_id, "user_id": "UABC123"}


class MissingServiceRequestRepository:
    async def find_by_id(self, _request_id: str) -> None:
        return None


class ForeignServiceRequestRepository:
    async def find_by_id(self, request_id: str) -> dict[str, str]:
        return {"request_id": request_id, "user_id": "UOTHER"}


def test_recommendation_api_preserves_pipeline_identifiers() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UABC123",
            email="customer@example.com",
            full_name="Test Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = ReadyEngine
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_interaction_repository] = EmptyInteractionRepository
        app.dependency_overrides[get_service_request_repository] = (
            OwnedServiceRequestRepository
        )
        app.dependency_overrides[get_component1_repository] = RecordingComponent1Repository

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
        assert response.json() == {
            "component_version": "1.0.0",
            "model_version": "test-model",
            "request_id": "RABC123",
            "query": "need an electrician",
            "user_id": "UABC123",
            "results": [],
        }

    asyncio.run(run_test())


def test_recommendation_api_requires_an_owned_service_request() -> None:
    async def request_with(repository: object) -> int:
        customer = UserPublic(
            user_id="UABC123",
            email="customer@example.com",
            full_name="Test Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = ReadyEngine
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_interaction_repository] = EmptyInteractionRepository
        app.dependency_overrides[get_service_request_repository] = lambda: repository
        app.dependency_overrides[get_component1_repository] = RecordingComponent1Repository
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/component1/recommend",
                    json={"request_id": "RABC123", "query": "need an electrician"},
                )
                return response.status_code
        finally:
            app.dependency_overrides.clear()

    assert asyncio.run(request_with(MissingServiceRequestRepository())) == 404
    assert asyncio.run(request_with(ForeignServiceRequestRepository())) == 403
