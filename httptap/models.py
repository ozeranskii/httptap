"""Data models for HTTP request analysis.

This module contains immutable data structures used throughout the httptap
application to store and transfer metrics, timing information, and request/
response data.

All models use dataclasses with slots for memory efficiency and clear
structure. Models are designed to be serializable to JSON for export
and API integration.

Key Models:
    - TimingMetrics: Phase-by-phase request timing breakdown.
    - NetworkInfo: IP address, TLS version, cipher, certificate details.
    - ResponseInfo: HTTP status, headers, body size.
    - StepMetrics: Complete metrics for one request in a redirect chain.

The models follow immutability principles where possible, with explicit
mutation methods (like calculate_derived) clearly documented.

Examples:
    Creating and using metrics:
        >>> timing = TimingMetrics(dns_ms=12.5, connect_ms=45.0)
        >>> timing.calculate_derived()
        >>> print(timing.to_dict())
        {'dns_ms': 12.5, 'connect_ms': 45.0, ...}

"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .constants import HTTP_REDIRECT_MAX, HTTP_REDIRECT_MIN


@dataclass(slots=True)
class TimingMetrics:
    """Timing metrics for HTTP request phases.

    All timing values are in milliseconds.

    Attributes:
        dns_ms: DNS resolution time.
        connect_ms: TCP connection establishment time.
        tls_ms: TLS handshake time (0 for HTTP).
        ttfb_ms: Time to first byte (headers received).
        total_ms: Total request time from start to finish.
        wait_ms: Server processing time (derived metric).
        xfer_ms: Response body transfer time (derived metric).
        is_estimated: Whether connect/TLS timing was estimated vs measured.

    """

    dns_ms: float = 0.0
    connect_ms: float = 0.0
    tls_ms: float = 0.0
    ttfb_ms: float = 0.0
    total_ms: float = 0.0
    wait_ms: float = 0.0
    xfer_ms: float = 0.0
    is_estimated: bool = False

    def calculate_derived(self) -> None:
        """Calculate derived timing metrics.

        This method computes timing values that are derived from the raw
        measurements. It should be called after all raw timing values
        (dns_ms, connect_ms, tls_ms, ttfb_ms, total_ms) are populated.

        Computes:
            wait_ms: Time server spent processing the request before sending
                the first byte of the response. Calculated as:
                max(0, ttfb_ms - (dns_ms + connect_ms + tls_ms))

            xfer_ms: Time spent transferring the response body after headers
                were received. Calculated as:
                max(0, total_ms - ttfb_ms)

        Note:
            Both values are clamped to 0 to handle edge cases where timing
            measurements may have slight inconsistencies due to measurement
            precision or system clock adjustments.

        Examples:
            >>> timing = TimingMetrics(
            ...     dns_ms=10.0,
            ...     connect_ms=20.0,
            ...     tls_ms=50.0,
            ...     ttfb_ms=100.0,
            ...     total_ms=150.0
            ... )
            >>> timing.calculate_derived()
            >>> print(f"Wait: {timing.wait_ms}ms, Transfer: {timing.xfer_ms}ms")
            Wait: 20.0ms, Transfer: 50.0ms

        """
        self.wait_ms = max(
            0.0,
            self.ttfb_ms - (self.dns_ms + self.connect_ms + self.tls_ms),
        )
        self.xfer_ms = max(0.0, self.total_ms - self.ttfb_ms)

    def to_dict(self) -> dict[str, float | bool]:
        """Convert timing metrics to dictionary.

        Returns:
            Dictionary with all timing metrics.

        """
        return {
            "dns_ms": self.dns_ms,
            "connect_ms": self.connect_ms,
            "tls_ms": self.tls_ms,
            "ttfb_ms": self.ttfb_ms,
            "total_ms": self.total_ms,
            "wait_ms": self.wait_ms,
            "xfer_ms": self.xfer_ms,
            "is_estimated": self.is_estimated,
        }


@dataclass(slots=True)
class NetworkInfo:
    """Network and security information for a connection.

    Attributes:
        ip: Resolved IP address.
        ip_family: Address family label (e.g., 'IPv4' or 'IPv6').
        tls_version: TLS protocol version (e.g., 'TLSv1.3').
        tls_cipher: TLS cipher suite used.
        cert_cn: Certificate Common Name.
        cert_days_left: Days until certificate expiration.
        tls_verified: Whether TLS certificate verification was enforced.

    """

    ip: str | None = None
    ip_family: str | None = None
    tls_version: str | None = None
    tls_cipher: str | None = None
    cert_cn: str | None = None
    cert_days_left: int | None = None
    tls_verified: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert network info to dictionary.

        Returns:
            Dictionary with all network information.

        """
        return {
            "ip": self.ip,
            "ip_family": self.ip_family,
            "tls_version": self.tls_version,
            "tls_cipher": self.tls_cipher,
            "cert_cn": self.cert_cn,
            "cert_days_left": self.cert_days_left,
            "tls_verified": self.tls_verified,
        }


@dataclass(slots=True)
class ResponseInfo:
    """HTTP response information.

    Attributes:
        status: HTTP status code.
        bytes: Response body size in bytes.
        content_type: Content-Type header value.
        server: Server header value.
        date: Date header parsed as datetime.
        location: Location header for redirects.
        headers: Sanitized response headers (secrets masked).

    """

    status: int | None = None
    bytes: int = 0
    content_type: str | None = None
    server: str | None = None
    date: datetime | None = None
    location: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert response info to dictionary.

        Returns:
            Dictionary with all response information.

        """
        return {
            "status": self.status,
            "bytes": self.bytes,
            "content_type": self.content_type,
            "server": self.server,
            "date": self.date.isoformat() if self.date else None,
            "location": self.location,
            "headers": self.headers,
        }


@dataclass(slots=True)
class StepMetrics:
    """Complete metrics for a single HTTP request step.

    Represents all collected data for one request in the chain,
    including timing, network, response information, and any errors.

    Attributes:
        url: The URL that was requested.
        step_number: Step number in redirect chain (1-indexed).
        timing: Timing metrics.
        network: Network and security information.
        response: HTTP response information.
        error: Error message if request failed.
        note: Additional notes or context.
        proxied_via: Proxy URL used for this request, if any.
        request_method: HTTP method used (GET, POST, PUT, etc.).
        request_headers: Request headers (sanitized).
        request_body_bytes: Size of request body in bytes.

    """

    url: str = ""
    step_number: int = 1
    timing: TimingMetrics = field(default_factory=TimingMetrics)
    network: NetworkInfo = field(default_factory=NetworkInfo)
    response: ResponseInfo = field(default_factory=ResponseInfo)
    error: str | None = None
    note: str | None = None
    proxied_via: str | None = None
    request_method: str | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert step metrics to dictionary for JSON export.

        Returns:
            Dictionary containing all step information organized by category.

        """
        return {
            "url": self.url,
            "step_number": self.step_number,
            "request": {
                "method": self.request_method,
                "headers": self.request_headers,
                "body_bytes": self.request_body_bytes,
            },
            "timing": self.timing.to_dict(),
            "network": self.network.to_dict(),
            "response": self.response.to_dict(),
            "error": self.error,
            "note": self.note,
            "proxy": self.proxied_via,
        }

    @property
    def has_error(self) -> bool:
        """Check if this step encountered an error.

        Returns:
            True if error occurred, False otherwise.

        """
        return self.error is not None

    @property
    def is_redirect(self) -> bool:
        """Check if this step is a redirect response.

        Returns:
            True if status is 3xx and Location header present.

        """
        return (
            self.response.status is not None
            and HTTP_REDIRECT_MIN <= self.response.status <= HTTP_REDIRECT_MAX
            and self.response.location is not None
        )
