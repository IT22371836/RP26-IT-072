from __future__ import annotations

import math
import threading
import time
from typing import Any

from app.schemas.common import utc_now

LATENCY_BUCKETS_MS = (5.0, 20.0, 50.0, 100.0, 250.0, 500.0, 1000.0)


class Component4RuntimeTelemetry:
    """Bounded, process-local operational counters with no request or user data."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._started_at = utc_now()
            self._started_monotonic = time.monotonic()
            self._requests_total = 0
            self._successful_requests = 0
            self._client_errors = 0
            self._server_errors = 0
            self._cache_hits = 0
            self._fresh_rankings = 0
            self._latency_total_ms = 0.0
            self._latency_maximum_ms = 0.0
            self._latency_buckets = {self._bucket_label(value): 0 for value in LATENCY_BUCKETS_MS}
            self._latency_buckets["gt_1000_ms"] = 0

    @staticmethod
    def _bucket_label(upper_bound_ms: float) -> str:
        return f"le_{int(upper_bound_ms)}_ms"

    def record(
        self,
        *,
        status_code: int,
        duration_ms: float,
        cached: bool | None,
    ) -> None:
        if not math.isfinite(duration_ms) or duration_ms < 0:
            raise ValueError("duration_ms must be a finite non-negative value")
        with self._lock:
            self._requests_total += 1
            if 200 <= status_code < 400:
                self._successful_requests += 1
            elif 400 <= status_code < 500:
                self._client_errors += 1
            else:
                self._server_errors += 1
            if cached is True:
                self._cache_hits += 1
            elif cached is False:
                self._fresh_rankings += 1
            self._latency_total_ms += duration_ms
            self._latency_maximum_ms = max(self._latency_maximum_ms, duration_ms)
            for upper_bound in LATENCY_BUCKETS_MS:
                if duration_ms <= upper_bound:
                    self._latency_buckets[self._bucket_label(upper_bound)] += 1
                    break
            else:
                self._latency_buckets["gt_1000_ms"] += 1

    def snapshot(self, component_version: str) -> dict[str, Any]:
        with self._lock:
            requests_total = self._requests_total
            completed_rankings = self._cache_hits + self._fresh_rankings
            return {
                "scope": "process_local",
                "component_version": component_version,
                "started_at": self._started_at,
                "uptime_seconds": max(0.0, time.monotonic() - self._started_monotonic),
                "requests_total": requests_total,
                "successful_requests": self._successful_requests,
                "client_errors": self._client_errors,
                "server_errors": self._server_errors,
                "cache_hits": self._cache_hits,
                "fresh_rankings": self._fresh_rankings,
                "cache_hit_ratio": (
                    self._cache_hits / completed_rankings if completed_rankings else 0.0
                ),
                "average_latency_ms": (
                    self._latency_total_ms / requests_total if requests_total else 0.0
                ),
                "maximum_latency_ms": self._latency_maximum_ms,
                "latency_buckets": dict(self._latency_buckets),
                "contains_personal_data": False,
                "reset_on_process_restart": True,
            }


component4_runtime_telemetry = Component4RuntimeTelemetry()
