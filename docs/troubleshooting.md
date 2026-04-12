---
title: Troubleshooting & FAQ
description: Common issues, error messages, and diagnostics when running httptap.
---

# Troubleshooting & FAQ

This page collects the most common questions and errors users hit when running
`httptap`. If your issue isn't listed, please
[open an issue](https://github.com/ozeranskii/httptap/issues) with the exact
command, the JSON export (if any), and the relevant terminal output.

## TLS and certificates

### `TLS handshake failed: CERTIFICATE_VERIFY_FAILED`

The server presented a certificate your trust store doesn't recognize.

- **Self-signed or expired cert on a non-production host** — add `--ignore-ssl`
  (disables validation, use on trusted networks only).
- **Internal CA** — point `--cacert` (alias `--ca-bundle`) at your PEM bundle.
- **System trust store out of date** — update `ca-certificates` on Linux, or
  refresh `certifi` in your Python environment (`uv pip install --upgrade certifi`).

The JSON export shows `network.tls_verified: false` and, when `--cacert` is
used, `network.tls_custom_ca: true`.

### Certificate shows `cert_days_left: null` or negative

`cert_days_left` is parsed from the leaf certificate's `notAfter` field. A
`null` value means the inspector couldn't fetch/parse the certificate (usually
TLS aborted before a cert was received). A **negative** value means the
certificate is already expired.

### `--ignore-ssl` still fails with `DH_KEY_TOO_SMALL` / `WRONG_VERSION_NUMBER`

Modern OpenSSL builds drop some ciphers and DH parameters for safety.
`--ignore-ssl` relaxes verification and protocol constraints but can't bring
back cipher suites (RC4, 3DES, weak DH) that were removed from the binary.
Workarounds: use an older curl, a proxy that terminates TLS, or rebuild OpenSSL.

## Proxies

### `--proxy` is ignored

The explicit `-x/--proxy` flag always wins over environment variables. Check:

1. You didn't pass an empty string by mistake — `--proxy ""` **explicitly
   disables** env-based proxies and forces direct connection.
2. The scheme matches the target — `HTTPS_PROXY` is used for `https://` URLs,
   `HTTP_PROXY` for `http://`.
3. The target host isn't matched by `NO_PROXY`. Check the `proxy_source` field
   in the JSON export; if it says `env:no_proxy`, your host is excluded.

### `NO_PROXY` pattern reference

- Exact host: `api.internal.example`
- Domain suffix: `.internal.example` (matches `foo.internal.example`)
- Wildcard: `*` (excludes everything)
- Multiple entries: comma-separated, whitespace trimmed

IP/CIDR matching is **not** supported — this follows the widely-adopted curl
behavior.

## HTTP/2

### Server responds with HTTP/1.1 even though `--no-http2` wasn't passed

HTTP/2 requires ALPN negotiation during the TLS handshake. If:

- the server does not advertise `h2` in ALPN, **or**
- the target uses plain `http://` (h2c is not supported),

httptap falls back to HTTP/1.1. Check `network.http_version` in the JSON
export.

### How do I force HTTP/1.1?

Use `--no-http2` (curl-compatible alias `--http1.1`). This disables ALPN h2
negotiation entirely.

## Timing

### `timing.is_estimated: true` — what does it mean?

httptap normally gets phase timings from `httpcore` trace hooks. When those
hooks are unavailable (e.g., a custom `RequestExecutor` that bypasses them,
or certain HTTP/2 connection-reuse paths), httptap falls back to splitting the
total elapsed time using heuristics. The breakdown is still directionally
correct but less precise than the default path.

### Why do two consecutive runs show wildly different `dns_ms`?

The system resolver caches entries. The first request pays the full RTT to
your DNS server; subsequent requests hit the cache (often sub-millisecond).
To bypass caches, supply a custom resolver via the Python API or flush the
local cache (e.g., `sudo dscacheutil -flushcache` on macOS, `resolvectl flush-caches`
on systemd).

### `ttfb_ms` is zero or lower than `connect_ms`

On connection reuse (keep-alive for subsequent redirect steps, HTTP/2 stream
multiplexing) there's no new TCP connect for that step — `connect_ms` will be
`0` or very small. `ttfb_ms` measures time until the first response byte on
that specific request; comparing it to `connect_ms` across steps is expected
to look odd.

## Output

### No colors in my terminal

httptap honors the [`NO_COLOR`](https://no-color.org) convention and Rich's
TTY detection:

- Unset `NO_COLOR` if it's set.
- Piping stdout to a file or another process disables colors; set
  `FORCE_COLOR=1` to override.
- `TERM=dumb` also disables rendering.

### `--metrics-only` stopped showing a `proxy=` field

It didn't — the field is always present. Old screenshots/examples may predate
the change. Expected format:

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

Sources for `proxy`: `direct`, `none` (NO_PROXY hit), `disabled` (`--proxy ""`),
`<url>` with a `proxy_from=...` hint.

## Scripting & CI

### What exit codes should I check?

See the [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes) section
in the README. Typical CI pattern: treat `75` (network / TLS, transient) as
retryable, fail hard on `64` (usage) and `70` (bug).

### Can httptap emit Prometheus metrics?

Not out of the box. Use `--metrics-only` and post-process with `awk`/`jq`, or
parse the `--json` export. A dedicated exporter is on the roadmap — track
[issue tracker](https://github.com/ozeranskii/httptap/issues) for updates.

## Python API

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` lives in `httptap.constants`, not the top-level namespace:

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### My custom resolver isn't being called

`HTTPTapAnalyzer` uses the injected resolver only for the diagnostic DNS lookup
timing. Actual connection resolution is still performed by `httpx`/`httpcore`.
To route the real connection through your resolver, implement a custom
`RequestExecutor` as well.

---

## Still stuck?

- Run with `--metrics-only` and include the full output in your report.
- Run with `--json report.json` and attach the report (redact auth headers).
- Confirm the version — `httptap --version` — we only support the latest
  minor.
