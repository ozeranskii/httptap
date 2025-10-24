# Basic Usage

## Command-Line Interface

The `httptap` command-line interface provides various options to customize your HTTP requests and output.

## Syntax

```bash
httptap [OPTIONS] URL
```

## Options

### Request Options

#### `-H, --header`

Add custom HTTP headers to the request. Can be used multiple times.

```bash
httptap -H "Accept: application/json" https://httpbin.io
```

```bash
httptap \
  -H "User-Agent: MyApp/1.0" \
  -H "Authorization: Bearer token123" \
  https://httpbin.io/bearer
```

#### `--follow`

Follow HTTP redirects and show timing for each step in the chain.

```bash
httptap --follow https://httpbin.io/redirect/3
```

By default, httptap does not follow redirects and will stop at the first redirect response (3xx status code).

### Output Options

#### `--compact`

Display results in a compact single-line format, suitable for logging.

```bash
httptap --compact https://httpbin.io
```

Output:

```
Step 1: dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms status=200 bytes=389
```

#### `--metrics-only`

Output raw metrics without formatting, ideal for scripting and automation.

```bash
httptap --metrics-only https://httpbin.io
```

Output:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2
```

#### `--json PATH`

Export full request data to a JSON file.

```bash
httptap --json report.json https://httpbin.io
```

The JSON file contains:

- Timing breakdown for all phases
- Network information (IP address, TLS details, certificate info)
- Response metadata (status, headers, body size)
- Complete redirect chain (when using `--follow`)

#### `--version`

Display the httptap version and Python runtime information.

```bash
httptap --version
```

## HTTP Methods

Currently, httptap issues **GET requests only**. This keeps the interface simple and avoids exposing sensitive request
data in output.

If you need to profile POST/PUT workloads, you can use the Python API to wrap httptap and override the request executor.

## Request Flow

Every httptap request follows these phases:

1. **DNS Resolution** - Domain name lookup
2. **TCP Connect** - Establish TCP connection
3. **TLS Handshake** - Negotiate secure connection (HTTPS only)
4. **Server Wait** - Time between request sent and first response byte
5. **Body Transfer** - Download response body

## Understanding Output

### Rich Mode (Default)

The default rich output displays a waterfall table with:

- Phase name and duration
- Visual progress bar
- Network details (IP, TLS version, certificate info)
- Response metadata (status, size, content-type)

### Timing Breakdown

- **DNS (ms)** - Time to resolve domain to IP address
- **Connect (ms)** - Time to establish TCP connection
- **TLS (ms)** - Time for TLS handshake (HTTPS only)
- **TTFB (ms)** - Time to first byte (includes server processing)
- **Transfer (ms)** - Time to download response body
- **Total (ms)** - End-to-end request duration

### Network Information

- **IP Address** - Resolved IP address and family (IPv4/IPv6)
- **TLS Version** - Protocol version (TLS 1.2, TLS 1.3)
- **Cipher Suite** - Negotiated cipher suite
- **Certificate CN** - Common Name from server certificate
- **Certificate Expiry** - Days until certificate expires

## Examples

### Basic Health Check

```bash
httptap https://httpbin.io/status/200
```

### API Request with Authentication

```bash
httptap \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Accept: application/json" \
  https://httpbin.io/bearer
```

### Follow Redirect Chain

```bash
httptap --follow https://httpbin.io/redirect/3
```

### Export for Analysis

```bash
httptap --json analysis.json --follow https://httpbin.io/redirect/2
```

### Log to File

```bash
httptap --metrics-only https://httpbin.io/delay/1 >> api-latency.log
```

---

## What's Next?

<div class="grid cards" markdown>

-   :material-palette:{ .lg .middle } **[Output Formats](output-formats.md)**

    ---

    Rich, compact, JSON, and metrics modes

-   :material-cog:{ .lg .middle } **[Advanced Features](advanced.md)**

    ---

    Custom components and programmatic usage

-   :material-api:{ .lg .middle } **[API Reference](../api/overview.md)**

    ---

    Extend httptap with protocols

</div>
