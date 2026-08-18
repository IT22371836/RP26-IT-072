"""Migrate the remaining MongoDB application state into Firebase RTDB.

The operation is additive: existing Firebase leaf values are preserved. Run a
dry-run and backup before ``--apply``. Password hashes are intentionally
excluded because Firebase Authentication is the only authentication store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient

from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient

COLLECTIONS = {
    "core/users": ("users", "user_id"),
    "core/customer_profiles": ("customer_profiles", "customer_id"),
    "core/provider_verification_events": ("provider_verification_events", "event_id"),
    "component1/service_requests": ("service_requests", "request_id"),
    "component1/interactions": ("interactions", "interaction_id"),
    "component1/runs": ("component1_runs", "run_id"),
    "component1/provider_scores": ("component1_provider_scores", None),
    "component4/runs": ("component4_runs", "run_id"),
    "component4/provider_scores": ("component4_provider_scores", None),
    "pipeline/runs": ("pipeline_runs", "run_id"),
    "pipeline/workers": ("pipeline_workers", "worker_id"),
}
SENSITIVE_FIELDS = {"hashed_password", "password", "password_hash"}
# Research roots are structurally outside every generated target path. Only
# the adjacent runtime nodes are downloaded and compared before/after apply.
UNTOUCHED_ROOTS = {"daily_demand", "filter_requests"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--mongo-uri")
    parser.add_argument("--mongo-database")
    args = parser.parse_args()
    if args.resume and not args.apply:
        parser.error("--resume is only valid with --apply")
    if args.apply and args.backup_dir is None:
        parser.error("--apply requires --backup-dir")
    return args


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): json_value(item)
            for key, item in value.items()
            if key != "_id" and key not in SENSITIVE_FIELDS and item is not None
        }
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def record_key(collection: str, key_field: str | None, document: dict[str, Any]) -> str:
    if key_field and document.get(key_field):
        return str(document[key_field])
    if collection in {"component1_provider_scores", "component4_provider_scores"}:
        run_id = document.get("run_id", "unknown-run")
        provider_id = document.get("provider_id", "unknown-provider")
        return f"{run_id}__{provider_id}"
    return str(document["_id"])


def email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def merge_missing(existing: Any, desired: Any, path: str, report: dict[str, Any]) -> Any:
    if not isinstance(desired, dict):
        # RTDB represents empty arrays as an absent node. Treat the two states
        # as equivalent; application schemas restore their default empty list.
        if existing is None and desired == []:
            report["unchanged_leaf_values"] += 1
            return None
        if existing is None:
            report["missing_leaf_values"] += 1
            if len(report["missing_paths"]) < 500:
                report["missing_paths"].append(path)
            return deepcopy(desired)
        if existing == desired:
            report["unchanged_leaf_values"] += 1
        else:
            report["conflicting_leaf_values_preserved"] += 1
            if len(report["conflict_paths"]) < 500:
                report["conflict_paths"].append(path)
        return deepcopy(existing)
    current = deepcopy(existing) if isinstance(existing, dict) else {}
    if existing is not None and not isinstance(existing, dict):
        report["conflicting_leaf_values_preserved"] += 1
        if len(report["conflict_paths"]) < 500:
            report["conflict_paths"].append(path)
        return deepcopy(existing)
    for key, value in desired.items():
        child = f"{path}/{key}" if path else key
        current[key] = merge_missing(current.get(key), value, child, report)
    return current


def new_metrics() -> dict[str, Any]:
    return {
        "missing_leaf_values": 0,
        "missing_paths": [],
        "unchanged_leaf_values": 0,
        "conflicting_leaf_values_preserved": 0,
        "conflict_paths": [],
    }


def build_desired(database: Any) -> tuple[dict[str, Any], dict[str, int]]:
    desired: dict[str, Any] = {}
    counts: dict[str, int] = {}
    users_by_id: dict[str, dict[str, Any]] = {}

    for target, (collection, key_field) in COLLECTIONS.items():
        records: dict[str, Any] = {}
        for source in database[collection].find({}):
            key = record_key(collection, key_field, source)
            converted = json_value(source)
            records[key] = converted
            if collection == "users":
                users_by_id[key] = converted
        desired[target] = records
        counts[target] = len(records)

    providers: dict[str, Any] = {}
    for source in database["providers"].find({}):
        provider_id = str(source["provider_id"])
        converted = json_value(source)
        providers[provider_id] = converted
        user_id = str(source.get("user_id") or "")
        user = users_by_id.get(user_id)
        if (
            user is not None
            and not user.get("legacy", {}).get("firebase_uid")
            and provider_id.startswith("P")
        ):
            user.setdefault("legacy", {})["firebase_uid"] = provider_id
            user["auth_source"] = "firebase"
    desired["providers"] = providers
    counts["providers"] = len(providers)

    indexes: dict[str, Any] = {
        "users_by_email": {},
        "users_by_firebase_uid": {},
        "customer_profiles_by_user": {},
        "providers_by_user": {},
    }
    for user_id, user in users_by_id.items():
        email = str(user.get("email") or "").strip().lower()
        if email:
            indexes["users_by_email"][email_key(email)] = user_id
        uid = user.get("legacy", {}).get("firebase_uid")
        if uid:
            indexes["users_by_firebase_uid"][str(uid)] = user_id
    for customer_id, profile in desired["core/customer_profiles"].items():
        if profile.get("user_id"):
            indexes["customer_profiles_by_user"][str(profile["user_id"])] = customer_id
    for provider_id, profile in providers.items():
        if profile.get("user_id"):
            indexes["providers_by_user"][str(profile["user_id"])] = provider_id
    desired["core/indexes"] = indexes
    counts["core/indexes"] = sum(len(value) for value in indexes.values())

    desired["customers"] = {}
    counts["customers_additive_profiles"] = 0
    return desired, counts


def enrich_identity_links(
    desired: dict[str, Any],
    counts: dict[str, int],
    firebase_customers: Any,
    firebase_providers: Any,
) -> list[str]:
    """Link internal users only when a Firebase profile email is unique."""

    email_matches: dict[str, list[str]] = {}
    for profiles in (firebase_customers, firebase_providers):
        if not isinstance(profiles, dict):
            continue
        for uid, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            email = str(profile.get("email") or "").strip().lower()
            if email:
                email_matches.setdefault(email, []).append(str(uid))

    ambiguous: list[str] = []
    users = desired["core/users"]
    uid_index = desired["core/indexes"]["users_by_firebase_uid"]
    for user_id, user in users.items():
        if user.get("legacy", {}).get("firebase_uid"):
            continue
        email = str(user.get("email") or "").strip().lower()
        matches = sorted(set(email_matches.get(email, [])))
        if len(matches) == 1:
            uid = matches[0]
            user.setdefault("legacy", {})["firebase_uid"] = uid
            user["auth_source"] = "firebase"
            uid_index[uid] = user_id
        elif len(matches) > 1:
            ambiguous.append(email)

    customers: dict[str, Any] = {}
    for profile in desired["core/customer_profiles"].values():
        user = users.get(str(profile.get("user_id") or ""), {})
        uid = user.get("legacy", {}).get("firebase_uid")
        if uid:
            customers[str(uid)] = {
                "internalUserId": profile.get("user_id"),
                "internalCustomerId": profile.get("customer_id"),
                "phone": profile.get("phone"),
                "district": profile.get("district"),
                "city": profile.get("city"),
                "preferredLanguage": profile.get("preferred_language"),
                "location": profile.get("location"),
                "customerImage": profile.get("customer_image"),
            }
    desired["customers"] = json_value(customers)
    counts["customers_additive_profiles"] = len(customers)
    counts["core/indexes"] = sum(
        len(value) for value in desired["core/indexes"].values()
    )
    return ambiguous


def get_path(client: FirebaseRtdbClient, path: str) -> Any:
    return client._reference(path).get()


def set_report(path: Path | None, report: dict[str, Any]) -> None:
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    print(output, end="")


def main() -> int:
    args = parse_args()
    settings = get_settings()
    mongo_uri = args.mongo_uri or getattr(settings, "mongodb_uri", None)
    mongo_database = args.mongo_database or getattr(settings, "mongodb_database", None)
    if not mongo_uri or not mongo_database:
        # Mongo settings were removed from runtime Settings; migration uses the
        # old variables directly from the environment/.env when present.
        import os

        mongo_uri = mongo_uri or os.getenv("MONGODB_URI")
        mongo_database = mongo_database or os.getenv("MONGODB_DATABASE")
        if not mongo_uri and Path(".env").is_file():
            values = {}
            for line in Path(".env").read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
            mongo_uri = mongo_uri or values.get("MONGODB_URI")
            mongo_database = mongo_database or values.get("MONGODB_DATABASE")
    if not mongo_uri or not mongo_database:
        raise SystemExit("--mongo-uri and --mongo-database (or legacy .env values) are required")

    mongo = MongoClient(mongo_uri, serverSelectionTimeoutMS=30_000)
    try:
        mongo.admin.command("ping")
        desired, counts = build_desired(mongo[mongo_database])
    finally:
        mongo.close()

    firebase = FirebaseRtdbClient(settings)
    firebase_customers = get_path(firebase, "customers")
    firebase_providers = get_path(firebase, "providers")
    ambiguous_identity_emails = enrich_identity_links(
        desired, counts, firebase_customers, firebase_providers
    )
    untouched_before = {root: get_path(firebase, root) for root in sorted(UNTOUCHED_ROOTS)}
    existing = {
        path: (
            firebase_customers
            if path == "customers"
            else firebase_providers
            if path == "providers"
            else get_path(firebase, path)
        )
        for path in desired
    }
    metrics = new_metrics()
    merged = {
        path: merge_missing(existing.get(path), value, path, metrics)
        for path, value in desired.items()
    }
    report = {
        "mode": "apply" if args.apply else "verify-only" if args.verify_only else "dry-run",
        "source_database": mongo_database,
        "record_counts": counts,
        **metrics,
        "sensitive_fields_exported": False,
        "ambiguous_identity_emails": ambiguous_identity_emails,
        "component2_untouched": True,
        "applied": False,
        "verified": metrics["missing_leaf_values"] == 0,
    }

    if args.backup_dir:
        args.backup_dir.mkdir(parents=True, exist_ok=True)
        (args.backup_dir / "firebase-targets-before.json").write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (args.backup_dir / "mongo-export-sanitized.json").write_text(
            json.dumps(desired, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if args.apply:
        for path in merged:
            reference = firebase._reference(path)
            desired_value = desired[path]

            def additive_transaction(
                current: Any, *, target: Any = desired_value, target_path: str = path
            ) -> Any:
                transaction_metrics = new_metrics()
                return merge_missing(current, target, target_path, transaction_metrics)

            reference.transaction(additive_transaction)
        after = {path: get_path(firebase, path) for path in desired}
        verify_metrics = new_metrics()
        for path, value in desired.items():
            merge_missing(after.get(path), value, path, verify_metrics)
        untouched_after = {root: get_path(firebase, root) for root in sorted(UNTOUCHED_ROOTS)}
        report.update(
            {
                "applied": True,
                "verified": verify_metrics["missing_leaf_values"] == 0,
                "remaining_missing_leaf_values": verify_metrics["missing_leaf_values"],
                "post_apply_conflicts_preserved": verify_metrics[
                    "conflicting_leaf_values_preserved"
                ],
                "component2_untouched": untouched_before == untouched_after,
            }
        )

    set_report(args.report, report)
    if args.dry_run:
        return 0
    return 0 if report["verified"] and report["component2_untouched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
