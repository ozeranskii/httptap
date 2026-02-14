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
import ssl
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from urllib.parse import urlparse

import httpx

from ._pkgmeta import get_package_info
from .constants import (
    CONNECT_PHASE_RATIO,
    DEFAULT_TIMEOUT_SECONDS,
    HTTP_DEFAULT_PORT,
    HTTPS_DEFAULT_PORT,
    MS_IN_SECOND,
    TLS_PHASE_RATIO,
    HTTPMethod,
)
from .implementations.dns import DNSResolutionError, SystemDNSResolver
from .implementations.timing import PerfCounterTimingCollector
from .implementations.tls import SocketTLSInspector, TLSInspectionError
from .models import NetworkInfo, ResponseInfo, TimingMetrics
from .tls_inspector import extract_certificate_info
from .utils import create_ssl_context, parse_http_date, sanitize_headers

if TYPE_CHECKING:
    from collections.abc import Mapping

    from httpx._types import ProxyTypes

    from .interfaces import DNSResolver, TimingCollector, TLSInspector
else:  # pragma: no cover - typing helper
    ProxyTypes = object  # type: ignore[assignment]


@runtime_checkable
class SSLInfoProvider(Protocol):
    """Protocol describing minimal TLS attributes exposed by stream objects."""

    def version(self) -> str:
        """Return the negotiated TLS protocol version."""

    def cipher(self) -> tuple[str, str, int]:
        """Return the active cipher suite description."""


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


def _build_timing_metrics(
    timing_collector: TimingCollector,
    *,
    is_https: bool,
    connect_ms: float | None = None,
    tls_ms: float | None = None,
) -> TimingMetrics:
    """Build complete timing metrics from collector and trace data.

    Args:
        timing_collector: Timing collector with raw measurements.
        is_https: Whether this was an HTTPS request.
        connect_ms: Optional precise TCP connection time from trace.
        tls_ms: Optional precise TLS handshake time from trace.

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
        connection_phase_ms = max(0.0, timing.ttfb_ms - timing.dns_ms)

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


def _consume_response_body(response: httpx.Response) -> int:
    """Read response body to completion and return byte count."""
    total_bytes = 0
    for chunk in response.iter_bytes():
        total_bytes += len(chunk)
    return total_bytes


class TraceCollector:
    """Collect low-level httpcore trace events for precise timing."""

    CONNECT_EVENT = "connection.connect_tcp"
    TLS_EVENT = "connection.start_tls"

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
        event[stage] = timestamp

    def _duration_ms(self, event_name: str) -> float | None:
        """Convert stored start/complete timestamps into milliseconds."""
        event = self._events.get(event_name)
        if not event:
            return None
        start = event.get("started")
        end = event.get("complete")
        if start is None or end is None or end < start:
            return None
        return (end - start) * MS_IN_SECOND

    @property
    def connect_ms(self) -> float | None:
        """Return measured TCP connect duration in milliseconds."""
        return self._duration_ms(self.CONNECT_EVENT)

    @property
    def tls_ms(self) -> float | None:
        """Return measured TLS handshake duration in milliseconds."""
        return self._duration_ms(self.TLS_EVENT)


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


def _resolve_effective_proxy(
    proxy: ProxyTypes | None,
    url_scheme: str,
    host: str,
) -> str | None:
    """Resolve the effective proxy URL for a request.

    When an explicit proxy is provided, returns its URL string. Otherwise
    checks standard proxy environment variables (HTTPS_PROXY, HTTP_PROXY,
    ALL_PROXY) with NO_PROXY exclusion support.

    Args:
        proxy: Explicit proxy from the caller, or None.
        url_scheme: Scheme of the target URL (e.g., "https").
        host: Hostname of the target URL.

    Returns:
        Proxy URL string if a proxy applies, None otherwise.

    """
    if proxy is not None:
        return str(getattr(proxy, "url", proxy))

    # Check NO_PROXY exclusions before reading proxy env vars.
    # Lowercase no_proxy takes priority per curl/Python convention.
    no_proxy = os.environ.get("no_proxy", os.environ.get("NO_PROXY", ""))
    if _host_matches_no_proxy(host, no_proxy):
        return None

    # Resolve scheme-specific proxy env var, then ALL_PROXY fallback.
    # Lowercase variants take priority per curl/Python getproxies() convention.
    scheme_lower = url_scheme.lower()
    scheme_upper = url_scheme.upper()

    return (
        os.environ.get(f"{scheme_lower}_proxy")
        or os.environ.get(f"{scheme_upper}_PROXY")
        or os.environ.get("all_proxy")  # noqa: SIM112 - lowercase variant takes priority
        or os.environ.get("ALL_PROXY")
    ) or None


def make_request(  # noqa: C901, PLR0912, PLR0915, PLR0913
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    *,
    method: HTTPMethod = HTTPMethod.GET,
    content: bytes | None = None,
    http2: bool = True,
    verify_ssl: bool = True,
    ca_bundle_path: str | None = None,
    proxy: ProxyTypes | None = None,
    dns_resolver: DNSResolver | None = None,
    tls_inspector: TLSInspector | None = None,
    timing_collector: TimingCollector | None = None,
    force_new_connection: bool = True,
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
        dns_resolver: Custom DNS resolver implementation.
            Defaults to SystemDNSResolver.
        tls_inspector: Custom TLS inspector implementation.
            Defaults to SocketTLSInspector.
        timing_collector: Custom timing collector implementation.
            Defaults to PerfCounterTimingCollector.
        force_new_connection: Force httpx to create a new connection instead
            of reusing pooled connections. When True (default), ensures accurate
            connect/TLS timing by disabling connection pooling. Set to False
            for better performance when timing accuracy is not critical.
        headers: Optional HTTP headers applied to the request. User-supplied
            values override the defaults (except the tool's User-Agent).

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

        By default (force_new_connection=True), connection pooling is disabled
        to ensure accurate connect/TLS timing from httpcore trace events.
        Set force_new_connection=False for better performance when precise
        timing is not critical.

    """
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

    try:
        parsed_url = urlparse(url)
        host = parsed_url.hostname
        port = parsed_url.port or (HTTPS_DEFAULT_PORT if parsed_url.scheme == "https" else HTTP_DEFAULT_PORT)
        is_https = parsed_url.scheme == "https"

        if not host:
            msg = "Invalid URL: missing hostname"
            raise HTTPClientError(msg)  # noqa: TRY301

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
        effective_proxy_url = _resolve_effective_proxy(proxy, parsed_url.scheme, host)
        skip_local_dns = effective_proxy_url is not None and _needs_remote_dns(effective_proxy_url)

        if skip_local_dns:
            # Remote DNS proxy: skip local resolution, let the proxy handle it
            timing_collector.mark_dns_start()
            timing_collector.mark_dns_end()
            network_info.ip = None
            network_info.ip_family = None
            request_target = host
        else:
            # Local DNS: resolve hostname before connecting
            timing_collector.mark_dns_start()
            try:
                ip, ip_family, _dns_ms = dns_resolver.resolve(host, port, timeout)
                network_info.ip = ip
                network_info.ip_family = ip_family
            except DNSResolutionError as e:
                raise HTTPClientError(str(e)) from e
            finally:
                timing_collector.mark_dns_end()

            request_target = f"[{ip}]" if ip_family == "IPv6" else ip

        timing_collector.mark_request_start()

        trace = TraceCollector()

        # Configure connection limits to force new connections if requested
        limits = httpx.Limits(
            max_connections=1,
            max_keepalive_connections=0 if force_new_connection else 1,
        )

        ssl_context = create_ssl_context(verify_ssl=verify_ssl, ca_bundle_path=ca_bundle_path)

        with httpx.Client(
            timeout=timeout,
            http2=http2,
            follow_redirects=False,
            verify=ssl_context,
            proxy=proxy,
            limits=limits,
        ) as client:
            client.headers["User-Agent"] = USER_AGENT
            if headers:
                client.headers.update(headers)
            # Ensure the Host header is set to the original domain name
            client.headers["Host"] = host

            request_url = f"{parsed_url.scheme}://{request_target}:{port}{parsed_url.path}"
            if parsed_url.query:
                request_url += f"?{parsed_url.query}"

            with client.stream(
                method.value, request_url, content=content, extensions={"trace": trace, "sni_hostname": host}
            ) as response:
                timing_collector.mark_ttfb()
                _populate_response_metadata(response, response_info)
                response_info.bytes = _consume_response_body(response)
                _populate_tls_from_stream(response, network_info)
                network_info.http_version = network_info.http_version or _normalize_http_version(response.http_version)

        timing_collector.mark_request_end()

        timing = _build_timing_metrics(
            timing_collector,
            is_https=is_https,
            connect_ms=trace.connect_ms,
            tls_ms=trace.tls_ms,
        )

        # Gather TLS metadata for HTTPS.
        # Skip separate TLS inspection when using a proxy, as the TLS inspector
        # makes a direct socket connection that bypasses the proxy. TLS info is
        # already captured via _populate_tls_from_stream when available.
        if is_https and network_info.tls_version is None and effective_proxy_url is None:
            try:
                tls_info = tls_inspector.inspect(host, port, timeout)
                # Merge TLS info (preserve IP/family from DNS)
                network_info.tls_version = tls_info.tls_version
                network_info.tls_cipher = tls_info.tls_cipher
                network_info.cert_cn = tls_info.cert_cn
                network_info.cert_days_left = tls_info.cert_days_left
            except TLSInspectionError:
                # TLS inspection is non-fatal, continue without it
                pass

    except httpx.TimeoutException as exc:
        msg = f"Request timeout: {exc}"
        raise HTTPClientError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Request failed: {exc}"
        raise HTTPClientError(msg) from exc
    except HTTPClientError:
        raise
    except Exception as exc:
        msg = f"Unexpected error: {exc}"
        raise HTTPClientError(msg) from exc

    return timing, network_info, response_info


def _populate_tls_from_stream(
    response: httpx.Response,
    network_info: NetworkInfo,
) -> None:
    ssl_object = _extract_ssl_object(response)
    if ssl_object is None:
        return

    with suppress(AttributeError):  # pragma: no cover - defensive
        network_info.tls_version = network_info.tls_version or ssl_object.version()

    cipher_info = None
    with suppress(AttributeError):  # pragma: no cover - defensive
        cipher_info = ssl_object.cipher()
    if cipher_info:
        network_info.tls_cipher = network_info.tls_cipher or cipher_info[0]

    if isinstance(ssl_object, ssl.SSLSocket):
        try:
            cert_info = extract_certificate_info(ssl_object)
        except Exception:  # pragma: no cover - defensive  # noqa: BLE001
            cert_info = None
    else:
        cert_info = None
    if cert_info:
        network_info.cert_cn = network_info.cert_cn or cert_info.common_name
        network_info.cert_days_left = network_info.cert_days_left or cert_info.days_until_expiry


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
) -> ssl.SSLObject | ssl.SSLSocket | SSLInfoProvider | None:
    """Return the SSL object associated with the httpx response stream if available."""
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None

    getter = getattr(stream, "get_extra_info", None)
    if not callable(getter):
        return None

    try:
        ssl_candidate = getter("ssl_object")
    except Exception:  # pragma: no cover - defensive  # noqa: BLE001
        return None

    if isinstance(ssl_candidate, (ssl.SSLSocket, ssl.SSLObject, SSLInfoProvider)):
        return ssl_candidate
    return None
