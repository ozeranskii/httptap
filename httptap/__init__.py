"""HTTP request visualizer (DNS → TCP → TLS → HTTP).

httptap is a command-line tool that provides detailed visibility into
HTTP request execution, breaking down DNS resolution, TCP connection,
TLS handshake, server wait, and body transfer timings.

Examples:
    $ httptap https://example.com
    $ httptap --follow --json output.json https://example.com

Modules:
    analyzer: Main orchestration for HTTP request analysis.
    cli: Command-line interface and argument parsing.
    exporter: Data export functionality (JSON).
    formatters: Output formatting utilities.
    http_client: HTTP client with detailed timing instrumentation.
    implementations: Concrete implementations of Protocol interfaces.
    interfaces: Protocol definitions for extensibility.
    models: Data models for metrics and request/response information.
    render: Output rendering orchestration.
    tls_inspector: TLS certificate inspection.
    utils: Helper utilities for common operations.
    visualizer: Waterfall timeline visualization.

"""

from ._pkgmeta import package_author, package_license, package_version

__version__ = package_version()
__author__ = package_author()
__license__ = package_license()

from .analyzer import HTTPTapAnalyzer, RequestExecutor
from .exporter import JSONExporter
from .implementations import (
    DNSResolutionError,
    PerfCounterTimingCollector,
    SocketTLSInspector,
    SystemDNSResolver,
    TLSInspectionError,
)
from .interfaces import DNSResolver, Exporter, TimingCollector, TLSInspector, Visualizer
from .models import (
    NetworkInfo,
    ResponseInfo,
    StepMetrics,
    TimingMetrics,
)
from .render import OutputRenderer
from .visualizer import WaterfallVisualizer

__all__ = [
    "DNSResolutionError",
    "DNSResolver",
    "Exporter",
    "HTTPTapAnalyzer",
    "JSONExporter",
    "NetworkInfo",
    "OutputRenderer",
    "PerfCounterTimingCollector",
    "RequestExecutor",
    "ResponseInfo",
    "SocketTLSInspector",
    "StepMetrics",
    "SystemDNSResolver",
    "TLSInspectionError",
    "TLSInspector",
    "TimingCollector",
    "TimingMetrics",
    "Visualizer",
    "WaterfallVisualizer",
]
