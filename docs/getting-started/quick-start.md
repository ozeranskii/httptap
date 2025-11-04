# Quick Start

This guide will walk you through the basic usage of httptap.

## Basic Request

Run a simple HTTP request and display a rich waterfall view:

```bash
httptap https://httpbin.io
```

This will output a detailed timing breakdown showing:

- DNS resolution time
- TCP connection establishment
- TLS handshake (for HTTPS)
- Time to first byte (TTFB)
- Response body transfer time

## Making POST Requests

Send JSON data to an API:

```bash
httptap --data '{"name": "John Doe", "email": "john@example.com"}' https://httpbin.io/post
```

!!! tip "Auto-POST behavior"
    When `--data` is provided without `--method`, httptap automatically switches to POST (similar to curl).

Load data from a file:

```bash
echo '{"title": "New Post", "content": "Hello World"}' > post-data.json
httptap --data @post-data.json https://httpbin.io/post
```

## Using Other HTTP Methods

httptap supports all standard HTTP methods:

**PUT request:**
```bash
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put
```

**PATCH request:**
```bash
httptap --method PATCH --data '{"field": "value"}' https://httpbin.io/patch
```

**DELETE request:**
```bash
httptap --method DELETE https://httpbin.io/delete
```

**HEAD request (headers only):**
```bash
httptap --method HEAD https://httpbin.io/get
```

## Adding Custom Headers

Add custom HTTP headers using the `-H` flag:

```bash
httptap -H "Accept: application/json" https://httpbin.io/json
```

Multiple headers can be added by repeating the flag:

```bash
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://httpbin.io/bearer
```

## Following Redirects

By default, httptap does not follow redirects. To follow redirect chains:

```bash
httptap --follow https://httpbin.io/redirect/3
```

This will show timing information for each step in the redirect chain.

## Compact Output

For single-line output suitable for logging:

```bash
httptap --compact https://httpbin.io
```

Output example:

```
Step 1: dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms status=200 bytes=389
```

## Metrics-Only Mode

Get raw metrics without formatting, perfect for scripts:

```bash
httptap --metrics-only https://httpbin.io
```

Output example:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2
```

## JSON Export

Export full request data to JSON for later analysis:

```bash
httptap --json output.json https://httpbin.io
```

The JSON file will contain:

- Detailed timing for all phases
- Network information (IP, TLS version, certificate details)
- Response metadata (status, headers, body size)
- Full redirect chain (if `--follow` is used)

## Common Use Cases

### API Testing

Test a complete REST API workflow:

```bash
# Create a resource
httptap --data '{"title": "Test Post"}' https://httpbin.io/post

# Update the resource
httptap --method PUT --data '{"title": "Updated Post"}' https://httpbin.io/put

# Partial update
httptap --method PATCH --data '{"published": true}' https://httpbin.io/patch

# Delete the resource
httptap --method DELETE https://httpbin.io/delete
```

### Check API Latency

```bash
httptap --compact https://httpbin.io/status/200
```

### Debug Slow Responses

```bash
httptap https://httpbin.io/delay/3
```

The waterfall view will help identify which phase is causing the delay (DNS, connection, TLS, or server processing).

### Verify TLS Configuration

```bash
httptap https://httpbin.io
```

Check the TLS version, cipher suite, and certificate expiration in the output.

### Performance Benchmarking

Establish performance baselines and track changes over time:

```bash
# Collect 10 samples and calculate statistics
for i in {1..10}; do
  httptap --metrics-only https://httpbin.io/delay/1
done | awk '/total=/ {
  # Extract total value
  for (i = 1; i <= NF; i++) {
    if ($i ~ /^total=/) {
      sub(/^total=/, "", $i)
      sum += $i
      values[++count] = $i
      break
    }
  }
}
END {
  if (count > 0) {
    avg = sum / count
    printf "Average: %.1f ms\n", avg
    printf "Samples: %d\n", count

    # Calculate min/max
    min = values[1]; max = values[1]
    for (i = 1; i <= count; i++) {
      if (values[i] < min) min = values[i]
      if (values[i] > max) max = values[i]
    }
    printf "Min: %.1f ms\n", min
    printf "Max: %.1f ms\n", max
    printf "Range: %.1f ms\n", (max - min)
  }
}'
```

Example output:
```
Average: 1490.0 ms
Samples: 10
Min: 1445.4 ms
Max: 1532.4 ms
Range: 87.0 ms
```

This helps identify performance variability and establish reliable baselines for regression testing.

---

## What's Next?

<div class="grid cards" markdown>

-   :material-console:{ .lg .middle } **[Basic Usage Guide](../usage/basic.md)**

    ---

    Complete command-line reference

-   :material-palette:{ .lg .middle } **[Output Formats](../usage/output-formats.md)**

    ---

    Rich, compact, JSON, and metrics modes

-   :material-api:{ .lg .middle } **[API Reference](../api/overview.md)**

    ---

    Extend httptap with custom components

</div>
