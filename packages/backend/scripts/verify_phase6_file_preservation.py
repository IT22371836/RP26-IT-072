import argparse
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from app.main import app
from app.schemas.provider import ProviderPublic

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parents[1]
PRIVATE_CATEGORIES = {
    "identityDocument",
    "certification",
    "businessRegistration",
    "experienceProof",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Phase 6 file preservation without source database writes."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--copy-manifest", type=Path)
    parser.add_argument("--anonymous-audit", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_copy_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "not_started_by_design",
            "copies_declared": 0,
            "copies_verified": 0,
            "failures": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    copies = payload.get("copies")
    if not isinstance(copies, list):
        raise ValueError("copy manifest must contain a copies array")
    failures: list[str] = []
    verified = 0
    for index, item in enumerate(copies):
        if not isinstance(item, dict):
            failures.append(f"copies[{index}]:invalid_record")
            continue
        required = ("legacy_url", "current_url", "source_path", "current_path")
        if any(not isinstance(item.get(field), str) or not item[field] for field in required):
            failures.append(f"copies[{index}]:missing_dual_url_or_path")
            continue
        source_path = Path(item["source_path"])
        current_path = Path(item["current_path"])
        if not source_path.is_file() or not current_path.is_file():
            failures.append(f"copies[{index}]:file_missing")
            continue
        source_hash = sha256_file(source_path)
        current_hash = sha256_file(current_path)
        if source_hash != current_hash:
            failures.append(f"copies[{index}]:sha256_mismatch")
            continue
        if item.get("source_sha256") not in (None, source_hash):
            failures.append(f"copies[{index}]:declared_source_sha256_mismatch")
            continue
        if item.get("current_sha256") not in (None, current_hash):
            failures.append(f"copies[{index}]:declared_current_sha256_mismatch")
            continue
        verified += 1
    return {
        "status": "verified" if not failures else "failed",
        "copies_declared": len(copies),
        "copies_verified": verified,
        "failures": failures,
    }


def private_document_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for provider in (payload.get("providers") or {}).values():
        if not isinstance(provider, dict):
            continue
        documents = provider.get("documents") or {}
        if not isinstance(documents, dict):
            continue
        for category in PRIVATE_CATEGORIES:
            for item in documents.get(category) or []:
                if isinstance(item, dict) and isinstance(item.get("fileUrl"), str):
                    urls.append(item["fileUrl"])
    return urls


def audit_anonymous_access(urls: list[str]) -> dict[str, Any]:
    def status_for(url: str) -> str:
        try:
            request = Request(
                url,
                method="HEAD",
                headers={"User-Agent": "WEDA-Phase6-Privacy-Audit/1.0"},
            )
            with urlopen(request, timeout=15) as response:
                return str(response.status)
        except HTTPError as error:
            return str(error.code)
        except (URLError, TimeoutError):
            return "network_error"

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = Counter(executor.map(status_for, urls))
    anonymous_successes = sum(
        count for code, count in statuses.items() if code.isdigit() and 200 <= int(code) < 300
    )
    return {
        "performed": True,
        "checked": len(urls),
        "anonymous_successes": anonymous_successes,
        "status_counts": dict(sorted(statuses.items())),
        "urls_or_tokens_logged": 0,
        "response_body_bytes_read": 0,
    }


def inventory_export(payload: dict[str, Any]) -> dict[str, Any]:
    values = {"fileUrl": [], "providerImage": [], "customerImage": []}
    private_urls: list[str] = []
    for customer in (payload.get("customers") or {}).values():
        if isinstance(customer, dict) and isinstance(customer.get("customerImage"), str):
            values["customerImage"].append(customer["customerImage"])
    for provider in (payload.get("providers") or {}).values():
        if not isinstance(provider, dict):
            continue
        if isinstance(provider.get("providerImage"), str):
            values["providerImage"].append(provider["providerImage"])
        documents = provider.get("documents") or {}
        if not isinstance(documents, dict):
            continue
        for category, items in documents.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("fileUrl"), str):
                    continue
                values["fileUrl"].append(item["fileUrl"])
                if category in PRIVATE_CATEGORIES:
                    private_urls.append(item["fileUrl"])
    tokenized_private = sum(
        1 for url in private_urls if "token" in parse_qs(urlparse(url).query)
    )
    return {
        "preserved_value_counts": {key: len(items) for key, items in values.items()},
        "private_document_urls": len(private_urls),
        "tokenized_private_document_urls": tokenized_private,
        "values_modified": 0,
        "urls_or_tokens_in_report": 0,
    }


def implementation_controls() -> dict[str, bool | int]:
    paths = set(app.openapi()["paths"])
    required_routes = {
        "/api/v1/providers/me/documents/{category}/upload",
        "/api/v1/providers/me/documents/{category}/{file_id}/content",
        "/api/v1/admin/providers/{provider_id}/documents/{category}/{file_id}/content",
    }
    customer_source = (
        REPOSITORY_ROOT / "WEB" / "src" / "components" / "CustomerDashboard.tsx"
    ).read_text(encoding="utf-8")
    firebase_source = (
        REPOSITORY_ROOT / "WEB" / "src" / "config" / "firebase.ts"
    ).read_text(encoding="utf-8")
    storage_rules = (REPOSITORY_ROOT / "WEB" / "storage.rules").read_text(
        encoding="utf-8"
    )
    public_fields = set(ProviderPublic.model_fields)
    return {
        "required_private_routes_present": len(required_routes & paths),
        "required_private_routes_expected": len(required_routes),
        "public_provider_excludes_nic": "nic" not in public_fields,
        "public_provider_excludes_documents": "documents" not in public_fields,
        "customer_uses_sanitized_provider_read": "fetchPublicProviders" in customer_source,
        "customer_nic_render_absent": "selectedProviderModal.nic" not in customer_source,
        "firebase_public_sanitizer_removes_private_fields": (
            "nic: _nic" in firebase_source and "documents: _documents" in firebase_source
        ),
        "private_storage_sdk_access_denied": (
            "match /private/providers/" in storage_rules
            and "allow read, write: if false" in storage_rules
        ),
    }


def build_report(
    source: Path,
    copy_manifest: Path | None,
    anonymous_audit: bool = False,
) -> dict[str, Any]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    inventory = inventory_export(payload)
    controls = implementation_controls()
    copies = verify_copy_manifest(copy_manifest)
    anonymous = (
        audit_anonymous_access(private_document_urls(payload))
        if anonymous_audit
        else {"performed": False}
    )
    implementation_passed = (
        controls["required_private_routes_present"]
        == controls["required_private_routes_expected"]
        and all(value for key, value in controls.items() if not key.endswith("_expected"))
        and copies["status"] != "failed"
    )
    external_privacy_remediation_required = (
        inventory["tokenized_private_document_urls"] > 0
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-file-preservation-verification",
        "summary": {
            "implementation_passed": implementation_passed,
            "phase_complete": implementation_passed
            and not external_privacy_remediation_required,
            "external_privacy_remediation_required": external_privacy_remediation_required,
            "source_database_writes": 0,
            "source_storage_writes": 0,
        },
        "inventory": inventory,
        "controls": controls,
        "copy_verification": copies,
        "anonymous_access_audit": anonymous,
        "remaining_gate": (
            "Copy private legacy objects to managed private paths, verify SHA-256, retain "
            "legacy_url/current_url, then revoke legacy download tokens after owner approval."
            if external_privacy_remediation_required
            else None
        ),
    }


def main() -> int:
    args = parse_args()
    report = build_report(args.input, args.copy_manifest, args.anonymous_audit)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["implementation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
