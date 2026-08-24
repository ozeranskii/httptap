---
title: Protocol Interfaces
description: Protocol contracts and worked examples for extending httptap with custom implementations.
---

# Protocol Interfaces

httptap uses `Protocol` classes (PEP 544) for structural subtyping, so you can supply custom
implementations without inheriting from any base class.

## Why protocols?

- **Duck typing with type safety** — type checkers verify your implementation
- **No inheritance required** — just implement the methods
- **Clear contracts** — explicit interface definitions
- **Easy testing** — simple to mock and substitute

The interface contracts below are rendered from source. Each is followed by a worked custom
implementation you can adapt.

## DNSResolver

::: httptap.interfaces.DNSResolver

httptap dials the resolved IP address directly while keeping the original hostname for the
`Host` header and TLS SNI. IPv6 addresses are bracketed automatically; implementations only
need to return a valid `(ip, family, duration_ms)` tuple. `family` is `"IPv4"`, `"IPv6"`, or
`"AF_<num>"` for other address families.

### Example implementation

```python
import socket
import time


class CustomDNSResolver:
    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        start = time.perf_counter()
        try:
            addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            ip_address = addr_info[0][4][0]
            family = "IPv6" if ":" in ip_address else "IPv4"
            duration_ms = (time.perf_counter() - start) * 1000
            return ip_address, family, duration_ms
        except socket.gaierror as e:
            raise Exception(f"DNS resolution failed: {e}")


from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(dns_resolver=CustomDNSResolver())
```

## TLSInspector

::: httptap.interfaces.TLSInspector

### Example implementation

```python
import ssl
import socket
import time
from datetime import datetime
from httptap.models import NetworkInfo


class CustomTLSInspector:
    def inspect(self, host: str, port: int, timeout: float) -> NetworkInfo:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                version = ssock.version()
                cipher = ssock.cipher()[0]
                cert = ssock.getpeercert()
                cert_cn = dict(x[0] for x in cert["subject"])["commonName"]
                not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                days_left = (not_after - datetime.now()).days

        return NetworkInfo(
            tls_version=version,
            tls_cipher=cipher,
            cert_cn=cert_cn,
            cert_days_left=days_left,
        )


from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(tls_inspector=CustomTLSInspector())
```

## TimingCollector

A new collector instance is created for each request in the chain, so pass the **class**
(a factory), not an instance.

::: httptap.interfaces.TimingCollector

### Example implementation

```python
import time
from httptap.models import TimingMetrics


class CustomTimingCollector:
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


# Pass the class (not an instance) as the factory:
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(timing_collector_factory=CustomTimingCollector)
```

## Visualizer

::: httptap.interfaces.Visualizer

### Example implementation

```python
from httptap.models import StepMetrics


class SimpleVisualizer:
    def render(self, step: StepMetrics) -> None:
        print(f"Step {step.step_number}: {step.url}")
        print(f"  Status: {step.response.status}")
        print(f"    DNS:     {step.timing.dns_ms:8.2f}ms")
        print(f"    Connect: {step.timing.connect_ms:8.2f}ms")
        print(f"    TLS:     {step.timing.tls_ms:8.2f}ms")
        print(f"    TTFB:    {step.timing.ttfb_ms:8.2f}ms")
        print(f"    Total:   {step.timing.total_ms:8.2f}ms")


from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
for step in analyzer.analyze_url("https://httpbin.io"):
    SimpleVisualizer().render(step)
```

## Exporter

::: httptap.interfaces.Exporter

Concrete exporters may embed an optional SLO evaluation via the keyword-only `slo_result`
argument; see the built-in [`JSONExporter`](overview.md#httptap.exporter.JSONExporter).

### Example implementation

```python
import yaml
from collections.abc import Sequence
from httptap.models import StepMetrics
from httptap.slo import SLOResult


class YAMLExporter:
    def export(
        self,
        steps: Sequence[StepMetrics],
        initial_url: str,
        output_path: str,
        *,
        slo_result: SLOResult | None = None,
    ) -> None:
        data = {
            "initial_url": initial_url,
            "total_steps": len(steps),
            "steps": [
                {
                    "url": step.url,
                    "status": step.response.status,
                    "timing": step.timing.to_dict(),
                    "network": step.network.to_dict(),
                }
                for step in steps
            ],
        }
        if slo_result is not None:
            data["slo"] = slo_result.to_dict()
        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
YAMLExporter().export(steps, "https://httpbin.io", "output.yaml")
```

## RequestExecutor

For full control over how requests are performed, implement `RequestExecutor` and pass an
instance as `request_executor=` to `HTTPTapAnalyzer`.

::: httptap.request_executor.RequestExecutor

::: httptap.request_executor.RequestOptions

::: httptap.request_executor.RequestOutcome

## Type checking

All protocols are fully type-hinted and work with mypy, pyright, and other type checkers.
Because they are structural, any class implementing the required methods satisfies the type —
no explicit subclassing needed.

```python
from httptap.interfaces import DNSResolver


class MyResolver:
    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        return "192.168.1.1", "IPv4", 10.5


resolver: DNSResolver = MyResolver()  # verified by the type checker
```

## Next steps

- See [core components documentation](core.md)
- Review [advanced usage examples](../usage/advanced.md)
- Check [contributing guidelines](../development/contributing.md) to add new protocols
