# Roadmap

This document describes what httptap intends to do — and, equally
importantly, what it does **not** intend to do — over roughly the next
twelve months. It is intentionally light on dates and heavy on scope: the
project is maintained by a single person in their spare time, so concrete
schedules would be misleading.

The roadmap is living. Opening an issue to propose a change is welcome and
is the preferred way to request scope adjustments. Merged scope changes are
reflected here in the same pull request.

**Last reviewed:** 2026-04-12

## Mission

`httptap` is a diagnostic command-line tool that dissects a single HTTP
request into its constituent phases (DNS, TCP connect, TLS handshake,
server wait, body transfer) and renders those timings in a form suitable
for humans, logs, or scripts. The mission is to make per-phase HTTP timing
legible to a developer the same way a browser's waterfall makes it legible
to a web author — but from the terminal, without a browser, and without
pulling in a heavyweight framework.

## Current Phase: Maintenance & Polish

The project is stable and in active maintenance. The release cadence is
dictated by:

- incoming bug reports and security updates,
- dependency refreshes via Dependabot,
- small quality-of-life improvements contributed by users or the maintainer.

There is no committed feature list. New functionality is added only when it
clearly serves the mission and fits within the non-goals below.

## In Scope

The following themes are accepted as potential work. Specific items only
materialize when the maintainer or a contributor actually picks them up.

- **Core timing accuracy** — refinements to httpcore trace hooks, better
  handling of HTTP/2 connection reuse, more precise fallbacks when direct
  timing is unavailable.
- **Output formats** — additional machine-readable exporters (e.g.,
  Prometheus text format, OpenTelemetry traces) when driven by a concrete
  user need.
- **Protocol support** — minor improvements to HTTP/1.1 and HTTP/2 behavior
  as upstream (`httpx`, `httpcore`) gains features; potential support for
  HTTP/3 if and when stable Python support lands.
- **TLS diagnostics** — additional certificate and handshake details
  reported by default or under flags.
- **Supply-chain hardening** — continuing improvements that raise the
  project's OpenSSF Scorecard and Best Practices posture.
- **Documentation** — worked examples, troubleshooting recipes, and
  integration cookbooks.

## Non-Goals

These items are explicitly **out of scope**. Contributions in these
directions will be declined politely so contributors don't waste effort.

- **Load testing / benchmarking** — httptap measures a single request; tools
  like `wrk`, `k6`, or `vegeta` already serve the benchmarking use case.
- **Full curl replacement** — httptap aims for curl-compatible flags on the
  overlap that makes sense; it does not target feature parity with curl.
- **Scripting / session runners** — multi-request workflows, cookies,
  scripting, or chainable request/response assertions belong in tools like
  `httpie` or `hurl`.
- **Server-side tooling** — httptap is strictly a client. Proxying,
  mitmproxy-style interception, or server emulation are out of scope.
- **GUI or TUI** — terminal output stays as Rich renders; no full-screen
  TUI and no graphical interface.
- **Plugin ecosystem** — the Python Protocol interfaces are explicitly
  supported as a programmatic extension point, but a dynamic plugin loader
  or plugin registry is not planned.
- **Non-HTTP protocols** — gRPC, WebSocket, MQTT, etc. are out of scope.

## Deprecation Policy

- Public API and CLI flags follow Semantic Versioning 2.0.0.
- Breaking changes ship only in a major version bump (`X.0.0`) with
  migration notes in `CHANGELOG.md` and the release notes.
- Deprecations are announced at least one minor release before removal and
  emit a runtime warning where practical.

## Supported Versions

See [SECURITY.md](SECURITY.md) for the currently supported minor series.

## Python Support

The project targets the Python versions currently labelled as supported by
the [Python release calendar](https://devguide.python.org/versions/) plus
the current pre-release series (3.10–3.15 at the time of writing). Older
Python versions are dropped only at major releases and only when required
by a dependency.

## How to Propose a Change

Open a [GitHub issue](https://github.com/ozeranskii/httptap/issues/new) with
the "enhancement" label describing the problem, the proposed direction, and
(if applicable) why it fits within the mission and does not cross a
non-goal. The maintainer will respond with acceptance, pushback, or a
request for more detail.

Significant changes are expected to land as a pull request only after the
proposal has been discussed.
