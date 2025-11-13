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
         ├─► Timing Provider (Protocol)
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

### RequestStep

Data model representing a single request/response cycle.

```python
from httptap.models import RequestStep

step: RequestStep
print(step.url)           # Request URL
print(step.timing)        # Timing information
print(step.network)       # Network details
print(step.response)      # Response data
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
step.network.ip             # IP address
step.network.ip_family      # IPv4 or IPv6
step.network.http_version   # HTTP protocol (HTTP/1.1, HTTP/2.0, ...)
step.network.tls_version    # TLS protocol version
step.network.tls_cipher     # Cipher suite
step.network.cert_cn        # Certificate common name
step.network.cert_days_left # Days until expiration
```

### Response Data

```python
step.response.status        # HTTP status code
step.response.bytes         # Response body size
step.response.content_type  # Content-Type header
step.response.server        # Server header
step.response.date          # Response date
step.response.location      # Location header (redirects)
step.response.headers       # All headers dict
```

## Protocol Interfaces

httptap uses Protocol classes (PEP 544) for type-safe extensibility.

### DNSResolverProtocol

Interface for custom DNS resolution implementations.

```python
from httptap.interfaces import DNSResolverProtocol

class CustomResolver:
    def resolve(self, host: str, port: int, timeout: float):
        """Resolve host to IP address.

        Returns:
            tuple[str, str, float]: (ip_address, family, duration_ms)
        """
        pass
```

### TLSInspectorProtocol

Interface for TLS certificate and connection inspection.

```python
from httptap.interfaces import TLSInspectorProtocol

class CustomTLSInspector:
    def inspect(self, host: str, port: int, timeout: float):
        """Inspect TLS connection and certificate.

        Returns:
            tuple: (tls_version, cipher, cert_cn, days_left, duration_ms)
        """
        pass
```

### TimingProviderProtocol

Interface for request timing implementations.

```python
from httptap.interfaces import TimingProviderProtocol

class CustomTimingProvider:
    def time_request(self, url: str, headers: dict):
        """Time HTTP request execution.

        Returns:
            RequestStep: Complete step with timing information
        """
        pass
```

### VisualizerProtocol

Interface for custom output visualization.

```python
from httptap.interfaces import VisualizerProtocol
from httptap.models import RequestStep

class CustomVisualizer:
    def render(self, steps: list[RequestStep], *, follow: bool = False):
        """Render request steps for display."""
        pass
```

### ExporterProtocol

Interface for custom data export formats.

```python
from httptap.interfaces import ExporterProtocol
from httptap.models import RequestStep

class CustomExporter:
    def export(self, steps: list[RequestStep], output_path: str):
        """Export request data to file."""
        pass
```

## Built-in Implementations

httptap provides default implementations of all protocols:

### SystemDNSResolver

Uses Python's `socket.getaddrinfo()` for DNS resolution.

```python
from httptap.implementations import SystemDNSResolver

resolver = SystemDNSResolver()
ip, family, duration = resolver.resolve("httpbin.io", 443, timeout=5.0)
```

### SocketTLSInspector

Uses Python's `ssl` module to inspect TLS connections.

```python
from httptap.implementations import SocketTLSInspector

inspector = SocketTLSInspector()
version, cipher, cn, days, duration = inspector.inspect("httpbin.io", 443, 5.0)
```

### HTTPCoreTimingProvider

Uses httpcore trace hooks for precise timing.

```python
from httptap.implementations import HTTPCoreTimingProvider

provider = HTTPCoreTimingProvider()
step = provider.time_request("https://httpbin.io", headers={})
```

### WaterfallVisualizer

Uses Rich library for beautiful terminal output.

```python
from httptap import WaterfallVisualizer

visualizer = WaterfallVisualizer()
visualizer.render(steps)
```

### JSONExporter

Exports request data to JSON format.

```python
from httptap import JSONExporter

exporter = JSONExporter()
exporter.export(steps, "output.json")
```

## Type Hints

All public APIs are fully type-hinted for excellent IDE support.

```python
from httptap import HTTPTapAnalyzer
from httptap.models import RequestStep

def analyze_api(url: str) -> list[RequestStep]:
    """Analyze API endpoint and return steps."""
    analyzer: HTTPTapAnalyzer = HTTPTapAnalyzer()
    steps: list[RequestStep] = analyzer.analyze_url(url)
    return steps
```

## Error Handling

httptap raises standard Python exceptions:

- `ValueError` - Invalid input parameters
- `TimeoutError` - Request timeout exceeded
- `ConnectionError` - Network connection failed
- `Exception` - General errors with descriptive messages

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()

try:
    steps = analyzer.analyze_url("https://invalid-domain.com")
except TimeoutError:
    print("Request timed out")
except ConnectionError:
    print("Connection failed")
except Exception as e:
    print(f"Error: {e}")
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
