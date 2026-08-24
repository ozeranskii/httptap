---
description: デバッグや自動化に合わせて、リッチ、コンパクト、メトリクスのみ、JSON の各出力モードを使い分けます。
---

# 出力形式

httptap は、インタラクティブなトラブルシューティングから自動化されたスクリプティングまで、さまざまなユースケースに合わせた複数の出力形式をサポートしています。

## リッチモード（デフォルト）

デフォルトの出力形式は [Rich](https://github.com/Textualize/rich) ライブラリを使用し、ターミナルに美しいウォーターフォールテーブルを表示します。

```bash
httptap https://httpbin.io
```

### 機能

- シンタックスハイライト付きの**色付き出力**
- タイミングフェーズの**視覚的なプログレスバー**
- 読みやすい**構造化されたテーブル**
- IP、TLS バージョン、証明書情報を含む**ネットワークの詳細**
- ステータス、ヘッダー、ボディサイズを示す**レスポンスのメタデータ**

### 使いどころ

- インタラクティブなデバッグセッション
- リクエストパフォーマンスの視覚的な確認
- 関係者へのタイミングデータの提示

## コンパクトモード

ステップごとに人間が読みやすい 1 行で、ターミナルログやリダイレクトチェーンのトレース向けに設計されています。

```bash
httptap --compact https://httpbin.io/get
```

### 出力例

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

### 機能

- **ステップごとに 1 行** — 最初に HTTP ステータス、続いてメソッドと URL、次にフェーズごとのタイミング、そして人間が読みやすいボディサイズ。
- **タイミングには `ms` サフィックスが付く**ため、散文的なログエントリと並べても自然に読めます。
- **レスポンスサイズ**は適切な単位（`B`、`KB`、`MB`）で書式設定されます。
- **リダイレクトの要約テーブル**は引き続きステップごとの行の後に出力されるため、チェーン全体の形が見えたままになります。

### 使いどころ

- ログファイルへの追記
- 手早いパフォーマンス比較
- URL とステータスを確認したい CI / CD パイプラインの出力
- 完全なウォーターフォールでは情報が多すぎる場合の、ターミナルに優しい要約

## メトリクスのみモード

書式なしの生のメトリクスで、他のツールによる解析に最適化されています。

```bash
httptap --metrics-only https://httpbin.io
```

### 出力例

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

### 機能

- **機械で解析可能な**形式
- ネットワークの詳細を含む**完全なメトリクス**
- 抽出しやすい**一貫した構造**
- **色や書式**文字を含まない

### 使いどころ

- スクリプティングと自動化
- 分析のためのデータ収集
- 監視ツールとの統合
- awk/grep/sed による解析

### 解析の例

```bash
# TTFB 値を抽出する
httptap --metrics-only https://httpbin.io/delay/1 | grep -oP 'ttfb=\K[0-9.]+'

# すべてのタイミングメトリクスを取得する
httptap --metrics-only https://httpbin.io/get | \
  awk '{for(i=1;i<=NF;i++){if($i ~ /=/) print $i}}'
```

## JSON エクスポート

包括的な分析のために、完全なリクエストデータを構造化された JSON としてエクスポートします。

```bash
httptap --json output.json https://httpbin.io
```

### JSON の構造

```json
{
  "initial_url": "https://httpbin.io",
  "total_steps": 1,
  "steps": [
    {
      "url": "https://httpbin.io",
      "step_number": 1,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
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
        "http_version": "HTTP/2.0",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "cert_sans": ["httpbin.io", "*.httpbin.io"],
        "cert_issuer": "WE1",
        "cert_serial": "05BB0F0AA84C8FECE0E72D805BA7A5D2B",
        "cert_not_before": "2025-04-01T00:00:00+00:00",
        "cert_not_after": "2025-09-01T00:00:00+00:00",
        "tls_verified": true,
        "tls_custom_ca": null,
        "proxy_url": null,
        "proxy_source": null
      },
      "response": {
        "status": 200,
        "bytes": 389,
        "content_type": "application/json",
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": null,
        "headers": {
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-type": "application/json",
          "server": "gunicorn/19.9.0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
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

### 機能

- 全フェーズの**完全なデータエクスポート**
- 解析しやすい**構造化された形式**
- 複数ステップによる**リダイレクトチェーンのサポート**
- **メタデータの保持**（ヘッダー、タイムスタンプ）
- リクエスト失敗時の**エラー情報**

### 使いどころ

- 後処理による分析
- データパイプラインとの統合
- 長期的なパフォーマンス追跡
- 詳細なデバッグセッション
- チームメンバーとの結果共有

### 処理の例

`jq` を使って特定のフィールドを抽出する:

```bash
# 合計時間を取得する
jq '.summary.total_time_ms' output.json

# すべての TTFB 値を抽出する
jq '.steps[].timing.ttfb_ms' output.json

# 証明書の有効期限を取得する
jq '.steps[0].network.cert_days_left' output.json

# 失敗したリクエストをフィルタリングする
jq 'select(.summary.errors > 0)' output.json
```

## リダイレクトチェーン

`--follow` を使用すると、すべての出力形式にリダイレクトチェーンの各ステップのデータが含まれます。

### リッチモード

チェーン全体の合計を含む要約テーブルを表示します。

```bash
httptap --follow https://httpbin.io/redirect/3
```

### コンパクトモード

リダイレクトステップごとに 1 行を出力し、続いてリダイレクトチェーンの要約テーブルを出力します。

```bash
httptap --follow --compact https://httpbin.io/redirect/2
```

出力:

```
Step 1: 302 GET https://httpbin.io/redirect/2 | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 0 B
Step 2: 302 GET https://httpbin.io/relative-redirect/1 | dns=2.7ms connect=97.5ms tls=194.0ms ttfb=400.2ms total=400.6ms | 0 B
Step 3: 200 GET https://httpbin.io/get | dns=2.6ms connect=97.4ms tls=197.3ms ttfb=403.2ms total=404.0ms | 389 B
```

### JSON エクスポート

`steps` 配列にすべてのステップを含め、完全なタイミングとメタデータを付与します。

```bash
httptap --follow --json redirect-chain.json https://httpbin.io/redirect/3
```

## オプションの組み合わせ

出力形式のオプションは他のフラグと組み合わせられます:

```bash
# コンパクト出力でリダイレクトを追跡する
httptap --follow --compact https://httpbin.io/redirect/2

# メトリクス表示でリダイレクトチェーンを JSON にエクスポートする
httptap --follow --json chain.json --metrics-only https://bit.ly/example
```

!!! note
    `--json` と表示モード（`--compact`、`--metrics-only`）を同時に使用した場合、表示モードは標準出力に表示され、JSON はファイルに書き込まれます。

---

## SLO しきい値のオーバーレイ

`--slo KEY=MS[,KEY=MS...]` は、最終的に成功したリクエストに対して評価された合否判定を、すべての出力モードに付加します。

- **リッチモード** — ウォーターフォールの後に枠付きのパネルが出力されます。ボーダーは合格で緑、不合格で赤になり、各違反が実測値、しきい値、超過量（ミリ秒単位）とともに列挙されます。
- **コンパクトモード** — 上記のリッチモードと同じように動作します。SLO パネルは引き続き 1 行のステップ要約の後に出力されます。
- **メトリクスのみ** — 最終的に成功したステップの行に `slo=pass` または `slo=fail slo_violations=<keys>` のトークンが追加されます。中間のリダイレクトステップは変更されません。
- **JSON** — `summary.slo` に `pass`、`thresholds_ms`、`violations[]`（それぞれ `key`、`threshold_ms`、`actual_ms`、`delta_ms` を含む）が含まれます。`--slo` が指定されない場合は存在しません。

違反があると `httptap` は完全な出力をレンダリングしつつ終了コード `4` で終了するため、事後分析のための証拠が保持されます。

仕様の文法、評価ルール、終了コードの優先順位、CI / cron のレシピについては、専用の [SLO しきい値チェック](slo.md) ページを参照してください。

---

## 次のステップ

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } **[高度な機能](advanced.md)**

    ---

    カスタムコンポーネント、監視、バッチ分析

-   :material-api:{ .lg .middle } **[API リファレンス](../api/overview.md)**

    ---

    プログラムからの利用と拡張

</div>
