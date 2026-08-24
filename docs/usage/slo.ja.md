---
title: SLO しきい値チェック
description: --slo を使って、CI、cron、稼働監視でフェーズごとのレイテンシ予算に基づきリクエストをゲートします。
---

# SLO しきい値チェック

`httptap --slo` は、計測されたタイミングをフェーズごとのレイテンシ予算と照合してチェックし、いずれかの予算を超過した場合に非ゼロのコードで終了します。これにより、単一のリクエストが、CI ゲート、cron ベースの合成監視、稼働監視、デプロイ後のスモークテストに適した合否プローブになります。カスタムのシェルパーサーを書く必要はありません。

## クイックな例

```shell
httptap --slo total=500,ttfb=200 https://api.example.com/health
```

- `total_ms ≤ 500` **かつ** `ttfb_ms ≤ 200` の場合に `0` で終了します。
- いずれかの予算を超過した場合に `4` で終了します。
- 結果にかかわらず完全なウォーターフォールと JSON エクスポートを引き続き出力するため、ゲートによって調査が妨げられることは決してありません。

## 仕様の構文

`KEY=MS` ペアのカンマ区切りリストを `--slo` に渡します:

```
--slo KEY=MS[,KEY=MS]*
```

- `KEY` はサポートされているタイミングフェーズの 1 つです（大文字・小文字を区別しません）。
- `MS` は正の有限なミリ秒数です（整数または浮動小数点数）。
- キーと値の前後の空白は許容されます。

### サポートされるキー

| Key       | 意味                                                            |
|-----------|----------------------------------------------------------------|
| `dns`     | 名前解決の時間                                                  |
| `connect` | TCP 接続の確立                                                  |
| `tls`     | TLS ハンドシェイク（プレーン HTTP では `0`）                    |
| `ttfb`    | 最初のバイトまでの時間（DNS + connect + TLS + サーバー待機）    |
| `wait`    | サーバー処理時間（`ttfb - (dns + connect + tls)`）              |
| `xfer`    | レスポンスボディの転送時間（`total - ttfb`）                    |
| `total`   | エンドツーエンドのリクエスト所要時間                            |

### 不正な仕様

`--slo` は以下を拒否し、`64`（使用法エラー）で終了します:

- 空の仕様（`--slo ""`）。
- 不明なキー（`--slo foo=500` → `Unknown SLO key 'foo'`）。
- 重複したキー（`--slo total=500,total=600`）。
- 数値でない値（`--slo total=fast`）。
- ゼロ、負、または有限でない値（`--slo total=0`、`total=nan`、`total=inf`）。
- `=` の欠落（`--slo total500`）。

具体的なエラーは、インタラクティブな使用のために Rich 書式のパネルで出力され、`--metrics-only` ではプレーンテキストで出力されます。

## 評価ルール

SLO しきい値は、リクエストチェーンの**最終的に成功したステップ**に対して評価されます:

- 単一リクエスト → そのリクエストに対してチェックされます。
- リダイレクトチェーン（`--follow`）→ 中間のリダイレクトではなく、終端のレスポンスに対してチェックされます。ユーザーは実際にリクエストを処理したものに関心があるという前提です。
- すべてのステップがエラーになった場合 → SLO は完全にスキップされ、終了コードはネットワーク障害を反映します（下記参照）。

しきい値は `actual ≤ threshold` のときに合格します。等しい場合は違反とは**みなされません**。違反は決定論的な出力のために、そのキーのアルファベット順で報告されます。

## 終了コード

`--slo` は `httptap` の全体的な終了コードの優先順位に統合されています:

| 優先度   | 条件                                     | 終了コード |
|:--------:|------------------------------------------|:---------:|
| 1        | 不正な引数（不正な `--slo` 仕様）        | `64`      |
| 2        | いずれかのステップでのネットワーク／TLS 障害 | `75`      |
| 3        | 内部エラー                               | `70`      |
| 4        | 最終的に成功したステップでの SLO 違反     | `4`       |
| 5        | 成功                                     | `0`       |

ネットワークエラーは常に SLO 違反よりも優先されるため、障害のあるホストが CI ログの中でレイテンシのリグレッションを装うことはありません。

## 出力形式

### リッチ（デフォルト）

ウォーターフォールとリダイレクト要約（あれば）の後に、`httptap` は SLO 評価を要約するパネルを出力します:

```
╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms, ttfb≤200ms            │
│ Violations:                                    │
│   • total: 723.4ms > 500ms (+223.4ms)          │
│   • ttfb: 315.2ms > 200ms (+115.2ms)          │
╰────────────────────────────────────────────────╯
```

パネルのボーダーとアイコンはステータスに一致します。合格は緑の `✓`、不合格は赤の `✗` です。

### コンパクト

`--compact` はステップごとに人間が読みやすい 1 行を出力し、続いてデフォルトモードで表示されるのと同じ Rich の SLO パネルを出力します:

```
Step 1: 200 GET https://api.example.com | dns=3.3ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=900.0ms | 1.2 KB

╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms                        │
│ Violations:                                    │
│   • total: 900.0ms > 500ms (+400.0ms)          │
╰────────────────────────────────────────────────╯
```

### メトリクスのみ

`--metrics-only` は、最終的に成功したステップの標準的な `key=value` 行に SLO トークンを追加します:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=900.0 ... slo=fail slo_violations=total,ttfb
```

合格の場合:

```
Step 1: ... proxy=direct slo=pass
```

中間のリダイレクトステップは SLO トークンを**持たず**、行数を変えません。

### JSON エクスポート

`--json PATH` は `summary` ブロックを `slo` オブジェクトで拡張します:

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

各違反は、キー、ユーザーが指定したしきい値、計測値、超過量を持ちます。`delta_ms` は厳密に正であり、違反を深刻度順にランク付けするために使用できます。

`--slo` フラグが渡されない場合、`slo` キーは存在しません。summary の形は既存の利用者と後方互換です。

## レシピ

### cron ベースの合成監視

```cron
* * * * * httptap --slo total=1000,ttfb=500 https://api.example.com/health \
  || curl -X POST https://alerts.example.com/page/oncall
```

### デプロイ後の CI ゲート

```yaml
- name: Smoke-test staging latency
  run: |
    httptap --slo total=2000,tls=300,ttfb=800 \
      https://staging.example.com/
```

このステップは終了コード `4` または `64` の場合のみ失敗します。ネットワークエラー（終了コード `75`）は別途処理できます:

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

### Kubernetes readiness プローブ

```yaml
readinessProbe:
  exec:
    command:
      - httptap
      - --slo
      - total=5000
      - http://localhost:8080/healthz
```

### リグレッションバー

```shell
httptap --slo total=500,ttfb=200 --json regression.json https://prod.example.com/
jq '.summary.slo.violations' regression.json
```

### マルチホストのカナリア

```shell
for host in prod-eu prod-us prod-ap; do
  httptap --slo total=1500 "https://${host}.example.com/health" || echo "${host}: SLO miss"
done
```

## ヒント

- まずは `--slo total=<P95 latency>` から始め、`--json` エクスポートからベースラインデータが得られたらフェーズごとの予算を追加してください。
- `xfer` と `wait` は派生メトリクスであり、その合計は `total` によって上限が定まります。`total` の予算を設定すると、個々のフェーズは暗黙的に上限が定まります。
- `--timeout` と組み合わせてください。`--slo` はリクエスト完了*後*にレイテンシをチェックします。`--timeout` はハングしたリクエストを強制終了します。通常は両方を使いたいはずです。
- SLO 出力は [`httpstat` の `--slo`](https://github.com/reorx/httpstat#slo-thresholds) 形式（`slo=pass` / `slo=fail` トークン、終了コード `4`）をミラーしているため、スクリプトを相互に利用できます。
