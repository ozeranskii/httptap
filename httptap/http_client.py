"""HTTP client with detailed timing instrumentation.

This module provides an HTTP client that captures precise timing information
for each phase of the request: DNS resolution, TCP connection, TLS handshake,
time to first byte, and body transfer.

The timing collection uses httpx's event hooks and low-level trace callbacks
to capture accurate measurements at each phase boundary. When precise timing
is unavailable (e.g., connection pooling or HTTP/2 multiplexing), the module
falls back to estimated timing based on heuristics.

Key Features:
    - Phase-by-phase timing: DNS, TCP, TLS, TTFB, transfer phases.
    - HTTP/2 support with accurate timing.
    - TLS certificate inspection.
    - Graceful fallback for missing timing data.
    - User-Agent identification for debugging.

Implementation Notes:
    The module uses a two-stage approach for timing:
    1. Primary: httpx EventHooks for precise low-level events
    2. Fallback: Estimation using fixed ratios when hooks unavailable

    For HTTPS, when precise connect/TLS timing is unavailable, we estimate
    from the time between DNS completion and TTFB (the connection phase):
    - TCP Connect: 30% of connection_phase_time
    - TLS Handshake: 70% of connection_phase_time

    Where connection_phase_time = TTFB_total - DNS_time

    These ratios (30%/70%) are conservative estimates based on typical
    network conditions where TLS handshake dominates connection time.

Examples:
    Basic usage:
        >>> timing, network, response = make_request(
        ...     "https://example.com",
        ...     timeout=10.0,
        ...     http2=True,
        ... )
        >>> print(f"Total: {timing.total_ms:.1f}ms")
        Total: 234.5ms

"""

from __future__ import annotations

import os
import socket
import ssl
import threading
import time
import warnings
from base64 import b64encode
from contextlib import closing, suppress
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit, urlunsplit

import httpcore
import httpx

from ._pkgmeta import get_package_info
from .constants import (
    CONNECT_PHASE_RATIO,
    DEFAULT_TIMEOUT_SECONDS,
    HTTP_DEFAULT_PORT,
    HTTPS_DEFAULT_PORT,
    MS_IN_SECOND,
    PROXY_SOURCE_CLI,
    PROXY_SOURCE_DISABLED,
    PROXY_SOURCE_NO_MATCH,
    PROXY_SOURCE_NO_PROXY,
    TLS_PHASE_RATIO,
    HTTPMethod,
)
from .implementations.dns import DNSResolutionError, SystemDNSResolver
from .implementations.timing import PerfCounterTimingCollector
from .implementations.tls import SocketTLSInspector, TLSInspectionError
from .models import NetworkInfo, ResponseInfo, TimingMetrics
from .tls_inspector import (
    SSLObjectLike,
    apply_certificate_info,
    extract_certificate_info,
)
from .utils import create_ssl_context, parse_http_date, redact_url_credentials, sanitize_headers

if TYPE_CHECKING:
    from collections.abc import Mapping

    from httpx._types import ProxyTypes

    from .interfaces import DNSResolver, TimingCollector, TLSInspector
else:  # pragma: no cover - typing helper
    ProxyTypes = object  # type: ignore[assignment]


def _build_user_agent() -> str:
    info = get_package_info()
    return f"httptap/{info.version} (+{info.homepage})"


USER_AGENT = _build_user_agent()


class HTTPClientError(Exception):
    """Raised when HTTP request fails.

    This exception wraps various failure modes including network errors,
    timeouts, DNS failures, and TLS errors into a single exception type
    for consistent error handling by callers.

    Attributes:
        The exception message contains detailed information about the
        failure cause and can be logged or displayed to users.

    Examples:
        >>> try:
        ...     make_request("https://invalid.example", timeout=5.0)
        ... except HTTPClientError as e:
        ...     print(f"Request failed: {e}")
        Request failed: DNS resolution failed: invalid.example

    """

    def __init__(self, message: str, *, network_info: NetworkInfo | None = None) -> None:
        """Initialize an error with optional partial network metadata."""
        super().__init__(message)
        self.network_info = network_info


_DEADLINE_EXCEEDED = "Request timeout: total deadline exceeded"


def remaining_timeout(deadline: float) -> float:
    """Return the seconds left before a ``time.monotonic()`` deadline.

    Raises:
        HTTPClientError: If the deadline has already passed.

    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise HTTPClientError(_DEADLINE_EXCEEDED)
    return remaining


def _build_timing_metrics(
    timing_collector: TimingCollector,
    *,
    is_https: bool,
    connect_ms: float | None = None,
    tls_ms: float | None = None,
    failed_attempts_ms: float = 0.0,
) -> TimingMetrics:
    """Build complete timing metrics from collector and trace data.

    Args:
        timing_collector: Timing collector with raw measurements.
        is_https: Whether this was an HTTPS request.
        connect_ms: Optional precise TCP connection time from trace.
        tls_ms: Optional precise TLS handshake time from trace.
        failed_attempts_ms: Time spent on resolved addresses that failed before
            the one that answered. It is already part of ``ttfb_ms`` and
            ``total_ms`` and is counted as connect time, so it is neither
            estimated as TLS nor left over as server wait.

    Returns:
        TimingMetrics with all phase durations and derived metrics calculated.

    Note:
        When connect_ms or tls_ms are not provided, estimates these values
        using heuristics. For HTTPS: 30% connect, 70% TLS. For HTTP: 100% connect.

    """
    timing = timing_collector.get_metrics()

    # Use precise timing from trace if available
    if connect_ms is not None:
        timing.connect_ms = connect_ms
        timing.is_estimated = False
    if is_https and tls_ms is not None:
        timing.tls_ms = tls_ms
        timing.is_estimated = False

    # Estimate connect/TLS if not available from trace
    if timing.connect_ms == 0.0 and (not is_https or timing.tls_ms == 0.0):
        # Calculate connection phase time (time from DNS end to TTFB)
        # This represents the TCP connect + TLS handshake time
        connection_phase_ms = max(0.0, timing.ttfb_ms - timing.dns_ms - failed_attempts_ms)

        if is_https:
            # Estimate using 30%/70% split (TCP/TLS)
            timing.connect_ms = connection_phase_ms * CONNECT_PHASE_RATIO
            timing.tls_ms = connection_phase_ms * TLS_PHASE_RATIO
            timing.is_estimated = True
        else:
            # HTTP: all connection phase is TCP connect
            timing.connect_ms = connection_phase_ms
            timing.tls_ms = 0.0
            timing.is_estimated = False  # HTTP doesn't need TLS estimation

    timing.connect_ms += failed_attempts_ms
    timing.calculate_derived()
    return timing


def _populate_response_metadata(
    response: httpx.Response,
    response_info: ResponseInfo,
) -> None:
    """Populate response metadata from httpx response."""
    response_info.status = response.status_code
    response_info.content_type = response.headers.get("content-type")
    response_info.server = response.headers.get("server")
    response_info.location = response.headers.get("location")

    date_str = response.headers.get("date")
    if date_str:
        response_info.date = parse_http_date(date_str)

    response_info.headers = sanitize_headers(dict(response.headers))


def _consume_response_body(response: httpx.Response, deadline: float | None = None) -> int:
    """Read the encoded response body to completion and return its wire size.

    With ``deadline`` set, every received chunk is checked against it, so a
    body that keeps trickling in cannot outlive the total request budget.

    Raises:
        httpx.ReadTimeout: If a chunk arrives after ``deadline``.

    """
    if response.is_stream_consumed:
        # In-memory responses (e.g. mock transports) arrive already read; the
        # raw stream is gone, so the decoded content is the only size left.
        return len(response.content)

    total_bytes = 0
    for chunk in response.iter_raw():
        total_bytes += len(chunk)
        if deadline is not None and time.monotonic() >= deadline:
            raise httpx.ReadTimeout(_DEADLINE_EXCEEDED)
    return total_bytes


class _DeadlineWatchdog:
    """Shut the request's connection down once the total deadline passes.

    httpx timeouts bound each network operation, not the request: a server
    that answers every read just before the read timeout (late headers, a
    stalled body, trickling bytes) can keep a request alive far past the
    deadline. Recomputing per-read timeouts is not possible from outside
    httpcore, which fixes the read timeout when a response starts, so a timer
    thread shuts the socket down at the deadline instead. That wakes a
    blocked read at once without polling, and the request then fails with a
    transport error that ``make_request`` reports as the deadline.

    The socket is taken from the httpcore trace events that hand over a new
    stream (TCP connect, TLS handshake). A TLS handshake in progress cannot be
    interrupted this way, since the TLS socket only exists once it completes;
    it stays bounded by the connect timeout and is shut down right after if
    the deadline passed meanwhile.
    """

    _STREAM_EVENTS = (".connect_tcp.complete", ".start_tls.complete")

    def __init__(self, deadline: float) -> None:
        """Prepare a watchdog for ``deadline``; it is armed by entering the context."""
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._active = True
        self.expired = False
        self._timer = threading.Timer(max(0.0, deadline - time.monotonic()), self._expire)
        self._timer.daemon = True

    def __enter__(self) -> Self:
        """Start the deadline timer."""
        self._timer.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Disarm the watchdog and wait for its timer thread to finish."""
        with self._lock:
            self._active = False
            self._socket = None
        self._timer.cancel()
        self._timer.join()

    def observe(self, name: str, info: Mapping[str, object]) -> None:
        """Track the socket of the latest stream reported by an httpcore trace event."""
        if not name.endswith(self._STREAM_EVENTS):
            return
        get_extra_info = getattr(info.get("return_value"), "get_extra_info", None)
        sock = get_extra_info("socket") if callable(get_extra_info) else None
        if not isinstance(sock, socket.socket):
            return
        with self._lock:
            self._socket = sock
            if self.expired:
                self._shutdown()

    def _expire(self) -> None:
        with self._lock:
            if not self._active:
                return
            self.expired = True
            self._shutdown()

    def _shutdown(self) -> None:
        if self._socket is None:
            return
        # socket.socket.shutdown also for TLS sockets: SSLSocket.shutdown
        # drops the SSL object under the thread blocked reading from it.
        with suppress(OSError):
            socket.socket.shutdown(self._socket, socket.SHUT_RDWR)


class TraceCollector:
    """Collect low-level httpcore trace events for precise timing."""

    CONNECT_EVENT = "connection.connect_tcp"
    TLS_EVENT = "connection.start_tls"
    PROXY_TLS_EVENT = "proxy.start_tls"
    SOCKS_CONNECT_EVENT = "socks.connect_tcp"
    SOCKS_HANDSHAKE_EVENT = "socks.setup_socks5_connection"
    SOCKS_TLS_EVENT = "socks.start_tls"

    def __init__(self) -> None:
        """Initialize empty event store for trace durations."""
        self._events: dict[str, dict[str, float]] = {}

    def __call__(self, name: str, _info: dict[str, object]) -> None:
        """Record start/complete timestamps for relevant trace events."""
        timestamp = time.perf_counter()
        prefix, _, stage = name.rpartition(".")
        if not prefix:
            return
        event = self._events.setdefault(prefix, {})
        # Keep the first occurrence: through a CONNECT proxy the tunnel request
        # reuses the same event names as the request sent through the tunnel.
        event.setdefault(stage, timestamp)

    def _stamp(self, event_name: str, stage: str) -> float | None:
        """Return the recorded timestamp of ``event_name.stage``."""
        return self._events.get(event_name, {}).get(stage)

    @staticmethod
    def _elapsed_ms(start: float | None, end: float | None) -> float | None:
        """Return ``end - start`` in milliseconds, or None if either is missing or out of order."""
        if start is None or end is None or end < start:
            return None
        return (end - start) * MS_IN_SECOND

    def _duration_ms(self, event_name: str) -> float | None:
        """Convert stored start/complete timestamps into milliseconds."""
        return self._elapsed_ms(self._stamp(event_name, "started"), self._stamp(event_name, "complete"))

    @property
    def connect_ms(self) -> float | None:
        """Return the time to establish the connection to the origin, in milliseconds.

        For a direct connection this is the TCP connect. Through a proxy the
        origin is reachable only once the proxy path is set up, so the span
        runs from the TCP connect to the proxy until the origin TLS handshake
        starts (or the path is ready, for plain HTTP):

        - HTTP CONNECT proxy: TCP to the proxy, the proxy TLS handshake for an
          ``https://`` proxy, and the CONNECT round-trip.
        - SOCKS proxy: TCP to the proxy and the SOCKS5 handshake.
        """
        socks_started = self._stamp(self.SOCKS_CONNECT_EVENT, "started")
        if socks_started is not None:
            ready = self._stamp(self.SOCKS_TLS_EVENT, "started") or self._stamp(self.SOCKS_HANDSHAKE_EVENT, "complete")
            return self._elapsed_ms(socks_started, ready)
        tunnel_ready = self._stamp(self.PROXY_TLS_EVENT, "started")
        if tunnel_ready is not None:
            return self._elapsed_ms(self._stamp(self.CONNECT_EVENT, "started"), tunnel_ready)
        return self._duration_ms(self.CONNECT_EVENT)

    @property
    def tls_ms(self) -> float | None:
        """Return measured TLS handshake duration in milliseconds.

        HTTPS requests through CONNECT and SOCKS proxies emit the origin
        handshake as ``proxy.start_tls`` / ``socks.start_tls``; prefer those over
        the handshake with an ``https://`` proxy itself.
        """
        for event_name in (self.PROXY_TLS_EVENT, self.SOCKS_TLS_EVENT, self.TLS_EVENT):
            duration = self._duration_ms(event_name)
            if duration is not None:
                return duration
        return None


def _defining_class(cls: type, name: str) -> type | None:
    """Return the class in ``cls``'s MRO that defines attribute ``name``."""
    return next((klass for klass in cls.__mro__ if name in vars(klass)), None)


def _resolve_addresses(
    dns_resolver: DNSResolver,
    host: str,
    port: int,
    timeout: float,
) -> list[tuple[str, str]]:
    """Resolve ``host`` to the addresses to try, in order.

    ``resolve_all()`` is an optional extension of the ``DNSResolver`` protocol
    that enables address fallback. It is only used when it is at least as
    specific as ``resolve()``: a subclass that overrides just ``resolve()``
    (for example to pin an address) must not be bypassed by an inherited
    ``resolve_all()``.

    Raises:
        DNSResolutionError: If the resolver returns no usable address.

    """
    resolver_type = type(dns_resolver)
    resolve_all = getattr(dns_resolver, "resolve_all", None)
    all_owner = _defining_class(resolver_type, "resolve_all")
    one_owner = _defining_class(resolver_type, "resolve")
    if callable(resolve_all) and (one_owner is None or all_owner is None or issubclass(all_owner, one_owner)):
        addresses, _dns_ms = resolve_all(host, port, timeout)
    else:
        ip, ip_family, _dns_ms = dns_resolver.resolve(host, port, timeout)
        addresses = [(ip, ip_family)]
    if not addresses:
        msg = f"No usable address records for {host}"
        raise DNSResolutionError(msg)
    return list(addresses)


# httpcore's message when a SOCKS5 proxy answers CONNECT with a failure reply
# (refused, host or network unreachable, ...). The proxy was reached and
# accepted the credentials, so the failure concerns this target address only;
# authentication and handshake failures use other messages.
_SOCKS_CONNECT_REPLY_FAILURE = "Proxy Server could not connect:"


def _is_socks_target_refusal(error: httpx.ProxyError) -> bool:
    """Return whether a SOCKS proxy refused to reach this particular target address."""
    return str(error).startswith(_SOCKS_CONNECT_REPLY_FAILURE)


def _close_streams(streams: list[httpcore.NetworkStream]) -> None:
    """Close httpcore network streams, ignoring ones that are already closed."""
    for stream in streams:
        with suppress(Exception):
            stream.close()


def _has_tls_error(error: BaseException) -> bool:
    """Return whether an HTTP client error was caused by TLS negotiation."""
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, ssl.SSLError):
            return True
        cause = cause.__cause__
    return False


# Proxy schemes where DNS resolution happens on the proxy side.
# All other schemes (e.g. socks5) perform local DNS on the client.
_REMOTE_DNS_PROXY_SCHEMES: frozenset[str] = frozenset({"socks5h", "http", "https"})


def _needs_remote_dns(proxy_url: str) -> bool:
    """Check if the proxy requires remote DNS resolution.

    Remote DNS proxy types send the hostname to the proxy for resolution:
        - socks5h:// - SOCKS5 with remote hostname resolution
        - http:// - HTTP CONNECT proxy
        - https:// - HTTPS CONNECT proxy

    Local DNS proxy types resolve DNS on the client side:
        - socks5:// - SOCKS5 with local DNS resolution

    Args:
        proxy_url: The proxy URL to check.

    Returns:
        True if the proxy handles DNS resolution remotely.

    """
    scheme = proxy_url.split("://", maxsplit=1)[0].lower()
    return scheme in _REMOTE_DNS_PROXY_SCHEMES


_SUPPORTED_PROXY_SCHEMES: tuple[str, ...] = ("http", "https", "socks5", "socks5h")
_MAX_PORT = 65535


def _with_default_proxy_scheme(value: str) -> str:
    """Treat a proxy given without a scheme as a plain HTTP proxy, as curl does."""
    return value if "://" in value else f"http://{value}"


def _proxy_url_problem(proxy_url: str) -> str | None:
    """Return why ``proxy_url`` cannot be used as a proxy, or None if it can.

    The reason never repeats the URL, so it is safe to show next to the
    redacted URL.
    """
    try:
        parsed = httpx.URL(proxy_url)
        port = parsed.port
    except httpx.InvalidURL:
        return "malformed URL"
    if parsed.scheme not in _SUPPORTED_PROXY_SCHEMES:
        return f"unsupported scheme {parsed.scheme!r}; expected one of {', '.join(_SUPPORTED_PROXY_SCHEMES)}"
    if not parsed.host:
        return "missing host"
    if port is not None and not 1 <= port <= _MAX_PORT:
        return f"port {port} out of range 1-{_MAX_PORT}"
    return None


def _host_matches_no_proxy(host: str, no_proxy: str) -> bool:
    """Check if a hostname matches any entry in the NO_PROXY exclusion list.

    Supports exact matches, suffix matches with leading dot, and wildcard (*).

    Args:
        host: Hostname to check (e.g., "api.example.com").
        no_proxy: Comma-separated list of hosts/patterns to exclude.

    Returns:
        True if the host should bypass proxy.

    """
    if not no_proxy:
        return False

    host_lower = host.lower()

    def _matches(pattern: str) -> bool:
        return (
            pattern in {"*", host_lower}
            or (pattern.startswith(".") and host_lower.endswith(pattern))
            or host_lower.endswith(f".{pattern}")
        )

    return any(_matches(entry.strip().lower()) for entry in no_proxy.split(",") if entry.strip())


_PROXY_URL_ENV_VARS: frozenset[str] = frozenset(
    {
        "http_proxy",
        "HTTP_PROXY",
        "https_proxy",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    }
)


def _any_proxy_env_set() -> bool:
    """Return True if any proxy URL environment variable is set.

    Only checks variables that carry a proxy URL (http_proxy, https_proxy,
    all_proxy and their uppercase variants). NO_PROXY / no_proxy are
    exclusion lists, not proxy URLs, and are intentionally excluded.
    """
    return any(os.environ.get(v) for v in _PROXY_URL_ENV_VARS)


def _resolve_effective_proxy(
    proxy: ProxyTypes | None,
    url_scheme: str,
    host: str,
    *,
    noproxy: bool = False,
) -> tuple[str | None, str | None]:
    """Resolve the effective proxy URL for a request.

    When an explicit proxy is provided, returns its URL string. Otherwise
    checks standard proxy environment variables (HTTPS_PROXY, HTTP_PROXY,
    ALL_PROXY) with NO_PROXY exclusion support.

    Args:
        proxy: Explicit proxy from the caller, or None.
        url_scheme: Scheme of the target URL (e.g., "https").
        host: Hostname of the target URL.
        noproxy: When True, skip all proxy resolution and connect directly.

    Returns:
        Tuple of (proxy_url, source) where source describes the origin:
        - ("url", "--proxy") for explicit CLI proxy
        - ("url", "HTTPS_PROXY") for env-var proxy (var name as source)
        - (None, "NO_PROXY") when host matched NO_PROXY exclusion
        - (None, "noproxy") when proxy was disabled via --proxy ""
        - (None, "no_proxy_env") when proxy env vars exist but none matched
        - (None, None) when no proxy is configured at all

    """
    if noproxy:
        return None, PROXY_SOURCE_DISABLED

    if proxy is not None:
        return str(getattr(proxy, "url", proxy)), PROXY_SOURCE_CLI

    # Check NO_PROXY exclusions before reading proxy env vars.
    # Lowercase no_proxy takes priority per curl/Python convention.
    no_proxy = os.environ.get("no_proxy", os.environ.get("NO_PROXY", ""))
    if _host_matches_no_proxy(host, no_proxy):
        return None, PROXY_SOURCE_NO_PROXY

    # Resolve scheme-specific proxy env var, then ALL_PROXY fallback.
    # Lowercase variants take priority per curl/Python getproxies() convention.
    scheme_lower = url_scheme.lower()
    scheme_upper = url_scheme.upper()

    for var_name in (
        f"{scheme_lower}_proxy",
        f"{scheme_upper}_PROXY",
        "all_proxy",
        "ALL_PROXY",
    ):
        value = os.environ.get(var_name)
        if value:
            return _with_default_proxy_scheme(value), var_name

    if _any_proxy_env_set():
        return None, PROXY_SOURCE_NO_MATCH

    return None, None


def proxy_resolves_remotely(proxy: ProxyTypes | None, url: str, *, noproxy: bool = False) -> bool:
    """Return whether the proxy effective for ``url`` resolves the target hostname itself.

    Local DNS overrides (address family, ``--resolve``) cannot apply in that case.
    """
    parsed_url = urlsplit(url)
    if parsed_url.hostname is None:
        return False
    effective_proxy_url, _source = _resolve_effective_proxy(
        proxy,
        parsed_url.scheme,
        parsed_url.hostname,
        noproxy=noproxy,
    )
    return effective_proxy_url is not None and _needs_remote_dns(effective_proxy_url)


def make_request(  # noqa: C901, PLR0912, PLR0915, PLR0913
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    *,
    deadline: float | None = None,
    method: HTTPMethod = HTTPMethod.GET,
    content: bytes | None = None,
    http2: bool = True,
    verify_ssl: bool = True,
    ca_bundle_path: str | None = None,
    proxy: ProxyTypes | None = None,
    noproxy: bool = False,
    dns_resolver: DNSResolver | None = None,
    tls_inspector: TLSInspector | None = None,
    timing_collector: TimingCollector | None = None,
    force_new_connection: bool | None = None,
    headers: Mapping[str, str] | None = None,
) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
    """Make HTTP request and collect comprehensive metrics.

    Performs a complete HTTP request with detailed instrumentation to
    capture timing, network, and response information at each phase.

    This is the main entry point for making instrumented HTTP requests.
    It handles:
    - Manual DNS resolution with timing
    - HTTP/1.1 and HTTP/2 support
    - Precise timing collection via httpx traces
    - TLS certificate inspection (separate probe)
    - Response header and body parsing

    Args:
        url: Target URL to request. Must be valid HTTP/HTTPS URL with scheme.
        timeout: Maximum time to wait for complete response in seconds.
            Applies to the entire request including DNS, connection, and transfer.
        deadline: Optional ``time.monotonic()`` deadline shared by a redirect
            chain. Defaults to ``timeout`` seconds from now; every phase (DNS,
            connect, body transfer, TLS probe) is bounded by it.
        method: HTTP method to use (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS).
            Defaults to GET.
        content: Optional request body as bytes. Typically used with POST, PUT, PATCH.
        http2: Whether to enable HTTP/2 protocol negotiation. Set to False
            to force HTTP/1.1.
        verify_ssl: Whether to verify TLS certificates during the request.
            Defaults to True. Set to False when troubleshooting hosts with
            self-signed or otherwise invalid certificates.
        ca_bundle_path: Path to custom CA certificate bundle (PEM format).
            Only used when verify_ssl is True. If None, uses system CA bundle.
        proxy: Optional proxy URL or mapping (supports http/https/socks5/socks5h).
        noproxy: When True, ignore proxy environment variables and connect
            directly. Triggered by --proxy "".
        dns_resolver: Custom DNS resolver implementation.
            Defaults to SystemDNSResolver.
        tls_inspector: Custom TLS inspector implementation.
            Defaults to SocketTLSInspector.
        timing_collector: Custom timing collector implementation.
            Defaults to PerfCounterTimingCollector.
        force_new_connection: Deprecated and ignored. A fresh ``httpx.Client``
            (and therefore a fresh connection) is created for every request, so
            connection pooling is never used. Accepted only for backward
            compatibility; passing a value emits a ``DeprecationWarning``.
        headers: Optional HTTP headers applied to the request. User-supplied
            values override the defaults.

    Returns:
        Tuple of (timing_metrics, network_info, response_info):
            - timing_metrics: Phase-by-phase timing breakdown.
            - network_info: IP, TLS version, cipher, certificate details.
            - response_info: Status, headers, body size, parsed date.

    Raises:
        HTTPClientError: If request fails at any phase (DNS, connect,
            TLS handshake, timeout, or HTTP error). The exception message
            contains details about the failure.

    Examples:
        Basic request:
            >>> timing, network, response = make_request("https://example.com")
            >>> print(f"Status: {response.status}")
            Status: 200
            >>> print(f"IP: {network.ip}")
            IP: 93.184.216.34
            >>> print(f"Total time: {timing.total_ms:.1f}ms")
            Total time: 234.5ms

        With custom implementations:
            >>> custom_resolver = MyDNSResolver()
            >>> timing, network, response = make_request(
            ...     "https://api.example.com",
            ...     dns_resolver=custom_resolver,
            ...     timeout=5.0,
            ...     http2=False
            ... )

    Notes:
        The function performs DNS resolution manually before the HTTP request
        to capture accurate DNS timing. The resolved IP is not passed to httpx,
        so httpx will perform its own DNS resolution internally.

        For HTTPS requests, the function makes a separate TLS probe connection
        to extract detailed certificate information (CN, expiry, etc). This probe
        happens after the main request completes and adds minimal overhead.

        By default a new connection is used for every request: httptap creates
        a short-lived ``httpx.Client`` per call, so connection pooling never
        applies and connect/TLS timing is always fresh.

    """
    if force_new_connection is not None:
        warnings.warn(
            "force_new_connection is deprecated and has no effect; a new "
            "httpx.Client is created for every request. It will be removed in "
            "a future release.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Use default implementations if not provided
    if dns_resolver is None:
        dns_resolver = SystemDNSResolver()
    if tls_inspector is None:
        tls_inspector = SocketTLSInspector(verify=verify_ssl, ca_bundle_path=ca_bundle_path)
    if timing_collector is None:
        timing_collector = PerfCounterTimingCollector()

    network_info = NetworkInfo()
    network_info.tls_verified = verify_ssl
    network_info.tls_custom_ca = bool(ca_bundle_path) if verify_ssl else False
    response_info = ResponseInfo()
    request_deadline = deadline if deadline is not None else time.monotonic() + timeout
    watchdog = _DeadlineWatchdog(request_deadline)

    try:
        remaining_timeout(request_deadline)
        try:
            parsed_url = urlsplit(url)
            source_url = httpx.URL(url)
            host = parsed_url.hostname
            port = parsed_url.port or (HTTPS_DEFAULT_PORT if parsed_url.scheme == "https" else HTTP_DEFAULT_PORT)
        except (ValueError, httpx.InvalidURL) as exc:
            msg = f"Invalid URL: {exc}"
            raise HTTPClientError(msg) from exc
        is_https = parsed_url.scheme == "https"

        if not host:
            msg = "Invalid URL: missing hostname"
            raise HTTPClientError(msg)  # noqa: TRY301
        # IDNA 2008 A-label form for DNS, Host and SNI alike: given a Unicode
        # name, getaddrinfo would apply IDNA 2003, which maps some names
        # (faß.de -> fass.de) to a different domain than the one in Host/SNI.
        wire_host = source_url.raw_host.decode("ascii")

        # Determine effective proxy and DNS resolution strategy.
        #
        # Different proxy types have different DNS resolution requirements:
        # - socks5h://, http://, https:// → Remote DNS (proxy resolves hostname)
        # - socks5:// → Local DNS (client resolves, sends IP to proxy)
        # - No proxy → Local DNS (direct connection)
        #
        # When using remote DNS proxies, we skip local resolution and send the
        # original hostname so the proxy can resolve it. This prevents TLS errors
        # caused by sending CONNECT with an IP instead of a hostname.
        effective_proxy_url, proxy_source = _resolve_effective_proxy(
            proxy,
            parsed_url.scheme,
            host,
            noproxy=noproxy,
        )
        network_info.proxy_url = redact_url_credentials(effective_proxy_url) if effective_proxy_url else None
        network_info.proxy_source = proxy_source
        if effective_proxy_url is not None:
            problem = _proxy_url_problem(effective_proxy_url)
            if problem is not None:
                msg = f"Invalid proxy URL in {proxy_source}: {network_info.proxy_url} ({problem})"
                raise HTTPClientError(msg, network_info=network_info)  # noqa: TRY301
        skip_local_dns = effective_proxy_url is not None and _needs_remote_dns(effective_proxy_url)

        if skip_local_dns:
            # Remote DNS proxy: skip local resolution, let the proxy handle it
            timing_collector.mark_dns_start()
            timing_collector.mark_dns_end()
            network_info.ip = None
            network_info.ip_family = None
            addresses = [(host, "")]
        else:
            # Local DNS: resolve hostname before connecting
            timing_collector.mark_dns_start()
            try:
                addresses = _resolve_addresses(dns_resolver, wire_host, port, remaining_timeout(request_deadline))
            except DNSResolutionError as e:
                raise HTTPClientError(str(e), network_info=network_info) from e
            finally:
                timing_collector.mark_dns_end()

        trace = TraceCollector()

        ssl_context = create_ssl_context(verify_ssl=verify_ssl, ca_bundle_path=ca_bundle_path)

        try:
            transport = httpx.HTTPTransport(
                verify=ssl_context,
                http2=http2,
                # Proxy resolution is handled above against the original hostname.
                # Do not let httpx reapply environment proxy settings after DNS.
                proxy=proxy if proxy is not None and effective_proxy_url is not None else effective_proxy_url,
                trust_env=False,
            )
        except (ValueError, ImportError, httpx.InvalidURL) as exc:
            # httpx renders proxy URLs with the password masked, and optional
            # transport dependencies (socksio, h2) fail with an ImportError.
            msg = f"Cannot set up the HTTP client: {exc}"
            raise HTTPClientError(msg, network_info=network_info) from exc
        # The client only builds requests (default headers, timeouts); they are
        # sent on the transport directly. Client.send prepares the next redirect
        # request even with follow_redirects=False and fails on a Location that
        # httpx cannot parse, which would turn a received 3xx into an error.
        client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=False, trust_env=False)

        with client, watchdog:
            client.headers["User-Agent"] = USER_AGENT
            if headers:
                client.headers.update(headers)
            if not headers or not any(name.lower() == "host" for name in headers):
                host_header = f"[{wire_host}]" if ":" in wire_host else wire_host
                default_port = HTTPS_DEFAULT_PORT if parsed_url.scheme == "https" else HTTP_DEFAULT_PORT
                if port != default_port:
                    host_header = f"{host_header}:{port}"
                client.headers["Host"] = host_header

            has_authorization_header = headers is not None and any(name.lower() == "authorization" for name in headers)
            if parsed_url.username is not None and not has_authorization_header:
                credentials = f"{source_url.username}:{source_url.password}".encode()
                client.headers["Authorization"] = f"Basic {b64encode(credentials).decode('ascii')}"

            # One request start for every attempt: time lost on addresses that
            # failed is part of the request, as with curl. The final attempt's
            # trace only measures its own connect, so the failed attempts are
            # added to connect_ms (curl's time_connect counts them as well);
            # otherwise they would show up as server wait time.
            timing_collector.mark_request_start()
            requests_started = time.perf_counter()
            failed_attempts_ms = 0.0
            for index, (ip, ip_family) in enumerate(addresses):  # pragma: no branch - exits via break or raise
                attempt_timeout = request_deadline - time.monotonic()
                if attempt_timeout <= 0:
                    msg = "Request timeout exhausted before connection could be established"
                    raise httpx.ConnectTimeout(msg)
                addresses_left = len(addresses) - index
                client.timeout = httpx.Timeout(attempt_timeout, connect=attempt_timeout / addresses_left)
                # Not keyed on ip_family: with a remote-DNS proxy the target is the
                # URL host itself, which may be an IPv6 literal with no family set.
                request_target = f"[{ip}]" if ":" in ip else ip
                request_url = urlunsplit(
                    (parsed_url.scheme, f"{request_target}:{port}", parsed_url.path, parsed_url.query, "")
                )
                # Record the address before connecting so a total failure still reports
                # the last address tried; the trace restarts so it describes the
                # connection that served the response.
                network_info.ip = None if skip_local_dns else ip
                network_info.ip_family = None if skip_local_dns else ip_family
                trace = TraceCollector()
                tcp_streams: list[httpcore.NetworkStream] = []

                def on_trace(
                    name: str,
                    info: dict[str, object],
                    trace: TraceCollector = trace,
                    tcp_streams: list[httpcore.NetworkStream] = tcp_streams,
                ) -> None:
                    trace(name, info)
                    watchdog.observe(name, info)
                    stream = info.get("return_value")
                    if name.endswith(".connect_tcp.complete") and isinstance(stream, httpcore.NetworkStream):
                        tcp_streams.append(stream)

                failed_attempts_ms = (time.perf_counter() - requests_started) * MS_IN_SECOND
                try:
                    try:
                        request = client.build_request(
                            method.value,
                            request_url,
                            content=content,
                            extensions={"trace": on_trace, "sni_hostname": wire_host},
                        )
                        response = transport.handle_request(request)
                        response.request = request
                        with closing(response):
                            timing_collector.mark_ttfb()
                            _populate_response_metadata(response, response_info)
                            _populate_tls_from_stream(response, network_info)
                            network_info.http_version = network_info.http_version or _normalize_http_version(
                                response.http_version
                            )
                            response_info.bytes = _consume_response_body(response, request_deadline)
                            break
                    except Exception:
                        # httpcore's SOCKS pool does not close the proxy socket when
                        # the handshake or TLS setup fails; with address fallback
                        # those sockets would pile up until garbage collection.
                        _close_streams(tcp_streams)
                        raise
                except httpx.ProxyError as exc:
                    if not _is_socks_target_refusal(exc) or index == len(addresses) - 1:
                        raise
                except httpx.ConnectError as exc:
                    # Through a proxy (only a local-DNS socks5:// one resolves to
                    # several addresses) the TCP connect goes to the proxy itself,
                    # so its failure would repeat for every address.
                    if (
                        watchdog.expired
                        or effective_proxy_url is not None
                        or _has_tls_error(exc)
                        or index == len(addresses) - 1
                    ):
                        raise
                except httpx.ConnectTimeout:
                    if effective_proxy_url is not None or index == len(addresses) - 1:
                        raise

        timing_collector.mark_request_end()

        timing = _build_timing_metrics(
            timing_collector,
            is_https=is_https,
            connect_ms=trace.connect_ms,
            tls_ms=trace.tls_ms,
            failed_attempts_ms=failed_attempts_ms,
        )

        # Fallback probe: only when the live connection exposed no TLS and no
        # proxy is set. A direct socket probe would bypass the proxy and could
        # reach a different backend, so it must never run while a proxy is used.
        if is_https and network_info.tls_version is None and effective_proxy_url is None:
            # The probe is optional metadata: with no budget left it is skipped
            # rather than turning a completed response into a timeout.
            probe_timeout = request_deadline - time.monotonic()
            if probe_timeout > 0:
                with suppress(TLSInspectionError):
                    _merge_tls_info(
                        network_info,
                        _probe_tls(tls_inspector, wire_host, port, probe_timeout, connect_host=network_info.ip),
                    )

    except httpx.TimeoutException as exc:
        if time.monotonic() >= request_deadline:
            raise HTTPClientError(_DEADLINE_EXCEEDED, network_info=network_info) from exc
        msg = f"Request timeout: {exc}"
        raise HTTPClientError(msg, network_info=network_info) from exc
    except httpx.RequestError as exc:
        if watchdog.expired:
            # The watchdog shut the connection down; the transport error it
            # caused is only a symptom of the deadline.
            raise HTTPClientError(_DEADLINE_EXCEEDED, network_info=network_info) from exc
        msg = f"Request failed: {exc}"
        if (
            is_https
            and host is not None
            and verify_ssl
            and effective_proxy_url is None
            and _is_certificate_verification_error(exc)
        ):
            # The diagnostic probe only uses what is left of the total budget;
            # the verification failure stays the reported error either way.
            probe_timeout = request_deadline - time.monotonic()
            if probe_timeout > 0:
                with suppress(TLSInspectionError):
                    diagnostic_inspector = SocketTLSInspector(verify=False)
                    _merge_tls_info(
                        network_info,
                        diagnostic_inspector.inspect(wire_host, port, probe_timeout, connect_host=network_info.ip),
                    )
        raise HTTPClientError(msg, network_info=network_info) from exc
    except HTTPClientError:
        raise

    return timing, network_info, response_info


def _probe_tls(
    tls_inspector: TLSInspector,
    host: str,
    port: int,
    timeout: float,
    *,
    connect_host: str | None,
) -> NetworkInfo:
    """Run the fallback TLS probe against the address the request used.

    The built-in inspector can dial ``connect_host`` while keeping ``host`` for
    SNI, so ``--resolve``, ``-4``/``-6`` and injected resolvers are honoured.
    Custom inspectors keep the plain ``TLSInspector`` protocol.
    """
    if isinstance(tls_inspector, SocketTLSInspector) and connect_host:
        return tls_inspector.inspect(host, port, timeout, connect_host=connect_host)
    return tls_inspector.inspect(host, port, timeout)


def _merge_tls_info(network_info: NetworkInfo, tls_info: NetworkInfo) -> None:
    """Merge TLS and certificate metadata without replacing DNS metadata."""
    network_info.tls_version = tls_info.tls_version
    network_info.tls_cipher = tls_info.tls_cipher
    network_info.cert_cn = tls_info.cert_cn
    network_info.cert_days_left = tls_info.cert_days_left
    network_info.cert_sans = tls_info.cert_sans
    network_info.cert_issuer = tls_info.cert_issuer
    network_info.cert_serial = tls_info.cert_serial
    network_info.cert_not_before = tls_info.cert_not_before
    network_info.cert_not_after = tls_info.cert_not_after


def _is_certificate_verification_error(exc: BaseException) -> bool:
    """Return whether an HTTPX error was caused by certificate verification."""
    pending = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(current).upper():
            return True
        pending.extend(error for error in (current.__cause__, current.__context__) if error is not None)
        pending.extend(error for error in current.args if isinstance(error, BaseException))
    return False


def _populate_tls_from_stream(
    response: httpx.Response,
    network_info: NetworkInfo,
) -> None:
    """Fill TLS metadata from the connection that served the response.

    Reads the negotiated version, cipher, and full peer certificate directly
    from the live SSL object exposed by httpcore's ``network_stream`` — no
    extra handshake, and the certificate is guaranteed to come from the node
    that actually answered (unlike a separate probe, which re-resolves DNS and
    may land on a different backend).

    This must be called while the response stream is still open, before the
    body is consumed: once the body is drained the sync backend releases the
    SSL object and ``get_extra_info("ssl_object")`` returns ``None``.
    """
    ssl_object = _extract_ssl_object(response)
    if ssl_object is None:
        return

    with suppress(Exception):
        network_info.tls_version = network_info.tls_version or ssl_object.version()

    with suppress(Exception):
        cipher_info = ssl_object.cipher()
        if cipher_info:
            network_info.tls_cipher = network_info.tls_cipher or cipher_info[0]

    with suppress(Exception):
        cert_info = extract_certificate_info(ssl_object)
        if cert_info is not None:
            apply_certificate_info(network_info, cert_info)


def _normalize_http_version(version: str | None) -> str | None:
    """Return a consistent HTTP/x.y string, adding .0 when missing."""
    if not version:
        return None

    normalized = version.upper()
    if normalized in {"H2", "H3"}:
        normalized = f"HTTP/{normalized[1:]}"

    if not normalized.startswith("HTTP/"):
        return version

    proto = normalized.split("/", 1)[1]
    if "." not in proto:
        proto = f"{proto}.0"

    return f"HTTP/{proto}"


def _extract_ssl_object(
    response: httpx.Response,
) -> SSLObjectLike | None:
    """Return the live SSL object backing the response stream, if any.

    Queries the documented ``network_stream`` response extension via
    ``get_extra_info``. The ``"ssl_object"`` key is preferred — it works across
    every backend (a low-level ``_ssl._SSLSocket`` on the sync backend, an
    :class:`ssl.SSLObject` on the async and TLS-in-TLS/proxy paths) — with
    ``"socket"`` (an :class:`ssl.SSLSocket`) as a fallback. Candidates are
    accepted purely by structural type (:class:`SSLObjectLike`), so plain
    (non-TLS) sockets are naturally rejected and the caller never has to branch
    on a concrete class.
    """
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None

    getter = getattr(stream, "get_extra_info", None)
    if not callable(getter):
        return None

    for key in ("ssl_object", "socket"):
        candidate: object | None = None
        with suppress(Exception):  # extras are best-effort across backends
            candidate = getter(key)
        if isinstance(candidate, SSLObjectLike):
            return candidate
    return None
