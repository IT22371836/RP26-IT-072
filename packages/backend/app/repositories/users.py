from __future__ import annotations

import hashlib
from typing import Any

from app.repositories.firebase_store import FirebaseStore, nested_set, sorted_records


class DuplicateEmailError(Exception):
    pass


class FirebaseLinkConflictError(Exception):
    pass


def _email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class UserRepository:
    PATH = "core/users"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        user_id = str(document["user_id"])
        email = str(document["email"]).strip().lower()
        existing = await self.find_by_email(email)
        if existing is not None or await self.find_by_id(user_id) is not None:
            raise DuplicateEmailError
        payload = {**document, "email": email}
        await self.store.multi_update(
            {
                f"{self.PATH}/{user_id}": payload,
                f"core/indexes/users_by_email/{_email_key(email)}": user_id,
            }
        )
        return payload

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        user_id = await self.store.get(f"core/indexes/users_by_email/{_email_key(email)}")
        if isinstance(user_id, str):
            return await self.find_by_id(user_id)
        matches = await self.find_all_by_email(email, limit=1)
        return matches[0] if matches else None

    async def find_all_by_email(self, email: str, *, limit: int = 2) -> list[dict[str, Any]]:
        normalized = email.strip().lower()
        records = await self.store.get(self.PATH) or {}
        return [
            item
            for item in records.values()
            if isinstance(item, dict) and str(item.get("email") or "").strip().lower() == normalized
        ][:limit]

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        value = await self.store.get(f"{self.PATH}/{user_id}")
        return value if isinstance(value, dict) else None

    async def find_by_firebase_uid(self, firebase_uid: str) -> dict[str, Any] | None:
        user_id = await self.store.get(f"core/indexes/users_by_firebase_uid/{firebase_uid}")
        if isinstance(user_id, str):
            return await self.find_by_id(user_id)
        records = await self.store.get(self.PATH) or {}
        for item in records.values():
            if (
                isinstance(item, dict)
                and item.get("legacy", {}).get("firebase_uid") == firebase_uid
            ):
                return item
        return None

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
        existing = await self.find_by_firebase_uid(firebase_uid)
        if existing is not None:
            return existing
        matches = await self.find_all_by_email(email)
        if len(matches) > 1 or (matches and str(matches[0].get("role")) != role):
            raise FirebaseLinkConflictError
        document = (
            matches[0]
            if matches
            else {
                "user_id": user_id,
                "email": email.strip().lower(),
                "full_name": full_name,
                "role": role,
                "is_active": True,
                "created_at": now,
            }
        )
        assigned_id = str(document["user_id"])
        if document.get("legacy", {}).get("firebase_uid") not in (None, firebase_uid):
            raise FirebaseLinkConflictError
        document = {**document, "auth_source": "firebase", "auth_version": 1, "updated_at": now}
        document.setdefault("legacy", {})["firebase_uid"] = firebase_uid

        conflict = False

        def claim(current: Any) -> Any:
            nonlocal conflict
            if current in (None, assigned_id):
                return assigned_id
            conflict = True
            return current

        await self.store.transaction(f"core/indexes/users_by_firebase_uid/{firebase_uid}", claim)
        if conflict:
            raise FirebaseLinkConflictError
        await self.store.multi_update(
            {
                f"{self.PATH}/{assigned_id}": document,
                f"core/indexes/users_by_email/{_email_key(email)}": assigned_id,
            }
        )
        return document

    async def list_all(self, limit: int = 500) -> list[dict[str, Any]]:
        return sorted_records(await self.store.get(self.PATH), field="created_at", limit=limit)

    async def count(self) -> int:
        return len(await self.store.shallow(self.PATH))

    async def set_active(self, user_id: str, is_active: bool) -> dict[str, Any] | None:
        document = await self.find_by_id(user_id)
        if document is None:
            return None
        document["is_active"] = is_active
        await self.store.set(f"{self.PATH}/{user_id}", document)
        return document

    async def link_firebase_identity(
        self,
        user_id: str,
        firebase_uid: str,
        firebase_email: str,
        hashed_password: str,
        linked_at: Any,
        auth_version: int,
    ) -> dict[str, Any]:
        document = await self.find_by_id(user_id)
        if document is None or document.get("legacy", {}).get("firebase_uid"):
            raise FirebaseLinkConflictError
        existing = await self.find_by_firebase_uid(firebase_uid)
        if existing is not None:
            raise FirebaseLinkConflictError
        nested_set(document, "legacy.firebase_uid", firebase_uid)
        document.update({"auth_version": auth_version, "updated_at": linked_at})
        nested_set(document, "auth_transition.firebase_email_at_link", firebase_email)
        nested_set(document, "auth_transition.firebase_linked_at", linked_at)
        # Password hashes are intentionally not copied into Firebase RTDB.
        await self.store.multi_update(
            {
                f"{self.PATH}/{user_id}": document,
                f"core/indexes/users_by_firebase_uid/{firebase_uid}": user_id,
            }
        )
        return document

    async def change_password(
        self,
        user_id: str,
        hashed_password: str,
        changed_at: Any,
        current_auth_version: int,
    ) -> dict[str, Any] | None:
        # Password lifecycle belongs exclusively to Firebase Authentication.
        return None
