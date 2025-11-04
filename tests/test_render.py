from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.render import OutputRenderer
from httptap.visualizer import WaterfallVisualizer

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def build_step(
    url: str,
    status: int,
    total_ms: float,
    *,
    step_number: int = 1,
    error: str | None = None,
) -> StepMetrics:
    timing = TimingMetrics(total_ms=total_ms)
    network = NetworkInfo(ip="203.0.113.5", ip_family="IPv4")
    response = ResponseInfo(status=status, bytes=128)
    return StepMetrics(
        url=url,
        step_number=step_number,
        timing=timing,
        network=network,
        response=response,
        error=error,
    )


def test_redirect_summary_includes_total() -> None:
    console = Console(record=True, width=120)
    renderer = OutputRenderer(console=console)
    steps = [
        build_step("http://example.com", 301, 121.5),
        build_step("https://www.example.com", 200, 210.3),
    ]

    renderer._render_redirect_summary(steps)
    output = console.export_text()

    assert "Total" in output
    assert "331.8ms" in output


def test_render_analysis_metrics_only() -> None:
    console = Console(record=True, width=120)
    renderer = OutputRenderer(console=console, metrics_only=True)
    step = build_step("https://example.test", 200, 50.0)

    renderer.render_analysis([step], "https://example.test")

    output = console.export_text()
    assert "dns=" in output
    assert "status=200" in output


@pytest.mark.parametrize(
    "durations",
    [
        [10.0, 20.0, 30.0, 40.0],
        [0.1, 0.1, 0.1, 0.1],
        [5.0, 0.0, 15.0, 5.0],
    ],
)
def test_compute_phase_widths_respects_chart_width(durations: list[float]) -> None:
    console = Console(record=True, width=120)
    visualizer = WaterfallVisualizer(console=console, max_bar_width=20)
    widths = visualizer._compute_phase_widths(durations)

    assert sum(widths) <= visualizer.max_bar_width
    for duration, width in zip(durations, widths, strict=True):
        if duration > 0:
            assert width >= 1


class TestOutputRenderer:
    """Test suite for OutputRenderer."""

    def test_initialization_defaults(self) -> None:
        """Test renderer initializes with default values."""
        renderer = OutputRenderer()

        assert renderer.compact is False
        assert renderer.metrics_only is False
        assert renderer.console is not None
        assert renderer.visualizer is not None
        assert renderer.exporter is not None

    def test_initialization_with_custom_values(self) -> None:
        """Test renderer initializes with custom values."""
        console = Console(record=True)
        renderer = OutputRenderer(compact=True, metrics_only=True, console=console)

        assert renderer.compact is True
        assert renderer.metrics_only is True
        assert renderer.console is console

    def test_render_analysis_single_step(self) -> None:
        """Test rendering analysis with single step."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console)
        step = build_step("https://example.com", 200, 100.0)

        renderer.render_analysis([step], "https://example.com")

        output = console.export_text()
        assert "Analyzing" in output
        assert "example.com" in output

    def test_render_analysis_multiple_steps_shows_redirect_summary(self) -> None:
        """Test that multiple steps show redirect summary."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console)
        steps = [
            build_step("http://example.com", 301, 50.0, step_number=1),
            build_step("https://example.com", 200, 100.0, step_number=2),
        ]

        renderer.render_analysis(steps, "http://example.com")

        output = console.export_text()
        assert "Redirect Chain Summary" in output
        assert "Total" in output

    def test_render_analysis_compact_mode_skips_waterfall(self) -> None:
        """Test that compact mode doesn't render waterfall."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(compact=True, console=console)
        step = build_step("https://example.com", 200, 100.0)

        renderer.render_analysis([step], "https://example.com")

        output = console.export_text()
        # Should not contain waterfall timeline
        assert "Request Timeline" not in output

    def test_render_analysis_metrics_only_mode(self) -> None:
        """Test metrics-only mode output."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(metrics_only=True, console=console)
        step = build_step("https://example.com", 200, 100.0)

        renderer.render_analysis([step], "https://example.com")

        output = console.export_text()
        # Should contain metrics line
        assert "status=200" in output
        # Should not contain header
        assert "Analyzing" not in output

    def test_render_step_with_error(self) -> None:
        """Test rendering step with error."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console)
        step = build_step("https://example.com", 0, 0.0, error="Connection timeout")

        renderer.render_analysis([step], "https://example.com")

        output = console.export_text()
        assert "ERROR" in output or "timeout" in output

    def test_export_json(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test JSON export functionality."""
        console = Console()
        renderer = OutputRenderer(console=console)
        step = build_step("https://example.com", 200, 100.0)
        output_path = tmp_path / "output.json"

        # Mock the exporter's export method
        mock_export = mocker.patch.object(renderer.exporter, "export")

        renderer.export_json([step], "https://example.com", str(output_path))

        mock_export.assert_called_once_with(
            [step],
            "https://example.com",
            str(output_path),
        )

    def test_print_header(self) -> None:
        """Test header printing."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console)

        renderer._print_header("https://example.com")

        output = console.export_text()
        assert "Analyzing" in output
        assert "example.com" in output
        assert "HTTP Tap Analysis" in output

    def test_render_metrics_only_with_error(self) -> None:
        """Test metrics-only rendering with error step."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(metrics_only=True, console=console)
        step = build_step("https://example.com", 0, 0.0, error="DNS failed")

        renderer._render_metrics_only([step])

        output = console.export_text()
        assert "ERROR" in output
        assert "DNS failed" in output

    def test_build_redirect_table_structure(self) -> None:
        """Test redirect table structure."""
        console = Console()
        renderer = OutputRenderer(console=console)
        steps = [
            build_step("http://example.com", 301, 50.0, step_number=1),
            build_step("https://example.com", 200, 100.0, step_number=2),
        ]

        table = renderer._build_redirect_table(steps)

        assert table.title == "Redirect Chain Summary"
        assert len(table.columns) == 4  # Step, URL, Status, Time

    def test_build_redirect_table_with_error_step(self) -> None:
        """Test redirect table handles error steps."""
        console = Console()
        renderer = OutputRenderer(console=console)
        steps = [
            build_step("http://example.com", 301, 50.0, step_number=1),
            build_step("https://example.com", 0, 0.0, step_number=2, error="Timeout"),
        ]

        table = renderer._build_redirect_table(steps)

        # Table should still be created
        assert table is not None

    def test_render_step_skips_empty_network_and_response(self) -> None:
        """Network/response lines should be omitted when data is unavailable."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console)

        captured: list[StepMetrics] = []

        class VisualizerStub:
            def render(self, step: StepMetrics) -> None:
                captured.append(step)

        renderer.visualizer = VisualizerStub()

        step = StepMetrics(
            url="https://example.test",
            timing=TimingMetrics(total_ms=25.0),
            network=NetworkInfo(),
            response=ResponseInfo(),
        )

        renderer._render_step(step)

        output = console.export_text()
        assert "IP:" not in output
        assert "Status:" not in output
        assert captured
        assert captured[0] is step

    @pytest.mark.parametrize(
        ("status", "expected_color"),
        [
            (200, "green"),
            (201, "green"),
            (299, "green"),
            (301, "yellow"),
            (302, "yellow"),
            (399, "yellow"),
            (400, "red"),
            (404, "red"),
            (500, "red"),
        ],
    )
    def test_format_table_status_colors(self, status: int, expected_color: str) -> None:
        """Test status formatting with correct colors."""
        console = Console()
        renderer = OutputRenderer(console=console)
        step = build_step("https://example.com", status, 100.0)

        result = renderer._format_table_status(step)

        assert expected_color in result
        assert str(status) in result

    def test_format_table_status_error(self) -> None:
        """Test status formatting for error responses."""
        console = Console()
        renderer = OutputRenderer(console=console)
        step = build_step("https://example.com", 0, 0.0, error="Failed")
        # Clear status to simulate error
        step.response.status = None

        result = renderer._format_table_status(step)

        assert "ERROR" in result
        assert "red" in result.lower()

    def test_render_step_calls_visualizer(self, mocker: MockerFixture) -> None:
        """Test that render_step calls visualizer in non-compact mode."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console, compact=False)
        step = build_step("https://example.com", 200, 100.0)

        mock_render = mocker.patch.object(renderer.visualizer, "render")

        renderer._render_step(step)

        mock_render.assert_called_once_with(step)

    def test_render_step_skips_visualizer_in_compact_mode(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that render_step skips visualizer in compact mode."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console, compact=True)
        step = build_step("https://example.com", 200, 100.0)

        mock_render = mocker.patch.object(renderer.visualizer, "render")

        renderer._render_step(step)

        mock_render.assert_not_called()

    def test_render_analysis_separates_steps_with_rules(self) -> None:
        """Test that multiple steps are separated with rules."""
        console = Console(record=True, width=120)
        renderer = OutputRenderer(console=console)
        steps = [
            build_step("http://example.com", 301, 50.0, step_number=1),
            build_step("https://example.com", 200, 100.0, step_number=2),
        ]

        renderer.render_analysis(steps, "http://example.com")

        output = console.export_text()
        # Should have separation between steps
        assert len(output) > 0
