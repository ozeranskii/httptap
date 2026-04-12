"""Service Level Objective (SLO) evaluation for HTTP request timings.

This module implements SLO threshold checking: the user supplies
per-phase latency budgets (in milliseconds) and httptap evaluates the
actual measurements against them. A violation produces a non-zero
exit code, structured violation records in the JSON export, and
human-readable output for terminal and scripting pipelines.

SLO keys map one-to-one to ``TimingMetrics`` fields that express a
duration in milliseconds. The ``is_estimated`` flag is intentionally
excluded because it is boolean, not a duration.

Typical usage:
    >>> thresholds = parse_slo_spec("total=500,ttfb=200")
    >>> result = evaluate_slo(step, thresholds)
    >>> if not result.passed:
    ...     for v in result.violations:
    ...         print(f"{v.key}: {v.actual_ms}ms > {v.threshold_ms}ms")

"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .models import StepMetrics


# Keys accepted in ``--slo``. Each maps to a ``TimingMetrics.*_ms``
# field; adding a new entry here requires updating the ``timing_map``
# inside :func:`evaluate_slo` so the key-to-attribute mapping stays
# in sync.
SLO_KEYS: frozenset[str] = frozenset({"dns", "connect", "tls", "ttfb", "wait", "xfer", "total"})


class SLOSpecError(ValueError):
    """Raised when an ``--slo`` specification cannot be parsed."""


@dataclass(frozen=True, slots=True)
class SLOViolation:
    """A single threshold violation.

    Attributes:
        key: Timing phase key (e.g., ``"total"``, ``"ttfb"``).
        threshold_ms: Budget supplied by the user, in milliseconds.
        actual_ms: Measured timing value, in milliseconds.

    """

    key: str
    threshold_ms: float
    actual_ms: float

    @property
    def delta_ms(self) -> float:
        """Overrun over the budget, in milliseconds.

        By construction :func:`evaluate_slo` only emits violations where
        ``actual_ms > threshold_ms``, so this value is always strictly
        positive for objects produced by this module. Callers that
        instantiate ``SLOViolation`` directly should preserve this
        invariant to keep downstream output consistent.
        """
        return self.actual_ms - self.threshold_ms

    def to_dict(self) -> dict[str, float | str]:
        """Serialize to a plain ``dict`` for JSON export.

        Returns:
            Mapping with keys ``key``, ``threshold_ms``, ``actual_ms``,
            ``delta_ms``.

        """
        return {
            "key": self.key,
            "threshold_ms": self.threshold_ms,
            "actual_ms": self.actual_ms,
            "delta_ms": self.delta_ms,
        }


@dataclass(frozen=True, slots=True)
class SLOResult:
    """Result of evaluating timings against a set of SLO thresholds.

    Produced by :func:`evaluate_slo`, which guarantees the contract
    used by the rest of the codebase:

    * ``thresholds_ms`` is a fresh ``dict`` snapshot of the input
      mapping — safe to mutate by the caller without affecting the
      result object's serialization.
    * ``violations`` is a ``tuple`` sorted alphabetically by
      :attr:`SLOViolation.key`, making :meth:`to_dict` output
      byte-stable across evaluations with the same input.

    The dataclass is ``frozen=True`` so attribute reassignment is
    blocked; this is shallow immutability (as with any Python frozen
    dataclass) — external callers who hand-construct ``SLOResult``
    with mutable containers should not mutate them after handover.

    :class:`SLOResult` is not hashable (``thresholds_ms`` is a
    ``dict``) and therefore cannot be used as a ``dict`` key or added
    to a ``set``; equality comparison via ``==`` works and is
    structural.

    Attributes:
        thresholds_ms: User-supplied budgets keyed by SLO key.
        violations: Violations sorted alphabetically by ``key``.
            When empty, the evaluation passed.

    """

    thresholds_ms: dict[str, float] = field(default_factory=dict)
    violations: tuple[SLOViolation, ...] = ()

    @property
    def passed(self) -> bool:
        """Return ``True`` when every threshold was met or undercut."""
        return len(self.violations) == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain ``dict`` for JSON export.

        Threshold keys are emitted in alphabetical order so that two
        evaluations with the same user input always produce
        byte-identical JSON (useful for diffing and cache keys).

        Returns:
            Mapping with keys ``pass``, ``thresholds_ms``, ``violations``.

        """
        return {
            "pass": self.passed,
            "thresholds_ms": {key: self.thresholds_ms[key] for key in sorted(self.thresholds_ms)},
            "violations": [v.to_dict() for v in self.violations],
        }


def parse_slo_spec(raw: str) -> dict[str, float]:
    """Parse an ``--slo`` specification string.

    The expected grammar is a comma-separated list of ``KEY=MS`` pairs.
    Whitespace around keys and values is tolerated. Keys are
    case-insensitive and normalised to lowercase.

    Args:
        raw: String passed via ``--slo``, e.g. ``"total=500,ttfb=200"``.

    Returns:
        Mapping of lowercase SLO key to threshold in milliseconds.

    Raises:
        SLOSpecError: If the string is empty, a pair is malformed, a
            key is unknown, a key is duplicated, or a value is not a
            positive, finite number.

    Examples:
        >>> parse_slo_spec("total=500,ttfb=200")
        {'total': 500.0, 'ttfb': 200.0}
        >>> parse_slo_spec("Total=500")
        {'total': 500.0}

    """
    if not raw or not raw.strip():
        msg = "SLO specification is empty (expected KEY=MS[,KEY=MS...])."
        raise SLOSpecError(msg)

    thresholds: dict[str, float] = {}

    for pair in raw.split(","):
        token = pair.strip()
        if not token:
            msg = f"Empty item in SLO specification '{raw}' (expected KEY=MS[,KEY=MS...])."
            raise SLOSpecError(msg)

        if token.count("=") != 1:
            msg = f"Invalid SLO item '{token}' (expected exactly one '=' between KEY and MS)."
            raise SLOSpecError(msg)

        key_raw, value_raw = token.split("=", 1)
        key = key_raw.strip().lower()
        value_str = value_raw.strip()

        if not key:
            msg = f"Invalid SLO item '{token}' (KEY must not be empty)."
            raise SLOSpecError(msg)

        if key not in SLO_KEYS:
            allowed = ", ".join(sorted(SLO_KEYS))
            msg = f"Unknown SLO key '{key}'. Valid keys: {allowed}."
            raise SLOSpecError(msg)

        if key in thresholds:
            msg = f"Duplicate SLO key '{key}' in specification '{raw}'."
            raise SLOSpecError(msg)

        try:
            value = float(value_str)
        except ValueError as exc:
            msg = f"Invalid SLO value for '{key}': '{value_str}' is not a number."
            raise SLOSpecError(msg) from exc

        if not math.isfinite(value) or value <= 0:
            msg = f"Invalid SLO value for '{key}': '{value_str}' must be a positive finite number of milliseconds."
            raise SLOSpecError(msg)

        thresholds[key] = value

    return thresholds


def evaluate_slo(
    step: StepMetrics,
    thresholds: Mapping[str, float],
) -> SLOResult:
    """Evaluate timings on a single step against SLO thresholds.

    Args:
        step: Step whose ``timing`` is compared to the thresholds.
        thresholds: Mapping of SLO key to threshold in milliseconds.
            Every key must be a member of :data:`SLO_KEYS`.

    Returns:
        :class:`SLOResult` listing any violations in ascending
        alphabetical order of the user-supplied threshold keys. The
        order is stable so the JSON export is reproducible.

    Raises:
        SLOSpecError: If ``thresholds`` contains a key that is not a
            member of :data:`SLO_KEYS`. Programmatic callers are
            expected to validate input via :func:`parse_slo_spec`
            first; this check guards against accidental misuse.

    """
    unknown = set(thresholds) - SLO_KEYS
    if unknown:
        allowed = ", ".join(sorted(SLO_KEYS))
        bad = ", ".join(sorted(unknown))
        msg = f"Unknown SLO key(s): {bad}. Valid keys: {allowed}."
        raise SLOSpecError(msg)

    # Keep this mapping in lockstep with SLO_KEYS (the frozenset above).
    timing_map: dict[str, float] = {
        "dns": step.timing.dns_ms,
        "connect": step.timing.connect_ms,
        "tls": step.timing.tls_ms,
        "ttfb": step.timing.ttfb_ms,
        "wait": step.timing.wait_ms,
        "xfer": step.timing.xfer_ms,
        "total": step.timing.total_ms,
    }

    violations = tuple(
        SLOViolation(key=key, threshold_ms=thresholds[key], actual_ms=timing_map[key])
        for key in sorted(thresholds)
        if timing_map[key] > thresholds[key]
    )

    return SLOResult(thresholds_ms=dict(thresholds), violations=violations)


def select_step_for_evaluation(steps: Sequence[StepMetrics]) -> StepMetrics | None:
    """Pick the step whose timing should be checked against SLO.

    By convention, SLOs apply to the *final* successful step of a
    redirect chain (the one that actually served the user's request).
    If every step errored out, returns ``None`` — the caller is
    expected to treat that as a network failure rather than an SLO
    violation.

    Args:
        steps: Steps returned by ``HTTPTapAnalyzer.analyze_url``.

    Returns:
        Final successful step, or ``None`` if there is no such step.

    """
    for step in reversed(steps):
        if not step.has_error:
            return step
    return None
