"""Repair Firebase provider profiles and materialize the C1/C2/C4 eligibility relation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from firebase_admin import auth, db

from app.core.config import get_settings
from app.integrations.firebase_component2 import FirebaseRtdbClient
from app.services.provider_eligibility import (
    ELIGIBILITY_VERSION,
    LEGACY_SOURCE,
    RESEARCH_PIPELINE_TARGET,
    RESEARCH_SELECTION_VERSION,
    RESEARCH_SOURCE,
    WEB_SOURCE,
    c1_profile_ready,
    c2_profile_ready,
    select_research_baseline,
    standard_profile_ready,
)

ROOT = Path(__file__).resolve().parents[3]
C1_PROVIDERS = ROOT / "packages/backend/app/components/component1/artifacts/providers.json"
C4_PROVIDER_MAP = ROOT / "ml/components/component4/data/processed/provider_id_map.csv"
DEFAULT_PROVIDER_IMAGE = (
    "https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/"
    "providers%2Fprovider_default.png?alt=media"
)
SYSTEM_ACTOR = "SYSTEM_PROVIDER_ELIGIBILITY_V1"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--provider-id")
    parser.add_argument(
        "--research-pipeline-target", type=int, default=RESEARCH_PIPELINE_TARGET
    )
    parser.add_argument(
        "--source", choices=(RESEARCH_SOURCE, WEB_SOURCE, LEGACY_SOURCE)
    )
    return parser.parse_args()


def email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def deterministic_web_user_id(firebase_uid: str) -> str:
    return "UWEB" + hashlib.sha256(firebase_uid.encode("utf-8")).hexdigest()[:12].upper()


def load_artifacts() -> tuple[list[dict[str, Any]], set[str], set[str]]:
    providers = json.loads(C1_PROVIDERS.read_text(encoding="utf-8"))
    c1_ids = {str(item["provider_id"]) for item in providers}
    with C4_PROVIDER_MAP.open(encoding="utf-8", newline="") as source:
        c4_ids = {str(item["provider_id"]) for item in csv.DictReader(source)}
    return providers, c1_ids, c4_ids


def source_for(provider_id: str, profile: dict[str, Any]) -> str:
    existing = str(profile.get("profileSource") or "")
    if existing in {RESEARCH_SOURCE, WEB_SOURCE, LEGACY_SOURCE}:
        return existing
    if profile.get("researchSeed") is True:
        return RESEARCH_SOURCE
    if (
        str(profile.get("id")) == provider_id
        and str(profile.get("uid")) == provider_id
        and c1_profile_ready(profile)
        and c2_profile_ready(profile)
    ):
        return WEB_SOURCE
    return LEGACY_SOURCE


def auth_inventory(app: Any) -> dict[str, Any]:
    return {item.uid: item for item in auth.list_users(app=app).iterate_all()}


def resolve_user_id(
    provider_id: str,
    profile: dict[str, Any],
    source: str,
    users: dict[str, Any],
    indexes: dict[str, Any],
    auth_user: Any | None,
) -> tuple[str | None, str | None]:
    indexed = (indexes.get("users_by_firebase_uid") or {}).get(provider_id)
    candidates = {
        str(user_id)
        for user_id, user in users.items()
        if isinstance(user, dict)
        and user.get("legacy", {}).get("firebase_uid") == provider_id
    }
    if isinstance(indexed, str):
        candidates.add(indexed)
    declared = profile.get("userId") or profile.get("user_id")
    if isinstance(declared, str) and declared in users:
        candidates.add(declared)
    email = str(profile.get("email") or getattr(auth_user, "email", "") or "").lower()
    if email:
        candidates.update(
            str(user_id)
            for user_id, user in users.items()
            if isinstance(user, dict)
            and str(user.get("email") or "").strip().lower() == email
            and str(user.get("role")) == "provider"
        )
    if len(candidates) > 1:
        return None, "multiple_core_users"
    if candidates:
        return next(iter(candidates)), None
    if auth_user is None:
        return None, "firebase_auth_user_missing"
    if source == RESEARCH_SOURCE and provider_id.startswith("P"):
        return "U" + provider_id[1:], None
    if source == WEB_SOURCE:
        return deterministic_web_user_id(provider_id), None
    return None, "legacy_provider_has_no_safe_identity"


def research_backfill(profile: dict[str, Any], provider_id: str) -> None:
    profile.setdefault("nic", f"RESEARCH-{provider_id}")
    profile.setdefault("phone", f"research-{provider_id}")
    profile.setdefault("preferredLanguage", "Sinhala, English")
    profile.setdefault("providerImage", DEFAULT_PROVIDER_IMAGE)
    seed = profile.setdefault("pipelineSeed", {})
    sources = seed.setdefault("derivedFieldSources", {})
    sources.setdefault("nic", "synthetic_research_identifier")
    sources.setdefault("phone", "synthetic_non_dialable_research_contact")
    sources.setdefault("preferredLanguage", "research_default_sinhala_english")
    sources.setdefault("providerImage", "project_default_provider_image")


def core_user_document(
    current: dict[str, Any] | None,
    *,
    user_id: str,
    provider_id: str,
    profile: dict[str, Any],
    auth_user: Any,
    now: str,
) -> dict[str, Any]:
    document = deepcopy(current or {})
    if document.get("role") not in (None, "provider"):
        raise RuntimeError(f"Core user role collision for {provider_id}")
    email = str(document.get("email") or profile.get("email") or auth_user.email or "").lower()
    if not email:
        raise RuntimeError(f"Provider {provider_id} has no email relation")
    document.update(
        {
            "user_id": user_id,
            "email": email,
            "full_name": str(
                document.get("full_name")
                or profile.get("fullName")
                or auth_user.display_name
                or provider_id
            ),
            "role": "provider",
            "is_active": True,
            "auth_source": "firebase",
            "auth_version": 1,
            "updated_at": now,
        }
    )
    document.setdefault("created_at", now)
    document.setdefault("legacy", {})["firebase_uid"] = provider_id
    return document


def verification_event(
    provider_id: str, previous: bool, mode: str, reason: str, now: str
) -> dict[str, Any]:
    return {
        "event_id": f"VELIGIBILITYV1-{provider_id}",
        "provider_id": provider_id,
        "admin_user_id": SYSTEM_ACTOR,
        "previous_verified": previous,
        "verified": True,
        "mode": mode,
        "reason": reason,
        "created_at": now,
    }


def build_updates(
    providers: dict[str, Any],
    users: dict[str, Any],
    indexes: dict[str, Any],
    auth_users: dict[str, Any],
    c1_ids: set[str],
    c4_ids: set[str],
    active_research_ids: set[str],
    *,
    provider_filter: str | None,
    source_filter: str | None,
    limit: int | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    updates: dict[str, Any] = {}
    counts = {
        "research": 0,
        "website": 0,
        "legacy": 0,
        "eligible": 0,
        "verified": 0,
        "inactive_research": 0,
        "relations_repaired": 0,
        "research_fields_backfilled": 0,
    }
    quarantined: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    selected = sorted(providers.items())
    if provider_filter:
        selected = [item for item in selected if item[0] == provider_filter]
    processed = 0
    for provider_id, raw in selected:
        if not isinstance(raw, dict):
            continue
        source = source_for(provider_id, raw)
        if source_filter and source != source_filter:
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        profile = deepcopy(raw)
        profile["profileSource"] = source
        profile["schemaVersion"] = 2
        if source == RESEARCH_SOURCE:
            counts["research"] += 1
            missing_before = sum(
                not profile.get(field)
                for field in ("nic", "phone", "preferredLanguage", "providerImage")
            )
            research_backfill(profile, provider_id)
            counts["research_fields_backfilled"] += missing_before
        elif source == WEB_SOURCE:
            counts["website"] += 1
        else:
            counts["legacy"] += 1

        auth_user = auth_users.get(provider_id)
        user_id, relation_error = resolve_user_id(
            provider_id, profile, source, users, indexes, auth_user
        )
        relations_valid = user_id is not None and auth_user is not None
        if relations_valid:
            current_user = users.get(str(user_id))
            user = core_user_document(
                current_user if isinstance(current_user, dict) else None,
                user_id=str(user_id),
                provider_id=provider_id,
                profile=profile,
                auth_user=auth_user,
                now=now,
            )
            existing_provider_user = profile.get("userId") or profile.get("user_id")
            if existing_provider_user != user_id:
                counts["relations_repaired"] += 1
            profile["userId"] = str(user_id)
            comparable_user = {key: value for key, value in user.items() if key != "updated_at"}
            comparable_current = {
                key: value
                for key, value in (
                    current_user if isinstance(current_user, dict) else {}
                ).items()
                if key != "updated_at"
            }
            if comparable_user != comparable_current:
                updates[f"core/users/{user_id}"] = user
            if (indexes.get("users_by_firebase_uid") or {}).get(provider_id) != user_id:
                updates[f"core/indexes/users_by_firebase_uid/{provider_id}"] = str(user_id)
            hashed_email = email_key(user["email"])
            if (indexes.get("users_by_email") or {}).get(hashed_email) != user_id:
                updates[f"core/indexes/users_by_email/{hashed_email}"] = str(user_id)
            if (indexes.get("providers_by_user") or {}).get(str(user_id)) != provider_id:
                updates[f"core/indexes/providers_by_user/{user_id}"] = provider_id

        c1_ready = c1_profile_ready(profile)
        c2_ready = c2_profile_ready(profile)
        profile_complete = standard_profile_ready(profile)
        c4_ready = provider_id in c4_ids if source == RESEARCH_SOURCE else source == WEB_SOURCE
        source_ready = (
            source == WEB_SOURCE
            or (source == RESEARCH_SOURCE and provider_id in c1_ids and provider_id in c4_ids)
        )
        integrity_ready = bool(
            source_ready
            and c1_ready
            and c2_ready
            and c4_ready
            and profile_complete
            and relations_valid
        )
        pipeline_selected = source == WEB_SOURCE or (
            source == RESEARCH_SOURCE and provider_id in active_research_ids
        )
        eligible = integrity_ready and pipeline_selected
        if integrity_ready:
            previous_verified = profile.get("verified") is True
            profile["verified"] = True
            mode = (
                "research_seed_integrity"
                if source == RESEARCH_SOURCE
                else "website_profile_integrity_migration"
            )
            reason = (
                "C1/C2/C4 research provider integrity verified"
                if source == RESEARCH_SOURCE
                else "Website provider profile, Firebase identity, and pipeline readiness verified"
            )
            current_verification = profile.get("verification") or {}
            if (
                current_verification.get("status") != "verified"
                or current_verification.get("mode") != mode
            ):
                profile["verification"] = {
                    **current_verification,
                    "status": "verified",
                    "mode": mode,
                    "last_action_by": SYSTEM_ACTOR,
                    "last_action_at": now,
                    "last_reason": reason,
                }
                event = verification_event(provider_id, previous_verified, mode, reason, now)
                updates[f"core/provider_verification_events/{event['event_id']}"] = event
            counts["verified"] += 1
            if eligible:
                counts["eligible"] += 1
            elif source == RESEARCH_SOURCE:
                counts["inactive_research"] += 1
                excluded.append(
                    {
                        "provider_id": provider_id,
                        "source": source,
                        "reason": "outside_balanced_research_pipeline_baseline",
                    }
                )
        else:
            profile["verified"] = False
            quarantined.append(
                {
                    "provider_id": provider_id,
                    "source": source,
                    "reason": relation_error
                    or (
                        "profile_or_component_readiness_incomplete"
                        if not (
                            c1_ready
                            and c2_ready
                            and c4_ready
                            and profile_complete
                            and source_ready
                        )
                        else "unknown"
                    ),
                }
            )
        profile["pipelineEligibility"] = {
            "version": ELIGIBILITY_VERSION,
            "eligible": eligible,
            "verified": profile.get("verified") is True,
            "c1Ready": c1_ready,
            "c2Ready": c2_ready,
            "c4Ready": c4_ready,
            "profileComplete": profile_complete,
            "relationsValid": relations_valid,
            "activeResearchBaseline": (
                provider_id in active_research_ids if source == RESEARCH_SOURCE else False
            ),
            "selectionVersion": RESEARCH_SELECTION_VERSION,
            "researchBaselineTarget": len(active_research_ids),
            "selectionReason": (
                "balanced_research_category_location"
                if source == RESEARCH_SOURCE and provider_id in active_research_ids
                else "verified_website_registration"
                if source == WEB_SOURCE and eligible
                else "outside_balanced_research_pipeline_baseline"
                if source == RESEARCH_SOURCE and integrity_ready
                else "profile_or_relation_not_ready"
            ),
            "evaluatedAt": now,
        }
        updates[f"providers/{provider_id}"] = profile
    return updates, {
        "counts": counts,
        "quarantined": quarantined,
        "excluded_count": len(excluded),
        "excluded_sample": excluded[:20],
        "processed": processed,
    }


def provider_values_from_updates(
    providers: dict[str, Any], updates: dict[str, Any]
) -> dict[str, Any]:
    projected = deepcopy(providers)
    for path, value in updates.items():
        if path.startswith("providers/"):
            projected[path.split("/", 1)[1]] = value
    return projected


def verification_summary(providers: dict[str, Any], c1_ids: set[str], c4_ids: set[str]) -> dict[str, Any]:
    research = []
    website = []
    legacy = []
    for provider_id, profile in providers.items():
        if not isinstance(profile, dict):
            continue
        source = source_for(provider_id, profile)
        (research if source == RESEARCH_SOURCE else website if source == WEB_SOURCE else legacy).append(
            (provider_id, profile)
        )
    eligible = [
        (provider_id, profile)
        for provider_id, profile in providers.items()
        if isinstance(profile, dict)
        and profile.get("verified") is True
        and isinstance(profile.get("pipelineEligibility"), dict)
        and profile["pipelineEligibility"].get("eligible") is True
    ]
    verified_profiles = [
        (provider_id, profile)
        for provider_id, profile in providers.items()
        if isinstance(profile, dict) and profile.get("verified") is True
    ]
    eligible_research = [
        (provider_id, profile)
        for provider_id, profile in eligible
        if source_for(provider_id, profile) == RESEARCH_SOURCE
    ]
    missing_research_fields = sum(
        not profile.get(field)
        for _, profile in research
        for field in ("nic", "phone", "preferredLanguage", "providerImage")
    )
    return {
        "provider_count": len(providers),
        "research_count": len(research),
        "website_count": len(website),
        "legacy_count": len(legacy),
        "eligible_count": len(eligible),
        "verified_count": len(verified_profiles),
        "verified_research_count": sum(
            source_for(provider_id, profile) == RESEARCH_SOURCE
            for provider_id, profile in verified_profiles
        ),
        "eligible_research_count": sum(
            source_for(provider_id, profile) == RESEARCH_SOURCE
            for provider_id, profile in eligible
        ),
        "eligible_website_count": sum(
            source_for(provider_id, profile) == WEB_SOURCE
            for provider_id, profile in eligible
        ),
        "missing_research_field_values": missing_research_fields,
        "research_c1_c4_intersection_count": sum(
            provider_id in c1_ids and provider_id in c4_ids for provider_id, _ in research
        ),
        "eligible_research_category_counts": {
            category: sum(
                str(profile.get("category") or "") == category
                for _, profile in eligible_research
            )
            for category in sorted(
                {str(profile.get("category") or "") for _, profile in eligible_research}
            )
        },
        "eligible_research_category_district_coverage": {
            category: len(
                {
                    str(profile.get("district") or "")
                    for _, profile in eligible_research
                    if str(profile.get("category") or "") == category
                }
            )
            for category in sorted(
                {str(profile.get("category") or "") for _, profile in eligible_research}
            )
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def apply_batches(app: Any, updates: dict[str, Any], batch_size: int = 250) -> None:
    items = list(updates.items())
    root = db.reference("/", app=app)
    for offset in range(0, len(items), batch_size):
        root.update(dict(items[offset : offset + batch_size]))


def main() -> int:
    args = arguments()
    settings = get_settings()
    client = FirebaseRtdbClient(settings)
    app = client._app()
    artifact_profiles, c1_ids, c4_ids = load_artifacts()
    baseline = select_research_baseline(
        artifact_profiles,
        c1_ids & c4_ids,
        args.research_pipeline_target,
    )
    providers = db.reference("providers", app=app).get() or {}
    users = db.reference("core/users", app=app).get() or {}
    indexes = db.reference("core/indexes", app=app).get() or {}
    component2_filter_requests = db.reference("filter_requests", app=app).get() or {}
    component2_hash_before = canonical_sha256(component2_filter_requests)
    auth_users = auth_inventory(app)

    if args.verify_only:
        summary = verification_summary(providers, c1_ids, c4_ids)
        expected_updates, _ = build_updates(
            providers,
            users,
            indexes,
            auth_users,
            c1_ids,
            c4_ids,
            baseline.provider_ids,
            provider_filter=args.provider_id,
            source_filter=args.source,
            limit=args.limit,
        )
        expected = verification_summary(
            provider_values_from_updates(providers, expected_updates), c1_ids, c4_ids
        )
        verified = (
            summary == expected
            and summary["research_count"] == 4_998
            and summary["research_c1_c4_intersection_count"] == 4_998
            and summary["missing_research_field_values"] == 0
            and summary["verified_research_count"] == 4_998
            and summary["eligible_research_count"]
            == args.research_pipeline_target
        )
        report = {
            "mode": "verify-only",
            "verified": verified,
            "summary": summary,
            "expected": expected,
            "component2_untouched": True,
            "component2_filter_requests_sha256": component2_hash_before,
            "research_baseline": {
                "target": args.research_pipeline_target,
                "selection_version": RESEARCH_SELECTION_VERSION,
                "category_quotas": baseline.category_quotas,
            },
        }
        write_json(args.report, report)
        print(json.dumps(report, indent=2))
        return 0 if verified else 1

    updates, plan = build_updates(
        providers,
        users,
        indexes,
        auth_users,
        c1_ids,
        c4_ids,
        baseline.provider_ids,
        provider_filter=args.provider_id,
        source_filter=args.source,
        limit=args.limit,
    )
    projected = provider_values_from_updates(providers, updates)
    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "applied": False,
        "plan": plan,
        "projected": verification_summary(projected, c1_ids, c4_ids),
        "component2_untouched": True,
        "component2_filter_requests_sha256_before": component2_hash_before,
        "research_baseline": {
            "target": args.research_pipeline_target,
            "selection_version": RESEARCH_SELECTION_VERSION,
            "category_quotas": baseline.category_quotas,
        },
    }
    if args.apply:
        if args.backup_dir is None:
            raise RuntimeError("--backup-dir is required with --apply")
        args.backup_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.backup_dir / "providers.json", providers)
        write_json(args.backup_dir / "core-users.json", users)
        write_json(args.backup_dir / "core-indexes.json", indexes)
        write_json(
            args.backup_dir / "component2-filter-requests.json",
            component2_filter_requests,
        )
        write_json(
            args.backup_dir / "provider-verification-events.json",
            db.reference("core/provider_verification_events", app=app).get() or {},
        )
        apply_batches(app, updates)
        stored = db.reference("providers", app=app).get() or {}
        component2_hash_after = canonical_sha256(
            db.reference("filter_requests", app=app).get() or {}
        )
        report["applied"] = True
        report["verified"] = True
        report["stored"] = verification_summary(stored, c1_ids, c4_ids)
        report["component2_filter_requests_sha256_after"] = component2_hash_after
        report["component2_untouched"] = (
            component2_hash_before == component2_hash_after
        )
        expected = report["projected"]
        if report["stored"] != expected or not report["component2_untouched"]:
            report["verified"] = False
    write_json(args.report, report)
    print(json.dumps(report, indent=2))
    return 0 if not args.apply or report.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
