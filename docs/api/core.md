# Core Components

This page documents the core classes and functions in httptap.

## HTTPTapAnalyzer

The main analyzer class that orchestrates HTTP request analysis.

### Constructor

```python
HTTPTapAnalyzer(
    *,
    follow_redirects: bool = False,
    timeout: float = 20.0,
    http2: bool = True,
    verify_ssl: bool = True,
    ca_bundle_path: str | None = None,
    max_redirects: int = 10,
    request_executor: RequestExecutor | None = None,
    proxy: ProxyTypes | None = None,
    dns_resolver: DNSResolver | None = None,
    tls_inspector: TLSInspector | None = None,
    timing_collector_factory: type[TimingCollector] | None = None,
)
```

**Parameters:**

- `follow_redirects` - Whether to follow 3xx redirects
- `timeout` - Request timeout in seconds (default 20)
- `http2` - Enable HTTP/2 support (default True)
- `verify_ssl` - Whether to verify TLS certificates
- `ca_bundle_path` - Path to custom CA certificate bundle (PEM format)
- `max_redirects` - Maximum number of redirects to follow
- `request_executor` - Custom request executor implementation (optional)
- `proxy` - Proxy URL (http/https/socks5/socks5h) for all requests
- `dns_resolver` - Custom DNS resolver implementation (optional)
- `tls_inspector` - Custom TLS inspector implementation (optional)
- `timing_collector_factory` - Factory class for creating timing collectors (optional)

If not provided, default implementations are used.

### Methods

#### analyze_url()

```python
def analyze_url(
    self,
    url: str,
    *,
    method: HTTPMethod = HTTPMethod.GET,
    content: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> list[StepMetrics]
```

Analyze an HTTP request and return detailed timing information.

**Parameters:**

- `url` - The URL to analyze (must include scheme: http:// or https://)
- `method` - HTTP method to use (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
- `content` - Optional request body as bytes
- `headers` - Optional custom HTTP headers

**Returns:**

- `list[StepMetrics]` - List of request steps (one per redirect)

**Example:**

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod

analyzer = HTTPTapAnalyzer(follow_redirects=True)
steps = analyzer.analyze_url(
    "https://httpbin.io",
    headers={"Accept": "application/json"},
)
```

## Data Models

### StepMetrics

Represents a single HTTP request/response cycle.

```python
@dataclass(slots=True)
class StepMetrics:
    url: str = ""                                       # Request URL
    step_number: int = 1                                # Step number in redirect chain
    timing: TimingMetrics = field(default_factory=...)   # Timing information
    network: NetworkInfo = field(default_factory=...)    # Network details
    response: ResponseInfo = field(default_factory=...)  # Response data
    error: str | None = None                            # Error message if failed
    note: str | None = None                             # Additional notes
    proxied_via: str | None = None                      # Proxy URL used, if any
    request_method: str | None = None                   # HTTP method used
    request_headers: dict[str, str] = field(...)        # Request headers (sanitized)
    request_body_bytes: int = 0                         # Size of request body
```

### TimingMetrics

Contains detailed timing breakdown for the request. All values are in milliseconds.

```python
@dataclass(slots=True)
class TimingMetrics:
    dns_ms: float = 0.0        # DNS resolution time
    connect_ms: float = 0.0    # TCP connection time
    tls_ms: float = 0.0        # TLS handshake time
    ttfb_ms: float = 0.0       # Time to first byte
    total_ms: float = 0.0      # Total request time
    wait_ms: float = 0.0       # Server processing time (derived)
    xfer_ms: float = 0.0       # Body transfer time (derived)
    is_estimated: bool = False  # Whether timing is estimated
```

Call `calculate_derived()` after populating raw timing values to compute `wait_ms` and `xfer_ms`.

### NetworkInfo

Contains network-level details about the connection. All fields are optional.

```python
@dataclass(slots=True)
class NetworkInfo:
    ip: str | None = None              # Resolved IP address
    ip_family: str | None = None       # "IPv4" or "IPv6"
    http_version: str | None = None    # HTTP protocol version
    tls_version: str | None = None     # TLS protocol version
    tls_cipher: str | None = None      # Cipher suite name
    cert_cn: str | None = None         # Certificate common name
    cert_days_left: int | None = None  # Days until certificate expires
    tls_verified: bool | None = None   # Whether TLS verification was enforced
    tls_custom_ca: bool | None = None  # True when custom CA bundle was used
```

### ResponseInfo

Contains HTTP response metadata.

```python
@dataclass(slots=True)
class ResponseInfo:
    status: int | None = None            # HTTP status code
    bytes: int = 0                       # Response body size
    content_type: str | None = None      # Content-Type header
    server: str | None = None            # Server header
    date: datetime | None = None         # Response date (parsed)
    location: str | None = None          # Location header (redirects)
    headers: dict[str, str] = field(...) # Sanitized response headers
```

## Utility Functions

### validate_url()

Validate that a URL is a valid HTTP/HTTPS URL.

```python
from httptap.utils import validate_url

validate_url("https://httpbin.io")     # True
validate_url("ftp://example.com")      # False
```

### sanitize_headers()

Mask sensitive header values (Authorization, Cookie, API keys).

```python
from httptap.utils import sanitize_headers

sanitize_headers({"Authorization": "Bearer secret123"})
# {'Authorization': 'Bear****t123'}
```

### parse_http_date()

Parse HTTP date header to datetime.

```python
from httptap.utils import parse_http_date

dt = parse_http_date("Mon, 22 Oct 2025 12:00:00 GMT")
```

### create_ssl_context()

Create an SSL context with configurable verification and optional custom CA bundle.

```python
from httptap.utils import create_ssl_context

ctx = create_ssl_context(verify_ssl=True, ca_bundle_path="/path/to/ca.pem")
```

## Constants

### Timeouts and Limits

```python
from httptap.constants import (
    DEFAULT_TIMEOUT_SECONDS,       # 20.0 seconds
    TLS_PROBE_MAX_TIMEOUT_SECONDS, # 5.0 seconds
    HTTP_DEFAULT_PORT,             # 80
    HTTPS_DEFAULT_PORT,            # 443
)
```

### Exit Codes

```python
from httptap.constants import (
    EXIT_CODE_OK,        # 0 - Success
    EXIT_CODE_USAGE,     # 64 - Invalid arguments
    EXIT_CODE_SOFTWARE,  # 70 - Internal error
    EXIT_CODE_TEMPFAIL,  # 75 - Network/TLS error
)
```

## Example: Complete Usage

```python
from httptap import HTTPTapAnalyzer

# Create analyzer with custom settings
analyzer = HTTPTapAnalyzer(
    follow_redirects=True,
    timeout=30.0,
    http2=True,
)

# Analyze with custom headers
steps = analyzer.analyze_url(
    "https://httpbin.io/bearer",
    headers={
        "Authorization": "Bearer token123",
        "Accept": "application/json",
        "User-Agent": "MyApp/1.0",
    },
)

# Process results
for step in steps:
    print(f"Step {step.step_number}: {step.url}")
    print(f"  Status: {step.response.status}")
    print(f"  DNS: {step.timing.dns_ms:.2f}ms")
    print(f"  Connect: {step.timing.connect_ms:.2f}ms")
    print(f"  TLS: {step.timing.tls_ms:.2f}ms")
    print(f"  TTFB: {step.timing.ttfb_ms:.2f}ms")
    print(f"  Total: {step.timing.total_ms:.2f}ms")
    if step.network.ip:
        print(f"  IP: {step.network.ip} ({step.network.ip_family})")
    if step.network.http_version:
        print(f"  HTTP: {step.network.http_version}")
    if step.network.tls_version:
        print(f"  TLS: {step.network.tls_version}")
    if step.network.cert_cn:
        print(f"  Certificate: {step.network.cert_cn} "
              f"(expires in {step.network.cert_days_left} days)")
```

---

## What's Next?

<div class="grid cards" markdown>

-   :material-puzzle:{ .lg .middle } **[Protocol Interfaces](interfaces.md)**

    ---

    Implement custom DNS, TLS, timing, and more

-   :material-cog:{ .lg .middle } **[Advanced Usage](../usage/advanced.md)**

    ---

    Patterns for monitoring, testing, batch analysis

-   :material-account-group:{ .lg .middle } **[Contributing](../development/contributing.md)**

    ---

    Extend httptap and contribute back

</div>
