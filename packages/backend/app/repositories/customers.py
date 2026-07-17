from typing import Any

from pymongo import ASCENDING


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
        self, user_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        await self.collection.update_one({"user_id": user_id}, {"$set": updates})
        return await self.find_by_user_id(user_id)
