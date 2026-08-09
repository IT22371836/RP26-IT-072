from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient

BOOKING_EVENT_TYPES = {
    "selected",
    "booking_requested",
    "booking_completed",
    "booking_cancelled",
    "rated",
}


def iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None


def build_booking_records(
    interactions: list[dict[str, Any]],
    firebase_uids: dict[str, str],
) -> list[tuple[str, str, dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in interactions:
        key = (
            str(event.get("user_id", "")),
            str(event.get("request_id", "")),
            str(event.get("provider_id", "")),
        )
        grouped[key].append(event)

    records: list[tuple[str, str, dict[str, Any]]] = []
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
        if requested is None:
            continue
        terminal = next(
            (
                item
                for item in reversed(ordered)
                if item.get("interaction_type")
                in {"booking_completed", "booking_cancelled"}
            ),
            None,
        )
        rating = next(
            (item for item in reversed(ordered) if item.get("interaction_type") == "rated"),
            None,
        )
        status = (
            str(terminal["interaction_type"])
            if terminal is not None
            else "booking_requested"
        )
        booking_id = str(requested["interaction_id"])
        record = {
            "booking_id": booking_id,
            "request_id": request_id,
            "pipeline_run_id": requested.get("pipeline_run_id"),
            "customer_uid": firebase_uid,
            "provider_id": provider_id,
            "provider_name": requested.get("provider_name"),
            "category": requested.get("category"),
            "status": status,
            "requested_at": iso(requested.get("timestamp")),
            "updated_at": iso(ordered[-1].get("timestamp")),
            "completed_at": (
                iso(terminal.get("timestamp"))
                if terminal and status == "booking_completed"
                else None
            ),
            "cancelled_at": (
                iso(terminal.get("timestamp"))
                if terminal and status == "booking_cancelled"
                else None
            ),
            "rating": rating.get("rating") if rating else None,
            "review_text": rating.get("review_text") if rating else None,
            "rated_at": iso(rating.get("timestamp")) if rating else None,
            "source": "mongo_interactions_migration_v1",
            "source_event_ids": [str(item["interaction_id"]) for item in ordered],
        }
        records.append((firebase_uid, booking_id, record))
    return records


async def run(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    client = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    database = client[settings.mongodb_database]
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
        query: dict[str, Any] = {"interaction_type": {"$in": sorted(BOOKING_EVENT_TYPES)}}
        interactions = list(
            database.interactions.find(query, {"_id": 0}).sort("timestamp", 1)
        )
    finally:
        client.close()

    records = build_booking_records(interactions, firebase_uids)
    if args.limit is not None:
        records = records[: args.limit]
    booking_user_ids = {
        str(item.get("user_id"))
        for item in interactions
        if item.get("interaction_type") == "booking_requested"
    }
    event_type_counts = Counter(
        str(item.get("interaction_type") or "missing") for item in interactions
    )
    unmapped_user_ids = sorted(booking_user_ids - firebase_uids.keys())
    firebase = FirebaseRtdbClient(settings)
    created = 0
    updated = 0
    verified = 0
    mismatches: list[str] = []
    conflicts: list[str] = []
    profiles: dict[str, dict[str, Any] | None] = {}

    if args.apply or args.verify_only:
        unique_uids = sorted({firebase_uid for firebase_uid, _, _ in records})
        profile_values = await asyncio.gather(
            *(firebase.get_customer(firebase_uid) for firebase_uid in unique_uids)
        )
        profiles = dict(zip(unique_uids, profile_values, strict=True))

        for firebase_uid, booking_id, record in records:
            profile = profiles.get(firebase_uid)
            path = f"{firebase_uid}/{booking_id}"
            if profile is None:
                mismatches.append(f"missing-customer-profile:{path}")
                continue
            history = profile.get("bookingHistory")
            stored = history.get(booking_id) if isinstance(history, dict) else None
            if stored is None or stored == record:
                continue
            same_identity = (
                isinstance(stored, dict)
                and stored.get("booking_id") == booking_id
                and stored.get("request_id") == record["request_id"]
                and stored.get("provider_id") == record["provider_id"]
            )
            if args.apply and (
                not isinstance(stored, dict)
                or stored.get("source") != "mongo_interactions_migration_v1"
                or not same_identity
            ):
                conflicts.append(path)

    # Preflight every destination before the first write. Existing live records are
    # never replaced; only an earlier version of this migration may be advanced.
    if args.apply and not mismatches and not conflicts:
        for firebase_uid, booking_id, record in records:
            profile = profiles[firebase_uid]
            history = profile.get("bookingHistory") if profile else None
            stored = history.get(booking_id) if isinstance(history, dict) else None
            if stored == record:
                continue
            if stored is None:
                if await firebase.create_customer_booking(firebase_uid, booking_id, record):
                    created += 1
            else:
                await firebase.update_customer_booking(firebase_uid, booking_id, record)
                updated += 1

    if (args.apply and not mismatches and not conflicts) or args.verify_only:
        histories: dict[str, dict[str, dict[str, Any]]] = {}
        for firebase_uid, booking_id, record in records:
            if profiles.get(firebase_uid) is None:
                continue
            if firebase_uid not in histories:
                histories[firebase_uid] = await firebase.get_customer_booking_history(
                    firebase_uid
                )
            stored = histories[firebase_uid].get(booking_id)
            if stored == record:
                verified += 1
            else:
                mismatches.append(f"{firebase_uid}/{booking_id}")

    return {
        "mode": "apply" if args.apply else "verify-only" if args.verify_only else "dry-run",
        "source_event_count": len(interactions),
        "source_event_type_counts": dict(sorted(event_type_counts.items())),
        "booking_request_event_count": event_type_counts["booking_requested"],
        "mapped_booking_count": len(records),
        "created_count": created,
        "updated_count": updated,
        "verified_count": verified,
        "mismatch_count": len(mismatches) + len(conflicts),
        "mismatches": [*mismatches, *(f"collision:{path}" for path in conflicts)][:100],
        "unmapped_user_count": len(unmapped_user_ids),
        "unmapped_user_ids": unmapped_user_ids[:100],
        "firebase_path": "customers/{firebase_uid}/bookingHistory/{booking_id}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate Mongo booking events into Firebase customer booking history"
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
