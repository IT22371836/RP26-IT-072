from motor.motor_asyncio import AsyncIOMotorDatabase


class MaintenanceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["maintenance_requests"]

    async def count(self) -> int:
        return await self.collection.count_documents({})
