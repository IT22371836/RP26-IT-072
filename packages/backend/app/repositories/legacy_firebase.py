from copy import deepcopy
from typing import Any, Literal

from pymongo import ASCENDING

from app.schemas.common import utc_now

MIGRATION_VERSION = "firebase-to-mongo-v1"

LEGACY_COLLECTIONS = {
    "customers": "legacy_firebase_customers",
    "providers": "legacy_firebase_providers",
    "filter_requests": "legacy_firebase_filter_requests",
    "daily_demand": "legacy_firebase_daily_demand",
}

SnapshotStatus = Literal["inserted", "unchanged", "conflict"]


class LegacyFirebaseRepository:
    """Append-only persistence for exact Firebase RTDB source records."""

    def __init__(self, database: Any) -> None:
        self.database = database
        self.identity_map = database["legacy_identity_map"]

    async def ensure_indexes(self) -> None:
        for collection_name in LEGACY_COLLECTIONS.values():
            collection = self.database[collection_name]
            await collection.create_index(
                [("source_node", ASCENDING), ("source_key", ASCENDING)],
                unique=True,
            )
            await collection.create_index([("source_sha256", ASCENDING)])

        await self.identity_map.create_index(
            [("entity_type", ASCENDING), ("firebase_key", ASCENDING)],
            unique=True,
        )
        for field in (
            "firebase_uid",
            "mongo_user_id",
            "mongo_customer_id",
            "mongo_provider_id",
            "mongo_request_id",
        ):
            await self.identity_map.create_index([(field, ASCENDING)], sparse=True)

    async def store_snapshot(self, snapshot: dict[str, Any]) -> SnapshotStatus:
        """Insert once, return conflicts, and never mutate an existing snapshot."""

        source_node = str(snapshot["source_node"])
        if source_node not in LEGACY_COLLECTIONS:
            raise ValueError(f"Unsupported Firebase node: {source_node}")

        collection = self.database[LEGACY_COLLECTIONS[source_node]]
        identity = {
            "source_node": source_node,
            "source_key": str(snapshot["source_key"]),
        }
        existing = await collection.find_one(identity)
        if existing is not None:
            return self._compare_existing(existing, snapshot)

        document = deepcopy(snapshot)
        document["imported_at"] = utc_now()
        result = await collection.update_one(
            identity,
            {"$setOnInsert": document},
            upsert=True,
        )
        if result.upserted_id is not None:
            return "inserted"

        # Another migration worker may have inserted the key between find and update.
        existing = await collection.find_one(identity)
        if existing is None:
            raise RuntimeError(
                f"Snapshot upsert returned no document for {source_node}/{identity['source_key']}"
            )
        return self._compare_existing(existing, snapshot)

    async def find_snapshot(self, source_node: str, source_key: str) -> dict[str, Any] | None:
        if source_node not in LEGACY_COLLECTIONS:
            raise ValueError(f"Unsupported Firebase node: {source_node}")
        return await self.database[LEGACY_COLLECTIONS[source_node]].find_one(
            {"source_node": source_node, "source_key": source_key}
        )

    async def store_identity_mapping(self, mapping: dict[str, Any]) -> SnapshotStatus:
        """Insert one identity decision without overwriting a previous decision."""

        identity = {
            "entity_type": str(mapping["entity_type"]),
            "firebase_key": str(mapping["firebase_key"]),
        }
        existing = await self.identity_map.find_one(identity)
        if existing is not None:
            return self._compare_identity_mapping(existing, mapping)

        document = deepcopy(mapping)
        now = utc_now()
        document["created_at"] = now
        document["updated_at"] = now
        result = await self.identity_map.update_one(
            identity,
            {"$setOnInsert": document},
            upsert=True,
        )
        if result.upserted_id is not None:
            return "inserted"

        existing = await self.identity_map.find_one(identity)
        if existing is None:
            raise RuntimeError(
                "Identity upsert returned no document for "
                f"{identity['entity_type']}/{identity['firebase_key']}"
            )
        return self._compare_identity_mapping(existing, mapping)

    @staticmethod
    def _compare_existing(
        existing: dict[str, Any], snapshot: dict[str, Any]
    ) -> SnapshotStatus:
        if (
            existing.get("source_sha256") == snapshot.get("source_sha256")
            and existing.get("source_record") == snapshot.get("source_record")
            and existing.get("migration_version") == MIGRATION_VERSION
        ):
            return "unchanged"
        return "conflict"

    @staticmethod
    def _compare_identity_mapping(
        existing: dict[str, Any], mapping: dict[str, Any]
    ) -> SnapshotStatus:
        compared_fields = (
            "entity_type",
            "firebase_key",
            "firebase_uid",
            "mongo_user_id",
            "mongo_customer_id",
            "mongo_provider_id",
            "mongo_request_id",
            "match_method",
            "match_status",
            "match_reason",
            "migration_version",
        )
        if all(existing.get(field) == mapping.get(field) for field in compared_fields):
            return "unchanged"
        return "conflict"
