import ast
import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.customers import customer_user
from app.api.dependencies import (
    get_current_user,
    get_customer_profile_repository,
    get_integration_read_repository,
    get_provider_repository,
)
from app.api.integration import admin_user
from app.api.providers import provider_user
from app.main import app
from app.migrations.union_model import plan_customer_union, plan_provider_union
from app.repositories.concurrency import ProfileConcurrencyError
from app.repositories.customers import CustomerProfileRepository
from app.repositories.providers import ProviderRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole
from app.schemas.customer import CustomerProfileUpdate
from app.schemas.integration import (
    ContextFilterResult,
    DailyDemandRecord,
    IntegrationExtractedFeatures,
    IntegrationLocation,
    IntegrationProviderDocuments,
    IntegrationWorkingHours,
    dump_preserving_unknown,
)
from app.schemas.provider import ProviderProfileUpdate

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeUpdateCollection:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.update_calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        if all(self.document.get(key) == value for key, value in query.items()):
            return deepcopy(self.document)
        return None

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
    ) -> SimpleNamespace:
        self.update_calls.append((deepcopy(query), deepcopy(update)))
        matched = all(self.document.get(key) == value for key, value in query.items())
        if matched:
            self.document.update(deepcopy(update["$set"]))
        return SimpleNamespace(matched_count=int(matched), modified_count=int(matched))


class FakeDatabase:
    def __init__(self, collection_name: str, collection: FakeUpdateCollection) -> None:
        self.collection_name = collection_name
        self.collection = collection

    def __getitem__(self, name: str) -> FakeUpdateCollection:
        if name == "provider_verification_events":
            return FakeUpdateCollection({})
        assert name == self.collection_name
        return self.collection


class FakeIntegrationReadRepository:
    async def get_current_daily_demand(self) -> dict[str, Any]:
        return {
            "compile_date": "2026-07-30",
            "by_category": {
                "Plumbers": {
                    "service_category": "Plumbers",
                    "Monday": 30,
                    "future_internal_score": 99,
                }
            },
            "summary": [
                {
                    "Service Category": "Plumbers",
                    "Monday": 30,
                    "Total Weekly Orders": 212,
                    "private_document_url": "must-not-leak",
                }
            ],
            "_id": "mongo-internal",
            "password_hash": "must-not-leak",
        }

    async def list_filter_requests(self, limit: int) -> list[dict[str, Any]]:
        assert limit == 10
        return [
            {
                "id": "firebase-filter-key",
                "request_id": "legacy-request",
                "user_id": "legacy-user",
                "isNewRequest": False,
                "output_results": {
                    "weather_risk": "LOW_RISK",
                    "evaluated_providers": [
                        {
                            "provider_id": "legacy-provider",
                            "provider_location": {
                                "latitude": 6.9,
                                "longitude": 79.8,
                                "private_location_note": "must-not-leak",
                            },
                            "nic": "must-not-leak",
                        }
                    ],
                    "private_document_url": "must-not-leak",
                },
                "_id": "mongo-internal",
                "password_hash": "must-not-leak",
                "nic": "must-not-leak",
            }
        ]


class ConflictProfileRepository:
    async def find_by_user_id(self, user_id: str) -> dict[str, str]:
        return {"user_id": user_id}

    async def update_by_user_id(
        self,
        _user_id: str,
        _updates: dict[str, Any],
        *,
        expected_updated_at: datetime,
    ) -> None:
        assert expected_updated_at == datetime(2026, 8, 5, 10, tzinfo=UTC)
        raise ProfileConcurrencyError


def test_legacy_models_are_optional_alias_aware_and_preserve_unknown_fields() -> None:
    assert IntegrationLocation().model_dump(exclude_unset=True) == {}
    assert IntegrationWorkingHours().model_dump(exclude_unset=True) == {}
    assert IntegrationExtractedFeatures().model_dump(exclude_unset=True) == {}

    documents = IntegrationProviderDocuments.model_validate(
        {
            "identityDocument": [
                {
                    "fileId": "firebase-file",
                    "fileUrl": "https://storage.example/file",
                    "futureChecksum": "abc123",
                }
            ],
            "futureDocumentGroup": [{"untouched": True}],
        }
    )
    dumped_documents = dump_preserving_unknown(documents)
    assert dumped_documents["identityDocument"][0]["futureChecksum"] == "abc123"
    assert dumped_documents["futureDocumentGroup"] == [{"untouched": True}]

    context = ContextFilterResult.model_validate(
        {
            "isNewRequest": False,
            "futurePipelineResult": {"nested": [False, None, 0, ""]},
        }
    )
    demand = DailyDemandRecord.model_validate(
        {"futureDemandField": {"nested": [False, None, 0, ""]}}
    )
    assert dump_preserving_unknown(context)["futurePipelineResult"] == {
        "nested": [False, None, 0, ""]
    }
    assert dump_preserving_unknown(demand)["futureDemandField"] == {
        "nested": [False, None, 0, ""]
    }


def test_profile_payloads_accept_web_aliases_and_concurrency_tokens() -> None:
    timestamp = "2026-08-05T10:00:00Z"
    customer = CustomerProfileUpdate.model_validate(
        {"customerImage": "https://example/customer.png", "expectedUpdatedAt": timestamp}
    )
    provider = ProviderProfileUpdate.model_validate(
        {
            "fullName": "Updated Provider",
            "experienceYears": 8,
            "expectedUpdatedAt": timestamp,
        }
    )

    assert customer.customer_image == "https://example/customer.png"
    assert customer.expected_updated_at == datetime(2026, 8, 5, 10, tzinfo=UTC)
    assert provider.provider_name == "Updated Provider"
    assert provider.experience_years == 8
    assert provider.expected_updated_at == customer.expected_updated_at


@pytest.mark.parametrize(
    ("repository_type", "collection_name", "identity_field"),
    [
        (CustomerProfileRepository, "customer_profiles", "customer_id"),
        (ProviderRepository, "providers", "provider_id"),
    ],
)
def test_profile_updates_use_set_preserve_unknown_fields_and_reject_stale_writes(
    repository_type: type[CustomerProfileRepository] | type[ProviderRepository],
    collection_name: str,
    identity_field: str,
) -> None:
    async def run_test() -> None:
        version = datetime(2026, 8, 5, 10, tzinfo=UTC)
        document = {
            identity_field: "PROFILE1",
            "user_id": "U1",
            "city": "Colombo",
            "updated_at": version,
            "unknown_legacy": {"nested": [False, None, 0, ""]},
        }
        collection = FakeUpdateCollection(document)
        repository = repository_type(FakeDatabase(collection_name, collection))

        updated = await repository.update_by_user_id(
            "U1",
            {"city": "Kandy", "updated_at": datetime(2026, 8, 5, 11, tzinfo=UTC)},
            expected_updated_at=version,
        )
        assert updated is not None
        assert updated["city"] == "Kandy"
        assert updated["unknown_legacy"] == {"nested": [False, None, 0, ""]}
        assert collection.update_calls[0][1] == {
            "$set": {
                "city": "Kandy",
                "updated_at": datetime(2026, 8, 5, 11, tzinfo=UTC),
            }
        }

        with pytest.raises(ProfileConcurrencyError):
            await repository.update_by_user_id(
                "U1",
                {"city": "Galle"},
                expected_updated_at=version,
            )
        assert collection.document["city"] == "Kandy"
        assert collection.document["unknown_legacy"] == {
            "nested": [False, None, 0, ""]
        }

    asyncio.run(run_test())


def test_union_plans_add_sync_metadata_without_changing_existing_attributes() -> None:
    sync_time = datetime(2026, 8, 5, 12, tzinfo=UTC)
    user = {"user_id": "U1", "role": "customer"}
    customer_profile = {"customer_id": "C1", "user_id": "U1"}
    provider_profile = {"provider_id": "P1", "user_id": "U2"}

    customer_plan = plan_customer_union(
        "customer-key",
        {},
        user,
        customer_profile,
        synced_at=sync_time,
    )
    provider_plan = plan_provider_union(
        "provider-key",
        {},
        {"user_id": "U2", "role": "provider"},
        provider_profile,
        synced_at=sync_time,
    )

    for plan in (customer_plan, provider_plan):
        for target in ("user", "profile"):
            updates = plan[target]["updates"]
            assert updates["migration_version"] == "firebase-to-mongo-v1"
            assert updates["source_system"] == "firebase_rtdb"
            assert updates["last_synced_at"] == sync_time
    assert user == {"user_id": "U1", "role": "customer"}
    assert customer_profile == {"customer_id": "C1", "user_id": "U1"}
    assert provider_profile == {"provider_id": "P1", "user_id": "U2"}


def test_web_integration_endpoints_are_authenticated_and_privacy_allowlisted() -> None:
    async def run_test() -> None:
        user = UserPublic(
            user_id="UADMIN",
            email="admin@example.com",
            full_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        repository = FakeIntegrationReadRepository()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[admin_user] = lambda: user
        app.dependency_overrides[get_integration_read_repository] = lambda: repository
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                demand_response = await client.get(
                    "/api/v1/integration/daily-demand/current"
                )
                history_response = await client.get(
                    "/api/v1/integration/filter-requests?limit=10"
                )
                customer = user.model_copy(update={"role": UserRole.CUSTOMER})
                del app.dependency_overrides[admin_user]
                app.dependency_overrides[get_current_user] = lambda: customer
                forbidden_history = await client.get(
                    "/api/v1/integration/filter-requests?limit=10"
                )
        finally:
            app.dependency_overrides.clear()

        assert demand_response.status_code == 200
        demand = demand_response.json()
        assert demand["by_category"]["Plumbers"]["Monday"] == 30
        assert "future_internal_score" not in demand["by_category"]["Plumbers"]
        assert "private_document_url" not in demand["summary"][0]
        assert "_id" not in demand
        assert "password_hash" not in demand

        assert history_response.status_code == 200
        assert forbidden_history.status_code == 403
        history = history_response.json()[0]
        assert history["id"] == "firebase-filter-key"
        assert history["isNewRequest"] is False
        assert "_id" not in history
        assert "password_hash" not in history
        assert "nic" not in history
        output = history["output_results"]
        assert "private_document_url" not in output
        evaluated = output["evaluated_providers"][0]
        assert "nic" not in evaluated
        assert "private_location_note" not in evaluated["provider_location"]

    asyncio.run(run_test())


def test_profile_endpoints_return_conflict_for_stale_concurrency_tokens() -> None:
    async def run_test() -> None:
        customer = UserPublic(
            user_id="UCUSTOMER",
            email="customer@example.com",
            full_name="Customer",
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        provider = UserPublic(
            user_id="UPROVIDER",
            email="provider@example.com",
            full_name="Provider",
            role=UserRole.PROVIDER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        conflicts = ConflictProfileRepository()
        app.dependency_overrides[get_customer_profile_repository] = lambda: conflicts
        app.dependency_overrides[get_provider_repository] = lambda: conflicts
        app.dependency_overrides[customer_user] = lambda: customer
        app.dependency_overrides[provider_user] = lambda: provider
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                customer_response = await client.patch(
                    "/api/v1/customers/me",
                    json={
                        "city": "Kandy",
                        "expectedUpdatedAt": "2026-08-05T10:00:00Z",
                    },
                )
                provider_response = await client.patch(
                    "/api/v1/providers/me",
                    json={
                        "city": "Galle",
                        "expected_updated_at": "2026-08-05T10:00:00Z",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert customer_response.status_code == 409
        assert customer_response.json()["detail"].startswith("Customer profile changed")
        assert provider_response.status_code == 409
        assert provider_response.json()["detail"].startswith("Provider profile changed")

    asyncio.run(run_test())


def test_repository_update_audit_rejects_replacement_and_non_operator_updates() -> None:
    violations: list[str] = []
    for path in sorted((BACKEND_ROOT / "app" / "repositories").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "replace_one" in source or "$unset" in source:
            violations.append(f"{path.name}: destructive update primitive")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"update_one", "update_many", "find_one_and_update"}:
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Dict):
                violations.append(f"{path.name}:{node.lineno}: non-literal update")
                continue
            keys = [
                key.value
                for key in node.args[1].keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            ]
            if not keys or any(not key.startswith("$") for key in keys):
                violations.append(f"{path.name}:{node.lineno}: replacement-style update")
    assert violations == []
