---
title: Core Components
description: Reference for HTTPTapAnalyzer, the core data models, and utility helpers.
---

# Core Components

This page documents the core class and data models of httptap, rendered directly from the
source docstrings so signatures and defaults always match the installed version.

## HTTPTapAnalyzer

The main analyzer class that orchestrates HTTP request analysis, including redirect following
and per-step metric collection.

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod

analyzer = HTTPTapAnalyzer(follow_redirects=True)
steps = analyzer.analyze_url(
    "https://httpbin.io",
    headers={"Accept": "application/json"},
)
```

::: httptap.analyzer.HTTPTapAnalyzer

## Data models

All models are `@dataclass(slots=True)` and expose `to_dict()` for JSON export.

::: httptap.models.StepMetrics

::: httptap.models.TimingMetrics

::: httptap.models.NetworkInfo

::: httptap.models.ResponseInfo

## Utility functions

::: httptap.utils.validate_url

::: httptap.utils.sanitize_headers

::: httptap.utils.parse_http_date

::: httptap.utils.create_ssl_context

## Constants

Selected values from `httptap.constants` (see the module source for the full set):

### Timeouts and limits

```python
from httptap.constants import (
    DEFAULT_TIMEOUT_SECONDS,  # 20.0 seconds
    TLS_PROBE_MAX_TIMEOUT_SECONDS,  # 5.0 seconds
    HTTP_DEFAULT_PORT,  # 80
    HTTPS_DEFAULT_PORT,  # 443
)
```

### Exit codes

```python
from httptap.constants import (
    EXIT_CODE_OK,  # 0  - Success (os.EX_OK)
    EXIT_CODE_USAGE,  # 64 - Invalid arguments (os.EX_USAGE)
    EXIT_CODE_SOFTWARE,  # 70 - Internal error (os.EX_SOFTWARE)
    EXIT_CODE_TEMPFAIL,  # 75 - Network/TLS error (os.EX_TEMPFAIL)
)
```

## Example: complete usage

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(follow_redirects=True, timeout=30.0, http2=True)

steps = analyzer.analyze_url(
    "https://httpbin.io/bearer",
    headers={
        "Authorization": "Bearer token123",
        "Accept": "application/json",
        "User-Agent": "MyApp/1.0",
    },
)

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
    if step.network.cert_cn:
        print(f"  Certificate: {step.network.cert_cn} (expires in {step.network.cert_days_left} days)")
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
