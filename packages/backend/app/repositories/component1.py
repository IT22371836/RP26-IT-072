from typing import Any

from app.repositories.firebase_store import FirebaseStore
from app.schemas.common import utc_now


class Component1Repository:
    """Firebase persistence for Component 1 runs and ranked Top-20 snapshots."""

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def persist_completed(
        self,
        run_document: dict[str, Any],
        provider_documents: list[dict[str, Any]],
    ) -> None:
        run_id = str(run_document["run_id"])
        now = utc_now()
        await self.store.set(
            f"component1/runs/{run_id}",
            {**run_document, "status": "running", "updated_at": now},
        )
        try:
            updates = {
                f"component1/provider_scores/{run_id}__{document['provider_id']}": document
                for document in provider_documents
            }
            if updates:
                await self.store.multi_update(updates)
            completed_at = utc_now()
            await self.store.set(
                f"component1/runs/{run_id}",
                {
                    **run_document,
                    "status": "completed",
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
            )
        except Exception:
            await self.store.update(
                f"component1/runs/{run_id}",
                {"status": "failed", "updated_at": utc_now()},
            )
            raise
