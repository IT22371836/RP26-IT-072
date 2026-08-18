from __future__ import annotations

import asyncio
from collections.abc import Callable
from copy import deepcopy
from datetime import date, datetime
from typing import Any

from app.integrations.firebase_component2 import FirebaseRtdbClient


def json_safe(value: Any) -> Any:
    """Convert application values into RTDB-compatible JSON values."""

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
            if key != "_id" and item is not None
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def nested_get(document: dict[str, Any], path: str, default: Any = None) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def nested_set(document: dict[str, Any], path: str, value: Any) -> None:
    target = document
    parts = path.split(".")
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = json_safe(value)


def sorted_records(
    value: Any,
    *,
    field: str,
    reverse: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    records = [item for item in (value or {}).values() if isinstance(item, dict)]
    records.sort(key=lambda item: str(nested_get(item, field, "")), reverse=reverse)
    return records if limit is None else records[:limit]


class FirebaseStore:
    """Small asynchronous RTDB primitive layer for repository implementations."""

    def __init__(self, client: FirebaseRtdbClient) -> None:
        self.client = client

    async def get(self, path: str) -> Any:
        return await asyncio.to_thread(self.client._reference(path).get)

    async def shallow(self, path: str) -> dict[str, Any]:
        value = await asyncio.to_thread(self.client._reference(path).get, shallow=True)
        return value if isinstance(value, dict) else {}

    async def set(self, path: str, value: Any) -> None:
        await asyncio.to_thread(self.client._reference(path).set, json_safe(value))

    async def update(self, path: str, values: dict[str, Any]) -> None:
        await asyncio.to_thread(self.client._reference(path).update, json_safe(values))

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self.client._reference(path).delete)

    async def transaction(
        self,
        path: str,
        callback: Callable[[Any], Any],
    ) -> Any:
        def run(current: Any) -> Any:
            return json_safe(callback(deepcopy(current)))

        return await asyncio.to_thread(self.client._reference(path).transaction, run)

    async def multi_update(self, updates: dict[str, Any]) -> None:
        await self.update("/", updates)
