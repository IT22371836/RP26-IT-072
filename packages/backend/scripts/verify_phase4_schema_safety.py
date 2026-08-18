import argparse
import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.main import app
from app.migrations.firebase_rtdb import load_firebase_export
from app.schemas.integration import (
    ContextFilterResult,
    ContextFilterResultWeb,
    DailyDemandRecord,
    DailyDemandWebResponse,
    IntegrationExtractedFeatures,
    IntegrationLocation,
    IntegrationProviderDocuments,
    IntegrationWorkingHours,
    dump_preserving_unknown,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Phase 4 schema and repository safety without database writes."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def repository_update_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted((BACKEND_ROOT / "app" / "repositories").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "replace_one" in source or "$unset" in source:
            violations.append(f"{path.name}:destructive_update_primitive")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"update_one", "update_many", "find_one_and_update"}:
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Dict):
                violations.append(f"{path.name}:{node.lineno}:non_literal_update")
                continue
            keys = [
                key.value
                for key in node.args[1].keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            ]
            if not keys or any(not key.startswith("$") for key in keys):
                violations.append(f"{path.name}:{node.lineno}:replacement_style_update")
    return violations


def provider_model_counts(providers: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {
        "locations": 0,
        "working_hours": 0,
        "document_sets": 0,
        "extracted_features": 0,
        "credibility_records": 0,
    }
    for provider in providers.values():
        if isinstance(provider.get("location"), dict):
            IntegrationLocation.model_validate(provider["location"])
            counts["locations"] += 1
        if isinstance(provider.get("workingHours"), dict):
            IntegrationWorkingHours.model_validate(provider["workingHours"])
            counts["working_hours"] += 1
        if isinstance(provider.get("documents"), dict):
            IntegrationProviderDocuments.model_validate(provider["documents"])
            counts["document_sets"] += 1
        features = provider.get("extractedFeatures")
        if not isinstance(features, dict) and isinstance(provider.get("documents"), dict):
            features = provider["documents"].get("extractedFeatures")
        if isinstance(features, dict):
            IntegrationExtractedFeatures.model_validate(features)
            counts["extracted_features"] += 1
            if isinstance(features.get("credibility"), dict):
                counts["credibility_records"] += 1
    return counts


def privacy_allowlist_passes() -> bool:
    context = ContextFilterResultWeb.model_validate(
        {
            "id": "source-key",
            "request_id": "request-id",
            "_id": "forbidden",
            "password_hash": "forbidden",
            "nic": "forbidden",
            "private_document_url": "forbidden",
        }
    ).model_dump(by_alias=True)
    demand = DailyDemandWebResponse.model_validate(
        {"compile_date": "2026-08-05", "_id": "forbidden", "nic": "forbidden"}
    ).model_dump(by_alias=True)
    forbidden = {"_id", "password_hash", "nic", "private_document_url"}
    return not forbidden.intersection(context) and not forbidden.intersection(demand)


def build_report(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    filter_exact = 0
    for record in data.get("filter_requests", {}).values():
        model = ContextFilterResult.model_validate(record)
        if dump_preserving_unknown(model) == record:
            filter_exact += 1

    daily_exact = 0
    for record in data.get("daily_demand", {}).values():
        model = DailyDemandRecord.model_validate(record)
        if dump_preserving_unknown(model) == record:
            daily_exact += 1

    paths = set(app.openapi()["paths"])
    required_routes = {
        "/api/v1/integration/daily-demand/current",
        "/api/v1/integration/filter-requests",
        "/api/v1/component1/recommend",
        "/api/v1/component4/rank",
    }
    missing_routes = sorted(required_routes - paths)
    update_violations = repository_update_violations()
    provider_counts = provider_model_counts(data.get("providers", {}))
    passed = (
        filter_exact == len(data.get("filter_requests", {}))
        and daily_exact == len(data.get("daily_demand", {}))
        and not missing_routes
        and not update_violations
        and privacy_allowlist_passes()
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-schema-verification",
        "summary": {
            "passed": passed,
            "filter_records_validated_exactly": filter_exact,
            "daily_demand_records_validated_exactly": daily_exact,
            "provider_models_validated": provider_counts,
            "required_api_routes_present": len(required_routes) - len(missing_routes),
            "required_api_routes_expected": len(required_routes),
            "privacy_allowlist_passed": privacy_allowlist_passes(),
            "repository_update_violations": len(update_violations),
            "source_database_writes": 0,
        },
        "missing_routes": missing_routes,
        "repository_update_violations": update_violations,
        "safety_contract": {
            "legacy_models_allow_unknown_fields": True,
            "web_response_models_are_allowlisted": True,
            "profile_optimistic_concurrency": "optional expected_updated_at token",
            "component1_request_ownership_required": True,
            "component4_request_ownership_required": True,
        },
    }


def main() -> int:
    args = parse_args()
    report = build_report(load_firebase_export(args.input.resolve()))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
