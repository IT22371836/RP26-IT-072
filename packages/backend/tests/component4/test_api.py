import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_component4_repository,
    get_provider_repository,
    get_service_request_repository,
    get_user_repository,
)
from app.components.component4.router import customer_user, engine_dependency
from app.components.component4.service import Component4RankingEngine
from app.core.config import Settings
from app.core.database import MongoDatabase
from app.main import app
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole


class InMemoryComponent4Repository:
    def __init__(self) -> None:
        self.responses: dict[str, dict[str, Any]] = {}
        self.persist_count = 0

    async def find_completed_response(
        self,
        run_id: str,
        _user_id: str,
    ) -> dict[str, Any] | None:
        return self.responses.get(run_id)

    async def persist_completed(
        self,
        run_document: dict[str, Any],
        _provider_documents: list[dict[str, Any]],
    ) -> None:
        self.persist_count += 1
        self.responses[run_document["run_id"]] = run_document["response"]


class EmptyProviderRepository:
    async def list_by_ids(self, _provider_ids: list[str]) -> list[dict[str, Any]]:
        return []


class OwnedServiceRequestRepository:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    async def find_by_id(self, request_id: str) -> dict[str, str]:
        return {"request_id": request_id, "user_id": self.user_id}


class EmptyUserRepository:
    async def find_by_id(self, _user_id: str) -> None:
        return None


class FailingComponent4Repository(InMemoryComponent4Repository):
    async def persist_completed(
        self,
        _run_document: dict[str, Any],
        _provider_documents: list[dict[str, Any]],
    ) -> None:
        raise RuntimeError("database unavailable")


def loaded_engine() -> Component4RankingEngine:
    settings = Settings()
    engine = Component4RankingEngine(
        settings.component4_artifact_dir,
        settings.component4_category_priors_path,
    )
    engine.load()
    return engine


def test_rank_endpoint_persists_and_returns_cached_top5() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UTEST123",
            email="component4@example.com",
            full_name="Component 4 Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        engine = loaded_engine()
        repository = InMemoryComponent4Repository()
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = lambda: engine
        app.dependency_overrides[get_component4_repository] = lambda: repository
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_service_request_repository] = lambda: (
            OwnedServiceRequestRepository(customer.user_id)
        )
        payload = {
            "request_id": "RAPITEST1",
            "provider_ids": [f"P{index:05d}" for index in range(1, 11)],
            "top_k": 5,
        }

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                first = await client.post("/api/v1/component4/rank", json=payload)
                second = await client.post("/api/v1/component4/rank", json=payload)
                stored = await client.get(
                    f"/api/v1/component4/runs/{first.json()['run_id']}"
                )
        finally:
            app.dependency_overrides.clear()

        assert first.status_code == 200
        assert first.json()["input_count"] == 10
        assert first.json()["output_count"] == 5
        assert first.json()["cached"] is False
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert stored.status_code == 200
        assert stored.json()["providers"] == first.json()["providers"]
        assert repository.persist_count == 1

    asyncio.run(run_test())


def test_rank_endpoint_returns_404_for_unknown_provider() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UTEST404",
            email="unknown@example.com",
            full_name="Unknown Provider Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = loaded_engine
        app.dependency_overrides[get_component4_repository] = InMemoryComponent4Repository
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_service_request_repository] = lambda: (
            OwnedServiceRequestRepository(customer.user_id)
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/component4/rank",
                    json={
                        "request_id": "RUNKNOWN1",
                        "provider_ids": ["PUNKNOWN1"],
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "PUNKNOWN1" in response.json()["detail"]

    asyncio.run(run_test())


def test_rank_endpoint_rejects_a_request_owned_by_another_customer() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UOWNER1",
            email="owner@example.com",
            full_name="Request Owner",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = loaded_engine
        app.dependency_overrides[get_component4_repository] = InMemoryComponent4Repository
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_service_request_repository] = lambda: (
            OwnedServiceRequestRepository("UOTHER1")
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/component4/rank",
                    json={
                        "request_id": "ROWNER1",
                        "provider_ids": ["P00001"],
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 403

    asyncio.run(run_test())


def test_rank_endpoint_reports_persistence_unavailability() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UDBFAIL1",
            email="dbfail@example.com",
            full_name="Database Failure Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = loaded_engine
        app.dependency_overrides[get_component4_repository] = FailingComponent4Repository
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_service_request_repository] = lambda: (
            OwnedServiceRequestRepository(customer.user_id)
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/component4/rank",
                    json={
                        "request_id": "RDBFAIL1",
                        "provider_ids": ["P00001"],
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert response.json()["detail"] == "Component 4 ranking persistence is unavailable"

    asyncio.run(run_test())


def test_rank_endpoint_requires_authentication() -> None:
    async def run_test() -> None:
        app.dependency_overrides[get_user_repository] = EmptyUserRepository
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/component4/rank",
                    json={
                        "request_id": "RNOAUTH1",
                        "provider_ids": ["P00001"],
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 401

    asyncio.run(run_test())


def test_model_weight_and_health_endpoints() -> None:
    async def run_test() -> None:
        engine = loaded_engine()
        app.dependency_overrides[engine_dependency] = lambda: engine
        original_ping = MongoDatabase.ping
        MongoDatabase.ping = AsyncMock(return_value=True)  # type: ignore[method-assign]

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                models = await client.get("/api/v1/component4/models")
                weights = await client.get("/api/v1/component4/weights/Electricians")
                health = await client.get("/api/v1/component4/health")
        finally:
            MongoDatabase.ping = original_ping  # type: ignore[method-assign]
            app.dependency_overrides.clear()

        assert models.status_code == 200
        assert models.json()["provider_score_count"] == 10_000
        assert weights.status_code == 200
        assert sum(weights.json()["weights"].values()) == 1.0
        assert health.status_code == 200
        assert health.json()["ready"] is True

    asyncio.run(run_test())


def test_component4_health_reports_shared_database_failure() -> None:
    async def run_test() -> None:
        app.dependency_overrides[engine_dependency] = loaded_engine
        original_ping = MongoDatabase.ping
        MongoDatabase.ping = AsyncMock(return_value=False)  # type: ignore[method-assign]

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/v1/component4/health")
        finally:
            MongoDatabase.ping = original_ping  # type: ignore[method-assign]
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert response.json()["detail"] == "Shared MongoDB is unavailable"

    asyncio.run(run_test())
