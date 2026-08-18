from typing import Any

from app.repositories.concurrency import ProfileConcurrencyError
from app.repositories.firebase_store import FirebaseStore, nested_set


class CustomerProfileRepository:
    PATH = "core/customer_profiles"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.store.set(f"{self.PATH}/{document['customer_id']}", document)
        await self.store.set(
            f"core/indexes/customer_profiles_by_user/{document['user_id']}",
            document["customer_id"],
        )
        return document

    async def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        customer_id = await self.store.get(f"core/indexes/customer_profiles_by_user/{user_id}")
        if isinstance(customer_id, str):
            value = await self.store.get(f"{self.PATH}/{customer_id}")
            return value if isinstance(value, dict) else None
        records = await self.store.get(self.PATH) or {}
        for key, item in records.items():
            if isinstance(item, dict) and item.get("user_id") == user_id:
                await self.store.set(f"core/indexes/customer_profiles_by_user/{user_id}", key)
                return item
        return None

    async def update_by_user_id(
        self,
        user_id: str,
        updates: dict[str, Any],
        *,
        expected_updated_at: Any | None = None,
    ) -> dict[str, Any] | None:
        current = await self.find_by_user_id(user_id)
        if current is None:
            return None
        customer_id = str(current["customer_id"])
        conflict = False

        def apply(value: Any) -> Any:
            nonlocal conflict
            if not isinstance(value, dict):
                return value
            if expected_updated_at is not None and str(value.get("updated_at")) != str(
                expected_updated_at
            ):
                conflict = True
                return value
            for key, item in updates.items():
                nested_set(value, key, item)
            return value

        updated = await self.store.transaction(f"{self.PATH}/{customer_id}", apply)
        if conflict:
            raise ProfileConcurrencyError
        return updated if isinstance(updated, dict) else None
