from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest

from httptap.analyzer import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
from httptap.http_client import HTTPClientError
from httptap.models import NetworkInfo, ResponseInfo, TimingMetrics
from httptap.request_executor import RequestOptions, RequestOutcome

if TYPE_CHECKING:
    from collections.abc import Mapping


class StubExecutor:
    def __init__(self, results: list[tuple[int, str | None]]) -> None:
        self.results = results
        self.calls: list[Mapping[str, str] | None] = []
        self.urls: list[str] = []

    def execute(self, options: RequestOptions) -> RequestOutcome:
        if not self.results:
            msg = "no more results"
            raise HTTPClientError(msg)

        self.calls.append(options.headers)
        self.urls.append(options.url)
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
    assert steps[0].error_kind == "network"
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


@pytest.mark.parametrize(
    ("location", "reason"),
    [
        ("http://example.test:99999/next", "Port out of range"),
        ("http://example.test:abc/next", "Port could not be cast"),
        ("http://[::1/next", "Invalid IPv6 URL"),
        ("ftp://example.test/next", "unsupported scheme 'ftp'"),
        ("http://:8080/next", "missing host"),
        ("http://example.test:0/next", "port must be between 1 and 65535"),
    ],
)
def test_analyze_url_records_invalid_redirect_target_as_error_step(location: str, reason: str) -> None:
    executor = StubExecutor([(302, location), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/start", method=HTTPMethod.POST, content=b"x")

    assert len(executor.calls) == 1
    assert len(steps) == 2
    redirect, failed = steps
    assert redirect.response.status == 302
    assert not redirect.has_error
    assert failed.step_number == 2
    assert failed.url == location
    assert failed.request_method == "GET"
    assert failed.request_body_bytes == 0
    assert failed.error_kind == "network"
    assert (failed.error or "").startswith(f"Invalid redirect target: {reason}")
    assert failed.response.status is None


def test_analyze_url_redacts_credentials_of_invalid_redirect_target() -> None:
    executor = StubExecutor([(302, "http://alice:topsecret@example.test:99999/next")])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/start")

    assert steps[1].url == "http://alice:****@example.test:99999/next"
    assert "topsecret" not in repr(steps[1].to_dict())


def test_analyze_url_resolves_invalid_relative_redirect_against_current_url() -> None:
    executor = StubExecutor([(302, "//example.test:99999/next")])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/start")

    assert steps[1].url == "https://example.test:99999/next"
    assert steps[1].has_error


def test_analyze_url_redirect_limit_takes_precedence_over_invalid_target() -> None:
    executor = StubExecutor([(302, "http://example.test:99999/next")])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, max_redirects=0, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/start")

    assert len(steps) == 1
    assert steps[0].redirect_limit_reached
    assert not steps[0].has_error


def test_analyze_url_redacts_location_but_follows_real_target() -> None:
    executor = StubExecutor([(302, "http://alice:topsecret@example.test/ok"), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/start")

    assert executor.urls[1] == "http://alice:topsecret@example.test/ok"
    assert steps[0].response.location == "http://alice:****@example.test/ok"
    assert steps[1].url == "http://alice:****@example.test/ok"


def test_analyze_url_redacts_location_without_following() -> None:
    executor = StubExecutor([(302, "http://alice:topsecret@example.test/ok")])
    analyzer = HTTPTapAnalyzer(request_executor=executor)

    steps = analyzer.analyze_url("https://example.test/start")

    assert steps[0].response.location == "http://alice:****@example.test/ok"
    assert steps[0].is_redirect


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
    assert not steps[-1].has_error
    assert steps[-1].note == "Maximum redirects followed (5)"
    assert steps[-1].redirect_limit_reached


def test_analyze_url_allows_final_response_at_redirect_limit() -> None:
    """A non-redirect response after the allowed redirects succeeds."""
    executor = StubExecutor(
        [(301, f"https://example.test/{index}") for index in range(5)] + [(200, None)],
    )
    analyzer = HTTPTapAnalyzer(
        follow_redirects=True,
        max_redirects=5,
        request_executor=executor,
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 6
    assert steps[-1].response.status == 200
    assert not steps[-1].has_error


def test_analyze_url_shares_deadline_across_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every redirect hop receives the same chain deadline."""

    class DeadlineRecordingExecutor:
        def __init__(self) -> None:
            self.deadlines: list[float | None] = []
            self.timeouts: list[float] = []
            self.responses = [(301, "https://example.test/final"), (200, None)]

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.deadlines.append(options.deadline)
            self.timeouts.append(options.timeout)
            clock[0] += 1.0
            status, location = self.responses.pop(0)
            return RequestOutcome(
                timing=TimingMetrics(total_ms=10.0),
                network=NetworkInfo(ip="203.0.113.5", ip_family="IPv4"),
                response=ResponseInfo(status=status, location=location),
            )

    clock = [100.0]
    executor = DeadlineRecordingExecutor()
    monkeypatch.setattr("httptap.analyzer.time.monotonic", lambda: clock[0])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, timeout=2.0, request_executor=executor)

    analyzer.analyze_url("https://example.test")

    assert executor.deadlines == [102.0, 102.0]
    assert executor.timeouts == [2.0, 1.0]


def test_analyze_url_stops_when_redirect_deadline_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired chain deadline prevents the next redirect request."""

    class ExpiringExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, _options: RequestOptions) -> RequestOutcome:
            self.calls += 1
            clock[0] = 103.0
            return RequestOutcome(
                timing=TimingMetrics(total_ms=10.0),
                network=NetworkInfo(ip="203.0.113.5", ip_family="IPv4"),
                response=ResponseInfo(status=301, location="https://example.test/final"),
            )

    clock = [100.0]
    executor = ExpiringExecutor()
    monkeypatch.setattr("httptap.analyzer.time.monotonic", lambda: clock[0])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, timeout=2.0, request_executor=executor)

    steps = analyzer.analyze_url("https://example.test")

    assert executor.calls == 1
    assert len(steps) == 2
    assert steps[-1].error == "Request timeout: total deadline exceeded"


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
    assert steps[0].error_kind == "internal"
    assert "Unexpected failure" in (steps[0].error or "")
    assert "Unexpected error" in (steps[0].note or "")


def test_analyze_url_preserves_network_info_from_failed_request() -> None:
    """Network metadata from a transport failure remains visible on the step."""

    class VerificationFailingExecutor:
        def execute(self, _options: RequestOptions) -> RequestOutcome:
            network = NetworkInfo(cert_cn="expired.example.test", cert_days_left=-1)
            message = "certificate verify failed"
            raise HTTPClientError(message, network_info=network)

    steps = HTTPTapAnalyzer(request_executor=VerificationFailingExecutor()).analyze_url("https://expired.example.test")

    assert steps[0].error == "certificate verify failed"
    assert steps[0].network.cert_cn == "expired.example.test"
    assert steps[0].network.cert_days_left == -1


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


def test_analyze_url_with_socks5h_proxy() -> None:
    """Test that socks5h proxy (remote DNS) is properly passed through analyzer."""

    class ProxyAwareExecutor:
        def __init__(self) -> None:
            self.proxies: list[object | None] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.proxies.append(options.proxy)
            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.1", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ProxyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        proxy="socks5h://gateway:1080",
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.proxies == ["socks5h://gateway:1080"]
    assert steps[0].proxied_via == "socks5h://gateway:1080"


def test_analyze_url_with_http_proxy() -> None:
    """Test that HTTP proxy is properly passed through analyzer."""

    class ProxyAwareExecutor:
        def __init__(self) -> None:
            self.proxies: list[object | None] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.proxies.append(options.proxy)
            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.2", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ProxyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        proxy="http://proxy.example.com:8080",
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.proxies == ["http://proxy.example.com:8080"]
    assert steps[0].proxied_via == "http://proxy.example.com:8080"


def test_analyze_url_with_https_proxy() -> None:
    """Test that HTTPS proxy is properly passed through analyzer."""

    class ProxyAwareExecutor:
        def __init__(self) -> None:
            self.proxies: list[object | None] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.proxies.append(options.proxy)
            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.3", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ProxyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        proxy="https://secure-proxy.example.com:8443",
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.proxies == ["https://secure-proxy.example.com:8443"]
    assert steps[0].proxied_via == "https://secure-proxy.example.com:8443"


def test_analyze_url_with_socks5_proxy() -> None:
    """Test that socks5 proxy (local DNS) is properly passed through analyzer."""

    class ProxyAwareExecutor:
        def __init__(self) -> None:
            self.proxies: list[object | None] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.proxies.append(options.proxy)
            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.4", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ProxyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        proxy="socks5://gateway:1080",
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.proxies == ["socks5://gateway:1080"]
    assert steps[0].proxied_via == "socks5://gateway:1080"


def test_analyze_url_with_proxy_and_redirects() -> None:
    """Test that proxy is used for all requests in redirect chain."""

    class ProxyAwareExecutor:
        def __init__(self) -> None:
            self.proxies: list[object | None] = []
            self.call_count = 0

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.proxies.append(options.proxy)
            self.call_count += 1

            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.5", ip_family="IPv4")

            if self.call_count == 1:
                response = ResponseInfo(status=301, location="https://example.test/final")
            else:
                response = ResponseInfo(status=200)

            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ProxyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        proxy="socks5h://gateway:1080",
        follow_redirects=True,
    )

    steps = analyzer.analyze_url("https://example.test/initial")

    assert len(steps) == 2
    assert steps[0].response.status == 301
    assert steps[1].response.status == 200
    # Verify proxy was used for both requests
    assert executor.proxies == ["socks5h://gateway:1080", "socks5h://gateway:1080"]
    assert steps[0].proxied_via == "socks5h://gateway:1080"
    assert steps[1].proxied_via == "socks5h://gateway:1080"


def test_analyze_url_proxy_with_authentication() -> None:
    """Test that proxy with authentication credentials is properly handled."""

    class ProxyAwareExecutor:
        def __init__(self) -> None:
            self.proxies: list[object | None] = []

        def execute(self, options: RequestOptions) -> RequestOutcome:
            self.proxies.append(options.proxy)
            timing = TimingMetrics(total_ms=10.0)
            network = NetworkInfo(ip="198.51.100.6", ip_family="IPv4")
            response = ResponseInfo(status=200)
            return RequestOutcome(timing=timing, network=network, response=response)

    executor = ProxyAwareExecutor()
    analyzer = HTTPTapAnalyzer(
        request_executor=executor,
        proxy="socks5h://user:password@gateway:1080",
    )

    steps = analyzer.analyze_url("https://example.test")

    assert len(steps) == 1
    assert steps[0].response.status == 200
    assert executor.proxies == ["socks5h://user:password@gateway:1080"]
    assert steps[0].proxied_via == "socks5h://user:****@gateway:1080"


class RecordingExecutor:
    def __init__(self, results: list[tuple[int, str | None]]) -> None:
        self.results = results
        self.calls: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RequestOutcome:
        self.calls.append(options)
        status, location = self.results.pop(0)
        timing = TimingMetrics(total_ms=10.0)
        network = NetworkInfo(ip="203.0.113.5", ip_family="IPv4")
        response = ResponseInfo(status=status, location=location)
        return RequestOutcome(timing=timing, network=network, response=response)


CREDENTIAL_HEADERS = {
    "Authorization": "Bearer secret",
    "Cookie": "session=1",
    "Host": "vhost.test",
    "Proxy-Authorization": "Basic cHJveHk6cHc=",
    "X-Trace": "abc",
}


@pytest.mark.parametrize(
    ("initial_url", "location"),
    [
        ("https://example.test/start", "https://attacker.test/landing"),
        ("https://example.test/start", "http://example.test/landing"),
        ("https://example.test/start", "https://example.test:8443/landing"),
        ("http://example.test:8080/start", "https://example.test/landing"),
    ],
)
def test_analyze_url_drops_credentials_on_cross_origin_redirect(initial_url: str, location: str) -> None:
    executor = RecordingExecutor([(302, location), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url(initial_url, headers=CREDENTIAL_HEADERS)

    assert executor.calls[0].headers == CREDENTIAL_HEADERS
    assert executor.calls[1].headers == {"X-Trace": "abc"}
    assert steps[1].request_headers == {"X-Trace": "abc"}


@pytest.mark.parametrize(
    ("initial_url", "location"),
    [
        ("https://example.test/start", "/landing"),
        ("https://example.test/start", "https://EXAMPLE.test:443/landing"),
        ("http://example.test/start", "https://example.test/landing"),
    ],
)
def test_analyze_url_keeps_credentials_on_same_origin_or_https_upgrade(initial_url: str, location: str) -> None:
    executor = RecordingExecutor([(301, location), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    analyzer.analyze_url(initial_url, headers=CREDENTIAL_HEADERS)

    assert executor.calls[1].headers == CREDENTIAL_HEADERS


def test_analyze_url_drops_credentials_for_rest_of_chain_after_cross_origin_hop() -> None:
    executor = RecordingExecutor(
        [(302, "https://other.test/a"), (302, "https://example.test/b"), (200, None)],
    )
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    analyzer.analyze_url("https://example.test/start", headers=CREDENTIAL_HEADERS)

    assert executor.calls[2].headers == {"X-Trace": "abc"}


@pytest.mark.parametrize(
    ("status", "method", "expected_method"),
    [
        (303, HTTPMethod.POST, HTTPMethod.GET),
        (303, HTTPMethod.PUT, HTTPMethod.GET),
        (301, HTTPMethod.POST, HTTPMethod.GET),
        (302, HTTPMethod.POST, HTTPMethod.GET),
    ],
)
def test_analyze_url_switches_to_get_without_body(
    status: int,
    method: HTTPMethod,
    expected_method: HTTPMethod,
) -> None:
    executor = RecordingExecutor([(status, "/landing"), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)
    headers = {"Content-Type": "application/json", "X-Trace": "abc"}

    steps = analyzer.analyze_url("https://example.test/form", method=method, content=b'{"a":1}', headers=headers)

    assert executor.calls[1].method == expected_method
    assert executor.calls[1].content is None
    assert executor.calls[1].headers == {"X-Trace": "abc"}
    assert steps[1].request_method == expected_method.value
    assert steps[1].request_body_bytes == 0


@pytest.mark.parametrize(
    ("status", "method"),
    [
        (307, HTTPMethod.POST),
        (308, HTTPMethod.POST),
        (302, HTTPMethod.PUT),
        (303, HTTPMethod.HEAD),
    ],
)
def test_analyze_url_preserves_method_and_body(status: int, method: HTTPMethod) -> None:
    executor = RecordingExecutor([(status, "/landing"), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)
    headers = {"Content-Type": "application/json"}

    analyzer.analyze_url("https://example.test/form", method=method, content=b'{"a":1}', headers=headers)

    assert executor.calls[1].method == method
    assert executor.calls[1].content == b'{"a":1}'
    assert executor.calls[1].headers == headers


def test_analyze_url_redirect_without_headers() -> None:
    executor = RecordingExecutor([(302, "https://other.test/"), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    analyzer.analyze_url("https://example.test/")

    assert executor.calls[1].headers is None


def test_analyze_url_redacts_userinfo_in_steps_but_requests_with_it() -> None:
    """URL credentials authenticate the request but never reach the step data."""
    executor = RecordingExecutor([(302, "/next"), (200, None)])
    analyzer = HTTPTapAnalyzer(follow_redirects=True, request_executor=executor)

    steps = analyzer.analyze_url("https://user:s3cret@example.test/start")

    assert [call.url for call in executor.calls] == [
        "https://user:s3cret@example.test/start",
        "https://user:s3cret@example.test/next",
    ]
    assert [step.url for step in steps] == [
        "https://user:****@example.test/start",
        "https://user:****@example.test/next",
    ]


class _FailingExecutor:
    def __init__(self, network: NetworkInfo) -> None:
        self.network = network

    def execute(self, options: RequestOptions) -> RequestOutcome:
        del options
        message = "Request failed: connection refused"
        raise HTTPClientError(message, network_info=self.network)


def test_failed_step_keeps_partial_network_info_and_proxy() -> None:
    """A failed request still reports where it went and through which proxy."""
    network = NetworkInfo(
        ip="203.0.113.7", ip_family="IPv4", proxy_url="http://proxy.test:3128", proxy_source="--proxy"
    )
    analyzer = HTTPTapAnalyzer(request_executor=_FailingExecutor(network))

    step = analyzer.analyze_url("http://example.test/")[0]

    assert step.error_kind == "network"
    assert step.network.ip == "203.0.113.7"
    assert step.proxied_via == "http://proxy.test:3128"


class _StalledBodyExecutor:
    def execute(self, options: RequestOptions) -> RequestOutcome:
        del options
        received = ResponseInfo(
            status=200,
            bytes=1,
            location="http://alice:topsecret@example.test/next",
            headers={"content-length": "100"},
        )
        message = "Request timeout: total deadline exceeded"
        raise HTTPClientError(message, network_info=NetworkInfo(ip="203.0.113.7"), response_info=received)


def test_failed_step_keeps_the_response_received_before_the_failure() -> None:
    """A body that stalls after the headers still reports the status, headers and bytes received."""
    analyzer = HTTPTapAnalyzer(request_executor=_StalledBodyExecutor(), follow_redirects=True)

    steps = analyzer.analyze_url("http://example.test/")

    assert len(steps) == 1
    step = steps[0]
    assert step.error_kind == "network"
    assert step.response.status == 200
    assert step.response.bytes == 1
    assert step.response.headers == {"content-length": "100"}
    assert step.response.location == "http://alice:****@example.test/next"


def test_failed_step_falls_back_to_configured_proxy() -> None:
    analyzer = HTTPTapAnalyzer(
        request_executor=_FailingExecutor(NetworkInfo()),
        proxy="http://user:pw@proxy.test:3128",
    )

    step = analyzer.analyze_url("http://example.test/")[0]

    assert step.proxied_via == "http://user:****@proxy.test:3128"
