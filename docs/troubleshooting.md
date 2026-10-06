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

### `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed`

The server presented a certificate your trust store doesn't recognize. The
failed step reports an error such as
`Request failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1077)`;
the reason after the colon (self-signed, expired, unable to get local issuer
certificate, hostname mismatch) and the `_ssl.c` line number vary.

- **Self-signed or expired cert on a non-production host** — add `--ignore-ssl`
  (disables validation, use on trusted networks only).
- **Internal CA** — point `--cacert` (alias `--ca-bundle`) at your PEM bundle.
- **System trust store out of date** — update `ca-certificates` on Linux, or
  refresh `certifi` in your Python environment (`uv pip install --upgrade certifi`).

httptap retries only a diagnostic TLS handshake without verification and reports
the presented certificate's CN, SANs, issuer, validity period, and expiry in the
failed step. The request itself still fails verification. Direct diagnostic
probes are skipped when a proxy is active so httptap does not bypass it.

### Certificate shows `cert_days_left: null` or negative

`cert_days_left` is parsed from the leaf certificate's `notAfter` field. A
`null` value means the certificate could not be fetched/parsed — usually TLS
aborted before a cert was received, the target is plain `http://`, or the
request failed before the TLS handshake. `--ignore-ssl` does not clear it: with
verification disabled httptap parses the peer certificate from its DER form,
so `cert_cn`, `cert_days_left`, and the other `cert_*` fields are still
reported. A **negative** value means the certificate is already expired.

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
   in the JSON export; if it says `NO_PROXY`, your host is excluded.

### `Invalid proxy URL`

A malformed `-x/--proxy` value (an unsupported scheme, a missing host, an invalid
or out-of-range port, an unterminated IPv6 literal) is rejected with exit `64`
before any request is made. The same problem in `HTTP_PROXY`, `HTTPS_PROXY` or
`ALL_PROXY` fails the request with a network error (exit `75`) that names the
variable. Both errors show the URL with its password masked. A value without a
scheme, such as `proxy.local:3128`, is valid and treated as `http://`.

### `NO_PROXY` pattern reference

- Host and its subdomains: `api.internal.example` (also matches
  `v1.api.internal.example`)
- Subdomains only: `.internal.example` (matches `foo.internal.example`, not
  `internal.example`)
- Wildcard: `*` (excludes everything)
- Multiple entries: comma-separated, whitespace trimmed, case-insensitive

IP addresses are compared as plain hostnames. CIDR ranges (supported by curl
since 7.86.0) and port-specific entries are **not** supported.

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
hooks report no connect/TLS events for a request (e.g., a transport that does
not emit `httpcore` trace events), httptap falls back to splitting the time
between DNS and the first response byte using heuristics (30% connect, 70% TLS
for HTTPS). The breakdown is still directionally
correct but less precise than the default path.

### Why do two consecutive runs show wildly different `dns_ms`?

The system resolver caches entries. The first request pays the full RTT to
your DNS server; subsequent requests hit the cache (often sub-millisecond).
To bypass caches, supply a custom resolver via the Python API or flush the
local cache (e.g., `sudo dscacheutil -flushcache` on macOS, `resolvectl flush-caches`
on systemd).

### `connect_ms` is much higher than the round-trip time

When a host resolves to several addresses, httptap tries them in order and moves
to the next one when a connection fails. The time spent on the failed attempts
is included in `connect_ms` and `total_ms`, as curl's `time_connect` does, while
`ip` shows the address that answered. Use `--resolve` to measure a single
address.

### Every redirect step shows full `connect_ms` and `tls_ms`

httptap opens a new connection for every request, including each redirect
step, so connections are never reused and every step pays its own TCP connect
and TLS handshake. `ttfb_ms` is counted from the start of DNS resolution, so
it already includes `dns_ms`, `connect_ms`, and `tls_ms`; the server's own
processing time is `wait_ms`. A step whose timings are all `0` failed before a
response arrived — check its `error` field.

## Output

### No colors in my terminal

httptap honors the [`NO_COLOR`](https://no-color.org) convention and Rich's
TTY detection:

- Unset `NO_COLOR` if it's set.
- Piping stdout to a file or another process disables colors; set
  `FORCE_COLOR=1` to override.
- `TERM=dumb` also disables rendering.

### `--metrics-only` stopped showing a `proxy=` field

It didn't — the field is present on every step that received a response. Old
screenshots/examples may predate the change. Failed steps are printed as
`Step N: ERROR - <message>` and carry no metrics or `proxy=` field. Expected
format for a successful step:

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

Possible values:

- `proxy=<url> proxy_from=arg` — proxy set with `-x/--proxy`.
- `proxy=<url> proxy_from=env:<VAR>` — proxy taken from an environment
  variable such as `https_proxy` or `HTTPS_PROXY`.
- `proxy=none proxy_from=env:no_proxy` — the host matched `NO_PROXY`.
- `proxy=disabled proxy_from=arg` — proxies disabled with `--proxy ""`.
- `proxy=direct proxy_from=no_scheme_match` — proxy variables are set, but
  none applies to the URL scheme.
- `proxy=direct` — no proxy configured.

Values are percent-encoded where they would otherwise break `key=value`
tokenization.

## Scripting & CI

### What exit codes should I check?

See the [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes) section
in the README. Typical CI pattern: treat `75` (network / TLS, transient) as
retryable, fail hard on `64` (usage), `70` (bug), `47` (redirect limit
reached with `--follow`), `73` (`--json` or `--har` file not written), `22` (HTTP
4xx/5xx with `--fail`), and `4` (SLO violation if you supplied `--slo`).
When several apply, the highest-priority code wins; see the
[precedence table](usage/slo.md#exit-codes).

### My `--slo` budget is never triggered even though the request is slow.

Check three things:

1. The key you set maps to an actual timing phase. Valid keys are
   `dns`, `connect`, `tls`, `ttfb`, `wait`, `xfer`, `total` — anything
   else rejects the command with exit `64` (SLO Error panel).
2. SLO is evaluated on the **final successful step**, not intermediate
   redirects. If `--follow` bounced through several hops and the last
   step was fast, the overall chain total isn't compared. Use `total`
   against the last request's budget, or aggregate manually from
   `--json` if you need per-step guarantees. When the redirect limit is
   reached, the evaluated step is the last `3xx` response.
3. If every step errored, SLO is skipped entirely — the exit code
   reflects the network failure (usually `75`). No `slo=` token
   appears in `--metrics-only` output in that case.

### Can httptap emit Prometheus metrics?

Yes. Use `--prometheus PATH` to write a node_exporter textfile collector file.
See [Output Formats](usage/output-formats.md#prometheus-textfile-export) for
metric names and labels.

## Python API

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` lives in `httptap.constants`, not the top-level namespace:

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### My custom resolver isn't being called

`HTTPTapAnalyzer` uses the injected resolver for direct connections and local-DNS
SOCKS5 proxies. HTTP, HTTPS, and SOCKS5H proxies resolve the target remotely;
use a custom `RequestExecutor` if you need to change that behavior.

---

## Still stuck?

- Run with `--metrics-only` and include the full output in your report.
- Run with `--json report.json` and attach the report (redact auth headers).
- Confirm the version — `httptap --version` — we only support the latest
  minor.
