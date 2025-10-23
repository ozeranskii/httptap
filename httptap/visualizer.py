"""Waterfall visualization for HTTP request timelines.

This module handles the visual representation of request phases
as a cascading waterfall diagram.
"""

import itertools
import math

from rich.console import Console

from .interfaces import Visualizer
from .models import StepMetrics


class WaterfallVisualizer(Visualizer):
    """Creates waterfall diagrams showing request phase timelines."""

    __slots__ = ("console", "max_bar_width")

    BAR_CHAR = "⠿"

    def __init__(self, console: Console, max_bar_width: int = 80) -> None:
        """Configure the visualizer with a console and maximum bar width."""
        self.console = console
        self.max_bar_width = max_bar_width

    def render(self, step: StepMetrics) -> None:
        """Render a waterfall timeline for the provided step if data is valid."""
        if step.has_error or step.timing.total_ms <= 0:
            return

        phases = self._get_phases(step)
        durations = [duration for _, duration, _ in phases]
        bar_widths = self._compute_phase_widths(durations)
        used_width = sum(bar_widths) or 1
        scale = step.timing.total_ms / used_width

        self.console.print("\n  [bold]Request Timeline:[/bold]")

        current_position_chars = 0
        for (label, duration, color), bar_width in zip(phases, bar_widths, strict=True):
            current_position_chars = self._render_phase(
                label,
                duration,
                color,
                current_position_chars,
                bar_width,
            )

        self._render_total(step.timing.total_ms, scale)

    @staticmethod
    def _get_phases(step: StepMetrics) -> list[tuple[str, float, str]]:
        phases = [
            ("DNS", step.timing.dns_ms, "cyan"),
            ("Connect", step.timing.connect_ms, "green"),
            ("TLS", step.timing.tls_ms, "magenta"),
            ("Wait", step.timing.wait_ms, "blue"),
            ("Transfer", step.timing.xfer_ms, "red"),
        ]
        filtered = [phase for phase in phases if phase[1] > 0.0]
        return filtered or phases[:1]

    def _render_phase(
        self,
        label: str,
        duration: float,
        color: str,
        start_chars: int,
        bar_chars: int,
    ) -> int:
        max_width = self.max_bar_width
        start_chars = min(start_chars, max_width)
        bar_chars = max(bar_chars, 0)
        if start_chars >= max_width:
            start_chars = max_width - 1 if max_width else 0
            offset_str = " " * start_chars
            bar_chars = 1 if max_width else 0
        else:
            offset_str = " " * start_chars
        end_chars = min(max_width, start_chars + bar_chars)
        bar = self.BAR_CHAR * (end_chars - start_chars)

        label_field = f"{label}: "
        timing_str = f"{duration:.1f} ms"
        line = f"  {offset_str}[{color}]{bar}[/{color}] [{color}]{label_field}{timing_str}[/{color}]"
        self.console.print(line)

        return end_chars

    def _compute_phase_widths(self, durations: list[float]) -> list[int]:  # noqa: C901, PLR0912
        positives = [i for i, d in enumerate(durations) if d > 0]
        if not positives:
            return [0] * len(durations)

        width = max(self.max_bar_width, len(positives))
        total = sum(durations[i] for i in positives)
        scale = total / width if total else 1.0

        bar_counts: list[int] = [0] * len(durations)
        remainders: list[float] = [0.0] * len(durations)

        for _ in range(32):
            bar_counts = []
            remainders = []
            total_chars = 0
            for d in durations:
                if d <= 0 or scale <= 0:
                    bar_counts.append(0)
                    remainders.append(0.0)
                else:
                    raw = d / scale
                    count = max(1, math.ceil(raw))
                    bar_counts.append(count)
                    remainders.append(raw - math.floor(raw))
                    total_chars += count
            if total_chars <= width:
                break
            scale *= 1.1

        total_chars = sum(bar_counts)
        if total_chars < width:
            slack = width - total_chars
            order = list(positives)
            order.sort(key=lambda i: remainders[i], reverse=True)
            if not order:
                order = positives
            for idx in itertools.cycle(order):
                if slack <= 0:
                    break
                bar_counts[idx] += 1
                slack -= 1

        elif total_chars > width:
            over = total_chars - width
            order = [i for i in positives if bar_counts[i] > 1]
            order.sort(key=lambda i: (remainders[i], bar_counts[i]))
            for idx in order:
                while over > 0 and bar_counts[idx] > 1:
                    bar_counts[idx] -= 1
                    over -= 1
                if over <= 0:
                    break

        return bar_counts

    def _render_total(self, total_ms: float, scale: float) -> None:
        total_str = f"{total_ms:.1f}ms"
        scale_info = f"(1 char ≈ {scale:.2f}ms)"
        total_line = f"\n  [bold]Total:[/bold] [bold cyan]{total_str}[/bold cyan] [dim]{scale_info}[/dim]"
        self.console.print(total_line)
