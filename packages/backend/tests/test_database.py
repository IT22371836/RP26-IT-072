import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.core.database import MongoDatabase


def test_ping_returns_false_when_disconnected() -> None:
    async def run_test() -> None:
        MongoDatabase._client = None
        assert await MongoDatabase.ping() is False

    asyncio.run(run_test())


def test_ping_returns_true_for_connected_client() -> None:
    async def run_test() -> None:
        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1})
        MongoDatabase._client = client

        try:
            assert await MongoDatabase.ping() is True
            client.admin.command.assert_awaited_once_with("ping")
        finally:
            MongoDatabase._client = None

    asyncio.run(run_test())
