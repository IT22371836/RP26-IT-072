import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.migrations.firebase_rtdb import (
    FirebaseExportError,
    apply_snapshots,
    build_snapshot,
    inventory_export,
    load_firebase_export,
    new_report,
    source_sha256,
    verify_snapshots,
)
from app.migrations.identity_linking import resolve_identity_mapping
from app.migrations.phase2_inventory import verify_phase2_inventory
from app.repositories.legacy_firebase import LEGACY_COLLECTIONS, LegacyFirebaseRepository

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIREBASE_EXPORT = REPOSITORY_ROOT / "WEB" / "src" / "data" / (
    "service-e333a-default-rtdb-export.json"
)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: dict[tuple[str, str], dict[str, Any]] = {}
        self.indexes: list[tuple[Any, dict[str, Any]]] = []
        self.update_payloads: list[dict[str, Any]] = []

    async def create_index(self, keys: Any, **kwargs: Any) -> None:
        self.indexes.append((keys, kwargs))

    async def find_one(self, identity: dict[str, str]) -> dict[str, Any] | None:
        document = self.documents.get((identity["source_node"], identity["source_key"]))
        return deepcopy(document) if document is not None else None

    async def update_one(
        self,
        identity: dict[str, str],
        update: dict[str, Any],
        *,
        upsert: bool,
    ) -> SimpleNamespace:
        assert upsert is True
        assert set(update) == {"$setOnInsert"}
        self.update_payloads.append(deepcopy(update))
        key = (identity["source_node"], identity["source_key"])
        if key in self.documents:
            return SimpleNamespace(upserted_id=None)
        self.documents[key] = deepcopy(update["$setOnInsert"])
        return SimpleNamespace(upserted_id=f"inserted-{len(self.documents)}")


class FakeIdentityCollection:
    def __init__(self) -> None:
        self.indexes: list[tuple[Any, dict[str, Any]]] = []
        self.documents: dict[tuple[str, str], dict[str, Any]] = {}
        self.update_payloads: list[dict[str, Any]] = []

    async def create_index(self, keys: Any, **kwargs: Any) -> None:
        self.indexes.append((keys, kwargs))

    async def find_one(self, identity: dict[str, str]) -> dict[str, Any] | None:
        document = self.documents.get((identity["entity_type"], identity["firebase_key"]))
        return deepcopy(document) if document is not None else None

    async def update_one(
        self,
        identity: dict[str, str],
        update: dict[str, Any],
        *,
        upsert: bool,
    ) -> SimpleNamespace:
        assert upsert is True
        assert set(update) == {"$setOnInsert"}
        self.update_payloads.append(deepcopy(update))
        key = (identity["entity_type"], identity["firebase_key"])
        if key in self.documents:
            return SimpleNamespace(upserted_id=None)
        self.documents[key] = deepcopy(update["$setOnInsert"])
        return SimpleNamespace(upserted_id=f"identity-{len(self.documents)}")


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, Any] = {
            name: FakeCollection() for name in LEGACY_COLLECTIONS.values()
        }
        self.collections["legacy_identity_map"] = FakeIdentityCollection()

    def __getitem__(self, name: str) -> Any:
        return self.collections[name]


class FakeUserLookup:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = users

    async def find_all_by_email(
        self, email: str, *, limit: int = 2
    ) -> list[dict[str, Any]]:
        return [user for user in self.users if user.get("email") == email][:limit]

    async def find_by_firebase_uid(self, firebase_uid: str) -> dict[str, Any] | None:
        return next(
            (
                user
                for user in self.users
                if user.get("legacy", {}).get("firebase_uid") == firebase_uid
            ),
            None,
        )


def test_checked_in_export_inventory_contains_all_supported_nodes() -> None:
    data = load_firebase_export(FIREBASE_EXPORT)
    inventory = inventory_export(data)

    assert set(data) == set(LEGACY_COLLECTIONS)
    assert inventory["total_records"] == sum(len(records) for records in data.values())
    assert inventory["nodes"]["customers"]["record_count"] == 1
    assert inventory["nodes"]["providers"]["record_count"] == 4
    assert inventory["nodes"]["filter_requests"]["record_count"] == 2
    assert inventory["nodes"]["daily_demand"]["record_count"] == 1

    provider_paths = set(inventory["nodes"]["providers"]["field_paths"])
    assert "providers.{record}.workingHours.Monday.isOpen" in provider_paths
    assert "providers.{record}.documents.identityDocument[].fileUrl" in provider_paths
    assert (
        "providers.{record}.extractedFeatures.credibility.credibilityScore" in provider_paths
    )


def test_phase_two_inventory_preserves_every_checked_in_record_exactly() -> None:
    data = load_firebase_export(FIREBASE_EXPORT)

    report = verify_phase2_inventory(data)

    assert report["summary"]["passed"] is True
    assert report["summary"]["expected_records"] == 8
    assert report["summary"]["exact_snapshots"] == 8
    assert report["summary"]["snapshot_failures"] == 0
    assert report["summary"]["missing_nodes"] == []
    assert all(
        node_report["all_source_paths_preserved"]
        for node_report in report["nodes"].values()
    )


def test_phase_two_optional_fields_are_preserved_when_present_and_never_fabricated() -> None:
    provider = {
        "id": "minimal-provider",
        "credibility": {
            "score": 0,
            "level": "pending",
            "sourceSpecificFutureField": {"nested": [False, None, ""]},
        },
    }
    data = {
        "customers": {},
        "providers": {"provider-key": provider},
        "filter_requests": {},
        "daily_demand": {},
    }

    report = verify_phase2_inventory(data)
    snapshot = build_snapshot("providers", "provider-key", provider)

    assert report["summary"]["passed"] is True
    assert report["summary"]["provider_level_credibility_observed"] is True
    assert snapshot["source_record"] == provider
    assert "fullName" not in snapshot["source_record"]
    assert snapshot["source_record"]["credibility"]["score"] == 0
    assert snapshot["source_record"]["credibility"]["sourceSpecificFutureField"] == {
        "nested": [False, None, ""]
    }


def test_phase_two_inventory_requires_all_four_source_nodes() -> None:
    report = verify_phase2_inventory({"customers": {}})

    assert report["summary"]["passed"] is False
    assert report["summary"]["missing_nodes"] == [
        "providers",
        "filter_requests",
        "daily_demand",
    ]


def test_snapshot_is_a_deep_copy_and_hash_is_stable() -> None:
    record = {
        "fullName": "Test User",
        "location": {"latitude": 6.9271, "longitude": 79.8612},
        "skills": ["Plumbing", "Repairs"],
        "verified": False,
        "nullable": None,
    }
    reversed_record = dict(reversed(list(record.items())))

    snapshot = build_snapshot("providers", "firebase-key", record)
    assert snapshot["source_record"] == record
    assert snapshot["source_record"] is not record
    assert snapshot["source_sha256"] == source_sha256(reversed_record)

    record["location"]["latitude"] = 0
    assert snapshot["source_record"]["location"]["latitude"] == 6.9271


def test_load_rejects_unknown_nodes_and_non_object_records(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown.json"
    unknown.write_text('{"secrets": {"one": {"value": 1}}}', encoding="utf-8")
    with pytest.raises(FirebaseExportError, match="Unsupported top-level"):
        load_firebase_export(unknown)

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"customers": {"one": "not-an-object"}}', encoding="utf-8")
    with pytest.raises(FirebaseExportError, match="non-object records"):
        load_firebase_export(invalid)


def test_dry_run_reports_every_record_without_database_writes() -> None:
    data = load_firebase_export(FIREBASE_EXPORT)
    report = new_report("dry-run", data)

    assert report["summary"]["planned"] == report["summary"]["expected"]
    assert report["summary"]["inserted"] == 0
    assert report["issues"] == []


def test_phase_one_indexes_cover_snapshot_and_identity_uniqueness() -> None:
    async def run_test() -> None:
        database = FakeDatabase()
        repository = LegacyFirebaseRepository(database)

        await repository.ensure_indexes()

        for collection_name in LEGACY_COLLECTIONS.values():
            indexes = database[collection_name].indexes
            assert (
                [("source_node", 1), ("source_key", 1)],
                {"unique": True},
            ) in indexes
            assert ([("source_sha256", 1)], {}) in indexes

        identity_indexes = database["legacy_identity_map"].indexes
        assert (
            [("entity_type", 1), ("firebase_key", 1)],
            {"unique": True},
        ) in identity_indexes
        for field in (
            "firebase_uid",
            "mongo_user_id",
            "mongo_customer_id",
            "mongo_provider_id",
            "mongo_request_id",
        ):
            assert ([(field, 1)], {"sparse": True}) in identity_indexes

    asyncio.run(run_test())


def test_apply_is_idempotent_and_conflicts_never_overwrite() -> None:
    async def run_test() -> None:
        database = FakeDatabase()
        repository = LegacyFirebaseRepository(database)
        data = {
            "customers": {
                "firebase-customer": {
                    "id": "firebase-customer",
                    "fullName": "Original Name",
                    "location": {"latitude": 6.9, "longitude": 79.8},
                }
            }
        }

        first_report = await apply_snapshots(repository, data)
        assert first_report["summary"]["inserted"] == 1
        assert first_report["summary"]["conflicts"] == 0

        collection = database[LEGACY_COLLECTIONS["customers"]]
        stored_before = deepcopy(collection.documents[("customers", "firebase-customer")])
        assert len(collection.update_payloads) == 1

        second_report = await apply_snapshots(repository, data)
        assert second_report["summary"]["unchanged"] == 1
        assert len(collection.update_payloads) == 1

        changed = deepcopy(data)
        changed["customers"]["firebase-customer"]["fullName"] = "Changed Name"
        conflict_report = await apply_snapshots(repository, changed)
        assert conflict_report["summary"]["conflicts"] == 1
        assert collection.documents[("customers", "firebase-customer")] == stored_before
        assert len(collection.update_payloads) == 1

        verify_report = await verify_snapshots(repository, data)
        assert verify_report["summary"]["verified"] == 1
        assert verify_report["issues"] == []

        mismatch_report = await verify_snapshots(repository, changed)
        assert mismatch_report["summary"]["mismatched"] == 1

    asyncio.run(run_test())


def test_identity_resolution_prefers_uid_and_rejects_role_mismatch() -> None:
    async def run_test() -> None:
        lookup = FakeUserLookup(
            [
                {
                    "user_id": "UPROVIDER",
                    "email": "old-address@example.com",
                    "role": "provider",
                    "legacy": {"firebase_uid": "firebase-provider-uid"},
                },
                {
                    "user_id": "UWRONGROLE",
                    "email": "customer@example.com",
                    "role": "provider",
                },
                {
                    "user_id": "UINACTIVE",
                    "email": "inactive@example.com",
                    "role": "customer",
                    "is_active": False,
                },
            ]
        )

        uid_match = await resolve_identity_mapping(
            lookup,
            "providers",
            "provider-key",
            {
                "uid": "firebase-provider-uid",
                "email": "new-address@example.com",
                "role": "provider",
            },
        )
        assert uid_match["match_status"] == "matched"
        assert uid_match["match_method"] == "uid"
        assert uid_match["mongo_user_id"] == "UPROVIDER"

        wrong_role = await resolve_identity_mapping(
            lookup,
            "customers",
            "customer-key",
            {"email": " Customer@Example.com ", "role": "customer"},
        )
        assert wrong_role["match_status"] == "ambiguous"
        assert wrong_role["match_reason"] == "role_mismatch"
        assert wrong_role["mongo_user_id"] is None

        inactive = await resolve_identity_mapping(
            lookup,
            "customers",
            "inactive-key",
            {"email": "inactive@example.com", "role": "customer"},
        )
        assert inactive["match_status"] == "ambiguous"
        assert inactive["match_reason"] == "inactive_backend_user"
        assert inactive["mongo_user_id"] is None

        unmatched = await resolve_identity_mapping(
            lookup,
            "customers",
            "unmatched-key",
            {"fullName": "No Email Customer"},
        )
        assert unmatched["match_status"] == "unmatched"
        assert unmatched["match_reason"] == "no_linkable_identity"

    asyncio.run(run_test())


def test_identity_resolution_does_not_choose_between_duplicate_emails() -> None:
    async def run_test() -> None:
        lookup = FakeUserLookup(
            [
                {
                    "user_id": "UCUSTOMER1",
                    "email": "duplicate@example.com",
                    "role": "customer",
                },
                {
                    "user_id": "UCUSTOMER2",
                    "email": "duplicate@example.com",
                    "role": "customer",
                },
            ]
        )

        mapping = await resolve_identity_mapping(
            lookup,
            "customers",
            "duplicate-customer-key",
            {"email": " Duplicate@Example.com ", "role": "customer"},
        )

        assert mapping["match_method"] == "normalized_email"
        assert mapping["match_status"] == "ambiguous"
        assert mapping["match_reason"] == "duplicate_normalized_email"
        assert mapping["mongo_user_id"] is None

    asyncio.run(run_test())


def test_identity_decisions_are_idempotent_and_never_overwritten() -> None:
    async def run_test() -> None:
        database = FakeDatabase()
        repository = LegacyFirebaseRepository(database)
        mapping = {
            "entity_type": "customer",
            "firebase_key": "firebase-customer",
            "firebase_uid": None,
            "mongo_user_id": "U123",
            "mongo_customer_id": "C123",
            "mongo_provider_id": None,
            "mongo_request_id": None,
            "match_method": "normalized_email",
            "match_status": "matched",
            "match_reason": "unique_identity_match",
            "migration_version": "firebase-to-mongo-v1",
        }

        assert await repository.store_identity_mapping(mapping) == "inserted"
        assert await repository.store_identity_mapping(mapping) == "unchanged"

        changed = deepcopy(mapping)
        changed["mongo_user_id"] = "UDIFFERENT"
        assert await repository.store_identity_mapping(changed) == "conflict"

        collection = database["legacy_identity_map"]
        stored = collection.documents[("customer", "firebase-customer")]
        assert stored["mongo_user_id"] == "U123"
        assert len(collection.update_payloads) == 1

    asyncio.run(run_test())


def test_apply_creates_explicit_identity_decisions_when_lookup_is_enabled() -> None:
    async def run_test() -> None:
        database = FakeDatabase()
        repository = LegacyFirebaseRepository(database)
        lookup = FakeUserLookup(
            [
                {
                    "user_id": "UCUSTOMER",
                    "email": "customer@example.com",
                    "role": "customer",
                }
            ]
        )
        data = {
            "customers": {
                "customer-key": {
                    "email": "customer@example.com",
                    "role": "customer",
                }
            },
            "providers": {
                "provider-key": {
                    "uid": "unknown-firebase-uid",
                    "email": "provider@example.com",
                    "role": "provider",
                }
            },
        }

        report = await apply_snapshots(repository, data, lookup)

        assert report["summary"]["identity_expected"] == 2
        assert report["summary"]["identity_inserted"] == 2
        assert report["summary"]["identity_matched"] == 1
        assert report["summary"]["identity_unmatched"] == 1
        assert report["summary"]["identity_conflicts"] == 0
        identity_documents = database["legacy_identity_map"].documents
        assert identity_documents[("customer", "customer-key")]["mongo_user_id"] == (
            "UCUSTOMER"
        )
        assert identity_documents[("provider", "provider-key")]["match_status"] == (
            "unmatched"
        )

    asyncio.run(run_test())
