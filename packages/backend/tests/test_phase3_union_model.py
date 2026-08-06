from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.migrations.union_model import (
    PRESERVED_PROVIDER_FIELDS,
    PRESERVED_SERVICE_REQUEST_FIELDS,
    allocate_unmatched_identity,
    plan_additive_updates,
    plan_customer_union,
    plan_provider_union,
    resolve_request_mapping,
)


def identity_mapping(status: str, entity_type: str = "customer") -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "firebase_key": "firebase-key",
        "firebase_uid": "firebase-uid",
        "mongo_user_id": None,
        "mongo_customer_id": None,
        "mongo_provider_id": None,
        "mongo_request_id": None,
        "match_method": None,
        "match_status": status,
        "match_reason": "test",
        "migration_version": "firebase-to-mongo-v1",
    }


def test_additive_updates_never_overwrite_existing_values_or_scalar_parents() -> None:
    existing = {
        "zero": 0,
        "blank": "",
        "nullable": None,
        "same": {"value": [1, 2]},
        "legacy": "old-scalar-value",
    }
    before = deepcopy(existing)

    plan = plan_additive_updates(
        existing,
        {
            "zero": 99,
            "blank": "replacement",
            "nullable": "replacement",
            "same.value": [1, 2],
            "legacy.firebase_key": "unsafe-nested-write",
            "new_nested.value": {"preserved": True},
        },
    )

    assert existing == before
    assert plan["updates"] == {"new_nested.value": {"preserved": True}}
    assert plan["unchanged"] == ["same.value"]
    assert plan["conflicts"] == [
        "blank",
        "legacy.firebase_key",
        "nullable",
        "zero",
    ]


def test_public_ids_are_allocated_only_for_safely_unmatched_records() -> None:
    calls: list[str] = []

    def id_factory(prefix: str) -> str:
        calls.append(prefix)
        return f"{prefix}-generated"

    matched = identity_mapping("matched")
    ambiguous = identity_mapping("ambiguous")
    assert allocate_unmatched_identity(matched, id_factory) == matched
    assert allocate_unmatched_identity(ambiguous, id_factory) == ambiguous
    assert calls == []

    customer = identity_mapping("unmatched")
    allocated_customer = allocate_unmatched_identity(customer, id_factory)
    assert customer["mongo_user_id"] is None
    assert allocated_customer["firebase_key"] == "firebase-key"
    assert allocated_customer["firebase_uid"] == "firebase-uid"
    assert allocated_customer["mongo_user_id"] == "U-generated"
    assert allocated_customer["mongo_customer_id"] == "C-generated"
    assert allocated_customer["match_method"] == "newly_created"
    assert allocated_customer["requires_account_claim"] is True

    provider = identity_mapping("unmatched", "provider")
    allocated_provider = allocate_unmatched_identity(provider, id_factory)
    assert allocated_provider["mongo_user_id"] == "U-generated"
    assert allocated_provider["mongo_provider_id"] == "P-generated"
    assert calls == ["U", "C", "U", "P"]


def test_customer_union_preserves_identifiers_and_flags_profile_conflicts() -> None:
    source = {
        "id": "firebase-customer-id",
        "uid": "firebase-auth-uid",
        "fullName": "Firebase Name",
        "phone": "0700000000",
        "district": "Colombo",
        "city": "Colombo 03",
        "preferredLanguage": "si",
        "location": {"latitude": 6.9, "longitude": 79.8},
        "customerImage": "https://example.invalid/customer.jpg",
        "createdAt": "2025-01-02T03:04:05Z",
        "createdTimestamp": 1735787045000,
    }
    user = {"user_id": "U1", "full_name": "Existing Name"}
    profile = {
        "customer_id": "C1",
        "user_id": "U1",
        "phone": "0711111111",
        "city": "Colombo 03",
    }
    before = deepcopy((user, profile))

    plan = plan_customer_union("firebase-node-key", source, user, profile)

    assert (user, profile) == before
    assert plan["mongo_user_id"] == "U1"
    assert plan["mongo_customer_id"] == "C1"
    assert plan["user"]["updates"]["legacy.firebase_key"] == "firebase-node-key"
    assert plan["user"]["updates"]["legacy.firebase_id"] == source["id"]
    assert plan["user"]["updates"]["legacy.firebase_uid"] == source["uid"]
    assert plan["user"]["updates"]["legacy.firebase_created_at"] == source["createdAt"]
    assert plan["user"]["updates"]["legacy.firebase_created_at_parsed"] == datetime(
        2025, 1, 2, 3, 4, 5, tzinfo=UTC
    )
    assert "full_name" in plan["user"]["conflicts"]
    assert "phone" in plan["profile"]["conflicts"]
    assert "city" in plan["profile"]["unchanged"]
    assert plan["profile"]["updates"]["location"] == source["location"]


def test_provider_union_keeps_every_existing_provider_field_unchanged() -> None:
    provider = {
        "provider_id": "P1",
        "user_id": "U1",
        "provider_name": "Existing Provider",
        "category": "Electrical",
        "district": "Gampaha",
        "city": "Negombo",
        "experience_years": 10,
        "skills": ["Rewiring"],
        "description": "Existing description",
        "rating": 4.8,
        "review_count": 19,
        "booking_success_rate": 0.91,
        "interaction_count": 52,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2025, 1, 1, tzinfo=UTC),
    }
    source = {
        "id": "firebase-provider-id",
        "uid": "firebase-provider-uid",
        "fullName": "Different Firebase Name",
        "category": "Plumbing",
        "district": "Colombo",
        "city": "Moratuwa",
        "experienceYears": 7,
        "skills": ["Pipe repair"],
        "description": "Different Firebase description",
        "phone": "0770000000",
        "verified": True,
    }
    user = {"user_id": "U1", "role": "provider"}
    before = deepcopy((user, provider))

    plan = plan_provider_union("firebase-provider-key", source, user, provider)

    assert (user, provider) == before
    assert plan["mongo_user_id"] == "U1"
    assert plan["mongo_provider_id"] == "P1"
    assert not set(PRESERVED_PROVIDER_FIELDS) & set(plan["profile"]["updates"])
    assert {
        "provider_name",
        "category",
        "district",
        "city",
        "experience_years",
        "skills",
        "description",
    } <= set(plan["profile"]["conflicts"])
    assert plan["profile"]["updates"]["phone"] == source["phone"]
    assert plan["profile"]["updates"]["legacy.firebase_key"] == (
        "firebase-provider-key"
    )
    assert plan["profile"]["updates"]["verification.verified"] is True
    assert plan["profile"]["updates"]["verification.source_system"] == (
        "firebase_rtdb"
    )
    assert plan["review_reasons"] == []


def test_invalid_provider_experience_is_not_copied() -> None:
    plan = plan_provider_union(
        "provider-key",
        {"experienceYears": "seven"},
        {"user_id": "U1"},
        {"provider_id": "P1", "user_id": "U1"},
    )

    assert "experience_years" not in plan["profile"]["updates"]
    assert plan["review_reasons"] == ["invalid_experience_years"]


def test_request_union_links_exact_ids_without_modifying_service_requests() -> None:
    requests = [
        {
            "request_id": "R1",
            "user_id": "U1",
            "request_text": "Repair a leaking tap",
            "category": "Plumbing",
            "district": "Colombo",
            "city": "Moratuwa",
            "urgency": "normal",
            "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        }
    ]
    before = deepcopy(requests)
    record = {
        "request_id": "R1",
        "results": [{"provider_id": "P1", "score": 0.9}],
        "unrelated_category_guess": "Must not become a request category",
    }

    mapping = resolve_request_mapping("filter-key", record, requests)

    assert requests == before
    assert mapping["match_status"] == "matched"
    assert mapping["match_method"] == "request_id"
    assert mapping["mongo_request_id"] == "R1"
    assert mapping["service_request_updates"] == {}
    assert mapping["review_required"] is False
    assert all(field in requests[0] for field in PRESERVED_SERVICE_REQUEST_FIELDS)


def test_incomplete_or_ambiguous_request_links_are_sent_to_review() -> None:
    service_requests = [{"request_id": "R1"}, {"request_id": "R1"}]

    missing = resolve_request_mapping("missing-key", {"category": "Plumbing"}, [])
    unmatched = resolve_request_mapping(
        "unmatched-key", {"request_id": "R404", "city": "Kandy"}, []
    )
    duplicate = resolve_request_mapping(
        "duplicate-key", {"request_id": "R1"}, service_requests
    )

    assert (missing["match_status"], missing["match_reason"]) == (
        "unmatched",
        "missing_request_id",
    )
    assert (unmatched["match_status"], unmatched["match_reason"]) == (
        "unmatched",
        "no_service_request",
    )
    assert (duplicate["match_status"], duplicate["match_reason"]) == (
        "ambiguous",
        "duplicate_service_request_id",
    )
    assert all(item["review_required"] for item in (missing, unmatched, duplicate))
    assert all(
        item["service_request_updates"] == {}
        for item in (missing, unmatched, duplicate)
    )
