from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError


class DuplicateEmailError(Exception):
    pass


class UserRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["users"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("user_id", ASCENDING)], unique=True)
        await self.collection.create_index([("email", ASCENDING)], unique=True)

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError as error:
            raise DuplicateEmailError from error
        return document

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email.lower()})

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"user_id": user_id})
