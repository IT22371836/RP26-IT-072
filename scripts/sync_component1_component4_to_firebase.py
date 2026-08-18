"""Add scoped MongoDB data to Firebase RTDB without touching existing app data.

The migration is additive: existing Firebase values are never overwritten.  A
dry run is the default; pass ``--apply`` to issue one conditional multi-path
PATCH guarded by the Firebase root ETag captured during planning.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bson import ObjectId
from pymongo import MongoClient


COMPONENT_COLLECTIONS = {
    "component1": {
        "providers": ("providers", "provider_id"),
        "service_requests": ("service_requests", "request_id"),
        "interactions": ("interactions", "interaction_id"),
    },
    "component4": {
        "provider_scores": ("component4_provider_scores", None),
        "runs": ("component4_runs", "run_id"),
    },
    "core": {
        "users": ("users", "user_id"),
        "customer_profiles": ("customer_profiles", "customer_id"),
        "provider_verification_events": ("provider_verification_events", None),
    },
}
PROTECTED_ROOTS = {"customers", "daily_demand", "filter_requests", "providers"}
SENSITIVE_FIELDS = {"hashed_password"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--firebase-url")
    parser.add_argument("--mongo-uri")
    parser.add_argument("--mongo-database")
    return parser.parse_args()


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): converted
            for key, item in value.items()
            if key != "_id"
            and key not in SENSITIVE_FIELDS
            and (converted := json_value(item)) is not None
        }
    if isinstance(value, (list, tuple)):
        return [converted for item in value if (converted := json_value(item)) is not None]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if value is None:
        return None  # RTDB treats null as deletion, so callers omit it.
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def document_key(collection: str, key_field: str | None, document: dict[str, Any]) -> str:
    if key_field and document.get(key_field):
        return str(document[key_field])
    if collection == "component4_provider_scores":
        run_id = document.get("run_id", "unknown-run")
        provider_id = document.get("provider_id", "unknown-provider")
        return f"{run_id}__{provider_id}"
    return str(document["_id"])


def export_mongo(database: Any) -> dict[str, Any]:
    exported: dict[str, Any] = {}
    for component, collections in COMPONENT_COLLECTIONS.items():
        exported[component] = {}
        for firebase_name, (mongo_name, key_field) in collections.items():
            records: dict[str, Any] = {}
            for document in database[mongo_name].find({}):
                key = document_key(mongo_name, key_field, document)
                records[key] = json_value(document)
            exported[component][firebase_name] = records
    return exported


def request_json(url: str, method: str = "GET", body: Any = None, etag: str | None = None):
    headers = {"Accept": "application/json"}
    if method == "GET":
        headers["X-Firebase-ETag"] = "true"
    if etag:
        headers["if-match"] = etag
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method=method)
    with urlopen(request, timeout=60) as response:
        parsed = json.loads(response.read().decode("utf-8"))
        return parsed, response.headers.get("ETag")


def plan_missing(existing: Any, desired: Any, path: str = "") -> tuple[dict[str, Any], list[str], list[str]]:
    updates: dict[str, Any] = {}
    unchanged: list[str] = []
    conflicts: list[str] = []
    if isinstance(desired, dict):
        current = existing if isinstance(existing, dict) else {}
        if existing is not None and not isinstance(existing, dict):
            return updates, unchanged, [path]
        for key, value in desired.items():
            child = f"{path}/{key}" if path else key
            child_updates, child_unchanged, child_conflicts = plan_missing(
                current.get(key), value, child
            )
            updates.update(child_updates)
            unchanged.extend(child_unchanged)
            conflicts.extend(child_conflicts)
        return updates, unchanged, conflicts
    if existing is None:
        if desired is not None:
            updates[path] = desired
    elif existing == desired:
        unchanged.append(path)
    else:
        conflicts.append(path)
    return updates, unchanged, conflicts


def merge_missing(existing: Any, desired: Any) -> Any:
    """Return a copy with absent dictionary members added and present values preserved."""
    if not isinstance(desired, dict):
        return deepcopy(desired) if existing is None else deepcopy(existing)
    merged = deepcopy(existing) if isinstance(existing, dict) else {}
    for key, value in desired.items():
        merged[key] = merge_missing(merged.get(key), value)
    return merged


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    backend_env = read_env(root / "packages" / "backend" / ".env")
    web_env = read_env(root / "WEB" / ".env")
    mongo_uri = args.mongo_uri or os.getenv("MONGODB_URI") or backend_env.get("MONGODB_URI")
    mongo_database = (
        args.mongo_database
        or os.getenv("MONGODB_DATABASE")
        or backend_env.get("MONGODB_DATABASE")
    )
    firebase_url = (
        args.firebase_url
        or os.getenv("VITE_FIREBASE_DATABASE_URL")
        or web_env.get("VITE_FIREBASE_DATABASE_URL")
    )
    if not mongo_uri or not mongo_database or not firebase_url:
        raise SystemExit("MongoDB URI/database and Firebase database URL are required")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=30_000)
    try:
        client.admin.command("ping")
        desired = export_mongo(client[mongo_database])
    finally:
        client.close()

    firebase_endpoint = firebase_url.rstrip("/") + "/.json"
    existing, etag = request_json(firebase_endpoint)
    if not isinstance(existing, dict) or not etag:
        raise SystemExit("Firebase root response or ETag is invalid")
    protected_before = {name: existing.get(name) for name in PROTECTED_ROOTS}
    scoped_existing = {name: existing.get(name) for name in COMPONENT_COLLECTIONS}
    updates, unchanged, conflicts = plan_missing(scoped_existing, desired)
    if any(path.split("/", 1)[0] not in COMPONENT_COLLECTIONS for path in updates):
        raise SystemExit("Planner attempted to leave the Component 1/4 namespaces")

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "mongo_database": mongo_database,
        "firebase_roots_before": sorted(existing),
        "protected_roots": sorted(PROTECTED_ROOTS),
        "record_counts": {
            f"{component}/{collection}": len(records)
            for component, collections in desired.items()
            for collection, records in collections.items()
        },
        "planned_leaf_updates": len(updates),
        "unchanged_leaf_values": len(unchanged),
        "conflicting_leaf_values_preserved": len(conflicts),
        "conflict_paths": sorted(conflicts),
        "applied": False,
        "protected_roots_unchanged": True,
    }

    if args.backup_dir:
        args.backup_dir.mkdir(parents=True, exist_ok=True)
        (args.backup_dir / "firebase-before.json").write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (args.backup_dir / "mongo-component1-component4.json").write_text(
            json.dumps(desired, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if args.apply and updates:
        try:
            for component, component_desired in desired.items():
                component_endpoint = firebase_url.rstrip("/") + f"/{component}.json"
                component_existing, component_etag = request_json(component_endpoint)
                if not component_etag:
                    raise SystemExit(f"Firebase ETag missing for {component}")
                component_merged = merge_missing(component_existing, component_desired)
                if component_merged != component_existing:
                    request_json(
                        component_endpoint,
                        method="PUT",
                        body=component_merged,
                        etag=component_etag,
                    )
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SystemExit(f"Firebase conditional PUT failed ({error.code}): {detail}")
        verified, _ = request_json(firebase_endpoint)
        protected_after = {name: verified.get(name) for name in PROTECTED_ROOTS}
        report["protected_roots_unchanged"] = protected_after == protected_before
        verify_updates, _, verify_conflicts = plan_missing(
            {name: verified.get(name) for name in COMPONENT_COLLECTIONS}, desired
        )
        report["remaining_missing_leaf_values"] = len(verify_updates)
        report["post_apply_conflicts"] = sorted(verify_conflicts)
        report["applied"] = not verify_updates and protected_after == protected_before

    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if not args.apply or report["applied"] or not updates else 1


if __name__ == "__main__":
    sys.exit(main())
