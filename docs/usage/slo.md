---
title: SLO Threshold Checking
description: Use --slo to gate requests on per-phase latency budgets in CI, cron, and uptime checks.
---

# SLO Threshold Checking

`httptap --slo` checks measured timings against per-phase latency
budgets and exits with a non-zero code when any budget is exceeded.
This turns a single request into a pass/fail probe suitable for CI
gates, cron-based synthetic monitoring, uptime checks, and
post-deployment smoke tests — without writing a custom shell parser.

## Quick Example

```shell
httptap --slo total=500,ttfb=200 https://api.example.com/health
```

- Exits with `0` when `total_ms ≤ 500` **and** `ttfb_ms ≤ 200`.
- Exits with `4` when any budget is exceeded.
- Continues to print the full waterfall and JSON export regardless of
  the outcome, so investigations are never blocked by the gate.

## Specification Syntax

Pass a comma-separated list of `KEY=MS` pairs to `--slo`:

```
--slo KEY=MS[,KEY=MS]*
```

- `KEY` is one of the supported timing phases (case-insensitive).
- `MS` is a positive finite number of milliseconds (integer or float).
- Whitespace around keys and values is tolerated.

### Supported keys

| Key       | Meaning                                                        |
|-----------|----------------------------------------------------------------|
| `dns`     | DNS resolution time                                            |
| `connect` | TCP connection establishment                                   |
| `tls`     | TLS handshake (`0` for plain HTTP)                             |
| `ttfb`    | Time to first byte (DNS + connect + TLS + server wait)         |
| `wait`    | Server processing time (`ttfb - (dns + connect + tls)`)        |
| `xfer`    | Response body transfer time (`total - ttfb`)                   |
| `total`   | End-to-end request duration                                    |

### Malformed specifications

`--slo` rejects the following and exits with `64` (usage error):

- Empty specification (`--slo ""`).
- Unknown key (`--slo foo=500` → `Unknown SLO key 'foo'`).
- Duplicate key (`--slo total=500,total=600`).
- Non-numeric value (`--slo total=fast`).
- Zero, negative, or non-finite value (`--slo total=0`, `total=nan`,
  `total=inf`).
- Missing `=` (`--slo total500`).

The specific error is printed in a Rich-formatted panel for
interactive use, and in plain text under `--metrics-only`.

## Evaluation Rules

SLO thresholds are evaluated against the **final successful step** of
a request chain:

- Single request → checked against that request.
- Redirect chain (`--follow`) → checked against the terminal response,
  not the intermediate redirects. The assumption is that users care
  about what actually served their request.
- All steps errored → SLO is skipped entirely; the exit code reflects
  the network failure (see below).

A threshold passes when `actual ≤ threshold`. Equality does **not**
count as a violation. Violations are reported in alphabetical order of
their key for deterministic output.

## Exit Codes

`--slo` integrates with the overall exit-code precedence of `httptap`:

| Priority | Condition                               | Exit code |
|:--------:|-----------------------------------------|:---------:|
| 1        | Invalid arguments (bad `--slo` spec)    | `64`      |
| 2        | Network / TLS failure on any step       | `75`      |
| 3        | Internal error                          | `70`      |
| 4        | SLO violation on final successful step  | `4`       |
| 5        | Success                                 | `0`       |

Network errors always take precedence over SLO violations, so a
failing host does not masquerade as a latency regression in a CI log.

## Output Formats

### Rich (default)

After the waterfall and any redirect summary, `httptap` prints a panel
summarising the SLO evaluation:

```
╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms, ttfb≤200ms            │
│ Violations:                                    │
│   • total: 723.4ms > 500ms (+223.4ms)          │
│   • ttfb:  315.2ms > 200ms (+115.2ms)          │
╰────────────────────────────────────────────────╯
```

The panel border and icon match the status: green `✓` for pass, red
`✗` for fail.

### Compact

`--compact` prints one human-readable line per step followed by the
same Rich SLO panel shown under the default mode:

```
Step 1: 200 GET https://api.example.com | dns=3.3ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=900.0ms | 1.2 KB

╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms                        │
│ Violations:                                    │
│   • total: 900.0ms > 500ms (+400.0ms)          │
╰────────────────────────────────────────────────╯
```

### Metrics-only

`--metrics-only` appends SLO tokens to the standard `key=value` line
of the final successful step:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=900.0 ... slo=fail slo_violations=total,ttfb
```

Pass case:

```
Step 1: ... proxy=direct slo=pass
```

Intermediate redirect steps do **not** carry SLO tokens, keeping the
line count unchanged.

### JSON Export

`--json PATH` extends the `summary` block with an `slo` object:

```json
{
  "summary": {
    "total_time_ms": 900.0,
    "final_status": 200,
    "final_url": "https://api.example.com/health",
    "final_bytes": 128,
    "errors": 0,
    "slo": {
      "pass": false,
      "thresholds_ms": { "total": 500.0, "ttfb": 200.0 },
      "violations": [
        {
          "key": "total",
          "threshold_ms": 500.0,
          "actual_ms": 900.0,
          "delta_ms": 400.0
        }
      ]
    }
  }
}
```

Each violation carries the key, the user-supplied threshold, the
measured value, and the overrun. `delta_ms` is strictly positive and
can be used to rank violations by severity.

When no `--slo` flag is passed the `slo` key is absent — the summary
shape is backward compatible with existing consumers.

## Recipes

### Cron-based synthetic monitoring

```cron
* * * * * httptap --slo total=1000,ttfb=500 https://api.example.com/health \
  || curl -X POST https://alerts.example.com/page/oncall
```

### CI gate after deploy

```yaml
- name: Smoke-test staging latency
  run: |
    httptap --slo total=2000,tls=300,ttfb=800 \
      https://staging.example.com/
```

The step fails only on exit `4` or `64`. Network errors (exit `75`)
can be handled separately:

```yaml
- name: Smoke-test staging latency
  id: smoke
  continue-on-error: true
  run: httptap --slo total=2000 https://staging.example.com/
- name: Fail CI only on SLO violation
  if: steps.smoke.outcome == 'failure' && steps.smoke.conclusion != 'success'
  run: |
    if [ "${{ steps.smoke.outputs.exit_code }}" = "4" ]; then
      echo "SLO violation — failing build."
      exit 1
    fi
```

### Kubernetes readiness probe

```yaml
readinessProbe:
  exec:
    command:
      - httptap
      - --slo
      - total=5000
      - http://localhost:8080/healthz
```

### Regression bar

```shell
httptap --slo total=500,ttfb=200 --json regression.json https://prod.example.com/
jq '.summary.slo.violations' regression.json
```

### Multi-host canary

```shell
for host in prod-eu prod-us prod-ap; do
  httptap --slo total=1500 "https://${host}.example.com/health" || echo "${host}: SLO miss"
done
```

## Tips

- Start with `--slo total=<P95 latency>` and add per-phase budgets
  once you have baseline data from `--json` exports.
- `xfer` and `wait` are derived metrics; their sum is bounded by
  `total`. If you set a `total` budget the individual phases are
  implicitly capped.
- Combine with `--timeout`: `--slo` checks latency *after* the
  request completed; `--timeout` hard-kills a request that hangs. You
  usually want both.
- SLO output mirrors
  [`httpstat`'s `--slo`](https://github.com/reorx/httpstat#slo-thresholds)
  format (`slo=pass` / `slo=fail` tokens, exit code `4`), so scripts
  can be used interchangeably.
