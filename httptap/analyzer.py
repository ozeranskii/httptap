"""Main HTTP request analyzer orchestration.

This module coordinates the analysis of HTTP requests, handling redirects,
collecting metrics, and managing the overall request flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from urllib.parse import urljoin

from .constants import DEFAULT_TIMEOUT_SECONDS
from .http_client import HTTPClientError, make_request
from .models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .interfaces import DNSResolver, TimingCollector, TLSInspector


class RequestExecutor(Protocol):
    """Protocol for HTTP request executors.

    Defines the interface for functions that execute HTTP requests and return
    comprehensive timing, network, and response metrics.

    Implementations should accept optional Protocol dependencies for DNS resolution,
    TLS inspection, and timing collection to enable dependency injection and testing.
    """

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
        """Execute HTTP request and collect metrics.

        Args:
            url: Target URL to request.
            timeout: Request timeout in seconds.
            http2: Whether to enable HTTP/2 support.
            http2: Whether to enable HTTP/2 support.
            dns_resolver: Custom DNS resolver implementation. Defaults to built-in.
            tls_inspector: Custom TLS inspector implementation. Defaults to built-in.
            timing_collector: Custom timing collector instance. Defaults to built-in.
            force_new_connection: Force new connection for accurate timing.
                Defaults to True.
            headers: Optional HTTP headers to include with the request.

        Returns:
            Tuple of (timing_metrics, network_info, response_info).

        Raises:
            HTTPClientError: If request fails.

        """
        ...


class HTTPTapAnalyzer:
    """Orchestrates HTTP request analysis with redirect following.

    This class manages the high-level flow of analyzing HTTP requests,
    including following redirect chains and collecting metrics at each step.

    Attributes:
        follow_redirects: Whether to follow HTTP redirects.
        timeout: Request timeout in seconds.
        http2: Whether to enable HTTP/2 support.
        max_redirects: Maximum number of redirects to follow.

    """

    __slots__ = (
        "_dns_resolver",
        "_request",
        "_timing_collector",
        "_tls_inspector",
        "follow_redirects",
        "http2",
        "max_redirects",
        "timeout",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        follow_redirects: bool = False,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http2: bool = True,
        max_redirects: int = 10,
        request_executor: RequestExecutor = make_request,
        dns_resolver: DNSResolver | None = None,
        tls_inspector: TLSInspector | None = None,
        timing_collector_factory: type[TimingCollector] | None = None,
    ) -> None:
        """Initialize HTTP analyzer.

        Args:
            follow_redirects: Whether to follow 3xx redirects.
            timeout: Request timeout in seconds.
            http2: Enable HTTP/2 support.
            max_redirects: Maximum number of redirects to follow.
            request_executor: Callable performing the HTTP request and returning
                timing, network, and response information. Defaults to the
                built-in httpx implementation.
            dns_resolver: Custom DNS resolver implementation. If None, make_request
                will use its default (SystemDNSResolver).
            tls_inspector: Custom TLS inspector implementation. If None, make_request
                will use its default (SocketTLSInspector).
            timing_collector_factory: Factory class for creating timing collectors.
                If None, make_request will use its default (PerfCounterTimingCollector).
                Note: This should be a class, not an instance, as a new collector
                is created for each request.

        Note:
            The request_executor parameter accepts any callable matching the
            RequestExecutor protocol signature. The Protocol dependencies
            (dns_resolver, tls_inspector, timing_collector_factory) are passed
            through to the request_executor if it supports them.

        """
        self.follow_redirects = follow_redirects
        self.timeout = timeout
        self.http2 = http2
        self.max_redirects = max_redirects
        self._request = request_executor
        self._dns_resolver = dns_resolver
        self._tls_inspector = tls_inspector
        self._timing_collector = timing_collector_factory

    def analyze_url(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[StepMetrics]:
        """Analyze URL with optional redirect following.

        Performs HTTP request(s) and collects comprehensive metrics.
        If follow_redirects is enabled and server returns 3xx with Location,
        continues following redirects up to max_redirects.

        Args:
            url: Initial URL to analyze. Must be valid HTTP/HTTPS URL.
            headers: Optional mapping of request headers applied to every step.

        Returns:
            List of StepMetrics, one per request in the chain. Each step contains
            timing, network, and response information. Returns at least one step
            even if request fails.

        Examples:
            Basic usage without redirects:
                >>> analyzer = HTTPTapAnalyzer()
                >>> steps = analyzer.analyze_url("https://example.com")
                >>> print(f"Total time: {steps[0].timing.total_ms}ms")
                Total time: 234.5ms

            Following redirect chain:
                >>> analyzer = HTTPTapAnalyzer(follow_redirects=True)
                >>> steps = analyzer.analyze_url("http://example.com")
                >>> for i, step in enumerate(steps, 1):
                ...     print(f"Step {i}: {step.response.status}")
                Step 1: 301
                Step 2: 200

        """
        steps: list[StepMetrics] = []
        current_url = url
        redirect_count = 0

        while redirect_count <= self.max_redirects:
            step_number = len(steps) + 1
            step = self._analyze_single_request(
                current_url,
                step_number,
                headers=headers,
            )
            steps.append(step)

            # Check if we should follow redirect
            if not self.follow_redirects:
                break

            if step.has_error:
                # Stop on error
                break

            if step.is_redirect:
                # Follow redirect
                next_url = step.response.location
                if next_url:
                    # Handle relative URLs
                    current_url = urljoin(current_url, next_url)
                    redirect_count += 1
                else:
                    # No Location header despite 3xx status
                    break
            else:
                # Not a redirect, we're done
                break

        return steps

    def _analyze_single_request(
        self,
        url: str,
        step_number: int,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> StepMetrics:
        """Analyze a single HTTP request.

        Args:
            url: URL to request.
            step_number: Step number in redirect chain (1-indexed).
            headers: Optional request headers for this step.

        Returns:
            StepMetrics with collected data. If request fails, error field
            will be populated, but step is still returned with partial data.

        Note:
            This method catches all exceptions and converts them to StepMetrics
            with error information, ensuring the analysis chain can continue.

        """
        step = StepMetrics(url=url, step_number=step_number)

        try:
            # Create timing collector instance if factory provided
            timing_collector = self._timing_collector() if self._timing_collector else None

            # Make request and collect metrics with injected dependencies
            timing, network, response = self._request(
                url,
                self.timeout,
                http2=self.http2,
                dns_resolver=self._dns_resolver,
                tls_inspector=self._tls_inspector,
                timing_collector=timing_collector,
                force_new_connection=True,
                headers=headers,
            )

            # Populate step metrics
            step.timing = timing
            step.network = network
            step.response = response

        except HTTPClientError as e:
            # Request failed, but we have partial data
            step.error = str(e)
            step.note = f"Step {step_number}: Request failed"

        except Exception as exc:  # noqa: BLE001
            # Unexpected error
            step.error = str(exc)
            step.note = f"Step {step_number}: Unexpected error"

        return step
