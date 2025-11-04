"""Unit tests for waterfall visualizer."""

from __future__ import annotations

import sys
from io import StringIO
from typing import TYPE_CHECKING, no_type_check

from rich.console import Console
from typing_extensions import Self

from httptap.models import StepMetrics, TimingMetrics
from httptap.visualizer import WaterfallVisualizer

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest


class TestWaterfallVisualizer:
    """Test suite for WaterfallVisualizer."""

    def test_initialization(self) -> None:
        """Test visualizer initialization."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=100)

        assert visualizer.console is console
        assert visualizer.max_bar_width == 100

    def test_render_skips_steps_with_errors(self) -> None:
        """Test that render skips steps that have errors."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        step = StepMetrics(error="Connection failed")

        visualizer.render(step)

        # Should not render anything for error steps
        result = output.getvalue()
        assert "Request Timeline" not in result

    def test_render_skips_steps_with_zero_timing(self) -> None:
        """Test that render skips steps with zero or negative total_ms."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(total_ms=0.0)
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        assert "Request Timeline" not in result

    def test_render_outputs_timeline_header(self) -> None:
        """Test that render outputs timeline header."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(
            dns_ms=10.0,
            connect_ms=20.0,
            tls_ms=30.0,
            ttfb_ms=80.0,
            total_ms=100.0,
        )
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        assert "Request Timeline" in result

    def test_render_outputs_all_phases(self) -> None:
        """Test that render outputs all timing phases."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(
            dns_ms=10.0,
            connect_ms=20.0,
            tls_ms=30.0,
            ttfb_ms=80.0,
            total_ms=100.0,
        )
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        assert "DNS" in result
        assert "Connect" in result
        assert "TLS" in result
        assert "Wait" in result
        assert "Transfer" in result

    def test_render_outputs_total_time(self) -> None:
        """Test that render outputs total time."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(
            dns_ms=50.0,
            connect_ms=50.0,
            ttfb_ms=150.0,
            total_ms=200.0,
        )
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        assert "Total" in result
        assert "200.0ms" in result

    def test_render_omits_zero_duration_phase(self) -> None:
        """TLS line should be omitted when duration is zero."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(
            dns_ms=15.0,
            connect_ms=40.0,
            tls_ms=0.0,
            ttfb_ms=60.0,
            total_ms=90.0,
        )
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        assert "DNS" in result
        assert "Connect" in result
        assert "TLS" not in result
        assert "Wait" in result

    def test_get_phases_returns_correct_structure(self) -> None:
        """Test that _get_phases returns correct phase structure."""
        console = Console()
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(
            dns_ms=10.5,
            connect_ms=20.3,
            tls_ms=30.1,
            wait_ms=15.2,
            xfer_ms=5.9,
        )
        step = StepMetrics(timing=timing)

        phases = visualizer._get_phases(step)

        assert len(phases) == 5
        assert phases[0] == ("DNS", 10.5, "cyan")
        assert phases[1] == ("Connect", 20.3, "green")
        assert phases[2] == ("TLS", 30.1, "magenta")
        assert phases[3] == ("Wait", 15.2, "blue")
        assert phases[4] == ("Transfer", 5.9, "red")

    def test_get_phases_filters_zero_duration(self) -> None:
        """Phases with zero duration are omitted from rendering."""
        console = Console()
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(
            dns_ms=5.0,
            connect_ms=0.0,
            tls_ms=0.0,
            wait_ms=12.0,
            xfer_ms=3.0,
        )
        step = StepMetrics(timing=timing)

        phases = visualizer._get_phases(step)

        labels = [label for label, _duration, _color in phases]
        assert labels == ["DNS", "Wait", "Transfer"]

    def test_compute_phase_widths_all_zero_returns_zeros(self) -> None:
        """Test that _compute_phase_widths returns zeros for zero durations."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        durations = [0.0, 0.0, 0.0, 0.0, 0.0]
        widths = visualizer._compute_phase_widths(durations)

        assert widths == [0, 0, 0, 0, 0]

    def test_compute_phase_widths_distributes_width(self) -> None:
        """Test that _compute_phase_widths distributes width proportionally."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        durations = [10.0, 20.0, 30.0, 20.0, 20.0]
        widths = visualizer._compute_phase_widths(durations)

        # All widths should be positive
        assert all(w > 0 for w in widths)
        # Total should not exceed max_bar_width
        assert sum(widths) <= 80
        # Proportions should roughly match (larger durations get more chars)
        assert widths[2] >= widths[0]  # 30ms should get more than 10ms

    def test_compute_phase_widths_adds_slack_for_remaining_width(self) -> None:
        """Slack branch should assign leftover characters to longest remainder."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=40)

        durations = [1000.0, 1.0]
        widths = visualizer._compute_phase_widths(durations)

        assert sum(widths) == 40
        assert widths[1] >= 2  # slack assigned to smaller duration

    def test_compute_phase_widths_reduces_overflow_when_iterations_exhausted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Overflow branch should trim counts when scaling loop hits limit."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=5)

        def single_iteration(_n: int) -> list[int]:
            return [0]

        module_dict = sys.modules["httptap.visualizer"].__dict__
        monkeypatch.setitem(module_dict, "range", single_iteration)

        durations = [500.0, 400.0, 300.0]
        widths = visualizer._compute_phase_widths(durations)

        assert sum(widths) <= visualizer.max_bar_width
        assert all(w >= 1 for w in widths)

    def test_compute_phase_widths_respects_max_width(self) -> None:
        """Test that _compute_phase_widths respects max_bar_width."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=40)

        durations = [100.0, 200.0, 150.0, 100.0, 50.0]
        widths = visualizer._compute_phase_widths(durations)

        # Total should not exceed max_bar_width
        assert sum(widths) <= 40

    def test_compute_phase_widths_gives_at_least_one_char_to_positive_durations(
        self,
    ) -> None:
        """Test that positive durations get at least 1 character."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        durations = [0.1, 0.0, 100.0, 0.0, 0.2]
        widths = visualizer._compute_phase_widths(durations)

        # Small positive values should get at least 1 char
        assert widths[0] >= 1
        assert widths[2] >= 1
        assert widths[4] >= 1
        # Zero values should get 0 chars
        assert widths[1] == 0
        assert widths[3] == 0

    def test_compute_phase_widths_handles_single_phase(self) -> None:
        """Test _compute_phase_widths with single non-zero phase."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        durations = [0.0, 0.0, 100.0, 0.0, 0.0]
        widths = visualizer._compute_phase_widths(durations)

        # Single phase should use full width
        assert widths[2] <= 80
        assert widths[2] > 0
        # Others should be zero
        assert widths[0] == 0
        assert widths[1] == 0
        assert widths[3] == 0
        assert widths[4] == 0

    def test_render_phase_returns_correct_end_position(self) -> None:
        """Test that _render_phase returns correct end position."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        end_pos = visualizer._render_phase(
            label="DNS",
            duration=10.5,
            color="cyan",
            start_chars=0,
            bar_chars=10,
        )

        assert end_pos == 10

    def test_render_phase_respects_max_width(self) -> None:
        """Test that _render_phase respects max_bar_width."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=40)

        # Try to render beyond max_width
        end_pos = visualizer._render_phase(
            label="Connect",
            duration=50.0,
            color="green",
            start_chars=35,
            bar_chars=20,
        )

        # Should be capped at max_bar_width
        assert end_pos <= 40

    def test_render_phase_handles_zero_bar_width(self) -> None:
        """Test that _render_phase handles zero bar width."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        end_pos = visualizer._render_phase(
            label="TLS",
            duration=0.0,
            color="magenta",
            start_chars=10,
            bar_chars=0,
        )

        # End position should equal start position
        assert end_pos == 10

    def test_render_phase_outputs_label_and_duration(self) -> None:
        """Test that _render_phase outputs label and duration."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        visualizer._render_phase(
            label="Wait",
            duration=25.7,
            color="blue",
            start_chars=20,
            bar_chars=15,
        )

        result = output.getvalue()
        assert "Wait" in result
        assert "25.7 ms" in result

    def test_render_total_outputs_timing_info(self) -> None:
        """Test that _render_total outputs timing information."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        visualizer._render_total(total_ms=123.4, scale=1.5)

        result = output.getvalue()
        assert "Total" in result
        assert "123.4ms" in result
        assert "1.50ms" in result  # Scale info

    def test_render_handles_very_small_timings(self) -> None:
        """Test render handles very small timing values correctly."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        timing = TimingMetrics(
            dns_ms=0.1,
            connect_ms=0.2,
            tls_ms=0.3,
            ttfb_ms=1.0,
            total_ms=1.5,
        )
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        # Should not raise exceptions
        visualizer.render(step)

        result = output.getvalue()
        assert "Request Timeline" in result

    def test_render_handles_very_large_timings(self) -> None:
        """Test render handles very large timing values correctly."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        timing = TimingMetrics(
            dns_ms=1000.0,
            connect_ms=2000.0,
            tls_ms=3000.0,
            ttfb_ms=10000.0,
            total_ms=15000.0,
        )
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        # Should not raise exceptions
        visualizer.render(step)

        result = output.getvalue()
        assert "Request Timeline" in result
        assert "15000.0ms" in result

    def test_render_with_negative_total_skips_rendering(self) -> None:
        """Test that negative total_ms skips rendering."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(total_ms=-10.0)
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        assert result == ""

    def test_visualizer_uses_bar_character(self) -> None:
        """Test that visualizer uses the correct bar character."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console)

        timing = TimingMetrics(dns_ms=10.0, total_ms=10.0)
        timing.calculate_derived()
        step = StepMetrics(timing=timing)

        visualizer.render(step)

        result = output.getvalue()
        # Should contain the bar character
        assert WaterfallVisualizer.BAR_CHAR in result

    def test_render_phase_when_start_exceeds_max_width(self) -> None:
        """Test _render_phase when start position exceeds max_bar_width."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=20)

        # Start position exceeds max width
        end_pos = visualizer._render_phase(
            label="Transfer",
            duration=10.0,
            color="red",
            start_chars=25,
            bar_chars=5,
        )

        # Should cap at max_width and still render 1 char
        assert end_pos <= 20
        result = output.getvalue()
        assert "Transfer" in result

    def test_render_phase_at_exactly_max_width(self) -> None:
        """Test _render_phase when start is exactly at max_bar_width."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=30)

        end_pos = visualizer._render_phase(
            label="Wait",
            duration=5.0,
            color="blue",
            start_chars=30,
            bar_chars=10,
        )

        # Should handle edge case gracefully
        assert end_pos <= 30
        result = output.getvalue()
        assert "Wait" in result

    def test_render_phase_with_zero_max_width(self) -> None:
        """Test _render_phase with max_bar_width=0."""
        output = StringIO()
        console = Console(file=output, width=120, legacy_windows=False)
        visualizer = WaterfallVisualizer(console, max_bar_width=0)

        end_pos = visualizer._render_phase(
            label="DNS",
            duration=10.0,
            color="cyan",
            start_chars=0,
            bar_chars=5,
        )

        # Should handle zero max_width
        assert end_pos == 0
        result = output.getvalue()
        assert "DNS" in result

    def test_compute_phase_widths_requires_iterative_scaling(self) -> None:
        """Test _compute_phase_widths with values requiring iterative scaling."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=10)

        # Many large values that need iterative scale adjustment
        durations = [100.0, 100.0, 100.0, 100.0, 100.0]
        widths = visualizer._compute_phase_widths(durations)

        # Should converge to max_bar_width
        assert sum(widths) <= 10
        # All should get at least 1 char
        assert all(w >= 1 for w in widths)

    def test_compute_phase_widths_with_under_allocation(self) -> None:
        """Test _compute_phase_widths when total is under max_bar_width (slack)."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=100)

        # Small durations that won't fill max width initially
        durations = [1.0, 2.0, 1.0, 0.0, 1.0]
        widths = visualizer._compute_phase_widths(durations)

        # Should distribute slack to reach max_bar_width
        assert sum(widths) <= 100
        # Non-zero durations should get chars
        assert widths[0] > 0
        assert widths[1] > 0
        assert widths[2] > 0
        assert widths[4] > 0
        # Zero duration gets zero chars
        assert widths[3] == 0

    def test_compute_phase_widths_with_over_allocation(self) -> None:
        """Test _compute_phase_widths when total exceeds max_bar_width."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=5)

        # Many phases that would exceed max width
        durations = [10.0, 10.0, 10.0, 10.0, 10.0]
        widths = visualizer._compute_phase_widths(durations)

        # Should reduce to fit max_bar_width
        assert sum(widths) <= 5
        # All should still get at least 1 char
        assert all(w >= 1 for w in widths)

    def test_compute_phase_widths_with_mixed_very_small_and_large(self) -> None:
        """Test _compute_phase_widths with very small and very large values."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=80)

        # One huge value and tiny values
        durations = [0.01, 1000.0, 0.02, 0.0, 0.01]
        widths = visualizer._compute_phase_widths(durations)

        # Large value should get most chars
        assert widths[1] > widths[0]
        assert widths[1] > widths[2]
        assert widths[1] > widths[4]
        # Small positive values should still get at least 1
        assert widths[0] >= 1
        assert widths[2] >= 1
        assert widths[4] >= 1
        # Zero gets zero
        assert widths[3] == 0

    def test_compute_phase_widths_recovers_when_order_cleared(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """list(positives) returning an empty sequence should fall back safely."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=20)

        class ClearingList(list[int]):
            cleared = False

            @no_type_check
            def sort(self, *args: object, **kwargs: object) -> None:
                super().sort(*args, **kwargs)
                self.clear()
                type(self).cleared = True

        def clearing_list(iterable: list[int]) -> ClearingList:
            return ClearingList(iterable)

        module_dict = sys.modules["httptap.visualizer"].__dict__
        monkeypatch.setitem(module_dict, "list", clearing_list)
        monkeypatch.setattr("httptap.visualizer.math.ceil", lambda value: int(value))

        durations = [12.0, 6.0]
        widths = visualizer._compute_phase_widths(durations)

        assert ClearingList.cleared is True
        assert sum(widths) == visualizer.max_bar_width

    def test_compute_phase_widths_slack_branch_uses_cycle(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Slack allocation should iterate with itertools.cycle."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=30)

        cycle_calls: list[list[int]] = []

        def fake_cycle(order: list[int]) -> Iterator[int]:
            cycle_calls.append(list(order))

            def generator() -> Iterator[int]:
                while True:
                    yield from order

            return generator()

        monkeypatch.setattr("httptap.visualizer.math.ceil", lambda value: int(value))
        monkeypatch.setattr("httptap.visualizer.itertools.cycle", fake_cycle)

        durations = [15.0, 5.0]
        widths = visualizer._compute_phase_widths(durations)

        assert cycle_calls  # slack branch exercised
        assert sum(widths) == visualizer.max_bar_width

    def test_compute_phase_widths_overflow_branch_trims_counts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Overflow reduction should trim counts down to fit max width."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=6)

        module_dict = sys.modules["httptap.visualizer"].__dict__
        monkeypatch.setattr("httptap.visualizer.math.ceil", lambda value: int(value) + 2)
        monkeypatch.setitem(module_dict, "range", lambda _n: [0])

        durations = [20.0, 18.0, 16.0]
        widths = visualizer._compute_phase_widths(durations)

        assert sum(widths) <= visualizer.max_bar_width
        assert any(width == 1 for width in widths)

    def test_compute_phase_widths_slack_cycle_can_exhaust(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Slack allocation loop should handle iterators that terminate."""
        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=25)

        def empty_cycle(_order: list[int]) -> Iterator[int]:
            return iter(())

        monkeypatch.setattr("httptap.visualizer.math.ceil", lambda value: int(value))
        monkeypatch.setattr("httptap.visualizer.itertools.cycle", empty_cycle)

        widths = visualizer._compute_phase_widths([12.0, 6.0])

        assert sum(widths) < visualizer.max_bar_width

    def test_compute_phase_widths_overflow_loop_can_complete(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Overflow trimming loop should tolerate counts that never shrink."""
        import builtins

        console = Console()
        visualizer = WaterfallVisualizer(console, max_bar_width=6)

        module_dict = sys.modules["httptap.visualizer"].__dict__
        orig_sum = builtins.sum

        class NonReducible(int):
            def __new__(cls, value: int) -> Self:  # pragma: no cover - defensive
                return int.__new__(cls, value)

            def __gt__(self, _other: object) -> bool:
                return False

        def fake_sum(values: list[int]) -> int:
            total = orig_sum(values)
            for index, val in enumerate(values):
                values[index] = NonReducible(val)
            return total

        monkeypatch.setitem(module_dict, "sum", fake_sum)
        monkeypatch.setitem(module_dict, "range", lambda _n: [0])
        monkeypatch.setattr("httptap.visualizer.math.ceil", lambda value: int(value) + 2)

        widths = visualizer._compute_phase_widths([25.0, 20.0, 15.0])

        assert all(isinstance(width, NonReducible) for width in widths)
        assert sum(int(width) for width in widths) > visualizer.max_bar_width

    def test_compute_phase_widths_empty_order_fallback(self) -> None:
        """Test _compute_phase_widths handles empty order edge case."""
        console = Console()
        # Use very small max_width to trigger slack distribution
        visualizer = WaterfallVisualizer(console, max_bar_width=50)

        # Durations that create specific remainder pattern
        durations = [10.0, 10.0, 10.0, 0.0, 0.0]
        widths = visualizer._compute_phase_widths(durations)

        # Should handle distribution without errors
        assert sum(widths) <= 50
        assert widths[0] > 0
        assert widths[1] > 0
        assert widths[2] > 0
