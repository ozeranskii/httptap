from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from httptap.analyzer import HTTPTapAnalyzer
from httptap.http_client import HTTPClientError
from httptap.models import NetworkInfo, ResponseInfo, TimingMetrics
from httptap.request_executor import RequestOptions, RequestOutcome

if TYPE_CHECKING:
    from collections.abc import Mapping


class StubExecutor:
    def __init__(self, results: list[tuple[int, str | None]]) -> None:
        self.results = results
        self.calls: list[Mapping[str, str] | None] = []

    def execute(self, options: RequestOptions) -> RequestOutcome:
        if not self.results:
            msg = "no more results"
            raise HTTPClientError(msg)

        self.calls.append(options.headers)
        status, location = self.results.pop(0)

        timing = TimingMetrics(total_ms=100.0)
        network = NetworkInfo(ip="203.0.113.5", ip_family="IPv4")
        response = ResponseInfo(status=status, location=location)
        return RequestOutcome(timing=timing, network=network, response=response)


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


def test_analyze_url_with_redirect_blank_location_header() -> None:
    """Test handling of 3xx response with blank Location header."""
    executor = StubExecutor([(302, "")])  # Redirect with empty location string
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/initial")

    # Redirect should not be followed when Location header is blank
    assert len(steps) == 1
    assert steps[0].response.status == 302
    assert steps[0].response.location == ""


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
            self.proxies: list[object | None] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.flags.append(options.verify_ssl)
            self.proxies.append(options.proxy)

            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.1", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return RequestOutcome(timing=timing, network=network, response=response)

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


def test_analyze_url_handles_unexpected_exception() -> None:
    """Test handling of unexpected exceptions during request."""

    class FailingExecutor:
        def execute(self, _options: RequestOptions) -> RequestOutcome:
            msg = "Unexpected failure"
            raise RuntimeError(msg)

    analyzer = HTTPTapAnalyzer(request_executor=FailingExecutor())

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].has_error
    assert "Unexpected failure" in (steps[0].error or "")
    assert "Unexpected error" in (steps[0].note or "")


def test_analyze_url_with_post_method() -> None:
    """Test POST request with method parameter."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/post",
        method=HTTPMethod.POST,
        content=b'{"key": "value"}',
    )

    assert len(steps) == 1
    assert steps[0].request_method == "POST"
    assert steps[0].request_body_bytes == 16
    assert steps[0].response.status == 200


def test_analyze_url_with_put_method() -> None:
    """Test PUT request with method parameter."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/put",
        method=HTTPMethod.PUT,
        content=b'{"status": "updated"}',
    )

    assert len(steps) == 1
    assert steps[0].request_method == "PUT"
    assert steps[0].request_body_bytes == 21


def test_analyze_url_with_patch_method() -> None:
    """Test PATCH request with method parameter."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/patch",
        method=HTTPMethod.PATCH,
        content=b'{"field": "value"}',
    )

    assert len(steps) == 1
    assert steps[0].request_method == "PATCH"
    assert steps[0].request_body_bytes == 18


def test_analyze_url_with_delete_method() -> None:
    """Test DELETE request with method parameter."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(204, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/delete",
        method=HTTPMethod.DELETE,
    )

    assert len(steps) == 1
    assert steps[0].request_method == "DELETE"
    assert steps[0].request_body_bytes == 0


def test_analyze_url_with_head_method() -> None:
    """Test HEAD request with method parameter."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/get",
        method=HTTPMethod.HEAD,
    )

    assert len(steps) == 1
    assert steps[0].request_method == "HEAD"


def test_analyze_url_with_options_method() -> None:
    """Test OPTIONS request with method parameter."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/",
        method=HTTPMethod.OPTIONS,
    )

    assert len(steps) == 1
    assert steps[0].request_method == "OPTIONS"


def test_analyze_url_sanitizes_request_headers() -> None:
    """Test that request headers are sanitized in step metrics."""
    from httptap.constants import HTTPMethod

    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url(
        "https://httpbin.test/post",
        method=HTTPMethod.POST,
        headers={
            "Authorization": "Bearer secret-token-12345",
            "Content-Type": "application/json",
        },
    )

    assert len(steps) == 1
    assert "Authorization" in steps[0].request_headers
    assert "secret" not in steps[0].request_headers["Authorization"]
    assert "****" in steps[0].request_headers["Authorization"]
    assert steps[0].request_headers["Content-Type"] == "application/json"


def test_analyze_url_with_get_method_default() -> None:
    """Test that GET is the default method when not specified."""
    executor = StubExecutor([(200, None)])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url("https://httpbin.test/get")

    assert len(steps) == 1
    assert steps[0].request_method == "GET"
    assert steps[0].request_body_bytes == 0
    assert steps[0].request_headers == {}
