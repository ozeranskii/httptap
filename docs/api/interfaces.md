# Protocol Interfaces

httptap uses Protocol classes (PEP 544) for structural subtyping. This allows you to provide custom implementations
without inheriting from base classes.

## Why Protocols?

Protocols provide:

- **Duck typing with type safety** - Type checkers verify your implementation
- **No inheritance required** - Just implement the methods
- **Clear contracts** - Explicit interface definitions
- **Easy testing** - Simple to mock and substitute

## DNSResolverProtocol

Interface for DNS resolution implementations.

### Protocol Definition

```python
from typing import Protocol

class DNSResolverProtocol(Protocol):
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

## TLSInspectorProtocol

Interface for TLS connection and certificate inspection.

### Protocol Definition

```python
from typing import Protocol

class TLSInspectorProtocol(Protocol):
    def inspect(
        self,
        host: str,
        port: int,
        timeout: float
    ) -> tuple[str, str, str, int, float]:
        """Inspect TLS connection and certificate.

        Args:
            host: Hostname to connect to
            port: Port number
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (version, cipher, cert_cn, days_left, duration_ms) where:
            - version: TLS protocol version (e.g., "TLSv1.3")
            - cipher: Cipher suite name
            - cert_cn: Certificate common name
            - days_left: Days until certificate expires
            - duration_ms: Inspection time in milliseconds

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

class CustomTLSInspector:
    def inspect(self, host: str, port: int, timeout: float):
        start = time.perf_counter()

        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # Get TLS version
                    version = ssock.version()

                    # Get cipher suite
                    cipher = ssock.cipher()[0]

                    # Get certificate info
                    cert = ssock.getpeercert()
                    cert_cn = dict(x[0] for x in cert['subject'])['commonName']

                    # Calculate days until expiry
                    not_after = datetime.strptime(
                        cert['notAfter'],
                        '%b %d %H:%M:%S %Y %Z'
                    )
                    days_left = (not_after - datetime.now()).days

                    duration_ms = (time.perf_counter() - start) * 1000
                    return version, cipher, cert_cn, days_left, duration_ms

        except Exception as e:
            raise Exception(f"TLS inspection failed: {e}")

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(tls_inspector=CustomTLSInspector())
```

## TimingProviderProtocol

Interface for HTTP request timing implementations.

### Protocol Definition

```python
from typing import Protocol
from httptap.models import RequestStep

class TimingProviderProtocol(Protocol):
    def time_request(
        self,
        url: str,
        headers: dict[str, str] | None = None
    ) -> RequestStep:
        """Execute HTTP request and capture timing.

        Args:
            url: URL to request
            headers: Optional custom headers

        Returns:
            RequestStep with complete timing and response information

        Raises:
            Exception: If request fails
        """
        ...
```

### Example Implementation

```python
import httpx
import time
from httptap.models import RequestStep, TimingInfo, NetworkInfo, ResponseInfo

class CustomTimingProvider:
    def time_request(self, url: str, headers: dict | None = None):
        start_total = time.perf_counter()

        # Make request
        with httpx.Client() as client:
            response = client.get(url, headers=headers or {}, follow_redirects=False)

        total_ms = (time.perf_counter() - start_total) * 1000

        # Build timing info (simplified)
        timing = TimingInfo(
            dns_ms=0.0,
            connect_ms=0.0,
            tls_ms=0.0,
            ttfb_ms=total_ms,
            total_ms=total_ms,
            wait_ms=0.0,
            xfer_ms=0.0,
            is_estimated=True
        )

        # Build network info (simplified)
        network = NetworkInfo(
            ip="",
            ip_family="",
            http_version="",
            tls_version="",
            tls_cipher="",
            cert_cn="",
            cert_days_left=0
        )

        # Build response info
        response_info = ResponseInfo(
            status=response.status_code,
            bytes=len(response.content),
            content_type=response.headers.get("content-type"),
            server=response.headers.get("server"),
            date=response.headers.get("date"),
            location=response.headers.get("location"),
            headers=dict(response.headers)
        )

        return RequestStep(
            url=url,
            step_number=1,
            timing=timing,
            network=network,
            response=response_info,
            error=None,
            note=None
        )

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(timing_provider=CustomTimingProvider())
```

## VisualizerProtocol

Interface for custom output visualization.

### Protocol Definition

```python
from typing import Protocol
from httptap.models import RequestStep

class VisualizerProtocol(Protocol):
    def render(
        self,
        steps: list[RequestStep],
        *,
        follow: bool = False
    ) -> None:
        """Render request steps for display.

        Args:
            steps: List of request steps to visualize
            follow: Whether steps are from redirect chain

        Returns:
            None (output to console/stdout)
        """
        ...
```

### Example Implementation

```python
from httptap.models import RequestStep

class SimpleVisualizer:
    """Simple text-based visualizer."""

    def render(self, steps: list[RequestStep], *, follow: bool = False):
        print(f"\nAnalyzed {len(steps)} step(s):\n")

        for step in steps:
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
analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

visualizer = SimpleVisualizer()
visualizer.render(steps)
```

## ExporterProtocol

Interface for custom data export formats.

### Protocol Definition

```python
from typing import Protocol
from httptap.models import RequestStep

class ExporterProtocol(Protocol):
    def export(
        self,
        steps: list[RequestStep],
        output_path: str
    ) -> None:
        """Export request data to file.

        Args:
            steps: List of request steps to export
            output_path: Path to output file

        Returns:
            None (writes to file)

        Raises:
            Exception: If export fails
        """
        ...
```

### Example Implementation

```python
import yaml
from httptap.models import RequestStep

class YAMLExporter:
    """Export request data to YAML format."""

    def export(self, steps: list[RequestStep], output_path: str):
        data = {
            "total_steps": len(steps),
            "steps": []
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
                    "total_ms": step.timing.total_ms
                },
                "network": {
                    "ip": step.network.ip,
                    "family": step.network.ip_family,
                    "http_version": step.network.http_version,
                    "tls_version": step.network.tls_version
                }
            }
            data["steps"].append(step_data)

        with open(output_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

# Usage
analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

exporter = YAMLExporter()
exporter.export(steps, "output.yaml")
```

## Type Checking

All protocols are fully type-hinted and work with mypy, pyright, and other type checkers.

```python
from typing import reveal_type
from httptap.interfaces import DNSResolverProtocol

class MyResolver:
    def resolve(self, host: str, port: int, timeout: float):
        return "192.168.1.1", "IPv4", 10.5

# Type checker will verify MyResolver implements the protocol
resolver: DNSResolverProtocol = MyResolver()
reveal_type(resolver)  # Type: DNSResolverProtocol
```

## Next Steps

- See [core components documentation](core.md)
- Review [advanced usage examples](../usage/advanced.md)
- Check [contributing guidelines](../development/contributing.md) to add new protocols
