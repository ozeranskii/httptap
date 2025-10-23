"""Output rendering orchestration for HTTP request analysis.

This module coordinates various output formatters and visualizers
to present analysis results to the user.
"""

from collections.abc import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .constants import (
    HTTP_REDIRECT_MAX,
    HTTP_REDIRECT_MIN,
    HTTP_SUCCESS_MAX,
    HTTP_SUCCESS_MIN,
)
from .exporter import JSONExporter
from .formatters import (
    format_error,
    format_metrics_line,
    format_network_info,
    format_response_info,
    format_step_header,
)
from .interfaces import Exporter, Visualizer
from .models import StepMetrics
from .visualizer import WaterfallVisualizer


class OutputRenderer:
    """Orchestrates output rendering for HTTP analysis.

    Coordinates formatters, visualizers, and exporters to present
    analysis results in various formats (full, compact, metrics-only).

    Single Responsibility: Coordinate output components.

    Attributes:
        compact: Enable compact output mode.
        metrics_only: Enable metrics-only output mode.
        console: Rich console for output.
        visualizer: Waterfall timeline visualizer.
        exporter: JSON data exporter.

    """

    __slots__ = ("compact", "console", "exporter", "metrics_only", "visualizer")

    def __init__(
        self,
        *,
        compact: bool = False,
        metrics_only: bool = False,
        console: Console | None = None,
        visualizer: Visualizer | None = None,
        exporter: Exporter | None = None,
    ) -> None:
        """Initialize output renderer.

        Args:
            compact: Use compact single-line output.
            metrics_only: Use minimal machine-readable output.
            console: Custom console instance for output.
            visualizer: Custom visualizer implementation.
            exporter: Custom exporter implementation.

        """
        self.compact = compact
        self.metrics_only = metrics_only
        self.console = console or Console()
        self.visualizer = visualizer or WaterfallVisualizer(self.console)
        self.exporter = exporter or JSONExporter(self.console)

    def render_analysis(self, steps: Sequence[StepMetrics], initial_url: str) -> None:
        """Render complete analysis output.

        Args:
            steps: Sequence of step metrics to render.
            initial_url: Initial URL that was analyzed.

        """
        if self.metrics_only:
            self._render_metrics_only(steps)
            return

        self._print_header(initial_url)

        for index, step in enumerate(steps):
            self._render_step(step)
            if index < len(steps) - 1:
                self.console.print(Rule(style="dim"))
                self.console.print()

        if len(steps) > 1:
            self._render_redirect_summary(steps)

    def export_json(
        self,
        steps: Sequence[StepMetrics],
        initial_url: str,
        output_path: str,
    ) -> None:
        """Export analysis data to JSON file.

        Args:
            steps: Sequence of step metrics to export.
            initial_url: Initial URL that was analyzed.
            output_path: Path to output JSON file.

        """
        self.exporter.export(steps, initial_url, output_path)

    def _print_header(self, initial_url: str) -> None:
        """Print analysis header with Rich panel.

        Args:
            initial_url: URL being analyzed.

        """
        header_text = Text()
        header_text.append("🔍 ", style="bold blue")
        header_text.append("Analyzing: ", style="bold blue")
        header_text.append(initial_url, style="cyan underline")

        panel = Panel(
            header_text,
            title="[bold blue]HTTP Tap Analysis[/bold blue]",
            border_style="blue",
            padding=(0, 1),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def _render_step(self, step: StepMetrics) -> None:
        """Render a single analysis step.

        Args:
            step: Step metrics to render.

        """
        # Header
        header_panel = Panel.fit(
            format_step_header(step),
            border_style="cyan",
            padding=(0, 1),
        )
        self.console.print(header_panel)

        # Handle errors with Rich panel
        if step.has_error:
            error_panel = format_error(step)
            self.console.print(error_panel)
            return

        # Network info
        network_line = format_network_info(step)
        if network_line:
            self.console.print(network_line)

        # Response info
        response_line = format_response_info(step)
        if response_line:
            self.console.print(response_line)

        # Waterfall (unless compact mode)
        if not self.compact:
            self.visualizer.render(step)

    def _render_metrics_only(self, steps: Sequence[StepMetrics]) -> None:
        """Render minimal machine-readable output.

        Args:
            steps: Sequence of step metrics.

        """
        for step in steps:
            if step.has_error:
                self.console.print(f"Step {step.step_number}: ERROR - {step.error}")
            else:
                self.console.print(format_metrics_line(step))

    def _render_redirect_summary(self, steps: Sequence[StepMetrics]) -> None:
        """Render redirect chain summary table.

        Args:
            steps: Sequence of step metrics (redirect chain).

        """
        table = self._build_redirect_table(steps)
        self.console.print()
        self.console.print(table)

    def _build_redirect_table(self, steps: Sequence[StepMetrics]) -> Table:
        """Build redirect summary table.

        Args:
            steps: Sequence of step metrics.

        Returns:
            Rich Table instance.

        """
        table = Table(title="Redirect Chain Summary", show_lines=False)
        table.add_column("Step", style="cyan", no_wrap=True, justify="center")
        table.add_column("URL", style="blue", overflow="fold")
        table.add_column("Status", style="yellow", justify="center")
        table.add_column("Time", style="green", justify="right")

        for step in steps:
            status_str = self._format_table_status(step)
            time_str = f"{step.timing.total_ms:.1f}ms" if not step.has_error else "N/A"

            table.add_row(
                str(step.step_number),
                step.url,
                status_str,
                time_str,
            )

        total_time = sum(step.timing.total_ms for step in steps if not step.has_error)
        table.add_section()
        table.add_row(
            "",
            "Total",
            "",
            f"{total_time:.1f}ms",
            style="bold",
        )

        return table

    @staticmethod
    def _format_table_status(step: StepMetrics) -> str:
        """Format status for table display.

        Args:
            step: Step metrics.

        Returns:
            Formatted status string with color markup.

        """
        if not step.response.status:
            return "[red]ERROR[/red]"

        status = step.response.status
        if HTTP_SUCCESS_MIN <= status <= HTTP_SUCCESS_MAX:
            style = "green"
        elif HTTP_REDIRECT_MIN <= status <= HTTP_REDIRECT_MAX:
            style = "yellow"
        else:
            style = "red"

        return f"[{style}]{status}[/{style}]"
