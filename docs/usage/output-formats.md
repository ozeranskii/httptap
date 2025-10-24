# Output Formats

httptap supports multiple output formats to suit different use cases, from interactive troubleshooting to automated
scripting.

## Rich Mode (Default)

The default output format uses the [Rich](https://github.com/Textualize/rich) library to display a beautiful waterfall
table in your terminal.

```bash
httptap https://httpbin.io
```

### Features

- **Colorized output** with syntax highlighting
- **Visual progress bars** for timing phases
- **Structured tables** for easy reading
- **Network details** including IP, TLS version, and certificate info
- **Response metadata** showing status, headers, and body size

### When to Use

- Interactive debugging sessions
- Visual inspection of request performance
- Presentation of timing data to stakeholders

## Compact Mode

Single-line output format ideal for logging and quick comparisons.

```bash
httptap --compact https://httpbin.io
```

### Example Output

```
Step 1: dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms status=200 bytes=389
```

### Features

- **Single line per request** step
- **Human-readable** timing values
- **Essential metrics** only
- **Easy to grep** and filter

### When to Use

- Append to log files
- Quick performance comparisons
- CI/CD pipeline output
- Terminal-friendly summaries

## Metrics-Only Mode

Raw metrics without formatting, optimized for parsing by other tools.

```bash
httptap --metrics-only https://httpbin.io
```

### Example Output

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2
```

### Features

- **Machine-parseable** format
- **Complete metrics** including network details
- **Consistent structure** for easy extraction
- **No colors or formatting** characters

### When to Use

- Scripting and automation
- Data collection for analysis
- Integration with monitoring tools
- Parsing with awk/grep/sed

### Parsing Examples

```bash
# Extract TTFB values
httptap --metrics-only https://httpbin.io/delay/1 | grep -oP 'ttfb=\K[0-9.]+'

# Get all timing metrics
httptap --metrics-only https://httpbin.io/get | \
  awk '{for(i=1;i<=NF;i++){if($i ~ /=/) print $i}}'
```

## JSON Export

Full request data exported as structured JSON for comprehensive analysis.

```bash
httptap --json output.json https://httpbin.io
```

### JSON Structure

```json
{
  "initial_url": "https://httpbin.io",
  "total_steps": 1,
  "steps": [
    {
      "url": "https://httpbin.io",
      "step_number": 1,
      "timing": {
        "dns_ms": 8.947,
        "connect_ms": 96.977,
        "tls_ms": 194.566,
        "ttfb_ms": 445.951,
        "total_ms": 447.344,
        "wait_ms": 145.461,
        "xfer_ms": 1.392,
        "is_estimated": false
      },
      "network": {
        "ip": "44.211.11.205",
        "ip_family": "IPv4",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143
      },
      "response": {
        "status": 200,
        "bytes": 389,
        "content_type": "application/json",
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": null,
        "headers": {}
      },
      "error": null,
      "note": null
    }
  ],
  "summary": {
    "total_time_ms": 447.344,
    "final_status": 200,
    "final_url": "https://httpbin.io",
    "final_bytes": 389,
    "errors": 0
  }
}
```

### Features

- **Complete data export** of all phases
- **Structured format** for easy parsing
- **Redirect chain support** with multiple steps
- **Metadata preservation** (headers, timestamps)
- **Error information** when requests fail

### When to Use

- Post-processing analysis
- Integration with data pipelines
- Long-term performance tracking
- Detailed debugging sessions
- Sharing results with team members

### Processing Examples

Using `jq` to extract specific fields:

```bash
# Get total time
jq '.summary.total_time_ms' output.json

# Extract all TTFB values
jq '.steps[].timing.ttfb_ms' output.json

# Get certificate expiration
jq '.steps[0].network.cert_days_left' output.json

# Filter failed requests
jq 'select(.summary.errors > 0)' output.json
```

## Redirect Chains

When using `--follow`, all output formats include data for each step in the redirect chain.

### Rich Mode

Shows a summary table with totals for the entire chain.

```bash
httptap --follow https://httpbin.io/redirect/3
```

### Compact Mode

Outputs one line per redirect step.

```bash
httptap --follow --compact https://httpbin.io/redirect/3
```

Output:

```
Step 1: dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms status=302 bytes=0
Step 2: dns=2.7ms connect=97.5ms tls=194.0ms ttfb=400.2ms total=400.6ms status=302 bytes=0
Step 3: dns=2.6ms connect=97.4ms tls=197.3ms ttfb=403.2ms total=404.0ms status=200 bytes=389
```

### JSON Export

Includes all steps in the `steps` array with complete timing and metadata.

```bash
httptap --follow --json redirect-chain.json https://httpbin.io/redirect/3
```

## Combining Options

Output format options can be combined with other flags:

```bash
# Follow redirects with compact output
httptap --follow --compact https://httpbin.io/redirect/2

# Export redirect chain to JSON with metrics display
httptap --follow --json chain.json --metrics-only https://bit.ly/example
```

!!! note
    When both `--json` and display modes (`--compact`, `--metrics-only`) are used together, the display mode shows on stdout while JSON is written to the file.

---

## What's Next?

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } **[Advanced Features](advanced.md)**

    ---

    Custom components, monitoring, batch analysis

-   :material-api:{ .lg .middle } **[API Reference](../api/overview.md)**

    ---

    Programmatic usage and extensions

</div>
