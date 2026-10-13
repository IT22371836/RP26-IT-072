from typing import Any

from app.repositories.firebase_store import FirebaseStore


class Component3Repository:
    """Persist the current demand forecast through the shared Firebase adapter."""

    PATH = "daily_demand/current"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def save_current_forecast(self, payload: dict[str, Any]) -> None:
        await self.store.set(self.PATH, payload)
