from typing import Any

from app.repositories.firebase_store import FirebaseStore, sorted_records


class ServiceRequestRepository:
    PATH = "component1/service_requests"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.store.set(f"{self.PATH}/{document['request_id']}", document)
        return document

    async def find_by_id(self, request_id: str) -> dict[str, Any] | None:
        value = await self.store.get(f"{self.PATH}/{request_id}")
        return value if isinstance(value, dict) else None

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        value = await self.store.get(self.PATH) or {}
        filtered = {
            key: item
            for key, item in value.items()
            if isinstance(item, dict) and item.get("user_id") == user_id
        }
        return sorted_records(filtered, field="created_at", limit=limit)

    async def list_all(self, limit: int = 500) -> list[dict[str, Any]]:
        return sorted_records(await self.store.get(self.PATH), field="created_at", limit=limit)

    async def count(self) -> int:
        return len(await self.store.shallow(self.PATH))
