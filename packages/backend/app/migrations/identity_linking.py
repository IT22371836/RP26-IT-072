from __future__ import annotations

from typing import Any, Protocol

from app.repositories.legacy_firebase import MIGRATION_VERSION


class IdentityUserLookup(Protocol):
    async def find_all_by_email(
        self, email: str, *, limit: int = 2
    ) -> list[dict[str, Any]]: ...

    async def find_by_firebase_uid(self, firebase_uid: str) -> dict[str, Any] | None: ...


def normalize_email(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def firebase_uid_for_record(source_node: str, record: dict[str, Any]) -> str | None:
    # Customer RTDB records do not store a UID explicitly. Do not assume their node key is a UID.
    if source_node != "providers":
        return None
    uid = record.get("uid")
    return uid.strip() if isinstance(uid, str) and uid.strip() else None


async def resolve_identity_mapping(
    user_lookup: IdentityUserLookup,
    source_node: str,
    firebase_key: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    if source_node not in {"customers", "providers"}:
        raise ValueError(f"Identity linking does not support Firebase node {source_node!r}")

    entity_type = "customer" if source_node == "customers" else "provider"
    firebase_uid = firebase_uid_for_record(source_node, record)
    source_email = normalize_email(record.get("email"))
    user: dict[str, Any] | None = None
    match_method: str | None = None
    ambiguous_email = False

    if firebase_uid:
        user = await user_lookup.find_by_firebase_uid(firebase_uid)
        if user is not None:
            match_method = "uid"

    if user is None and source_email:
        email_matches = await user_lookup.find_all_by_email(source_email, limit=2)
        if len(email_matches) == 1:
            user = email_matches[0]
            match_method = "normalized_email"
        elif len(email_matches) > 1:
            match_method = "normalized_email"
            ambiguous_email = True

    match_status = "unmatched"
    match_reason = "no_backend_user"
    mongo_user_id: str | None = None
    if ambiguous_email:
        match_status = "ambiguous"
        match_reason = "duplicate_normalized_email"
    elif user is not None:
        backend_role = str(user.get("role", ""))
        if user.get("is_active") is False:
            match_status = "ambiguous"
            match_reason = "inactive_backend_user"
        elif backend_role != entity_type:
            match_status = "ambiguous"
            match_reason = "role_mismatch"
        else:
            match_status = "matched"
            match_reason = "unique_identity_match"
            mongo_user_id = str(user["user_id"])
    elif not source_email and not firebase_uid:
        match_reason = "no_linkable_identity"

    return {
        "entity_type": entity_type,
        "firebase_key": firebase_key,
        "firebase_uid": firebase_uid,
        "mongo_user_id": mongo_user_id,
        "mongo_customer_id": None,
        "mongo_provider_id": None,
        "mongo_request_id": None,
        "match_method": match_method,
        "match_status": match_status,
        "match_reason": match_reason,
        "migration_version": MIGRATION_VERSION,
    }
