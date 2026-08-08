from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.migrations.identity_linking import IdentityUserLookup, resolve_identity_mapping
from app.repositories.legacy_firebase import (
    LEGACY_COLLECTIONS,
    MIGRATION_VERSION,
    LegacyFirebaseRepository,
)
from app.schemas.common import utc_now


class FirebaseExportError(ValueError):
    """The supplied RTDB export is not safe to migrate."""


def load_firebase_export(path: Path) -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FirebaseExportError(f"Could not read Firebase export {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise FirebaseExportError("Firebase export must be a top-level JSON object")

    unexpected = sorted(set(raw) - set(LEGACY_COLLECTIONS))
    if unexpected:
        raise FirebaseExportError(
            "Unsupported top-level Firebase nodes: " + ", ".join(unexpected)
        )

    normalized: dict[str, dict[str, Any]] = {}
    for node, records in raw.items():
        if records is None:
            normalized[node] = {}
            continue
        if not isinstance(records, dict):
            raise FirebaseExportError(f"Firebase node {node!r} must contain keyed records")
        invalid_keys = [key for key, record in records.items() if not isinstance(record, dict)]
        if invalid_keys:
            sample = ", ".join(str(key) for key in invalid_keys[:5])
            raise FirebaseExportError(
                f"Firebase node {node!r} contains non-object records: {sample}"
            )
        normalized[node] = records
    return normalized


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def source_sha256(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(record)).hexdigest()


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def iter_field_values(value: Any, path: str) -> Iterable[tuple[str, Any]]:
    """Yield dotted leaf paths while representing every array position as ``[]``."""

    if isinstance(value, dict):
        if not value:
            yield path, value
            return
        for key in sorted(value):
            child_path = f"{path}.{key}" if path else str(key)
            yield from iter_field_values(value[key], child_path)
        return

    if isinstance(value, list):
        array_path = f"{path}[]"
        if not value:
            yield array_path, value
            return
        for item in value:
            yield from iter_field_values(item, array_path)
        return

    yield path, value


def inventory_export(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    total_records = 0
    for node in sorted(data):
        records = data[node]
        total_records += len(records)
        type_counts: dict[str, Counter[str]] = {}
        for record in records.values():
            for path, value in iter_field_values(record, f"{node}.{{record}}"):
                type_counts.setdefault(path, Counter())[value_type(value)] += 1
        nodes[node] = {
            "record_count": len(records),
            "field_paths": sorted(type_counts),
            "field_type_counts": {
                path: dict(sorted(counts.items())) for path, counts in sorted(type_counts.items())
            },
        }
    return {"total_records": total_records, "nodes": nodes}


def build_snapshot(source_node: str, source_key: str, record: dict[str, Any]) -> dict[str, Any]:
    if source_node not in LEGACY_COLLECTIONS:
        raise FirebaseExportError(f"Unsupported Firebase node: {source_node}")
    return {
        "source_system": "firebase_rtdb",
        "source_node": source_node,
        "source_key": source_key,
        "source_record": deepcopy(record),
        "source_sha256": source_sha256(record),
        "migration_version": MIGRATION_VERSION,
    }


def new_report(mode: str, data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inventory = inventory_export(data)
    return {
        "migration_version": MIGRATION_VERSION,
        "mode": mode,
        "generated_at": utc_now().isoformat(),
        "inventory": inventory,
        "summary": {
            "expected": inventory["total_records"],
            "planned": inventory["total_records"] if mode == "dry-run" else 0,
            "inserted": 0,
            "unchanged": 0,
            "conflicts": 0,
            "verified": 0,
            "missing": 0,
            "mismatched": 0,
            "failed": 0,
            "identity_expected": len(data.get("customers", {}))
            + len(data.get("providers", {})),
            "identity_inserted": 0,
            "identity_unchanged": 0,
            "identity_conflicts": 0,
            "identity_matched": 0,
            "identity_ambiguous": 0,
            "identity_unmatched": 0,
        },
        "issues": [],
    }


async def apply_snapshots(
    repository: LegacyFirebaseRepository,
    data: dict[str, dict[str, Any]],
    user_lookup: IdentityUserLookup | None = None,
) -> dict[str, Any]:
    report = new_report("apply", data)
    await repository.ensure_indexes()
    identity_candidates: list[tuple[str, str, dict[str, Any]]] = []
    for node in sorted(data):
        for source_key in sorted(data[node]):
            snapshot = build_snapshot(node, source_key, data[node][source_key])
            try:
                status = await repository.store_snapshot(snapshot)
            except Exception as exc:  # the report must identify every failed source key
                report["summary"]["failed"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "failed",
                        "error": type(exc).__name__,
                    }
                )
                continue
            if status == "conflict":
                report["summary"]["conflicts"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "conflict",
                    }
                )
            else:
                report["summary"][status] += 1
                if user_lookup is not None and node in {"customers", "providers"}:
                    identity_candidates.append((node, source_key, data[node][source_key]))

    if user_lookup is not None:
        for node, source_key, record in identity_candidates:
            try:
                mapping = await resolve_identity_mapping(
                    user_lookup,
                    node,
                    source_key,
                    record,
                )
                status = await repository.store_identity_mapping(mapping)
            except Exception as exc:
                report["summary"]["failed"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "identity_failed",
                        "error": type(exc).__name__,
                    }
                )
                continue

            report["summary"][f"identity_{mapping['match_status']}"] += 1
            if status == "conflict":
                report["summary"]["conflicts"] += 1
                report["summary"]["identity_conflicts"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "identity_conflict",
                    }
                )
            else:
                report["summary"][f"identity_{status}"] += 1
    return report


async def verify_snapshots(
    repository: LegacyFirebaseRepository,
    data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    report = new_report("verify-only", data)
    for node in sorted(data):
        for source_key in sorted(data[node]):
            expected = build_snapshot(node, source_key, data[node][source_key])
            try:
                existing = await repository.find_snapshot(node, source_key)
            except Exception as exc:
                report["summary"]["failed"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "failed",
                        "error": type(exc).__name__,
                    }
                )
                continue
            if existing is None:
                report["summary"]["missing"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "missing",
                    }
                )
            elif (
                existing.get("source_record") != expected["source_record"]
                or existing.get("source_sha256") != expected["source_sha256"]
                or existing.get("migration_version") != MIGRATION_VERSION
            ):
                report["summary"]["mismatched"] += 1
                report["issues"].append(
                    {
                        "source_node": node,
                        "source_key": source_key,
                        "status": "mismatched",
                    }
                )
            else:
                report["summary"]["verified"] += 1
    return report


def report_has_failures(report: dict[str, Any]) -> bool:
    summary = report["summary"]
    return any(summary[key] for key in ("conflicts", "missing", "mismatched", "failed"))


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
