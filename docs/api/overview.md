---
title: API Overview
description: High-level tour of the public httptap API surface exported from the package root.
---

# API Overview

httptap provides a clean Python API for programmatic use and extension. This page maps the
public surface exported from the `httptap` package root; the linked pages drill into the core
classes and the extensibility protocols.

## Architecture

httptap is built around a modular architecture with clear, injectable interfaces:

```
┌─────────────────┐
│  CLI / Renderer │  wires Visualizers & Exporters
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTPTapAnalyzer│  ◄── main entry point
└────────┬────────┘
         │  (injectable collaborators)
         ├─► DNS Resolver     (Protocol)
         ├─► TLS Inspector    (Protocol)
         ├─► Timing Collector (Protocol)
         └─► Request Executor (Protocol)
```

## Main entry point

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
```

`analyze_url` also accepts keyword-only arguments for non-GET requests:

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod

analyzer = HTTPTapAnalyzer(follow_redirects=True, timeout=10.0)
steps = analyzer.analyze_url(
    "https://httpbin.io/post",
    method=HTTPMethod.POST,
    content=b'{"name": "John"}',
    headers={"Content-Type": "application/json"},
)
```

::: httptap.analyzer.HTTPTapAnalyzer
    options:
      members: false
      show_bases: false

See **[Core Components](core.md)** for the full method and data-model reference.

## Core data model

A single request/response cycle is captured by `StepMetrics`, which nests timing, network,
and response detail. Full field-level docs live on the [Core Components](core.md) page.

- [`StepMetrics`](core.md#httptap.models.StepMetrics) — one request in a redirect chain
- [`TimingMetrics`](core.md#httptap.models.TimingMetrics) — phase-by-phase timing
- [`NetworkInfo`](core.md#httptap.models.NetworkInfo) — IP, TLS, certificate, and proxy detail
- [`ResponseInfo`](core.md#httptap.models.ResponseInfo) — status, headers, body size

## Protocol interfaces

httptap uses `Protocol` classes (PEP 544) for type-safe, inheritance-free extensibility.
Each protocol and a worked custom implementation is documented on the
**[Protocol Interfaces](interfaces.md)** page:
`DNSResolver`, `TLSInspector`, `TimingCollector`, `Visualizer`, `Exporter`, and `RequestExecutor`.

## Request executor

For fully customised HTTP behaviour, implement the `RequestExecutor` protocol and pass an
instance as `request_executor=` to `HTTPTapAnalyzer`. The protocol contract and its
`RequestOptions` / `RequestOutcome` data classes are documented on the
**[Protocol Interfaces](interfaces.md#requestexecutor)** page.

## Built-in implementations

httptap ships production-ready defaults for every protocol; all are importable from the
package root.

::: httptap.implementations.dns.SystemDNSResolver

::: httptap.implementations.tls.SocketTLSInspector

::: httptap.implementations.timing.PerfCounterTimingCollector

::: httptap.visualizer.WaterfallVisualizer

::: httptap.exporter.JSONExporter

::: httptap.request_executor.HTTPClientRequestExecutor

## SLO evaluation

The SLO helpers are exposed at the package root so programmatic callers can parse, evaluate,
and serialize latency budgets exactly as the CLI does.

```python
from httptap import HTTPTapAnalyzer, evaluate_slo, parse_slo_spec, select_step_for_evaluation

analyzer = HTTPTapAnalyzer(follow_redirects=True)
steps = analyzer.analyze_url("https://api.example.com/health")

thresholds = parse_slo_spec("total=500,ttfb=200")
target = select_step_for_evaluation(steps)
if target is not None:
    result = evaluate_slo(target, thresholds)
    if not result.passed:
        for violation in result.violations:
            print(f"{violation.key}: {violation.actual_ms:.1f}ms > {violation.threshold_ms:g}ms")
```

::: httptap.slo.parse_slo_spec

::: httptap.slo.evaluate_slo

::: httptap.slo.select_step_for_evaluation

::: httptap.slo.SLOResult

::: httptap.slo.SLOViolation

::: httptap.slo.SLOSpecError

::: httptap.slo.SLO_KEYS

## Error handling

httptap returns errors as part of `StepMetrics` rather than raising during analysis.

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
