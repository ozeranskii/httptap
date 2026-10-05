from __future__ import annotations

import gzip
import socket
import ssl
import threading
import time
from contextlib import suppress
from types import SimpleNamespace, TracebackType
from typing import TYPE_CHECKING, Any, NoReturn, Self

import httpcore
import httpx
import pytest
from httpcore._backends.sync import SyncBackend

from httptap.constants import (
    PROXY_SOURCE_CLI,
    PROXY_SOURCE_DISABLED,
    PROXY_SOURCE_NO_MATCH,
    PROXY_SOURCE_NO_PROXY,
)
from httptap.http_client import (
    USER_AGENT,
    HTTPClientError,
    TraceCollector,
    _build_timing_metrics,
    _build_user_agent,
    _consume_response_body,
    _DeadlineWatchdog,
    _extract_ssl_object,
    _host_matches_no_proxy,
    _is_certificate_verification_error,
    _needs_remote_dns,
    _normalize_http_version,
    _populate_response_metadata,
    _populate_tls_from_stream,
    _resolve_addresses,
    _resolve_effective_proxy,
    make_request,
    proxy_resolves_remotely,
)
from httptap.implementations.dns import DNSResolutionError, OverrideDNSResolver, SystemDNSResolver
from httptap.implementations.tls import SocketTLSInspector
from httptap.models import NetworkInfo, TimingMetrics
from httptap.tls_inspector import TLSInspectionError

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
        headers={"Authorization": token, "Accept": "application/json"},
    )

    assert response.status == status_code
    assert response.bytes == len(body)
    assert network.tls_version == "TLSv1.3"
    assert network.cert_cn == "example.test"
    assert timing.is_estimated is True  # connect/TLS derived from heuristics


def test_make_request_starts_timing_after_client_setup(  # noqa: C901
    mocker: pytest_mock.MockerFixture,
) -> None:
    events: list[str] = []

    class EventTimingCollector(FakeTimingCollector):
        def __init__(self) -> None:
            super().__init__(TimingMetrics(total_ms=1.0, ttfb_ms=1.0))

        def mark_dns_start(self) -> None:
            events.append("dns_start")

        def mark_dns_end(self) -> None:
            events.append("dns_end")

        def mark_request_start(self) -> None:
            events.append("request_start")

        def mark_ttfb(self) -> None:
            events.append("ttfb")

        def mark_request_end(self) -> None:
            events.append("request_end")

    class ResponseStream:
        def __enter__(self) -> httpx.Response:
            return httpx.Response(200, request=httpx.Request("GET", "https://203.0.113.10:443/"))

        def __exit__(self, *_exc: object) -> None:
            return None

    class DummyClient:
        def __init__(self, **_kwargs: object) -> None:
            events.append("client_init")
            self.headers: dict[str, str] = {}

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def stream(self, *_args: object, **_kwargs: object) -> ResponseStream:
            events.append("stream")
            return ResponseStream()

    def fake_create_ssl_context(**_kwargs: object) -> object:
        events.append("ssl_context")
        return object()

    mocker.patch("httptap.http_client.create_ssl_context", side_effect=fake_create_ssl_context)
    mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

    make_request(
        "https://example.test/",
        dns_resolver=FakeDNSResolver(),
        tls_inspector=FakeTLSInspector(),
        timing_collector=EventTimingCollector(),
    )

    assert events.index("request_start") > events.index("ssl_context")
    assert events.index("request_start") > events.index("client_init")
    assert events.index("request_start") < events.index("stream")


def test_make_request_preserves_user_host_header(
    httpx_mock: pytest_httpx.HTTPXMock,
) -> None:
    """A user-provided Host header is sent unchanged."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Host"] == "vhost.test"
        return httpx.Response(200, request=request)

    httpx_mock.add_callback(handler, method="GET", url="http://203.0.113.10:8000/")

    _timing, _network, response = make_request(
        "http://127.0.0.1:8000/",
        dns_resolver=FakeDNSResolver(),
        tls_inspector=FakeTLSInspector(),
        timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        headers={"host": "vhost.test"},
    )

    assert response.status == 200


def test_make_request_includes_non_default_port_in_host_header(
    httpx_mock: pytest_httpx.HTTPXMock,
) -> None:
    """The default Host header includes a non-default IPv4 port."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Host"] == "127.0.0.1:8000"
        return httpx.Response(200, request=request)

    httpx_mock.add_callback(handler, method="GET", url="http://203.0.113.10:8000/")

    _timing, _network, response = make_request(
        "http://127.0.0.1:8000/",
        dns_resolver=FakeDNSResolver(),
        tls_inspector=FakeTLSInspector(),
        timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
    )

    assert response.status == 200


def test_make_request_preserves_path_params_and_url_userinfo(
    httpx_mock: pytest_httpx.HTTPXMock,
) -> None:
    """URL userinfo becomes Basic auth without changing the request path."""
    url = "http://user:pw@example.test/a;jsessionid=1?q=1"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/a;jsessionid=1?q=1"
        assert request.headers["Authorization"] == "Basic dXNlcjpwdw=="
        return httpx.Response(200, request=request)

    dns_resolver = FakeDNSResolver()
    ip, _family, _dns_ms = dns_resolver.resolve("example.test", 80, 5.0)
    httpx_mock.add_callback(handler, method="GET", url=f"http://{ip}/a;jsessionid=1?q=1")

    _timing, _network, response = make_request(
        url,
        dns_resolver=dns_resolver,
        tls_inspector=FakeTLSInspector(),
        timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
    )

    assert response.status == 200


def test_make_request_preserves_explicit_authorization_over_url_userinfo(
    httpx_mock: pytest_httpx.HTTPXMock,
) -> None:
    """An explicit Authorization header overrides credentials from the URL."""
    url = "http://user:pw@example.test/"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer custom-token"
        return httpx.Response(200, request=request)

    httpx_mock.add_callback(handler, method="GET", url="http://203.0.113.10/")

    _timing, _network, response = make_request(
        url,
        dns_resolver=FakeDNSResolver(),
        tls_inspector=FakeTLSInspector(),
        timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        headers={"authorization": "Bearer custom-token"},
    )

    assert response.status == 200


def test_make_request_rejects_expired_deadline_before_dns() -> None:
    """An expired chain deadline does not start another network operation."""
    calls: list[tuple[str, int, float]] = []

    class TrackingResolver:
        def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
            calls.append((host, port, timeout))
            return "203.0.113.10", "IPv4", 1.0

    with pytest.raises(HTTPClientError, match="total deadline exceeded"):
        make_request(
            "http://example.test",
            deadline=0.0,
            dns_resolver=TrackingResolver(),
        )

    assert calls == []


def test_make_request_total_deadline_stops_slow_stream() -> None:
    """The total deadline interrupts a body that keeps producing chunks."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    streaming = threading.Event()
    stop = threading.Event()

    def serve() -> None:
        with suppress(OSError):
            connection, _address = listener.accept()
            with connection:
                connection.recv(4096)
                connection.sendall(
                    b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n1\r\na\r\n"
                )
                streaming.set()
                # Chunks arrive well within the per-read timeout, so only the
                # total deadline can end the transfer before the stream does.
                stream_until = time.monotonic() + 10.0
                while time.monotonic() < stream_until and not stop.wait(0.05):
                    connection.sendall(b"1\r\nb\r\n")
                connection.sendall(b"0\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    # A generous budget keeps DNS and connect on slow CI runners well inside it,
    # so the deadline is reached while the body is streaming.
    timeout = 2.0
    started = time.monotonic()
    try:
        with pytest.raises(HTTPClientError, match="total deadline exceeded"):
            make_request(f"http://127.0.0.1:{port}/", timeout=timeout, http2=False)
        elapsed = time.monotonic() - started
    finally:
        stop.set()
        listener.close()
        thread.join(timeout=5)

    assert streaming.is_set()
    assert elapsed < timeout + 3.0
    assert not thread.is_alive()


def _serve_stalling_response(header_chunks: list[bytes], delay: float) -> tuple[int, threading.Thread]:
    """Send ``header_chunks`` ``delay`` seconds apart, then stall until the client goes away."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def serve() -> None:
        with listener:
            connection, _address = listener.accept()
            with connection:
                connection.recv(4096)
                with suppress(OSError):
                    for chunk in header_chunks:
                        time.sleep(delay)
                        connection.sendall(chunk)
                    connection.settimeout(5)
                    connection.recv(1)  # returns once the client closes the connection

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener.getsockname()[1], thread


@pytest.mark.parametrize(
    ("header_chunks", "delay"),
    [
        ([b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nx"], 0.6),
        ([bytes([byte]) for byte in b"HTTP/1.1 200 OK\r\n"], 0.1),
    ],
    ids=["late-headers-then-body-stall", "trickling-headers"],
)
def test_make_request_total_deadline_is_independent_of_read_timing(header_chunks: list[bytes], delay: float) -> None:
    """Each read staying under the read timeout must not stretch the total deadline."""
    port, thread = _serve_stalling_response(header_chunks, delay)
    threads_before = threading.active_count()
    started = time.monotonic()

    with pytest.raises(HTTPClientError, match="total deadline exceeded") as exc_info:
        make_request(f"http://127.0.0.1:{port}/", timeout=1.0, http2=False)

    assert time.monotonic() - started < 1.4
    assert exc_info.value.network_info is not None
    assert exc_info.value.network_info.ip == "127.0.0.1"
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert threading.active_count() == threads_before - 1


def _stream_event(sock: object) -> dict[str, object]:
    return {"return_value": SimpleNamespace(get_extra_info=lambda name: sock if name == "socket" else None)}


class TestDeadlineWatchdog:
    """The watchdog shuts down only the live connection, and only after the deadline."""

    def test_shuts_down_observed_socket_at_deadline(self) -> None:
        local, remote = socket.socketpair()
        with local, remote, _DeadlineWatchdog(time.monotonic() + 0.05) as watchdog:
            watchdog.observe("connection.connect_tcp.complete", _stream_event(local))
            local.settimeout(5)
            assert local.recv(1) == b""  # woken by the shutdown, not by the timeout
            assert watchdog.expired is True

    def test_socket_reported_after_expiry_is_shut_down_at_once(self) -> None:
        local, remote = socket.socketpair()
        with local, remote, _DeadlineWatchdog(time.monotonic()) as watchdog:
            deadline = time.monotonic() + 5
            while not watchdog.expired and time.monotonic() < deadline:
                time.sleep(0.01)
            watchdog.observe("connection.start_tls.complete", _stream_event(local))
            local.settimeout(5)
            assert local.recv(1) == b""

    @pytest.mark.parametrize(
        ("name", "info"),
        [
            ("connection.connect_tcp.started", _stream_event(None)),
            ("connection.connect_tcp.complete", {"return_value": None}),
            ("connection.connect_tcp.complete", _stream_event(object())),
        ],
    )
    def test_ignores_events_without_a_socket(self, name: str, info: dict[str, object]) -> None:
        with _DeadlineWatchdog(time.monotonic() + 60) as watchdog:
            watchdog.observe(name, info)
            assert watchdog._socket is None

    def test_does_nothing_once_disarmed(self) -> None:
        local, remote = socket.socketpair()
        with local, remote:
            watchdog = _DeadlineWatchdog(time.monotonic() + 60)
            with watchdog:
                watchdog.observe("connection.connect_tcp.complete", _stream_event(local))
            watchdog._expire()  # a timer that fired while being cancelled

            assert watchdog.expired is False
            remote.sendall(b"x")
            assert local.recv(1) == b"x"

    def test_expiry_tolerates_missing_and_closed_sockets(self) -> None:
        watchdog = _DeadlineWatchdog(time.monotonic() + 60)
        with watchdog:
            watchdog._expire()
            local, remote = socket.socketpair()
            local.close()
            remote.close()
            watchdog.observe("connection.connect_tcp.complete", _stream_event(local))

        assert watchdog.expired is True


def test_certificate_verification_error_detection_handles_cyclic_chains() -> None:
    """Exception chains that reference themselves terminate."""
    outer = httpx.ConnectError("connect failed")
    inner = OSError("socket closed")
    outer.__cause__ = inner
    inner.__context__ = outer

    assert _is_certificate_verification_error(outer) is False


class TestResolveAddresses:
    """Choosing between resolve() and the optional resolve_all()."""

    def test_subclass_overriding_only_resolve_is_honoured(self, mocker: pytest_mock.MockerFixture) -> None:
        getaddrinfo = mocker.patch("socket.getaddrinfo")

        class Pinned(SystemDNSResolver):
            def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                return "127.0.0.1", "IPv4", 0.0

        assert _resolve_addresses(Pinned(), "example.invalid", 80, 5.0) == [("127.0.0.1", "IPv4")]
        getaddrinfo.assert_not_called()

    def test_subclass_overriding_resolve_all_gets_fallback(self) -> None:
        class Pinned(SystemDNSResolver):
            def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                return "127.0.0.1", "IPv4", 0.0

            def resolve_all(self, _host: str, _port: int, _timeout: float) -> tuple[list[tuple[str, str]], float]:
                return [("::1", "IPv6"), ("127.0.0.1", "IPv4")], 0.0

        assert _resolve_addresses(Pinned(), "example.invalid", 80, 5.0) == [("::1", "IPv6"), ("127.0.0.1", "IPv4")]

    def test_resolver_without_resolve_all_uses_resolve(self) -> None:
        assert _resolve_addresses(FakeDNSResolver(), "example.test", 80, 5.0) == [("203.0.113.10", "IPv4")]

    def test_empty_resolve_all_result_is_an_error(self) -> None:
        class Empty:
            def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                raise AssertionError

            def resolve_all(self, _host: str, _port: int, _timeout: float) -> tuple[list[tuple[str, str]], float]:
                return [], 0.0

        with pytest.raises(DNSResolutionError, match="No usable address records"):
            _resolve_addresses(Empty(), "example.test", 80, 5.0)

    def test_make_request_reports_empty_resolution_as_network_error(self) -> None:
        class Empty:
            def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                raise AssertionError

            def resolve_all(self, _host: str, _port: int, _timeout: float) -> tuple[list[tuple[str, str]], float]:
                return [], 0.0

        with pytest.raises(HTTPClientError, match="No usable address records"):
            make_request("http://example.test/", dns_resolver=Empty())


@pytest.mark.parametrize(
    ("url", "pinned", "expected"),
    [
        ("http://bücher.test:8080/", ("bücher.test", 8080), ("xn--bcher-kva.test:8080", "xn--bcher-kva.test")),
        ("http://Example.TEST/", ("example.test", 80), ("example.test", "example.test")),
        ("http://[2001:db8::1]:8080/", ("2001:db8::1", 8080), ("[2001:db8::1]:8080", "2001:db8::1")),
    ],
    ids=["idn", "ascii", "ipv6"],
)
def test_make_request_sends_wire_form_of_host(
    httpx_mock: pytest_httpx.HTTPXMock,
    url: str,
    pinned: tuple[str, int],
    expected: tuple[str, str],
) -> None:
    """Host and SNI use the IDNA A-label while --resolve keys keep the user's spelling."""
    expected_host, expected_sni = expected

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Host"] == expected_host
        assert request.extensions["sni_hostname"] == expected_sni
        return httpx.Response(200, request=request)

    port_suffix = "" if pinned[1] == 80 else f":{pinned[1]}"
    httpx_mock.add_callback(handler, url=f"http://127.0.0.1{port_suffix}/")

    _timing, _network, response = make_request(
        url,
        dns_resolver=OverrideDNSResolver({pinned: "127.0.0.1"}),
        timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
    )

    assert response.status == 200


class TestErrorsCarryNetworkInfo:
    """Network failures keep the partial network data gathered before the error."""

    def test_connect_error_keeps_ip_and_proxy(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(HTTPClientError) as exc_info:
            make_request(
                "http://example.test/",
                dns_resolver=FakeDNSResolver(),
                proxy="socks5://proxy.test:1080",
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

        network = exc_info.value.network_info
        assert network is not None
        assert network.ip == "203.0.113.10"
        assert network.proxy_url == "socks5://proxy.test:1080"

    def test_timeout_keeps_network_info(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ReadTimeout("read timed out"))

        with pytest.raises(HTTPClientError, match="Request timeout") as exc_info:
            make_request(
                "http://example.test/",
                timeout=5.0,
                dns_resolver=FakeDNSResolver(),
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

        assert exc_info.value.network_info is not None
        assert exc_info.value.network_info.ip == "203.0.113.10"

    def test_dns_failure_keeps_proxy_decision(self) -> None:
        class Failing:
            def resolve(self, host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                message = f"DNS resolution failed for {host}"
                raise DNSResolutionError(message)

        with pytest.raises(HTTPClientError, match="DNS resolution failed") as exc_info:
            make_request("http://example.test/", dns_resolver=Failing(), noproxy=True)

        assert exc_info.value.network_info is not None
        assert exc_info.value.network_info.proxy_source is not None


def _serve_one_proxied_request() -> tuple[int, list[bytes], threading.Thread]:
    """Start a forward proxy that records one request head and answers 204."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    received: list[bytes] = []

    def serve() -> None:
        with listener:
            connection, _address = listener.accept()
            with connection:
                request = b""
                while b"\r\n\r\n" not in request:
                    request += connection.recv(4096)
                received.append(request)
                connection.sendall(b"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener.getsockname()[1], received, thread


class TestIPv6LiteralThroughRemoteDNSProxy:
    """A proxy that resolves names itself still gets an IPv6 literal target in brackets."""

    def test_forward_proxy_request_reaches_proxy(self) -> None:
        proxy_port, received, thread = _serve_one_proxied_request()

        _timing, network, response = make_request(
            "http://[::1]:8081/path", timeout=5.0, http2=False, proxy=f"http://127.0.0.1:{proxy_port}"
        )
        thread.join(timeout=2)

        assert response.status == 204
        assert network.ip is None
        assert network.proxy_url == f"http://127.0.0.1:{proxy_port}"
        assert b"\r\nHost: [::1]:8081\r\n" in received[0]

    @pytest.mark.parametrize(
        "proxy", ["http://proxy.test:3128", "https://proxy.test:3128", "socks5h://proxy.test:1080"]
    )
    def test_request_target_is_bracketed(self, mocker: pytest_mock.MockerFixture, proxy: str) -> None:
        captured: dict[str, Any] = {}

        class DummyClient:
            def __init__(self, *_: object, **__: object) -> None:
                self.headers: dict[str, str] = {}

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(self, _method: str, request_url: str, *, extensions: dict[str, object], **_kw: object) -> object:
                captured["request_url"] = request_url
                captured["sni"] = extensions["sni_hostname"]
                captured["host"] = self.headers["Host"]

                class _Stream:
                    def __enter__(self) -> httpx.Response:
                        return httpx.Response(200, request=httpx.Request("GET", request_url))

                    def __exit__(self, *_exc: object) -> None:
                        return None

                return _Stream()

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        make_request(
            "https://[2001:db8::1]:8443/x",
            proxy=proxy,
            tls_inspector=FakeTLSInspector(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        )

        assert captured == {
            "request_url": "https://[2001:db8::1]:8443/x",
            "sni": "2001:db8::1",
            "host": "[2001:db8::1]:8443",
        }


class _OneAddressFailsResolver:
    """Resolve to an address that cannot be reached, then to the working one."""

    def __init__(self, failing: tuple[str, str]) -> None:
        self._failing = failing

    def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:  # pragma: no cover
        return "127.0.0.1", "IPv4", 0.0

    def resolve_all(self, _host: str, _port: int, _timeout: float) -> tuple[list[tuple[str, str]], float]:
        return [self._failing, ("127.0.0.1", "IPv4")], 0.0


def _serve_http_ok(count: int = 1) -> tuple[int, threading.Thread]:
    """Answer ``count`` plain HTTP requests on 127.0.0.1 with ``200 ok``."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def serve() -> None:
        with listener:
            for _ in range(count):
                connection, _address = listener.accept()
                with connection:
                    request = b""
                    while b"\r\n\r\n" not in request:
                        request += connection.recv(4096)
                    connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener.getsockname()[1], thread


def _serve_socks5(
    *,
    refused_hosts: frozenset[str] = frozenset(),
    accepted_auth: tuple[bytes, bytes] | None = None,
) -> tuple[int, list[str], threading.Thread]:
    """Run a SOCKS5 proxy that refuses CONNECT to ``refused_hosts`` and relays the rest.

    Returns the port, the log of requested targets (and auth failures), and the
    server thread, which ends once the listener is idle for a second.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(1)
    log: list[str] = []

    def handle(client: socket.socket) -> None:
        client.recv(262)
        if accepted_auth is None:
            client.sendall(b"\x05\x00")
        else:
            client.sendall(b"\x05\x02")
            request = client.recv(515)
            username = request[2 : 2 + request[1]]
            password = request[3 + request[1] :]
            if (username, password) != accepted_auth:
                log.append("auth failed")
                client.sendall(b"\x01\x01")
                return
            client.sendall(b"\x01\x00")
        request = client.recv(262)
        if request[3] == 4:
            host = socket.inet_ntop(socket.AF_INET6, request[4:20])
            port = int.from_bytes(request[20:22], "big")
        else:
            host = socket.inet_ntoa(request[4:8])
            port = int.from_bytes(request[8:10], "big")
        log.append(host)
        reply_tail = b"\x00\x01" + socket.inet_aton("127.0.0.1") + port.to_bytes(2, "big")
        if host in refused_hosts:
            client.sendall(b"\x05\x05" + reply_tail)  # connection refused
            return
        with socket.create_connection((host, port)) as upstream:
            client.sendall(b"\x05\x00" + reply_tail)
            to_upstream = threading.Thread(target=_relay, args=(client, upstream), daemon=True)
            to_upstream.start()
            _relay(upstream, client)
            to_upstream.join(timeout=2)

    def serve() -> None:
        with listener:
            while True:
                try:
                    client, _address = listener.accept()
                except TimeoutError:
                    return
                with client:
                    handle(client)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener.getsockname()[1], log, thread


def _relay(source: socket.socket, target: socket.socket) -> None:
    with suppress(OSError):
        while data := source.recv(65536):
            target.sendall(data)
    with suppress(OSError):
        target.shutdown(socket.SHUT_WR)


class TestAddressFallbackAccounting:
    """Time spent on addresses that failed is part of the request, and counted as connect time."""

    def test_failed_attempts_count_towards_connect_and_total(self, mocker: pytest_mock.MockerFixture) -> None:
        port, thread = _serve_http_ok()
        connect_tcp = SyncBackend.connect_tcp
        failed_attempt_seconds = 0.3

        def connect_or_fail_slowly(self: SyncBackend, host: str, *args: Any, **kwargs: Any) -> object:  # noqa: ANN401
            if host == "192.0.2.1":
                time.sleep(failed_attempt_seconds)
                message = "timed out"
                raise httpcore.ConnectTimeout(message)
            return connect_tcp(self, host, *args, **kwargs)

        mocker.patch.object(SyncBackend, "connect_tcp", connect_or_fail_slowly)
        started = time.perf_counter()

        timing, network, response = make_request(
            f"http://example.test:{port}/",
            timeout=5.0,
            http2=False,
            dns_resolver=_OneAddressFailsResolver(("192.0.2.1", "IPv4")),
        )
        wall_ms = (time.perf_counter() - started) * 1000
        thread.join(timeout=2)

        assert response.status == 200
        assert network.ip == "127.0.0.1"
        failed_ms = failed_attempt_seconds * 1000
        assert failed_ms <= timing.total_ms <= wall_ms
        assert timing.ttfb_ms >= failed_ms
        assert timing.connect_ms >= failed_ms
        assert timing.is_estimated is False
        assert timing.wait_ms < failed_ms
        phases = timing.dns_ms + timing.connect_ms + timing.tls_ms + timing.wait_ms
        assert phases == pytest.approx(timing.ttfb_ms)


class TestSocksLocalDNSFallback:
    """With a local-DNS SOCKS proxy, a target the proxy cannot reach falls back to the next address."""

    def test_refused_target_falls_back_to_next_address(self) -> None:
        origin_port, origin = _serve_http_ok()
        proxy_port, log, proxy = _serve_socks5(refused_hosts=frozenset({"::1"}))

        _timing, network, response = make_request(
            f"http://localhost:{origin_port}/",
            timeout=5.0,
            http2=False,
            proxy=f"socks5://127.0.0.1:{proxy_port}",
            dns_resolver=_OneAddressFailsResolver(("::1", "IPv6")),
        )
        origin.join(timeout=2)
        proxy.join(timeout=3)

        assert response.status == 200
        assert network.ip == "127.0.0.1"
        assert log == ["::1", "127.0.0.1"]

    def test_refused_last_address_is_reported(self) -> None:
        proxy_port, log, proxy = _serve_socks5(refused_hosts=frozenset({"::1", "127.0.0.1"}))

        with pytest.raises(HTTPClientError, match="Proxy Server could not connect"):
            make_request(
                "http://localhost:9/",
                timeout=5.0,
                proxy=f"socks5://127.0.0.1:{proxy_port}",
                dns_resolver=_OneAddressFailsResolver(("::1", "IPv6")),
            )
        proxy.join(timeout=3)

        assert log == ["::1", "127.0.0.1"]

    def test_authentication_failure_is_not_retried(self) -> None:
        proxy_port, log, proxy = _serve_socks5(accepted_auth=(b"user", b"right"))

        with pytest.raises(HTTPClientError, match="Invalid username/password"):
            make_request(
                "http://localhost:9/",
                timeout=5.0,
                proxy=f"socks5://user:wrong@127.0.0.1:{proxy_port}",
                dns_resolver=_OneAddressFailsResolver(("::1", "IPv6")),
            )
        proxy.join(timeout=3)

        assert log == ["auth failed"]

    @pytest.mark.parametrize("error", [httpcore.ConnectError, httpcore.ConnectTimeout])
    def test_unreachable_proxy_is_not_retried(
        self,
        mocker: pytest_mock.MockerFixture,
        error: type[Exception],
    ) -> None:
        def unreachable(*_args: object, **_kwargs: object) -> NoReturn:
            message = "proxy unreachable"
            raise error(message)

        connect_tcp = mocker.patch.object(SyncBackend, "connect_tcp", side_effect=unreachable)

        with pytest.raises(HTTPClientError, match="proxy unreachable"):
            make_request(
                "http://localhost:9/",
                timeout=5.0,
                proxy="socks5://127.0.0.1:1080",
                dns_resolver=_OneAddressFailsResolver(("::1", "IPv6")),
            )

        assert connect_tcp.call_count == 1


class TestProxyURLValidation:
    """Proxy URLs that cannot be used fail as network errors without leaking credentials."""

    def test_scheme_less_env_proxy_is_used_as_http_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        proxy_port, received, thread = _serve_one_proxied_request()
        monkeypatch.setenv("HTTP_PROXY", f"user:s3cret@127.0.0.1:{proxy_port}")

        _timing, network, response = make_request("http://origin.test:8080/path", timeout=5.0, http2=False)
        thread.join(timeout=2)

        assert response.status == 204
        assert network.proxy_url == f"http://user:****@127.0.0.1:{proxy_port}"
        assert received[0].startswith(b"GET http://origin.test:8080/path HTTP/1.1\r\n")
        assert b"Proxy-Authorization: Basic dXNlcjpzM2NyZXQ=" in received[0]

    @pytest.mark.parametrize(
        ("proxy_url", "reason"),
        [
            ("ftp://user:s3cret@127.0.0.1:3128", "unsupported scheme"),
            ("socks4://user:s3cret@127.0.0.1:1080", "unsupported scheme"),
            ("http://user:s3cret@[::1", "malformed"),
            ("http://user:s3cret@127.0.0.1:abc", "malformed"),
            ("http://user:s3cret@127.0.0.1:99999", "port"),
            ("http://user:s3cret@127.0.0.1:0", "port"),
            ("http://user:s3cret@", "missing host"),
        ],
    )
    def test_invalid_env_proxy_is_a_redacted_client_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        proxy_url: str,
        reason: str,
    ) -> None:
        monkeypatch.setenv("HTTP_PROXY", proxy_url)

        with pytest.raises(HTTPClientError, match=reason) as exc_info:
            make_request("http://example.test/", dns_resolver=FakeDNSResolver())

        assert "s3cret" not in str(exc_info.value)
        assert "HTTP_PROXY" in str(exc_info.value)
        network = exc_info.value.network_info
        assert network is not None
        assert network.proxy_url is not None
        assert "s3cret" not in network.proxy_url
        assert network.proxy_source == "HTTP_PROXY"

    def test_explicit_proxy_is_validated_too(self) -> None:
        with pytest.raises(HTTPClientError, match="unsupported scheme") as exc_info:
            make_request("http://example.test/", proxy="user:s3cret@gateway:3128", dns_resolver=FakeDNSResolver())

        assert "s3cret" not in str(exc_info.value)

    def test_client_construction_failure_is_a_client_error(self, mocker: pytest_mock.MockerFixture) -> None:
        mocker.patch(
            "httptap.http_client.httpx.Client",
            side_effect=ImportError("Using SOCKS proxy, but the 'socksio' package is not installed."),
        )

        with pytest.raises(HTTPClientError, match="socksio") as exc_info:
            make_request(
                "http://example.test/",
                proxy="socks5://user:s3cret@gateway:1080",
                dns_resolver=FakeDNSResolver(),
            )

        assert exc_info.value.network_info is not None
        assert exc_info.value.network_info.proxy_url == "socks5://user:****@gateway:1080"


@pytest.mark.parametrize("url", ["http://example.test:99999/", "http://example.test:abc/"])
def test_make_request_reports_invalid_url_as_client_error(url: str) -> None:
    """A malformed redirect target fails like any other request error, not as an internal error."""
    with pytest.raises(HTTPClientError, match="Invalid URL"):
        make_request(url, dns_resolver=FakeDNSResolver())


class TestBuildUserAgent:
    """Test suite for _build_user_agent function."""

    def test_build_user_agent_includes_version(self) -> None:
        """Test that user agent includes package version."""
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
            "httptap.http_client.get_package_info",
            return_value=PackageInfo(
                version="0.0.0",
                author=faker.name(),
                homepage=faker.url(),
                license=faker.pystr(min_chars=5, max_chars=12),
            ),
        )

        assert "httptap/0.0.0" in _build_user_agent()


class TestBuildTimingMetrics:
    """Test suite for _build_timing_metrics function."""

    def test_build_timing_with_precise_connect_and_tls(self) -> None:
        """Test building timing with precise connect and TLS values."""
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
        body = b"Hello, World!" * 100
        response = httpx.Response(200, content=body)

        total_bytes = _consume_response_body(response)

        assert total_bytes == len(body)

    def test_consume_response_body_counts_encoded_bytes(self) -> None:
        """Compressed responses report the bytes received on the wire."""
        encoded_body = gzip.compress(b"x" * 100_000)
        response = httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=httpx.ByteStream(encoded_body),
        )

        assert _consume_response_body(response) == len(encoded_body)

    def test_consume_response_body_ignores_invalid_content_encoding(self) -> None:
        """Invalid content encoding does not prevent collecting wire bytes."""
        encoded_body = b"not a gzip stream"
        response = httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=httpx.ByteStream(encoded_body),
        )

        assert _consume_response_body(response) == len(encoded_body)

    def test_consume_response_body_rejects_expired_deadline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A body chunk received after the deadline fails the request."""
        response = httpx.Response(200, stream=httpx.ByteStream(b"body"))
        monkeypatch.setattr("httptap.http_client.time.monotonic", lambda: 2.0)

        with pytest.raises(httpx.ReadTimeout, match="total deadline exceeded"):
            _consume_response_body(response, deadline=1.0)


CERT_DICT: dict[str, Any] = {
    "subject": ((("commonName", "example.test"),),),
    "issuer": ((("commonName", "Example Root CA"),),),
    "subjectAltName": (("DNS", "example.test"), ("DNS", "www.example.test")),
    "notBefore": "Jan  1 00:00:00 2025 GMT",
    "notAfter": "Jan  1 00:00:00 2035 GMT",
    "serialNumber": "0ABCDEF0",
}


class FakeSSLObject:
    """Duck-typed stand-in for the live SSL object exposed by httpcore.

    Mirrors the surface shared by ``ssl.SSLSocket``, ``ssl.SSLObject`` and the
    low-level ``_ssl._SSLSocket``: ``version()``, ``cipher()`` and
    ``getpeercert()``.
    """

    def __init__(
        self,
        *,
        version: str | None = "TLSv1.3",
        cipher: tuple[str, str, int] | None = ("TLS_AES_128_GCM_SHA256", "TLSv1.3", 128),
        cert: dict[str, Any] | None = None,
        cert_der: bytes | None = None,
        cipher_error: bool = False,
    ) -> None:
        self._version = version
        self._cipher = cipher
        self._cert = CERT_DICT if cert is None else cert
        self._cert_der = cert_der
        self._cipher_error = cipher_error

    def version(self) -> str | None:
        return self._version

    def cipher(self) -> tuple[str, str, int] | None:
        if self._cipher_error:
            msg = "cipher unavailable"
            raise AttributeError(msg)
        return self._cipher

    def getpeercert(self, binary_form: bool = False, /) -> dict[str, Any] | bytes | None:  # noqa: FBT001, FBT002
        return self._cert_der if binary_form else self._cert


class FakeStream:
    """Network stream stub returning a fake SSL object under a chosen key."""

    def __init__(self, obj: object, *, key: str = "ssl_object") -> None:
        self._obj = obj
        self._key = key

    def get_extra_info(self, name: str) -> object | None:
        return self._obj if name == self._key else None


class TestPopulateTLSFromStream:
    """Test suite for _populate_tls_from_stream function."""

    def test_populate_tls_from_stream_enriches_network_info(self) -> None:
        """Stream with SSL object enriches version, cipher, and full cert data."""
        response = httpx.Response(200)
        network_info = NetworkInfo()
        response.extensions["network_stream"] = FakeStream(FakeSSLObject())

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher == "TLS_AES_128_GCM_SHA256"
        assert network_info.cert_cn == "example.test"
        assert network_info.cert_issuer == "Example Root CA"
        assert network_info.cert_sans == ["example.test", "www.example.test"]
        assert network_info.cert_serial == "0ABCDEF0"
        assert network_info.cert_not_before is not None
        assert network_info.cert_not_after is not None
        assert isinstance(network_info.cert_days_left, int)

    def test_populate_tls_from_stream_preserves_existing_fields(self) -> None:
        """Existing TLS metadata is not overwritten by stream data."""
        response = httpx.Response(200)
        network_info = NetworkInfo(
            tls_version="TLSv1.2",
            tls_cipher="TLS_CHACHA20_POLY1305_SHA256",
            cert_cn="cached.example",
            cert_days_left=30,
            cert_issuer="Cached CA",
        )
        response.extensions["network_stream"] = FakeStream(FakeSSLObject())

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.2"
        assert network_info.tls_cipher == "TLS_CHACHA20_POLY1305_SHA256"
        assert network_info.cert_cn == "cached.example"
        assert network_info.cert_days_left == 30
        assert network_info.cert_issuer == "Cached CA"

    def test_populate_tls_from_stream_handles_missing_ssl_object(self) -> None:
        """Gracefully handle streams without SSL metadata."""
        response = httpx.Response(200)
        network_info = NetworkInfo()
        response.extensions["network_stream"] = FakeStream(None)

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version is None
        assert network_info.tls_cipher is None
        assert network_info.cert_cn is None

    def test_populate_tls_from_stream_falls_back_to_socket_key(self) -> None:
        """When ssl_object is absent, the socket extra is used instead."""
        response = httpx.Response(200)
        network_info = NetworkInfo()
        response.extensions["network_stream"] = FakeStream(FakeSSLObject(), key="socket")

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.cert_cn == "example.test"

    def test_populate_tls_from_stream_ignores_non_tls_socket(self) -> None:
        """A plain (non-TLS) socket without getpeercert is ignored."""
        response = httpx.Response(200)
        network_info = NetworkInfo()

        class PlainSocket:
            def getsockname(self) -> tuple[str, int]:
                return ("127.0.0.1", 12345)

        response.extensions["network_stream"] = FakeStream(PlainSocket(), key="socket")

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version is None
        assert network_info.cert_cn is None

    def test_populate_tls_from_stream_without_certificate(self) -> None:
        """No parsed peer cert (e.g. verification disabled) still yields version/cipher."""
        response = httpx.Response(200)
        network_info = NetworkInfo()
        response.extensions["network_stream"] = FakeStream(FakeSSLObject(cert={}))

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher == "TLS_AES_128_GCM_SHA256"
        assert network_info.cert_cn is None
        assert network_info.cert_sans == []

    def test_populate_tls_from_stream_when_cipher_missing(self) -> None:
        """Cipherless streams leave tls_cipher unset while keeping other data."""
        response = httpx.Response(200)
        network_info = NetworkInfo()
        response.extensions["network_stream"] = FakeStream(FakeSSLObject(cipher_error=True))

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher is None
        assert network_info.cert_cn == "example.test"

    def test_populate_tls_from_stream_when_cipher_empty(self) -> None:
        """A None cipher tuple leaves tls_cipher unset while keeping other data."""
        response = httpx.Response(200)
        network_info = NetworkInfo()
        response.extensions["network_stream"] = FakeStream(FakeSSLObject(cipher=None))

        _populate_tls_from_stream(response, network_info)

        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher is None
        assert network_info.cert_cn == "example.test"


def test_extract_ssl_object_handles_non_callable_getter() -> None:
    """Non-callable network stream extras should be ignored safely."""
    response = httpx.Response(200)

    class NonCallableStream:
        get_extra_info = None

    response.extensions["network_stream"] = NonCallableStream()

    assert _extract_ssl_object(response) is None


def test_extract_ssl_object_returns_first_tls_capable_candidate() -> None:
    """The socket key is consulted when ssl_object yields nothing usable."""
    response = httpx.Response(200)
    ssl_obj = FakeSSLObject()
    response.extensions["network_stream"] = FakeStream(ssl_obj, key="socket")

    assert _extract_ssl_object(response) is ssl_obj


class RecordingTLSInspector:
    """TLS inspector that records how many times its probe was invoked."""

    def __init__(self) -> None:
        self.calls = 0

    def inspect(self, host: str, _port: int, _timeout: float) -> NetworkInfo:
        self.calls += 1
        info = NetworkInfo()
        info.tls_version = "TLSv1.2"
        info.tls_cipher = "ECDHE-RSA-AES128-GCM-SHA256"
        info.cert_cn = host
        info.cert_days_left = 77
        return info


class TestLiveTLSExtractionSupersedesProbe:
    """The live connection is the primary TLS source; the probe is fallback-only."""

    @staticmethod
    def _patch_client(mocker: pytest_mock.MockerFixture, network_stream: object) -> None:
        class DummyStream:
            def __enter__(self) -> httpx.Response:
                request = httpx.Request("GET", "https://secure.test/")
                return httpx.Response(
                    200,
                    request=request,
                    content=b"ok",
                    extensions={"network_stream": network_stream},
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

            def stream(self, *_: object, **__: object) -> DummyStream:
                return DummyStream()

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

    def test_probe_skipped_when_live_tls_available(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """No extra handshake when the live connection exposes TLS metadata."""
        self._patch_client(mocker, FakeStream(FakeSSLObject()))
        inspector = RecordingTLSInspector()

        _timing, network, _response = make_request(
            "https://secure.test/",
            timeout=5.0,
            dns_resolver=FakeDNSResolver(),
            tls_inspector=inspector,
            timing_collector=FakeTimingCollector(TimingMetrics(dns_ms=1.0, ttfb_ms=5.0, total_ms=6.0)),
        )

        assert inspector.calls == 0
        assert network.tls_version == "TLSv1.3"
        assert network.cert_cn == "example.test"
        assert network.cert_issuer == "Example Root CA"
        assert network.cert_sans == ["example.test", "www.example.test"]

    def test_probe_used_when_live_tls_absent(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """The dedicated probe fills TLS metadata when the live object is unavailable."""
        self._patch_client(mocker, FakeStream(None))
        inspector = RecordingTLSInspector()

        _timing, network, _response = make_request(
            "https://secure.test/",
            timeout=5.0,
            dns_resolver=FakeDNSResolver(),
            tls_inspector=inspector,
            timing_collector=FakeTimingCollector(TimingMetrics(dns_ms=1.0, ttfb_ms=5.0, total_ms=6.0)),
        )

        assert inspector.calls == 1
        assert network.tls_version == "TLSv1.2"
        assert network.cert_cn == "secure.test"


class TestTraceCollector:
    """Test suite for TraceCollector class."""

    def test_trace_collector_captures_connect_timing(self) -> None:
        """Test that TraceCollector captures TCP connect timing."""
        trace = TraceCollector()

        # Simulate httpcore trace events
        trace("connection.connect_tcp.started", {})
        trace("connection.connect_tcp.complete", {})

        connect_ms = trace.connect_ms
        assert connect_ms is not None
        assert connect_ms >= 0.0

    def test_trace_collector_captures_tls_timing(self) -> None:
        """Test that TraceCollector captures TLS handshake timing."""
        trace = TraceCollector()

        trace("connection.start_tls.started", {})
        trace("connection.start_tls.complete", {})

        tls_ms = trace.tls_ms
        assert tls_ms is not None
        assert tls_ms >= 0.0

    def test_trace_collector_prefers_tunneled_tls_timing(self) -> None:
        """The TLS handshake after CONNECT is the origin TLS measurement."""
        trace = TraceCollector()
        trace._events[trace.TLS_EVENT] = {"started": 1.0, "complete": 1.5}
        trace._events[trace.PROXY_TLS_EVENT] = {"started": 2.0, "complete": 2.025}

        assert trace.tls_ms == pytest.approx(25.0)

    def test_trace_collector_counts_connect_tunnel_as_connect_time(self, mocker: pytest_mock.MockerFixture) -> None:
        """Through a CONNECT proxy, connect spans TCP to the proxy plus the tunnel round-trip."""
        events = [
            ("connection.connect_tcp.started", 1.000),
            ("connection.connect_tcp.complete", 1.002),
            ("http11.send_request_headers.started", 1.002),  # CONNECT request
            ("http11.receive_response_headers.complete", 1.122),  # proxy: 200 Connection established
            ("proxy.start_tls.started", 1.122),
            ("proxy.start_tls.complete", 1.500),
            ("http11.send_request_headers.started", 1.500),  # request through the tunnel
            ("http11.receive_response_headers.complete", 1.640),
        ]
        mocker.patch("httptap.http_client.time.perf_counter", side_effect=[timestamp for _, timestamp in events])
        trace = TraceCollector()
        for name, _timestamp in events:
            trace(name, {})

        assert trace.connect_ms == pytest.approx(122.0)
        assert trace.tls_ms == pytest.approx(378.0)
        # The tunnel request must not overwrite the first occurrence of shared event names.
        assert trace._events["http11.send_request_headers"]["started"] == pytest.approx(1.002)

    @pytest.mark.parametrize(
        ("events", "connect_ms", "tls_ms"),
        [
            (
                [
                    ("socks.connect_tcp.started", 1.000),
                    ("socks.connect_tcp.complete", 1.002),
                    ("socks.setup_socks5_connection.started", 1.002),
                    ("socks.setup_socks5_connection.complete", 1.090),
                    ("socks.start_tls.started", 1.090),
                    ("socks.start_tls.complete", 1.300),
                ],
                90.0,
                210.0,
            ),
            (
                [
                    ("socks.connect_tcp.started", 1.000),
                    ("socks.connect_tcp.complete", 1.002),
                    ("socks.setup_socks5_connection.started", 1.002),
                    ("socks.setup_socks5_connection.complete", 1.040),
                ],
                40.0,
                None,
            ),
        ],
        ids=["https", "http"],
    )
    def test_trace_collector_measures_socks_path(
        self,
        mocker: pytest_mock.MockerFixture,
        events: list[tuple[str, float]],
        connect_ms: float,
        tls_ms: float | None,
    ) -> None:
        """Through SOCKS, connect covers TCP to the proxy plus the SOCKS5 handshake."""
        mocker.patch("httptap.http_client.time.perf_counter", side_effect=[timestamp for _, timestamp in events])
        trace = TraceCollector()
        for name, _timestamp in events:
            trace(name, {})

        assert trace.connect_ms == pytest.approx(connect_ms)
        assert trace.tls_ms == (pytest.approx(tls_ms) if tls_ms is not None else None)

    def test_trace_collector_ignores_tunnel_without_tcp_connect(self) -> None:
        """Without a recorded TCP connect, the tunnel span cannot be measured."""
        trace = TraceCollector()
        trace._events[trace.PROXY_TLS_EVENT] = {"started": 2.0, "complete": 2.025}

        assert trace.connect_ms is None

    def test_trace_collector_returns_none_for_missing_events(self) -> None:
        """Test that TraceCollector returns None for incomplete events."""
        trace = TraceCollector()

        # No events captured
        assert trace.connect_ms is None
        assert trace.tls_ms is None

    def test_trace_collector_returns_none_for_incomplete_events(self) -> None:
        """Test that TraceCollector handles incomplete event pairs."""
        trace = TraceCollector()

        # Only started, no complete
        trace("connection.connect_tcp.started", {})

        assert trace.connect_ms is None

    def test_trace_collector_ignores_invalid_events(self) -> None:
        """Test that TraceCollector ignores events without proper structure."""
        trace = TraceCollector()

        # Event without prefix (no dot)
        trace("invalid_event", {})

        # Should not crash, just ignore
        assert trace.connect_ms is None

    def test_trace_collector_handles_inverted_timestamps(self) -> None:
        """Test that TraceCollector handles end before start."""
        import time

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
                content: bytes | None = None,
                *,
                extensions: dict[str, object] | None = None,
            ) -> DummyStream:
                assert content is None
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
        url = "https://[2001:db8::1]:8443/"
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
                content: bytes | None = None,
                extensions: dict[str, object] | None = None,
            ) -> DummyStream:
                assert method == "GET"
                assert content is None
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
        )

        assert response.status == 200
        assert captured["request_url"] == "https://[2001:db8::1]:8443/"
        extensions = captured["extensions"]
        headers = captured["headers"]
        assert isinstance(extensions, dict)
        assert isinstance(headers, dict)
        assert extensions.get("sni_hostname") == "2001:db8::1"
        assert headers.get("Host") == "[2001:db8::1]:8443"

    def test_make_request_handles_missing_hostname(self) -> None:
        """Test error handling for URL without hostname."""
        with pytest.raises(HTTPClientError, match="Invalid URL: missing hostname"):
            make_request(
                "http://",
                timeout=5.0,
            )

    def test_make_request_handles_dns_error(self) -> None:
        """Test error handling for DNS resolution failure."""

        class FailingDNSResolver:
            def resolve(self, _h: str, _p: int, _t: float) -> tuple[str, str, float]:
                msg = "DNS lookup failed"
                raise DNSResolutionError(msg)

        with pytest.raises(HTTPClientError, match="DNS lookup failed"):
            make_request(
                "https://invalid.test",
                timeout=5.0,
                dns_resolver=FailingDNSResolver(),
            )

    def test_make_request_handles_timeout(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test error handling for request timeout."""
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
            )

    def test_make_request_handles_connection_error(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test error handling for connection errors."""
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
            )

    def test_make_request_preserves_certificate_on_verification_failure(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Certificate diagnostics survive a failed verified HTTPS request."""
        url = "https://expired.example.test"
        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("expired.example.test", 443, 5.0)
        httpx_mock.add_exception(
            httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired"),
            method="GET",
            url=f"https://{ip}",
        )
        certificate_info = NetworkInfo(
            tls_version="TLSv1.2",
            cert_cn="expired.example.test",
            cert_issuer="Example CA",
            cert_days_left=-1,
        )
        inspect = mocker.patch("httptap.http_client.SocketTLSInspector.inspect", return_value=certificate_info)

        with pytest.raises(HTTPClientError, match="CERTIFICATE_VERIFY_FAILED") as exc_info:
            make_request(
                url,
                timeout=5.0,
                dns_resolver=dns_resolver,
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

        inspect.assert_called_once()
        (probe_host, probe_port, probe_timeout), probe_kwargs = inspect.call_args
        assert (probe_host, probe_port, probe_kwargs) == ("expired.example.test", 443, {"connect_host": ip})
        assert 0 < probe_timeout <= 5.0
        assert exc_info.value.network_info is not None
        assert exc_info.value.network_info.cert_cn == "expired.example.test"
        assert exc_info.value.network_info.cert_days_left == -1

    def test_make_request_skips_certificate_probe_when_budget_is_spent(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """The verification error is still reported when no time is left for diagnostics."""
        clock = iter([0.0, 0.0, 0.0, 0.0, 0.0])
        mocker.patch("httptap.http_client.time.monotonic", side_effect=lambda: next(clock, 10.0))
        httpx_mock.add_exception(
            httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired"),
            method="GET",
            url="https://203.0.113.10",
        )
        inspect = mocker.patch("httptap.http_client.SocketTLSInspector.inspect")

        with pytest.raises(HTTPClientError, match="CERTIFICATE_VERIFY_FAILED"):
            make_request(
                "https://expired.example.test",
                timeout=5.0,
                dns_resolver=FakeDNSResolver(),
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

        inspect.assert_not_called()

    def test_make_request_does_not_probe_directly_when_proxy_is_configured(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Certificate diagnostics must not bypass a configured proxy."""

        class FailingClient:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                self.headers: dict[str, str] = {}

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def stream(self, *_args: object, **_kwargs: object) -> object:
                msg = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired"
                raise httpx.ConnectError(msg)

        mocker.patch("httptap.http_client.httpx.Client", side_effect=FailingClient)
        inspect = mocker.patch("httptap.http_client.SocketTLSInspector.inspect")

        with pytest.raises(HTTPClientError, match="CERTIFICATE_VERIFY_FAILED"):
            make_request(
                "https://expired.example.test",
                timeout=5.0,
                proxy="http://proxy.example.test:8080",
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

        inspect.assert_not_called()

    def test_make_request_falls_back_to_next_resolved_address(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """A connection failure on one address retries the next DNS result."""
        mocker.patch.object(
            SystemDNSResolver,
            "resolve_all",
            return_value=([("::1", "IPv6"), ("127.0.0.1", "IPv4")], 1.0),
        )
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"), method="GET", url="http://[::1]/")
        httpx_mock.add_response(method="GET", url="http://127.0.0.1/", status_code=200)

        _timing, network, response = make_request(
            "http://localhost/",
            timeout=5.0,
            dns_resolver=SystemDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert response.status == 200
        assert network.ip == "127.0.0.1"
        assert network.ip_family == "IPv4"

    def test_make_request_falls_back_after_connect_timeout(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """A connection timeout on one address retries the next DNS result."""
        mocker.patch.object(
            SystemDNSResolver,
            "resolve_all",
            return_value=([("::1", "IPv6"), ("127.0.0.1", "IPv4")], 1.0),
        )
        httpx_mock.add_exception(httpx.ConnectTimeout("Connection timed out"), method="GET", url="http://[::1]/")
        httpx_mock.add_response(method="GET", url="http://127.0.0.1/", status_code=200)

        _timing, network, response = make_request(
            "http://localhost/",
            timeout=5.0,
            dns_resolver=SystemDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert response.status == 200
        assert network.ip == "127.0.0.1"
        assert network.ip_family == "IPv4"

    def test_make_request_raises_when_every_address_times_out(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """The last connection timeout is reported once no address is left."""
        mocker.patch.object(
            SystemDNSResolver,
            "resolve_all",
            return_value=([("::1", "IPv6"), ("127.0.0.1", "IPv4")], 1.0),
        )
        httpx_mock.add_exception(httpx.ConnectTimeout("Connection timed out"), method="GET", url="http://[::1]/")
        httpx_mock.add_exception(httpx.ConnectTimeout("Connection timed out"), method="GET", url="http://127.0.0.1/")

        with pytest.raises(HTTPClientError, match="Request timeout"):
            make_request(
                "http://localhost/",
                timeout=5.0,
                dns_resolver=SystemDNSResolver(),
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

    def test_make_request_keeps_response_when_tls_probe_runs_out_of_budget(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An optional probe that hits the deadline does not fail a completed response."""
        clock = [0.0]

        class ExpiringTLSInspector:
            def inspect(self, _h: str, _p: int, _t: float) -> NetworkInfo:
                clock[0] = 2.0
                message = "TLS probe timed out"
                raise TLSInspectionError(message)

        monkeypatch.setattr("httptap.http_client.time.monotonic", lambda: clock[0])
        httpx_mock.add_response(method="GET", url="https://203.0.113.10", status_code=200)

        _timing, network, response = make_request(
            "https://example.test",
            timeout=1.0,
            dns_resolver=FakeDNSResolver(),
            tls_inspector=ExpiringTLSInspector(),
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert response.status == 200
        assert network.tls_version is None

    def test_make_request_skips_tls_probe_without_budget(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        readings = iter([0.0, 0.0, 0.0, 0.0, 0.0])
        mocker.patch("httptap.http_client.time.monotonic", side_effect=lambda: next(readings, 10.0))
        inspector = mocker.Mock()
        httpx_mock.add_response(method="GET", url="https://203.0.113.10", status_code=200)

        _timing, _network, response = make_request(
            "https://example.test",
            timeout=5.0,
            dns_resolver=FakeDNSResolver(),
            tls_inspector=inspector,
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert response.status == 200
        inspector.inspect.assert_not_called()

    def test_builtin_tls_probe_dials_the_address_the_request_used(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        inspect = mocker.patch.object(SocketTLSInspector, "inspect", return_value=NetworkInfo(tls_version="TLSv1.3"))
        httpx_mock.add_response(method="GET", url="https://203.0.113.10", status_code=200)

        _timing, network, _response = make_request(
            "https://example.test",
            timeout=5.0,
            dns_resolver=FakeDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert network.tls_version == "TLSv1.3"
        (probe_host, probe_port, _probe_timeout), probe_kwargs = inspect.call_args
        assert (probe_host, probe_port, probe_kwargs) == ("example.test", 443, {"connect_host": "203.0.113.10"})

    def test_make_request_stops_falling_back_when_deadline_is_spent(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """No further address is tried once the overall timeout is used up."""
        mocker.patch.object(
            SystemDNSResolver,
            "resolve_all",
            return_value=([("::1", "IPv6"), ("127.0.0.1", "IPv4")], 1.0),
        )
        # deadline = 0 + 5; DNS and the first attempt run at 0, the second attempt would start at 10.
        readings = iter([0.0, 0.0, 0.0, 0.0, 0.0])
        mocker.patch("httptap.http_client.time.monotonic", side_effect=lambda: next(readings, 10.0))
        httpx_mock.add_exception(httpx.ConnectTimeout("Connection timed out"), method="GET", url="http://[::1]/")

        with pytest.raises(HTTPClientError, match="total deadline exceeded"):
            make_request(
                "http://localhost/",
                timeout=5.0,
                dns_resolver=SystemDNSResolver(),
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

    def test_make_request_uses_resolve_all_from_custom_resolver(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Any resolver exposing resolve_all gets the fallback, not only SystemDNSResolver."""

        class MultiAddressResolver:
            def resolve(self, _host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                raise AssertionError

            def resolve_all(self, _host: str, _port: int, _timeout: float) -> tuple[list[tuple[str, str]], float]:
                return [("::1", "IPv6"), ("127.0.0.1", "IPv4")], 0.0

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"), method="GET", url="http://[::1]/")
        httpx_mock.add_response(method="GET", url="http://127.0.0.1/", status_code=200)

        _timing, network, response = make_request(
            "http://localhost/",
            timeout=5.0,
            dns_resolver=MultiAddressResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert response.status == 200
        assert network.ip == "127.0.0.1"

    def test_make_request_does_not_fallback_after_tls_error(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """A TLS verification error must not be hidden by a second address."""
        mocker.patch.object(
            SystemDNSResolver,
            "resolve_all",
            return_value=([("2001:db8::1", "IPv6"), ("203.0.113.10", "IPv4")], 1.0),
        )
        tls_error = httpx.ConnectError("certificate verify failed")
        tls_error.__cause__ = ssl.SSLCertVerificationError("certificate verify failed")
        httpx_mock.add_exception(tls_error, method="GET", url="https://[2001:db8::1]/")

        with pytest.raises(HTTPClientError, match="certificate verify failed"):
            make_request(
                "https://example.test/",
                timeout=5.0,
                dns_resolver=SystemDNSResolver(),
                timing_collector=FakeTimingCollector(TimingMetrics()),
            )

        assert len(httpx_mock.get_requests()) == 1

    def test_make_request_reserves_timeout_for_fallback(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Each address receives a share of the remaining connect timeout."""
        mocker.patch.object(
            SystemDNSResolver,
            "resolve_all",
            return_value=([("::1", "IPv6"), ("127.0.0.1", "IPv4")], 1.0),
        )
        # deadline, pre-DNS check, DNS budget and the first attempt read 100; the second attempt reads 105.
        clock_values = iter([100.0, 100.0, 100.0, 100.0, 100.0, 105.0])
        mocker.patch("httptap.http_client.time.monotonic", side_effect=lambda: next(clock_values, 105.0))
        connect_timeouts: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            timeout = request.extensions["timeout"]
            assert isinstance(timeout, dict)
            connect_timeouts.append(timeout["connect"])
            if len(connect_timeouts) == 1:
                msg = "Connection timed out"
                raise httpx.ConnectTimeout(msg)
            return httpx.Response(200, request=request)

        httpx_mock.add_callback(handler)
        httpx_mock.add_callback(handler)

        _timing, _network, response = make_request(
            "http://localhost/",
            timeout=10.0,
            dns_resolver=SystemDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics()),
        )

        assert response.status == 200
        assert connect_timeouts == [5.0, 5.0]

    def test_make_request_handles_tls_inspection_error(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test that TLS inspection errors don't fail the request."""

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
        )

        assert response.status == 200
        # Should have used default implementations successfully
        mock_resolve.assert_called_once()

    def test_make_request_force_new_connection_is_deprecated(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test that force_new_connection is deprecated, ignored, and drops limits."""
        url = "https://example.test"
        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("example.test", 443, 5.0)
        httpx_mock.add_response(method="GET", url=f"https://{ip}", status_code=200)

        limits_spy = mocker.spy(httpx, "Limits")

        with pytest.warns(DeprecationWarning, match="force_new_connection is deprecated"):
            make_request(
                url,
                timeout=5.0,
                dns_resolver=dns_resolver,
                timing_collector=FakeTimingCollector(TimingMetrics(total_ms=100.0)),
                force_new_connection=True,
            )

        limits_spy.assert_not_called()

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
        proxy = httpx.Proxy("socks5://gateway:1080", headers={"X-Proxy-Test": "enabled"})
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
            proxy=proxy,
            dns_resolver=FakeDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        )

        assert created_clients
        assert created_clients[0].kwargs["proxy"] is proxy
        assert created_clients[0].kwargs["trust_env"] is False

    def test_make_request_redacts_proxy_credentials_in_network_info(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        url = "https://proxy.test"
        proxy_url = "http://user:secret@gateway:3128"
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

        _, network, _ = make_request(
            url,
            timeout=5.0,
            proxy=proxy_url,
            dns_resolver=FakeDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        )

        assert created_clients[0].kwargs["proxy"] == proxy_url
        assert network.proxy_url == "http://user:****@gateway:3128"

    @pytest.mark.parametrize(
        ("proxy_url", "expect_dns_called", "expect_hostname_in_url"),
        [
            ("socks5h://gateway:1080", False, True),
            ("http://proxy.example.com:8080", False, True),
            ("https://secure-proxy.example.com:8443", False, True),
            ("socks5://gateway:1080", True, False),
        ],
        ids=["socks5h-remote-dns", "http-remote-dns", "https-remote-dns", "socks5-local-dns"],
    )
    def test_make_request_dns_resolution_depends_on_proxy_type(
        self,
        mocker: pytest_mock.MockerFixture,
        proxy_url: str,
        *,
        expect_dns_called: bool,
        expect_hostname_in_url: bool,
    ) -> None:
        """Verify DNS resolution strategy depends on proxy type.

        Remote DNS proxies (socks5h, http, https) skip local DNS and use hostname.
        Local DNS proxies (socks5) resolve DNS locally and use IP address.
        """
        url = "https://target.test/api"
        dns_calls: list[str] = []

        class SpyDNSResolver:
            def resolve(self, host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                dns_calls.append(host)
                return "203.0.113.10", "IPv4", 4.2

        captured_urls: list[str] = []

        class DummyClient:
            def __init__(self, *_: object, **__: object) -> None:
                self.headers: dict[str, str] = {}

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(self, _method: str, request_url: str, **_kw: object) -> object:
                captured_urls.append(request_url)

                class _Stream:
                    def __enter__(self) -> httpx.Response:
                        return httpx.Response(200, request=httpx.Request("GET", url))

                    def __exit__(self, *_exc: object) -> None:
                        return None

                return _Stream()

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        make_request(
            url,
            timeout=5.0,
            proxy=proxy_url,
            dns_resolver=SpyDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        )

        assert len(captured_urls) == 1
        request_host = httpx.URL(captured_urls[0]).host
        if expect_dns_called:
            assert len(dns_calls) == 1
            assert request_host == "203.0.113.10"
        else:
            assert len(dns_calls) == 0
            assert request_host == "target.test"

        if expect_hostname_in_url:
            assert request_host == "target.test"

    def test_make_request_env_proxy_skips_local_dns(
        self,
        mocker: pytest_mock.MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Proxy from HTTPS_PROXY env var triggers remote DNS behavior."""
        url = "https://example.com/path"
        monkeypatch.setenv("HTTPS_PROXY", "http://env-proxy:3128")

        dns_calls: list[str] = []
        created_clients: list[Any] = []

        class SpyDNSResolver:
            def resolve(self, host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                dns_calls.append(host)
                return "203.0.113.99", "IPv4", 4.2

        captured_urls: list[str] = []

        class DummyClient:
            def __init__(self, *_: object, **kwargs: object) -> None:
                self.kwargs = kwargs
                self.headers: dict[str, str] = {}
                created_clients.append(self)

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(self, _method: str, request_url: str, **_kw: object) -> object:
                captured_urls.append(request_url)

                class _Stream:
                    def __enter__(self) -> httpx.Response:
                        return httpx.Response(200, request=httpx.Request("GET", url), content=b"ok")

                    def __exit__(self, *_exc: object) -> None:
                        return None

                return _Stream()

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        make_request(
            url,
            timeout=5.0,
            proxy=None,
            dns_resolver=SpyDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        )

        assert len(dns_calls) == 0
        assert len(captured_urls) == 1
        assert httpx.URL(captured_urls[0]).host == "example.com"
        assert created_clients[0].kwargs["proxy"] == "http://env-proxy:3128"
        assert created_clients[0].kwargs["trust_env"] is False

    @pytest.mark.parametrize(
        ("noproxy", "no_proxy"),
        [(False, "internal.corp,localhost"), (True, "")],
        ids=["no-proxy-env", "explicit-noproxy"],
    )
    def test_make_request_disabled_proxy_preserves_local_dns(
        self,
        mocker: pytest_mock.MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
        *,
        noproxy: bool,
        no_proxy: str,
    ) -> None:
        """NO_PROXY and --proxy "" bypass environment proxy settings."""
        url = "https://internal.corp/api"
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
        if no_proxy:
            monkeypatch.setenv("NO_PROXY", no_proxy)

        dns_calls: list[str] = []
        created_clients: list[Any] = []

        class SpyDNSResolver:
            def resolve(self, host: str, _port: int, _timeout: float) -> tuple[str, str, float]:
                dns_calls.append(host)
                return "10.0.0.5", "IPv4", 1.0

        captured_urls: list[str] = []

        class DummyClient:
            def __init__(self, *_: object, **kwargs: object) -> None:
                self.kwargs = kwargs
                self.headers: dict[str, str] = {}
                created_clients.append(self)

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def stream(self, _method: str, request_url: str, **_kw: object) -> object:
                captured_urls.append(request_url)

                class _Stream:
                    def __enter__(self) -> httpx.Response:
                        return httpx.Response(200, request=httpx.Request("GET", url), content=b"ok")

                    def __exit__(self, *_exc: object) -> None:
                        return None

                return _Stream()

        mocker.patch("httptap.http_client.httpx.Client", side_effect=DummyClient)

        make_request(
            url,
            timeout=5.0,
            proxy=None,
            noproxy=noproxy,
            dns_resolver=SpyDNSResolver(),
            timing_collector=FakeTimingCollector(TimingMetrics(total_ms=1.0)),
        )

        assert len(dns_calls) == 1
        assert len(captured_urls) == 1
        assert "10.0.0.5" in captured_urls[0]
        assert created_clients[0].kwargs["proxy"] is None
        assert created_clients[0].kwargs["trust_env"] is False

    def test_make_request_handles_unexpected_exception(
        self,
        httpx_mock: pytest_httpx.HTTPXMock,
    ) -> None:
        """Test handling of unexpected exceptions."""
        dns_resolver = FakeDNSResolver()
        ip, _family, _dns_ms = dns_resolver.resolve("error.test", 443, 5.0)
        # Simulate unexpected exception
        httpx_mock.add_exception(
            RuntimeError("Unexpected internal error"),
            method="GET",
            url=f"https://{ip}",
        )

        with pytest.raises(RuntimeError, match="Unexpected internal error"):
            make_request(
                "https://error.test",
                timeout=5.0,
                dns_resolver=dns_resolver,
                timing_collector=FakeTimingCollector(TimingMetrics()),
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

        assert _normalize_http_version(raw) == expected

    def test_returns_none_when_missing(self) -> None:

        assert _normalize_http_version(None) is None

    def test_leaves_unknown_strings_untouched(self) -> None:

        assert _normalize_http_version("spdy/3") == "spdy/3"


class TestNeedsRemoteDNS:
    """Unit tests for proxy DNS resolution type detection."""

    @pytest.mark.parametrize(
        ("proxy_url", "expected"),
        [
            ("socks5h://gateway:1080", True),
            ("SOCKS5H://gateway:1080", True),
            ("http://proxy:8080", True),
            ("HTTP://proxy:8080", True),
            ("https://proxy:8443", True),
            ("socks5://gateway:1080", False),
            ("SOCKS5://gateway:1080", False),
            ("socks5h://user:pass@gateway:1080", True),
        ],
        ids=[
            "socks5h",
            "socks5h-upper",
            "http",
            "http-upper",
            "https",
            "socks5-local",
            "socks5-local-upper",
            "socks5h-with-auth",
        ],
    )
    def test_detects_proxy_dns_type(self, proxy_url: str, *, expected: bool) -> None:
        assert _needs_remote_dns(proxy_url) is expected


class TestHostMatchesNoProxy:
    """Unit tests for NO_PROXY pattern matching."""

    @pytest.mark.parametrize(
        ("host", "no_proxy", "expected"),
        [
            ("example.com", "", False),
            ("example.com", "example.com", True),
            ("example.com", "EXAMPLE.COM", True),
            ("sub.example.com", "example.com", True),
            ("sub.example.com", ".example.com", True),
            ("notexample.com", "example.com", False),
            ("example.com", "*", True),
            ("any.host", "*", True),
            ("api.internal.corp", "internal.corp,localhost", True),
            ("external.com", "internal.corp,localhost", False),
            ("example.com", " example.com , other.com ", True),
        ],
        ids=[
            "empty-no-proxy",
            "exact-match",
            "case-insensitive",
            "suffix-match",
            "dot-prefix-match",
            "no-partial-match",
            "wildcard",
            "wildcard-any",
            "multi-entry-match",
            "multi-entry-no-match",
            "whitespace-trimmed",
        ],
    )
    def test_pattern_matching(self, host: str, no_proxy: str, *, expected: bool) -> None:
        assert _host_matches_no_proxy(host, no_proxy) is expected


class TestProxyResolvesRemotely:
    """proxy_resolves_remotely reports whether local DNS overrides can apply."""

    @pytest.mark.parametrize(
        ("proxy", "expected"),
        [
            ("http://proxy.test:8080", True),
            ("socks5h://proxy.test:1080", True),
            ("socks5://proxy.test:1080", False),
            (None, False),
        ],
    )
    def test_proxy_kinds(self, proxy: str | None, *, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            monkeypatch.delenv(name, raising=False)

        assert proxy_resolves_remotely(proxy, "https://example.test/") is expected

    def test_url_without_hostname(self) -> None:
        assert proxy_resolves_remotely("http://proxy.test:8080", "https:///path") is False


class TestResolveEffectiveProxy:
    """Unit tests for effective proxy resolution."""

    def test_explicit_proxy_returned_as_is(self) -> None:
        url, source = _resolve_effective_proxy("socks5h://gw:1080", "https", "example.com")
        assert url == "socks5h://gw:1080"
        assert source == PROXY_SOURCE_CLI

    def test_none_proxy_with_no_env_returns_none(self) -> None:
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url is None
        assert source is None

    def test_env_var_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url == "http://proxy:3128"
        # On Windows, env vars are case-insensitive so the lowercase
        # variant may match first; compare case-insensitively.
        assert source is not None
        assert source.upper() == "HTTPS_PROXY"

    def test_all_proxy_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALL_PROXY", "socks5h://all:1080")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url == "socks5h://all:1080"
        assert source is not None
        assert source.upper() == "ALL_PROXY"

    def test_no_proxy_excludes_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
        monkeypatch.setenv("NO_PROXY", "example.com")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url is None
        assert source == PROXY_SOURCE_NO_PROXY

    def test_no_proxy_does_not_exclude_other_hosts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
        monkeypatch.setenv("NO_PROXY", "internal.corp")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url == "http://proxy:3128"
        assert source is not None
        assert source.upper() == "HTTPS_PROXY"

    def test_lowercase_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("https_proxy", "http://lower:3128")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url == "http://lower:3128"
        assert source == "https_proxy"

    def test_lowercase_env_var_takes_priority_over_uppercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Lowercase variant wins per curl/Python getproxies() convention."""
        monkeypatch.setenv("HTTPS_PROXY", "http://upper:3128")
        monkeypatch.setenv("https_proxy", "http://lower:3128")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url == "http://lower:3128"
        assert source == "https_proxy"

    def test_no_proxy_env_when_env_vars_exist_but_no_scheme_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return 'no_proxy_env' when proxy env vars exist but none match the scheme."""
        monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
        url, source = _resolve_effective_proxy(None, "https", "example.com")
        assert url is None
        assert source == PROXY_SOURCE_NO_MATCH

    def test_scheme_less_env_value_defaults_to_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Like curl and ``-x``, a proxy without a scheme is a plain HTTP proxy."""
        monkeypatch.setenv("HTTP_PROXY", "user:s3cret@127.0.0.1:3128")
        url, _source = _resolve_effective_proxy(None, "http", "example.com")
        assert url == "http://user:s3cret@127.0.0.1:3128"

    def test_noproxy_flag_ignores_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return 'noproxy' when noproxy flag is set, even with proxy env vars."""
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
        url, source = _resolve_effective_proxy(None, "https", "example.com", noproxy=True)
        assert url is None
        assert source == PROXY_SOURCE_DISABLED
