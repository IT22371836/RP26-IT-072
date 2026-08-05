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
from app.components.component4.router import admin_user, customer_user, engine_dependency
from app.components.component4.service import Component4RankingEngine
from app.components.component4.telemetry import component4_runtime_telemetry
from app.core.config import Settings, get_settings
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
            "source": "development_fixture",
            "request_id": "RAPITEST1",
            "user_id": customer.user_id,
            "component_version": "not-component2",
            "model_version": "not-component2",
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
        assert first.json()["handoff"] == {
            "source": "development_fixture",
            "request_id": "RAPITEST1",
            "user_id": customer.user_id,
            "component_version": "not-component2",
            "model_version": "not-component2",
        }
        assert first.json()["cached"] is False
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert stored.status_code == 200
        assert stored.json()["providers"] == first.json()["providers"]
        assert repository.persist_count == 1

    asyncio.run(run_test())


def test_admin_runtime_metrics_report_fresh_and_cached_rankings() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UMETRICS1",
            email="metrics-customer@example.com",
            full_name="Metrics Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        administrator = UserPublic(
            user_id="UADMINMETRICS1",
            email="metrics-admin@example.com",
            full_name="Metrics Administrator",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        repository = InMemoryComponent4Repository()
        component4_runtime_telemetry.reset()
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[admin_user] = lambda: administrator
        app.dependency_overrides[engine_dependency] = loaded_engine
        app.dependency_overrides[get_component4_repository] = lambda: repository
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_service_request_repository] = lambda: (
            OwnedServiceRequestRepository(customer.user_id)
        )
        payload = {
            "source": "development_fixture",
            "request_id": "RMETRICS1",
            "user_id": customer.user_id,
            "component_version": "not-component2",
            "model_version": "not-component2",
            "provider_ids": ["P00001", "P00002"],
        }

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                first = await client.post("/api/v1/component4/rank", json=payload)
                second = await client.post("/api/v1/component4/rank", json=payload)
                metrics = await client.get("/api/v1/component4/runtime-metrics")
        finally:
            app.dependency_overrides.clear()
            component4_runtime_telemetry.reset()

        assert first.status_code == 200
        assert second.status_code == 200
        assert metrics.status_code == 200
        assert metrics.json()["scope"] == "process_local"
        assert metrics.json()["component_version"] == "component4-phase12"
        assert metrics.json()["requests_total"] == 2
        assert metrics.json()["successful_requests"] == 2
        assert metrics.json()["fresh_rankings"] == 1
        assert metrics.json()["cache_hits"] == 1
        assert metrics.json()["cache_hit_ratio"] == 0.5
        assert metrics.json()["contains_personal_data"] is False

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
                        "source": "development_fixture",
                        "request_id": "RUNKNOWN1",
                        "user_id": customer.user_id,
                        "component_version": "not-component2",
                        "model_version": "not-component2",
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
                        "source": "development_fixture",
                        "request_id": "ROWNER1",
                        "user_id": customer.user_id,
                        "component_version": "not-component2",
                        "model_version": "not-component2",
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
                        "source": "development_fixture",
                        "request_id": "RDBFAIL1",
                        "user_id": customer.user_id,
                        "component_version": "not-component2",
                        "model_version": "not-component2",
                        "provider_ids": ["P00001"],
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert response.json()["detail"] == "Component 4 ranking persistence is unavailable"

    asyncio.run(run_test())


def test_rank_endpoint_enforces_identity_and_production_fixture_policy() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="ULINEAGE1",
            email="lineage@example.com",
            full_name="Lineage Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        repository = InMemoryComponent4Repository()
        production = Settings(
            app_env="production",
            jwt_secret_key="phase11-production-test-secret-key",
        )
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[engine_dependency] = loaded_engine
        app.dependency_overrides[get_settings] = lambda: production
        app.dependency_overrides[get_component4_repository] = lambda: repository
        app.dependency_overrides[get_provider_repository] = EmptyProviderRepository
        app.dependency_overrides[get_service_request_repository] = lambda: (
            OwnedServiceRequestRepository(customer.user_id)
        )
        base_payload = {
            "request_id": "RLINEAGE1",
            "user_id": customer.user_id,
            "component_version": "component2-v1",
            "model_version": "context-v1",
            "provider_ids": ["P00001"],
        }

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                identity_mismatch = await client.post(
                    "/api/v1/component4/rank",
                    json={
                        **base_payload,
                        "source": "component2",
                        "user_id": "UOTHER1",
                    },
                )
                forbidden_fixture = await client.post(
                    "/api/v1/component4/rank",
                    json={
                        **base_payload,
                        "source": "development_fixture",
                        "component_version": "not-component2",
                        "model_version": "not-component2",
                    },
                )
                component2 = await client.post(
                    "/api/v1/component4/rank",
                    json={**base_payload, "source": "component2"},
                )
        finally:
            app.dependency_overrides.clear()

        assert identity_mismatch.status_code == 403
        assert forbidden_fixture.status_code == 403
        assert "forbidden in production" in forbidden_fixture.json()["detail"]
        assert component2.status_code == 200
        assert component2.json()["handoff"]["component_version"] == "component2-v1"
        assert repository.persist_count == 1

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
                        "source": "development_fixture",
                        "request_id": "RNOAUTH1",
                        "user_id": "UTESTNOAUTH",
                        "component_version": "not-component2",
                        "model_version": "not-component2",
                        "provider_ids": ["P00001"],
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 401

    asyncio.run(run_test())


def test_runtime_metrics_requires_administrator_authentication() -> None:
    async def run_test() -> None:
        app.dependency_overrides[get_user_repository] = EmptyUserRepository
        app.dependency_overrides[engine_dependency] = loaded_engine
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/v1/component4/runtime-metrics")
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
                readiness = await client.get("/api/v1/component4/integration-readiness")
                release = await client.get("/api/v1/component4/release-readiness")
                handoff = await client.get("/api/v1/component4/handoff-readiness")
                final = await client.get("/api/v1/component4/final-readiness")
                weights = await client.get("/api/v1/component4/weights/Electricians")
                health = await client.get("/api/v1/component4/health")
        finally:
            MongoDatabase.ping = original_ping  # type: ignore[method-assign]
            app.dependency_overrides.clear()

        assert models.status_code == 200
        assert models.json()["provider_score_count"] == 10_000
        assert models.json()["evaluation_version"] == "ranking-evaluation-v1"
        assert (
            models.json()["ranking_ground_truth_validation"]
            == "held_out_proxy_validated_phase8"
        )
        assert (
            models.json()["production_ground_truth_validation"]
            == "pending_real_component2_and_independent_relevance_judgements"
        )
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "awaiting_component2"
        assert readiness.json()["component4_ready"] is True
        assert readiness.json()["component2_connected"] is False
        assert readiness.json()["production_ready"] is False
        assert release.status_code == 200
        assert release.json()["component4_operationally_ready"] is True
        assert release.json()["component2_connected"] is False
        assert release.json()["production_ready"] is False
        assert all(release.json()["checks"].values())
        assert handoff.status_code == 200
        assert handoff.json()["status"] == "contract_ready_awaiting_component2"
        assert handoff.json()["contract_enforced"] is True
        assert handoff.json()["component2_connected"] is False
        assert handoff.json()["production_ready"] is False
        assert final.status_code == 200
        assert final.json()["component4_release_candidate_ready"] is True
        assert final.json()["external_api_load_test_passed"] is False
        assert final.json()["component2_connected"] is False
        assert final.json()["production_ready"] is False
        assert all(final.json()["checks"].values())
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
