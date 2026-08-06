import argparse
import asyncio
import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from app.core.config import get_settings
from app.migrations.firebase_rtdb import build_snapshot, load_firebase_export
from app.migrations.identity_linking import resolve_identity_mapping
from app.migrations.union_model import (
    PRESERVED_PROVIDER_FIELDS,
    PRESERVED_SERVICE_REQUEST_FIELDS,
    allocate_unmatched_identity,
    plan_customer_union,
    plan_provider_union,
    resolve_request_mapping,
)


class StateUserLookup:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = users

    async def find_all_by_email(
        self, email: str, *, limit: int = 2
    ) -> list[dict[str, Any]]:
        normalized = email.strip().lower()
        return [
            user
            for user in self.users
            if str(user.get("email", "")).strip().lower() == normalized
        ][:limit]

    async def find_by_firebase_uid(self, firebase_uid: str) -> dict[str, Any] | None:
        return next(
            (
                user
                for user in self.users
                if user.get("legacy", {}).get("firebase_uid") == firebase_uid
            ),
            None,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the Phase 3 additive union model without database writes."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


async def build_report(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    client = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        client.admin.command("ping")
        database = client[settings.mongodb_database]
        users = list(database["users"].find({}))
        customer_profiles = list(database["customer_profiles"].find({}))
        providers = list(database["providers"].find({}))
        service_requests = list(database["service_requests"].find({}))
    finally:
        client.close()

    users_before = deepcopy(users)
    customer_profiles_before = deepcopy(customer_profiles)
    providers_before = deepcopy(providers)
    service_requests_before = deepcopy(service_requests)
    lookup = StateUserLookup(users)
    identity_counts: Counter[str] = Counter()
    conflict_fields: Counter[str] = Counter()
    additive_fields: Counter[str] = Counter()
    review_reasons: Counter[str] = Counter()
    allocated_prefixes: Counter[str] = Counter()

    def planned_id(prefix: str) -> str:
        allocated_prefixes[prefix] += 1
        return f"{prefix}<planned-{allocated_prefixes[prefix]}>"

    for node, entity_type in (("customers", "customer"), ("providers", "provider")):
        for source_key, record in data.get(node, {}).items():
            mapping = await resolve_identity_mapping(lookup, node, source_key, record)
            original_status = mapping["match_status"]
            if original_status == "unmatched":
                allocated = allocate_unmatched_identity(mapping, planned_id)
                identity_counts["planned_new"] += 1
                identity_counts[f"planned_new_{entity_type}"] += 1
                if allocated["match_status"] != "matched":
                    review_reasons["unmatched_allocation_failed"] += 1
                continue
            if original_status == "ambiguous":
                identity_counts["ambiguous"] += 1
                review_reasons[mapping["match_reason"]] += 1
                continue

            identity_counts["matched_existing"] += 1
            user = next(
                item for item in users if item.get("user_id") == mapping["mongo_user_id"]
            )
            if node == "customers":
                profile = next(
                    (
                        item
                        for item in customer_profiles
                        if item.get("user_id") == mapping["mongo_user_id"]
                    ),
                    None,
                )
                plan = plan_customer_union(source_key, record, user, profile)
            else:
                profile = next(
                    (
                        item
                        for item in providers
                        if item.get("user_id") == mapping["mongo_user_id"]
                    ),
                    None,
                )
                plan = plan_provider_union(source_key, record, user, profile)
                review_reasons.update(plan["review_reasons"])
            for target in ("user", "profile"):
                conflict_fields.update(plan[target]["conflicts"])
                additive_fields.update(plan[target]["updates"])

    request_counts: Counter[str] = Counter()
    exact_filter_snapshots = 0
    for source_key, record in data.get("filter_requests", {}).items():
        mapping = resolve_request_mapping(source_key, record, service_requests)
        request_counts[mapping["match_status"]] += 1
        if mapping["review_required"]:
            review_reasons[mapping["match_reason"]] += 1
        snapshot = build_snapshot("filter_requests", source_key, record)
        if snapshot["source_record"] == record:
            exact_filter_snapshots += 1

    state_unchanged = (
        users == users_before
        and customer_profiles == customer_profiles_before
        and providers == providers_before
        and service_requests == service_requests_before
    )
    provider_fields_unchanged = all(
        all(before.get(field) == after.get(field) for field in PRESERVED_PROVIDER_FIELDS)
        for before, after in zip(providers_before, providers, strict=True)
    )
    service_request_fields_unchanged = all(
        all(
            before.get(field) == after.get(field)
            for field in PRESERVED_SERVICE_REQUEST_FIELDS
        )
        for before, after in zip(service_requests_before, service_requests, strict=True)
    )
    expected_id_allocations = 2 * identity_counts["planned_new"]
    actual_id_allocations = sum(allocated_prefixes.values())
    passed = (
        state_unchanged
        and provider_fields_unchanged
        and service_request_fields_unchanged
        and actual_id_allocations == expected_id_allocations
        and exact_filter_snapshots == len(data.get("filter_requests", {}))
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-dry-run",
        "summary": {
            "passed": passed,
            "firebase_entities": len(data.get("customers", {}))
            + len(data.get("providers", {})),
            "identity_decisions": dict(sorted(identity_counts.items())),
            "planned_public_ids": dict(sorted(allocated_prefixes.items())),
            "public_ids_generated_only_for_unmatched": (
                actual_id_allocations == expected_id_allocations
            ),
            "additive_update_paths": sum(additive_fields.values()),
            "conflicting_paths_for_review": sum(conflict_fields.values()),
            "request_decisions": dict(sorted(request_counts.items())),
            "filter_snapshots_exact": exact_filter_snapshots,
            "source_documents_unchanged": state_unchanged,
            "provider_fields_unchanged": provider_fields_unchanged,
            "service_request_fields_unchanged": service_request_fields_unchanged,
        },
        "additive_fields": dict(sorted(additive_fields.items())),
        "conflict_fields": dict(sorted(conflict_fields.items())),
        "review_reasons": dict(sorted(review_reasons.items())),
        "request_model": {
            "link_collection": "legacy_identity_map",
            "link_method": "exact request_id",
            "service_request_updates_planned": 0,
            "context_filter_results_required_now": False,
            "context_filter_results_decision": (
                "deferred until an active-read API requires projection; immutable filter "
                "snapshots remain the source of truth"
            ),
        },
        "source_database_writes": 0,
    }


def main() -> int:
    args = parse_args()
    data = load_firebase_export(args.input.resolve())
    report = asyncio.run(build_report(data))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
