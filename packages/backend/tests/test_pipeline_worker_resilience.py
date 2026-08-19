from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.pipeline import worker as worker_module


def test_worker_reconnects_after_transient_database_failure(monkeypatch) -> None:
    events: list[str] = []

    class Database:
        @classmethod
        def connect(cls, _settings):
            events.append("connect")
            return object()

        @classmethod
        def disconnect(cls) -> None:
            events.append("disconnect")

    class Worker:
        calls = 0

        def __init__(self, _database, _settings) -> None:
            pass

        async def warmup(self) -> dict[str, int | float]:
            return {
                "eligible_count": 1_010,
                "research_count": 1_000,
                "website_count": 10,
                "processing_time_ms": 1.0,
            }

        async def run_once(self) -> bool:
            Worker.calls += 1
            if Worker.calls == 1:
                raise OSError("temporary DNS failure")
            raise asyncio.CancelledError

    async def indexes(_database) -> None:
        events.append("indexes")

    async def sleep(_seconds: float) -> None:
        events.append("sleep")

    monkeypatch.setattr(worker_module, "get_settings", lambda: SimpleNamespace(
        pipeline_poll_interval_seconds=0.1,
        pipeline_worker_id="test-worker",
    ))
    monkeypatch.setattr(worker_module, "FirebaseDatabase", Database)
    monkeypatch.setattr(worker_module, "PipelineWorker", Worker)
    monkeypatch.setattr(worker_module, "ensure_application_indexes", indexes)
    monkeypatch.setattr(worker_module.asyncio, "sleep", sleep)

    try:
        asyncio.run(worker_module.run_forever())
    except asyncio.CancelledError:
        pass

    assert Worker.calls == 2
    assert events.count("connect") == 2
    assert events.count("indexes") == 2
    assert "sleep" in events
    assert events.count("disconnect") >= 2
