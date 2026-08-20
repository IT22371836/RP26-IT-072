import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.interactions import accept_booking, complete_booking, reject_booking
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole


class InteractionRepositoryStub:
    def __init__(self, source: dict[str, Any]) -> None:
        self.records = [source]

    async def find_by_id(self, interaction_id: str) -> dict[str, Any] | None:
        return next(
            (item for item in self.records if item["interaction_id"] == interaction_id),
            None,
        )

    async def has_event(
        self, user_id: str, request_id: str, provider_id: str, interaction_type: Any
    ) -> bool:
        return any(
            item["user_id"] == user_id
            and item["request_id"] == request_id
            and item["provider_id"] == provider_id
            and item["interaction_type"] == interaction_type.value
            for item in self.records
        )

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        self.records.append(document)
        return document

    async def provider_statistics(self, provider_id: str) -> dict[str, int | float]:
        completed = sum(
            item["interaction_type"] == "booking_completed"
            for item in self.records
            if item["provider_id"] == provider_id
        )
        return {
            "rating": 0.0,
            "review_count": 0,
            "booking_success_rate": 1.0 if completed else 0.0,
            "interaction_count": len(self.records),
        }


class ProviderRepositoryStub:
    def __init__(self, provider_user_id: str, provider_id: str) -> None:
        self.provider_user_id = provider_user_id
        self.provider_id = provider_id
        self.statistics: dict[str, Any] = {}

    async def find_by_user_id(self, user_id: str) -> dict[str, str] | None:
        if user_id != self.provider_user_id:
            return None
        return {"provider_id": self.provider_id}

    async def update_statistics(
        self, provider_id: str, statistics: dict[str, Any]
    ) -> None:
        assert provider_id == self.provider_id
        self.statistics = statistics


class UserRepositoryStub:
    async def find_by_id(self, user_id: str) -> dict[str, Any]:
        return {"user_id": user_id, "legacy": {"firebase_uid": "customer-firebase"}}


class FirebaseBookingStub:
    def __init__(self) -> None:
        self.booking: dict[str, Any] | None = None

    async def create_customer_booking(
        self, firebase_uid: str, booking_id: str, payload: dict[str, Any]
    ) -> bool:
        assert firebase_uid == "customer-firebase"
        if self.booking is None:
            self.booking = dict(payload)
            return True
        return False

    async def transition_customer_booking(
        self,
        firebase_uid: str,
        booking_id: str,
        expected_statuses: set[str],
        updates: dict[str, Any],
    ) -> None:
        assert firebase_uid == "customer-firebase"
        assert self.booking is not None
        assert self.booking["status"] in expected_statuses
        self.booking.update(updates)


def provider_user() -> UserPublic:
    return UserPublic(
        user_id="provider-user",
        email="provider@example.com",
        full_name="Provider Test",
        role=UserRole.PROVIDER,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def booking_source() -> dict[str, Any]:
    return {
        "interaction_id": "BOOKING1",
        "request_id": "REQUEST1",
        "user_id": "customer-user",
        "provider_id": "P00001",
        "provider_name": "Provider Test",
        "category": "Electricians",
        "interaction_type": "booking_requested",
        "rating": None,
        "review_text": None,
        "timestamp": datetime.now(UTC),
    }


def test_provider_accepts_then_completes_booking() -> None:
    async def run() -> None:
        interactions = InteractionRepositoryStub(booking_source())
        providers = ProviderRepositoryStub("provider-user", "P00001")
        users = UserRepositoryStub()
        firebase = FirebaseBookingStub()

        accepted = await accept_booking(
            "BOOKING1", provider_user(), interactions, providers, users, firebase
        )
        assert accepted.interaction_type == "booking_accepted"
        assert accepted.booking_interaction_id == "BOOKING1"
        assert firebase.booking is not None
        assert firebase.booking["status"] == "booking_accepted"

        completed = await complete_booking(
            "BOOKING1", provider_user(), interactions, providers, users, firebase
        )
        assert completed.interaction_type == "booking_completed"
        assert firebase.booking["status"] == "booking_completed"
        assert providers.statistics["booking_success_rate"] == 1.0

    asyncio.run(run())


def test_provider_can_reject_pending_booking_but_cannot_accept_it_twice() -> None:
    async def run() -> None:
        interactions = InteractionRepositoryStub(booking_source())
        providers = ProviderRepositoryStub("provider-user", "P00001")
        users = UserRepositoryStub()
        firebase = FirebaseBookingStub()

        rejected = await reject_booking(
            "BOOKING1", provider_user(), interactions, providers, users, firebase
        )
        assert rejected.interaction_type == "booking_rejected"
        assert firebase.booking is not None
        assert firebase.booking["status"] == "booking_rejected"

        with pytest.raises(HTTPException) as error:
            await accept_booking(
                "BOOKING1", provider_user(), interactions, providers, users, firebase
            )
        assert error.value.status_code == 409

    asyncio.run(run())


def test_booking_must_be_accepted_before_completion() -> None:
    async def run() -> None:
        interactions = InteractionRepositoryStub(booking_source())
        with pytest.raises(HTTPException) as error:
            await complete_booking(
                "BOOKING1",
                provider_user(),
                interactions,
                ProviderRepositoryStub("provider-user", "P00001"),
                UserRepositoryStub(),
                FirebaseBookingStub(),
            )
        assert error.value.status_code == 409
        assert "Accept the booking" in str(error.value.detail)

    asyncio.run(run())
