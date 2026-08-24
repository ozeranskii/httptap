---
title: トラブルシューティング & FAQ
description: httptap の実行時によくある問題、エラーメッセージ、診断方法。
---

# トラブルシューティング & FAQ

このページでは、`httptap` の実行時にユーザーが遭遇する最もよくある質問やエラーをまとめています。あなたの問題が掲載されていない場合は、正確なコマンド、JSON エクスポート（あれば）、および関連するターミナル出力を添えて[イシューを作成](https://github.com/ozeranskii/httptap/issues)してください。

## TLS と証明書

### `TLS handshake failed: CERTIFICATE_VERIFY_FAILED`

サーバーが、あなたのトラストストアが認識しない証明書を提示しました。

- **非本番ホスト上の自己署名または期限切れの証明書** — `--ignore-ssl` を追加します（検証を無効化するため、信頼できるネットワークでのみ使用してください）。
- **内部 CA** — `--cacert`（別名 `--ca-bundle`）を自分の PEM バンドルに向けます。
- **システムのトラストストアが古い** — Linux では `ca-certificates` を更新するか、Python 環境の `certifi` を更新します（`uv pip install --upgrade certifi`）。

JSON エクスポートには `network.tls_verified: false` が表示され、`--cacert` を使用した場合は `network.tls_custom_ca: true` も表示されます。

### 証明書に `cert_days_left: null` または負の値が表示される

`cert_days_left` はリーフ証明書の `notAfter` フィールドから解析されます。`null` の値は証明書を取得/解析できなかったことを意味します。通常は、証明書を受信する前に TLS が中断されたか、`--ignore-ssl` が使用された場合です（検証を無効にすると、ピア証明書は解析済みのディクショナリとして表面化されないため、`cert_cn`/`cert_days_left` およびその他の `cert_*` フィールドは `null` のままとなり、一方で `tls_version`/`tls_cipher` は依然として報告されます）。**負**の値は、証明書がすでに期限切れであることを意味します。

### `--ignore-ssl` を使っても `DH_KEY_TOO_SMALL` / `WRONG_VERSION_NUMBER` で失敗する

最近の OpenSSL ビルドは、安全性のために一部の暗号や DH パラメータを削除しています。`--ignore-ssl` は検証やプロトコルの制約を緩和しますが、バイナリから削除された暗号スイート（RC4、3DES、脆弱な DH）を復活させることはできません。回避策: 古い curl を使う、TLS を終端するプロキシを使う、または OpenSSL を再ビルドします。

## プロキシ

### `--proxy` が無視される

明示的な `-x/--proxy` フラグは常に環境変数より優先されます。次を確認してください:

1. 誤って空文字列を渡していないこと — `--proxy ""` は環境変数ベースのプロキシを**明示的に無効化**し、直接接続を強制します。
2. スキームがターゲットと一致していること — `HTTPS_PROXY` は `https://` の URL に、`HTTP_PROXY` は `http://` に使用されます。
3. ターゲットホストが `NO_PROXY` にマッチしていないこと。JSON エクスポートの `proxy_source` フィールドを確認してください。`NO_PROXY` と表示されていれば、あなたのホストは除外されています。

### `NO_PROXY` パターンのリファレンス

- 完全一致ホスト: `api.internal.example`
- ドメインサフィックス: `.internal.example`（`foo.internal.example` にマッチ）
- ワイルドカード: `*`（すべてを除外）
- 複数エントリ: カンマ区切り、前後の空白はトリミングされる

IP/CIDR マッチングは**サポートされていません** — これは広く採用されている curl の挙動に従っています。

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

httptap は通常、`httpcore` のトレースフックからフェーズのタイミングを取得します。それらのフックが利用できない場合（例: それらをバイパスするカスタム `RequestExecutor`、または特定の HTTP/2 接続再利用パス）、httptap は経過時間の合計をヒューリスティックで分割するフォールバックを使用します。内訳は依然として方向性としては正しいものの、デフォルトのパスより精度は落ちます。

### 連続する 2 回の実行で `dns_ms` が大きく異なるのはなぜ？

システムのリゾルバはエントリをキャッシュします。最初のリクエストは DNS サーバーへの完全な RTT を支払い、その後のリクエストはキャッシュにヒットします（多くの場合ミリ秒未満）。キャッシュをバイパスするには、Python API 経由でカスタムリゾルバを渡すか、ローカルキャッシュをフラッシュします（例: macOS では `sudo dscacheutil -flushcache`、systemd では `resolvectl flush-caches`）。

### `ttfb_ms` がゼロ、または `connect_ms` より小さい

接続の再利用時（後続のリダイレクトステップでの keep-alive、HTTP/2 のストリーム多重化）には、そのステップに対して新しい TCP 接続がありません — `connect_ms` は `0` または非常に小さくなります。`ttfb_ms` はその特定のリクエストで最初のレスポンスバイトが返るまでの時間を計測します。ステップ間で `connect_ms` と比較すると、奇妙に見えるのが予想される挙動です。

## 出力

### ターミナルに色が付かない

httptap は [`NO_COLOR`](https://no-color.org) の規約と Rich の TTY 検出を尊重します:

- `NO_COLOR` が設定されている場合は解除してください。
- 標準出力をファイルや別のプロセスにパイプすると色が無効になります。上書きするには `FORCE_COLOR=1` を設定してください。
- `TERM=dumb` も描画を無効にします。

### `--metrics-only` に `proxy=` フィールドが表示されなくなった

そうではありません — このフィールドは常に存在します。古いスクリーンショットや例は変更前のものかもしれません。想定される形式:

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

`proxy` の値のソース: `direct`、`none`（NO_PROXY にヒット）、`disabled`（`--proxy ""`）、`proxy_from=...` のヒント付きの `<url>`。

## スクリプト & CI

### どの終了コードを確認すべき？

README の [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes) セクションを参照してください。典型的な CI のパターン: `75`（ネットワーク / TLS、一時的）はリトライ可能として扱い、`64`（使用方法）、`70`（バグ）、`4`（`--slo` を指定した場合の SLO 違反）ではハードに失敗させます。

### リクエストが遅いのに `--slo` の予算が一度もトリガーされない。

3 つを確認してください:

1. 設定したキーが実際のタイミングフェーズにマッピングされていること。有効なキーは `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total` です — それ以外は終了コード `64`（SLO Error パネル）でコマンドを拒否します。
2. SLO は**最終的に成功したステップ**で評価され、中間のリダイレクトでは評価されません。`--follow` が複数のホップを経由し、最後のステップが高速だった場合、チェーン全体の合計は比較されません。終端リクエストの予算に対して `total` を使うか、ステップごとの保証が必要な場合は `--json` から手動で集計してください。
3. すべてのステップがエラーになった場合、SLO は完全にスキップされます — 終了コードはネットワーク障害を反映します（通常は `75`）。その場合、`--metrics-only` の出力に `slo=` トークンは現れません。

### httptap は Prometheus メトリクスを出力できる？

そのままでは出力できません。`--metrics-only` を使って `awk`/`jq` で後処理するか、`--json` エクスポートを解析してください。専用のエクスポーターはロードマップにあります — 最新情報は[イシュートラッカー](https://github.com/ozeranskii/httptap/issues)を追ってください。

## Python API

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` はトップレベルの名前空間ではなく `httptap.constants` にあります:

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### カスタムリゾルバが呼び出されない

`HTTPTapAnalyzer` は、注入されたリゾルバを診断用の DNS ルックアップのタイミング計測にのみ使用します。実際の接続の名前解決は、依然として `httpx`/`httpcore` によって行われます。実際の接続を自分のリゾルバ経由でルーティングするには、カスタム `RequestExecutor` も実装してください。

---

## それでも解決しない？

- `--metrics-only` を付けて実行し、その出力全体をレポートに含めてください。
- `--json report.json` を付けて実行し、レポートを添付してください（認証ヘッダーは伏せてください）。
- バージョンを確認してください — `httptap --version` — 最新のマイナーバージョンのみをサポートしています。
