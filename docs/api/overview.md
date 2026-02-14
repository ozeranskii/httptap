# API Overview

httptap provides a clean Python API for programmatic usage and extension. This page gives an overview of the main
components.

## Architecture

httptap is built around a modular architecture with clear interfaces:

```
┌─────────────────┐
│  CLI Interface  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTPTapAnalyzer│ ◄── Main entry point
└────────┬────────┘
         │
         ├─► DNS Resolver (Protocol)
         ├─► TLS Inspector (Protocol)
         ├─► Timing Collector (Protocol)
         ├─► Visualizer (Protocol)
         └─► Exporter (Protocol)
```

## Core Components

### HTTPTapAnalyzer

The main analyzer class that orchestrates HTTP request analysis.

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
```

### StepMetrics

Data model representing a single request/response cycle.

```python
from httptap.models import StepMetrics

step: StepMetrics
print(step.url)           # Request URL
print(step.timing)        # TimingMetrics object
print(step.network)       # NetworkInfo object
print(step.response)      # ResponseInfo object
```

### Timing Information

```python
step.timing.dns_ms        # DNS resolution time
step.timing.connect_ms    # TCP connection time
step.timing.tls_ms        # TLS handshake time
step.timing.ttfb_ms       # Time to first byte
step.timing.total_ms      # Total request time
step.timing.wait_ms       # Server processing time
step.timing.xfer_ms       # Body transfer time
step.timing.is_estimated  # Whether timing is estimated
```

### Network Information

```python
step.network.ip             # IP address (str | None)
step.network.ip_family      # IPv4 or IPv6 (str | None)
step.network.http_version   # HTTP protocol (str | None)
step.network.tls_version    # TLS protocol version (str | None)
step.network.tls_cipher     # Cipher suite (str | None)
step.network.cert_cn        # Certificate common name (str | None)
step.network.cert_days_left # Days until expiration (int | None)
step.network.tls_verified   # Whether TLS was verified (bool | None)
step.network.tls_custom_ca  # Custom CA bundle used (bool | None)
```

### Response Data

```python
step.response.status        # HTTP status code (int | None)
step.response.bytes         # Response body size (int)
step.response.content_type  # Content-Type header (str | None)
step.response.server        # Server header (str | None)
step.response.date          # Response date (datetime | None)
step.response.location      # Location header (str | None)
step.response.headers       # All headers dict
```

## Protocol Interfaces

httptap uses Protocol classes (PEP 544) for type-safe extensibility.

### DNSResolver

Interface for custom DNS resolution implementations.

```python
from httptap.interfaces import DNSResolver

class CustomResolver:
    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        """Resolve host to IP address.

        Returns:
            tuple[str, str, float]: (ip_address, family, duration_ms)
        """
        ...
```

### TLSInspector

Interface for TLS certificate and connection inspection.

```python
from httptap.interfaces import TLSInspector
from httptap.models import NetworkInfo

class CustomTLSInspector:
    def inspect(self, host: str, port: int, timeout: float) -> NetworkInfo:
        """Inspect TLS connection and certificate.

        Returns:
            NetworkInfo with TLS version, cipher, and certificate data.
        """
        ...
```

### TimingCollector

Interface for request timing implementations. A new instance is created for each request.

```python
from httptap.interfaces import TimingCollector
from httptap.models import TimingMetrics

class CustomTimingCollector:
    def mark_dns_start(self) -> None: ...
    def mark_dns_end(self) -> None: ...
    def mark_request_start(self) -> None: ...
    def mark_ttfb(self) -> None: ...
    def mark_request_end(self) -> None: ...
    def get_metrics(self) -> TimingMetrics: ...
```

### Visualizer

Interface for custom output visualization.

```python
from httptap.interfaces import Visualizer
from httptap.models import StepMetrics

class CustomVisualizer:
    def render(self, step: StepMetrics) -> None:
        """Render a single request step for display."""
        ...
```

### Exporter

Interface for custom data export formats.

```python
from httptap.interfaces import Exporter
from httptap.models import StepMetrics
from collections.abc import Sequence

class CustomExporter:
    def export(self, steps: Sequence[StepMetrics], initial_url: str, output_path: str) -> None:
        """Export request data to file."""
        ...
```

## Built-in Implementations

httptap provides default implementations of all protocols:

### SystemDNSResolver

Uses Python's `socket.getaddrinfo()` for DNS resolution.

```python
from httptap import SystemDNSResolver

resolver = SystemDNSResolver()
ip, family, duration = resolver.resolve("httpbin.io", 443, timeout=5.0)
```

### SocketTLSInspector

Uses Python's `ssl` module to inspect TLS connections.

```python
from httptap import SocketTLSInspector

inspector = SocketTLSInspector()
network_info = inspector.inspect("httpbin.io", 443, 5.0)
print(network_info.tls_version, network_info.tls_cipher)
```

### PerfCounterTimingCollector

Uses `time.perf_counter()` for precise timing.

```python
from httptap import PerfCounterTimingCollector

collector = PerfCounterTimingCollector()
collector.mark_dns_start()
# ... perform DNS ...
collector.mark_dns_end()
metrics = collector.get_metrics()
```

### WaterfallVisualizer

Uses Rich library for waterfall terminal output.

```python
from rich.console import Console
from httptap import WaterfallVisualizer

visualizer = WaterfallVisualizer(Console())
visualizer.render(step)
```

### JSONExporter

Exports request data to JSON format.

```python
from rich.console import Console
from httptap import JSONExporter

exporter = JSONExporter(Console())
exporter.export(steps, "https://httpbin.io", "output.json")
```

## Request Executor

For fully customized HTTP behavior, implement the `RequestExecutor` protocol.

```python
from httptap import RequestExecutor, RequestOptions, RequestOutcome

class CustomExecutor:
    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Perform an HTTP request based on provided options."""
        ...
```

## Type Hints

All public APIs are fully type-hinted for excellent IDE support.

```python
from httptap import HTTPTapAnalyzer
from httptap.models import StepMetrics

def analyze_api(url: str) -> list[StepMetrics]:
    """Analyze API endpoint and return steps."""
    analyzer: HTTPTapAnalyzer = HTTPTapAnalyzer()
    steps: list[StepMetrics] = analyzer.analyze_url(url)
    return steps
```

## Error Handling

httptap returns errors as part of `StepMetrics` rather than raising exceptions during analysis.

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://invalid-domain.example")

step = steps[0]
if step.has_error:
    print(f"Error: {step.error}")
else:
    print(f"Status: {step.response.status}")
```

---

## What's Next?

<div class="grid cards" markdown>

-   :material-code-json:{ .lg .middle } **[Core Components](core.md)**

    ---

    HTTPTapAnalyzer, data models, utilities

-   :material-puzzle:{ .lg .middle } **[Protocol Interfaces](interfaces.md)**

    ---

    Extend with custom implementations

-   :material-cog:{ .lg .middle } **[Advanced Usage](../usage/advanced.md)**

    ---

    Real-world examples and patterns

</div>
