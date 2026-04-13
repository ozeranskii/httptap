"""Hypothesis property-based tests for parsers and validators.

These tests complement the example-based suites by exercising a broad
cross-section of inputs automatically. They focus on **invariants**:
properties that must hold for every input, not for a hand-picked case.

Profiles
--------
``dev`` (default) runs the standard Hypothesis budget (100 examples,
fast feedback for local development).

``ci`` (selected when ``CI=1``) runs 500 examples, disables the
deadline, and derandomises the seed so a given build is
bit-reproducible.

``nightly`` (selected when ``HYPOTHESIS_PROFILE=nightly``) stretches
the budget to 5 000 examples for longer-running supply-chain runs.
"""

from __future__ import annotations

import json
import math
import os

from hypothesis import (
    HealthCheck,
    assume,
    example,
    given,
    settings,
    target,
)
from hypothesis import (
    strategies as st,
)

from httptap.http_client import _host_matches_no_proxy
from httptap.models import StepMetrics, TimingMetrics
from httptap.slo import (
    SLO_KEYS,
    SLOSpecError,
    evaluate_slo,
    parse_slo_spec,
)
from httptap.utils import validate_url

settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "ci",
    max_examples=500,
    deadline=None,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "nightly",
    max_examples=5_000,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE") or ("ci" if os.getenv("CI") else "dev"))


slo_key = st.sampled_from(sorted(SLO_KEYS))
positive_finite_float = st.floats(
    min_value=1e-6,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def slo_spec_and_expected(draw: st.DrawFn) -> tuple[str, dict[str, float]]:
    """Generate a valid ``--slo`` spec plus the dict it should parse to.

    Uses each ``SLO_KEYS`` entry at most once so the duplicate-key rule
    never trips during round-trip testing.
    """
    size = draw(st.integers(min_value=1, max_value=len(SLO_KEYS)))
    keys = draw(st.lists(slo_key, min_size=size, max_size=size, unique=True))
    values = draw(st.lists(positive_finite_float, min_size=size, max_size=size))
    expected = dict(zip(keys, values, strict=True))
    spec = ",".join(f"{k}={v}" for k, v in expected.items())
    return spec, expected


class TestParseSLOSpec:
    """Invariants for :func:`httptap.slo.parse_slo_spec`."""

    @given(slo_spec_and_expected())
    @example(("total=500", {"total": 500.0}))
    @example(("connect=1,total=500000", {"connect": 1.0, "total": 500_000.0}))
    def test_round_trip_preserves_every_key(
        self,
        pair: tuple[str, dict[str, float]],
    ) -> None:
        spec, expected = pair
        parsed = parse_slo_spec(spec)
        assert set(parsed) == set(expected)
        for key, value in expected.items():
            assert math.isclose(parsed[key], value, rel_tol=1e-9)
            target(value, label=f"{key}_ms")

    @given(st.floats(allow_nan=False, allow_infinity=False, max_value=0.0))
    @example(-1.0)
    @example(0.0)
    def test_non_positive_values_rejected(self, value: float) -> None:
        try:
            parse_slo_spec(f"total={value}")
        except SLOSpecError:
            return
        msg = f"expected SLOSpecError for non-positive value {value!r}"
        raise AssertionError(msg)

    @given(st.sampled_from(["inf", "-inf", "nan", "NaN", "+inf", "Infinity"]))
    def test_non_finite_values_rejected(self, literal: str) -> None:
        try:
            parse_slo_spec(f"total={literal}")
        except SLOSpecError:
            return
        msg = f"expected SLOSpecError for non-finite literal {literal!r}"
        raise AssertionError(msg)

    @given(
        st.text(alphabet=st.characters(blacklist_categories=("Cc",)), max_size=20).filter(
            lambda s: s.strip().lower() not in SLO_KEYS
        )
    )
    @example("bogus")
    @example("TOTAL_MS")
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_unknown_key_rejected(self, key: str) -> None:
        assume("=" not in key and "," not in key and key.strip() != "")
        try:
            parse_slo_spec(f"{key}=100")
        except SLOSpecError:
            return
        msg = f"expected SLOSpecError for unknown key {key!r}"
        raise AssertionError(msg)

    @given(slo_key, positive_finite_float, st.sampled_from([" ", "  ", "\t"]))
    def test_whitespace_around_tokens_is_tolerated(
        self,
        key: str,
        value: float,
        whitespace: str,
    ) -> None:
        spec = f"{whitespace}{key}{whitespace}={whitespace}{value}{whitespace}"
        parsed = parse_slo_spec(spec)
        assert set(parsed) == {key}

    @given(slo_spec_and_expected())
    def test_parse_is_idempotent(self, pair: tuple[str, dict[str, float]]) -> None:
        """Reserialising the parsed dict into a spec must round-trip."""
        spec, _expected = pair
        first = parse_slo_spec(spec)
        reconstituted = ",".join(f"{k}={v}" for k, v in first.items())
        second = parse_slo_spec(reconstituted)
        assert first == second

    @given(slo_key, positive_finite_float)
    def test_keys_are_lower_cased(self, key: str, value: float) -> None:
        parsed = parse_slo_spec(f"{key.upper()}={value}")
        assert key in parsed


class TestValidateURL:
    """Invariants for :func:`httptap.utils.validate_url`."""

    @given(st.sampled_from(["http", "https", "HTTP", "HTTPS", "Http", "HtTpS"]))
    @example("http")
    @example("HTTP")
    def test_accepts_http_https_schemes_case_insensitive(self, scheme: str) -> None:
        assert validate_url(f"{scheme}://example.com/") is True

    @given(
        st.text(min_size=1, max_size=30).filter(
            lambda s: s.lower() not in ("http", "https") and "/" not in s and ":" not in s
        )
    )
    @example("ftp")
    @example("file")
    @example("ssh")
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_rejects_other_schemes(self, scheme: str) -> None:
        assert validate_url(f"{scheme}://example.com/") is False

    @given(st.text(max_size=30).filter(lambda s: "://" not in s))
    @example("")
    @example("example.com")
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_rejects_without_scheme_separator(self, garbage: str) -> None:
        assert validate_url(garbage) is False


class TestHostMatchesNoProxy:
    """Invariants for :func:`httptap.http_client._host_matches_no_proxy`."""

    @given(st.text(min_size=1, max_size=40).filter(lambda s: "," not in s))
    @example("example.com")
    def test_empty_no_proxy_always_false(self, host: str) -> None:
        assert _host_matches_no_proxy(host, "") is False

    @given(st.text(min_size=1, max_size=40).filter(lambda s: "," not in s))
    @example("example.com")
    @example("192.168.1.1")
    def test_star_matches_every_host(self, host: str) -> None:
        assert _host_matches_no_proxy(host, "*") is True

    @given(st.from_regex(r"[a-z0-9-]{1,30}\.example\.com", fullmatch=True))
    @example("api.example.com")
    @example("a.example.com")
    def test_suffix_match_with_leading_dot(self, host: str) -> None:
        assert _host_matches_no_proxy(host, ".example.com") is True

    @given(st.from_regex(r"[a-z0-9-]{1,15}", fullmatch=True))
    def test_suffix_match_without_leading_dot(self, subdomain: str) -> None:
        host = f"{subdomain}.example.com"
        assert _host_matches_no_proxy(host, "example.com") is True

    @given(st.from_regex(r"[a-z0-9-]{1,30}\.co", fullmatch=True))
    def test_unrelated_domain_does_not_match(self, host: str) -> None:
        assume(not host.endswith(".example.com"))
        assert _host_matches_no_proxy(host, "example.com") is False

    @given(st.from_regex(r"[a-z0-9-]{1,20}", fullmatch=True))
    @example("example.com")
    def test_exact_match_is_case_insensitive(self, host: str) -> None:
        assert _host_matches_no_proxy(host.upper(), host.lower()) is True
        assert _host_matches_no_proxy(host.lower(), host.upper()) is True

    @given(
        host=st.from_regex(r"[a-z0-9-]{1,20}", fullmatch=True),
        noise=st.lists(
            st.from_regex(r"[a-z0-9.-]{1,20}", fullmatch=True),
            max_size=5,
        ),
        matching_position=st.integers(min_value=0, max_value=5),
    )
    def test_any_matching_entry_triggers_match(
        self,
        host: str,
        noise: list[str],
        matching_position: int,
    ) -> None:
        """Adding a guaranteed-match entry forces the result to True."""
        position = matching_position % (len(noise) + 1)
        entries = [*noise[:position], host, *noise[position:]]
        assert _host_matches_no_proxy(host, ",".join(entries)) is True


class TestTimingMetricsDerived:
    """Invariants for :meth:`TimingMetrics.calculate_derived`."""

    @given(
        dns=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        connect=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        tls=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        ttfb=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        total=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_wait_and_xfer_are_always_non_negative(
        self,
        dns: float,
        connect: float,
        tls: float,
        ttfb: float,
        total: float,
    ) -> None:
        """Derived fields clamp at zero regardless of input ordering."""
        timing = TimingMetrics(
            dns_ms=dns,
            connect_ms=connect,
            tls_ms=tls,
            ttfb_ms=ttfb,
            total_ms=total,
        )
        timing.calculate_derived()
        assert timing.wait_ms >= 0.0
        assert timing.xfer_ms >= 0.0

    @given(
        dns=st.floats(min_value=0, max_value=500, allow_nan=False),
        connect=st.floats(min_value=0, max_value=500, allow_nan=False),
        tls=st.floats(min_value=0, max_value=500, allow_nan=False),
        extra_wait=st.floats(min_value=0, max_value=500, allow_nan=False),
        extra_xfer=st.floats(min_value=0, max_value=500, allow_nan=False),
    )
    def test_consistent_timings_round_trip(
        self,
        dns: float,
        connect: float,
        tls: float,
        extra_wait: float,
        extra_xfer: float,
    ) -> None:
        """Construct consistent timings, derive, check the arithmetic holds."""
        ttfb = dns + connect + tls + extra_wait
        total = ttfb + extra_xfer
        timing = TimingMetrics(
            dns_ms=dns,
            connect_ms=connect,
            tls_ms=tls,
            ttfb_ms=ttfb,
            total_ms=total,
        )
        timing.calculate_derived()
        assert math.isclose(timing.wait_ms, extra_wait, abs_tol=1e-9)
        assert math.isclose(timing.xfer_ms, extra_xfer, abs_tol=1e-9)


class TestSLOEndToEnd:
    """End-to-end properties that cross parse_slo_spec + evaluate_slo."""

    @staticmethod
    def _step_with_timings(timings: dict[str, float]) -> StepMetrics:
        return StepMetrics(
            url="https://example.com",
            timing=TimingMetrics(
                dns_ms=timings.get("dns", 0.0),
                connect_ms=timings.get("connect", 0.0),
                tls_ms=timings.get("tls", 0.0),
                ttfb_ms=timings.get("ttfb", 0.0),
                total_ms=timings.get("total", 0.0),
                wait_ms=timings.get("wait", 0.0),
                xfer_ms=timings.get("xfer", 0.0),
            ),
        )

    @given(slo_spec_and_expected())
    def test_parse_then_evaluate_passes_for_zero_timings(
        self,
        pair: tuple[str, dict[str, float]],
    ) -> None:
        """A step with zero timings never violates any positive budget."""
        spec, _expected = pair
        thresholds = parse_slo_spec(spec)
        step = self._step_with_timings({})
        result = evaluate_slo(step, thresholds)
        assert result.passed is True
        assert result.violations == ()

    @given(slo_spec_and_expected())
    def test_parse_then_evaluate_fails_when_timings_double_thresholds(
        self,
        pair: tuple[str, dict[str, float]],
    ) -> None:
        """Doubling every timing above its threshold forces full violation."""
        spec, expected = pair
        thresholds = parse_slo_spec(spec)
        timings = {k: v * 2 + 1 for k, v in expected.items()}
        step = self._step_with_timings(timings)
        result = evaluate_slo(step, thresholds)
        assert result.passed is False
        assert {v.key for v in result.violations} == set(expected)


class TestSLOResultJSONStability:
    """Byte-stable JSON output for equivalent SLO inputs."""

    @given(slo_spec_and_expected())
    def test_to_dict_is_byte_stable_across_equivalent_specs(
        self,
        pair: tuple[str, dict[str, float]],
    ) -> None:
        """Two equal thresholds must serialise to identical JSON."""
        spec, _expected = pair
        step = StepMetrics(url="https://example.com", timing=TimingMetrics())
        first = evaluate_slo(step, parse_slo_spec(spec)).to_dict()
        second = evaluate_slo(step, parse_slo_spec(spec)).to_dict()
        assert json.dumps(first) == json.dumps(second)

    @given(slo_spec_and_expected())
    def test_thresholds_emitted_in_alphabetical_order(
        self,
        pair: tuple[str, dict[str, float]],
    ) -> None:
        """Documented contract: stable, sorted keys in summary.slo."""
        spec, _expected = pair
        step = StepMetrics(url="https://example.com", timing=TimingMetrics())
        result = evaluate_slo(step, parse_slo_spec(spec))
        keys = list(result.to_dict()["thresholds_ms"].keys())
        assert keys == sorted(keys)
