from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from app.pipeline.schemas import PipelineStatus
from app.repositories.firebase_store import FirebaseStore, nested_get, nested_set, sorted_records
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
    status: PipelineStatus, timestamp: Any, updates: dict[str, Any] | None = None
) -> dict[str, Any]:
    values = updates or {}
    details: dict[str, Any] = {}
    component1, component2, component4, error = (
        values.get("component1"),
        values.get("component2"),
        values.get("component4"),
        values.get("error"),
    )
    if isinstance(component1, dict):
        details = {
            "engine": component1.get("engine"),
            "component_version": component1.get("component_version"),
            "model_version": component1.get("model_version"),
            "input_provider_count": component1.get("candidate_pool_count")
            or component1.get("artifact_provider_count"),
            "artifact_provider_count": component1.get("artifact_provider_count"),
            "verified_firebase_provider_count": component1.get("verified_firebase_provider_count"),
            "additional_verified_provider_count": component1.get(
                "additional_verified_provider_count"
            ),
            "eligible_research_provider_count": component1.get(
                "eligible_research_provider_count"
            ),
            "eligible_website_provider_count": component1.get(
                "eligible_website_provider_count"
            ),
            "candidate_source": component1.get("candidate_source"),
            "output_provider_count": len(component1.get("providers", [])),
            "processing_time_ms": component1.get("processing_time_ms"),
        }
    elif isinstance(component2, dict):
        evaluated = component2.get("all_evaluated_providers", [])
        ids = component2.get("output_results", {}).get("provider_ids", [])
        details = {
            "engine": component2.get("engine"),
            "component_version": component2.get("component_version"),
            "model_version": component2.get("model_version"),
            "input_provider_count": len(evaluated),
            "output_provider_count": len(ids),
            "rejected_provider_count": max(0, len(evaluated) - len(ids)),
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
            "outside_cutoff_provider_count": max(
                0,
                int(component4.get("input_count") or 0) - int(component4.get("output_count") or 0),
            ),
            "source": component4.get("handoff", {}).get("source"),
            "processing_time_ms": component4.get("pipeline_processing_time_ms")
            or component4.get("processing_time_ms"),
        }
    elif isinstance(error, dict):
        details = {"error_code": error.get("code"), "retryable": error.get("retryable")}
    return {
        "stage": STATUS_STAGE[status],
        "status": status.value,
        "message": STATUS_MESSAGES[status],
        "timestamp": timestamp,
        "details": {key: value for key, value in details.items() if value is not None},
    }


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=UTC)


def _matches_filters(document: dict[str, Any], filters: dict[str, Any]) -> bool:
    for path, expected in filters.items():
        actual = nested_get(document, path)
        if isinstance(expected, dict) and any(
            operator in expected for operator in ("$gte", "$lte")
        ):
            actual_time = _parse_time(actual)
            if "$gte" in expected and actual_time < _parse_time(expected["$gte"]):
                return False
            if "$lte" in expected and actual_time > _parse_time(expected["$lte"]):
                return False
        elif actual != expected:
            return False
    return True


class PipelineRepository:
    PATH = "pipeline/runs"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def create_or_get(self, document: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        digest = hashlib.sha256(
            f"{document['user_id']}\0{document['idempotency_key']}".encode()
        ).hexdigest()
        index_path = f"pipeline/idempotency/{digest}"
        created = False

        def claim(current: Any) -> Any:
            nonlocal created
            if current is None:
                created = True
                return document["run_id"]
            return current

        run_id = await self.store.transaction(index_path, claim)
        if created:
            await self.store.set(f"{self.PATH}/{document['run_id']}", document)
            return document, True
        existing = await self.find_by_id(str(run_id))
        if existing is None:
            raise RuntimeError("Pipeline idempotency index references a missing run")
        return existing, False

    async def mark_created(self, run_id: str) -> dict[str, Any]:
        now = utc_now()
        changed = False

        def apply(current: Any) -> Any:
            nonlocal changed
            if (
                isinstance(current, dict)
                and current.get("status") == PipelineStatus.INITIALIZING.value
            ):
                current.update({"status": PipelineStatus.CREATED.value, "updated_at": now})
                current.setdefault("execution_log", []).append(
                    pipeline_execution_event(PipelineStatus.CREATED, now)
                )
                changed = True
            return current

        document = await self.store.transaction(f"{self.PATH}/{run_id}", apply)
        if not changed or not isinstance(document, dict):
            raise RuntimeError("Pipeline run could not be initialized")
        return document

    async def delete_initializing(self, run_id: str) -> None:
        document = await self.find_by_id(run_id)
        if (
            not isinstance(document, dict)
            or document.get("status") != PipelineStatus.INITIALIZING.value
        ):
            return
        digest = hashlib.sha256(
            f"{document['user_id']}\0{document['idempotency_key']}".encode()
        ).hexdigest()
        await self.store.delete(f"{self.PATH}/{run_id}")
        indexed_run = await self.store.get(f"pipeline/idempotency/{digest}")
        if indexed_run == run_id:
            await self.store.delete(f"pipeline/idempotency/{digest}")

    async def find_by_id(self, run_id: str) -> dict[str, Any] | None:
        value = await self.store.get(f"{self.PATH}/{run_id}")
        return value if isinstance(value, dict) else None

    async def list_for_user(
        self, user_id: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        values = await self.store.get(self.PATH) or {}
        records = sorted_records(
            {
                k: v
                for k, v in values.items()
                if isinstance(v, dict) and v.get("user_id") == user_id
            },
            field="created_at",
        )
        return records[offset : offset + limit]

    async def list_all(
        self, limit: int, offset: int = 0, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        values = await self.store.get(self.PATH) or {}
        records = [v for v in values.values() if isinstance(v, dict)]
        if filters:
            records = [item for item in records if _matches_filters(item, filters)]
        records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return records[offset : offset + limit]

    async def claim_next(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now = utc_now()
        selected: dict[str, Any] | None = None
        recoverable = {
            PipelineStatus.COMPONENT1_RUNNING.value,
            PipelineStatus.COMPONENT1_COMPLETED.value,
            PipelineStatus.COMPONENT2_RUNNING.value,
            PipelineStatus.COMPONENT2_COMPLETED.value,
            PipelineStatus.COMPONENT4_RUNNING.value,
        }

        def claim(runs: Any) -> Any:
            nonlocal selected
            if not isinstance(runs, dict):
                return runs
            candidates = []
            for key, item in runs.items():
                if not isinstance(item, dict):
                    continue
                status = item.get("status")
                queued = status in {
                    PipelineStatus.CREATED.value,
                    PipelineStatus.RETRY_PENDING.value,
                }
                expired = status in recoverable and _parse_time(item.get("lease_expires_at")) < now
                if queued or expired:
                    candidates.append((str(item.get("created_at") or ""), key, item))
            if not candidates:
                return runs
            _, key, item = min(candidates)
            item.update(
                {
                    "worker_id": worker_id,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                    "attempt_count": int(item.get("attempt_count") or 0) + 1,
                }
            )
            selected = item
            runs[key] = item
            return runs

        await self.store.transaction(self.PATH, claim)
        return selected

    async def transition(
        self,
        run_id: str,
        worker_id: str,
        status: PipelineStatus,
        updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        changed = False
        stage_paths = {
            PipelineStatus.COMPONENT1_RUNNING: "stage_timestamps.component1.started_at",
            PipelineStatus.COMPONENT1_COMPLETED: "stage_timestamps.component1.completed_at",
            PipelineStatus.COMPONENT2_RUNNING: "stage_timestamps.component2.started_at",
            PipelineStatus.COMPONENT2_COMPLETED: "stage_timestamps.component2.completed_at",
            PipelineStatus.COMPONENT4_RUNNING: "stage_timestamps.component4.started_at",
            PipelineStatus.COMPLETED: "stage_timestamps.component4.completed_at",
        }

        def apply(current: Any) -> Any:
            nonlocal changed
            if not isinstance(current, dict) or current.get("worker_id") != worker_id:
                return current
            current.update({"status": status.value, "updated_at": now})
            for key, value in (updates or {}).items():
                nested_set(current, key, value)
            if status in stage_paths:
                nested_set(current, stage_paths[status], now)
            if status == PipelineStatus.COMPLETED:
                current["completed_at"] = now
            current.setdefault("execution_log", []).append(
                pipeline_execution_event(status, now, updates)
            )
            changed = True
            return current

        document = await self.store.transaction(f"{self.PATH}/{run_id}", apply)
        if not changed or not isinstance(document, dict):
            raise RuntimeError("Pipeline lease was lost")
        return document

    async def heartbeat(self, run_id: str, worker_id: str, lease_seconds: int) -> bool:
        now = utc_now()
        matched = False

        def apply(current: Any) -> Any:
            nonlocal matched
            if isinstance(current, dict) and current.get("worker_id") == worker_id:
                current.update(
                    {
                        "lease_expires_at": now + timedelta(seconds=lease_seconds),
                        "worker_heartbeat_at": now,
                    }
                )
                matched = True
            return current

        await self.store.transaction(f"{self.PATH}/{run_id}", apply)
        return matched

    async def worker_heartbeat(self, worker_id: str, *, active_run_id: str | None = None) -> None:
        await self.store.set(
            f"pipeline/workers/{worker_id}",
            {"worker_id": worker_id, "active_run_id": active_run_id, "heartbeat_at": utc_now()},
        )

    async def get_worker(self, worker_id: str) -> dict[str, Any] | None:
        value = await self.store.get(f"pipeline/workers/{worker_id}")
        return value if isinstance(value, dict) else None

    async def fail(
        self, run_id: str, worker_id: str, *, code: str, message: str, retryable: bool
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
        changed = False

        def apply(current: Any) -> Any:
            nonlocal changed
            if (
                isinstance(current, dict)
                and current.get("user_id") == user_id
                and current.get("status") == PipelineStatus.FAILED.value
                and current.get("error", {}).get("retryable") is True
            ):
                current.update(
                    {
                        "status": PipelineStatus.RETRY_PENDING.value,
                        "error": None,
                        "worker_id": None,
                        "lease_expires_at": None,
                        "updated_at": now,
                    }
                )
                current.setdefault("retry_history", []).append(
                    {"requested_at": now, "requested_by": user_id}
                )
                current.setdefault("execution_log", []).append(
                    pipeline_execution_event(PipelineStatus.RETRY_PENDING, now)
                )
                changed = True
            return current

        result = await self.store.transaction(f"{self.PATH}/{run_id}", apply)
        return result if changed and isinstance(result, dict) else None

    async def set_selection(
        self, run_id: str, user_id: str, provider_id: str, interaction_id: str
    ) -> dict[str, Any] | None:
        changed = False

        def apply(current: Any) -> Any:
            nonlocal changed
            valid_ids = (
                [
                    item.get("provider_id")
                    for item in current.get("component4", {}).get("providers", [])
                ]
                if isinstance(current, dict)
                else []
            )
            if (
                isinstance(current, dict)
                and current.get("user_id") == user_id
                and current.get("status") == PipelineStatus.COMPLETED.value
                and not current.get("selected_provider_id")
                and provider_id in valid_ids
            ):
                now = utc_now()
                current.update(
                    {
                        "selected_provider_id": provider_id,
                        "booking_interaction_id": interaction_id,
                        "selected_at": now,
                        "updated_at": now,
                    }
                )
                changed = True
            return current

        result = await self.store.transaction(f"{self.PATH}/{run_id}", apply)
        return result if changed and isinstance(result, dict) else None

    async def create_selection_with_interactions(
        self,
        run_id: str,
        user_id: str,
        provider_id: str,
        interaction_id: str,
        interaction_documents: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        result = await self.set_selection(run_id, user_id, provider_id, interaction_id)
        if result is None:
            return None
        try:
            await self.store.multi_update(
                {
                    f"component1/interactions/{item['interaction_id']}": item
                    for item in interaction_documents
                }
            )
        except Exception:
            await self.rollback_selection(run_id, interaction_id)
            raise
        return result

    async def rollback_selection(self, run_id: str, interaction_id: str) -> None:
        def apply(current: Any) -> Any:
            if (
                isinstance(current, dict)
                and current.get("booking_interaction_id") == interaction_id
            ):
                current.update(
                    {
                        "selected_provider_id": None,
                        "booking_interaction_id": None,
                        "selected_at": None,
                        "updated_at": utc_now(),
                    }
                )
            return current

        await self.store.transaction(f"{self.PATH}/{run_id}", apply)
