"""Resumable, collision-safe research provider import for Components 1, 2, and 4."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from firebase_admin import auth, credentials, db, initialize_app
from pymongo import AsyncMongoClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.services.provider_eligibility import (
    RESEARCH_PIPELINE_TARGET,
    RESEARCH_SELECTION_VERSION,
    select_research_baseline,
)

ROOT = Path(__file__).resolve().parents[3]
C1_PROVIDERS = ROOT / "packages/backend/app/components/component1/artifacts/providers.json"
C4_SCORES = ROOT / "ml/components/component4/artifacts/catf-v1/provider_catf_scores.csv"
C4_PROVIDER_MAP = ROOT / "ml/components/component4/data/processed/provider_id_map.csv"
SEED_VERSION = "pipeline-shared-providers-v3"
DEFAULT_PROVIDER_IMAGE = (
    "https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/"
    "providers%2Fprovider_default.png?alt=media"
)
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DISTRICT_CENTROIDS = {
    "Colombo": (6.9271, 79.8612), "Gampaha": (7.0840, 79.9925),
    "Kalutara": (6.5854, 79.9607), "Kandy": (7.2906, 80.6337),
    "Matale": (7.4675, 80.6234), "Nuwara Eliya": (6.9497, 80.7891),
    "Galle": (6.0535, 80.2210), "Matara": (5.9549, 80.5550),
    "Hambantota": (6.1248, 81.1185), "Jaffna": (9.6615, 80.0255),
    "Kilinochchi": (9.3803, 80.3992), "Mannar": (8.9810, 79.9044),
    "Vavuniya": (8.7542, 80.4982), "Mullaitivu": (9.2671, 80.8142),
    "Batticaloa": (7.7170, 81.7000), "Ampara": (7.2912, 81.6724),
    "Trincomalee": (8.5874, 81.2152), "Kurunegala": (7.4863, 80.3647),
    "Puttalam": (8.0362, 79.8283), "Anuradhapura": (8.3114, 80.4037),
    "Polonnaruwa": (7.9403, 81.0188), "Badulla": (6.9934, 81.0550),
    "Monaragala": (6.8728, 81.3507), "Ratnapura": (6.6828, 80.3992),
    "Kegalle": (7.2513, 80.3464),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--category")
    parser.add_argument(
        "--research-pipeline-target", type=int, default=RESEARCH_PIPELINE_TARGET
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_lfs_pointer(path: Path) -> None:
    with path.open("rb") as source:
        if source.read(80).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError(f"Required artifact is still a Git LFS pointer: {path}")


def canonical_user_id(provider_id: str) -> str:
    return "U" + provider_id[1:]


def research_email(provider_id: str, provider_name: Any) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", str(provider_name or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "", ascii_name) or "provider"
    return f"{slug}12.{provider_id.lower()}@gmail.com"


def coordinates(provider: dict[str, Any]) -> tuple[float, float, str]:
    base = DISTRICT_CENTROIDS.get(provider["district"], DISTRICT_CENTROIDS["Colombo"])
    digest = hashlib.sha256(
        f"{SEED_VERSION}:{provider['city']}:{provider['provider_id']}".encode()
    ).digest()
    angle = int.from_bytes(digest[:4], "big") / (2**32) * 2 * math.pi
    radius = 0.005 + int.from_bytes(digest[4:6], "big") / 65535 * 0.025
    return (
        round(base[0] + math.sin(angle) * radius, 6),
        round(base[1] + math.cos(angle) * radius, 6),
        "district_centroid_provider_id_jitter",
    )


def load_population(category: str | None, limit: int | None) -> list[dict[str, Any]]:
    reject_lfs_pointer(C1_PROVIDERS)
    reject_lfs_pointer(C4_SCORES)
    reject_lfs_pointer(C4_PROVIDER_MAP)
    c1 = json.loads(C1_PROVIDERS.read_text(encoding="utf-8"))
    with C4_PROVIDER_MAP.open(encoding="utf-8", newline="") as source:
        c4_ids = {row["provider_id"] for row in csv.DictReader(source)}
    providers = [row for row in c1 if row["provider_id"] in c4_ids]
    if len(providers) != 4_998:
        raise RuntimeError(f"Expected exact C1/C4 intersection of 4,998, found {len(providers)}")
    counts = Counter(row["category"] for row in providers)
    if len(counts) != 14 or set(counts.values()) != {357}:
        raise RuntimeError(f"Expected 357 providers in each of 14 categories, found {counts}")
    if category:
        providers = [row for row in providers if row["category"].casefold() == category.casefold()]
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive")
        providers = providers[:limit]
    return providers


def provider_documents(
    provider: dict[str, Any], import_id: str, password: str | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    provider_id = provider["provider_id"]
    user_id = canonical_user_id(provider_id)
    email = research_email(provider_id, provider["provider_name"])
    latitude, longitude, coordinate_source = coordinates(provider)
    now = datetime.now(UTC)
    seed = {
        "version": SEED_VERSION,
        "importId": import_id,
        "researchSeed": True,
        "coordinateSource": coordinate_source,
        "workingHoursSource": "research_default_0800_1800_daily",
        "derivedFieldSources": {
            "nic": "synthetic_research_identifier",
            "phone": "synthetic_non_dialable_research_contact",
            "preferredLanguage": "research_default_sinhala_english",
            "providerImage": "project_default_provider_image",
        },
    }
    working_hours = {
        day: {"isOpen": True, "start": "08:00 AM", "end": "06:00 PM"} for day in DAYS
    }
    mongo_user = {
        "user_id": user_id,
        "email": email,
        "hashed_password": hash_password(password) if password else "DRY_RUN_NOT_A_HASH",
        "full_name": provider["provider_name"],
        "role": "provider",
        "is_active": True,
        "auth_version": 1,
        "legacy": {"firebase_uid": provider_id},
        "researchSeed": True,
        "pipelineSeed": seed,
        "created_at": now,
        "updated_at": now,
    }
    mongo_provider = {
        **provider,
        "provider_id": provider_id,
        "user_id": user_id,
        "email": email,
        "skills": [item.strip() for item in provider["skills"].split(",") if item.strip()],
        "location": {"latitude": latitude, "longitude": longitude},
        "working_hours": working_hours,
        "verified": False,
        "role": "provider",
        "researchSeed": True,
        "pipelineSeed": seed,
        "created_at": now,
        "updated_at": now,
    }
    return mongo_user, mongo_provider


def rtdb_provider(
    provider: dict[str, Any],
    import_id: str,
    pipeline_eligible: bool = True,
    research_target: int = RESEARCH_PIPELINE_TARGET,
) -> dict[str, Any]:
    _, mongo = provider_documents(provider, import_id, None)
    evaluated_at = mongo["created_at"].isoformat()
    return {
        "id": mongo["provider_id"],
        "uid": mongo["provider_id"],
        "userId": mongo["user_id"],
        "email": mongo["email"],
        "fullName": mongo["provider_name"],
        "role": "provider",
        "category": mongo["category"],
        "district": mongo["district"],
        "city": mongo["city"],
        "skills": mongo["skills"],
        "description": mongo["description"],
        "experienceYears": mongo["experience_years"],
        "rating": mongo["rating"],
        "reviewCount": mongo["review_count"],
        "bookingSuccessRate": mongo["booking_success_rate"],
        "interactionCount": mongo["interaction_count"],
        "location": mongo["location"],
        "workingHours": mongo["working_hours"],
        "nic": f"RESEARCH-{mongo['provider_id']}",
        "phone": f"research-{mongo['provider_id']}",
        "preferredLanguage": "Sinhala, English",
        "providerImage": DEFAULT_PROVIDER_IMAGE,
        "verified": True,
        "verification": {
            "status": "verified",
            "mode": "research_seed_integrity",
            "last_action_by": "SYSTEM_RESEARCH_IMPORT",
            "last_action_at": evaluated_at,
            "last_reason": "C1/C2/C4 research provider integrity verified",
        },
        "profileSource": "research_seed",
        "schemaVersion": 2,
        "pipelineEligibility": {
            "version": 1,
            "eligible": pipeline_eligible,
            "verified": True,
            "c1Ready": True,
            "c2Ready": True,
            "c4Ready": True,
            "profileComplete": True,
            "relationsValid": True,
            "activeResearchBaseline": pipeline_eligible,
            "selectionVersion": RESEARCH_SELECTION_VERSION,
            "researchBaselineTarget": research_target,
            "selectionReason": (
                "balanced_research_category_location"
                if pipeline_eligible
                else "outside_balanced_research_pipeline_baseline"
            ),
            "evaluatedAt": evaluated_at,
        },
        "researchSeed": True,
        "pipelineSeed": mongo["pipelineSeed"],
        "createdAt": mongo["created_at"].isoformat(),
        "createdTimestamp": int(mongo["created_at"].timestamp() * 1000),
    }


def firebase_app(settings):
    if not settings.firebase_credentials_path or not settings.firebase_database_url:
        raise RuntimeError("FIREBASE_CREDENTIALS_PATH and FIREBASE_DATABASE_URL are required")
    return initialize_app(
        credentials.Certificate(str(settings.firebase_credentials_path)),
        {
            "projectId": settings.firebase_project_id,
            "databaseURL": settings.firebase_database_url,
        },
        name=f"research-import-{uuid4().hex}",
    )


def firebase_accounts(app: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    by_uid: dict[str, Any] = {}
    by_email: dict[str, Any] = {}
    for user in auth.list_users(app=app).iterate_all():
        by_uid[user.uid] = user
        if user.email:
            by_email[user.email.lower()] = user
    return by_uid, by_email


async def mongo_collisions(database: Any, providers: list[dict[str, Any]]) -> dict[str, list[str]]:
    provider_ids = [item["provider_id"] for item in providers]
    user_ids = [canonical_user_id(item) for item in provider_ids]
    emails = [
        research_email(item["provider_id"], item["provider_name"])
        for item in providers
    ]
    users = await database.users.find(
        {"$or": [{"user_id": {"$in": user_ids}}, {"email": {"$in": emails}}]},
        {"user_id": 1, "email": 1},
    ).to_list(length=len(providers) * 2)
    found_providers = await database.providers.find(
        {"$or": [{"provider_id": {"$in": provider_ids}}, {"user_id": {"$in": user_ids}}]},
        {"provider_id": 1, "user_id": 1},
    ).to_list(length=len(providers) * 2)
    return {
        "users": sorted(str(item.get("user_id")) for item in users),
        "providers": sorted(str(item.get("provider_id")) for item in found_providers),
    }


def save_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")


async def build_mongo_documents(
    providers: list[dict[str, Any]], import_id: str, password: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        return await asyncio.gather(
            *(
                loop.run_in_executor(
                    executor, provider_documents, provider, import_id, password
                )
                for provider in providers
            )
        )


async def build_auth_records(
    providers: list[dict[str, Any]], password: str, bcrypt_module: Any
) -> list[Any]:
    def build(provider: dict[str, Any]) -> Any:
        provider_id = provider["provider_id"]
        return auth.ImportUserRecord(
            uid=provider_id,
            email=research_email(provider_id, provider["provider_name"]),
            display_name=provider["provider_name"],
            password_hash=bcrypt_module.hashpw(
                password.encode(), bcrypt_module.gensalt(rounds=10)
            ),
            disabled=False,
        )

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=8) as executor:
        return await asyncio.gather(
            *(loop.run_in_executor(executor, build, provider) for provider in providers)
        )


async def execute(args: argparse.Namespace) -> int:
    settings = get_settings()
    full_population = load_population(None, None)
    baseline = select_research_baseline(
        full_population,
        {str(provider["provider_id"]) for provider in full_population},
        args.research_pipeline_target,
    )
    providers = full_population
    if args.category:
        providers = [
            provider
            for provider in providers
            if str(provider["category"]).casefold() == args.category.casefold()
        ]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        providers = providers[: args.limit]
    previous = (
        json.loads(args.report.read_text("utf-8"))
        if args.resume and args.report.exists()
        else {}
    )
    import_id = previous.get("import_id") or f"RSEED-{uuid4().hex[:12].upper()}"
    completed = set(previous.get("completed_stages", []))
    report: dict[str, Any] = {
        "seed_version": SEED_VERSION,
        "import_id": import_id,
        "mode": "verify-only" if args.verify_only else "apply" if args.apply else "dry-run",
        "research_baseline": {
            "target": args.research_pipeline_target,
            "selection_version": RESEARCH_SELECTION_VERSION,
            "category_quotas": baseline.category_quotas,
        },
        "scope_count": len(providers),
        "full_population": not args.category and args.limit is None,
        "category_counts": dict(sorted(Counter(item["category"] for item in providers).items())),
        "artifact_sha256": {
            "component1": sha256(C1_PROVIDERS),
            "component4_scores": sha256(C4_SCORES),
            "component4_provider_map": sha256(C4_PROVIDER_MAP),
        },
        "completed_stages": sorted(completed),
        "contains_plaintext_password": False,
    }
    client = AsyncMongoClient(settings.mongodb_uri)
    app = firebase_app(settings)
    try:
        database = client[settings.mongodb_database]
        await client.admin.command("ping")
        expected_ids = {item["provider_id"] for item in providers}
        expected_emails = {
            research_email(item["provider_id"], item["provider_name"])
            for item in providers
        }
        resume_mongo = args.resume and "mongo" in completed
        resume_auth = args.resume and "firebase_auth" in completed
        resume_rtdb = args.resume and "rtdb" in completed
        collisions = await mongo_collisions(database, providers)
        auth_by_uid, auth_by_email = await asyncio.to_thread(firebase_accounts, app)
        rtdb_root = await asyncio.to_thread(db.reference("providers", app=app).get)
        rtdb_root = rtdb_root if isinstance(rtdb_root, dict) else {}
        auth_collisions = sorted(
            expected_ids.intersection(auth_by_uid)
            | {user.uid for email, user in auth_by_email.items() if email in expected_emails}
        )
        rtdb_collisions = sorted(expected_ids.intersection(rtdb_root))
        if (
            (collisions["users"] or collisions["providers"])
            and not resume_mongo
            and not args.verify_only
        ):
            raise RuntimeError(f"Mongo identity collision: {collisions}")
        if auth_collisions and not resume_auth and not args.verify_only:
            raise RuntimeError(f"Firebase Auth UID/email collision: {auth_collisions[:20]}")
        if rtdb_collisions and not resume_rtdb and not args.verify_only:
            raise RuntimeError(f"Firebase RTDB provider collision: {rtdb_collisions[:20]}")
        completed.add("preflight")
        report["completed_stages"] = sorted(completed)
        report["preflight"] = (
            {
                "mongo_users": len(set(collisions["users"])),
                "mongo_providers": len(set(collisions["providers"])),
                "firebase_auth": len(set(auth_collisions)),
                "firebase_rtdb": len(set(rtdb_collisions)),
            }
            if args.verify_only
            else {
                "mongo": collisions,
                "auth": auth_collisions,
                "rtdb": rtdb_collisions,
            }
        )
        save_report(args.report, report)

        if args.verify_only:
            valid_mongo = (
                len(set(collisions["users"])) == len(providers)
                and len(set(collisions["providers"])) == len(providers)
            )
            valid_auth = len(set(auth_collisions)) == len(providers)
            valid_rtdb = len(set(rtdb_collisions)) == len(providers)
            report["verified"] = valid_mongo and valid_auth and valid_rtdb
            report["verification"] = {
                "expected": len(providers),
                **report["preflight"],
                "component1_eligibility": len(providers),
                "component4_coverage": len(providers),
            }
            save_report(args.report, report)
            return 0 if report["verified"] else 1
        if not args.apply:
            report["dry_run_passed"] = True
            save_report(args.report, report)
            return 0
        password = settings.research_provider_password
        if password != "Weda@1234":
            raise RuntimeError("RESEARCH_PROVIDER_PASSWORD must equal the locked value Weda@1234")
        if args.backup_dir:
            args.backup_dir.mkdir(parents=True, exist_ok=True)
            backup = {
                "captured_at": datetime.now(UTC).isoformat(),
                "mongo_database": settings.mongodb_database,
                "firebase_project_id": settings.firebase_project_id,
                "target_paths_absent": not any(
                    (
                        collisions["users"],
                        collisions["providers"],
                        auth_collisions,
                        rtdb_collisions,
                    )
                ),
            }
            (args.backup_dir / f"{import_id}-prewrite.json").write_text(
                json.dumps(backup, indent=2) + "\n", encoding="utf-8"
            )
            (args.backup_dir / f"{import_id}-firebase-providers-before.json").write_text(
                json.dumps(rtdb_root, indent=2, default=str) + "\n", encoding="utf-8"
            )
        completed.add("backup")
        save_report(args.report, {**report, "completed_stages": sorted(completed)})

        if "mongo" not in completed:
            pairs = await build_mongo_documents(providers, import_id, password)
            await database.users.insert_many([item[0] for item in pairs], ordered=True)
            try:
                await database.providers.insert_many([item[1] for item in pairs], ordered=True)
            except Exception:
                await database.users.delete_many({"pipelineSeed.importId": import_id})
                raise
            completed.add("mongo")
            save_report(args.report, {**report, "completed_stages": sorted(completed)})

        if "firebase_auth" not in completed:
            try:
                import bcrypt
            except ImportError as error:
                raise RuntimeError(
                    "Install the backend dev dependencies to use Firebase Auth bulk import"
                ) from error
            records = await build_auth_records(providers, password, bcrypt)
            for offset in range(0, len(records), 1000):
                result = await asyncio.to_thread(
                    auth.import_users,
                    records[offset : offset + 1000],
                    hash_alg=auth.UserImportHash.bcrypt(),
                    app=app,
                )
                if result.failure_count:
                    raise RuntimeError(f"Firebase Auth batch import failed: {result.errors}")
            completed.add("firebase_auth")
            save_report(args.report, {**report, "completed_stages": sorted(completed)})

        if "rtdb" not in completed:
            updates = {
                f"providers/{item['provider_id']}": rtdb_provider(
                    item,
                    import_id,
                    str(item["provider_id"]) in baseline.provider_ids,
                    args.research_pipeline_target,
                )
                for item in providers
            }
            await asyncio.to_thread(db.reference("/", app=app).update, updates)
            completed.add("rtdb")

        mongo_user_count = await database.users.count_documents(
            {"pipelineSeed.importId": import_id}
        )
        mongo_provider_count = await database.providers.count_documents(
            {"pipelineSeed.importId": import_id}
        )
        auth_by_uid, _ = await asyncio.to_thread(firebase_accounts, app)
        verified_auth = sum(provider_id in auth_by_uid for provider_id in expected_ids)
        verified_rtdb = await asyncio.to_thread(db.reference("providers", app=app).get)
        verified_rtdb_count = sum(
            isinstance((verified_rtdb or {}).get(provider_id), dict)
            for provider_id in expected_ids
        )
        expected = len(providers)
        report["verification"] = {
            "expected": expected,
            "mongo_users": mongo_user_count,
            "mongo_providers": mongo_provider_count,
            "firebase_auth": verified_auth,
            "firebase_rtdb": verified_rtdb_count,
            "component1_eligibility": expected,
            "component4_coverage": expected,
        }
        report["verified"] = all(
            value == expected for key, value in report["verification"].items() if key != "expected"
        )
        if report["verified"]:
            completed.add("verification")
        report["completed_stages"] = sorted(completed)
        save_report(args.report, report)
        return 0 if report["verified"] else 1
    finally:
        await client.close()


def main() -> int:
    args = parse_args()
    if args.resume and not args.report.exists():
        raise SystemExit("--resume requires an existing --report file")
    return asyncio.run(execute(args))


if __name__ == "__main__":
    sys.exit(main())
