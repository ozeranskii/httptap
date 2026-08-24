---
description: 代理、自定义 CA 包、Python API 以及用于 httptap 高级用法的扩展模式。
---

# 高级功能

本指南介绍 httptap 的高级用法模式和自定义选项。

## 自定义 DNS 解析

你可以通过 Python API 提供自定义的 DNS 解析器实现。httptap 始终拨号连接到解析出的 IP 地址（IPv4/IPv6），同时为 `Host` 请求头和 TLS SNI 保留原始主机名。IPv6 字面量会被自动加上方括号，因此自定义解析器只需返回正确的 IP/地址族元组即可。

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver


class CustomDNSResolver(SystemDNSResolver):
    """Custom DNS resolver with hardcoded responses."""

    def resolve(self, host: str, port: int, timeout: float):
        # Override with custom logic
        if host == "httpbin.io":
            return "44.211.11.205", "IPv4", 0.1
        return super().resolve(host, port, timeout)


# Use custom resolver
analyzer = HTTPTapAnalyzer(dns_resolver=CustomDNSResolver())
steps = analyzer.analyze_url("https://httpbin.io")
```

## 自定义 TLS 检查

实现自定义的 TLS 检查逻辑，以提取额外的证书信息。

```python
from httptap import HTTPTapAnalyzer
from httptap.interfaces import TLSInspector
from httptap.models import NetworkInfo


class CustomTLSInspector:
    """Custom TLS inspector with extended certificate checks."""

    def inspect(self, host: str, port: int, timeout: float) -> NetworkInfo:
        # Custom TLS inspection logic
        # Return: NetworkInfo with TLS version, cipher, and certificate data
        ...


analyzer = HTTPTapAnalyzer(tls_inspector=CustomTLSInspector())
```

## 编程化使用

将 httptap 作为 Python 库使用，以集成到你自己的应用程序中。

### 基础分析

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

for step in steps:
    print(f"URL: {step.url}")
    print(f"Status: {step.response.status}")
    print(f"Total time: {step.timing.total_ms:.2f}ms")
```

### 使用自定义请求头

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
headers = {"Authorization": "Bearer token123", "Accept": "application/json"}

steps = analyzer.analyze_url("https://httpbin.io/bearer", headers=headers)
```

### 跟随重定向

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(follow_redirects=True)
steps = analyzer.analyze_url("https://httpbin.io/redirect/3")

print(f"Total steps in redirect chain: {len(steps)}")
```

### 发送请求体

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url(
    "https://httpbin.io/post",
    method=HTTPMethod.POST,
    content=b'{"key": "value"}',
    headers={"Content-Type": "application/json"},
)
```

## 忽略 TLS 校验

在排查预发布环境或使用自签名证书的主机时，你可以跳过 TLS 校验：

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

请求仍会记录 TLS 元数据，但证书错误会被抑制，以便你专注于协议流程。请仅在可信环境中使用此参数，因为它会禁用针对中间人攻击的保护。
客户端会放宽许多加密套件和协议要求（弱哈希、较老的 TLS 版本、较小的 DH 群），使旧式端点更有可能完成握手。某些被 OpenSSL 完全移除的极度弃用算法（例如某些平台上的 RC4、3DES）即使在此模式下仍可能失败。

## 使用代理 { #using-proxies }

通过出站代理（HTTP、HTTPS、SOCKS5/SOCKS5H）转发请求：

```shell
httptap --proxy https://proxy.internal:8443 https://httpbin.io/get
```

```shell
httptap --proxy socks5h://proxy.internal:1080 https://httpbin.io/get
```

忽略所有代理环境变量并直接连接：

```shell
httptap --proxy "" https://httpbin.io/get
```

Rich 输出和 JSON 导出会包含代理 URI 及其来源（例如 `(from arg --proxy)`、`(from env HTTPS_PROXY)`、`(bypassed by env no_proxy)`），以便你确认实际使用的路径。

### 代理协议与 DNS 解析

httptap 支持四种代理协议，每种协议的 DNS 解析行为各不相同：

| Protocol   | DNS Resolved By | Use Case |
|------------|----------------|----------|
| `socks5h://` | 代理服务器 | 隐私保护、企业网络、访问内部 DNS |
| `http://`    | 代理服务器 | 标准 HTTP 代理（CONNECT 方法） |
| `https://`   | 代理服务器 | 与代理之间的加密连接 |
| `socks5://`  | 客户端（本地） | 当你需要控制 DNS 解析时 |

`socks5h` 中的 `h` 后缀代表 "hostname"（一种 curl 约定）。使用 `socks5h://` 时，主机名会被发送到代理，由代理进行解析。使用 `socks5://` 时，客户端在本地解析 DNS，并将 IP 发送给代理。

### 环境变量代理

当未提供 `--proxy` 参数时，httptap 会检查环境变量：

1. `no_proxy` / `NO_PROXY` - 逗号分隔的需要绕过代理的主机列表（小写优先）
2. `https_proxy` / `HTTPS_PROXY` - 用于 HTTPS 请求的代理（小写优先）
3. `http_proxy` / `HTTP_PROXY` - 用于 HTTP 请求的代理（小写优先）
4. `all_proxy` / `ALL_PROXY` - 用于所有协议的回退代理

`--proxy` 参数始终优先于环境变量。

**NO_PROXY 模式：**

- `*` - 对所有主机绕过代理
- `example.com` - 精确主机名匹配
- `.example.com` - example.com 的所有子域名
- `sub.example.com` - 精确子域名匹配

## 自定义 CA 包

对于由私有 CA 签名的内部端点，使用 `--cacert` 提供一个 PEM 包：

```bash
httptap --cacert ~/certs/company-ca.pem https://internal-api.example.com/health
```

CLI 输出会显示 `TLS CA: custom bundle`，以表明使用了非系统信任库。JSON 导出会包含 `network.tls_custom_ca: true`，以便下游工具检测自定义信任配置。该参数与 `--ignore-ssl` 互斥。

## 自定义请求执行器

对于完全自定义的行为，你可以提供你自己的请求执行器。执行器会接收打包在 `RequestOptions` 中的所有参数，因此 httptap 新增的参数仍保持向后兼容。

```python
from httptap import HTTPTapAnalyzer, RequestExecutor, RequestOptions, RequestOutcome


class RecordingExecutor(RequestExecutor):
    def __init__(self) -> None:
        self.last_options: RequestOptions | None = None

    def execute(self, options: RequestOptions) -> RequestOutcome:
        self.last_options = options
        # Call the built-in client (or your preferred HTTP library)
        from httptap.http_client import make_request

        timing, network, response = make_request(
            options.url,
            options.timeout,
            http2=options.http2,
            verify_ssl=options.verify_ssl,
            dns_resolver=options.dns_resolver,
            tls_inspector=options.tls_inspector,
            timing_collector=options.timing_collector,
            force_new_connection=options.force_new_connection,
            headers=options.headers,
        )
        return RequestOutcome(timing=timing, network=network, response=response)


executor = RecordingExecutor()
analyzer = HTTPTapAnalyzer(request_executor=executor)
analyzer.analyze_url("https://httpbin.io/get", headers={"X-Debug": "1"})
print(executor.last_options.headers)  # {'X-Debug': '1'}
```

## 自定义可视化

通过实现 `Visualizer` 协议来创建你自己的可视化。

```python
from httptap.models import StepMetrics


class CustomVisualizer:
    """Custom visualizer for request steps."""

    def render(self, step: StepMetrics) -> None:
        print(f"Step {step.step_number}: {step.timing.total_ms}ms")


# Use custom visualizer
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

visualizer = CustomVisualizer()
for step in steps:
    visualizer.render(step)
```

## 自定义导出格式

实现 JSON 之外的自定义导出格式。

```python
from collections.abc import Sequence
from httptap.models import StepMetrics
import csv


class CSVExporter:
    """Export request data to CSV format."""

    def export(self, steps: Sequence[StepMetrics], initial_url: str, output_path: str) -> None:
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "status", "dns_ms", "connect_ms", "tls_ms", "ttfb_ms", "total_ms"])

            for step in steps:
                writer.writerow(
                    [
                        step.url,
                        step.response.status,
                        step.timing.dns_ms,
                        step.timing.connect_ms,
                        step.timing.tls_ms,
                        step.timing.ttfb_ms,
                        step.timing.total_ms,
                    ]
                )


# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

exporter = CSVExporter()
exporter.export(steps, "https://httpbin.io", "output.csv")
```

## 性能监控

使用 httptap 进行持续的性能监控。

```python
import time
from httptap import HTTPTapAnalyzer


def monitor_endpoint(url: str, interval: int = 60):
    """Monitor endpoint every interval seconds."""
    analyzer = HTTPTapAnalyzer()

    while True:
        steps = analyzer.analyze_url(url)
        step = steps[0]

        # Log metrics
        print(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} - "
            f"TTFB: {step.timing.ttfb_ms:.2f}ms, "
            f"Total: {step.timing.total_ms:.2f}ms, "
            f"Status: {step.response.status}"
        )

        time.sleep(interval)


# Monitor API endpoint every minute
monitor_endpoint("https://httpbin.io/status/200", interval=60)
```

## 批量分析

并发分析多个 URL。

```python
from concurrent.futures import ThreadPoolExecutor
from httptap import HTTPTapAnalyzer


def analyze_url(url: str):
    """Analyze a single URL."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url(url)
    return url, steps[0].timing.total_ms


# List of URLs to analyze
urls = ["https://httpbin.io", "https://httpbin.io/delay/1", "https://httpbin.io/gzip"]

# Analyze concurrently
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(analyze_url, urls))

# Print results
for url, total_ms in results:
    print(f"{url}: {total_ms:.2f}ms")
```

## 错误处理

在分析 URL 时优雅地处理错误。

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io/status/500")

step = steps[0]
if step.has_error:
    print(f"Error: {step.error}")
else:
    print(f"Status: {step.response.status}")
```

## 与测试框架集成

在你的测试套件中使用 httptap 来验证性能要求。

```python
import pytest
from httptap import HTTPTapAnalyzer


def test_api_response_time():
    """Test that API responds within acceptable time."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url("https://httpbin.io/delay/0")

    # Assert TTFB is under 500ms
    assert steps[0].timing.ttfb_ms < 500, f"TTFB too high: {steps[0].timing.ttfb_ms}ms"

    # Assert total time is under 1 second
    assert steps[0].timing.total_ms < 1000, f"Total time too high: {steps[0].timing.total_ms}ms"


def test_tls_configuration():
    """Verify TLS configuration meets security standards."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url("https://httpbin.io")

    # Assert TLS 1.2 or higher
    assert steps[0].network.tls_version in ["TLSv1.2", "TLSv1.3"], (
        f"Insecure TLS version: {steps[0].network.tls_version}"
    )

    # Assert certificate is valid for at least 30 days
    assert steps[0].network.cert_days_left > 30, f"Certificate expiring soon: {steps[0].network.cert_days_left} days"
```

## 特定环境配置

为不同环境分别配置 httptap。

```python
import os
from httptap import HTTPTapAnalyzer

# Environment-specific settings
config = {
    "production": {
        "timeout": 30,
        "follow_redirects": True,
    },
    "staging": {
        "timeout": 60,
        "follow_redirects": True,
    },
    "development": {
        "timeout": 120,
        "follow_redirects": False,
    },
}

env = os.getenv("ENVIRONMENT", "development")
settings = config[env]

analyzer = HTTPTapAnalyzer(
    timeout=settings["timeout"],
    follow_redirects=settings["follow_redirects"],
)
steps = analyzer.analyze_url("https://httpbin.io/status/200")
```

## 调试技巧

### 启用详细日志

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
```

### 检查原始 HTTP 流量

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

# Inspect response headers
step = steps[0]
print("Response headers:")
for key, value in step.response.headers.items():
    print(f"  {key}: {value}")
```

---

## 下一步？

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **[API 参考](../api/overview.md)**

    ---

    详细的接口文档

-   :material-account-group:{ .lg .middle } **[贡献指南](../development/contributing.md)**

    ---

    扩展 httptap 并参与贡献

-   :material-rocket-launch:{ .lg .middle } **[发布流程](../development/release.md)**

    ---

    发布是如何进行的

</div>
