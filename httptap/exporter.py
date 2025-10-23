"""Data export functionality for HTTP request analysis.

This module handles exporting analysis data to various formats,
starting with JSON export capability.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

from rich.console import Console

from .interfaces import Exporter
from .models import StepMetrics


class SummaryExport(TypedDict):
    """Summary statistics included with exported analysis."""

    total_time_ms: float
    final_status: int | None
    final_url: str
    final_bytes: int
    errors: int


class ExportPayload(TypedDict):
    """Payload structure persisted to the JSON report."""

    initial_url: str
    total_steps: int
    steps: list[dict[str, Any]]
    summary: SummaryExport


class JSONExporter(Exporter):
    """Exports HTTP analysis data to JSON format.

    Handles serialization of step metrics and summary information
    to structured JSON files.

    Attributes:
        console: Rich console for user feedback.

    """

    __slots__ = ("console",)

    def __init__(self, console: Console) -> None:
        """Initialize JSON exporter.

        Args:
            console: Rich console instance.

        """
        self.console = console

    def export(
        self,
        steps: Sequence[StepMetrics],
        initial_url: str,
        output_path: str,
    ) -> None:
        """Export analysis data to JSON file.

        Creates a structured JSON file with all step metrics,
        timing information, and summary data.

        Args:
            steps: Sequence of step metrics to export.
            initial_url: Initial URL that was analyzed.
            output_path: Path to output JSON file.

        Raises:
            IOError: If file cannot be written.

        """
        data = self._build_export_data(steps, initial_url)
        self._write_json_file(data, output_path)
        self._print_success(output_path)

    def _build_export_data(
        self,
        steps: Sequence[StepMetrics],
        initial_url: str,
    ) -> ExportPayload:
        """Build export data structure.

        Args:
            steps: Sequence of step metrics.
            initial_url: Initial URL.

        Returns:
            Dictionary ready for JSON serialization.

        """
        return {
            "initial_url": initial_url,
            "total_steps": len(steps),
            "steps": [step.to_dict() for step in steps],
            "summary": self._build_summary(steps, initial_url),
        }

    @staticmethod
    def _build_summary(
        steps: Sequence[StepMetrics],
        initial_url: str,
    ) -> SummaryExport:
        """Build summary section of export data.

        Args:
            steps: Sequence of step metrics.
            initial_url: Initial URL.

        Returns:
            Summary dictionary.

        """
        successful_steps = [s for s in steps if not s.has_error]

        return {
            "total_time_ms": sum(s.timing.total_ms for s in successful_steps),
            "final_status": (steps[-1].response.status if steps and not steps[-1].has_error else None),
            "final_url": steps[-1].url if steps else initial_url,
            "final_bytes": (steps[-1].response.bytes if steps and not steps[-1].has_error else 0),
            "errors": sum(1 for s in steps if s.has_error),
        }

    @staticmethod
    def _write_json_file(data: ExportPayload, output_path: str) -> None:
        """Write data to JSON file.

        Args:
            data: Data to serialize.
            output_path: Output file path.

        Raises:
            IOError: If file cannot be written.

        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _print_success(self, output_path: str) -> None:
        """Print success message.

        Args:
            output_path: Path where file was written.

        """
        self.console.print(f"\n[green]✓ Exported analysis to {output_path}[/green]")
