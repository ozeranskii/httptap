"""Regression tests for machine-readable metrics output on narrow streams."""

import unittest
from io import StringIO

from rich.console import Console

from httptap.formatters import format_metrics_line
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.render import OutputRenderer


class TestMetricsNoWrap(unittest.TestCase):
    """Metrics records must not depend on the output stream width."""

    def test_success_and_error_records_remain_single_lines(self) -> None:
        """Preserve complete records, including long error messages."""
        success = StepMetrics(
            url="https://example.test/",
            step_number=1,
            timing=TimingMetrics(total_ms=123.4),
            network=NetworkInfo(ip="203.0.113.5", ip_family="IPv4"),
            response=ResponseInfo(status=200, bytes=128),
        )
        error = StepMetrics(
            url="https://example.test/",
            step_number=2,
            error="Connection failed " + "details " * 30,
        )
        expected = [
            format_metrics_line(success),
            f"Step 2: ERROR - {error.error}",
        ]
        for width in (20, 80, 120):
            with self.subTest(width=width):
                output = StringIO()
                console = Console(file=output, width=width, force_terminal=False, color_system=None)
                OutputRenderer(console=console, metrics_only=True).render_analysis(
                    [success, error], success.url
                )
                self.assertEqual(output.getvalue().splitlines(), expected)
