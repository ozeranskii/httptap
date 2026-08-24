---
description: プロキシ、カスタム CA バンドル、Python API、そして httptap の高度な利用のための拡張パターン。
---

# 高度な機能

このガイドでは、httptap の高度な利用パターンとカスタマイズオプションについて説明します。

## カスタムな名前解決

Python API を使うことで、カスタムの DNS リゾルバー実装を提供できます。httptap は常に解決された IP アドレス（IPv4/IPv6）にダイヤルしつつ、`Host` ヘッダーと TLS SNI のために元のホスト名を保持します。IPv6 リテラルは自動的にブラケットで囲まれるため、カスタムリゾルバーは正しい IP／ファミリのタプルを返すだけで済みます。

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

## カスタムな TLS インスペクション

追加の証明書情報を抽出するために、カスタムの TLS インスペクションロジックを実装します。

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

## プログラムからの利用

httptap を Python ライブラリとして使用し、アプリケーションに統合します。

### 基本的な分析

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

for step in steps:
    print(f"URL: {step.url}")
    print(f"Status: {step.response.status}")
    print(f"Total time: {step.timing.total_ms:.2f}ms")
```

### カスタムヘッダー付き

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
headers = {"Authorization": "Bearer token123", "Accept": "application/json"}

steps = analyzer.analyze_url("https://httpbin.io/bearer", headers=headers)
```

### リダイレクトの追跡

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(follow_redirects=True)
steps = analyzer.analyze_url("https://httpbin.io/redirect/3")

print(f"Total steps in redirect chain: {len(steps)}")
```

### リクエストボディの送信

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

## TLS 検証の無視

ステージング環境や自己署名証明書を持つホストのトラブルシューティングでは、TLS 検証をスキップできます:

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

リクエストは引き続き TLS メタデータを記録しますが、証明書エラーは抑制されるため、プロトコルフローに集中できます。このフラグは man-in-the-middle 攻撃に対する保護を無効にするため、信頼できる環境でのみ使用してください。
クライアントは多くの暗号とプロトコルの要件（弱いハッシュ、古い TLS バージョン、小さい DH グループ）を緩和し、レガシーなエンドポイントがハンドシェイクを完了しやすくなるようにします。OpenSSL が完全に削除した極端に非推奨のアルゴリズム（例: 一部のプラットフォームでの RC4、3DES）は、このモードでも失敗する場合があります。

## プロキシの使用 { #using-proxies }

アウトバウンドのプロキシ（HTTP、HTTPS、SOCKS5/SOCKS5H）経由でリクエストを送ります:

```shell
httptap --proxy https://proxy.internal:8443 https://httpbin.io/get
```

```shell
httptap --proxy socks5h://proxy.internal:1080 https://httpbin.io/get
```

すべてのプロキシ環境変数を無視して直接接続する:

```shell
httptap --proxy "" https://httpbin.io/get
```

リッチ出力と JSON エクスポートには、プロキシ URI とそのソース（例: `(from arg --proxy)`、`(from env HTTPS_PROXY)`、`(bypassed by env no_proxy)`）が含まれるため、どの経路が使われたかを確認できます。

### プロキシプロトコルと名前解決

httptap は 4 つのプロキシプロトコルをサポートしており、それぞれ名前解決の挙動が異なります:

| プロトコル   | DNS の解決者 | ユースケース |
|------------|----------------|----------|
| `socks5h://` | プロキシサーバー | プライバシー、企業ネットワーク、内部 DNS へのアクセス |
| `http://`    | プロキシサーバー | 標準的な HTTP プロキシ（CONNECT メソッド） |
| `https://`   | プロキシサーバー | プロキシへの暗号化された接続 |
| `socks5://`  | クライアント（ローカル） | 名前解決を制御する必要がある場合 |

`socks5h` の `h` サフィックスは "hostname"（curl の慣例）を表します。`socks5h://` では、ホスト名がプロキシに送信され、プロキシがそれを解決します。`socks5://` では、クライアントがローカルで DNS を解決し、IP をプロキシに送信します。

### 環境変数によるプロキシ

`--proxy` フラグが指定されない場合、httptap は環境変数をチェックします:

1. `no_proxy` / `NO_PROXY` - バイパスするホストのカンマ区切りリスト（小文字が優先）
2. `https_proxy` / `HTTPS_PROXY` - HTTPS リクエスト用のプロキシ（小文字が優先）
3. `http_proxy` / `HTTP_PROXY` - HTTP リクエスト用のプロキシ（小文字が優先）
4. `all_proxy` / `ALL_PROXY` - すべてのプロトコル用のフォールバックプロキシ

`--proxy` フラグは常に環境変数よりも優先されます。

**NO_PROXY のパターン:**

- `*` - すべてのホストでプロキシをバイパスする
- `example.com` - 完全なホスト名の一致
- `.example.com` - example.com のすべてのサブドメイン
- `sub.example.com` - 完全なサブドメインの一致

## カスタム CA バンドル

プライベート CA によって署名された内部エンドポイントのために、`--cacert` で PEM バンドルを指定します:

```bash
httptap --cacert ~/certs/company-ca.pem https://internal-api.example.com/health
```

CLI 出力には `TLS CA: custom bundle` と表示され、システム以外のトラストストアが使用されたことを示します。JSON エクスポートには `network.tls_custom_ca: true` が含まれるため、下流のツールがカスタムトラストを検出できます。このフラグは `--ignore-ssl` とは相互排他です。

## カスタムリクエストエグゼキューター

完全にカスタマイズされた挙動のために、独自のリクエストエグゼキューターを提供できます。エグゼキューターはすべてのパラメーターを `RequestOptions` にパッケージ化した形で受け取るため、httptap によって追加される新しいフラグは後方互換のままです。

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

## カスタムな可視化

`Visualizer` プロトコルを実装して、独自の可視化を作成します。

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

## カスタムなエクスポート形式

JSON 以外のカスタムなエクスポート形式を実装します。

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

## パフォーマンス監視

httptap を継続的なパフォーマンス監視に使用します。

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

## バッチ分析

複数の URL を並行して分析します。

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

## エラー処理

URL を分析する際に、エラーを適切に処理します。

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

## テストフレームワークとの統合

パフォーマンス要件を検証するために、テストスイートで httptap を使用します。

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

## 環境ごとの設定

さまざまな環境に合わせて httptap を設定します。

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

## デバッグのヒント

### 詳細なロギングを有効にする

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
```

### 生の HTTP トラフィックを検査する

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

## 次のステップ

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **[API リファレンス](../api/overview.md)**

    ---

    詳細なインターフェースのドキュメント

-   :material-account-group:{ .lg .middle } **[コントリビューションガイド](../development/contributing.md)**

    ---

    httptap を拡張してコントリビュートする

-   :material-rocket-launch:{ .lg .middle } **[リリースプロセス](../development/release.md)**

    ---

    リリースの仕組み

</div>
