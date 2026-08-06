from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.repositories.legacy_firebase import MIGRATION_VERSION
from app.schemas.common import new_public_id, utc_now

MISSING = object()

PRESERVED_PROVIDER_FIELDS = (
    "provider_id",
    "user_id",
    "provider_name",
    "category",
    "district",
    "city",
    "experience_years",
    "skills",
    "description",
    "rating",
    "review_count",
    "booking_success_rate",
    "interaction_count",
    "created_at",
    "updated_at",
)

PRESERVED_SERVICE_REQUEST_FIELDS = (
    "request_text",
    "category",
    "district",
    "city",
    "urgency",
    "request_id",
    "user_id",
    "created_at",
)


def _source(record: dict[str, Any], field: str) -> Any:
    return deepcopy(record[field]) if field in record else MISSING


def _dotted_state(document: dict[str, Any], path: str) -> tuple[str, Any]:
    value: Any = document
    parts = path.split(".")
    for index, part in enumerate(parts):
        if not isinstance(value, dict):
            return "blocked", value
        if part not in value:
            return "missing", MISSING
        value = value[part]
        if index < len(parts) - 1 and not isinstance(value, dict):
            return "blocked", value
    return "present", value


def _parsed_created_at(record: dict[str, Any]) -> Any:
    value = record.get("createdAt", MISSING)
    if not isinstance(value, str) or not value.strip():
        return MISSING
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return MISSING
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def plan_additive_updates(
    existing: dict[str, Any] | None,
    candidates: dict[str, Any],
) -> dict[str, Any]:
    """Plan dotted ``$set`` values without overwriting any existing attribute."""

    current = existing or {}
    updates: dict[str, Any] = {}
    unchanged: list[str] = []
    conflicts: list[str] = []
    for path, candidate in candidates.items():
        if candidate is MISSING:
            continue
        state, present = _dotted_state(current, path)
        if state == "missing":
            updates[path] = deepcopy(candidate)
        elif state == "present" and present == candidate:
            unchanged.append(path)
        else:
            conflicts.append(path)
    return {
        "updates": updates,
        "unchanged": sorted(unchanged),
        "conflicts": sorted(conflicts),
    }


def _legacy_candidates(source_key: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "legacy.firebase_key": source_key,
        "legacy.firebase_id": _source(record, "id"),
        "legacy.firebase_uid": _source(record, "uid"),
        "legacy.firebase_created_at": _source(record, "createdAt"),
        "legacy.firebase_created_at_parsed": _parsed_created_at(record),
        "legacy.firebase_created_timestamp": _source(record, "createdTimestamp"),
    }


def _integration_candidates(synced_at: datetime) -> dict[str, Any]:
    return {
        "migration_version": MIGRATION_VERSION,
        "source_system": "firebase_rtdb",
        "last_synced_at": synced_at,
    }


def plan_customer_union(
    source_key: str,
    record: dict[str, Any],
    user: dict[str, Any],
    customer_profile: dict[str, Any] | None,
    synced_at: datetime | None = None,
) -> dict[str, Any]:
    sync_time = synced_at or utc_now()
    user_candidates = {
        **_legacy_candidates(source_key, record),
        **_integration_candidates(sync_time),
        "full_name": _source(record, "fullName"),
    }
    profile_candidates = {
        "phone": _source(record, "phone"),
        "district": _source(record, "district"),
        "city": _source(record, "city"),
        "preferred_language": _source(record, "preferredLanguage"),
        "location": _source(record, "location"),
        "customer_image": _source(record, "customerImage"),
        **_legacy_candidates(source_key, record),
        **_integration_candidates(sync_time),
    }
    return {
        "entity_type": "customer",
        "mongo_user_id": user["user_id"],
        "mongo_customer_id": (
            customer_profile.get("customer_id") if customer_profile else None
        ),
        "user": plan_additive_updates(user, user_candidates),
        "profile": plan_additive_updates(customer_profile, profile_candidates),
    }


def plan_provider_union(
    source_key: str,
    record: dict[str, Any],
    user: dict[str, Any],
    provider: dict[str, Any] | None,
    synced_at: datetime | None = None,
) -> dict[str, Any]:
    sync_time = synced_at or utc_now()
    experience = _source(record, "experienceYears")
    invalid_experience = experience is not MISSING and (
        isinstance(experience, bool) or not isinstance(experience, (int, float))
    )
    if invalid_experience:
        experience = MISSING

    user_candidates = {
        **_legacy_candidates(source_key, record),
        **_integration_candidates(sync_time),
    }
    provider_candidates = {
        **_legacy_candidates(source_key, record),
        **_integration_candidates(sync_time),
        "provider_name": _source(record, "fullName"),
        "phone": _source(record, "phone"),
        "district": _source(record, "district"),
        "city": _source(record, "city"),
        "location": _source(record, "location"),
        "provider_image": _source(record, "providerImage"),
        "preferred_language": _source(record, "preferredLanguage"),
        "nic": _source(record, "nic"),
        "category": _source(record, "category"),
        "experience_years": experience,
        "skills": _source(record, "skills"),
        "description": _source(record, "description"),
        "working_hours": _source(record, "workingHours"),
        "documents": _source(record, "documents"),
        "extracted_features": _source(record, "extractedFeatures"),
        "verification.verified": _source(record, "verified"),
        "verification.source_system": (
            "firebase_rtdb" if "verified" in record else MISSING
        ),
    }
    return {
        "entity_type": "provider",
        "mongo_user_id": user["user_id"],
        "mongo_provider_id": provider.get("provider_id") if provider else None,
        "user": plan_additive_updates(user, user_candidates),
        "profile": plan_additive_updates(provider, provider_candidates),
        "review_reasons": ["invalid_experience_years"] if invalid_experience else [],
    }


def allocate_unmatched_identity(
    mapping: dict[str, Any],
    id_factory: Callable[[str], str] = new_public_id,
) -> dict[str, Any]:
    """Allocate public IDs only for a safely unmatched customer/provider decision."""

    allocated = deepcopy(mapping)
    if mapping.get("match_status") != "unmatched":
        return allocated
    entity_type = mapping.get("entity_type")
    if entity_type not in {"customer", "provider"}:
        return allocated

    allocated["mongo_user_id"] = id_factory("U")
    if entity_type == "customer":
        allocated["mongo_customer_id"] = id_factory("C")
    else:
        allocated["mongo_provider_id"] = id_factory("P")
    allocated["match_method"] = "newly_created"
    allocated["match_status"] = "matched"
    allocated["match_reason"] = "planned_new_identity_for_unmatched_record"
    allocated["requires_account_claim"] = True
    return allocated


def resolve_request_mapping(
    firebase_key: str,
    record: dict[str, Any],
    service_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    source_request_id = record.get("request_id")
    matches = (
        [item for item in service_requests if item.get("request_id") == source_request_id]
        if isinstance(source_request_id, str) and source_request_id
        else []
    )
    status = "unmatched"
    reason = "no_service_request"
    mongo_request_id: str | None = None
    if not isinstance(source_request_id, str) or not source_request_id:
        reason = "missing_request_id"
    elif len(matches) == 1:
        status = "matched"
        reason = "exact_request_id_match"
        mongo_request_id = str(matches[0]["request_id"])
    elif len(matches) > 1:
        status = "ambiguous"
        reason = "duplicate_service_request_id"

    return {
        "entity_type": "request",
        "firebase_key": firebase_key,
        "firebase_uid": None,
        "mongo_user_id": None,
        "mongo_customer_id": None,
        "mongo_provider_id": None,
        "mongo_request_id": mongo_request_id,
        "match_method": "request_id" if source_request_id else None,
        "match_status": status,
        "match_reason": reason,
        "migration_version": MIGRATION_VERSION,
        "service_request_updates": {},
        "review_required": status != "matched",
    }
