from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase


class ServiceRequestRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["service_requests"]
#Inserts a new service request into the database
    async def create(self, data: dict) -> dict:
        data["created_at"] = datetime.now(UTC)
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return data
    #
    async def find_all(self) -> list[dict]:
        cursor = self.collection.find({})
        return await cursor.to_list(length=None)
# Retrieves a service request by its ID
    async def find_by_id(self, request_id: str) -> dict | None:
        from bson import ObjectId
        return await self.collection.find_one({"_id": ObjectId(request_id)})
