from typing import Any

from pymongo import ASCENDING, DESCENDING


class ServiceRequestRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["service_requests"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("request_id", ASCENDING)], unique=True)
        await self.collection.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        await self.collection.create_index(
            [("category", ASCENDING), ("district", ASCENDING), ("city", ASCENDING)]
        )

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.collection.insert_one(document)
        return document

    async def find_by_id(self, request_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"request_id": request_id})

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", DESCENDING)
        return await cursor.to_list(length=limit)
