import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.pipeline import select_pipeline_provider
from app.pipeline.schemas import PipelineSelectionRequest
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole


def test_booking_rolls_back_firebase_history_when_pipeline_persistence_fails() -> None:
    class FailingRepository:
        async def find_by_id(self, _run_id):
            return {
                "run_id": "PIPE1",
                "request_id": "R1",
                "user_id": "U1",
                "status": "completed",
                "component4": {
                    "providers": [
                        {
                            "provider_id": "P00001",
                            "provider_name": "Provider",
                            "category": "Tile",
                        }
                    ]
                },
            }

        async def create_selection_with_interactions(self, *_args):
            raise RuntimeError("Firebase pipeline transaction failed")

    class Users:
        async def find_by_id(self, _user_id):
            return {"legacy": {"firebase_uid": "firebase-customer"}}

    class Firebase:
        def __init__(self) -> None:
            self.deleted = []

        async def create_customer_booking(self, *_args):
            return True

        async def delete_customer_booking_if_matching(self, *args):
            self.deleted.append(args)

    firebase = Firebase()
    current_user = UserPublic(
        user_id="U1",
        email="customer@example.com",
        full_name="Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        created_at=datetime.now(UTC),
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            select_pipeline_provider(
                "PIPE1",
                PipelineSelectionRequest(provider_id="P00001"),
                current_user,
                FailingRepository(),
                Users(),
                firebase,
            )
        )

    assert raised.value.status_code == 503
    assert raised.value.detail == "Booking persistence is temporarily unavailable"
    assert len(firebase.deleted) == 1
    assert firebase.deleted[0][0] == "firebase-customer"
    assert firebase.deleted[0][2] == "PIPE1"
