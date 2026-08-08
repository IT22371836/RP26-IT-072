from typing import Any

from pymongo import DESCENDING


class IntegrationReadRepository:
    """Read-only projections over immutable Firebase snapshot collections."""

    def __init__(self, database: Any) -> None:
        self.daily_demand = database["legacy_firebase_daily_demand"]
        self.filter_requests = database["legacy_firebase_filter_requests"]

    async def get_current_daily_demand(self) -> dict[str, Any] | None:
        snapshot = await self.daily_demand.find_one({"source_key": "current"})
        if snapshot is None:
            snapshot = await self.daily_demand.find_one(
                {},
                sort=[("imported_at", DESCENDING)],
            )
        source_record = snapshot.get("source_record") if snapshot else None
        return source_record if isinstance(source_record, dict) else None

    async def list_filter_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        snapshots = await (
            self.filter_requests.find({})
            .sort("source_record.output_results.evaluated_at", DESCENDING)
            .limit(limit)
            .to_list(length=limit)
        )
        results: list[dict[str, Any]] = []
        for snapshot in snapshots:
            source_record = snapshot.get("source_record")
            if not isinstance(source_record, dict):
                continue
            results.append({"id": str(snapshot["source_key"]), **source_record})
        return results
