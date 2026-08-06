from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.repositories.concurrency import ProfileConcurrencyError
from app.schemas.common import new_public_id, utc_now


class ProviderProfileExistsError(Exception):
    pass


class ProviderRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["providers"]
        self.verification_events = database["provider_verification_events"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("provider_id", ASCENDING)], unique=True)
        await self.collection.create_index([("user_id", ASCENDING)], unique=True)
        await self.collection.create_index(
            [("category", ASCENDING), ("district", ASCENDING), ("city", ASCENDING)]
        )
        await self.verification_events.create_index([("event_id", ASCENDING)], unique=True)
        await self.verification_events.create_index(
            [("provider_id", ASCENDING), ("created_at", DESCENDING)]
        )

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError as error:
            raise ProviderProfileExistsError from error
        return document

    async def find_by_id(self, provider_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"provider_id": provider_id})

    async def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"user_id": user_id})

    async def update_by_user_id(
        self,
        user_id: str,
        updates: dict[str, Any],
        *,
        expected_updated_at: Any | None = None,
    ) -> dict[str, Any] | None:
        query = {"user_id": user_id}
        if expected_updated_at is not None:
            query["updated_at"] = expected_updated_at
        result = await self.collection.update_one(query, {"$set": updates})
        if expected_updated_at is not None and result.matched_count == 0:
            if await self.find_by_user_id(user_id) is not None:
                raise ProfileConcurrencyError
            return None
        return await self.find_by_user_id(user_id)

    async def add_document(
        self,
        user_id: str,
        category: str,
        document: dict[str, Any],
    ) -> dict[str, Any] | None:
        result = await self.collection.update_one(
            {
                "user_id": user_id,
                "verified": {"$ne": True},
                "documents.status": {"$ne": True},
                f"documents.{category}.file_id": {"$ne": document["file_id"]},
            },
            {
                "$push": {f"documents.{category}": document},
                "$set": {"updated_at": utc_now()},
            },
        )
        return await self.find_by_user_id(user_id) if result.modified_count else None

    async def soft_delete_document(
        self,
        user_id: str,
        category: str,
        file_id: str,
    ) -> dict[str, Any] | None:
        result = await self.collection.update_one(
            {
                "user_id": user_id,
                "verified": {"$ne": True},
                "documents.status": {"$ne": True},
                f"documents.{category}": {
                    "$elemMatch": {"file_id": file_id, "deleted_at": None}
                },
            },
            {
                "$set": {
                    f"documents.{category}.$.deleted_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.find_by_user_id(user_id) if result.modified_count else None

    async def request_document_verification(self, user_id: str) -> dict[str, Any] | None:
        result = await self.collection.update_one(
            {
                "user_id": user_id,
                "verified": {"$ne": True},
                "documents.status": {"$ne": True},
            },
            {
                "$set": {
                    "documents.status": True,
                    "documents.verified": False,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.find_by_user_id(user_id) if result.modified_count else None

    async def set_verification(
        self,
        provider_id: str,
        admin_user_id: str,
        verified: bool,
        reason: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        existing = await self.find_by_id(provider_id)
        if existing is None:
            return None

        now = utc_now()
        event = {
            "event_id": new_public_id("V"),
            "provider_id": provider_id,
            "admin_user_id": admin_user_id,
            "previous_verified": bool(existing.get("verified", False)),
            "verified": verified,
            "reason": reason,
            "created_at": now,
        }
        updates: dict[str, Any] = {
            "verified": verified,
            "documents.status": False,
            "documents.verified": verified,
            "verification.status": "verified" if verified else "revoked",
            "verification.last_action_by": admin_user_id,
            "verification.last_action_at": now,
            "verification.last_reason": reason,
            "updated_at": now,
        }
        if verified:
            updates["verification.verified_at"] = now
            updates["verification.verified_by"] = admin_user_id
        else:
            updates["verification.revoked_at"] = now
            updates["verification.revoked_by"] = admin_user_id

        await self.collection.update_one({"provider_id": provider_id}, {"$set": updates})
        await self.verification_events.insert_one(event)
        updated = await self.find_by_id(provider_id)
        if updated is None:
            raise RuntimeError("Provider disappeared during verification update")
        return updated, event

    async def list_verification_events(
        self, provider_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        return (
            await self.verification_events.find({"provider_id": provider_id})
            .sort("created_at", DESCENDING)
            .to_list(length=limit)
        )

    async def list_all(self, limit: int = 10_000) -> list[dict[str, Any]]:
        return await self.collection.find({}).limit(limit).to_list(length=limit)

    async def list_by_ids(self, provider_ids: list[str]) -> list[dict[str, Any]]:
        if not provider_ids:
            return []
        return await self.collection.find(
            {"provider_id": {"$in": provider_ids}}
        ).to_list(length=len(provider_ids))

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def update_statistics(
        self, provider_id: str, statistics: dict[str, int | float]
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {"provider_id": provider_id},
            {"$set": {**statistics, "updated_at": utc_now()}},
            return_document=True,
        )
