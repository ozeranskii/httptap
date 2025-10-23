"""Timing collector implementations."""

from __future__ import annotations

import time

from httptap.constants import MS_IN_SECOND
from httptap.models import TimingMetrics


class PerfCounterTimingCollector:
    """High-precision timing collector using time.perf_counter()."""

    __slots__ = (
        "_dns_end",
        "_dns_start",
        "_end_time",
        "_request_start",
        "_start_time",
        "_ttfb_time",
    )

    def __init__(self) -> None:
        """Initialize timing collector with zeroed timestamps."""
        self._start_time = time.perf_counter()
        self._dns_start = 0.0
        self._dns_end = 0.0
        self._request_start = 0.0
        self._ttfb_time = 0.0
        self._end_time = 0.0

    def mark_dns_start(self) -> None:
        """Record the beginning of DNS resolution."""
        self._dns_start = time.perf_counter()

    def mark_dns_end(self) -> None:
        """Record the completion of DNS resolution."""
        self._dns_end = time.perf_counter()

    def mark_request_start(self) -> None:
        """Record the moment the HTTP request starts."""
        self._request_start = time.perf_counter()

    def mark_ttfb(self) -> None:
        """Record when the first response byte is received."""
        self._ttfb_time = time.perf_counter()

    def mark_request_end(self) -> None:
        """Record when the response body transfer completes."""
        self._end_time = time.perf_counter()

    def get_metrics(self) -> TimingMetrics:
        """Build a TimingMetrics instance populated with collected timings."""
        timing = TimingMetrics()
        timing.dns_ms = (self._dns_end - self._dns_start) * MS_IN_SECOND
        timing.total_ms = (self._end_time - self._start_time) * MS_IN_SECOND
        timing.ttfb_ms = (self._ttfb_time - self._start_time) * MS_IN_SECOND
        return timing
