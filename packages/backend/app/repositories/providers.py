from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError


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

    async def count(self) -> int:
        return await self.collection.count_documents({})
