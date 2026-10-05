---
title: トラブルシューティング & FAQ
description: httptap の実行時によくある問題、エラーメッセージ、診断方法。
---

# トラブルシューティング & FAQ

このページでは、`httptap` の実行時にユーザーが遭遇する最もよくある質問やエラーをまとめています。あなたの問題が掲載されていない場合は、正確なコマンド、JSON エクスポート（あれば）、および関連するターミナル出力を添えて[イシューを作成](https://github.com/ozeranskii/httptap/issues)してください。

## TLS と証明書

### `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed`

サーバーが、あなたのトラストストアが認識しない証明書を提示しました。失敗したステップには
`Request failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1077)`
のようなエラーが報告されます。コロンの後の理由（自己署名、期限切れ、ローカル発行者を取得できない、ホスト名の不一致）と `_ssl.c` の行番号は状況によって異なります。

- **非本番ホスト上の自己署名または期限切れの証明書** — `--ignore-ssl` を追加します（検証を無効化するため、信頼できるネットワークでのみ使用してください）。
- **内部 CA** — `--cacert`（別名 `--ca-bundle`）を自分の PEM バンドルに向けます。
- **システムのトラストストアが古い** — Linux では `ca-certificates` を更新するか、Python 環境の `certifi` を更新します（`uv pip install --upgrade certifi`）。

httptap は検証なしの診断用 TLS ハンドシェイクのみを再試行し、提示された証明書の CN、SAN、発行者、有効期間、有効期限を失敗したステップに表示します。リクエスト自体は検証に失敗したままです。プロキシが有効な場合、httptap がプロキシをバイパスしないように、直接の診断プローブはスキップされます。

### 証明書に `cert_days_left: null` または負の値が表示される

`cert_days_left` はリーフ証明書の `notAfter` フィールドから解析されます。`null` の値は証明書を取得/解析できなかったことを意味します。通常は、証明書を受信する前に TLS が中断された、ターゲットが平文の `http://` である、または TLS ハンドシェイクの前にリクエストが失敗した場合です。`--ignore-ssl` によって `null` になることはありません。検証を無効にした場合、httptap はピア証明書を DER 形式から解析するため、`cert_cn`、`cert_days_left`、およびその他の `cert_*` フィールドは引き続き報告されます。**負**の値は、証明書がすでに期限切れであることを意味します。

### `--ignore-ssl` を使っても `DH_KEY_TOO_SMALL` / `WRONG_VERSION_NUMBER` で失敗する

最近の OpenSSL ビルドは、安全性のために一部の暗号や DH パラメータを削除しています。`--ignore-ssl` は検証やプロトコルの制約を緩和しますが、バイナリから削除された暗号スイート（RC4、3DES、脆弱な DH）を復活させることはできません。回避策: 古い curl を使う、TLS を終端するプロキシを使う、または OpenSSL を再ビルドします。

## プロキシ

### `--proxy` が無視される

明示的な `-x/--proxy` フラグは常に環境変数より優先されます。次を確認してください:

1. 誤って空文字列を渡していないこと — `--proxy ""` は環境変数ベースのプロキシを**明示的に無効化**し、直接接続を強制します。
2. スキームがターゲットと一致していること — `HTTPS_PROXY` は `https://` の URL に、`HTTP_PROXY` は `http://` に使用されます。
3. ターゲットホストが `NO_PROXY` にマッチしていないこと。JSON エクスポートの `proxy_source` フィールドを確認してください。`NO_PROXY` と表示されていれば、あなたのホストは除外されています。

### `NO_PROXY` パターンのリファレンス

- ホストとそのサブドメイン: `api.internal.example`（`v1.api.internal.example` にもマッチ）
- サブドメインのみ: `.internal.example`（`foo.internal.example` にマッチし、`internal.example` にはマッチしない）
- ワイルドカード: `*`（すべてを除外）
- 複数エントリ: カンマ区切り、前後の空白はトリミングされ、大文字と小文字は区別されない

IP アドレスは通常のホスト名として比較されます。CIDR 範囲（curl は 7.86.0 からサポート）やポート指定のエントリは**サポートされていません**。

## HTTP/2

### `--no-http2` を渡していないのにサーバーが HTTP/1.1 で応答する

HTTP/2 には TLS ハンドシェイク中の ALPN ネゴシエーションが必要です。もし:

- サーバーが ALPN で `h2` をアドバタイズしない、**または**
- ターゲットが平文の `http://` を使用している（h2c はサポートされていない）

場合、httptap は HTTP/1.1 にフォールバックします。JSON エクスポートの `network.http_version` を確認してください。

### HTTP/1.1 を強制するには？

`--no-http2`（curl 互換の別名 `--http1.1`）を使用します。これにより ALPN の h2 ネゴシエーションが完全に無効化されます。

## タイミング

### `timing.is_estimated: true` — これはどういう意味？

httptap は通常、`httpcore` のトレースフックからフェーズのタイミングを取得します。あるリクエストについてそれらのフックが接続/TLS のイベントを 1 つも報告しない場合（例: `httpcore` のトレースイベントを発行しないトランスポート）、httptap は DNS から最初のレスポンスバイトまでの時間をヒューリスティック（HTTPS では接続 30%、TLS 70%）で分割するフォールバックを使用します。内訳は依然として方向性としては正しいものの、デフォルトのパスより精度は落ちます。

### 連続する 2 回の実行で `dns_ms` が大きく異なるのはなぜ？

システムのリゾルバはエントリをキャッシュします。最初のリクエストは DNS サーバーへの完全な RTT を支払い、その後のリクエストはキャッシュにヒットします（多くの場合ミリ秒未満）。キャッシュをバイパスするには、Python API 経由でカスタムリゾルバを渡すか、ローカルキャッシュをフラッシュします（例: macOS では `sudo dscacheutil -flushcache`、systemd では `resolvectl flush-caches`）。

### すべてのリダイレクトステップで `connect_ms` と `tls_ms` がフルに計上される

httptap は各リダイレクトステップを含め、リクエストごとに新しい接続を開きます。そのため接続が再利用されることはなく、各ステップがそれぞれ TCP 接続と TLS ハンドシェイクのコストを支払います。`ttfb_ms` は名前解決の開始から計測されるため、`dns_ms`、`connect_ms`、`tls_ms` をすでに含んでいます。サーバー自身の処理時間は `wait_ms` です。タイミングがすべて `0` のステップは、レスポンスが届く前に失敗しています — そのステップの `error` フィールドを確認してください。

## 出力

### ターミナルに色が付かない

httptap は [`NO_COLOR`](https://no-color.org) の規約と Rich の TTY 検出を尊重します:

- `NO_COLOR` が設定されている場合は解除してください。
- 標準出力をファイルや別のプロセスにパイプすると色が無効になります。上書きするには `FORCE_COLOR=1` を設定してください。
- `TERM=dumb` も描画を無効にします。

### `--metrics-only` に `proxy=` フィールドが表示されなくなった

そうではありません — このフィールドはレスポンスを受信したすべてのステップに存在します。古いスクリーンショットや例は変更前のものかもしれません。失敗したステップは `Step N: ERROR - <message>` として出力され、メトリクスや `proxy=` フィールドは含まれません。成功したステップで想定される形式:

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

取りうる値:

- `proxy=<url> proxy_from=arg` — `-x/--proxy` で設定されたプロキシ。
- `proxy=<url> proxy_from=env:<VAR>` — `https_proxy` や `HTTPS_PROXY` などの環境変数から取得されたプロキシ。
- `proxy=none proxy_from=env:no_proxy` — ホストが `NO_PROXY` にマッチした。
- `proxy=disabled proxy_from=arg` — `--proxy ""` でプロキシが無効化された。
- `proxy=direct proxy_from=no_scheme_match` — プロキシ変数は設定されているが、URL のスキームに該当するものがない。
- `proxy=direct` — プロキシが設定されていない。

`key=value` のトークン分割を壊してしまう値はパーセントエンコードされます。

## スクリプト & CI

### どの終了コードを確認すべき？

README の [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes) セクションを参照してください。典型的な CI のパターン: `75`（ネットワーク / TLS、一時的）はリトライ可能として扱い、`64`（使用方法）、`70`（バグ）、`47`（`--follow` でリダイレクト上限に到達）、`73`（`--json` ファイルを書き込めなかった）、`22`（`--fail` 指定時の HTTP 4xx/5xx）、`4`（`--slo` を指定した場合の SLO 違反）ではハードに失敗させます。複数が該当する場合は、優先度の最も高いコードが採用されます。[優先順位の表](usage/slo.md#exit-codes)を参照してください。

### リクエストが遅いのに `--slo` の予算が一度もトリガーされない。

3 つを確認してください:

1. 設定したキーが実際のタイミングフェーズにマッピングされていること。有効なキーは `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total` です — それ以外は終了コード `64`（SLO Error パネル）でコマンドを拒否します。
2. SLO は**最終的に成功したステップ**で評価され、中間のリダイレクトでは評価されません。`--follow` が複数のホップを経由し、最後のステップが高速だった場合、チェーン全体の合計は比較されません。最後のリクエストの予算に対して `total` を使うか、ステップごとの保証が必要な場合は `--json` から手動で集計してください。リダイレクト上限に到達した場合、評価されるステップは最後の `3xx` レスポンスです。
3. すべてのステップがエラーになった場合、SLO は完全にスキップされます — 終了コードはネットワーク障害を反映します（通常は `75`）。その場合、`--metrics-only` の出力に `slo=` トークンは現れません。

### httptap は Prometheus メトリクスを出力できる？

はい。`--prometheus PATH` を使うと、node_exporter の textfile collector 用ファイルを書き出せます。メトリクス名とラベルについては [出力形式](usage/output-formats.md#prometheus-textfile-export) を参照してください。

## Python API

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` はトップレベルの名前空間ではなく `httptap.constants` にあります:

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### カスタムリゾルバが呼び出されない

`HTTPTapAnalyzer` は、注入されたリゾルバを直接接続とローカル DNS の SOCKS5 プロキシに対して使用します。HTTP、HTTPS、SOCKS5H プロキシはターゲットをリモートで名前解決します。この挙動を変更する必要がある場合は、カスタム `RequestExecutor` を使用してください。

---

## それでも解決しない？

- `--metrics-only` を付けて実行し、その出力全体をレポートに含めてください。
- `--json report.json` を付けて実行し、レポートを添付してください（認証ヘッダーは伏せてください）。
- バージョンを確認してください — `httptap --version` — 最新のマイナーバージョンのみをサポートしています。
