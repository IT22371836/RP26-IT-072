from motor.motor_asyncio import AsyncIOMotorDatabase


class MaintenanceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["maintenance_requests"]

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("customer_id")
        await self.collection.create_index("provider_id")
        await self.collection.create_index("status")

    async def create_request(self, doc: dict) -> str:
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_customer(self, customer_id: str, limit: int = 20) -> list[dict]:
        cursor = self.collection.find({"customer_id": customer_id}).sort("created_at", -1).limit(limit)
        return [d async for d in cursor]

    async def find_by_provider(self, provider_id: str, limit: int = 20) -> list[dict]:
        cursor = self.collection.find({"provider_id": provider_id}).sort("created_at", -1).limit(limit)
        return [d async for d in cursor]

    async def count_by_status(self, owner_key: str, owner_id: str) -> dict:
        pipeline = [
            {"$match": {owner_key: owner_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        cursor = self.collection.aggregate(pipeline)
        res = {}
        async for doc in cursor:
            res[doc["_id"]] = doc["count"]
        return res
