import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.pipeline import select_pipeline_provider
from app.pipeline.schemas import PipelineSelectionRequest
from app.repositories.pipeline import PipelineRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole


class AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class Session(AsyncContext):
    def __init__(self) -> None:
        self.transaction_started = False

    async def start_transaction(self) -> AsyncContext:
        self.transaction_started = True
        return AsyncContext()


class Client:
    def __init__(self) -> None:
        self.session = Session()

    def start_session(self) -> Session:
        return self.session


class PipelineCollection:
    def __init__(self, database) -> None:
        self.database = database

    async def find_one_and_update(self, *_args, session=None, **_kwargs):
        assert session is self.database.client.session
        return {"run_id": "PIPE1", "selected_provider_id": "P00001"}


class InteractionCollection:
    def __init__(self) -> None:
        self.documents = []

    async def insert_many(self, documents, *, ordered, session):
        assert ordered is True
        assert session is not None
        self.documents.extend(documents)


class Database:
    def __init__(self) -> None:
        self.client = Client()
        self.interactions = InteractionCollection()
        self.pipeline = PipelineCollection(self)

    def __getitem__(self, name):
        return {
            "pipeline_runs": self.pipeline,
            "pipeline_workers": object(),
            "interactions": self.interactions,
        }[name]


def test_booking_transaction_awaits_async_pymongo_context() -> None:
    database = Database()
    repository = PipelineRepository(database)
    interactions = [
        {"interaction_id": "I1", "interaction_type": "selected"},
        {"interaction_id": "I2", "interaction_type": "booking_requested"},
    ]

    result = asyncio.run(
        repository.create_selection_with_interactions(
            "PIPE1", "U1", "P00001", "I2", interactions
        )
    )

    assert database.client.session.transaction_started is True
    assert result == {"run_id": "PIPE1", "selected_provider_id": "P00001"}
    assert database.interactions.documents == interactions


def test_booking_rolls_back_firebase_when_mongo_persistence_fails() -> None:
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
            raise RuntimeError("Mongo transaction failed")

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
