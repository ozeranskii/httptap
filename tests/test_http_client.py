from __future__ import annotations

import ssl
from types import SimpleNamespace, TracebackType
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from typing_extensions import Self

from httptap.http_client import make_request
from httptap.models import NetworkInfo, TimingMetrics

if TYPE_CHECKING:
    import pytest_httpx
    import pytest_mock
    from faker import Faker


class FakeDNSResolver:
    def resolve(
        self,
        _host: str,
        _port: int,
        _timeout: float,
    ) -> tuple[str, str, float]:
        return "203.0.113.10", "IPv4", 4.2


class FakeTLSInspector:
    def inspect(self, host: str, _port: int, _timeout: float) -> NetworkInfo:
        info = NetworkInfo()
        info.tls_version = "TLSv1.3"
        info.tls_cipher = "TLS_AES_128_GCM_SHA256"
        info.cert_cn = host
        info.cert_days_left = 90
        return info


class FakeTimingCollector:
    def __init__(self, metrics: TimingMetrics) -> None:
        self._metrics = metrics

    def mark_dns_start(self) -> None:  # pragma: no cover - simple no-op
        return None

    def mark_dns_end(self) -> None:  # pragma: no cover - simple no-op
        return None

    def mark_request_start(self) -> None:  # pragma: no cover - simple no-op
        return None

    def mark_ttfb(self) -> None:  # pragma: no cover - simple no-op
        return None

    def mark_request_end(self) -> None:  # pragma: no cover - simple no-op
        return None

    def get_metrics(self) -> TimingMetrics:
        return self._metrics


@pytest.mark.parametrize(
    "status_code",
    [200, 201],
)
def test_make_request_uses_custom_headers(
    httpx_mock: pytest_httpx.HTTPXMock,
    faker: Faker,
    status_code: int,
) -> None:
    url = "https://example.test/api"
    body = b'{"ok": true}'
    token = f"Bearer {faker.hexify('^' * 16)}"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == token
        assert request.headers["Accept"] == "application/json"
        assert request.headers["User-Agent"].startswith("httptap/")
        return httpx.Response(
            status_code,
            headers={"content-type": "application/json"},
            content=body,
        )

    dns_resolver = FakeDNSResolver()
    ip, _family, _dns_ms = dns_resolver.resolve("example.test", 443, 5.0)
    httpx_mock.add_callback(handler, method="GET", url=f"https://{ip}/api")

    timing_input = TimingMetrics(
        dns_ms=4.2,
        connect_ms=0.0,
        tls_ms=0.0,
        ttfb_ms=50.0,
        total_ms=55.0,
    )

    timing, network, response = make_request(
        url,
        timeout=5.0,
        http2=False,
        dns_resolver=dns_resolver,
        tls_inspector=FakeTLSInspector(),
        timing_collector=FakeTimingCollector(timing_input),
        force_new_connection=False,
        headers={"Authorization": token, "Accept": "application/json"},
    )

    assert response.status == status_code
    assert response.bytes == len(body)
    assert network.tls_version == "TLSv1.3"
    assert network.cert_cn == "example.test"
    assert timing.is_estimated is True  # connect/TLS derived from heuristics


class TestBuildUserAgent:
    """Test suite for _build_user_agent function."""

    def test_build_user_agent_includes_version(self) -> None:
        """Test that user agent includes package version."""
        from httptap.http_client import USER_AGENT

        assert "httptap/" in USER_AGENT
        assert "+https://github.com/ozeranskii/httptap" in USER_AGENT

    def test_build_user_agent_handles_package_not_found(
        self,
        mocker: pytest_mock.MockerFixture,
        faker: Faker,
    ) -> None:
        """Test that _build_user_agent handles PackageNotFoundError."""
        from httptap._pkgmeta import PackageInfo

        mocker.patch(
            "httptap._pkgmeta.get_package_info",
            return_value=PackageInfo(
                version="0.0.0",
                author=faker.name(),
                homepage=faker.url(),
                license=faker.pystr(min_chars=5, max_chars=12),
            ),
        )

        # Reload module to trigger _build_user_agent with mocked metadata
        import importlib

        import httptap.http_client

        importlib.reload(httptap.http_client)

        # Should use "0.0.0" as fallback version
        assert "httptap/0.0.0" in httptap.http_client.USER_AGENT


class TestBuildTimingMetrics:
    """Test suite for _build_timing_metrics function."""

    def test_build_timing_with_precise_connect_and_tls(self) -> None:
        """Test building timing with precise connect and TLS values."""
        from httptap.http_client import _build_timing_metrics

        timing_input = TimingMetrics(
            dns_ms=5.0,
            ttfb_ms=100.0,
            total_ms=150.0,
        )
        collector = FakeTimingCollector(timing_input)

        timing = _build_timing_metrics(
            collector,
            is_https=True,
            connect_ms=20.0,
            tls_ms=50.0,
        )

        assert timing.connect_ms == 20.0
        assert timing.tls_ms == 50.0
        assert timing.is_estimated is False

    def test_build_timing_estimates_https_when_missing(self) -> None:
        """Test HTTPS timing estimation when precise values unavailable."""
        from httptap.http_client import _build_timing_metrics

        timing_input = TimingMetrics(
            dns_ms=10.0,
            ttfb_ms=100.0,
            total_ms=150.0,
        )
        collector = FakeTimingCollector(timing_input)

        timing = _build_timing_metrics(
            collector,
            is_https=True,
            connect_ms=None,
            tls_ms=None,
        )

        # Connection phase = 100 - 10 = 90ms
        # Should split 30% connect (27ms), 70% TLS (63ms)
        assert timing.connect_ms == pytest.approx(27.0, abs=0.1)
        assert timing.tls_ms == pytest.approx(63.0, abs=0.1)
        assert timing.is_estimated is True

    def test_build_timing_estimates_http_when_missing(self) -> None:
        """Test HTTP timing estimation (no TLS)."""
        from httptap.http_client import _build_timing_metrics

        timing_input = TimingMetrics(
            dns_ms=5.0,
            ttfb_ms=50.0,
            total_ms=100.0,
        )
        collector = FakeTimingCollector(timing_input)

        timing = _build_timing_metrics(
            collector,
            is_https=False,
            connect_ms=None,
            tls_ms=None,
        )

        # Connection phase = 50 - 5 = 45ms
        # All goes to connect for HTTP
        assert timing.connect_ms == 45.0
        assert timing.tls_ms == 0.0
        assert timing.is_estimated is False  # HTTP doesn't need TLS estimation

    def test_build_timing_uses_partial_precise_values(self) -> None:
        """Test using only connect_ms when tls_ms is None."""
        from httptap.http_client import _build_timing_metrics

        timing_input = TimingMetrics(
            dns_ms=10.0,
            ttfb_ms=100.0,
            total_ms=150.0,
        )
        collector = FakeTimingCollector(timing_input)

        timing = _build_timing_metrics(
            collector,
            is_https=True,
            connect_ms=30.0,
            tls_ms=None,
        )

        # Connect is precise, but TLS still estimated
        assert timing.connect_ms == 30.0
        assert timing.is_estimated is False


class TestPopulateResponseMetadata:
    """Test suite for _populate_response_metadata function."""

    def test_populate_response_metadata_with_all_headers(self) -> None:
        """Test populating response metadata with all headers present."""
        from httptap.http_client import _populate_response_metadata
        from httptap.models import ResponseInfo

        response = httpx.Response(
            status_code=200,
            headers={
                "content-type": "application/json",
                "server": "nginx/1.21",
                "location": "/redirected",
                "date": "Mon, 23 Oct 2025 12:00:00 GMT",
                "x-custom": "value",
            },
        )

        response_info = ResponseInfo()
        _populate_response_metadata(response, response_info)

        assert response_info.status == 200
        assert response_info.content_type == "application/json"
        assert response_info.server == "nginx/1.21"
        assert response_info.location == "/redirected"
        assert response_info.date is not None
        assert "x-custom" in response_info.headers

    def test_populate_response_metadata_without_date(self) -> None:
        """Test populating response metadata without date header."""
        from httptap.http_client import _populate_response_metadata
        from httptap.models import ResponseInfo

        response = httpx.Response(
            status_code=404,
            headers={
                "content-type": "text/html",
            },
        )

        response_info = ResponseInfo()
        _populate_response_metadata(response, response_info)

        assert response_info.status == 404
        assert response_info.content_type == "text/html"
        assert response_info.date is None


class TestConsumeResponseBody:
    """Test suite for _consume_response_body function."""

    def test_consume_response_body_counts_bytes(self) -> None:
        """Test consuming response body and counting bytes."""
        from httptap.http_client import _consume_response_body

        body = b"Hello, World!" * 100
        response = httpx.Response(200, content=body)

        total_bytes = _consume_response_body(response)

        assert total_bytes == len(body)


class TestPopulateTLSFromStream:
    """Test suite for _populate_tls_from_stream function."""

    def test_populate_tls_from_stream_enriches_network_info(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Stream with SSL object enriches network info fields."""
        from httptap.http_client import _populate_tls_from_stream

        response = httpx.Response(200)
        network_info = NetworkInfo()

        class FakeSSLSocket:
            def version(self) -> str:
                return "TLSv1.3"

            def cipher(self) -> tuple[str, str, int]:
                return ("TLS_AES_128_GCM_SHA256", "TLSv1.3", 128)

        class FakeStream:
            def get_extra_info(self, name: str) -> FakeSSLSocket | None:
                return FakeSSLSocket() if name == "ssl_object" else None

        response.extensions["network_stream"] = FakeStream()
        mocker.patch("httptap.http_client.ssl.SSLSocket", FakeSSLSocket)
        mocker.patch(
            "httptap.http_client.extract_certificate_info",
            return_value=SimpleNamespace(
                common_name="example.test",
                days_until_expiry=120,
            ),
        )

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher == "TLS_AES_128_GCM_SHA256"
        assert network_info.cert_cn == "example.test"
        assert network_info.cert_days_left == 120

    def test_populate_tls_from_stream_preserves_existing_fields(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Existing TLS metadata is not overwritten by stream data."""
        from httptap.http_client import _populate_tls_from_stream

        response = httpx.Response(200)
        network_info = NetworkInfo(
            tls_version="TLSv1.2",
            tls_cipher="TLS_CHACHA20_POLY1305_SHA256",
            cert_cn="cached.example",
            cert_days_left=30,
        )

        class FakeSSLSocket:
            def version(self) -> str:
                return "TLSv1.3"

            def cipher(self) -> tuple[str, str, int]:
                return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

        class FakeStream:
            def get_extra_info(self, name: str) -> FakeSSLSocket | None:
                return FakeSSLSocket() if name == "ssl_object" else None

        response.extensions["network_stream"] = FakeStream()
        mocker.patch("httptap.http_client.ssl.SSLSocket", FakeSSLSocket)
        mocker.patch(
            "httptap.http_client.extract_certificate_info",
            return_value=SimpleNamespace(
                common_name="stream.example",
                days_until_expiry=365,
            ),
        )

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.2"
        assert network_info.tls_cipher == "TLS_CHACHA20_POLY1305_SHA256"
        assert network_info.cert_cn == "cached.example"
        assert network_info.cert_days_left == 30

    def test_populate_tls_from_stream_handles_missing_ssl_object(self) -> None:
        """Gracefully handle streams without SSL metadata."""
        from httptap.http_client import _populate_tls_from_stream

        response = httpx.Response(200)
        network_info = NetworkInfo()

        class NullStream:
            def get_extra_info(self, name: str) -> None:
                assert name == "ssl_object"

        response.extensions["network_stream"] = NullStream()

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version is None
        assert network_info.tls_cipher is None

    def test_populate_tls_from_stream_without_sslsocket(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Streams that return non-SSLSocket objects only populate TLS basics."""
        from httptap.http_client import _populate_tls_from_stream

        response = httpx.Response(200)
        network_info = NetworkInfo()

        class PseudoSSLObject:
            def version(self) -> str:
                return "TLSv1.2"

            def cipher(self) -> tuple[str, str, int]:
                return ("TLS_RSA_WITH_AES_128_GCM_SHA256", "TLSv1.2", 128)

        class FakeStream:
            def __init__(self) -> None:
                self._ssl = PseudoSSLObject()

            def get_extra_info(self, name: str) -> PseudoSSLObject | None:
                return self._ssl if name == "ssl_object" else None

        response.extensions["network_stream"] = FakeStream()
        mocker.patch(
            "httptap.http_client.extract_certificate_info",
            side_effect=AssertionError("should not be called"),
        )

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.2"
        assert network_info.tls_cipher == "TLS_RSA_WITH_AES_128_GCM_SHA256"
        assert network_info.cert_cn is None

    def test_populate_tls_from_stream_when_cipher_missing(self) -> None:
        """Cipherless streams leave tls_cipher unset while keeping other data."""
        from httptap.http_client import _populate_tls_from_stream

        response = httpx.Response(200)
        network_info = NetworkInfo()

        class MinimalSSLObject:
            def version(self) -> str:
                return "TLSv1.3"

            def cipher(self) -> tuple[str, str, int]:
                msg = "cipher unavailable"
                raise AttributeError(msg)

        class FakeStream:
            def get_extra_info(self, name: str) -> MinimalSSLObject | None:
                return MinimalSSLObject() if name == "ssl_object" else None

        response.extensions["network_stream"] = FakeStream()

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher is None


def test_extract_ssl_object_handles_non_callable_getter() -> None:
    """Non-callable network stream extras should be ignored safely."""
    from httptap.http_client import _extract_ssl_object

    response = httpx.Response(200)

    class NonCallableStream:
        get_extra_info = None

    response.extensions["network_stream"] = NonCallableStream()

    assert _extract_ssl_object(response) is None


class TestTraceCollector:
    """Test suite for TraceCollector class."""

    def test_trace_collector_captures_connect_timing(self) -> None:
        """Test that TraceCollector captures TCP connect timing."""
        from httptap.http_client import TraceCollector

        trace = TraceCollector()

        # Simulate httpcore trace events
        trace("connection.connect_tcp.started", {})
        trace("connection.connect_tcp.complete", {})

        connect_ms = trace.connect_ms
        assert connect_ms is not None
        assert connect_ms >= 0.0

    def test_trace_collector_captures_tls_timing(self) -> None:
        """Test that TraceCollector captures TLS handshake timing."""
        from httptap.http_client import TraceCollector

        trace = TraceCollector()

        trace("connection.start_tls.started", {})
        trace("connection.start_tls.complete", {})

        tls_ms = trace.tls_ms
        assert tls_ms is not None
        assert tls_ms >= 0.0

    def test_trace_collector_returns_none_for_missing_events(self) -> None:
        """Test that TraceCollector returns None for incomplete events."""
        from httptap.http_client import TraceCollector

        trace = TraceCollector()

        # No events captured
        assert trace.connect_ms is None
        assert trace.tls_ms is None

    def test_trace_collector_returns_none_for_incomplete_events(self) -> None:
        """Test that TraceCollector handles incomplete event pairs."""
        from httptap.http_client import TraceCollector

        trace = TraceCollector()

        # Only started, no complete
        trace("connection.connect_tcp.started", {})

        assert trace.connect_ms is None

    def test_trace_collector_ignores_invalid_events(self) -> None:
        """Test that TraceCollector ignores events without proper structure."""
        from httptap.http_client import TraceCollector

        trace = TraceCollector()

        # Event without prefix (no dot)
        trace("invalid_event", {})

        # Should not crash, just ignore
        assert trace.connect_ms is None

    def test_trace_collector_handles_inverted_timestamps(self) -> None:
        """Test that TraceCollector handles end before start."""
        import time

        from httptap.http_client import TraceCollector

        trace = TraceCollector()

        # Manually simulate inverted order
        trace._events["connection.connect_tcp"] = {
            "started": time.perf_counter(),
            "complete": time.perf_counter() - 1.0,  # Earlier than start
        }

        # Should return None for invalid duration
        assert trace.connect_ms is None


class TestMakeRequest:
    """Test suite for make_request function."""

    def test_make_request_http_success(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test successful HTTP request."""
        url = "http://example.test/page"
        body = b"<!DOCTYPE html><html></html>"

        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("example.test", 80, 5.0)
        httpx_mock.add_response(
            method="GET",
            url=f"http://{ip}/page",
            status_code=200,
            content=body,
            headers={"content-type": "text/html"},
        )

        timing, network, response = make_request(
            url,
            timeout=5.0,
            http2=False,
            dns_resolver=dns_resolver,
            timing_collector=FakeTimingCollector(
                TimingMetrics(dns_ms=5.0, ttfb_ms=50.0, total_ms=100.0),
            ),
            force_new_connection=False,
        )

        assert response.status == 200
        assert response.bytes == len(body)
        assert network.ip == "203.0.113.10"
        assert timing.total_ms > 0

    def test_make_request_https_with_tls_inspection(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test HTTPS request with TLS inspection."""
        url = "https://secure.test/api"
        body = b'{"success": true}'

        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("secure.test", 443, 5.0)
        httpx_mock.add_response(
            method="GET",
            url=f"https://{ip}/api",
            status_code=200,
            content=body,
        )

        _timing, network, response = make_request(
            url,
            timeout=5.0,
            dns_resolver=dns_resolver,
            tls_inspector=FakeTLSInspector(),
            timing_collector=FakeTimingCollector(
                TimingMetrics(dns_ms=5.0, ttfb_ms=50.0, total_ms=100.0),
            ),
            force_new_connection=False,
        )

        assert response.status == 200
        assert network.tls_version == "TLSv1.3"
        assert network.cert_cn == "secure.test"
        assert network.cert_days_left == 90

    def test_make_request_dials_ip_and_sets_host_header_and_sni(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Dial IP but preserve original host for headers and SNI."""
        url = "https://example.test/api?q=ok"
        captured: dict[str, object] = {}

        class DummyStream:
            def __init__(self, request_url: str) -> None:
                self.request_url = request_url

            def __enter__(self) -> httpx.Response:
                request = httpx.Request("GET", self.request_url)
                return httpx.Response(
                    200,
                    request=request,
                    headers={"content-type": "application/json"},
                    content=b"{}",
                    extensions={"network_stream": SimpleNamespace(get_extra_info=lambda _n: None)},
                )

            def __exit__(self, *_exc: object) -> None:
                return None

        class DummyClient:
            def __init__(self, *_: object, **__: object) -> None:
                self.headers: dict[str, str] = {}

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(
                self,
                method: str,
                request_url: str,
                *,
                extensions: dict[str, object] | None = None,
            ) -> DummyStream:
                assert method == "GET"
                assert extensions is not None
                captured["request_url"] = request_url
                captured["extensions"] = dict(extensions)
                captured["headers"] = dict(self.headers)
                return DummyStream(request_url)

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        timing_input = TimingMetrics(
            dns_ms=5.0,
            connect_ms=0.0,
            tls_ms=0.0,
            ttfb_ms=15.0,
            total_ms=20.0,
        )

        _timing, _network, response = make_request(
            url,
            timeout=5.0,
            dns_resolver=FakeDNSResolver(),
            tls_inspector=FakeTLSInspector(),
            timing_collector=FakeTimingCollector(timing_input),
            force_new_connection=True,
        )

        assert response.status == 200
        assert captured["request_url"] == "https://203.0.113.10:443/api?q=ok"
        assert captured["extensions"] is not None
        assert captured["headers"] is not None
        extensions = captured["extensions"]
        headers = captured["headers"]
        assert isinstance(extensions, dict)
        assert isinstance(headers, dict)
        assert extensions.get("sni_hostname") == "example.test"
        assert "trace" in extensions
        assert headers.get("Host") == "example.test"

    def test_make_request_brackets_ipv6_address(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """IPv6 targets are wrapped in brackets when dialing by IP."""
        url = "https://ipv6.test/"
        captured: dict[str, object] = {}

        class IPv6Resolver:
            def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                return "2001:db8::1", "IPv6", 1.0

        class DummyStream:
            def __init__(self, request_url: str) -> None:
                self.request_url = request_url

            def __enter__(self) -> httpx.Response:
                request = httpx.Request("GET", self.request_url)
                return httpx.Response(
                    200,
                    request=request,
                    headers={"content-type": "text/plain"},
                    content=b"ok",
                    extensions={"network_stream": SimpleNamespace(get_extra_info=lambda _n: None)},
                )

            def __exit__(self, *_exc: object) -> None:
                return None

        class DummyClient:
            def __init__(self, *_: object, **__: object) -> None:
                self.headers: dict[str, str] = {}

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(
                self,
                method: str,
                request_url: str,
                *,
                extensions: dict[str, object] | None = None,
            ) -> DummyStream:
                assert method == "GET"
                assert extensions is not None
                captured["request_url"] = request_url
                captured["extensions"] = dict(extensions)
                captured["headers"] = dict(self.headers)
                return DummyStream(request_url)

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        timing_input = TimingMetrics(dns_ms=1.0, ttfb_ms=5.0, total_ms=6.0)

        _timing, _network, response = make_request(
            url,
            timeout=2.0,
            dns_resolver=IPv6Resolver(),
            tls_inspector=FakeTLSInspector(),
            timing_collector=FakeTimingCollector(timing_input),
            force_new_connection=True,
        )

        assert response.status == 200
        assert captured["request_url"] == "https://[2001:db8::1]:443/"
        extensions = captured["extensions"]
        headers = captured["headers"]
        assert isinstance(extensions, dict)
        assert isinstance(headers, dict)
        assert extensions.get("sni_hostname") == "ipv6.test"
        assert headers.get("Host") == "ipv6.test"

    def test_make_request_handles_missing_hostname(self) -> None:
        """Test error handling for URL without hostname."""
        from httptap.http_client import HTTPClientError

        with pytest.raises(HTTPClientError, match="Invalid URL: missing hostname"):
            _timing, _network, _response = make_request(
                "http://",
                timeout=5.0,
                force_new_connection=False,
            )

    def test_make_request_handles_dns_error(self) -> None:
        """Test error handling for DNS resolution failure."""
        from httptap.http_client import HTTPClientError
        from httptap.implementations.dns import DNSResolutionError

        class FailingDNSResolver:
            def resolve(self, _h: str, _p: int, _t: float) -> tuple[str, str, float]:
                msg = "DNS lookup failed"
                raise DNSResolutionError(msg)

        with pytest.raises(HTTPClientError, match="DNS lookup failed"):
            make_request(
                "https://invalid.test",
                timeout=5.0,
                dns_resolver=FailingDNSResolver(),
                force_new_connection=False,
            )

    def test_make_request_handles_timeout(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test error handling for request timeout."""
        from httptap.http_client import HTTPClientError

        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("slow.test", 443, 5.0)
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timeout"),
            method="GET",
            url=f"https://{ip}",
        )

        with pytest.raises(HTTPClientError, match="Request timeout"):
            make_request(
                "https://slow.test",
                timeout=1.0,
                dns_resolver=dns_resolver,
                timing_collector=FakeTimingCollector(TimingMetrics()),
                force_new_connection=False,
            )

    def test_make_request_handles_connection_error(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test error handling for connection errors."""
        from httptap.http_client import HTTPClientError

        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("unreachable.test", 443, 5.0)
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            method="GET",
            url=f"https://{ip}",
        )

        with pytest.raises(HTTPClientError, match="Request failed"):
            make_request(
                "https://unreachable.test",
                timeout=5.0,
                dns_resolver=dns_resolver,
                timing_collector=FakeTimingCollector(TimingMetrics()),
                force_new_connection=False,
            )

    def test_make_request_handles_tls_inspection_error(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test that TLS inspection errors don't fail the request."""
        from httptap.implementations.tls import TLSInspectionError

        class FailingTLSInspector:
            def inspect(self, _h: str, _p: int, _t: float) -> NetworkInfo:
                msg = "TLS probe failed"
                raise TLSInspectionError(msg)

        url = "https://example.test"
        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("example.test", 443, 5.0)
        httpx_mock.add_response(method="GET", url=f"https://{ip}", status_code=200)

        # Should not raise, TLS inspection is non-fatal
        _timing, network, response = make_request(
            url,
            timeout=5.0,
            dns_resolver=dns_resolver,
            tls_inspector=FailingTLSInspector(),
            timing_collector=FakeTimingCollector(
                TimingMetrics(dns_ms=5.0, ttfb_ms=50.0, total_ms=100.0),
            ),
            force_new_connection=False,
        )

        assert response.status == 200
        # TLS info should be missing
        assert network.tls_version is None

    def test_make_request_uses_default_implementations(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test that make_request uses default implementations when not provided."""
        url = "http://example.test"
        httpx_mock.add_response(method="GET", url="http://198.51.100.5", status_code=200)

        # Mock DNS resolution to avoid real network call
        mock_resolve = mocker.patch(
            "httptap.implementations.dns.socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("198.51.100.5", 80)),
            ],
        )

        # Don't pass any custom implementations
        _timing, _network, response = make_request(
            url,
            timeout=5.0,
            http2=False,
            force_new_connection=False,
        )

        assert response.status == 200
        # Should have used default implementations successfully
        mock_resolve.assert_called_once()

    def test_make_request_force_new_connection_configures_limits(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test that force_new_connection properly configures httpx limits."""
        url = "https://example.test"
        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("example.test", 443, 5.0)
        httpx_mock.add_response(method="GET", url=f"https://{ip}", status_code=200)

        # Spy on httpx.Limits to verify configuration
        limits_spy = mocker.spy(httpx, "Limits")

        make_request(
            url,
            timeout=5.0,
            dns_resolver=dns_resolver,
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=100.0)),
            force_new_connection=True,
        )

        # Verify Limits was called with correct parameters
        limits_spy.assert_called_once_with(
            max_connections=1,
            max_keepalive_connections=0,
        )

    def test_make_request_disable_ssl_verification(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test that verify_ssl flag disables TLS verification."""
        url = "https://self-signed.test"
        created_clients: list[DummyClient] = []

        class DummyStream:
            def __enter__(self) -> httpx.Response:
                return response

            def __exit__(
                self,
                _exc_type: type[BaseException] | None,
                _exc: BaseException | None,
                _tb: TracebackType | None,
            ) -> None:
                return None

        class DummyClient:
            def __init__(self, *_: object, **kwargs: object) -> None:
                self.kwargs = kwargs
                self.headers: dict[str, str] = {}
                created_clients.append(self)

            def __enter__(self) -> Self:
                return self

            def __exit__(
                self,
                _exc_type: type[BaseException] | None,
                _exc: BaseException | None,
                _tb: TracebackType | None,
            ) -> None:
                return None

            def stream(
                self,
                method: str,
                request_url: str,
                *,
                content: bytes | None = None,
                extensions: dict[str, object] | None = None,
            ) -> DummyStream:
                assert method == "GET"
                assert content is None
                assert request_url == "https://203.0.113.10:443"
                assert extensions is not None
                assert "trace" in extensions
                return DummyStream()

        request = httpx.Request("GET", url)
        response = httpx.Response(
            200,
            request=request,
            headers={"content-type": "text/plain"},
            content=b"ok",
            extensions={
                "network_stream": SimpleNamespace(get_extra_info=lambda _name: None),
            },
        )

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        timing_input = TimingMetrics(
            dns_ms=2.0,
            connect_ms=0.0,
            tls_ms=0.0,
            ttfb_ms=10.0,
            total_ms=12.0,
        )

        _timing, network, obtained_response = make_request(
            url,
            timeout=5.0,
            verify_ssl=False,
            dns_resolver=FakeDNSResolver(),
            timing_collector=FakeTimingCollector(timing_input),
            force_new_connection=True,
        )

        assert obtained_response.status == 200
        assert created_clients
        verify_arg = created_clients[0].kwargs["verify"]
        assert isinstance(verify_arg, ssl.SSLContext)
        assert verify_arg.verify_mode == ssl.CERT_NONE
        assert verify_arg.check_hostname is False
        assert network.tls_verified is False

    def test_make_request_uses_proxies(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        url = "https://proxy.test"
        proxy_url = "socks5://gateway:1080"
        created_clients: list[Any] = []

        class DummyClient:
            def __init__(self, *_: object, **kwargs: object) -> None:
                self.kwargs = kwargs
                self.headers: dict[str, str] = {}
                created_clients.append(self)

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(self, *_args: object, **_kwargs: object) -> object:
                class _Stream:
                    def __enter__(self) -> httpx.Response:
                        request = httpx.Request("GET", url)
                        return httpx.Response(200, request=request)

                    def __exit__(self, *_exc: object) -> None:
                        return None

                return _Stream()

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        make_request(
            url,
            timeout=5.0,
            proxy=proxy_url,
            dns_resolver=FakeDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
            force_new_connection=True,
        )

        assert created_clients
        assert created_clients[0].kwargs["proxy"] == proxy_url

    def test_make_request_handles_unexpected_exception(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test handling of unexpected exceptions."""
        from httptap.http_client import HTTPClientError

        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("error.test", 443, 5.0)
        # Simulate unexpected exception
        httpx_mock.add_exception(
            RuntimeError("Unexpected internal error"),
            method="GET",
            url=f"https://{ip}",
        )

        with pytest.raises(HTTPClientError, match="Unexpected error"):
            make_request(
                "https://error.test",
                timeout=5.0,
                dns_resolver=dns_resolver,
                timing_collector=FakeTimingCollector(TimingMetrics()),
                force_new_connection=False,
            )


class TestNormalizeHttpVersion:
    """Unit tests for _normalize_http_version helper."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("HTTP/1.1", "HTTP/1.1"),
            ("HTTP/2", "HTTP/2.0"),
            ("h2", "HTTP/2.0"),
            ("H3", "HTTP/3.0"),
            ("HTTP/3.1", "HTTP/3.1"),
        ],
    )
    def test_normalizes_known_tokens(self, raw: str, expected: str) -> None:
        from httptap.http_client import _normalize_http_version

        assert _normalize_http_version(raw) == expected

    def test_returns_none_when_missing(self) -> None:
        from httptap.http_client import _normalize_http_version

        assert _normalize_http_version(None) is None

    def test_leaves_unknown_strings_untouched(self) -> None:
        from httptap.http_client import _normalize_http_version

        assert _normalize_http_version("spdy/3") == "spdy/3"
