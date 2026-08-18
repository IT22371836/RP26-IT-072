from __future__ import annotations

from app.core.config import Settings, get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient


class FirebaseDatabase:
    """Application database lifecycle backed exclusively by Firebase RTDB."""

    _client: FirebaseRtdbClient | None = None

    @classmethod
    def connect(cls, settings: Settings | None = None) -> FirebaseRtdbClient:
        cls._client = FirebaseRtdbClient(settings or get_settings())
        return cls._client

    @classmethod
    def disconnect(cls) -> None:
        cls._client = None

    @classmethod
    def get_database(cls) -> FirebaseRtdbClient:
        if cls._client is None:
            cls.connect()
        assert cls._client is not None
        return cls._client

    @classmethod
    async def ping(cls) -> bool:
        try:
            return await cls.get_database().ping()
        except Exception:
            return False


def get_database() -> FirebaseRtdbClient:
    return FirebaseDatabase.get_database()
