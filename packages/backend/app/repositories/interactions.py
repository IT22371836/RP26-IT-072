from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.schemas.interaction import InteractionType


class InteractionRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database["interactions"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("interaction_id", ASCENDING)], unique=True)
        await self.collection.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        await self.collection.create_index([("provider_id", ASCENDING), ("timestamp", DESCENDING)])

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.collection.insert_one(document)
        return document

    async def create_many(self, documents: list[dict[str, Any]]) -> None:
        if documents:
            await self.collection.insert_many(documents)

    async def list_for_user(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return (
            await self.collection.find({"user_id": user_id})
            .sort("timestamp", DESCENDING)
            .limit(limit)
            .to_list(length=limit)
        )

    async def list_for_provider(self, provider_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return (
            await self.collection.find(
                {
                    "provider_id": provider_id,
                    "interaction_type": {
                        "$in": [
                            InteractionType.BOOKING_REQUESTED.value,
                            InteractionType.BOOKING_COMPLETED.value,
                            InteractionType.BOOKING_CANCELLED.value,
                            InteractionType.RATED.value,
                        ]
                    },
                }
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
            .to_list(length=limit)
        )

    async def find_by_id(self, interaction_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"interaction_id": interaction_id})

    async def has_event(
        self, user_id: str, request_id: str, provider_id: str, interaction_type: InteractionType
    ) -> bool:
        return (
            await self.collection.find_one(
                {
                    "user_id": user_id,
                    "request_id": request_id,
                    "provider_id": provider_id,
                    "interaction_type": interaction_type.value,
                },
                {"_id": 1},
            )
            is not None
        )

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def preferred_provider_ids(self, user_id: str, limit: int = 500) -> list[str]:
        preference_events = [
            InteractionType.CLICK.value,
            InteractionType.SELECTED.value,
            InteractionType.BOOKING_REQUESTED.value,
            InteractionType.BOOKING_COMPLETED.value,
            InteractionType.RATED.value,
        ]
        records = (
            await self.collection.find(
                {"user_id": user_id, "interaction_type": {"$in": preference_events}},
                {"provider_id": 1, "interaction_type": 1},
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
            .to_list(length=limit)
        )
        weights = {
            InteractionType.CLICK.value: 1,
            InteractionType.SELECTED.value: 2,
            InteractionType.BOOKING_REQUESTED.value: 3,
            InteractionType.BOOKING_COMPLETED.value: 4,
            InteractionType.RATED.value: 4,
        }
        return [
            record["provider_id"]
            for record in records
            for _ in range(weights[record["interaction_type"]])
        ]
