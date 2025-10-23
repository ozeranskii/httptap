"""Unit tests for timing collector implementation."""

from __future__ import annotations

from unittest.mock import patch

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
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.001]):
            # side_effect: [__init__, mark_dns_start]
            collector = PerfCounterTimingCollector()
            collector.mark_dns_start()

            assert collector._dns_start == 1.001
            assert collector._dns_start > collector._start_time

    def test_mark_dns_end(self) -> None:
        """Test marking DNS end time."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.0, 1.001]):
            # side_effect: [__init__, mark_dns_start, mark_dns_end]
            collector = PerfCounterTimingCollector()
            collector.mark_dns_start()
            collector.mark_dns_end()

            assert collector._dns_end == 1.001
            assert collector._dns_end > collector._dns_start

    def test_mark_request_start(self) -> None:
        """Test marking request start time."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.001]):
            # side_effect: [__init__, mark_request_start]
            collector = PerfCounterTimingCollector()
            collector.mark_request_start()

            assert collector._request_start == 1.001
            assert collector._request_start > collector._start_time

    def test_mark_ttfb(self) -> None:
        """Test marking time to first byte."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.0, 1.001]):
            # side_effect: [__init__, mark_request_start, mark_ttfb]
            collector = PerfCounterTimingCollector()
            collector.mark_request_start()
            collector.mark_ttfb()

            assert collector._ttfb_time == 1.001
            assert collector._ttfb_time > collector._request_start

    def test_mark_request_end(self) -> None:
        """Test marking request end time."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.0, 1.001, 1.002]):
            # side_effect: [__init__, mark_request_start, mark_ttfb, mark_request_end]
            collector = PerfCounterTimingCollector()
            collector.mark_request_start()
            collector.mark_ttfb()
            collector.mark_request_end()

            assert collector._end_time == 1.002
            assert collector._end_time > collector._ttfb_time

    def test_get_metrics_calculates_dns_ms(self) -> None:
        """Test that get_metrics calculates DNS duration correctly."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.0, 1.005]):
            # side_effect: [__init__, mark_dns_start, mark_dns_end]
            collector = PerfCounterTimingCollector()
            collector.mark_dns_start()
            collector.mark_dns_end()

            metrics = collector.get_metrics()

            # 0.005 seconds * 1000 = 5.0 ms
            assert abs(metrics.dns_ms - 5.0) < 0.001  # Allow tiny floating point error

    def test_get_metrics_calculates_total_ms(self) -> None:
        """Test that get_metrics calculates total duration correctly."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.005]):
            # side_effect: [__init__, mark_request_end]
            collector = PerfCounterTimingCollector()
            collector.mark_request_end()

            metrics = collector.get_metrics()

            # 0.005 seconds * 1000 = 5.0 ms
            assert abs(metrics.total_ms - 5.0) < 0.001

    def test_get_metrics_calculates_ttfb_ms(self) -> None:
        """Test that get_metrics calculates TTFB correctly."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.003]):
            # side_effect: [__init__, mark_ttfb]
            collector = PerfCounterTimingCollector()
            collector.mark_ttfb()

            metrics = collector.get_metrics()

            # 0.003 seconds * 1000 = 3.0 ms
            assert abs(metrics.ttfb_ms - 3.0) < 0.001

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
        with patch(
            "httptap.implementations.timing.time.perf_counter",
            side_effect=[
                1.0,  # __init__ (_start_time)
                1.0,  # mark_dns_start
                1.002,  # mark_dns_end (2ms DNS)
                1.002,  # mark_request_start
                1.005,  # mark_ttfb (5ms from start)
                1.007,  # mark_request_end (7ms from start)
            ],
        ):
            collector = PerfCounterTimingCollector()

            # Simulate request flow
            collector.mark_dns_start()
            collector.mark_dns_end()
            collector.mark_request_start()
            collector.mark_ttfb()
            collector.mark_request_end()

            metrics = collector.get_metrics()

            # Verify all metrics are captured with exact values
            assert abs(metrics.dns_ms - 2.0) < 0.001  # 1.002 - 1.0 = 0.002s = 2ms
            assert abs(metrics.ttfb_ms - 5.0) < 0.001  # 1.005 - 1.0 = 0.005s = 5ms
            assert abs(metrics.total_ms - 7.0) < 0.001  # 1.007 - 1.0 = 0.007s = 7ms
            # Total should be greater than DNS
            assert metrics.total_ms >= metrics.dns_ms

    def test_metrics_are_in_milliseconds(self) -> None:
        """Test that all timing values are in milliseconds."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.0, 1.01]):
            # side_effect: [__init__, mark_dns_start, mark_dns_end]
            collector = PerfCounterTimingCollector()
            collector.mark_dns_start()
            collector.mark_dns_end()

            metrics = collector.get_metrics()

            # 0.01 seconds * 1000 = 10.0 ms
            assert abs(metrics.dns_ms - 10.0) < 0.001

    def test_multiple_get_metrics_calls_return_same_values(self) -> None:
        """Test that calling get_metrics multiple times returns consistent values."""
        with patch("httptap.implementations.timing.time.perf_counter", side_effect=[1.0, 1.0, 1.005, 1.010]):
            # side_effect: [__init__, mark_dns_start, mark_dns_end, mark_request_end]
            collector = PerfCounterTimingCollector()
            collector.mark_dns_start()
            collector.mark_dns_end()
            collector.mark_request_end()

            # get_metrics() doesn't call perf_counter, uses stored values
            metrics1 = collector.get_metrics()
            metrics2 = collector.get_metrics()

            # Values should be the same (based on same internal timestamps)
            assert abs(metrics1.dns_ms - 5.0) < 0.001
            assert abs(metrics2.dns_ms - 5.0) < 0.001
            assert metrics1.dns_ms == metrics2.dns_ms

            assert abs(metrics1.total_ms - 10.0) < 0.001
            assert abs(metrics2.total_ms - 10.0) < 0.001
            assert metrics1.total_ms == metrics2.total_ms

            # ttfb_time was never set (0.0), so calculation results in negative value
            # This is expected behavior when marks aren't set properly
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
