import asyncio
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

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
