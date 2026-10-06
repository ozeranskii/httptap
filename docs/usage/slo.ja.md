---
title: SLO しきい値チェック
description: --slo または --slo-file を使って、CI、cron、稼働監視でフェーズごとのレイテンシ予算に基づきリクエストをゲートします。
---

# SLO しきい値チェック

`httptap --slo` と `--slo-file` は、計測されたタイミングをフェーズごとのレイテンシ予算と照合してチェックし、いずれかの予算を超過した場合に非ゼロのコードで終了します。これにより、単一のリクエストが、CI ゲート、cron ベースの合成監視、稼働監視、デプロイ後のスモークテストに適した合否プローブになります。カスタムのシェルパーサーを書く必要はありません。

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

### ファイルベースのしきい値

`--slo-file PATH` を使うと、UTF-8 のファイルからしきい値を読み込みます。1 行に 1 つの `KEY=MS` エントリを記述します。空行と `#` で始まる行は無視されます。`--slo` と同じ検証ルールが適用されます。

`slo.txt`:

```text
# Health endpoint budget
total=500
ttfb=200
```

```shell
httptap --slo-file slo.txt https://api.example.com/health
```

`--slo-file` と `--slo` は併用できます。一致するキーについては、インラインの値がファイルの値を上書きします。

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
- 読み込めない `--slo-file`、または上記のいずれかを含む `--slo-file`。

具体的なエラーは、`--metrics-only` の場合も含め、Rich 書式の `SLO Error` パネルとして stderr に出力されます。リクエストは行われないため、stdout には何も書き込まれません。

## 評価ルール

SLO しきい値は、リクエストチェーンの**最終的に成功したステップ**、つまりネットワークエラーや TLS エラーで失敗しなかった最後のステップに対して評価されます:

- 単一リクエスト → そのリクエストに対してチェックされます。
- リダイレクトチェーン（`--follow`）→ 中間のリダイレクトではなく、最後のレスポンスに対してチェックされます。ユーザーは実際にリクエストを処理したものに関心があるという前提です。
- リダイレクト上限に到達した場合 → 最後のステップ自体が `3xx` リダイレクトであり、それでも評価されます。終了コードはいずれにしても `47` です（下記参照）。
- 後続のステップでエラーが発生した場合 → その前に成功した最後のステップが評価され、終了コードはネットワーク障害を反映します。
- すべてのステップがエラーになった場合 → SLO は完全にスキップされ、終了コードはネットワーク障害を反映します（下記参照）。

しきい値は `actual ≤ threshold` のときに合格します。等しい場合は違反とは**みなされません**。違反は決定論的な出力のために、そのキーのアルファベット順で報告されます。

## 終了コード { #exit-codes }

`--slo` は `httptap` の全体的な終了コードの優先順位に統合されています:

| 優先度      | 条件                                | 終了コード     |
|:--------:|-----------------------------------|:---------:|
| 1        | 不正な引数（不正な `--slo` 仕様）             | `64`      |
| 2        | 内部エラー                             | `70`      |
| 3        | リダイレクト上限に到達（`-L`）                 | `47`      |
| 4        | いずれかのステップでのネットワーク／TLS 障害          | `75`      |
| 5        | `--json` または `--har` のファイルを書き込めなかった | `73`      |
| 6        | `--fail` 指定時の HTTP 4xx/5xx レスポンス  | `22`      |
| 7        | 最終的に成功したステップでの SLO 違反             | `4`       |
| 8        | 成功                                | `0`       |

内部エラー、リダイレクト上限、ネットワークエラーは `--json`/`--har` の書き込み結果、`--fail`、SLO 違反よりも優先されるため、障害のあるホストが CI ログの中でレイテンシのリグレッションを装うことはありません。

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

このステップは、ネットワークエラー（`75`）を含め、非ゼロの終了コードであれば失敗します。SLO 違反（またはその他のエラー）ではビルドを失敗させつつ、ネットワークエラーでは警告にとどめたい場合は、終了コードを `$GITHUB_OUTPUT` に記録し、後続のステップでそれに応じて処理します:

```yaml
- name: Smoke-test staging latency
  id: smoke
  run: |
    set +e
    httptap --slo total=2000 https://staging.example.com/
    code=$?
    echo "exit_code=${code}" >> "$GITHUB_OUTPUT"
    if [ "${code}" -ne 0 ] && [ "${code}" -ne 75 ]; then
      exit "${code}"
    fi
- name: Warn on network errors
  if: steps.smoke.outputs.exit_code == '75'
  run: echo "::warning::httptap could not reach staging (exit 75)."
```

`set +e` により、非ゼロで終了した後もシェルが実行を続けるため、終了コードを記録できます。SLO 違反（`4`）の場合は、スモークステップ自体が失敗します。

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
