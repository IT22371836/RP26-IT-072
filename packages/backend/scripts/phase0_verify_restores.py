"""Verify Phase 0 Firebase and MongoDB restores without exposing record values."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from app.core.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firebase-source", type=Path, required=True)
    parser.add_argument("--firebase-restored", type=Path, required=True)
    parser.add_argument("--baseline-counts", type=Path, required=True)
    parser.add_argument("--mongo-restore-database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_indexes(collection: Any) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, details in collection.index_information().items():
        normalized[name] = {
            "key": [list(item) for item in details["key"]],
            "unique": bool(details.get("unique", False)),
            "sparse": bool(details.get("sparse", False)),
        }
    return normalized


def main() -> int:
    args = parse_args()
    firebase_source = json.loads(args.firebase_source.read_text(encoding="utf-8"))
    firebase_restored = json.loads(args.firebase_restored.read_text(encoding="utf-8"))
    baseline_counts = json.loads(args.baseline_counts.read_text(encoding="utf-8"))

    firebase_expected_counts = baseline_counts["firebase"]
    firebase_actual_counts = {
        node: len(records) for node, records in sorted(firebase_restored.items())
    }
    firebase_match = firebase_source == firebase_restored

    settings = get_settings()
    client = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    mongo_results: dict[str, Any] = {}
    try:
        client.admin.command("ping")
        source_database = client[settings.mongodb_database]
        restored_database = client[args.mongo_restore_database]
        source_collections = set(source_database.list_collection_names())
        restored_collections = set(restored_database.list_collection_names())
        expected_collections = set(baseline_counts["mongodb"])
        all_collections = sorted(expected_collections | restored_collections)
        for collection_name in all_collections:
            expected_count = baseline_counts["mongodb"].get(collection_name)
            actual_count = restored_database[collection_name].count_documents({})
            source_indexes = (
                normalize_indexes(source_database[collection_name])
                if collection_name in source_collections
                else {}
            )
            restored_indexes = (
                normalize_indexes(restored_database[collection_name])
                if collection_name in restored_collections
                else {}
            )
            mongo_results[collection_name] = {
                "expected_count": expected_count,
                "restored_count": actual_count,
                "count_match": expected_count == actual_count,
                "indexes_match": source_indexes == restored_indexes,
                "restored_index_names": sorted(restored_indexes),
            }
    finally:
        client.close()

    mongo_passed = all(
        result["count_match"] and result["indexes_match"]
        for result in mongo_results.values()
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "firebase": {
            "target": "local RTDB emulator namespace demo-weda-phase0",
            "exact_json_match": firebase_match,
            "expected_counts": firebase_expected_counts,
            "restored_counts": firebase_actual_counts,
            "counts_match": firebase_expected_counts == firebase_actual_counts,
            "source_canonical_sha256": canonical_sha256(firebase_source),
            "restored_canonical_sha256": canonical_sha256(firebase_restored),
        },
        "mongodb": {
            "target_database": args.mongo_restore_database,
            "collections": mongo_results,
            "passed": mongo_passed,
        },
        "source_databases_modified": False,
        "passed": firebase_match
        and firebase_expected_counts == firebase_actual_counts
        and mongo_passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
