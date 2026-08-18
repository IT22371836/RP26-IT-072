from __future__ import annotations

from typing import Any

from app.migrations.firebase_rtdb import build_snapshot, iter_field_values, source_sha256

DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

DOCUMENT_CATEGORIES = (
    "identityDocument",
    "certification",
    "businessRegistration",
    "experienceProof",
    "portfolioWork",
)

DOCUMENT_ITEM_FIELDS = ("fileId", "fileName", "fileUrl", "format", "uploadedAt")

CUSTOMER_PATHS = (
    "id",
    "fullName",
    "email",
    "role",
    "phone",
    "district",
    "city",
    "location.latitude",
    "location.longitude",
    "customerImage",
    "preferredLanguage",
    "createdAt",
    "createdTimestamp",
)

PROVIDER_BASE_PATHS = (
    "id",
    "uid",
    "fullName",
    "email",
    "role",
    "phone",
    "district",
    "city",
    "location.latitude",
    "location.longitude",
    "providerImage",
    "preferredLanguage",
    "createdAt",
    "createdTimestamp",
    "nic",
    "category",
    "experienceYears",
    "skills[]",
    "description",
    "verified",
)

PROVIDER_EXTRACTED_PATHS = (
    "extractedFeatures.provider_id",
    "extractedFeatures.service_category",
    "extractedFeatures.identity_verified",
    "extractedFeatures.certification_count",
    "extractedFeatures.highest_cert_level",
    "extractedFeatures.cert_issuer_reputation",
    "extractedFeatures.business_registered",
    "extractedFeatures.experience_years",
    "extractedFeatures.experience_reference_count",
    "extractedFeatures.portfolio_quality_score",
    "extractedFeatures.portfolio_count",
    "extractedFeatures.credibility.credibilityScore",
    "extractedFeatures.credibility.credibilityLevel",
    "extractedFeatures.credibility.lastEvaluatedAt",
)

FILTER_REQUEST_PATHS = (
    "request_id",
    "user_id",
    "service_date",
    "service_time.start_time",
    "service_time.end_time",
    "location_type",
    "isNewRequest",
    "results.provider_ids[]",
    "output_results.evaluated_at",
    "output_results.provider_ids[]",
    "output_results.recommendation",
    "output_results.weather_risk",
    "output_results.weather_summary",
    "output_results.evaluated_providers[].provider_id",
    "output_results.evaluated_providers[].provider_name",
    "output_results.evaluated_providers[].provider_location.latitude",
    "output_results.evaluated_providers[].provider_location.longitude",
    "output_results.evaluated_providers[].distance_km",
    "output_results.evaluated_providers[].is_available",
    "output_results.evaluated_providers[].location_type",
    "output_results.evaluated_providers[].recommendation",
    "output_results.evaluated_providers[].request_id",
    "output_results.evaluated_providers[].service_day",
    "output_results.evaluated_providers[].user_id",
    "output_results.evaluated_providers[].weather_risk",
    "output_results.evaluated_providers[].working_hours_status",
)

DAILY_DEMAND_TOP_PATHS = (
    "compile_date",
    "start_date",
    "end_date",
    "target_week",
    "last_updated",
)

DAILY_DEMAND_CATEGORY_FIELDS = (
    "service_category",
    *DAYS,
    "total_weekly",
    "avg_daily",
    "demand_level",
)

DAILY_DEMAND_SUMMARY_FIELDS = (
    "Service Category",
    *DAYS,
    "Total Weekly Orders",
    "Avg Daily Orders",
    "Weekly Demand Level",
)


def provider_paths() -> tuple[str, ...]:
    working_hours = tuple(
        f"workingHours.{day}.{field}"
        for day in DAYS
        for field in ("isOpen", "start", "end")
    )
    documents = ("documents.status", "documents.verified") + tuple(
        f"documents.{category}[].{field}"
        for category in DOCUMENT_CATEGORIES
        for field in DOCUMENT_ITEM_FIELDS
    )
    return PROVIDER_BASE_PATHS + working_hours + documents + PROVIDER_EXTRACTED_PATHS


def daily_demand_paths() -> tuple[str, ...]:
    category_paths = tuple(
        f"by_category.<category>.{field}" for field in DAILY_DEMAND_CATEGORY_FIELDS
    )
    summary_paths = tuple(f"summary[].{field}" for field in DAILY_DEMAND_SUMMARY_FIELDS)
    return DAILY_DEMAND_TOP_PATHS + category_paths + summary_paths


PHASE2_PATHS = {
    "customers": CUSTOMER_PATHS,
    "providers": provider_paths(),
    "filter_requests": FILTER_REQUEST_PATHS,
    "daily_demand": daily_demand_paths(),
}


def observed_paths(node: str, records: dict[str, dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for record in records.values():
        paths.update(path for path, _value in iter_field_values(record, ""))
        if node == "daily_demand":
            categories = record.get("by_category")
            if isinstance(categories, dict):
                for category in categories.values():
                    if isinstance(category, dict):
                        paths.update(
                            path
                            for path, _value in iter_field_values(
                                category, "by_category.<category>"
                            )
                        )
    return paths


def verify_phase2_inventory(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    node_reports: dict[str, Any] = {}
    exact_snapshots = 0
    snapshot_failures: list[dict[str, str]] = []

    for node, expected_paths in PHASE2_PATHS.items():
        records = data.get(node)
        if records is None:
            node_reports[node] = {
                "record_count": 0,
                "node_present": False,
                "expected_paths": len(expected_paths),
                "observed_expected_paths": [],
                "optional_absent_paths": list(expected_paths),
                "all_source_paths_preserved": False,
            }
            continue

        observed = observed_paths(node, records)
        expected = set(expected_paths)
        for source_key, record in records.items():
            snapshot = build_snapshot(node, source_key, record)
            if (
                snapshot["source_key"] == source_key
                and snapshot["source_record"] == record
                and set(snapshot["source_record"]) == set(record)
                and snapshot["source_sha256"] == source_sha256(record)
            ):
                exact_snapshots += 1
            else:
                snapshot_failures.append(
                    {"source_node": node, "source_key": source_key}
                )

        node_reports[node] = {
            "record_count": len(records),
            "node_present": True,
            "expected_paths": len(expected_paths),
            "observed_expected_paths": sorted(expected & observed),
            "optional_absent_paths": sorted(expected - observed),
            "additional_source_paths": sorted(observed - expected),
            "all_source_paths_preserved": True,
        }

    provider_credibility_observed = any(
        "credibility" in record for record in data.get("providers", {}).values()
    )
    expected_records = sum(len(records) for records in data.values())
    missing_nodes = [
        node for node, report in node_reports.items() if not report["node_present"]
    ]
    return {
        "summary": {
            "expected_records": expected_records,
            "exact_snapshots": exact_snapshots,
            "snapshot_failures": len(snapshot_failures),
            "missing_nodes": missing_nodes,
            "provider_level_credibility_observed": provider_credibility_observed,
            "provider_level_credibility_policy": (
                "preserved verbatim when present; never fabricated when absent"
            ),
            "passed": not missing_nodes
            and not snapshot_failures
            and exact_snapshots == expected_records,
        },
        "nodes": node_reports,
        "issues": snapshot_failures,
    }
