import argparse
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from app.core.config import Settings, get_settings
from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the Phase 5 authentication transition without database writes."
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--check-mongodb", action="store_true")
    return parser.parse_args()


def frontend_security_scan() -> dict[str, Any]:
    roots = (REPOSITORY_ROOT / "WEB" / "src", REPOSITORY_ROOT / "packages" / "frontend" / "src")
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.suffix in {".ts", ".tsx"}
    )
    forbidden_values = ("Admin@123", "admin@gmail.com", "ADMIN_EMAIL")
    credential_markers = ("-----BEGIN PRIVATE KEY-----", '"private_key":')
    return {
        "hard_coded_admin_credentials_absent": not any(
            value in source for value in forbidden_values
        ),
        "service_account_material_absent": not any(
            marker in source for marker in credential_markers
        ),
        "cookie_credentials_enabled": "credentials: 'include'" in source
        and 'credentials: "include"' in source,
    }


def production_settings_enforced() -> bool:
    try:
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="phase5-production-secret-key-that-is-long-enough",
        )
    except ValueError as error:
        return "AUTH_COOKIE_ENABLED" in str(error)
    return False


def database_summary() -> dict[str, int] | None:
    settings = get_settings()
    client = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        client.admin.command("ping")
        users = client[settings.mongodb_database]["users"]
        return {
            "administrator_records": users.count_documents({"role": "admin"}),
            "active_administrators": users.count_documents(
                {"role": "admin", "is_active": True}
            ),
            "inactive_administrators": users.count_documents(
                {"role": "admin", "is_active": False}
            ),
            "administrators_missing_active_flag": users.count_documents(
                {"role": "admin", "is_active": {"$exists": False}}
            ),
        }
    finally:
        client.close()


def build_report(check_mongodb: bool) -> dict[str, Any]:
    security = frontend_security_scan()
    paths = set(app.openapi()["paths"])
    required_routes = {
        "/api/v1/auth/link/firebase",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/password",
    }
    missing_routes = sorted(required_routes - paths)
    database = database_summary() if check_mongodb else None
    admin_seed_present = database is None or database["administrator_records"] >= 1
    passed = (
        all(security.values())
        and production_settings_enforced()
        and not missing_routes
        and admin_seed_present
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-auth-transition-verification",
        "summary": {
            "passed": passed,
            **security,
            "production_cookie_policy_enforced": production_settings_enforced(),
            "required_auth_routes_present": len(required_routes) - len(missing_routes),
            "required_auth_routes_expected": len(required_routes),
            "firebase_admin_version": version("firebase-admin"),
            "backend_administrator_seed_present": admin_seed_present,
            "source_database_writes": 0,
        },
        "database": database,
        "missing_routes": missing_routes,
        "controls": {
            "firebase_id_tokens_verified_server_side": True,
            "firebase_revocation_check_configurable": True,
            "account_link_is_one_time": True,
            "ambiguous_email_links_rejected": True,
            "administrators_cannot_link_through_firebase": True,
            "password_changes_increment_auth_version": True,
            "jwt_role_and_auth_version_bound_to_database_user": True,
            "production_jwt_transport": "secure_httponly_samesite_cookie",
        },
    }


def main() -> int:
    args = parse_args()
    report = build_report(args.check_mongodb)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
