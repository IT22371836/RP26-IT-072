from typing import Any

from pymongo import ASCENDING, DESCENDING, ReplaceOne

from app.schemas.common import utc_now


class Component4Repository:
    """Persistence for Component 4 runs and their ranked provider snapshots."""

    def __init__(self, database: Any) -> None:
        self.runs = database["component4_runs"]
        self.provider_scores = database["component4_provider_scores"]

    async def ensure_indexes(self) -> None:
        await self.runs.create_index([("run_id", ASCENDING)], unique=True)
        await self.runs.create_index(
            [("user_id", ASCENDING), ("request_id", ASCENDING), ("created_at", DESCENDING)]
        )
        await self.runs.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
        await self.provider_scores.create_index(
            [("run_id", ASCENDING), ("provider_id", ASCENDING)],
            unique=True,
        )
        await self.provider_scores.create_index(
            [("run_id", ASCENDING), ("rank", ASCENDING)]
        )
        await self.provider_scores.create_index(
            [("provider_id", ASCENDING), ("created_at", DESCENDING)]
        )

    async def find_completed_response(
        self,
        run_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        document = await self.runs.find_one(
            {"run_id": run_id, "user_id": user_id, "status": "completed"},
            {"response": 1},
        )
        if document is None:
            return None
        response = document.get("response")
        return response if isinstance(response, dict) else None

    async def persist_completed(
        self,
        run_document: dict[str, Any],
        provider_documents: list[dict[str, Any]],
    ) -> None:
        run_id = str(run_document["run_id"])
        started_at = utc_now()
        await self.runs.update_one(
            {"run_id": run_id},
            {
                "$set": {
                    **run_document,
                    "status": "running",
                    "started_at": started_at,
                    "updated_at": started_at,
                },
                "$setOnInsert": {"created_at": started_at},
            },
            upsert=True,
        )
        try:
            if provider_documents:
                await self.provider_scores.bulk_write(
                    [
                        ReplaceOne(
                            {
                                "run_id": run_id,
                                "provider_id": document["provider_id"],
                            },
                            document,
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
                {
                    "$set": {
                        "status": "failed",
                        "updated_at": utc_now(),
                    },
                    "$unset": {"response": ""},
                },
            )
            raise
