import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.integrations.firebase_component2 import (
    FirebaseRtdbClient,
    booking_history_preference_ids,
)
from scripts.migrate_booking_history_to_firebase import build_booking_records
from scripts.migrate_reviews_to_firebase import build_review_records


def test_booking_history_preserves_component1_interaction_weights() -> None:
    history = {
        "requested": {
            "provider_id": "P00001",
            "status": "booking_requested",
            "updated_at": "2026-08-01T10:00:00+00:00",
        },
        "completed": {
            "provider_id": "P00002",
            "status": "booking_completed",
            "updated_at": "2026-08-02T10:00:00+00:00",
        },
        "rated": {
            "provider_id": "P00003",
            "status": "booking_completed",
            "rating": 5,
            "updated_at": "2026-08-03T10:00:00+00:00",
        },
        "invalid": {"provider_id": "not-a-provider", "status": "booking_completed"},
        "firebase": {
            "provider_id": "GsMrbJuYYHR7d0uKEqA5OVjdKV73",
            "status": "booking_completed",
            "updated_at": "2026-08-04T10:00:00+00:00",
        },
    }

    preferences = booking_history_preference_ids(history)

    assert preferences.count("P00001") == 5
    assert preferences.count("P00002") == 9
    assert preferences.count("P00003") == 13
    assert preferences.count("GsMrbJuYYHR7d0uKEqA5OVjdKV73") == 9
    assert "not-a-provider" not in preferences


def test_mongo_booking_lifecycle_maps_to_one_firebase_customer_record() -> None:
    requested_at = datetime(2026, 8, 1, 10, tzinfo=UTC)
    completed_at = requested_at + timedelta(hours=2)
    rated_at = completed_at + timedelta(minutes=10)
    common = {
        "user_id": "U00001",
        "request_id": "R00001",
        "provider_id": "P00001",
        "provider_name": "Research Provider",
        "category": "Electricians",
    }
    interactions = [
        {
            **common,
            "interaction_id": "I-REQUEST",
            "interaction_type": "booking_requested",
            "timestamp": requested_at,
        },
        {
            **common,
            "interaction_id": "I-COMPLETE",
            "interaction_type": "booking_completed",
            "timestamp": completed_at,
        },
        {
            **common,
            "interaction_id": "I-RATING",
            "interaction_type": "rated",
            "rating": 5,
            "review_text": "Excellent work",
            "timestamp": rated_at,
        },
    ]

    records = build_booking_records(interactions, {"U00001": "firebase-customer"})

    assert len(records) == 1
    firebase_uid, booking_id, record = records[0]
    assert firebase_uid == "firebase-customer"
    assert booking_id == "I-REQUEST"
    assert record["status"] == "booking_completed"
    assert record["completed_at"] == completed_at.isoformat()
    assert record["rating"] == 5
    assert record["review_text"] == "Excellent work"
    assert record["source_event_ids"] == ["I-REQUEST", "I-COMPLETE", "I-RATING"]


def test_rated_booking_maps_to_matching_customer_and_provider_reviews() -> None:
    requested_at = datetime(2026, 8, 1, 10, tzinfo=UTC)
    completed_at = requested_at + timedelta(hours=2)
    rated_at = completed_at + timedelta(minutes=10)
    common = {
        "user_id": "U00001",
        "request_id": "R00001",
        "provider_id": "P00001",
        "provider_name": "Research Provider",
        "category": "Electricians",
    }
    records = build_review_records(
        [
            {
                **common,
                "interaction_id": "I-REQUEST",
                "interaction_type": "booking_requested",
                "timestamp": requested_at,
            },
            {
                **common,
                "interaction_id": "I-COMPLETE",
                "booking_interaction_id": "I-REQUEST",
                "interaction_type": "booking_completed",
                "timestamp": completed_at,
            },
            {
                **common,
                "interaction_id": "I-RATING",
                "booking_interaction_id": "I-REQUEST",
                "interaction_type": "rated",
                "rating": 5,
                "review_text": "Excellent work",
                "timestamp": rated_at,
            },
        ],
        {"U00001": "firebase-customer"},
    )

    assert len(records) == 1
    record = records[0]
    assert record["firebase_uid"] == "firebase-customer"
    assert record["booking_id"] == "I-REQUEST"
    assert record["customer_booking"]["rating"] == 5
    assert record["provider_review"]["rating"] == 5
    assert record["provider_review"]["verified_booking"] is True


def test_customer_clients_cannot_mutate_admin_booking_history() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    rules = json.loads((repository_root / "database.rules.json").read_text("utf-8"))
    customer_rule = rules["rules"]["customers"]["$uid"]

    assert customer_rule[".write"] == "auth != null && auth.uid === $uid"
    assert customer_rule[".validate"] == (
        "newData.child('bookingHistory').val() === "
        "data.child('bookingHistory').val()"
    )


def test_provider_clients_cannot_mutate_reviews_or_rating_aggregates() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    rules = json.loads((repository_root / "database.rules.json").read_text("utf-8"))
    validation = rules["rules"]["providers"]["$providerId"][".validate"]

    for protected_field in (
        "reviews",
        "reviewStats",
        "platformRating",
        "platformReviewCount",
        "rating",
        "reviewCount",
    ):
        assert f"newData.child('{protected_field}').val()" in validation
        assert f"data.child('{protected_field}').val()" in validation


def test_firebase_ping_uses_a_shallow_admin_root_read() -> None:
    calls: list[tuple[str, bool]] = []

    class Reference:
        def get(self, *, shallow: bool = False) -> dict[str, bool]:
            calls.append(("get", shallow))
            return {"providers": True}

    client = FirebaseRtdbClient(Settings(_env_file=None))
    client._reference = lambda path: (  # type: ignore[method-assign]
        calls.append((path, False)) or Reference()
    )

    assert asyncio.run(client.ping()) is True
    assert calls == [("/", False), ("get", True)]


def test_provider_review_is_idempotent_and_refreshes_platform_statistics() -> None:
    provider = {"id": "P00001"}
    reviews: dict[str, dict[str, object]] = {}
    provider_updates: dict[str, object] = {}

    class ProviderReference:
        def get(self) -> dict[str, object]:
            return provider

        def update(self, updates: dict[str, object]) -> None:
            provider_updates.update(updates)

    class ReviewsReference:
        def get(self) -> dict[str, dict[str, object]]:
            return reviews

    class ReviewReference:
        def transaction(self, callback):
            reviews["BOOKING1"] = callback(reviews.get("BOOKING1"))

    def reference(path: str):
        return {
            "providers/P00001": ProviderReference(),
            "providers/P00001/reviews": ReviewsReference(),
            "providers/P00001/reviews/BOOKING1": ReviewReference(),
        }[path]

    client = FirebaseRtdbClient(Settings(_env_file=None))
    client._reference = reference  # type: ignore[method-assign]
    payload = {
        "booking_id": "BOOKING1",
        "provider_id": "P00001",
        "customer_uid": "firebase-customer",
        "rating": 4,
        "review_text": "Good work",
        "reviewed_at": "2026-08-11T10:00:00+00:00",
        "source": "platform_booking",
    }

    assert asyncio.run(
        client.create_provider_review("P00001", "BOOKING1", payload)
    ) is True
    assert asyncio.run(
        client.create_provider_review("P00001", "BOOKING1", payload)
    ) is False
    statistics = asyncio.run(client.refresh_provider_review_statistics("P00001"))

    assert statistics["averageRating"] == 4
    assert statistics["count"] == 1
    assert provider_updates["platformRating"] == 4
    assert provider_updates["platformReviewCount"] == 1
    assert provider_updates["reviewStats"] == statistics


def test_booking_rollback_deletes_only_a_matching_pipeline_run() -> None:
    class Reference:
        def __init__(self, value: dict[str, str]) -> None:
            self.value = value
            self.deleted = False

        def get(self) -> dict[str, str]:
            return self.value

        def delete(self) -> None:
            self.deleted = True

    matching = Reference({"pipeline_run_id": "PIPE1"})
    other = Reference({"pipeline_run_id": "PIPE2"})
    client = FirebaseRtdbClient(Settings(_env_file=None))

    client._reference = lambda _path: matching  # type: ignore[method-assign]
    asyncio.run(
        client.delete_customer_booking_if_matching("customer", "booking", "PIPE1")
    )
    assert matching.deleted is True

    client._reference = lambda _path: other  # type: ignore[method-assign]
    asyncio.run(
        client.delete_customer_booking_if_matching("customer", "booking", "PIPE1")
    )
    assert other.deleted is False
