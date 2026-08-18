from typing import Any

from app.repositories.firebase_store import FirebaseStore
from app.schemas.common import utc_now


class Component4Repository:
    """Firebase persistence for Component 4 runs and provider score snapshots."""

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def find_completed_response(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        document = await self.store.get(f"component4/runs/{run_id}")
        if (
            not isinstance(document, dict)
            or document.get("user_id") != user_id
            or document.get("status") != "completed"
        ):
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
        await self.store.set(
            f"component4/runs/{run_id}",
            {
                **run_document,
                "status": "running",
                "started_at": started_at,
                "updated_at": started_at,
            },
        )
        try:
            updates = {
                f"component4/provider_scores/{run_id}__{document['provider_id']}": document
                for document in provider_documents
            }
            if updates:
                await self.store.multi_update(updates)
            completed_at = utc_now()
            await self.store.set(
                f"component4/runs/{run_id}",
                {
                    **run_document,
                    "status": "completed",
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
            )
        except Exception:
            await self.store.update(
                f"component4/runs/{run_id}",
                {"status": "failed", "updated_at": utc_now()},
            )
            raise
