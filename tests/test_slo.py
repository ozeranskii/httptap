"""Tests for the SLO threshold evaluation module."""

from __future__ import annotations

import math

import pytest

from httptap.models import StepMetrics, TimingMetrics
from httptap.slo import (
    SLO_KEYS,
    SLOResult,
    SLOSpecError,
    SLOViolation,
    evaluate_slo,
    parse_slo_spec,
    select_step_for_evaluation,
)


def _step(
    *,
    step_number: int = 1,
    error: str | None = None,
    **timing_fields: float,
) -> StepMetrics:
    """Build a minimal ``StepMetrics`` for SLO tests.

    Any ``<key>_ms`` keyword argument is forwarded to
    :class:`TimingMetrics`; unknown keys raise ``TypeError`` from the
    dataclass constructor.

    """
    return StepMetrics(
        url="https://example.com",
        step_number=step_number,
        timing=TimingMetrics(**timing_fields),  # type: ignore[arg-type]
        error=error,
    )


class TestSLOKeys:
    """SLO_KEYS should cover every duration-valued TimingMetrics field."""

    def test_expected_keys_are_present(self) -> None:
        assert frozenset({"dns", "connect", "tls", "ttfb", "wait", "xfer", "total"}) == SLO_KEYS

    def test_does_not_contain_is_estimated(self) -> None:
        assert "is_estimated" not in SLO_KEYS

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            SLO_KEYS.add("new_key")  # type: ignore[attr-defined]


class TestParseSLOSpec:
    """Parsing accepts well-formed specs and rejects anything else."""

    def test_single_key(self) -> None:
        assert parse_slo_spec("total=500") == {"total": 500.0}

    def test_multiple_keys(self) -> None:
        result = parse_slo_spec("total=500,ttfb=200,connect=100")
        assert result == {"total": 500.0, "ttfb": 200.0, "connect": 100.0}

    def test_fractional_values(self) -> None:
        assert parse_slo_spec("ttfb=123.45") == {"ttfb": 123.45}

    def test_whitespace_tolerance(self) -> None:
        assert parse_slo_spec(" total = 500 , ttfb = 200 ") == {
            "total": 500.0,
            "ttfb": 200.0,
        }

    def test_case_insensitive_keys(self) -> None:
        assert parse_slo_spec("TOTAL=500,Ttfb=200") == {"total": 500.0, "ttfb": 200.0}

    @pytest.mark.parametrize("key", sorted(SLO_KEYS))
    def test_every_supported_key(self, key: str) -> None:
        assert parse_slo_spec(f"{key}=100") == {key: 100.0}

    @pytest.mark.parametrize("raw", ["", "   ", "\t"])
    def test_empty_spec_rejected(self, raw: str) -> None:
        with pytest.raises(SLOSpecError, match="empty"):
            parse_slo_spec(raw)

    def test_empty_item_rejected(self) -> None:
        with pytest.raises(SLOSpecError, match="Empty item"):
            parse_slo_spec("total=500,,ttfb=200")

    @pytest.mark.parametrize("raw", ["total", "total=500=1000", "=500"])
    def test_malformed_item_rejected(self, raw: str) -> None:
        with pytest.raises(SLOSpecError):
            parse_slo_spec(raw)

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(SLOSpecError, match="Unknown SLO key 'foo'"):
            parse_slo_spec("foo=500")

    def test_duplicate_key_rejected(self) -> None:
        with pytest.raises(SLOSpecError, match="Duplicate SLO key 'total'"):
            parse_slo_spec("total=500,total=600")

    def test_non_numeric_value_rejected(self) -> None:
        with pytest.raises(SLOSpecError, match="is not a number"):
            parse_slo_spec("total=fast")

    @pytest.mark.parametrize("value", ["0", "-1", "-0.001", "inf", "nan"])
    def test_non_positive_or_non_finite_value_rejected(self, value: str) -> None:
        with pytest.raises(SLOSpecError, match="positive finite number"):
            parse_slo_spec(f"total={value}")

    def test_returns_new_dict_each_call(self) -> None:
        first = parse_slo_spec("total=500")
        second = parse_slo_spec("total=500")
        assert first == second
        assert first is not second


class TestEvaluateSLO:
    """Evaluation reports violations only when timings exceed budgets."""

    def test_pass_when_every_metric_under_budget(self) -> None:
        step = _step(total_ms=100.0, ttfb_ms=50.0)
        result = evaluate_slo(step, {"total": 500.0, "ttfb": 200.0})
        assert result.passed is True
        assert result.violations == ()
        assert dict(result.thresholds_ms) == {"total": 500.0, "ttfb": 200.0}

    def test_equal_to_threshold_is_pass(self) -> None:
        step = _step(total_ms=500.0)
        result = evaluate_slo(step, {"total": 500.0})
        assert result.passed is True

    def test_fail_when_single_metric_exceeds(self) -> None:
        step = _step(total_ms=600.0)
        result = evaluate_slo(step, {"total": 500.0})
        assert result.passed is False
        assert len(result.violations) == 1
        violation = result.violations[0]
        assert violation.key == "total"
        assert violation.threshold_ms == 500.0
        assert violation.actual_ms == 600.0
        assert violation.delta_ms == pytest.approx(100.0)

    def test_fail_reports_all_violations_in_sorted_order(self) -> None:
        step = _step(total_ms=600.0, ttfb_ms=300.0, connect_ms=200.0)
        result = evaluate_slo(
            step,
            {"ttfb": 200.0, "total": 500.0, "connect": 100.0},
        )
        assert result.passed is False
        # Sorted alphabetically for deterministic output.
        assert [v.key for v in result.violations] == ["connect", "total", "ttfb"]

    def test_empty_thresholds_always_pass(self) -> None:
        step = _step(total_ms=10000.0)
        result = evaluate_slo(step, {})
        assert result.passed is True
        assert dict(result.thresholds_ms) == {}

    @pytest.mark.parametrize("threshold_key", sorted(SLO_KEYS))
    def test_every_slo_key_maps_to_timing_field(self, threshold_key: str) -> None:
        """Every key in SLO_KEYS must resolve to a TimingMetrics attribute.

        Parametrised directly over :data:`SLO_KEYS` so that adding a
        new entry there breaks this test until :func:`evaluate_slo`
        grows the corresponding mapping.
        """
        actual_ms = 200.0
        timing = TimingMetrics(**{f"{threshold_key}_ms": actual_ms})  # type: ignore[arg-type]
        step = StepMetrics(url="https://example.com", timing=timing)

        # Threshold is half the measured value → violation on the one key.
        result = evaluate_slo(step, {threshold_key: actual_ms / 2})

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].key == threshold_key
        assert result.violations[0].actual_ms == actual_ms

    def test_unknown_key_raises_spec_error(self) -> None:
        step = _step(total_ms=100.0)
        with pytest.raises(SLOSpecError, match="Unknown SLO key"):
            evaluate_slo(step, {"bogus": 500.0})

    def test_mixed_known_and_unknown_keys_rejected(self) -> None:
        step = _step(total_ms=100.0)
        with pytest.raises(SLOSpecError, match="bogus"):
            evaluate_slo(step, {"total": 500.0, "bogus": 500.0})

    def test_does_not_mutate_input_thresholds(self) -> None:
        step = _step(total_ms=600.0)
        thresholds = {"total": 500.0, "ttfb": 100.0}
        snapshot = dict(thresholds)

        evaluate_slo(step, thresholds)

        assert thresholds == snapshot  # Caller's mapping preserved.

    def test_zero_phase_against_zero_threshold_is_pass(self) -> None:
        """TLS=0 on plain HTTP should not violate a tight TLS budget."""
        step = _step(tls_ms=0.0)
        result = evaluate_slo(step, {"tls": 1.0})
        assert result.passed is True


class TestSLOResult:
    """``SLOResult.to_dict`` produces stable JSON-ready data."""

    def test_pass_dict_shape(self) -> None:
        result = SLOResult(thresholds_ms={"total": 500.0}, violations=())
        assert result.to_dict() == {
            "pass": True,
            "thresholds_ms": {"total": 500.0},
            "violations": [],
        }

    def test_fail_dict_shape(self) -> None:
        violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=700.0)
        result = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))
        payload = result.to_dict()
        assert payload == {
            "pass": False,
            "thresholds_ms": {"total": 500.0},
            "violations": [
                {
                    "key": "total",
                    "threshold_ms": 500.0,
                    "actual_ms": 700.0,
                    "delta_ms": 200.0,
                }
            ],
        }

    def test_evaluate_copies_user_thresholds(self) -> None:
        """evaluate_slo snapshots the caller's mapping into the result."""
        thresholds = {"total": 500.0}
        step = _step(total_ms=100.0)

        result = evaluate_slo(step, thresholds)

        thresholds["total"] = 999.0
        assert result.thresholds_ms == {"total": 500.0}

    def test_frozen_attribute_reassignment_is_blocked(self) -> None:
        result = SLOResult(thresholds_ms={"total": 500.0}, violations=())
        with pytest.raises(AttributeError):
            result.violations = ()  # type: ignore[misc]

    def test_to_dict_thresholds_sorted_for_stable_json(self) -> None:
        """to_dict emits thresholds in alphabetical key order."""
        result = SLOResult(
            thresholds_ms={"total": 500.0, "connect": 100.0, "ttfb": 200.0},
            violations=(),
        )
        payload_keys = list(result.to_dict()["thresholds_ms"].keys())
        assert payload_keys == ["connect", "total", "ttfb"]

    def test_equality_compares_by_value(self) -> None:
        violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=700.0)
        first = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))
        second = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))
        assert first == second

    def test_is_not_hashable(self) -> None:
        result = SLOResult(thresholds_ms={"total": 500.0}, violations=())
        with pytest.raises(TypeError):
            hash(result)


class TestSLOViolation:
    """``SLOViolation.delta_ms`` captures the overrun."""

    def test_delta_is_positive_on_overrun(self) -> None:
        v = SLOViolation(key="total", threshold_ms=500.0, actual_ms=750.0)
        assert v.delta_ms == pytest.approx(250.0)

    def test_delta_is_zero_on_boundary(self) -> None:
        v = SLOViolation(key="total", threshold_ms=500.0, actual_ms=500.0)
        assert math.isclose(v.delta_ms, 0.0)

    def test_is_immutable(self) -> None:
        v = SLOViolation(key="total", threshold_ms=500.0, actual_ms=750.0)
        with pytest.raises(AttributeError):
            v.threshold_ms = 0.0  # type: ignore[misc]


class TestSelectStepForEvaluation:
    """SLO targets the final successful step of the chain."""

    def test_single_successful_step(self) -> None:
        step = _step(total_ms=100.0)
        assert select_step_for_evaluation([step]) is step

    def test_returns_last_step_when_all_succeed(self) -> None:
        first = _step(total_ms=50.0, step_number=1)
        second = _step(total_ms=100.0, step_number=2)
        third = _step(total_ms=150.0, step_number=3)
        assert select_step_for_evaluation([first, second, third]) is third

    def test_skips_trailing_errors(self) -> None:
        ok = _step(total_ms=100.0, step_number=1)
        failed = _step(step_number=2, error="connection refused")
        assert select_step_for_evaluation([ok, failed]) is ok

    def test_returns_none_when_all_failed(self) -> None:
        first = _step(step_number=1, error="DNS error")
        second = _step(step_number=2, error="TCP error")
        assert select_step_for_evaluation([first, second]) is None

    def test_empty_list_returns_none(self) -> None:
        assert select_step_for_evaluation([]) is None
