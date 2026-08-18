from typing import Any

from app.repositories.firebase_store import FirebaseStore, sorted_records


class IntegrationReadRepository:
    """Read-only projections over the authoritative Firebase nodes."""

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def get_current_daily_demand(self) -> dict[str, Any] | None:
        value = await self.store.get("daily_demand/current")
        if isinstance(value, dict):
            return value
        root = await self.store.get("daily_demand")
        if isinstance(root, dict):
            records = sorted_records(root, field="generated_at", limit=1)
            return records[0] if records else root
        return None

    async def list_filter_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        value = await self.store.get("filter_requests") or {}
        records = sorted_records(value, field="output_results.evaluated_at", limit=limit)
        return [{"id": str(record.get("request_id") or ""), **record} for record in records]
