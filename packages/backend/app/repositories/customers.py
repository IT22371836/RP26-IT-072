from typing import Any

from pymongo import ASCENDING

from app.repositories.concurrency import ProfileConcurrencyError


class CustomerProfileRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["customer_profiles"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("customer_id", ASCENDING)], unique=True)
        await self.collection.create_index([("user_id", ASCENDING)], unique=True)

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.collection.insert_one(document)
        return document

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
