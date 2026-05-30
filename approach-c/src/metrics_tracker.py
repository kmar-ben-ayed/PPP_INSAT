"""Thread-safe in-memory metrics tracker for API requests."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class MetricsSnapshot:
    """Snapshot of aggregated metrics."""

    request_count: int
    avg_latency_ms: float
    ttft_ms: float
    throughput_tokens_per_sec: float
    error_rate: float
    uptime_percent: float
    concurrent_requests_handled: int
    cold_start_ms: float
    rate_limit_hits: int
    cost_eur: float


class MetricsTracker:
    """Aggregate and expose performance metrics with thread safety."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.perf_counter()
        self._request_count = 0
        self._error_count = 0
        self._rate_limit_hits = 0
        self._total_latency_ms = 0.0
        self._total_ttft_ms = 0.0
        self._total_tokens = 0
        self._active_requests = 0
        self._max_concurrent = 0
        self._degraded_since: float | None = None
        self._degraded_seconds = 0.0
        self._cold_start_ms = 0.0

    def start_request(self) -> float:
        """Mark the start of a request and return a start timestamp."""
        now = time.perf_counter()
        with self._lock:
            self._active_requests += 1
            if self._active_requests > self._max_concurrent:
                self._max_concurrent = self._active_requests
        return now

    def end_request(
        self,
        latency_ms: float,
        ttft_ms: float,
        tokens: int,
        error: bool = False,
        rate_limit: bool = False,
    ) -> None:
        """Finalize a request and update aggregate metrics."""
        with self._lock:
            self._request_count += 1
            if error:
                self._error_count += 1
            if rate_limit:
                self._rate_limit_hits += 1
            self._total_latency_ms += latency_ms
            self._total_ttft_ms += ttft_ms
            self._total_tokens += tokens
            self._active_requests = max(0, self._active_requests - 1)

    def update_degraded(self, is_degraded: bool) -> None:
        """Track time spent in degraded state."""
        now = time.perf_counter()
        with self._lock:
            if is_degraded:
                if self._degraded_since is None:
                    self._degraded_since = now
            elif self._degraded_since is not None:
                self._degraded_seconds += now - self._degraded_since
                self._degraded_since = None

    def set_cold_start_ms(self, cold_start_ms: float) -> None:
        """Set cold start time (process start to server ready)."""
        with self._lock:
            self._cold_start_ms = max(0.0, cold_start_ms)

    def snapshot(self) -> MetricsSnapshot:
        """Return a metrics snapshot for reporting."""
        with self._lock:
            now = time.perf_counter()
            uptime_seconds = now - self._start_time
            avg_latency_ms = (
                self._total_latency_ms / self._request_count if self._request_count else 0.0
            )
            avg_ttft_ms = (
                self._total_ttft_ms / self._request_count if self._request_count else 0.0
            )
            total_latency_seconds = self._total_latency_ms / 1000 if self._total_latency_ms else 0.0
            throughput = (
                self._total_tokens / total_latency_seconds if total_latency_seconds > 0 else 0.0
            )
            error_rate = self._error_count / self._request_count if self._request_count else 0.0
            cold_start_ms = self._cold_start_ms
            degraded_seconds = self._degraded_seconds
            if self._degraded_since is not None:
                degraded_seconds += now - self._degraded_since
            if uptime_seconds <= 0:
                uptime_percent = 100.0
            else:
                uptime_percent = max(
                    0.0, min(100.0, ((uptime_seconds - degraded_seconds) / uptime_seconds) * 100)
                )
            return MetricsSnapshot(
                request_count=self._request_count,
                avg_latency_ms=round(avg_latency_ms, 2),
                ttft_ms=round(avg_ttft_ms, 2),
                throughput_tokens_per_sec=round(throughput, 4),
                error_rate=round(error_rate, 4),
                uptime_percent=round(uptime_percent, 2),
                concurrent_requests_handled=self._max_concurrent,
                cold_start_ms=round(cold_start_ms, 2),
                rate_limit_hits=self._rate_limit_hits,
                cost_eur=0.0,
            )
