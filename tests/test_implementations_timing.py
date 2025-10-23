"""Unit tests for timing collector implementation."""

from __future__ import annotations

import time

from httptap.implementations.timing import PerfCounterTimingCollector
from httptap.models import TimingMetrics


class TestPerfCounterTimingCollector:
    """Test suite for PerfCounterTimingCollector."""

    def test_initialization(self) -> None:
        """Test that collector initializes with zero values."""
        collector = PerfCounterTimingCollector()

        # Internal state should be initialized
        assert collector._dns_start == 0.0
        assert collector._dns_end == 0.0
        assert collector._request_start == 0.0
        assert collector._ttfb_time == 0.0
        assert collector._end_time == 0.0
        # Start time should be set
        assert collector._start_time > 0.0

    def test_mark_dns_start(self) -> None:
        """Test marking DNS start time."""
        collector = PerfCounterTimingCollector()
        initial_start = collector._start_time

        time.sleep(0.001)  # Small delay
        collector.mark_dns_start()

        assert collector._dns_start > initial_start
        assert collector._dns_start > 0.0

    def test_mark_dns_end(self) -> None:
        """Test marking DNS end time."""
        collector = PerfCounterTimingCollector()

        collector.mark_dns_start()
        time.sleep(0.001)  # Small delay
        collector.mark_dns_end()

        assert collector._dns_end > collector._dns_start

    def test_mark_request_start(self) -> None:
        """Test marking request start time."""
        collector = PerfCounterTimingCollector()

        time.sleep(0.001)
        collector.mark_request_start()

        assert collector._request_start > collector._start_time

    def test_mark_ttfb(self) -> None:
        """Test marking time to first byte."""
        collector = PerfCounterTimingCollector()

        collector.mark_request_start()
        time.sleep(0.001)
        collector.mark_ttfb()

        assert collector._ttfb_time > collector._request_start

    def test_mark_request_end(self) -> None:
        """Test marking request end time."""
        collector = PerfCounterTimingCollector()

        collector.mark_request_start()
        collector.mark_ttfb()
        time.sleep(0.001)
        collector.mark_request_end()

        assert collector._end_time > collector._ttfb_time

    def test_get_metrics_calculates_dns_ms(self) -> None:
        """Test that get_metrics calculates DNS duration correctly."""
        collector = PerfCounterTimingCollector()

        collector.mark_dns_start()
        time.sleep(0.005)  # 5ms delay
        collector.mark_dns_end()

        metrics = collector.get_metrics()

        assert metrics.dns_ms >= 4.0  # At least 4ms (allowing for timing variance)
        assert metrics.dns_ms < 10.0  # Less than 10ms

    def test_get_metrics_calculates_total_ms(self) -> None:
        """Test that get_metrics calculates total duration correctly."""
        collector = PerfCounterTimingCollector()

        time.sleep(0.005)  # 5ms delay from start
        collector.mark_request_end()

        metrics = collector.get_metrics()

        assert metrics.total_ms >= 4.0
        assert metrics.total_ms < 10.0

    def test_get_metrics_calculates_ttfb_ms(self) -> None:
        """Test that get_metrics calculates TTFB correctly."""
        collector = PerfCounterTimingCollector()

        time.sleep(0.003)
        collector.mark_ttfb()

        metrics = collector.get_metrics()

        assert metrics.ttfb_ms >= 2.0
        assert metrics.ttfb_ms < 10.0

    def test_get_metrics_returns_timing_metrics_instance(self) -> None:
        """Test that get_metrics returns TimingMetrics instance."""
        collector = PerfCounterTimingCollector()

        metrics = collector.get_metrics()

        assert isinstance(metrics, TimingMetrics)

    def test_get_metrics_with_no_marks_returns_zeros(self) -> None:
        """Test that get_metrics returns zero durations when no marks set."""
        collector = PerfCounterTimingCollector()

        metrics = collector.get_metrics()

        # DNS duration is 0 (end - start = 0 - 0)
        assert metrics.dns_ms == 0.0
        # When marks are not set, timing values can be negative or zero
        # This is expected behavior indicating improper timing collection

    def test_full_request_lifecycle(self) -> None:
        """Test complete request timing lifecycle."""
        collector = PerfCounterTimingCollector()

        # Simulate request flow
        collector.mark_dns_start()
        time.sleep(0.002)  # DNS lookup
        collector.mark_dns_end()

        collector.mark_request_start()
        time.sleep(0.003)  # Connection + request
        collector.mark_ttfb()

        time.sleep(0.002)  # Body transfer
        collector.mark_request_end()

        metrics = collector.get_metrics()

        # Verify all metrics are captured
        assert metrics.dns_ms > 0.0
        assert metrics.ttfb_ms > 0.0
        assert metrics.total_ms > 0.0
        # Total should be greater than DNS + other phases
        assert metrics.total_ms >= metrics.dns_ms

    def test_metrics_are_in_milliseconds(self) -> None:
        """Test that all timing values are in milliseconds."""
        collector = PerfCounterTimingCollector()

        collector.mark_dns_start()
        time.sleep(0.01)  # 10ms
        collector.mark_dns_end()

        metrics = collector.get_metrics()

        # 10ms delay should result in ~10ms DNS time
        assert 8.0 <= metrics.dns_ms <= 15.0

    def test_multiple_get_metrics_calls_return_same_values(self) -> None:
        """Test that calling get_metrics multiple times returns consistent values."""
        collector = PerfCounterTimingCollector()

        collector.mark_dns_start()
        collector.mark_dns_end()
        collector.mark_request_end()

        metrics1 = collector.get_metrics()
        time.sleep(0.001)
        metrics2 = collector.get_metrics()

        # Values should be the same (based on same internal timestamps)
        assert metrics1.dns_ms == metrics2.dns_ms
        assert metrics1.total_ms == metrics2.total_ms
        assert metrics1.ttfb_ms == metrics2.ttfb_ms

    def test_connect_and_tls_not_measured_by_collector(self) -> None:
        """Test that collector doesn't measure connect/TLS (those come from trace)."""
        collector = PerfCounterTimingCollector()

        collector.mark_dns_start()
        collector.mark_dns_end()
        collector.mark_request_start()
        collector.mark_ttfb()
        collector.mark_request_end()

        metrics = collector.get_metrics()

        # Connect and TLS are not measured by this collector
        assert metrics.connect_ms == 0.0
        assert metrics.tls_ms == 0.0
        # Wait and xfer are derived, not measured directly
        assert metrics.wait_ms == 0.0
        assert metrics.xfer_ms == 0.0
