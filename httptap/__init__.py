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

from ._pkgmeta import get_package_info
from .analyzer import HTTPTapAnalyzer
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
from .request_executor import CallableRequestExecutor, RequestExecutor, RequestOptions, RequestOutcome
from .visualizer import WaterfallVisualizer

_package_info = get_package_info()

__version__ = _package_info.version
__author__ = _package_info.author
__license__ = _package_info.license

__all__ = [
    "CallableRequestExecutor",
    "DNSResolutionError",
    "DNSResolver",
    "Exporter",
    "HTTPTapAnalyzer",
    "JSONExporter",
    "NetworkInfo",
    "OutputRenderer",
    "PerfCounterTimingCollector",
    "RequestExecutor",
    "RequestOptions",
    "RequestOutcome",
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
