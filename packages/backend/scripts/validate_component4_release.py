from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.components.component4.schemas import Component4RankRequest  # noqa: E402
from app.components.component4.service import Component4RankingEngine  # noqa: E402
from app.core.config import Settings  # noqa: E402

DEFAULT_CONFIG = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "artifacts"
    / "release-v1"
    / "release_config.json"
)
DEFAULT_REPORT_DIR = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "reports"
    / "release-v1"
)
CATF_MANIFEST = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "artifacts"
    / "catf-v1"
    / "manifest.json"
)
EVALUATION_MANIFEST = (
    REPOSITORY_ROOT
    / "ml"
    / "components"
    / "component4"
    / "artifacts"
    / "evaluation-v1"
    / "manifest.json"
)


class ReleaseValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseValidationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def file_metadata(path: Path) -> dict[str, Any]:
    return {
        "path": relative_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"release config is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(
        payload.get("version") == "component4-release-evidence-v1",
        "release evidence version changed",
    )
    benchmark = payload.get("benchmark", {})
    thresholds = payload.get("thresholds", {})
    require(int(benchmark.get("request_count", 0)) >= 100, "request count is too small")
    require(int(benchmark.get("candidate_count", 0)) == 10, "candidate count must be ten")
    require(int(benchmark.get("top_k", 0)) == 5, "top_k must be five")
    require(int(benchmark.get("concurrency_workers", 0)) > 0, "workers must be positive")
    require(
        all(float(value) > 0 for value in thresholds.values()),
        "performance thresholds must be positive",
    )
    return payload


def percentile(values: list[float], quantile: float) -> float:
    require(bool(values), "at least one timing sample is required")
    require(0 <= quantile <= 1, "quantile must be in 0..1")
    ordered = sorted(float(value) for value in values)
    require(all(math.isfinite(value) and value >= 0 for value in ordered), "bad timing")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_payloads(
    provider_ids: list[str],
    *,
    request_count: int,
    candidate_count: int,
    top_k: int,
    stride: int,
) -> list[Component4RankRequest]:
    require(len(provider_ids) >= candidate_count, "provider snapshot is too small")
    maximum_start = len(provider_ids) - candidate_count + 1
    payloads = []
    for index in range(request_count):
        start = (index * stride) % maximum_start
        payloads.append(
            Component4RankRequest(
                request_id=f"RRELEASE{index:06d}",
                provider_ids=provider_ids[start : start + candidate_count],
                top_k=top_k,
            )
        )
    return payloads


def timed_rank(
    engine: Component4RankingEngine,
    payload: Component4RankRequest,
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter_ns()
    result = engine.rank(payload, [])
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return result, elapsed_ms


def run_benchmark(
    engine: Component4RankingEngine,
    payloads: list[Component4RankRequest],
    *,
    workers: int,
) -> dict[str, Any]:
    sequential_started = time.perf_counter()
    sequential_pairs = [timed_rank(engine, payload) for payload in payloads]
    sequential_elapsed = time.perf_counter() - sequential_started
    sequential_results = [result for result, _ in sequential_pairs]
    sequential_latencies = [latency for _, latency in sequential_pairs]

    concurrent_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        concurrent_pairs = list(
            executor.map(
                lambda payload: timed_rank(engine, payload),
                payloads,
            )
        )
    concurrent_elapsed = time.perf_counter() - concurrent_started
    concurrent_results = [result for result, _ in concurrent_pairs]
    concurrent_latencies = [latency for _, latency in concurrent_pairs]

    repeated = engine.rank(payloads[0], [])
    reversed_payload = payloads[0].model_copy(
        update={"provider_ids": list(reversed(payloads[0].provider_ids))}
    )
    reversed_result = engine.rank(reversed_payload, [])
    deterministic_reordering = (
        repeated["run_id"] == reversed_result["run_id"]
        and repeated["providers"] == reversed_result["providers"]
    )
    concurrent_determinism = sequential_results == concurrent_results
    subset_preserved = all(
        {
            provider["provider_id"]
            for provider in result["providers"]
        }.issubset(payload.provider_ids)
        for payload, result in zip(payloads, sequential_results, strict=True)
    )
    top5_preserved = all(
        result["output_count"] <= 5 and len(result["providers"]) <= 5
        for result in sequential_results
    )
    return {
        "sequential_results": sequential_results,
        "checks": {
            "sequential_determinism": deterministic_reordering,
            "concurrent_determinism": concurrent_determinism,
            "candidate_subset_preserved": subset_preserved,
            "top5_limit_preserved": top5_preserved,
        },
        "sequential": summarize_timings(sequential_latencies, sequential_elapsed),
        "concurrent": summarize_timings(concurrent_latencies, concurrent_elapsed),
    }


def summarize_timings(latencies_ms: list[float], elapsed_seconds: float) -> dict[str, float]:
    return {
        "p50_ms": percentile(latencies_ms, 0.50),
        "p95_ms": percentile(latencies_ms, 0.95),
        "p99_ms": percentile(latencies_ms, 0.99),
        "maximum_ms": max(latencies_ms),
        "total_ms": elapsed_seconds * 1000,
        "operations_per_second": len(latencies_ms) / elapsed_seconds,
    }


def threshold_checks(
    cold_load_ms: float,
    benchmark: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, bool]:
    return {
        "cold_load_within_limit": cold_load_ms <= float(thresholds["cold_load_max_ms"]),
        "sequential_p95_within_limit": benchmark["sequential"]["p95_ms"]
        <= float(thresholds["sequential_p95_max_ms"]),
        "concurrent_p95_within_limit": benchmark["concurrent"]["p95_ms"]
        <= float(thresholds["concurrent_p95_max_ms"]),
        "sequential_throughput_within_limit": benchmark["sequential"][
            "operations_per_second"
        ]
        >= float(thresholds["sequential_min_operations_per_second"]),
        "concurrent_throughput_within_limit": benchmark["concurrent"][
            "operations_per_second"
        ]
        >= float(thresholds["concurrent_min_operations_per_second"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def run(
    config_path: Path,
    report_dir: Path,
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    config = load_config(config_path)
    settings = Settings()
    load_started = clock()
    engine = Component4RankingEngine(
        settings.component4_artifact_dir,
        settings.component4_category_priors_path,
    )
    engine.load()
    cold_load_ms = (clock() - load_started) * 1000

    benchmark_config = config["benchmark"]
    payloads = build_payloads(
        sorted(engine.provider_scores),
        request_count=int(benchmark_config["request_count"]),
        candidate_count=int(benchmark_config["candidate_count"]),
        top_k=int(benchmark_config["top_k"]),
        stride=int(benchmark_config["provider_stride"]),
    )
    benchmark = run_benchmark(
        engine,
        payloads,
        workers=int(benchmark_config["concurrency_workers"]),
    )
    checks = {
        "artifact_integrity": engine.ready,
        "provider_snapshot_complete": len(engine.provider_scores) == 10_000,
        **benchmark["checks"],
        **threshold_checks(cold_load_ms, benchmark, config["thresholds"]),
    }
    require(all(checks.values()), f"release checks failed: {checks}")

    report = {
        "phase": 10,
        "release_evidence_version": config["version"],
        "status": "passed",
        "component4_operationally_ready": True,
        "component2_connected": False,
        "production_ready": False,
        "production_status": "component4_ready_awaiting_component2_uat",
        "checks": checks,
        "performance": {
            "cold_load_ms": cold_load_ms,
            "sequential": benchmark["sequential"],
            "concurrent": benchmark["concurrent"],
        },
        "thresholds": {
            key: float(value)
            for key, value in config["thresholds"].items()
        },
        "benchmark": {
            "request_count": len(payloads),
            "candidate_count": int(benchmark_config["candidate_count"]),
            "top_k": int(benchmark_config["top_k"]),
            "concurrency_workers": int(benchmark_config["concurrency_workers"]),
            "ranking_failures": 0,
        },
        "versions": engine.versions,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "validated_test_boundaries": [
            "JWT authentication",
            "service-request ownership isolation",
            "tampered artifact rejection",
            "MongoDB persistence failure response",
            "deterministic cached-run persistence",
            "development fixture blocked in production",
        ],
        "remaining_production_gates": [
            "real Component 2 Top-10 API adapter",
            "Component 2 to Component 4 integration UAT",
            "production infrastructure load test with shared MongoDB",
        ],
    }
    report_path = report_dir / "release_readiness.json"
    write_json(report_path, report)
    manifest = {
        "release_evidence_version": config["version"],
        "status": "passed",
        "inputs": {
            "release_config": file_metadata(config_path),
            "catf_manifest": file_metadata(CATF_MANIFEST),
            "evaluation_manifest": file_metadata(EVALUATION_MANIFEST),
        },
        "reports": {
            "release_readiness": file_metadata(report_path),
        },
        "component4_operationally_ready": True,
        "production_ready": False,
    }
    write_json(report_dir / "manifest.json", manifest)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> None:
    args = parse_args()
    run(args.config, args.report_dir)


if __name__ == "__main__":
    main()
