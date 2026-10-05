"""Prometheus textfile exporter for HTTP timing metrics."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape

from .utils import url_hostname

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.console import Console

    from .models import StepMetrics

_PHASES = ("dns", "connect", "tls", "ttfb", "wait", "xfer", "total")


class PrometheusExporter:
    """Export request timings in the Prometheus textfile collector format."""

    __slots__ = ("console",)

    def __init__(self, console: Console) -> None:
        """Initialize the exporter.

        Args:
            console: Console used for export status messages.

        """
        self.console = console

    def export(self, steps: Sequence[StepMetrics], output_path: str) -> None:
        """Write metrics to ``output_path`` atomically.

        The exported duration values are in seconds, following Prometheus
        naming conventions. ``step`` distinguishes redirect-chain requests;
        no URL label is emitted to avoid unbounded label cardinality.

        Args:
            steps: Request steps to export.
            output_path: Destination textfile path.

        Raises:
            OSError: If the destination cannot be written.

        """
        self._write_textfile(self._render(steps), Path(output_path))
        self.console.print(f"\n[green]✓ Exported Prometheus metrics to {escape(output_path)}[/green]")

    @staticmethod
    def _render(steps: Sequence[StepMetrics], now: float | None = None) -> str:
        """Render steps as Prometheus text exposition format.

        Every sample carries a ``host`` label (hostname only, never the path or
        query) so several probes can share one textfile directory without
        producing duplicate series. Failed steps export only
        ``httptap_request_success 0``; their zeroed timings would otherwise look
        like a very fast success.
        """
        lines = [
            "# HELP httptap_request_success Whether the request step completed without a network error.",
            "# TYPE httptap_request_success gauge",
            "# HELP httptap_request_duration_seconds HTTP request timing by phase.",
            "# TYPE httptap_request_duration_seconds gauge",
            "# HELP httptap_response_status_code HTTP response status code.",
            "# TYPE httptap_response_status_code gauge",
            "# HELP httptap_response_body_size_bytes HTTP response body size.",
            "# TYPE httptap_response_body_size_bytes gauge",
            "# HELP httptap_last_run_timestamp_seconds Unix time when httptap wrote this file.",
            "# TYPE httptap_last_run_timestamp_seconds gauge",
        ]
        for step in steps:
            labels = f'host="{_label_value(url_hostname(step.url))}",step="{step.step_number}"'
            lines.append(f"httptap_request_success{{{labels}}} {0 if step.has_error else 1}")
            if step.has_error:
                continue

            for phase in _PHASES:
                value_ms = getattr(step.timing, f"{phase}_ms")
                lines.append(f'httptap_request_duration_seconds{{{labels},phase="{phase}"}} {value_ms / 1000:.12g}')
            if step.response.status is not None:
                lines.append(f"httptap_response_status_code{{{labels}}} {step.response.status}")
            lines.append(f"httptap_response_body_size_bytes{{{labels}}} {step.response.bytes}")

        if steps:
            host = _label_value(url_hostname(steps[0].url))
            timestamp = time.time() if now is None else now
            lines.append(f'httptap_last_run_timestamp_seconds{{host="{host}"}} {timestamp:.3f}')

        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_textfile(content: str, output_path: Path) -> None:
        """Write a textfile atomically so collectors never observe partial data."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as output_file:
                output_file.write(content)
            temporary_path.chmod(0o644)
            temporary_path.replace(output_path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise


def _label_value(value: str) -> str:
    """Escape a Prometheus label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
