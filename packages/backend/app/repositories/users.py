from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError


class DuplicateEmailError(Exception):
    pass


class FirebaseLinkConflictError(Exception):
    pass


class UserRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["users"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("user_id", ASCENDING)], unique=True)
        await self.collection.create_index([("email", ASCENDING)], unique=True)
        await self.collection.create_index(
            [("legacy.firebase_uid", ASCENDING)],
            unique=True,
            partialFilterExpression={"legacy.firebase_uid": {"$type": "string"}},
        )

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError as error:
            raise DuplicateEmailError from error
        return document

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email.lower()})

    async def find_all_by_email(
        self, email: str, *, limit: int = 2
    ) -> list[dict[str, Any]]:
        """Return enough exact normalized-email matches to detect ambiguity."""

        normalized_email = email.strip().lower()
        return await self.collection.find(
            {
                "$expr": {
                    "$eq": [
                        {"$toLower": {"$trim": {"input": "$email"}}},
                        normalized_email,
                    ]
                }
            }
        ).to_list(length=limit)

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"user_id": user_id})

    async def find_by_firebase_uid(self, firebase_uid: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"legacy.firebase_uid": firebase_uid})

    async def ensure_firebase_identity(
        self,
        *,
        firebase_uid: str,
        email: str,
        full_name: str,
        role: str,
        now: Any,
        user_id: str,
    ) -> dict[str, Any]:
        """Create/link a non-password Mongo shadow used only by the ML pipeline."""

        existing = await self.find_by_firebase_uid(firebase_uid)
        if existing is not None:
            return existing

        email_matches = await self.find_all_by_email(email)
        if len(email_matches) > 1:
            raise FirebaseLinkConflictError
        if email_matches:
            existing = email_matches[0]
            if str(existing.get("role")) != role:
                raise FirebaseLinkConflictError
            try:
                result = await self.collection.update_one(
                    {
                        "user_id": existing["user_id"],
                        "$or": [
                            {"legacy.firebase_uid": {"$exists": False}},
                            {"legacy.firebase_uid": firebase_uid},
                        ],
                    },
                    {
                        "$set": {
                            "legacy.firebase_uid": firebase_uid,
                            "auth_source": "firebase",
                            "updated_at": now,
                        }
                    },
                )
            except DuplicateKeyError as error:
                raise FirebaseLinkConflictError from error
            if result.matched_count != 1:
                raise FirebaseLinkConflictError
            linked = await self.find_by_firebase_uid(firebase_uid)
            if linked is None:
                raise FirebaseLinkConflictError
            return linked

        document = {
            "user_id": user_id,
            "email": email.strip().lower(),
            "full_name": full_name,
            "role": role,
            "is_active": True,
            "auth_source": "firebase",
            "auth_version": 1,
            "legacy": {"firebase_uid": firebase_uid},
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self.collection.insert_one(document)
            return document
        except DuplicateKeyError as error:
            concurrent = await self.find_by_firebase_uid(firebase_uid)
            if concurrent is not None:
                return concurrent
            raise FirebaseLinkConflictError from error

    async def list_all(self, limit: int = 500) -> list[dict[str, Any]]:
        return await self.collection.find({}).sort("created_at", DESCENDING).to_list(length=limit)

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def set_active(self, user_id: str, is_active: bool) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {"user_id": user_id}, {"$set": {"is_active": is_active}}, return_document=True
        )

    async def link_firebase_identity(
        self,
        user_id: str,
        firebase_uid: str,
        firebase_email: str,
        hashed_password: str,
        linked_at: Any,
        auth_version: int,
    ) -> dict[str, Any]:
        try:
            result = await self.collection.update_one(
                {
                    "user_id": user_id,
                    "is_active": {"$ne": False},
                    "legacy.firebase_uid": {"$exists": False},
                },
                {
                    "$set": {
                        "legacy.firebase_uid": firebase_uid,
                        "hashed_password": hashed_password,
                        "auth_version": auth_version,
                        "auth_transition.firebase_email_at_link": firebase_email,
                        "auth_transition.firebase_linked_at": linked_at,
                        "auth_transition.password_established_at": linked_at,
                        "updated_at": linked_at,
                    }
                },
            )
        except DuplicateKeyError as error:
            raise FirebaseLinkConflictError from error
        if result.matched_count != 1:
            raise FirebaseLinkConflictError
        document = await self.find_by_id(user_id)
        if document is None:
            raise RuntimeError("Linked user disappeared")
        return document

    async def change_password(
        self,
        user_id: str,
        hashed_password: str,
        changed_at: Any,
        current_auth_version: int,
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {"user_id": user_id, "auth_version": current_auth_version},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "auth_transition.password_changed_at": changed_at,
                    "updated_at": changed_at,
                },
                "$inc": {"auth_version": 1},
            },
            return_document=True,
        )
