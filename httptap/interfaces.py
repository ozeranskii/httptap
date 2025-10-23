"""Common interface definitions for httptap collaborators.

Defining lightweight protocols keeps the codebase flexible while avoiding
runtime overhead from heavy abstractions. These protocols describe the
behavioural contracts required for extensibility so alternative implementations
can be injected without modifying core logic.

This module provides Protocol-based interfaces for:
    - Visualizers: Render HTTP analysis steps in various formats.
    - Exporters: Persist analysis results to files.
    - DNSResolvers: Resolve hostnames to IP addresses with timing.
    - TLSInspectors: Inspect TLS certificates and connection metadata.
    - TimingCollectors: Collect and measure request timing at each phase.

Using Protocol instead of ABC provides structural subtyping (duck typing with
type safety) without requiring explicit inheritance, making the codebase more
flexible and easier to extend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .models import NetworkInfo, StepMetrics, TimingMetrics


class Visualizer(Protocol):
    """Renderable component capable of visualising a single step.

    This protocol defines the interface for visualizers that can render
    HTTP request analysis steps in various formats (waterfall, ASCII, etc.).

    Examples:
        >>> class CustomVisualizer:
        ...     def render(self, step: StepMetrics) -> None:
        ...         print(f"Step {step.step_number}: {step.timing.total_ms}ms")

    """

    def render(self, step: StepMetrics) -> None:
        """Render a visualisation for the provided HTTP step.

        Args:
            step: Step metrics containing timing, network, and response data.

        Note:
            Implementations should handle errors gracefully and avoid raising
            exceptions to prevent disrupting the analysis output.

        """


class Exporter(Protocol):
    """Component responsible for exporting analysis output.

    This protocol defines the interface for exporters that can persist
    analysis results in various formats (JSON, CSV, HTML, etc.).

    Examples:
        >>> class CSVExporter:
        ...     def export(
        ...         self,
        ...         steps: Sequence[StepMetrics],
        ...         initial_url: str,
        ...         output_path: str,
        ...     ) -> None:
        ...         # Write CSV file
        ...         pass

    """

    def export(
        self,
        steps: Sequence[StepMetrics],
        initial_url: str,
        output_path: str,
    ) -> None:
        """Persist the collected steps using the chosen representation.

        Args:
            steps: Sequence of step metrics to export.
            initial_url: The initial URL that was analyzed.
            output_path: Path to output file where results should be written.

        Raises:
            IOError: If file cannot be written or path is invalid.

        Note:
            Implementations should create parent directories if they don't exist.

        """


class DNSResolver(Protocol):
    """Protocol for DNS resolution implementations.

    This protocol defines the interface for DNS resolvers that can translate
    hostnames to IP addresses with timing measurements.

    Examples:
        >>> class CustomDNSResolver:
        ...     def resolve(
        ...         self, host: str, port: int, timeout: float
        ...     ) -> tuple[str, str, float]:
        ...         # Custom DNS resolution logic
        ...         return "93.184.216.34", "IPv4", 12.5

    """

    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        """Resolve hostname to IP address with timing.

        Args:
            host: Hostname to resolve (e.g., "example.com").
            port: Port number for the connection.
            timeout: Maximum time to wait for DNS resolution in seconds.

        Returns:
            Tuple of (ip_address, ip_family, resolution_time_ms).
            ip_family should be one of: 'IPv4', 'IPv6', or 'AF_<num>'.

        Raises:
            Exception: If hostname cannot be resolved. Implementations should
                define specific exception types for DNS failures.

        Note:
            Implementations should try multiple resolution methods
            (e.g., system resolver, custom nameservers) before failing.

        """


class TLSInspector(Protocol):
    """Protocol for TLS/SSL inspection implementations.

    This protocol defines the interface for inspecting TLS connections
    to extract certificate information and connection metadata.

    Examples:
        >>> class CustomTLSInspector:
        ...     def inspect(
        ...         self,
        ...         host: str,
        ...         port: int,
        ...         timeout: float,
        ...     ) -> NetworkInfo:
        ...         # Custom TLS inspection logic
        ...         return NetworkInfo(tls_version="TLSv1.3")

    """

    def inspect(
        self,
        host: str,
        port: int,
        timeout: float,
    ) -> NetworkInfo:
        """Inspect TLS connection and extract metadata.

        Args:
            host: Hostname to connect to.
            port: Port number (typically 443 for HTTPS).
            timeout: Connection timeout in seconds.

        Returns:
            NetworkInfo object with TLS version, cipher, and certificate data.

        Note:
            Implementations should handle connection failures gracefully
            and return partial data when possible (e.g., TLS version without
            certificate details if handshake succeeds but cert extraction fails).

        """


class TimingCollector(Protocol):
    """Protocol for collecting timing metrics during HTTP requests.

    This protocol defines the interface for components that measure and
    track timing information throughout request execution phases.

    Examples:
        >>> class CustomTimingCollector:
        ...     def mark_dns_start(self) -> None:
        ...         self._dns_start = time.time()
        ...     def get_metrics(self) -> TimingMetrics:
        ...         return TimingMetrics(dns_ms=self._dns_ms)

    """

    def mark_dns_start(self) -> None:
        """Mark the start of DNS resolution phase."""

    def mark_dns_end(self) -> None:
        """Mark the end of DNS resolution phase."""

    def mark_request_start(self) -> None:
        """Mark the start of HTTP request phase."""

    def mark_ttfb(self) -> None:
        """Mark the time to first byte (headers received)."""

    def mark_request_end(self) -> None:
        """Mark the end of HTTP request (body fully received)."""

    def get_metrics(self) -> TimingMetrics:
        """Calculate and return timing metrics.

        Returns:
            TimingMetrics with all phase durations calculated.

        Note:
            Should calculate derived metrics (wait_ms, xfer_ms) automatically.

        """
