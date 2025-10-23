from __future__ import annotations

from typing import TYPE_CHECKING

from httptap.analyzer import HTTPTapAnalyzer
from httptap.http_client import HTTPClientError
from httptap.models import NetworkInfo, ResponseInfo, TimingMetrics

if TYPE_CHECKING:
    from collections.abc import Mapping

    from httptap.interfaces import DNSResolver, TimingCollector, TLSInspector


class StubExecutor:
    def __init__(self, results: list[tuple[int, str | None]]) -> None:
        self.results = results
        self.calls: list[Mapping[str, str] | None] = []

    def __call__(  # noqa: PLR0913
        self,
        url: str,
        timeout: float,
        *,
        http2: bool,
        dns_resolver: DNSResolver | None = None,
        tls_inspector: TLSInspector | None = None,
        timing_collector: TimingCollector | None = None,
        force_new_connection: bool = True,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        del url
        del timeout
        del http2
        del dns_resolver
        del tls_inspector
        del timing_collector
        del force_new_connection
        if not self.results:
            msg = "no more results"
            raise HTTPClientError(msg)

        self.calls.append(headers)
        status, location = self.results.pop(0)

        timing = TimingMetrics(total_ms=100.0)
        network = NetworkInfo(ip="203.0.113.5", ip_family="IPv4")
        response = ResponseInfo(status=status, location=location)
        return timing, network, response


def test_analyze_url_without_redirect() -> None:
    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url("https://example.test", headers={"X": "1"})

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.calls == [{"X": "1"}]


def test_analyze_url_with_redirect_following() -> None:
    executor = StubExecutor([(301, "https://example.test/final"), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test")

    assert [step.response.status for step in steps] == [301, 200]
    assert steps[1].url == "https://example.test/final"


def test_analyze_url_records_error() -> None:
    executor = StubExecutor([])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url("https://example.test")
    assert steps[0].has_error
    assert "no more results" in (steps[0].error or "")


def test_analyze_url_stops_on_error_when_following_redirects() -> None:
    """Test that analyzer stops following redirects when an error occurs."""
    executor = StubExecutor([(301, "https://example.test/redirect")])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test")

    # First step should be redirect, second should have error
    assert len(steps) == 2
    assert steps[0].response.status == 301
    assert steps[1].has_error
    # Should stop after error
    assert "no more results" in (steps[1].error or "")


def test_analyze_url_with_redirect_missing_location_header() -> None:
    """Test handling of 3xx response without Location header."""
    executor = StubExecutor([(302, None)])  # Redirect with no location
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test")

    # Should stop after first step due to missing Location
    assert len(steps) == 1
    assert steps[0].response.status == 302
    assert steps[0].response.location is None


def test_analyze_url_respects_max_redirects() -> None:
    """Test that analyzer respects max_redirects limit."""
    # Create infinite redirect chain
    executor = StubExecutor(
        [(301, "https://example.test/1") for _ in range(20)],  # More than max
    )
    analyzer = HTTPTapAnalyzer(
        follow_redirects=True,
        max_redirects=5,
        request_executor=executor,
    )

    steps = analyzer.analyze_url("https://example.test")

    # Should stop at max_redirects + 1 (initial request + max redirects)
    assert len(steps) == 6  # Initial + 5 redirects
    assert all(step.response.status == 301 for step in steps)


def test_analyze_url_handles_unexpected_exception() -> None:
    """Test handling of unexpected exceptions during request."""

    class FailingExecutor:
        def __call__(
            self,
            *_args: object,
            **_kwargs: object,
        ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
            msg = "Unexpected failure"
            raise RuntimeError(msg)

    analyzer = HTTPTapAnalyzer(request_executor=FailingExecutor())

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].has_error
    assert "Unexpected failure" in (steps[0].error or "")
    assert "Unexpected error" in (steps[0].note or "")
