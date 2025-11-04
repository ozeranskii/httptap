# httptap

<table>
  <tr>
    <th>Releases</th>
    <th>CI &amp; Analysis</th>
    <th>Project Info</th>
  </tr>
  <tr>
    <td>
      <a href="https://pypi.org/project/httptap/">
        <img src="https://img.shields.io/pypi/v/httptap?color=3775A9&label=PyPI&logo=pypi" alt="PyPI" />
      </a><br />
      <a href="https://pypi.org/project/httptap/">
        <img src="https://img.shields.io/pypi/pyversions/httptap?logo=python" alt="Python Versions" />
      </a>
    </td>
    <td>
      <a href="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml">
        <img src="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml/badge.svg" alt="CI" />
      </a><br />
      <a href="https://github.com/ozeranskii/httptap/actions/workflows/codeql.yml">
        <img src="https://github.com/ozeranskii/httptap/actions/workflows/codeql.yml/badge.svg" alt="CodeQL" />
      </a><br />
      <a href="https://codecov.io/github/ozeranskii/httptap">
        <img src="https://codecov.io/github/ozeranskii/httptap/graph/badge.svg?token=OFOHOI1X5J" alt="Coverage" />
      </a>
    </td>
    <td>
      <a href="https://github.com/astral-sh/uv">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="Build Tool" />
      </a><br />
      <a href="https://github.com/astral-sh/ruff">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Lint" />
      </a><br />
      <a href="https://github.com/ozeranskii/httptap/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/ozeranskii/httptap?color=2E7D32" alt="License" />
      </a>
    </td>
  </tr>
</table>

`httptap` is a rich-powered CLI that dissects an HTTP request into every meaningful phase-DNS, TCP connect, TLS
handshake, server wait, and body transfer and renders the results as a timeline table, compact summary, or
machine-friendly metrics. It is designed for interactive troubleshooting, regression analysis, and recording of
performance baselines.

---

## Highlights

- **Phase-by-phase timing** – precise measurements built from httpcore trace hooks (with sane fallbacks when metal-level
  data is unavailable).
- **All HTTP methods** – GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS with request body support.
- **Request body support** – send JSON, XML, or any data inline or from file with automatic Content-Type detection.
- **IPv4/IPv6 aware** – the resolver and TLS inspector report both the address and its family.
- **TLS insights** – certificate CN, expiry countdown, cipher suite, and protocol version are captured automatically.
- **Multiple output modes** – rich waterfall view, compact single-line summaries, or `--metrics-only` for scripting.
- **JSON export** – persist full step data (including redirect chains) for later processing.
- **Extensible** – clean Protocol interfaces for DNS, TLS, timing, visualization, and export so you can plug in custom
  behavior.

> 📣 <strong>Exclusive for httptap users:</strong> Save 50% on <a href="https://gitkraken.cello.so/vY8yybnplsZ"><strong>GitKraken Pro</strong></a>. Bundle GitKraken Client, GitLens for VS Code, and powerful CLI tools to accelerate every repo workflow.

---

## Requirements

- Python 3.10-3.14 (CPython)
- macOS, Linux, or Windows (tested on CPython)
- No system dependencies beyond standard networking
- Code must follow the Google Python Style Guide (docstrings, formatting). See
  [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

---

## Installation

### Using Homebrew (macOS/Linux)

```shell
brew install httptap
```

### Using `uv`

```shell
uv pip install httptap
```

### Using `pip`

```shell
pip install httptap
```

### From source

```shell
git clone https://github.com/ozeranskii/httptap.git
cd httptap
uv venv
uv pip install .
```

---

### Shell completions

#### Homebrew Installation

If you installed httptap via Homebrew, shell completions are automatically available after installation. Just restart your shell:

```shell
# Restart your shell or reload configuration
exec $SHELL
```

Homebrew automatically installs completions to:
- Bash: `$(brew --prefix)/etc/bash_completion.d/`
- Zsh: `$(brew --prefix)/share/zsh/site-functions/`

#### Python Package Installation

If you installed httptap via `pip` or `uv`, you need to install the optional completion extras:

1. Install the completion extras:

   ```shell
   uv pip install "httptap[completion]"
   # or
   pip install "httptap[completion]"
   ```

2. Activate your virtual environment:

   ```shell
   source .venv/bin/activate
   ```

3. Run the global activation script for argument completions:

   ```shell
   activate-global-python-argcomplete
   ```

4. Restart your shell. Completions should now work in both bash and zsh.

**Note:** The global activation script provides argument completions for bash and zsh only. Other shells are not covered by the script and must be configured separately.

#### Usage Examples

Once completions are installed, you can use `Tab` to autocomplete commands and options:

```shell
# Complete command options
httptap --<TAB>
# Shows: --follow, --timeout, --no-http2, --ignore-ssl, --proxy, --header, --compact, --metrics-only, --json, --version, --help

# Complete after typing partial option
httptap --fol<TAB>
# Completes to: httptap --follow

# Complete multiple options
httptap --follow --time<TAB>
# Completes to: httptap --follow --timeout
```

---

## Quick Start

### Basic GET Request

Run a single request and display a rich waterfall:

```shell
httptap https://httpbin.io/get
```

### POST Request with Data

Send JSON data (auto-detects Content-Type):

```shell
httptap https://httpbin.io/post --data '{"name": "John", "email": "john@example.com"}'
```

**Note:** When `--data` is provided without `--method`, httptap automatically switches to POST (similar to curl).

Load data from file:

```shell
httptap https://httpbin.io/post --data @payload.json
```

Explicitly specify method (bypasses auto-POST):

```shell
httptap https://httpbin.io/post --method POST --data '{"status": "active"}'
```

### Other HTTP Methods

PUT request:

```shell
httptap https://httpbin.io/put --method PUT --data '{"key": "value"}'
```

PATCH request:

```shell
httptap https://httpbin.io/patch --method PATCH --data '{"field": "updated"}'
```

DELETE request:

```shell
httptap https://httpbin.io/delete --method DELETE
```

### Custom Headers

Add custom headers (repeat `-H` for multiple values):

```shell
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer super-secret" \
  https://httpbin.io/bearer
```

### Redirects and JSON Export

Follow redirect chains and dump metrics to JSON:

```shell
httptap --follow --json out/report.json https://httpbin.io/redirect/2
```

### Output Modes

Collect compact (single-line) timings suitable for logs:

```shell
httptap --compact https://httpbin.io/get
```

Expose raw metrics for scripts:

```shell
httptap --metrics-only https://httpbin.io/get | tee timings.log
```

### Advanced Usage

Programmatic users can inject a custom executor for advanced scenarios. The
default analyzer accepts either a modern `RequestExecutor` implementation or a
legacy callable wrapped with `CallableRequestExecutor`, so new request flags
remain backward compatible.

Bypass TLS verification when troubleshooting self-signed endpoints:

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

The flag disables certificate validation and relaxes many handshake
constraints so that legacy endpoints (expired/self-signed/hostname
mismatches, weak hashes, older TLS versions) still complete. Some
algorithms removed from modern OpenSSL builds (for example RC4 or
3DES) may remain unavailable. Use this mode only on trusted networks.

Route traffic through an HTTP/SOCKS proxy (explicit override takes precedence over env vars `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`):

```shell
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get
```

The output and JSON export include the proxy URI so you can confirm what
path was used.

---


## Releasing

### Prerequisites

- GitHub Environment `pypi` must be configured in repository settings
- PyPI Trusted Publishing configured for `ozeranskii/httptap`

### Steps

1. Trigger the **Release** workflow from GitHub Actions:
   - Provide exact version (e.g., `0.3.0`), OR
   - Select bump type: `patch`, `minor`, or `major`
2. The workflow will:
   - Update version in `pyproject.toml` using `uv version`
   - Generate changelog with `git-cliff` and update `CHANGELOG.md`
   - Commit changes and create a git tag
   - Run full test suite on the tagged version
   - Build wheel and source distribution
   - Publish to PyPI via Trusted Publishing (OIDC)
   - Create GitHub Release with generated notes

---

## Sample Output

![sample-output.png](docs/assets/sample-output.png)

The redirect summary includes a total row:
![sample-follow-redirects-output.png](docs/assets/sample-follow-redirects-output.png)

---

## JSON Export Structure

```json
{
  "initial_url": "https://httpbin.io/redirect/2",
  "total_steps": 3,
  "steps": [
    {
      "url": "https://httpbin.io/redirect/2",
      "step_number": 1,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 8.947208058089018,
        "connect_ms": 96.97712492197752,
        "tls_ms": 194.56583401188254,
        "ttfb_ms": 445.9513339679688,
        "total_ms": 447.3437919514254,
        "wait_ms": 145.46116697601974,
        "xfer_ms": 1.392457983456552,
        "is_estimated": false
      },
      "network": {
        "ip": "44.211.11.205",
        "ip_family": "IPv4",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "tls_verified": true
      },
      "response": {
        "status": 302,
        "bytes": 0,
        "content_type": null,
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": "/relative-redirect/1",
        "headers": {
          "access-control-allow-credentials": "true",
          "access-control-allow-origin": "*",
          "location": "/relative-redirect/1",
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-length": "0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    },
    {
      "url": "https://httpbin.io/relative-redirect/1",
      "step_number": 2,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 2.6895420160144567,
        "connect_ms": 97.51500003039837,
        "tls_ms": 193.99016606621444,
        "ttfb_ms": 400.2034160075709,
        "total_ms": 400.60841606464237,
        "wait_ms": 106.00870789494365,
        "xfer_ms": 0.4050000570714474,
        "is_estimated": false
      },
      "network": {
        "ip": "44.211.11.205",
        "ip_family": "IPv4",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "tls_verified": true
      },
      "response": {
        "status": 302,
        "bytes": 0,
        "content_type": null,
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": "/get",
        "headers": {
          "access-control-allow-credentials": "true",
          "access-control-allow-origin": "*",
          "location": "/get",
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-length": "0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    },
    {
      "url": "https://httpbin.io/get",
      "step_number": 3,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 2.643457963131368,
        "connect_ms": 97.36416593659669,
        "tls_ms": 197.3062080796808,
        "ttfb_ms": 403.2038329169154,
        "total_ms": 403.9644579170272,
        "wait_ms": 105.89000093750656,
        "xfer_ms": 0.7606250001117587,
        "is_estimated": false
      },
      "network": {
        "ip": "52.70.33.41",
        "ip_family": "IPv4",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "tls_verified": true
      },
      "response": {
        "status": 200,
        "bytes": 389,
        "content_type": "application/json; charset=utf-8",
        "server": null,
        "date": "2025-10-23T19:20:37+00:00",
        "location": null,
        "headers": {
          "access-control-allow-credentials": "true",
          "access-control-allow-origin": "*",
          "content-type": "application/json; charset=utf-8",
          "date": "Thu, 23 Oct 2025 19:20:37 GMT",
          "content-length": "389"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    }
  ],
  "summary": {
    "total_time_ms": 1251.916665933095,
    "final_status": 200,
    "final_url": "https://httpbin.io/get",
    "final_bytes": 389,
    "errors": 0
  }
}
```

## Metrics-only scripting

```shell
httptap --metrics-only https://httpbin.io/get
```

```terminaloutput
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4
tls_version=TLSv1.2
```

---

## Advanced Usage

### Custom Implementations

Swap in your own resolver or TLS inspector (anything satisfying the Protocol from `httptap.interfaces`):

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver


class HardcodedDNS(SystemDNSResolver):
    def resolve(self, host, port, timeout):
        return "93.184.216.34", "IPv4", 0.1


analyzer = HTTPTapAnalyzer(dns_resolver=HardcodedDNS())
steps = analyzer.analyze_url("https://httpbin.io")
```

---

## Development

```shell
git clone https://github.com/ozeranskii/httptap.git
cd httptap
uv sync
uv run pytest
uv run ruff check
uv run ruff format .
```

Tests expect outbound network access; you can mock `SystemDNSResolver` / `SocketTLSInspector` when running offline.

---

## Contributing

1. Fork and clone the repo.
2. Create a feature branch.
3. Run `pytest` and `ruff` before committing.
4. Submit a pull request with a clear description and any relevant screenshots or benchmarks.

We welcome bug reports, feature proposals, doc improvements, and creative new visualizations or exporters.

---

## License

Apache License 2.0 © Sergei Ozeranskii. See [LICENSE](https://github.com/ozeranskii/httptap/blob/main/LICENSE) for
details.

---

## Acknowledgements

- Built on the shoulders of fantastic
  libraries: [httpx](https://www.python-httpx.org/), [httpcore](https://github.com/encode/httpcore),
  and [Rich](https://github.com/Textualize/rich).
- Inspired by the tooling ecosystem around web performance (e.g., DevTools waterfalls, `curl --trace`).
- Special thanks to everyone who opens issues, shares ideas, or contributes patches.
