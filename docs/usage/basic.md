# Basic Usage

## Command-Line Interface

The `httptap` command-line interface provides various options to customize your HTTP requests and output.

## Syntax

```bash
httptap [OPTIONS] URL
```

## Options

### Request Options

#### `--method METHOD`

Specify the HTTP method to use. Supported methods: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.

```bash
httptap --method POST https://httpbin.io/post
```

**Default behavior:**
- Without `--data`: defaults to GET
- With `--data` but no `--method`: auto-switches to POST (similar to curl)
- With explicit `--method`: respects the specified method

#### `-d, --data DATA`

Send request body data. Can be inline string or file reference using `@filename` syntax.

**Inline JSON data:**
```bash
httptap --data '{"name": "John", "email": "john@example.com"}' https://httpbin.io/post
```

**Load from file:**
```bash
httptap --data @payload.json https://httpbin.io/post
```

**Auto-detection:**
- Content-Type is automatically detected (JSON, XML, plain text)
- File extension is checked first (.json, .xml, .txt)
- Falls back to JSON validation

**Examples with different methods:**
```bash
# POST (auto-detected when --data is present)
httptap --data '{"key": "value"}' https://httpbin.io/post

# PUT
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put

# PATCH
httptap --method PATCH --data '{"field": "modified"}' https://httpbin.io/patch

# Explicit GET with body (uncommon, triggers warning)
httptap --method GET --data 'query-data' https://httpbin.io/get
```

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

Follow HTTP redirects and show timing for each step in the chain (max 10 redirects).

```bash
httptap --follow https://httpbin.io/redirect/3
```

By default, httptap does not follow redirects and will stop at the first redirect response (3xx status code).

#### `--timeout SECONDS`

Abort the request chain if total elapsed time exceeds the specified number of seconds.

```bash
httptap --timeout 10 https://httpbin.io/delay/2
```

Default timeout is 20 seconds.

#### `--no-http2`

Disable HTTP/2 negotiation and force HTTP/1.1 connections.

```bash
httptap --no-http2 https://httpbin.io
```

By default, HTTP/2 is enabled if the server supports it.

#### `--ignore-ssl`

Disable TLS certificate verification. Useful for debugging self-signed hosts or expired certificates.

```bash
httptap --ignore-ssl https://self-signed.badssl.com
```

!!! warning
    Use this option only on trusted networks. It disables certificate validation and relaxes handshake constraints.

#### `--proxy URL`

Route requests through the specified proxy. Supports HTTP, HTTPS, SOCKS5, and SOCKS5H protocols.

```bash
# HTTP proxy
httptap --proxy http://proxy.local:8080 https://httpbin.io/get

# SOCKS5 proxy
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get
```

The proxy setting takes precedence over environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`).

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

httptap supports all standard HTTP methods:

- **GET** - Retrieve resource (default when no `--data` is provided)
- **POST** - Create/submit resource (auto-selected when `--data` is provided)
- **PUT** - Replace resource
- **PATCH** - Partially update resource
- **DELETE** - Remove resource
- **HEAD** - Get headers only
- **OPTIONS** - Query allowed methods

### Method Selection Logic

1. **Explicit method:** `--method` always takes precedence
2. **Auto-POST:** When `--data` is present without `--method`, defaults to POST
3. **Default GET:** Without `--data` or `--method`, uses GET

### Examples by Use Case

**API Testing:**
```bash
# Create resource
httptap --data '{"title": "New Post"}' https://httpbin.io/post

# Update resource
httptap --method PUT --data '{"title": "Updated"}' https://httpbin.io/put

# Partial update
httptap --method PATCH --data '{"status": "published"}' https://httpbin.io/patch

# Delete resource
httptap --method DELETE https://httpbin.io/delete
```

**Health Checks:**
```bash
# Quick check (headers only)
httptap --method HEAD https://httpbin.io/status/200

# Full response
httptap https://httpbin.io/status/200
```

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
