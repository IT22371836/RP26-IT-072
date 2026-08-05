from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.schemas.common import utc_now


class ProviderProfileExistsError(Exception):
    pass


class ProviderRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["providers"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("provider_id", ASCENDING)], unique=True)
        await self.collection.create_index([("user_id", ASCENDING)], unique=True)
        await self.collection.create_index(
            [("category", ASCENDING), ("district", ASCENDING), ("city", ASCENDING)]
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
