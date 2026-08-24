"""Adapters and data structures for executing HTTP requests.

This module provides a clean separation between high-level analysis logic and
low-level request execution. It exposes a declarative RequestOptions object,
an outcome wrapper, and a default RequestExecutor implementation that uses
the built-in HTTP client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from httpx._types import ProxyTypes

    from .models import NetworkInfo, ResponseInfo, TimingMetrics
else:  # pragma: no cover - typing helper
    ProxyTypes = object  # type: ignore[assignment]

from .constants import HTTPMethod
from .http_client import make_request

if TYPE_CHECKING:
    from .interfaces import DNSResolver, TimingCollector, TLSInspector


@dataclass(slots=True)
class RequestOptions:
    """Aggregates all parameters required to perform a single HTTP request.

    Attributes:
        url: Target URL to request. Must be a valid HTTP/HTTPS URL.
        timeout: Request timeout in seconds.
        method: HTTP method to use for the request.
        content: Optional request body as bytes.
        http2: Whether to enable HTTP/2 support.
        verify_ssl: Whether to verify TLS certificates.
        ca_bundle_path: Path to a custom CA certificate bundle (PEM format).
            Only used when verify_ssl is True. If None, the system CA bundle
            is used.
        dns_resolver: Custom DNS resolver implementation. If None, the executor
            uses its default resolver.
        tls_inspector: Custom TLS inspector implementation. If None, the executor
            uses its default inspector.
        timing_collector: Timing collector instance used to measure request
            phases. If None, no phase timing is collected for this request.
        force_new_connection: Whether to force a fresh connection instead of
            reusing a pooled one, ensuring per-request timing is accurate.
        headers: Optional mapping of request headers to send.
        proxy: Optional proxy URL (http/https/socks5/socks5h) applied to the
            request.
        noproxy: When True, ignore proxy environment variables and connect
            directly.
    """

    url: str
    timeout: float
    method: HTTPMethod = HTTPMethod.GET
    content: bytes | None = None
    http2: bool = True
    verify_ssl: bool = True
    ca_bundle_path: str | None = None
    dns_resolver: DNSResolver | None = None
    tls_inspector: TLSInspector | None = None
    timing_collector: TimingCollector | None = None
    force_new_connection: bool = True
    headers: Mapping[str, str] | None = None
    proxy: ProxyTypes | None = None
    noproxy: bool = False


@dataclass(slots=True)
class RequestOutcome:
    """Wraps the collected timing, network, and response objects.

    Attributes:
        timing: Timing metrics gathered for the request phases.
        network: Network and TLS/certificate information for the connection.
        response: HTTP response metadata (status, headers, body size).
    """

    timing: TimingMetrics
    network: NetworkInfo
    response: ResponseInfo


@runtime_checkable
class RequestExecutor(Protocol):
    """Protocol describing modern request executors used by the analyzer.

    Implementations perform a single HTTP request described by a
    :class:`RequestOptions` instance and return the collected metrics as a
    :class:`RequestOutcome`. This lets the analyzer delegate the actual
    transport work to interchangeable backends.

    Examples:
        >>> class CustomExecutor:
        ...     def execute(self, options: RequestOptions) -> RequestOutcome:
        ...         ...  # perform the request and collect metrics
    """

    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Perform an HTTP request based on the provided options.

        Args:
            options: Fully populated request parameters, including URL,
                timeout, method, and any injected collaborators.

        Returns:
            A RequestOutcome bundling the timing, network, and response data.

        Raises:
            httptap.http_client.HTTPClientError: If the request cannot be
                completed. Implementations should surface transport failures
                using this error type so the analyzer can record partial data.
        """


class HTTPClientRequestExecutor:
    """RequestExecutor that delegates to the built-in HTTP client.

    This is the default executor used by :class:`~httptap.analyzer.HTTPTapAnalyzer`.
    It forwards each request to :func:`httptap.http_client.make_request`, which
    instruments DNS, connection, TLS, and transfer timing.
    """

    __slots__ = ()

    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Perform an HTTP request using the default client.

        Args:
            options: Fully populated request parameters.

        Returns:
            A RequestOutcome bundling the timing, network, and response data.

        Raises:
            httptap.http_client.HTTPClientError: If the underlying HTTP request
                fails.
        """
        timing, network, response = make_request(
            options.url,
            options.timeout,
            method=options.method,
            content=options.content,
            http2=options.http2,
            verify_ssl=options.verify_ssl,
            ca_bundle_path=options.ca_bundle_path,
            proxy=options.proxy,
            noproxy=options.noproxy,
            dns_resolver=options.dns_resolver,
            tls_inspector=options.tls_inspector,
            timing_collector=options.timing_collector,
            force_new_connection=options.force_new_connection,
            headers=options.headers,
        )
        return RequestOutcome(timing=timing, network=network, response=response)
