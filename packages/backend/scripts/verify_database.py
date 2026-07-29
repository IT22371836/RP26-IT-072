import asyncio

from app.core.config import get_settings
from app.core.database import MongoDatabase
from app.repositories.indexes import ensure_application_indexes


async def main() -> None:
    await MongoDatabase.connect(get_settings())
    try:
        await ensure_application_indexes(MongoDatabase.get_database())
        print("MongoDB connection and application indexes are ready.")
    finally:
        await MongoDatabase.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
