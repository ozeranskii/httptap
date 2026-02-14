# Protocol Interfaces

httptap uses Protocol classes (PEP 544) for structural subtyping. This allows you to provide custom implementations
without inheriting from base classes.

## Why Protocols?

Protocols provide:

- **Duck typing with type safety** - Type checkers verify your implementation
- **No inheritance required** - Just implement the methods
- **Clear contracts** - Explicit interface definitions
- **Easy testing** - Simple to mock and substitute

## DNSResolver

Interface for DNS resolution implementations.

### Protocol Definition

```python
from typing import Protocol

class DNSResolver(Protocol):
    def resolve(
        self,
        host: str,
        port: int,
        timeout: float
    ) -> tuple[str, str, float]:
        """Resolve hostname to IP address.

        Args:
            host: Hostname to resolve
            port: Port number (may influence resolution)
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (ip_address, family, duration_ms) where:
            - ip_address: Resolved IP address string
            - family: "IPv4" or "IPv6"
            - duration_ms: Resolution time in milliseconds

        Raises:
            Exception: If resolution fails
        """
        ...
```

httptap dials the resolved IP address directly while keeping the original hostname for the `Host` header and TLS SNI. IPv6 addresses are bracketed automatically; implementations only need to return a valid IP/family tuple.

### Example Implementation

```python
import socket
import time

class CustomDNSResolver:
    def resolve(self, host: str, port: int, timeout: float):
        start = time.perf_counter()

        try:
            # Use getaddrinfo for resolution
            addr_info = socket.getaddrinfo(
                host, port,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM
            )
            ip_address = addr_info[0][4][0]

            # Determine IP family
            family = "IPv6" if ":" in ip_address else "IPv4"

            duration_ms = (time.perf_counter() - start) * 1000
            return ip_address, family, duration_ms

        except socket.gaierror as e:
            raise Exception(f"DNS resolution failed: {e}")

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(dns_resolver=CustomDNSResolver())
```

## TLSInspector

Interface for TLS connection and certificate inspection.

### Protocol Definition

```python
from typing import Protocol
from httptap.models import NetworkInfo

class TLSInspector(Protocol):
    def inspect(
        self,
        host: str,
        port: int,
        timeout: float
    ) -> NetworkInfo:
        """Inspect TLS connection and certificate.

        Args:
            host: Hostname to connect to
            port: Port number
            timeout: Maximum time to wait in seconds

        Returns:
            NetworkInfo object with TLS version, cipher, and certificate data.

        Raises:
            Exception: If inspection fails
        """
        ...
```

### Example Implementation

```python
import ssl
import socket
import time
from datetime import datetime
from httptap.models import NetworkInfo

class CustomTLSInspector:
    def inspect(self, host: str, port: int, timeout: float) -> NetworkInfo:
        start = time.perf_counter()

        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                version = ssock.version()
                cipher = ssock.cipher()[0]
                cert = ssock.getpeercert()
                cert_cn = dict(x[0] for x in cert["subject"])["commonName"]
                not_after = datetime.strptime(
                    cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
                )
                days_left = (not_after - datetime.now()).days

        return NetworkInfo(
            tls_version=version,
            tls_cipher=cipher,
            cert_cn=cert_cn,
            cert_days_left=days_left,
        )

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(tls_inspector=CustomTLSInspector())
```

## TimingCollector

Interface for HTTP request timing implementations. A new collector instance is created for each request in the chain.

### Protocol Definition

```python
from typing import Protocol
from httptap.models import TimingMetrics

class TimingCollector(Protocol):
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
        """
        ...
```

### Example Implementation

```python
import time
from httptap.models import TimingMetrics

class CustomTimingCollector:
    """Timing collector using perf_counter."""

    def __init__(self) -> None:
        self._dns_start = 0.0
        self._dns_end = 0.0
        self._request_start = 0.0
        self._ttfb = 0.0
        self._request_end = 0.0

    def mark_dns_start(self) -> None:
        self._dns_start = time.perf_counter()

    def mark_dns_end(self) -> None:
        self._dns_end = time.perf_counter()

    def mark_request_start(self) -> None:
        self._request_start = time.perf_counter()

    def mark_ttfb(self) -> None:
        self._ttfb = time.perf_counter()

    def mark_request_end(self) -> None:
        self._request_end = time.perf_counter()

    def get_metrics(self) -> TimingMetrics:
        dns_ms = (self._dns_end - self._dns_start) * 1000
        ttfb_ms = (self._ttfb - self._dns_start) * 1000
        total_ms = (self._request_end - self._dns_start) * 1000
        metrics = TimingMetrics(dns_ms=dns_ms, ttfb_ms=ttfb_ms, total_ms=total_ms)
        metrics.calculate_derived()
        return metrics

# Usage: pass the class (not an instance) as factory
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(timing_collector_factory=CustomTimingCollector)
```

## Visualizer

Interface for custom output visualization.

### Protocol Definition

```python
from typing import Protocol
from httptap.models import StepMetrics

class Visualizer(Protocol):
    def render(self, step: StepMetrics) -> None:
        """Render a single request step for display.

        Args:
            step: Step metrics containing timing, network, and response data.
        """
        ...
```

### Example Implementation

```python
from httptap.models import StepMetrics

class SimpleVisualizer:
    """Simple text-based visualizer."""

    def render(self, step: StepMetrics) -> None:
        print(f"Step {step.step_number}: {step.url}")
        print(f"  Status: {step.response.status}")
        print(f"  Timing:")
        print(f"    DNS:     {step.timing.dns_ms:8.2f}ms")
        print(f"    Connect: {step.timing.connect_ms:8.2f}ms")
        print(f"    TLS:     {step.timing.tls_ms:8.2f}ms")
        print(f"    TTFB:    {step.timing.ttfb_ms:8.2f}ms")
        print(f"    Total:   {step.timing.total_ms:8.2f}ms")
        print()

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

visualizer = SimpleVisualizer()
for step in steps:
    visualizer.render(step)
```

## Exporter

Interface for custom data export formats.

### Protocol Definition

```python
from typing import Protocol
from collections.abc import Sequence
from httptap.models import StepMetrics

class Exporter(Protocol):
    def export(
        self,
        steps: Sequence[StepMetrics],
        initial_url: str,
        output_path: str,
    ) -> None:
        """Export request data to file.

        Args:
            steps: Sequence of request steps to export
            initial_url: The initial URL that was analyzed
            output_path: Path to output file

        Raises:
            IOError: If file cannot be written
        """
        ...
```

### Example Implementation

```python
import yaml
from collections.abc import Sequence
from httptap.models import StepMetrics

class YAMLExporter:
    """Export request data to YAML format."""

    def export(self, steps: Sequence[StepMetrics], initial_url: str, output_path: str) -> None:
        data = {
            "initial_url": initial_url,
            "total_steps": len(steps),
            "steps": [],
        }

        for step in steps:
            step_data = {
                "url": step.url,
                "status": step.response.status,
                "timing": {
                    "dns_ms": step.timing.dns_ms,
                    "connect_ms": step.timing.connect_ms,
                    "tls_ms": step.timing.tls_ms,
                    "ttfb_ms": step.timing.ttfb_ms,
                    "total_ms": step.timing.total_ms,
                },
                "network": {
                    "ip": step.network.ip,
                    "family": step.network.ip_family,
                    "http_version": step.network.http_version,
                    "tls_version": step.network.tls_version,
                },
            }
            data["steps"].append(step_data)

        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

exporter = YAMLExporter()
exporter.export(steps, "https://httpbin.io", "output.yaml")
```

## RequestExecutor

Interface for custom HTTP request execution.

### Protocol Definition

```python
from typing import Protocol, runtime_checkable
from httptap.request_executor import RequestOptions, RequestOutcome

@runtime_checkable
class RequestExecutor(Protocol):
    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Perform an HTTP request based on provided options."""
        ...
```

## Type Checking

All protocols are fully type-hinted and work with mypy, pyright, and other type checkers.

```python
from typing import reveal_type
from httptap.interfaces import DNSResolver

class MyResolver:
    def resolve(self, host: str, port: int, timeout: float):
        return "192.168.1.1", "IPv4", 10.5

# Type checker will verify MyResolver implements the protocol
resolver: DNSResolver = MyResolver()
reveal_type(resolver)  # Type: DNSResolver
```

## Next Steps

- See [core components documentation](core.md)
- Review [advanced usage examples](../usage/advanced.md)
- Check [contributing guidelines](../development/contributing.md) to add new protocols
