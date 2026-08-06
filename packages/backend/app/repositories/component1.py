from typing import Any

from pymongo import ASCENDING, DESCENDING, UpdateOne

from app.schemas.common import utc_now


class Component1Repository:
    """Persistence for Component 1 recommendation runs and score snapshots."""

    def __init__(self, database: Any) -> None:
        self.runs = database["component1_runs"]
        self.provider_scores = database["component1_provider_scores"]

    async def ensure_indexes(self) -> None:
        await self.runs.create_index([("run_id", ASCENDING)], unique=True)
        await self.runs.create_index(
            [("user_id", ASCENDING), ("request_id", ASCENDING), ("created_at", DESCENDING)]
        )
        await self.provider_scores.create_index(
            [("run_id", ASCENDING), ("provider_id", ASCENDING)], unique=True
        )
        await self.provider_scores.create_index(
            [("run_id", ASCENDING), ("rank", ASCENDING)]
        )
        await self.provider_scores.create_index(
            [("provider_id", ASCENDING), ("created_at", DESCENDING)]
        )

    async def persist_completed(
        self,
        run_document: dict[str, Any],
        provider_documents: list[dict[str, Any]],
    ) -> None:
        """Idempotently persist one completed run and its ranked Top-20 scores."""

        run_id = str(run_document["run_id"])
        now = utc_now()
        await self.runs.update_one(
            {"run_id": run_id},
            {
                "$set": {**run_document, "status": "running", "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        try:
            if provider_documents:
                await self.provider_scores.bulk_write(
                    [
                        UpdateOne(
                            {
                                "run_id": run_id,
                                "provider_id": document["provider_id"],
                            },
                            {"$set": document},
                            upsert=True,
                        )
                        for document in provider_documents
                    ],
                    ordered=True,
                )
            completed_at = utc_now()
            await self.runs.update_one(
                {"run_id": run_id},
                {
                    "$set": {
                        **run_document,
                        "status": "completed",
                        "completed_at": completed_at,
                        "updated_at": completed_at,
                    }
                },
            )
        except Exception:
            await self.runs.update_one(
                {"run_id": run_id},
                {"$set": {"status": "failed", "updated_at": utc_now()}},
            )
            raise
