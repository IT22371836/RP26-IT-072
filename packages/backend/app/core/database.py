from typing import Any

from pymongo import AsyncMongoClient
from pymongo.server_api import ServerApi

from app.core.config import Settings


class MongoDatabase:
    """Own the single MongoDB client used by the FastAPI event loop."""

    _client: AsyncMongoClient | None = None
    _database: Any | None = None

    @classmethod
    async def connect(cls, settings: Settings) -> None:
        if cls._client is not None:
            return

        client = AsyncMongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
            server_api=ServerApi("1"),
            appname="weda.lk-api",
        )

        try:
            await client.admin.command("ping")
        except Exception:
            await client.close()
            raise

        cls._client = client
        cls._database = client[settings.mongodb_database]

    @classmethod
    async def disconnect(cls) -> None:
        if cls._client is not None:
            await cls._client.close()
        cls._client = None
        cls._database = None

    @classmethod
    def get_database(cls) -> Any:
        if cls._database is None:
            raise RuntimeError("MongoDB is not connected")
        return cls._database

    @classmethod
    async def ping(cls) -> bool:
        if cls._client is None:
            return False
        try:
            await cls._client.admin.command("ping")
        except Exception:
            return False
        return True


def get_database() -> Any:
    """FastAPI dependency that returns the connected application database."""

    return MongoDatabase.get_database()
