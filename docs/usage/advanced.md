# Advanced Features

This guide covers advanced usage patterns and customization options for httptap.

## Custom DNS Resolution

You can provide custom DNS resolver implementations by using the Python API.

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver

class CustomDNSResolver(SystemDNSResolver):
    """Custom DNS resolver with hardcoded responses."""

    def resolve(self, host: str, port: int, timeout: float):
        # Override with custom logic
        if host == "httpbin.io":
            return "44.211.11.205", "IPv4", 0.1
        return super().resolve(host, port, timeout)

# Use custom resolver
analyzer = HTTPTapAnalyzer(dns_resolver=CustomDNSResolver())
steps = analyzer.analyze_url("https://httpbin.io")
```

## Custom TLS Inspection

Implement custom TLS inspection logic to extract additional certificate information.

```python
from httptap import HTTPTapAnalyzer
from httptap.interfaces import TLSInspectorProtocol

class CustomTLSInspector:
    """Custom TLS inspector with extended certificate checks."""

    def inspect(self, host: str, port: int, timeout: float):
        # Custom TLS inspection logic
        # Return: (version, cipher, cert_cn, days_left, duration_ms)
        pass

analyzer = HTTPTapAnalyzer(tls_inspector=CustomTLSInspector())
```

## Programmatic Usage

Use httptap as a Python library for integration into your applications.

### Basic Analysis

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

for step in steps:
    print(f"URL: {step.url}")
    print(f"Status: {step.response.status}")
    print(f"Total time: {step.timing.total_ms:.2f}ms")
```

### With Custom Headers

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
headers = {
    "Authorization": "Bearer token123",
    "Accept": "application/json"
}

steps = analyzer.analyze_url(
    "https://httpbin.io/bearer",
    headers=headers
)
```

### Following Redirects

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url(
    "https://httpbin.io/redirect/3",
    follow_redirects=True
)

print(f"Total steps in redirect chain: {len(steps)}")
```

## Ignoring TLS Verification

When troubleshooting staging environments or hosts with self-signed certificates, you can skip TLS validation:

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

The request still records TLS metadata, but certificate errors are suppressed so you can focus on the protocol flow. Only use this flag in trusted environments because it disables protection against man-in-the-middle attacks.
The client relaxes many cipher and protocol requirements (weak hashes,
older TLS versions, small DH groups) so that legacy endpoints are more
likely to complete the handshake. Extremely deprecated algorithms that
OpenSSL removes entirely (e.g., RC4, 3DES on some platforms) may still
fail even in this mode.

### Using Proxies

Direct requests through an outbound proxy (HTTP, HTTPS, SOCKS5/SOCKS5H):

```shell
httptap --proxy https://proxy.internal:8443 https://httpbin.io/get
```

```shell
httptap --proxy socks5h://proxy.internal:1080 https://httpbin.io/get
```

The Rich output and JSON export include the proxy URI when one is used.

## Custom Request Executors

For fully customized behavior you can provide your own request executor.
Executors receive all parameters packaged inside `RequestOptions`, so new
flags added by httptap remain backward compatible.

```python
from httptap import HTTPTapAnalyzer, RequestExecutor, RequestOptions, RequestOutcome


class RecordingExecutor(RequestExecutor):
    def __init__(self) -> None:
        self.last_options: RequestOptions | None = None

    def execute(self, options: RequestOptions) -> RequestOutcome:
        self.last_options = options
        # Call the built-in client (or your preferred HTTP library)
        from httptap.http_client import make_request

        timing, network, response = make_request(
            options.url,
            options.timeout,
            http2=options.http2,
            verify_ssl=options.verify_ssl,
            dns_resolver=options.dns_resolver,
            tls_inspector=options.tls_inspector,
            timing_collector=options.timing_collector,
            force_new_connection=options.force_new_connection,
            headers=options.headers,
        )
        return RequestOutcome(timing=timing, network=network, response=response)


executor = RecordingExecutor()
analyzer = HTTPTapAnalyzer(request_executor=executor)
analyzer.analyze_url("https://httpbin.io/get", headers={"X-Debug": "1"})
print(executor.last_options.headers)  # {'X-Debug': '1'}
```

If you already have a callable compatible with the legacy signature, wrap
it with the provided adapter:

```python
from httptap import CallableRequestExecutor, HTTPTapAnalyzer


def legacy_executor(url, timeout, *, http2, headers=None, **kwargs):
    # Custom request logic here
    ...


adapter = CallableRequestExecutor(legacy_executor)
analyzer = HTTPTapAnalyzer(request_executor=adapter)
analyzer.analyze_url("https://legacy.example")
```

When a wrapped callable is missing support for newly introduced flags (such
as `verify_ssl`), the adapter logs a `DeprecationWarning` and transparently
retries without that parameter. This gives you time to update custom
executors while keeping behavior backward compatible.

## Custom Visualization

Create your own visualization by implementing the `VisualizerProtocol`.

```python
from httptap.interfaces import VisualizerProtocol
from httptap.models import RequestStep

class CustomVisualizer:
    """Custom visualizer for request steps."""

    def render(self, steps: list[RequestStep], *, follow: bool = False):
        for step in steps:
            # Custom rendering logic
            print(f"Step {step.step_number}: {step.timing.total_ms}ms")

# Use custom visualizer
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

visualizer = CustomVisualizer()
visualizer.render(steps)
```

## Custom Export Formats

Implement custom export formats beyond JSON.

```python
from httptap.interfaces import ExporterProtocol
from httptap.models import RequestStep
import csv

class CSVExporter:
    """Export request data to CSV format."""

    def export(self, steps: list[RequestStep], output_path: str):
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['url', 'status', 'dns_ms', 'connect_ms',
                           'tls_ms', 'ttfb_ms', 'total_ms'])

            for step in steps:
                writer.writerow([
                    step.url,
                    step.response.status,
                    step.timing.dns_ms,
                    step.timing.connect_ms,
                    step.timing.tls_ms,
                    step.timing.ttfb_ms,
                    step.timing.total_ms
                ])

# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

exporter = CSVExporter()
exporter.export(steps, "output.csv")
```

## Performance Monitoring

Use httptap for continuous performance monitoring.

```python
import time
from httptap import HTTPTapAnalyzer

def monitor_endpoint(url: str, interval: int = 60):
    """Monitor endpoint every interval seconds."""
    analyzer = HTTPTapAnalyzer()

    while True:
        steps = analyzer.analyze_url(url)
        step = steps[0]

        # Log metrics
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - "
              f"TTFB: {step.timing.ttfb_ms:.2f}ms, "
              f"Total: {step.timing.total_ms:.2f}ms, "
              f"Status: {step.response.status}")

        time.sleep(interval)

# Monitor API endpoint every minute
monitor_endpoint("https://httpbin.io/status/200", interval=60)
```

## Batch Analysis

Analyze multiple URLs concurrently.

```python
from concurrent.futures import ThreadPoolExecutor
from httptap import HTTPTapAnalyzer

def analyze_url(url: str):
    """Analyze a single URL."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url(url)
    return url, steps[0].timing.total_ms

# List of URLs to analyze
urls = [
    "https://httpbin.io",
    "https://httpbin.io/delay/1",
    "https://httpbin.io/gzip"
]

# Analyze concurrently
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(analyze_url, urls))

# Print results
for url, total_ms in results:
    print(f"{url}: {total_ms:.2f}ms")
```

## Error Handling

Handle errors gracefully when analyzing URLs.

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()

try:
    steps = analyzer.analyze_url("https://httpbin.io/status/500")
except Exception as e:
    print(f"Error analyzing URL: {e}")
    # Handle error appropriately
```

## Integration with Testing Frameworks

Use httptap in your test suites to verify performance requirements.

```python
import pytest
from httptap import HTTPTapAnalyzer

def test_api_response_time():
    """Test that API responds within acceptable time."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url("https://httpbin.io/delay/0")

    # Assert TTFB is under 500ms
    assert steps[0].timing.ttfb_ms < 500, \
        f"TTFB too high: {steps[0].timing.ttfb_ms}ms"

    # Assert total time is under 1 second
    assert steps[0].timing.total_ms < 1000, \
        f"Total time too high: {steps[0].timing.total_ms}ms"

def test_tls_configuration():
    """Verify TLS configuration meets security standards."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url("https://httpbin.io")

    # Assert TLS 1.2 or higher
    assert steps[0].network.tls_version in ["TLSv1.2", "TLSv1.3"], \
        f"Insecure TLS version: {steps[0].network.tls_version}"

    # Assert certificate is valid for at least 30 days
    assert steps[0].network.cert_days_left > 30, \
        f"Certificate expiring soon: {steps[0].network.cert_days_left} days"
```

## Environment-Specific Configuration

Configure httptap differently for various environments.

```python
import os
from httptap import HTTPTapAnalyzer

# Environment-specific settings
config = {
    "production": {
        "timeout": 30,
        "follow_redirects": True
    },
    "staging": {
        "timeout": 60,
        "follow_redirects": True
    },
    "development": {
        "timeout": 120,
        "follow_redirects": False
    }
}

env = os.getenv("ENVIRONMENT", "development")
settings = config[env]

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url(
    "https://httpbin.io/status/200",
    follow_redirects=settings["follow_redirects"]
)
```

## Debugging Tips

### Enable Detailed Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
```

### Inspect Raw HTTP Traffic

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

# Inspect response headers
step = steps[0]
print("Response headers:")
for key, value in step.response.headers.items():
    print(f"  {key}: {value}")
```

---

## What's Next?

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **[API Reference](../api/overview.md)**

    ---

    Detailed interface documentation

-   :material-account-group:{ .lg .middle } **[Contributing Guide](../development/contributing.md)**

    ---

    Extend httptap and contribute

-   :material-rocket-launch:{ .lg .middle } **[Release Process](../development/release.md)**

    ---

    How releases work

</div>
