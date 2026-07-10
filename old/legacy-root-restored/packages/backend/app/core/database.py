from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


class MongoConnection:
    client: AsyncIOMotorClient | None = None

    @classmethod
    async def connect(cls) -> None:
        cls.client = AsyncIOMotorClient(settings.mongodb_uri)

    @classmethod
    async def disconnect(cls) -> None:
        if cls.client is not None:
            cls.client.close()
            cls.client = None

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        if cls.client is None:
            raise RuntimeError("Mongo client is not initialized")
        return cls.client[settings.mongodb_database]


def get_database() -> AsyncIOMotorDatabase:
    return MongoConnection.get_db()
