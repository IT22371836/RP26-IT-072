from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient


def iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None


def build_review_records(
    interactions: list[dict[str, Any]],
    firebase_uids: dict[str, str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in interactions:
        grouped[
            (
                str(event.get("user_id", "")),
                str(event.get("request_id", "")),
                str(event.get("provider_id", "")),
            )
        ].append(event)

    records: list[dict[str, Any]] = []
    for (user_id, request_id, provider_id), events in grouped.items():
        firebase_uid = firebase_uids.get(user_id)
        if not firebase_uid:
            continue
        ordered = sorted(events, key=lambda item: iso(item.get("timestamp")) or "")
        requested = next(
            (
                item
                for item in ordered
                if item.get("interaction_type") == "booking_requested"
            ),
            None,
        )
        completed = next(
            (
                item
                for item in reversed(ordered)
                if item.get("interaction_type") == "booking_completed"
            ),
            None,
        )
        rating = next(
            (
                item
                for item in reversed(ordered)
                if item.get("interaction_type") == "rated"
            ),
            None,
        )
        if requested is None or completed is None or rating is None:
            continue
        booking_id = str(
            rating.get("booking_interaction_id")
            or completed.get("booking_interaction_id")
            or requested["interaction_id"]
        )
        rated_at = iso(rating.get("timestamp"))
        records.append(
            {
                "firebase_uid": firebase_uid,
                "booking_id": booking_id,
                "customer_booking": {
                    "booking_id": booking_id,
                    "request_id": request_id,
                    "pipeline_run_id": requested.get("pipeline_run_id"),
                    "customer_uid": firebase_uid,
                    "provider_id": provider_id,
                    "provider_name": requested.get("provider_name"),
                    "category": requested.get("category"),
                    "status": "booking_completed",
                    "requested_at": iso(requested.get("timestamp")),
                    "updated_at": rated_at,
                    "completed_at": iso(completed.get("timestamp")),
                    "cancelled_at": None,
                    "rating": rating.get("rating"),
                    "review_text": rating.get("review_text"),
                    "rated_at": rated_at,
                    "source": "mongo_review_migration_v1",
                },
                "provider_review": {
                    "review_id": booking_id,
                    "booking_id": booking_id,
                    "request_id": request_id,
                    "customer_uid": firebase_uid,
                    "provider_id": provider_id,
                    "provider_name": requested.get("provider_name"),
                    "category": requested.get("category"),
                    "rating": rating.get("rating"),
                    "review_text": rating.get("review_text"),
                    "reviewed_at": rated_at,
                    "verified_booking": True,
                    "source": "platform_booking",
                },
            }
        )
    return records


def same_review(left: Any, right: dict[str, Any]) -> bool:
    return isinstance(left, dict) and all(
        left.get(field) == right.get(field)
        for field in (
            "booking_id",
            "request_id",
            "customer_uid",
            "provider_id",
            "rating",
            "review_text",
        )
    )


async def run(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    mongo = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    database = mongo[settings.mongodb_database]
    try:
        users = list(
            database.users.find(
                {"legacy.firebase_uid": {"$type": "string"}},
                {"_id": 0, "user_id": 1, "legacy.firebase_uid": 1},
            )
        )
        firebase_uids = {
            str(item["user_id"]): str(item["legacy"]["firebase_uid"])
            for item in users
        }
        interactions = list(
            database.interactions.find(
                {
                    "interaction_type": {
                        "$in": ["booking_requested", "booking_completed", "rated"]
                    }
                },
                {"_id": 0},
            ).sort("timestamp", 1)
        )
    finally:
        mongo.close()

    records = build_review_records(interactions, firebase_uids)
    if args.limit is not None:
        records = records[: args.limit]
    firebase = FirebaseRtdbClient(settings)
    created_customer = 0
    updated_customer = 0
    created_provider = 0
    verified = 0
    mismatches: list[str] = []
    conflicts: list[str] = []

    if args.apply or args.verify_only:
        for record in records:
            uid = record["firebase_uid"]
            booking_id = record["booking_id"]
            provider_id = record["provider_review"]["provider_id"]
            customer = await firebase.get_customer(uid)
            providers = await firebase.get_providers([provider_id])
            if customer is None:
                mismatches.append(f"missing-customer:{uid}")
                continue
            if provider_id not in providers:
                mismatches.append(f"missing-provider:{provider_id}")
                continue
            history = customer.get("bookingHistory")
            customer_booking = (
                history.get(booking_id) if isinstance(history, dict) else None
            )
            expected_booking = record["customer_booking"]
            if customer_booking is not None and not (
                isinstance(customer_booking, dict)
                and customer_booking.get("booking_id") == booking_id
                and customer_booking.get("request_id") == expected_booking["request_id"]
                and customer_booking.get("provider_id") == provider_id
                and customer_booking.get("rating") in (None, expected_booking["rating"])
                and customer_booking.get("review_text")
                in (None, expected_booking["review_text"])
            ):
                conflicts.append(f"customer:{uid}/{booking_id}")
            provider_reviews = await firebase.get_provider_reviews(provider_id)
            stored_review = provider_reviews.get(booking_id)
            if stored_review is not None and not same_review(
                stored_review, record["provider_review"]
            ):
                conflicts.append(f"provider:{provider_id}/{booking_id}")

    if args.apply and not mismatches and not conflicts:
        touched_providers: set[str] = set()
        for record in records:
            uid = record["firebase_uid"]
            booking_id = record["booking_id"]
            provider_id = record["provider_review"]["provider_id"]
            history = await firebase.get_customer_booking_history(uid)
            if booking_id not in history:
                if await firebase.create_customer_booking(
                    uid, booking_id, record["customer_booking"]
                ):
                    created_customer += 1
            else:
                expected = record["customer_booking"]
                await firebase.update_customer_booking(
                    uid,
                    booking_id,
                    {
                        "status": "booking_completed",
                        "rating": expected["rating"],
                        "review_text": expected["review_text"],
                        "rated_at": expected["rated_at"],
                        "updated_at": expected["updated_at"],
                    },
                )
                updated_customer += 1
            if await firebase.create_provider_review(
                provider_id, booking_id, record["provider_review"]
            ):
                created_provider += 1
            touched_providers.add(provider_id)
        for provider_id in sorted(touched_providers):
            await firebase.refresh_provider_review_statistics(provider_id)

    if (args.apply and not mismatches and not conflicts) or args.verify_only:
        for record in records:
            uid = record["firebase_uid"]
            booking_id = record["booking_id"]
            provider_id = record["provider_review"]["provider_id"]
            customer = (await firebase.get_customer_booking_history(uid)).get(booking_id)
            provider = (await firebase.get_provider_reviews(provider_id)).get(booking_id)
            if (
                same_review(customer, record["provider_review"])
                and same_review(provider, record["provider_review"])
            ):
                verified += 1
            else:
                mismatches.append(f"verification:{provider_id}/{booking_id}")

    return {
        "mode": "apply" if args.apply else "verify-only" if args.verify_only else "dry-run",
        "source_interaction_count": len(interactions),
        "mapped_review_count": len(records),
        "customer_created_count": created_customer,
        "customer_updated_count": updated_customer,
        "provider_review_created_count": created_provider,
        "verified_pair_count": verified,
        "mismatch_count": len(mismatches) + len(conflicts),
        "mismatches": [*mismatches, *(f"collision:{item}" for item in conflicts)][:100],
        "customer_path": "customers/{firebase_uid}/bookingHistory/{booking_id}",
        "provider_path": "providers/{provider_id}/reviews/{booking_id}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate verified booking reviews to Firebase customer and provider paths"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(run(args))
    rendered = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if report["mismatch_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
