from typing import Any

from app.repositories.firebase_store import FirebaseStore, sorted_records
from app.schemas.interaction import InteractionType


class InteractionRepository:
    PATH = "component1/interactions"

    def __init__(self, database: Any) -> None:
        self.store = FirebaseStore(database)

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.store.set(f"{self.PATH}/{document['interaction_id']}", document)
        return document

    async def create_many(self, documents: list[dict[str, Any]]) -> None:
        if documents:
            await self.store.multi_update(
                {f"{self.PATH}/{item['interaction_id']}": item for item in documents}
            )

    async def _all(self) -> dict[str, dict[str, Any]]:
        value = await self.store.get(self.PATH) or {}
        return {key: item for key, item in value.items() if isinstance(item, dict)}

    async def list_for_user(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        values = await self._all()
        return sorted_records(
            {key: item for key, item in values.items() if item.get("user_id") == user_id},
            field="timestamp",
            limit=limit,
        )

    async def list_for_provider(self, provider_id: str, limit: int = 100) -> list[dict[str, Any]]:
        allowed = {
            InteractionType.BOOKING_REQUESTED.value,
            InteractionType.BOOKING_COMPLETED.value,
            InteractionType.BOOKING_CANCELLED.value,
            InteractionType.RATED.value,
        }
        values = await self._all()
        return sorted_records(
            {
                key: item
                for key, item in values.items()
                if item.get("provider_id") == provider_id
                and item.get("interaction_type") in allowed
            },
            field="timestamp",
            limit=limit,
        )

    async def list_reviews_for_provider(
        self, provider_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        values = await self._all()
        selected = {
            key: {field: item.get(field) for field in ("rating", "review_text", "timestamp")}
            for key, item in values.items()
            if item.get("provider_id") == provider_id
            and item.get("interaction_type") == InteractionType.RATED.value
        }
        return sorted_records(selected, field="timestamp", limit=limit)

    async def find_by_id(self, interaction_id: str) -> dict[str, Any] | None:
        value = await self.store.get(f"{self.PATH}/{interaction_id}")
        return value if isinstance(value, dict) else None

    async def has_event(
        self, user_id: str, request_id: str, provider_id: str, interaction_type: InteractionType
    ) -> bool:
        return any(
            item.get("user_id") == user_id
            and item.get("request_id") == request_id
            and item.get("provider_id") == provider_id
            and item.get("interaction_type") == interaction_type.value
            for item in (await self._all()).values()
        )

    async def count(self) -> int:
        return len(await self.store.shallow(self.PATH))

    async def provider_statistics(self, provider_id: str) -> dict[str, int | float]:
        records = [
            item for item in (await self._all()).values() if item.get("provider_id") == provider_id
        ]
        completed = sum(
            item.get("interaction_type") == InteractionType.BOOKING_COMPLETED.value
            for item in records
        )
        cancelled = sum(
            item.get("interaction_type") == InteractionType.BOOKING_CANCELLED.value
            for item in records
        )
        interaction_count = sum(
            item.get("interaction_type") != InteractionType.IMPRESSION.value for item in records
        )
        ratings = [
            float(item["rating"])
            for item in records
            if item.get("interaction_type") == InteractionType.RATED.value
            and isinstance(item.get("rating"), (int, float))
        ]
        closed = completed + cancelled
        return {
            "rating": sum(ratings) / len(ratings) if ratings else 0.0,
            "review_count": len(ratings),
            "booking_success_rate": completed / closed if closed else 0.0,
            "interaction_count": interaction_count,
        }

    async def preferred_provider_ids(self, user_id: str, limit: int = 500) -> list[str]:
        weights = {
            InteractionType.CLICK.value: 1,
            InteractionType.SELECTED.value: 2,
            InteractionType.BOOKING_REQUESTED.value: 3,
            InteractionType.BOOKING_COMPLETED.value: 4,
            InteractionType.RATED.value: 4,
        }
        records = await self.list_for_user(user_id, limit)
        return [
            str(item["provider_id"])
            for item in records
            if item.get("interaction_type") in weights
            for _ in range(weights[str(item["interaction_type"])])
        ]

    async def click_preference_provider_ids(self, user_id: str, limit: int = 500) -> list[str]:
        return [
            str(item["provider_id"])
            for item in await self.list_for_user(user_id, limit)
            if item.get("interaction_type") == InteractionType.CLICK.value
        ]

    async def find_booking_requested(
        self, user_id: str, request_id: str, provider_id: str
    ) -> dict[str, Any] | None:
        records = [
            item
            for item in (await self._all()).values()
            if item.get("user_id") == user_id
            and item.get("request_id") == request_id
            and item.get("provider_id") == provider_id
            and item.get("interaction_type") == InteractionType.BOOKING_REQUESTED.value
        ]
        records.sort(key=lambda item: str(item.get("timestamp") or ""))
        return records[0] if records else None
