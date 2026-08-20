"""Migrate active research providers to name-based Gmail logins and one password."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from firebase_admin import auth, db

from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient

EXPECTED_RESEARCH_ACCOUNTS = 1_000
LOCKED_PASSWORD = "Weda@1234"
EMAIL_VERSION = "research-provider-name-gmail-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def provider_name_slug(name: Any) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", str(name or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return re.sub(r"[^a-z0-9]+", "", ascii_name) or "provider"


def research_email(provider_id: str, provider_name: Any) -> str:
    return f"{provider_name_slug(provider_name)}12.{provider_id.lower()}@gmail.com"


def research_user_id(provider_id: str) -> str:
    return "U" + provider_id[1:]


def is_active_research(profile: Any) -> bool:
    if not isinstance(profile, dict):
        return False
    eligibility = profile.get("pipelineEligibility") or {}
    return bool(
        profile.get("researchSeed") is True
        and profile.get("profileSource") == "research_seed"
        and eligibility.get("activeResearchBaseline") is True
        and eligibility.get("eligible") is True
    )


def desired_emails(providers: dict[str, Any]) -> dict[str, str]:
    mapping = {
        provider_id: research_email(
            provider_id,
            profile.get("fullName") or profile.get("provider_name"),
        )
        for provider_id, profile in providers.items()
        if is_active_research(profile)
    }
    if len(mapping) != EXPECTED_RESEARCH_ACCOUNTS:
        raise RuntimeError(
            f"Expected {EXPECTED_RESEARCH_ACCOUNTS} active research providers, "
            f"found {len(mapping)}"
        )
    if len(set(mapping.values())) != len(mapping):
        raise RuntimeError("Generated research emails are not unique")
    return mapping


def auth_inventory(app: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    by_uid: dict[str, Any] = {}
    by_email: dict[str, Any] = {}
    for user in auth.list_users(app=app).iterate_all():
        by_uid[user.uid] = user
        if user.email:
            by_email[user.email.lower()] = user
    return by_uid, by_email


def validate_relations(
    providers: dict[str, Any],
    users: dict[str, Any],
    indexes: dict[str, Any],
    auth_by_uid: dict[str, Any],
    auth_by_email: dict[str, Any],
    mapping: dict[str, str],
    *,
    require_desired_email: bool,
) -> None:
    for provider_id, desired_email in sorted(mapping.items()):
        profile = providers[provider_id]
        user_id = research_user_id(provider_id)
        user = users.get(user_id)
        auth_user = auth_by_uid.get(provider_id)
        if auth_user is None:
            raise RuntimeError(f"Firebase Auth user missing: {provider_id}")
        owner = auth_by_email.get(desired_email)
        if owner is not None and owner.uid != provider_id:
            raise RuntimeError(
                f"Desired email collision: {desired_email} belongs to {owner.uid}"
            )
        if not isinstance(user, dict) or user.get("role") != "provider":
            raise RuntimeError(f"Core provider user missing: {provider_id}")
        if user.get("legacy", {}).get("firebase_uid") != provider_id:
            raise RuntimeError(f"Core Firebase UID relation mismatch: {provider_id}")
        if (indexes.get("providers_by_user") or {}).get(user_id) != provider_id:
            raise RuntimeError(f"Provider index mismatch: {provider_id}")
        if (indexes.get("users_by_firebase_uid") or {}).get(provider_id) != user_id:
            raise RuntimeError(f"Firebase UID index mismatch: {provider_id}")
        if require_desired_email:
            values = {
                str(profile.get("email") or "").lower(),
                str(user.get("email") or "").lower(),
                str(auth_user.email or "").lower(),
            }
            if values != {desired_email}:
                raise RuntimeError(f"Credential email mismatch: {provider_id}: {values}")
            if (indexes.get("users_by_email") or {}).get(email_key(desired_email)) != user_id:
                raise RuntimeError(f"Desired email index mismatch: {provider_id}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def auth_metadata(auth_by_uid: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    return {
        provider_id: {
            "uid": provider_id,
            "email": auth_by_uid[provider_id].email,
            "display_name": auth_by_uid[provider_id].display_name,
            "disabled": auth_by_uid[provider_id].disabled,
            "email_verified": auth_by_uid[provider_id].email_verified,
            "desired_email": mapping[provider_id],
        }
        for provider_id in sorted(mapping)
    }


def update_auth_identity(app: Any, provider_id: str, email: str) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            auth.update_user(
                provider_id,
                email=email,
                password=LOCKED_PASSWORD,
                disabled=False,
                app=app,
            )
            return
        except Exception as error:  # Firebase exceptions vary by transport failure.
            last_error = error
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Auth update failed for {provider_id}") from last_error


def update_auth_batch(
    app: Any, mapping: dict[str, str], workers: int
) -> None:
    if workers < 1 or workers > 16:
        raise ValueError("--workers must be between 1 and 16")
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(update_auth_identity, app, provider_id, email): provider_id
            for provider_id, email in mapping.items()
        }
        for future in as_completed(futures):
            provider_id = futures[future]
            try:
                future.result()
            except Exception:
                failures.append(provider_id)
    if failures:
        raise RuntimeError(f"Firebase Auth updates failed for: {sorted(failures)}")


def main() -> int:
    args = parse_args()
    if args.apply and args.backup_dir is None:
        raise RuntimeError("--backup-dir is required with --apply")
    settings = get_settings()
    if settings.research_provider_password != LOCKED_PASSWORD:
        raise RuntimeError(
            f"RESEARCH_PROVIDER_PASSWORD must equal the locked value {LOCKED_PASSWORD}"
        )
    app = FirebaseRtdbClient(settings)._app()
    providers = db.reference("providers", app=app).get() or {}
    users = db.reference("core/users", app=app).get() or {}
    indexes = db.reference("core/indexes", app=app).get() or {}
    filter_requests = db.reference("filter_requests", app=app).get() or {}
    filter_hash_before = canonical_sha256(filter_requests)
    mapping = desired_emails(providers)
    auth_by_uid, auth_by_email = auth_inventory(app)
    validate_relations(
        providers,
        users,
        indexes,
        auth_by_uid,
        auth_by_email,
        mapping,
        require_desired_email=args.verify_only,
    )

    already_migrated = sum(
        str(auth_by_uid[provider_id].email or "").lower() == email
        and str(providers[provider_id].get("email") or "").lower() == email
        and str(users[research_user_id(provider_id)].get("email") or "").lower() == email
        for provider_id, email in mapping.items()
    )
    report: dict[str, Any] = {
        "mode": "verify-only" if args.verify_only else "apply" if args.apply else "dry-run",
        "applied": False,
        "email_version": EMAIL_VERSION,
        "email_pattern": "{providername}12.{providerId-lowercase}@gmail.com",
        "account_count": len(mapping),
        "unique_email_count": len(set(mapping.values())),
        "already_migrated_count": already_migrated,
        "password_reset_count": 0,
        "sample": [
            {
                "provider_id": provider_id,
                "provider_name": providers[provider_id].get("fullName"),
                "email": mapping[provider_id],
            }
            for provider_id in sorted(mapping)[:10]
        ],
        "contains_plaintext_password": False,
        "component2_filter_requests_sha256_before": filter_hash_before,
    }
    if args.verify_only:
        report.update(
            {
                "verified": already_migrated == EXPECTED_RESEARCH_ACCOUNTS,
                "component2_untouched": True,
                "component2_filter_requests_sha256": filter_hash_before,
            }
        )
        write_json(args.report, report)
        print(json.dumps(report, indent=2))
        return 0 if report["verified"] else 1
    if not args.apply:
        write_json(args.report, report)
        print(json.dumps(report, indent=2))
        return 0

    backup_dir: Path = args.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    provider_ids = set(mapping)
    user_ids = {research_user_id(provider_id) for provider_id in provider_ids}
    write_json(
        backup_dir / "provider-profiles.json",
        {provider_id: providers[provider_id] for provider_id in sorted(provider_ids)},
    )
    write_json(
        backup_dir / "core-users.json",
        {user_id: users[user_id] for user_id in sorted(user_ids)},
    )
    write_json(backup_dir / "core-indexes.json", indexes)
    write_json(backup_dir / "firebase-auth-metadata.json", auth_metadata(auth_by_uid, mapping))
    write_json(backup_dir / "manifest.json", report)

    update_auth_batch(app, mapping, args.workers)
    updates: dict[str, Any] = {}
    for provider_id, desired_email in sorted(mapping.items()):
        user_id = research_user_id(provider_id)
        old_profile_email = str(providers[provider_id].get("email") or "").lower()
        old_user_email = str(users[user_id].get("email") or "").lower()
        updates[f"providers/{provider_id}/email"] = desired_email
        updates[f"providers/{provider_id}/pipelineSeed/credentialEmailVersion"] = EMAIL_VERSION
        updates[f"core/users/{user_id}/email"] = desired_email
        updates[f"core/indexes/users_by_email/{email_key(desired_email)}"] = user_id
        for old_email in {old_profile_email, old_user_email} - {"", desired_email}:
            if (indexes.get("users_by_email") or {}).get(email_key(old_email)) == user_id:
                updates[f"core/indexes/users_by_email/{email_key(old_email)}"] = None
    root = db.reference("/", app=app)
    items = list(updates.items())
    for offset in range(0, len(items), 250):
        root.update(dict(items[offset : offset + 250]))

    stored_providers = db.reference("providers", app=app).get() or {}
    stored_users = db.reference("core/users", app=app).get() or {}
    stored_indexes = db.reference("core/indexes", app=app).get() or {}
    stored_auth_uid, stored_auth_email = auth_inventory(app)
    validate_relations(
        stored_providers,
        stored_users,
        stored_indexes,
        stored_auth_uid,
        stored_auth_email,
        mapping,
        require_desired_email=True,
    )
    filter_hash_after = canonical_sha256(
        db.reference("filter_requests", app=app).get() or {}
    )
    report.update(
        {
            "applied": True,
            "verified": filter_hash_after == filter_hash_before,
            "already_migrated_count": EXPECTED_RESEARCH_ACCOUNTS,
            "password_reset_count": EXPECTED_RESEARCH_ACCOUNTS,
            "component2_filter_requests_sha256_after": filter_hash_after,
            "component2_untouched": filter_hash_after == filter_hash_before,
        }
    )
    write_json(args.report, report)
    write_json(backup_dir / "result.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
