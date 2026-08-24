---
description: 基本的なリクエストと一般的なコマンドライン例を通じて httptap を使い始める。
---

# クイックスタート

このガイドでは、httptap の基本的な使い方を順を追って説明します。

## 基本的なリクエスト

シンプルな HTTP リクエストを実行し、リッチなウォーターフォールビューを表示します:

```bash
httptap https://httpbin.io
```

これにより、以下を示す詳細なタイミングの内訳が出力されます:

- 名前解決の時間
- TCP 接続の確立
- TLS ハンドシェイク（HTTPS の場合）
- 最初のバイトまでの時間（TTFB）
- レスポンスボディの転送時間

## POST リクエストを行う

API に JSON データを送信します:

```bash
httptap --data '{"name": "John Doe", "email": "john@example.com"}' https://httpbin.io/post
```

!!! tip "自動 POST の挙動"
    `--data` が `--method` なしで指定された場合、httptap は自動的に POST に切り替わります（curl と同様）。

!!! tip "curl 互換フラグ"
    最も一般的な curl のフラグはそのまま使えます。HTTP メソッドには `-X/--request`、リダイレクトを追跡するには `-L/--location`、タイムアウトには `-m/--max-time`、証明書検証を無効にするには `-k/--insecure`、プロキシには `-x`、HTTP/1.1 を強制するには `--http1.1`（`--no-http2` と同等）を使用します。すべての curl オプションがサポートされているわけではないので、コマンドを置き換える際にはこれらの共通フラグにとどめてください。

ファイルからデータを読み込みます:

```bash
echo '{"title": "New Post", "content": "Hello World"}' > post-data.json
httptap --data @post-data.json https://httpbin.io/post
```

## その他の HTTP メソッドを使う

httptap はすべての標準的な HTTP メソッドをサポートしています:

**PUT リクエスト:**
```bash
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put
```

**PATCH リクエスト:**
```bash
httptap --method PATCH --data '{"field": "value"}' https://httpbin.io/patch
```

**DELETE リクエスト:**
```bash
httptap --method DELETE https://httpbin.io/delete
```

**HEAD リクエスト（ヘッダーのみ）:**
```bash
httptap --method HEAD https://httpbin.io/get
```

## カスタムヘッダーを追加する

`-H` フラグを使ってカスタム HTTP ヘッダーを追加します:

```bash
httptap -H "Accept: application/json" https://httpbin.io/json
```

フラグを繰り返すことで複数のヘッダーを追加できます:

```bash
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://httpbin.io/bearer
```

## リダイレクトを追跡する

デフォルトでは、httptap はリダイレクトを追跡しません。リダイレクトチェーンを追跡するには:

```bash
httptap --follow https://httpbin.io/redirect/3
```

これにより、リダイレクトチェーンの各ステップのタイミング情報が表示されます。

## コンパクト出力

ステップごとに人間が読める 1 行 — ターミナルのログや `grep` / `tee` でのテーリングに適しています:

```bash
httptap --compact https://httpbin.io/get
```

出力例:

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

この行は HTTP ステータスから始まるため、失敗が目立ちます。タイミングには `ms` サフィックスが付き、レスポンスサイズは適切な単位（`B`、`KB`、`MB`）で描画されます。リダイレクトチェーンは、リクエスト全体の形が見えるように、依然として完全な `Redirect Chain Summary` テーブルで終わります。

マシンで解析可能な `key=value` 出力（単位なし、IP/ファミリ/TLS フィールドを含む）が必要な場合は、以下の `--metrics-only` を使用してください。

## メトリクスのみモード

整形なしの生のメトリクスを取得します。スクリプトに最適です:

```bash
httptap --metrics-only https://httpbin.io
```

出力例:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

## JSON エクスポート

後の分析のために、リクエストの全データを JSON にエクスポートします:

```bash
httptap --json output.json https://httpbin.io
```

JSON ファイルには以下が含まれます:

- すべてのフェーズの詳細なタイミング
- ネットワーク情報（IP、TLS バージョン、証明書の詳細）
- レスポンスのメタデータ（ステータス、ヘッダー、ボディサイズ）
- 完全なリダイレクトチェーン（`--follow` を使用した場合）
- SLO 評価（`--slo` を指定した場合）

## SLO のしきい値チェック

`--slo` で、CI ジョブ、cron プローブ、または Kubernetes の readiness チェックを、フェーズごとのレイテンシ予算でゲートします:

```bash
httptap --slo total=500,ttfb=200 https://httpbin.io/get
```

すべての予算がパスすると終了コードは `0` になり、いずれかのしきい値が違反されると `4` になります。ウォーターフォール全体は依然として描画されるため、チェックが失敗した*理由*を確認できます。

!!! tip "サポートされる SLO キー"
    `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total` — それぞれがタイミングフェーズにマッピングされます。完全な仕様とレシピについては、専用の [SLO のしきい値チェック](../usage/slo.md) ページを参照してください。

## よくあるユースケース

### API テスト

完全な REST API ワークフローをテストします:

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

### API レイテンシの確認

```bash
httptap --compact https://httpbin.io/status/200
```

### 遅いレスポンスのデバッグ

```bash
httptap https://httpbin.io/delay/3
```

ウォーターフォールビューは、どのフェーズが遅延を引き起こしているか（DNS、接続、TLS、またはサーバー処理）を特定するのに役立ちます。

### TLS 構成の検証

```bash
httptap https://httpbin.io
```

出力で TLS バージョン、暗号スイート、証明書の有効期限を確認します。

### パフォーマンスのベンチマーク

パフォーマンスのベースラインを確立し、時間の経過に伴う変化を追跡します:

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

出力例:
```
Average: 1490.0 ms
Samples: 10
Min: 1445.4 ms
Max: 1532.4 ms
Range: 87.0 ms
```

これは、パフォーマンスのばらつきを特定し、リグレッションテストのための信頼できるベースラインを確立するのに役立ちます。

---

## 次のステップ

<div class="grid cards" markdown>

-   :material-console:{ .lg .middle } **[基本的な使い方ガイド](../usage/basic.md)**

    ---

    コマンドラインの完全なリファレンス

-   :material-palette:{ .lg .middle } **[出力形式](../usage/output-formats.md)**

    ---

    リッチ、コンパクト、JSON、メトリクスの各モード

-   :material-api:{ .lg .middle } **[API リファレンス](../api/overview.md)**

    ---

    独自コンポーネントで httptap を拡張する

</div>
