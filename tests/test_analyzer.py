from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest

from httptap.analyzer import HTTPTapAnalyzer
from httptap.http_client import HTTPClientError
from httptap.models import NetworkInfo, ResponseInfo, TimingMetrics
from httptap.request_executor import CallableRequestExecutor, RequestOptions, RequestOutcome

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
        verify_ssl: bool = True,
        proxy: Mapping[str, str] | str | None = None,
        dns_resolver: DNSResolver | None = None,
        tls_inspector: TLSInspector | None = None,
        timing_collector: TimingCollector | None = None,
        force_new_connection: bool = True,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        del url
        del timeout
        del http2
        del verify_ssl
        del proxy
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
    assert steps[0].proxied_via is None


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


def test_analyze_url_passes_verify_flag_when_supported() -> None:
    class VerifyAwareExecutor:
        def __init__(self) -> None:
            self.flags: list[bool] = []
            self.proxies: list[Mapping[str, str] | str | None] = []

        def __call__(  # noqa: PLR0913
            self,
            url: str,
            timeout: float,
            *,
            http2: bool,
            verify_ssl: bool = True,
            proxy: Mapping[str, str] | str | None = None,
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
            del headers
            self.flags.append(verify_ssl)
            self.proxies.append(proxy)

            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.1", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return timing, network, response

    executor = VerifyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        verify_ssl=False,
        proxy="http://proxy:8080",
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.flags == [False]
    assert executor.proxies == ["http://proxy:8080"]
    assert steps[0].proxied_via == "http://proxy:8080"
    assert executor.proxies == ["http://proxy:8080"]


def test_analyze_url_accepts_object_executor() -> None:
    class ObjectExecutor:
        def __init__(self) -> None:
            self.calls: list[RequestOptions] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.calls.append(options)
            timing = TimingMetrics(total_ms=8.0)
            network = NetworkInfo(ip="198.51.100.2", ip_family="IPv4")
            response = ResponseInfo(status=204)
            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ObjectExecutor()
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 204
    assert executor.calls
    assert executor.calls[0].verify_ssl is True
    assert executor.calls[0].proxy is None


def test_callable_request_executor_warns_on_missing_verify() -> None:
    class FlakyExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(  # noqa: PLR0913
            self,
            url: str,
            timeout: float,
            *,
            http2: bool,
            verify_ssl: bool = True,
            dns_resolver: DNSResolver | None = None,
            tls_inspector: TLSInspector | None = None,
            timing_collector: TimingCollector | None = None,
            force_new_connection: bool = True,
            headers: Mapping[str, str] | None = None,
        ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
            self.calls += 1
            if self.calls == 1:
                msg = "unexpected keyword argument 'verify_ssl'"
                raise TypeError(msg)
            del url
            del timeout
            del http2
            del verify_ssl
            del dns_resolver
            del tls_inspector
            del timing_collector
            del force_new_connection
            del headers
            timing = TimingMetrics(total_ms=12.0)
            network = NetworkInfo(ip="198.51.100.3", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return timing, network, response

    adapter = CallableRequestExecutor(FlakyExecutor())
    options = RequestOptions(
        url="https://example.test",
        timeout=5.0,
        http2=True,
        verify_ssl=False,
        dns_resolver=None,
        tls_inspector=None,
        timing_collector=None,
        force_new_connection=True,
        headers=None,
    )

    with pytest.warns(DeprecationWarning, match="verify_ssl"):
        outcome = adapter.execute(options)

    assert outcome.response.status == 200


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
