from __future__ import annotations

from datetime import timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.pipeline.schemas import PipelineStatus
from app.schemas.common import utc_now

STATUS_STAGE = {
    PipelineStatus.INITIALIZING: "pipeline",
    PipelineStatus.CREATED: "pipeline",
    PipelineStatus.COMPONENT1_RUNNING: "component1",
    PipelineStatus.COMPONENT1_COMPLETED: "component1",
    PipelineStatus.COMPONENT2_RUNNING: "component2",
    PipelineStatus.COMPONENT2_COMPLETED: "component2",
    PipelineStatus.COMPONENT4_RUNNING: "component4",
    PipelineStatus.COMPLETED: "component4",
    PipelineStatus.FAILED: "pipeline",
    PipelineStatus.RETRY_PENDING: "pipeline",
    PipelineStatus.CANCELLED: "pipeline",
}

STATUS_MESSAGES = {
    PipelineStatus.INITIALIZING: "Pipeline request initialized",
    PipelineStatus.CREATED: "Pipeline queued for the worker",
    PipelineStatus.COMPONENT1_RUNNING: "Component 1 hybrid recommendation started",
    PipelineStatus.COMPONENT1_COMPLETED: "Component 1 produced the Top-20",
    PipelineStatus.COMPONENT2_RUNNING: "Component 2 availability filtering started",
    PipelineStatus.COMPONENT2_COMPLETED: "Component 2 filtering completed",
    PipelineStatus.COMPONENT4_RUNNING: "Component 4 trust ranking started",
    PipelineStatus.COMPLETED: "Component 4 completed and the pipeline returned the Top-5",
    PipelineStatus.FAILED: "Pipeline execution failed",
    PipelineStatus.RETRY_PENDING: "Pipeline retry requested",
    PipelineStatus.CANCELLED: "Pipeline execution cancelled",
}


def pipeline_execution_event(
    status: PipelineStatus,
    timestamp: Any,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a compact, customer-safe persisted audit event for one transition."""

    values = updates or {}
    details: dict[str, Any] = {}
    component1 = values.get("component1")
    component2 = values.get("component2")
    component4 = values.get("component4")
    error = values.get("error")
    if isinstance(component1, dict):
        details = {
            "engine": component1.get("engine"),
            "component_version": component1.get("component_version"),
            "model_version": component1.get("model_version"),
            "input_provider_count": component1.get("candidate_pool_count")
            or component1.get("artifact_provider_count"),
            "artifact_provider_count": component1.get("artifact_provider_count"),
            "verified_firebase_provider_count": component1.get(
                "verified_firebase_provider_count"
            ),
            "additional_verified_provider_count": component1.get(
                "additional_verified_provider_count"
            ),
            "candidate_source": component1.get("candidate_source"),
            "output_provider_count": len(component1.get("providers", [])),
            "processing_time_ms": component1.get("processing_time_ms"),
        }
    elif isinstance(component2, dict):
        evaluated = component2.get("all_evaluated_providers", [])
        provider_ids = component2.get("output_results", {}).get("provider_ids", [])
        details = {
            "engine": component2.get("engine"),
            "component_version": component2.get("component_version"),
            "model_version": component2.get("model_version"),
            "input_provider_count": len(evaluated),
            "output_provider_count": len(provider_ids),
            "rejected_provider_count": max(0, len(evaluated) - len(provider_ids)),
            "weather_risk": component2.get("output_results", {}).get("weather_risk"),
            "processing_time_ms": component2.get("processing_time_ms"),
        }
    elif isinstance(component4, dict):
        details = {
            "engine": component4.get("engine"),
            "component_version": component4.get("component_version"),
            "model_versions": component4.get("versions"),
            "input_provider_count": component4.get("input_count"),
            "output_provider_count": component4.get("output_count"),
            "source": component4.get("handoff", {}).get("source"),
            "processing_time_ms": component4.get("pipeline_processing_time_ms")
            or component4.get("processing_time_ms"),
        }
    elif isinstance(error, dict):
        details = {
            "error_code": error.get("code"),
            "retryable": error.get("retryable"),
        }
    return {
        "stage": STATUS_STAGE[status],
        "status": status.value,
        "message": STATUS_MESSAGES[status],
        "timestamp": timestamp,
        "details": {key: value for key, value in details.items() if value is not None},
    }


class PipelineRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["pipeline_runs"]
        self.workers = database["pipeline_workers"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("run_id", ASCENDING)], unique=True)
        await self.collection.create_index(
            [("user_id", ASCENDING), ("idempotency_key", ASCENDING)], unique=True
        )
        await self.collection.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        await self.collection.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
        await self.collection.create_index([("lease_expires_at", ASCENDING)], sparse=True)
        await self.workers.create_index([("worker_id", ASCENDING)], unique=True)

    async def create_or_get(self, document: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        try:
            await self.collection.insert_one(document)
            return document, True
        except DuplicateKeyError:
            existing = await self.collection.find_one(
                {
                    "user_id": document["user_id"],
                    "idempotency_key": document["idempotency_key"],
                }
            )
            if existing is None:
                raise
            return existing, False

    async def mark_created(self, run_id: str) -> dict[str, Any]:
        now = utc_now()
        document = await self.collection.find_one_and_update(
            {"run_id": run_id, "status": PipelineStatus.INITIALIZING.value},
            {
                "$set": {"status": PipelineStatus.CREATED.value, "updated_at": now},
                "$push": {
                    "execution_log": pipeline_execution_event(
                        PipelineStatus.CREATED, now
                    )
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise RuntimeError("Pipeline run could not be initialized")
        return document

    async def find_by_id(self, run_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"run_id": run_id})

    async def list_for_user(
        self, user_id: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        return await self.collection.find({"user_id": user_id}).sort(
            "created_at", DESCENDING
        ).skip(offset).to_list(length=limit)

    async def list_all(
        self,
        limit: int,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return await self.collection.find(filters or {}).sort(
            "created_at", DESCENDING
        ).skip(offset).to_list(length=limit)

    async def claim_next(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now = utc_now()
        recoverable = [
            PipelineStatus.COMPONENT1_RUNNING.value,
            PipelineStatus.COMPONENT1_COMPLETED.value,
            PipelineStatus.COMPONENT2_RUNNING.value,
            PipelineStatus.COMPONENT2_COMPLETED.value,
            PipelineStatus.COMPONENT4_RUNNING.value,
        ]
        return await self.collection.find_one_and_update(
            {
                "$or": [
                    {
                        "status": {
                            "$in": [
                                PipelineStatus.CREATED.value,
                                PipelineStatus.RETRY_PENDING.value,
                            ]
                        }
                    },
                    {
                        "status": {"$in": recoverable},
                        "lease_expires_at": {"$lt": now},
                    },
                ]
            },
            {
                "$set": {
                    "worker_id": worker_id,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                },
                "$inc": {"attempt_count": 1},
            },
            sort=[("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )

    async def transition(
        self,
        run_id: str,
        worker_id: str,
        status: PipelineStatus,
        updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        values = {"status": status.value, "updated_at": now, **(updates or {})}
        stage_timestamp_paths = {
            PipelineStatus.COMPONENT1_RUNNING: "stage_timestamps.component1.started_at",
            PipelineStatus.COMPONENT1_COMPLETED: "stage_timestamps.component1.completed_at",
            PipelineStatus.COMPONENT2_RUNNING: "stage_timestamps.component2.started_at",
            PipelineStatus.COMPONENT2_COMPLETED: "stage_timestamps.component2.completed_at",
            PipelineStatus.COMPONENT4_RUNNING: "stage_timestamps.component4.started_at",
            PipelineStatus.COMPLETED: "stage_timestamps.component4.completed_at",
        }
        if timestamp_path := stage_timestamp_paths.get(status):
            values[timestamp_path] = now
        if status == PipelineStatus.COMPLETED:
            values["completed_at"] = now
        document = await self.collection.find_one_and_update(
            {"run_id": run_id, "worker_id": worker_id},
            {
                "$set": values,
                "$push": {
                    "execution_log": pipeline_execution_event(status, now, updates)
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise RuntimeError("Pipeline lease was lost")
        return document

    async def heartbeat(self, run_id: str, worker_id: str, lease_seconds: int) -> bool:
        now = utc_now()
        result = await self.collection.update_one(
            {"run_id": run_id, "worker_id": worker_id},
            {
                "$set": {
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "worker_heartbeat_at": now,
                }
            },
        )
        return result.matched_count == 1

    async def worker_heartbeat(
        self, worker_id: str, *, active_run_id: str | None = None
    ) -> None:
        await self.workers.update_one(
            {"worker_id": worker_id},
            {
                "$set": {
                    "worker_id": worker_id,
                    "active_run_id": active_run_id,
                    "heartbeat_at": utc_now(),
                }
            },
            upsert=True,
        )

    async def get_worker(self, worker_id: str) -> dict[str, Any] | None:
        return await self.workers.find_one({"worker_id": worker_id})

    async def fail(
        self,
        run_id: str,
        worker_id: str,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        await self.transition(
            run_id,
            worker_id,
            PipelineStatus.FAILED,
            {
                "error": {"code": code, "message": message, "retryable": retryable},
                "lease_expires_at": None,
            },
        )

    async def retry(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        now = utc_now()
        return await self.collection.find_one_and_update(
            {
                "run_id": run_id,
                "user_id": user_id,
                "status": PipelineStatus.FAILED.value,
                "error.retryable": True,
            },
            {
                "$set": {
                    "status": PipelineStatus.RETRY_PENDING.value,
                    "error": None,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                },
                "$push": {
                    "execution_log": pipeline_execution_event(
                        PipelineStatus.RETRY_PENDING, now
                    )
                },
            },
            return_document=ReturnDocument.AFTER,
        )

    async def set_selection(
        self,
        run_id: str,
        user_id: str,
        provider_id: str,
        interaction_id: str,
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {
                "run_id": run_id,
                "user_id": user_id,
                "status": PipelineStatus.COMPLETED.value,
                "selected_provider_id": None,
                "component4.providers.provider_id": provider_id,
            },
            {
                "$set": {
                    "selected_provider_id": provider_id,
                    "booking_interaction_id": interaction_id,
                    "selected_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def create_selection_with_interactions(
        self,
        run_id: str,
        user_id: str,
        provider_id: str,
        interaction_id: str,
        interaction_documents: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Commit the one-time selection and its two interaction events together."""

        client = self.collection.database.client
        async with client.start_session() as session:
            async with session.start_transaction():
                document = await self.collection.find_one_and_update(
                    {
                        "run_id": run_id,
                        "user_id": user_id,
                        "status": PipelineStatus.COMPLETED.value,
                        "selected_provider_id": None,
                        "component4.providers.provider_id": provider_id,
                    },
                    {
                        "$set": {
                            "selected_provider_id": provider_id,
                            "booking_interaction_id": interaction_id,
                            "selected_at": utc_now(),
                            "updated_at": utc_now(),
                        }
                    },
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )
                if document is None:
                    return None
                await self.collection.database["interactions"].insert_many(
                    interaction_documents,
                    ordered=True,
                    session=session,
                )
                return document

    async def rollback_selection(self, run_id: str, interaction_id: str) -> None:
        await self.collection.update_one(
            {"run_id": run_id, "booking_interaction_id": interaction_id},
            {
                "$set": {
                    "selected_provider_id": None,
                    "booking_interaction_id": None,
                    "selected_at": None,
                    "updated_at": utc_now(),
                }
            },
        )
