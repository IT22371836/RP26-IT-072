"""Generate privacy-safe Phase 0 evidence from Firebase and MongoDB backups.

The reports contain collection/node names, counts, field paths, value-shape counts,
and backup hashes. They never contain source record values or connection strings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from app.core.config import REPOSITORY_DIR, get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firebase-export", type=Path, required=True)
    parser.add_argument("--mongo-backup", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str) and value == "":
        return "empty_string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "scalar"


def walk_value(value: Any, path: str, counts: dict[str, Counter[str]]) -> None:
    counts.setdefault(path, Counter())[value_kind(value)] += 1
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            walk_value(child, child_path, counts)
    elif isinstance(value, list):
        item_path = f"{path}[]"
        for child in value:
            walk_value(child, item_path, counts)


def analyze_records(records: Iterable[dict[str, Any]]) -> tuple[int, list[str], dict[str, Any]]:
    aggregate: dict[str, Counter[str]] = {}
    present_records: Counter[str] = Counter()
    record_count = 0
    for record in records:
        record_count += 1
        local: dict[str, Counter[str]] = {}
        for key, value in record.items():
            walk_value(value, str(key), local)
        for path, counts in local.items():
            present_records[path] += 1
            aggregate.setdefault(path, Counter()).update(counts)

    stats: dict[str, Any] = {}
    for path in sorted(aggregate):
        counts = aggregate[path]
        stats[path] = {
            "present_records": present_records[path],
            "missing_records": record_count - present_records[path],
            "null_values": counts["null"],
            "empty_string_values": counts["empty_string"],
            "object_values": counts["object"],
            "array_values": counts["array"],
            "scalar_values": counts["scalar"],
        }
    return record_count, sorted(aggregate), stats


def read_project_id() -> str:
    env_path = REPOSITORY_DIR / "WEB" / ".env"
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        if raw_line.lstrip().startswith("VITE_FIREBASE_PROJECT_ID="):
            return raw_line.split("=", 1)[1].strip().strip("\"'")
    return "not-configured"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    firebase_export = args.firebase_export.resolve(strict=True)
    mongo_backup = args.mongo_backup.resolve(strict=True)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    firebase_data = json.loads(firebase_export.read_text(encoding="utf-8"))
    if not isinstance(firebase_data, dict):
        raise ValueError("Firebase export must be a top-level object")

    counts: dict[str, Any] = {"firebase": {}, "mongodb": {}}
    paths: dict[str, Any] = {"firebase": {}, "mongodb": {}}
    shapes: dict[str, Any] = {"firebase": {}, "mongodb": {}}

    for node, keyed_records in sorted(firebase_data.items()):
        if not isinstance(keyed_records, dict):
            raise ValueError(f"Firebase node {node!r} must contain keyed records")
        record_values = list(keyed_records.values())
        if not all(isinstance(record, dict) for record in record_values):
            raise ValueError(f"Firebase node {node!r} contains a non-object record")
        record_count, field_paths, value_shapes = analyze_records(record_values)
        counts["firebase"][node] = record_count
        paths["firebase"][node] = field_paths
        shapes["firebase"][node] = value_shapes

    settings = get_settings()
    client = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        client.admin.command("ping")
        database = client[settings.mongodb_database]
        for collection_name in sorted(database.list_collection_names()):
            collection = database[collection_name]
            documents = collection.find({})
            record_count, field_paths, value_shapes = analyze_records(documents)
            counts["mongodb"][collection_name] = record_count
            paths["mongodb"][collection_name] = field_paths
            shapes["mongodb"][collection_name] = value_shapes
    finally:
        client.close()

    generated_at = datetime.now(UTC).isoformat()
    context = {
        "generated_at": generated_at,
        "git_branch": subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPOSITORY_DIR,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "firebase_project_id": read_project_id(),
        "mongodb_database": settings.mongodb_database,
        "raw_personal_data_in_evidence": False,
        "backup_location": str(firebase_export.parent),
    }
    hashes = {
        "generated_at": generated_at,
        "firebase_rtdb_export": {
            "file": firebase_export.name,
            "bytes": firebase_export.stat().st_size,
            "sha256": sha256_file(firebase_export),
        },
        "mongodb_mongodump": {
            "file": mongo_backup.name,
            "bytes": mongo_backup.stat().st_size,
            "sha256": sha256_file(mongo_backup),
        },
    }

    write_json(output_dir / "baseline-context.json", context)
    write_json(output_dir / "baseline-counts.json", counts)
    write_json(output_dir / "baseline-field-paths.json", paths)
    write_json(output_dir / "baseline-value-shapes.json", shapes)
    write_json(output_dir / "baseline-hashes.json", hashes)
    print(
        json.dumps(
            {
                "firebase_records": sum(counts["firebase"].values()),
                "mongodb_documents": sum(counts["mongodb"].values()),
                "output_dir": str(output_dir),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
