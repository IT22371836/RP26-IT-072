"""Prune inactive research login accounts while preserving booked providers."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from firebase_admin import auth, db

from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient

EXPECTED_INACTIVE_COUNT = 3_998
EXPECTED_ACTIVE_RESEARCH_COUNT = 1_000
SELECTION_VERSION = "research-balanced-booking-preservation-v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    return parser.parse_args()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def research_user_id(provider_id: str) -> str:
    return "U" + provider_id[1:]


def is_inactive_research(provider_id: str, profile: Any) -> bool:
    if not isinstance(profile, dict):
        return False
    eligibility = profile.get("pipelineEligibility") or {}
    return bool(
        provider_id.startswith("P")
        and profile.get("researchSeed") is True
        and profile.get("profileSource") == "research_seed"
        and eligibility.get("activeResearchBaseline") is False
        and eligibility.get("eligible") is False
    )


def is_active_research(profile: Any) -> bool:
    if not isinstance(profile, dict):
        return False
    eligibility = profile.get("pipelineEligibility") or {}
    return bool(
        profile.get("researchSeed") is True
        and eligibility.get("activeResearchBaseline") is True
        and eligibility.get("eligible") is True
    )


def meaningful_provider_ids(
    interactions: dict[str, Any], customers: dict[str, Any]
) -> set[str]:
    provider_ids = {
        str(item.get("provider_id"))
        for item in interactions.values()
        if isinstance(item, dict)
        and str(item.get("interaction_type") or "") != "impression"
        and item.get("provider_id")
    }
    for customer in customers.values():
        if not isinstance(customer, dict):
            continue
        for booking in (customer.get("bookingHistory") or {}).values():
            if not isinstance(booking, dict):
                continue
            provider_id = booking.get("provider_id") or booking.get("providerId")
            if provider_id:
                provider_ids.add(str(provider_id))
    return provider_ids


def choose_booking_preserving_swaps(
    providers: dict[str, Any], protected_ids: set[str], referenced_ids: set[str]
) -> dict[str, str]:
    """Map each protected inactive provider to a safe active same-category demotion."""

    swaps: dict[str, str] = {}
    used: set[str] = set()
    for protected_id in sorted(protected_ids):
        protected = providers[protected_id]
        category = str(protected.get("category") or "")
        active = [
            (provider_id, profile)
            for provider_id, profile in providers.items()
            if is_active_research(profile)
            and str(profile.get("category") or "") == category
            and provider_id not in referenced_ids
            and provider_id not in used
        ]
        district_counts = Counter(str(profile.get("district") or "") for _, profile in active)
        candidates = sorted(
            active,
            key=lambda item: (
                -district_counts[str(item[1].get("district") or "")],
                item[0],
            ),
        )
        if not candidates:
            raise RuntimeError(
                f"No safe active same-category replacement for booked provider {protected_id}"
            )
        replacement_id = candidates[0][0]
        swaps[protected_id] = replacement_id
        used.add(replacement_id)
    return swaps


def validate_identity(
    provider_id: str,
    profile: dict[str, Any],
    users: dict[str, Any],
    indexes: dict[str, Any],
    auth_users: dict[str, Any],
) -> None:
    user_id = research_user_id(provider_id)
    email = str(profile.get("email") or "").strip().lower()
    auth_user = auth_users.get(provider_id)
    user = users.get(user_id)
    if str(profile.get("id")) != provider_id or str(profile.get("uid")) != provider_id:
        raise RuntimeError(f"Provider identity mismatch: {provider_id}")
    if str(profile.get("userId")) != user_id or str(profile.get("email")) != email:
        raise RuntimeError(f"Provider relation mismatch: {provider_id}")
    if auth_user is None or str(auth_user.email or "").lower() != email:
        raise RuntimeError(f"Firebase Auth identity mismatch: {provider_id}")
    if not isinstance(user, dict) or user.get("role") != "provider":
        raise RuntimeError(f"Core user missing: {provider_id}")
    if user.get("legacy", {}).get("firebase_uid") != provider_id:
        raise RuntimeError(f"Core user Firebase relation mismatch: {provider_id}")
    if (indexes.get("providers_by_user") or {}).get(user_id) != provider_id:
        raise RuntimeError(f"Provider index mismatch: {provider_id}")
    if (indexes.get("users_by_firebase_uid") or {}).get(provider_id) != user_id:
        raise RuntimeError(f"Firebase UID index mismatch: {provider_id}")
    if (indexes.get("users_by_email") or {}).get(email_key(email)) != user_id:
        raise RuntimeError(f"Email index mismatch: {provider_id}")


def promoted_profile(profile: dict[str, Any]) -> dict[str, Any]:
    result = dict(profile)
    eligibility = dict(result.get("pipelineEligibility") or {})
    eligibility.update(
        {
            "activeResearchBaseline": True,
            "eligible": True,
            "selectionVersion": SELECTION_VERSION,
            "selectionReason": "promoted_to_preserve_existing_booking",
            "researchBaselineTarget": EXPECTED_ACTIVE_RESEARCH_COUNT,
            "evaluatedAt": datetime.now(UTC).isoformat(),
        }
    )
    result["pipelineEligibility"] = eligibility
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def auth_inventory(app: Any) -> dict[str, Any]:
    return {user.uid: user for user in auth.list_users(app=app).iterate_all()}


def auth_metadata(users: dict[str, Any], provider_ids: set[str]) -> dict[str, Any]:
    return {
        provider_id: {
            "uid": users[provider_id].uid,
            "email": users[provider_id].email,
            "display_name": users[provider_id].display_name,
            "disabled": users[provider_id].disabled,
            "email_verified": users[provider_id].email_verified,
        }
        for provider_id in sorted(provider_ids)
        if provider_id in users
    }


def delete_auth_users(app: Any, provider_ids: set[str]) -> None:
    ordered = sorted(provider_ids)
    for offset in range(0, len(ordered), 500):
        result = auth.delete_users(ordered[offset : offset + 500], app=app)
        if result.failure_count:
            raise RuntimeError(f"Firebase Auth deletion failed: {result.errors}")


def verification_summary(providers: dict[str, Any]) -> dict[str, int]:
    research = [profile for profile in providers.values() if isinstance(profile, dict) and profile.get("researchSeed") is True]
    return {
        "provider_count": len(providers),
        "research_count": len(research),
        "active_research_count": sum(is_active_research(profile) for profile in research),
        "website_count": sum(
            isinstance(profile, dict) and profile.get("profileSource") == "web_registration"
            for profile in providers.values()
        ),
        "legacy_count": sum(
            isinstance(profile, dict) and profile.get("profileSource") == "legacy"
            for profile in providers.values()
        ),
    }


def main() -> int:
    args = parse_args()
    if args.apply and args.backup_dir is None:
        raise RuntimeError("--backup-dir is required with --apply")
    settings = get_settings()
    app = FirebaseRtdbClient(settings)._app()
    providers = db.reference("providers", app=app).get() or {}
    users = db.reference("core/users", app=app).get() or {}
    indexes = db.reference("core/indexes", app=app).get() or {}
    events = db.reference("core/provider_verification_events", app=app).get() or {}
    interactions = db.reference("component1/interactions", app=app).get() or {}
    customers = db.reference("customers", app=app).get() or {}
    filter_requests = db.reference("filter_requests", app=app).get() or {}
    filter_hash_before = canonical_sha256(filter_requests)
    auth_users = auth_inventory(app)

    inactive = {
        provider_id
        for provider_id, profile in providers.items()
        if is_inactive_research(provider_id, profile)
    }
    referenced = meaningful_provider_ids(interactions, customers)
    protected = inactive & referenced

    if args.verify_only:
        summary = verification_summary(providers)
        verified = (
            not inactive
            and summary["research_count"] == EXPECTED_ACTIVE_RESEARCH_COUNT
            and summary["active_research_count"] == EXPECTED_ACTIVE_RESEARCH_COUNT
        )
        report = {
            "mode": "verify-only",
            "verified": verified,
            "summary": summary,
            "component2_filter_requests_sha256": filter_hash_before,
            "component2_untouched": True,
        }
        write_json(args.report, report)
        print(json.dumps(report, indent=2))
        return 0 if verified else 1

    if len(inactive) != EXPECTED_INACTIVE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_INACTIVE_COUNT} inactive research providers, found {len(inactive)}"
        )
    for provider_id in sorted(inactive):
        validate_identity(provider_id, providers[provider_id], users, indexes, auth_users)

    swaps = choose_booking_preserving_swaps(providers, protected, referenced)
    demoted = set(swaps.values())
    deletion_ids = (inactive - protected) | demoted
    if len(deletion_ids) != EXPECTED_INACTIVE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_INACTIVE_COUNT} deletion IDs, found {len(deletion_ids)}"
        )
    for provider_id in sorted(demoted):
        validate_identity(provider_id, providers[provider_id], users, indexes, auth_users)

    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "applied": False,
        "inactive_count": len(inactive),
        "protected_booking_provider_ids": sorted(protected),
        "booking_preserving_swaps": swaps,
        "deletion_count": len(deletion_ids),
        "deletion_ids": sorted(deletion_ids),
        "preserved_paths": [
            "customers/*/bookingHistory",
            "component1/interactions",
            "pipeline/runs",
            "filter_requests",
            "research_provider_reviews",
            "research_customers",
        ],
        "component2_filter_requests_sha256_before": filter_hash_before,
        "contains_passwords": False,
    }
    if not args.apply:
        write_json(args.report, report)
        print(json.dumps({**report, "deletion_ids": f"{len(deletion_ids)} IDs"}, indent=2))
        return 0

    backup_dir: Path = args.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    relevant_user_ids = {research_user_id(provider_id) for provider_id in deletion_ids}
    write_json(
        backup_dir / "provider-profiles.json",
        {provider_id: providers[provider_id] for provider_id in sorted(deletion_ids)},
    )
    write_json(
        backup_dir / "core-users.json",
        {user_id: users[user_id] for user_id in sorted(relevant_user_ids)},
    )
    write_json(backup_dir / "core-indexes.json", indexes)
    write_json(
        backup_dir / "provider-verification-events.json",
        {
            event_id: event
            for event_id, event in events.items()
            if isinstance(event, dict) and str(event.get("provider_id") or "") in deletion_ids
        },
    )
    write_json(backup_dir / "firebase-auth-metadata.json", auth_metadata(auth_users, deletion_ids))
    write_json(
        backup_dir / "promoted-booked-providers.json",
        {provider_id: providers[provider_id] for provider_id in sorted(protected)},
    )
    write_json(backup_dir / "manifest.json", report)

    delete_auth_users(app, deletion_ids)
    updates: dict[str, Any] = {}
    for provider_id in sorted(deletion_ids):
        user_id = research_user_id(provider_id)
        email = str(providers[provider_id].get("email") or "").strip().lower()
        updates[f"providers/{provider_id}"] = None
        updates[f"core/users/{user_id}"] = None
        updates[f"core/indexes/providers_by_user/{user_id}"] = None
        updates[f"core/indexes/users_by_firebase_uid/{provider_id}"] = None
        updates[f"core/indexes/users_by_email/{email_key(email)}"] = None
        event_id = f"VELIGIBILITYV1-{provider_id}"
        if event_id in events:
            updates[f"core/provider_verification_events/{event_id}"] = None
    for provider_id in sorted(protected):
        updates[f"providers/{provider_id}"] = promoted_profile(providers[provider_id])
    root = db.reference("/", app=app)
    items = list(updates.items())
    for offset in range(0, len(items), 250):
        root.update(dict(items[offset : offset + 250]))

    stored_providers = db.reference("providers", app=app).get() or {}
    stored_filter_hash = canonical_sha256(
        db.reference("filter_requests", app=app).get() or {}
    )
    remaining_auth = auth_inventory(app)
    deleted_auth_remaining = sorted(deletion_ids & set(remaining_auth))
    summary = verification_summary(stored_providers)
    retained_protected = all(
        provider_id in stored_providers and is_active_research(stored_providers[provider_id])
        for provider_id in protected
    )
    verified = bool(
        summary["research_count"] == EXPECTED_ACTIVE_RESEARCH_COUNT
        and summary["active_research_count"] == EXPECTED_ACTIVE_RESEARCH_COUNT
        and not deleted_auth_remaining
        and retained_protected
        and stored_filter_hash == filter_hash_before
    )
    report.update(
        {
            "applied": True,
            "verified": verified,
            "summary": summary,
            "deleted_auth_remaining": deleted_auth_remaining,
            "protected_booking_providers_retained": retained_protected,
            "component2_filter_requests_sha256_after": stored_filter_hash,
            "component2_untouched": stored_filter_hash == filter_hash_before,
        }
    )
    write_json(args.report, report)
    write_json(backup_dir / "result.json", report)
    print(json.dumps({**report, "deletion_ids": f"{len(deletion_ids)} IDs"}, indent=2))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
