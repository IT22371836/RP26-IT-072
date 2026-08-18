from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.pipeline.schemas import PipelineStatus
from app.repositories.interactions import InteractionRepository
from app.repositories.pipeline import PipelineRepository
from app.repositories.users import UserRepository


class MemoryReference:
    def __init__(self, root: dict[str, Any], path: str) -> None:
        self.root = root
        self.parts = [part for part in path.strip("/").split("/") if part]

    def _parent(self, create: bool = False) -> tuple[dict[str, Any], str | None]:
        current = self.root
        for part in self.parts[:-1]:
            child = current.get(part)
            if not isinstance(child, dict):
                if not create:
                    return {}, self.parts[-1] if self.parts else None
                child = {}
                current[part] = child
            current = child
        return current, self.parts[-1] if self.parts else None

    def get(self, shallow: bool = False) -> Any:
        current: Any = self.root
        for part in self.parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        if shallow and isinstance(current, dict):
            return {key: True for key in current}
        return deepcopy(current)

    def set(self, value: Any) -> None:
        if not self.parts:
            self.root.clear()
            self.root.update(deepcopy(value))
            return
        parent, key = self._parent(create=True)
        assert key is not None
        parent[key] = deepcopy(value)

    def update(self, values: dict[str, Any]) -> None:
        for path, value in values.items():
            target = MemoryReference(self.root, "/".join([*self.parts, path]))
            if value is None:
                target.delete()
            else:
                target.set(value)

    def delete(self) -> None:
        parent, key = self._parent()
        if key is not None:
            parent.pop(key, None)

    def transaction(self, callback):
        updated = callback(self.get())
        if updated is None:
            self.delete()
        else:
            self.set(updated)
        return deepcopy(updated)


class MemoryFirebase:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    def _reference(self, path: str) -> MemoryReference:
        return MemoryReference(self.data, path)


def test_firebase_identity_and_pipeline_lifecycle() -> None:
    async def run() -> None:
        firebase = MemoryFirebase()
        users = UserRepository(firebase)
        pipelines = PipelineRepository(firebase)
        interactions = InteractionRepository(firebase)
        now = datetime.now(UTC)

        user = await users.ensure_firebase_identity(
            firebase_uid="firebase-customer-1",
            email="customer@example.com",
            full_name="Firebase Customer",
            role="customer",
            now=now,
            user_id="U1",
        )
        assert user["legacy"]["firebase_uid"] == "firebase-customer-1"
        assert (await users.find_by_firebase_uid("firebase-customer-1"))["user_id"] == "U1"

        run_document = {
            "run_id": "PIPE1",
            "request_id": "R1",
            "user_id": "U1",
            "idempotency_key": "request-key-1",
            "status": PipelineStatus.INITIALIZING.value,
            "request": {},
            "execution_log": [],
            "created_at": now,
            "updated_at": now,
            "attempt_count": 0,
        }
        stored, created = await pipelines.create_or_get(run_document)
        assert created is True
        assert stored["run_id"] == "PIPE1"
        _, duplicate_created = await pipelines.create_or_get(run_document)
        assert duplicate_created is False

        await pipelines.mark_created("PIPE1")
        claimed = await pipelines.claim_next("worker-1", 90)
        assert claimed is not None
        assert claimed["attempt_count"] == 1
        transitioned = await pipelines.transition(
            "PIPE1", "worker-1", PipelineStatus.COMPONENT1_RUNNING
        )
        assert transitioned["status"] == PipelineStatus.COMPONENT1_RUNNING.value
        filtered = await pipelines.list_all(
            10,
            filters={"created_at": {"$gte": now, "$lte": now}},
        )
        assert [item["run_id"] for item in filtered] == ["PIPE1"]
        await pipelines.fail(
            "PIPE1",
            "worker-1",
            code="firebase_failure",
            message="temporary",
            retryable=True,
        )
        retried = await pipelines.retry("PIPE1", "U1")
        assert retried is not None
        assert retried["status"] == PipelineStatus.RETRY_PENDING.value
        assert retried["retry_history"][0]["requested_by"] == "U1"

        await interactions.create(
            {
                "interaction_id": "I1",
                "request_id": "R1",
                "user_id": "U1",
                "provider_id": "P1",
                "interaction_type": "click",
                "timestamp": now,
            }
        )
        assert await interactions.click_preference_provider_ids("U1") == ["P1"]

    asyncio.run(run())
