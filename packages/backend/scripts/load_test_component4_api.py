from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ACCEPTANCE_CONFIG_VERSION = "component4-phase12-acceptance-v1"
DEFAULT_REQUESTS = 100
DEFAULT_CONCURRENCY = 10
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAXIMUM_P95_MS = 1000.0
DEFAULT_MINIMUM_THROUGHPUT_RPS = 5.0
DEFAULT_MAXIMUM_ERROR_RATE = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise the deployed Component 4 HTTP and MongoDB path with an authenticated "
            "handoff. The bearer token is read from an environment variable and never written "
            "to the report."
        )
    )
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--token-env", default="COMPONENT4_LOAD_TEST_TOKEN")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--provider-ids", nargs="+", required=True)
    parser.add_argument("--source", choices=("component2", "development_fixture"), required=True)
    parser.add_argument("--component-version", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--maximum-p95-ms", type=float, default=DEFAULT_MAXIMUM_P95_MS)
    parser.add_argument(
        "--minimum-throughput-rps",
        type=float,
        default=DEFAULT_MINIMUM_THROUGHPUT_RPS,
    )
    parser.add_argument("--maximum-error-rate", type=float, default=DEFAULT_MAXIMUM_ERROR_RATE)
    parser.add_argument("--force-recalculate", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def percentile(values: list[float], quantile: float) -> float:
    require(bool(values), "latency list must not be empty")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def validate_args(args: argparse.Namespace) -> None:
    require(1 <= len(args.provider_ids) <= 10, "provider IDs must contain one to ten items")
    require(len(args.provider_ids) == len(set(args.provider_ids)), "provider IDs must be unique")
    require(args.requests >= 1, "requests must be positive")
    require(1 <= args.concurrency <= args.requests, "concurrency must be within request count")
    require(args.timeout_seconds > 0, "timeout must be positive")
    require(args.maximum_p95_ms > 0, "maximum P95 must be positive")
    require(args.minimum_throughput_rps > 0, "minimum throughput must be positive")
    require(0 <= args.maximum_error_rate <= 1, "maximum error rate must be between zero and one")
    if args.source == "component2":
        require(
            args.component_version != "not-component2"
            and args.model_version != "not-component2",
            "real Component 2 load tests require real version identifiers",
        )


def validate_response(
    response: httpx.Response,
    *,
    payload: dict[str, Any],
) -> str | None:
    if response.status_code != 200:
        return f"HTTP {response.status_code}"
    try:
        body = response.json()
    except json.JSONDecodeError:
        return "response is not JSON"
    providers = body.get("providers")
    handoff = body.get("handoff")
    if not isinstance(providers, list) or len(providers) > 5:
        return "response violates Top-5"
    candidate_ids = set(payload["provider_ids"])
    if any(provider.get("provider_id") not in candidate_ids for provider in providers):
        return "response introduced a non-candidate provider"
    expected_handoff = {
        key: payload[key]
        for key in (
            "source",
            "request_id",
            "user_id",
            "component_version",
            "model_version",
        )
    }
    if handoff != expected_handoff:
        return "response changed handoff lineage"
    if body.get("request_id") != payload["request_id"] or body.get("user_id") != payload["user_id"]:
        return "response changed request or user identity"
    return None


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        print(
            f"Authentication token is missing from environment variable {args.token_env}",
            file=sys.stderr,
        )
        return 2

    payload = {
        "source": args.source,
        "request_id": args.request_id,
        "user_id": args.user_id,
        "component_version": args.component_version,
        "model_version": args.model_version,
        "provider_ids": args.provider_ids,
        "top_k": 5,
        "force_recalculate": args.force_recalculate,
    }
    url = f"{args.base_url.rstrip('/')}/component4/rank"
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(headers=headers, timeout=args.timeout_seconds) as client:
        warmup = client.post(url, json=payload)
        warmup_error = validate_response(warmup, payload=payload)
        if warmup_error:
            print(f"Warm-up failed: {warmup_error}", file=sys.stderr)
            return 1

        def execute(_: int) -> tuple[float, str | None]:
            started = time.perf_counter()
            try:
                response = client.post(url, json=payload)
                error = validate_response(response, payload=payload)
            except httpx.HTTPError as exception:
                error = type(exception).__name__
            return (time.perf_counter() - started) * 1000, error

        benchmark_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            results = list(executor.map(execute, range(args.requests)))
        elapsed_seconds = time.perf_counter() - benchmark_started

    latencies = [latency for latency, _ in results]
    errors = [error for _, error in results if error is not None]
    error_rate = len(errors) / args.requests
    throughput = args.requests / elapsed_seconds
    p95_ms = percentile(latencies, 0.95)
    checks = {
        "zero_contract_failures": not errors,
        "p95_within_threshold": p95_ms <= args.maximum_p95_ms,
        "throughput_within_threshold": throughput >= args.minimum_throughput_rps,
        "error_rate_within_threshold": error_rate <= args.maximum_error_rate,
    }
    report = {
        "phase": 12,
        "report_version": "component4-external-api-load-test-v1",
        "acceptance_config_version": ACCEPTANCE_CONFIG_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed" if all(checks.values()) else "failed",
        "target": args.base_url,
        "workload": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "candidate_count": len(args.provider_ids),
            "top_k": 5,
            "source": args.source,
            "force_recalculate": args.force_recalculate,
        },
        "results": {
            "successful_requests": args.requests - len(errors),
            "failed_requests": len(errors),
            "error_rate": error_rate,
            "throughput_requests_per_second": throughput,
            "latency_ms": {
                "minimum": min(latencies),
                "mean": statistics.fmean(latencies),
                "p50": percentile(latencies, 0.50),
                "p95": p95_ms,
                "p99": percentile(latencies, 0.99),
                "maximum": max(latencies),
            },
            "error_summary": {
                error: errors.count(error) for error in sorted(set(errors))
            },
        },
        "thresholds": {
            "maximum_p95_ms": args.maximum_p95_ms,
            "minimum_throughput_requests_per_second": args.minimum_throughput_rps,
            "maximum_error_rate": args.maximum_error_rate,
        },
        "checks": checks,
        "limitations": [
            "The report applies only to the supplied deployed API and MongoDB environment.",
            "A development_fixture run is not evidence of real Component 2 integration.",
            "The bearer token and provider, request, and user identifiers are not written.",
        ],
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
