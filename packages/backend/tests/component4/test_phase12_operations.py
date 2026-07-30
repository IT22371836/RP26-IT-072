import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from app.components.component4.telemetry import Component4RuntimeTelemetry
from scripts.load_test_component4_api import (
    ACCEPTANCE_CONFIG_VERSION,
    DEFAULT_CONCURRENCY,
    DEFAULT_MAXIMUM_ERROR_RATE,
    DEFAULT_MAXIMUM_P95_MS,
    DEFAULT_MINIMUM_THROUGHPUT_RPS,
    DEFAULT_REQUESTS,
    DEFAULT_TIMEOUT_SECONDS,
    percentile,
    validate_response,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_runtime_telemetry_is_bounded_and_contains_no_personal_data() -> None:
    telemetry = Component4RuntimeTelemetry()
    telemetry.record(status_code=200, duration_ms=4.0, cached=False)
    telemetry.record(status_code=200, duration_ms=15.0, cached=True)
    telemetry.record(status_code=404, duration_ms=40.0, cached=None)
    telemetry.record(status_code=503, duration_ms=1200.0, cached=None)

    snapshot = telemetry.snapshot("component4-phase12")

    assert snapshot["component_version"] == "component4-phase12"
    assert isinstance(snapshot["started_at"], datetime)
    assert snapshot["requests_total"] == 4
    assert snapshot["successful_requests"] == 2
    assert snapshot["client_errors"] == 1
    assert snapshot["server_errors"] == 1
    assert snapshot["cache_hits"] == 1
    assert snapshot["fresh_rankings"] == 1
    assert snapshot["cache_hit_ratio"] == 0.5
    assert snapshot["average_latency_ms"] == pytest.approx(314.75)
    assert snapshot["maximum_latency_ms"] == 1200.0
    assert sum(snapshot["latency_buckets"].values()) == 4
    assert snapshot["latency_buckets"]["gt_1000_ms"] == 1
    assert snapshot["contains_personal_data"] is False
    assert snapshot["reset_on_process_restart"] is True
    assert "user_id" not in snapshot
    assert "request_id" not in snapshot
    assert "provider_id" not in snapshot


def test_runtime_telemetry_rejects_invalid_latency() -> None:
    telemetry = Component4RuntimeTelemetry()

    with pytest.raises(ValueError, match="finite non-negative"):
        telemetry.record(status_code=200, duration_ms=float("nan"), cached=False)


def test_external_load_test_percentiles_are_deterministic() -> None:
    assert percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.5
    assert percentile([4.0, 1.0, 3.0, 2.0], 0.95) == pytest.approx(3.85)


def test_phase12_acceptance_config_matches_the_load_test_defaults() -> None:
    config_path = (
        REPOSITORY_ROOT
        / "ml"
        / "components"
        / "component4"
        / "artifacts"
        / "acceptance-v1"
        / "acceptance_config.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    workload = config["external_api_load_test"]

    assert config["version"] == ACCEPTANCE_CONFIG_VERSION
    assert workload == {
        "requests": DEFAULT_REQUESTS,
        "concurrency": DEFAULT_CONCURRENCY,
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "maximum_p95_ms": DEFAULT_MAXIMUM_P95_MS,
        "minimum_throughput_requests_per_second": DEFAULT_MINIMUM_THROUGHPUT_RPS,
        "maximum_error_rate": DEFAULT_MAXIMUM_ERROR_RATE,
    }
    assert config["production_ready"] is False


def test_external_load_test_validates_top5_subset_and_lineage() -> None:
    payload = {
        "source": "component2",
        "request_id": "RLOAD1",
        "user_id": "ULOAD1",
        "component_version": "component2-v1",
        "model_version": "context-v1",
        "provider_ids": ["P00001", "P00002"],
    }
    response = httpx.Response(
        200,
        json={
            "request_id": "RLOAD1",
            "user_id": "ULOAD1",
            "providers": [{"provider_id": "P00002"}],
            "handoff": {
                key: payload[key]
                for key in (
                    "source",
                    "request_id",
                    "user_id",
                    "component_version",
                    "model_version",
                )
            },
        },
    )

    assert validate_response(response, payload=payload) is None

    invalid = httpx.Response(
        200,
        json={
            **response.json(),
            "providers": [{"provider_id": "P99999"}],
        },
    )
    assert validate_response(invalid, payload=payload) == (
        "response introduced a non-candidate provider"
    )
