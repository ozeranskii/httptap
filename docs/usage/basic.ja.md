---
description: httptap をコマンドラインから実行し、任意の HTTP リクエストのフェーズごとのタイミングの内訳を読み解きます。
---

# 基本的な使い方

## コマンドラインインターフェース

`httptap` のコマンドラインインターフェースは、HTTP リクエストと出力をカスタマイズするためのさまざまなオプションを提供します。

## 構文

```bash
httptap [OPTIONS] URL
```

## オプション

> **curl 互換性:** 一般的な curl のフラグはエイリアスとして受け付けられます。`curl` を `httptap` に置き換えて、`-X/--request`、`-L/--location`、`-m/--max-time`、`-k/--insecure`、`-x`、`--http1.1` のような馴染みのあるオプションをそのまま使い続けられます。これは完全な curl のクローンではありません。ここに挙げた重複するフラグにとどめてください。

### リクエストオプション

#### `-X, --request, --method METHOD`

使用する HTTP メソッドを指定します。サポートされるメソッド: GET、POST、PUT、PATCH、DELETE、HEAD、OPTIONS。

*curl 互換エイリアス:* `-X`、`--request`。

```bash
httptap --method POST https://httpbin.io/post
```

**デフォルトの挙動:**
- `--data` なし: GET がデフォルトになります
- `--data` はあるが `--method` がない場合: 自動的に POST に切り替わります（curl と同様）
- `--method` を明示した場合: 指定したメソッドを尊重します

#### `-d, --data DATA`

リクエストボディのデータを送信します。インライン文字列でも、`@filename` 構文を使ったファイル参照でも指定できます。

**インライン JSON データ:**
```bash
httptap --data '{"name": "John", "email": "john@example.com"}' https://httpbin.io/post
```

**ファイルから読み込む:**
```bash
httptap --data @payload.json https://httpbin.io/post
```

**自動検出:**
- Content-Type は自動的に検出されます（JSON、XML、プレーンテキスト）
- 最初にファイル拡張子がチェックされます（.json、.xml、.txt）
- 検出できない場合は JSON 検証にフォールバックします

**さまざまなメソッドの例:**
```bash
# POST (--data がある場合に自動検出される)
httptap --data '{"key": "value"}' https://httpbin.io/post

# PUT
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put

# PATCH
httptap --method PATCH --data '{"field": "modified"}' https://httpbin.io/patch

# ボディ付きの明示的な GET (まれ、警告を発生させる)
httptap --method GET --data 'query-data' https://httpbin.io/get
```

#### `-H, --header`

リクエストにカスタム HTTP ヘッダーを追加します。複数回使用できます。

```bash
httptap -H "Accept: application/json" https://httpbin.io
```

```bash
httptap \
  -H "User-Agent: MyApp/1.0" \
  -H "Authorization: Bearer token123" \
  https://httpbin.io/bearer
```

#### `-L, --location, --follow`

HTTP リダイレクトを追跡し、チェーン内の各ステップのタイミングを表示します（リダイレクトは最大 10 回）。

*curl 互換エイリアス:* `-L`、`--location`。

```bash
httptap --follow https://httpbin.io/redirect/3
```

デフォルトでは、httptap はリダイレクトを追跡せず、最初のリダイレクトレスポンス（3xx ステータスコード）で停止します。

#### `-m, --max-time, --timeout SECONDS`

経過時間の合計が指定した秒数を超えた場合、リクエストチェーンを中止します。

*curl 互換エイリアス:* `-m`、`--max-time`。

```bash
httptap --timeout 10 https://httpbin.io/delay/2
```

デフォルトのタイムアウトは 20 秒です。

#### `--no-http2` / `--http1.1`

HTTP/2 のネゴシエーションを無効にし、HTTP/1.1 接続を強制します。

```bash
httptap --no-http2 https://httpbin.io
```

デフォルトでは、サーバーが対応していれば HTTP/2 が有効になります。

*curl 互換エイリアス:* `--http1.1`。

#### `-k, --insecure, --ignore-ssl`

TLS 証明書の検証を無効にします。自己署名ホストや期限切れの証明書のデバッグに便利です。

```bash
httptap --ignore-ssl https://self-signed.badssl.com
```

!!! warning
    このオプションは信頼できるネットワークでのみ使用してください。証明書の検証を無効にし、ハンドシェイクの制約を緩和します。

*curl 互換エイリアス:* `-k`、`--insecure`。

#### `-x, --proxy URL`

指定したプロキシ経由でリクエストをルーティングします。HTTP、HTTPS、SOCKS5、SOCKS5H の各プロトコルに対応しています。

*curl 互換エイリアス:* `-x`。

```bash
# HTTP プロキシ
httptap --proxy http://proxy.local:8080 https://httpbin.io/get

# SOCKS5 プロキシ (DNS はプロキシで解決)
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get

# SOCKS5 プロキシ (DNS はローカルで解決)
httptap --proxy socks5://proxy.local:1080 https://httpbin.io/get

# プロキシの環境変数を無視して直接接続する
httptap --proxy "" https://httpbin.io/get
```

`--proxy` フラグは環境変数（`HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`）よりも優先されます。すべてのプロキシ環境変数を無視して直接接続するには `--proxy ""` を使用してください。プロキシプロトコル、名前解決、環境変数の設定の詳細については [高度な機能](advanced.md#using-proxies) を参照してください。

#### `--cacert, --ca-bundle PATH`

TLS 検証にカスタム CA 証明書バンドル（PEM 形式）を使用します。プライベート CA によって署名された内部エンドポイントに便利です。

```bash
httptap --cacert ~/certs/company-ca.pem https://internal-api.example.com/health
```

`--ignore-ssl` とは相互排他です。

### 出力オプション

#### `--compact`

結果をコンパクトな 1 行形式で表示します。ロギングに適しています。

```bash
httptap --compact https://httpbin.io/get
```

出力:

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

`--compact` はステップごとに人間が読みやすい 1 行を出力し（ログやリダイレクトチェーンのトレースに適しています）、分析ヘッダーと `Redirect Chain Summary` テーブルも引き続きレンダリングします。レスポンスサイズは適切な単位（`B`、`KB`、`MB`）で表示されます。機械で解析可能な出力については `--metrics-only` を参照してください。

#### `--metrics-only`

書式なしの生のメトリクスを出力します。スクリプトや自動化に最適です。

```bash
httptap --metrics-only https://httpbin.io
```

出力:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

#### `--json PATH`

完全なリクエストデータを JSON ファイルにエクスポートします。

```bash
httptap --json report.json https://httpbin.io
```

JSON ファイルには以下が含まれます:

- 全フェーズのタイミングの内訳
- ネットワーク情報（IP アドレス、TLS の詳細、証明書情報）
- レスポンスのメタデータ（ステータス、ヘッダー、ボディサイズ）
- 完全なリダイレクトチェーン（`--follow` を使用した場合）
- SLO 評価（`--slo` を指定した場合）

#### `--slo KEY=MS[,KEY=MS...]`

最終的に成功したステップを、フェーズごとのレイテンシ予算と照合してチェックします。違反があった場合でも `httptap` は完全なレポートをレンダリングしますが、終了コード `4` で終了するため、その結果を CI ジョブ、cron プローブ、Kubernetes の readiness チェックのゲートに使用できます。

```bash
httptap --slo total=500,ttfb=200 https://httpbin.io/get
```

サポートされるキー: `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total`。完全な仕様、終了コードの優先順位、CI/cron のレシピについては、専用の [SLO しきい値チェック](slo.md) ページを参照してください。

#### `--version`

httptap のバージョンを表示して終了します。

```bash
httptap --version
```

## HTTP メソッド

httptap はすべての標準 HTTP メソッドをサポートしています:

- **GET** - リソースの取得（`--data` が指定されない場合のデフォルト）
- **POST** - リソースの作成／送信（`--data` が指定された場合に自動選択）
- **PUT** - リソースの置換
- **PATCH** - リソースの部分更新
- **DELETE** - リソースの削除
- **HEAD** - ヘッダーのみの取得
- **OPTIONS** - 許可されたメソッドの照会

### メソッド選択のロジック

1. **明示的なメソッド:** `--method` は常に優先されます
2. **自動 POST:** `--method` なしで `--data` がある場合、POST がデフォルトになります
3. **デフォルト GET:** `--data` も `--method` もない場合、GET を使用します

### ユースケース別の例

**API テスト:**
```bash
# リソースの作成
httptap --data '{"title": "New Post"}' https://httpbin.io/post

# リソースの更新
httptap --method PUT --data '{"title": "Updated"}' https://httpbin.io/put

# 部分更新
httptap --method PATCH --data '{"status": "published"}' https://httpbin.io/patch

# リソースの削除
httptap --method DELETE https://httpbin.io/delete
```

**ヘルスチェック:**
```bash
# クイックチェック (ヘッダーのみ)
httptap --method HEAD https://httpbin.io/status/200

# 完全なレスポンス
httptap https://httpbin.io/status/200
```

## リクエストフロー

すべての httptap リクエストは次のフェーズをたどります:

1. **名前解決** - ドメイン名のルックアップ
2. **TCP 接続** - TCP 接続の確立
3. **TLS ハンドシェイク** - セキュアな接続のネゴシエーション（HTTPS のみ）
4. **サーバー待機** - リクエスト送信から最初のレスポンスバイトまでの時間
5. **ボディ転送** - レスポンスボディのダウンロード

## 出力の理解

### リッチモード（デフォルト）

デフォルトのリッチな出力は、次の内容を含むウォーターフォールテーブルを表示します:

- フェーズ名と所要時間
- 視覚的なプログレスバー
- ネットワークの詳細（IP、TLS バージョン、証明書情報）
- レスポンスのメタデータ（ステータス、サイズ、content-type）

### タイミングの内訳

- **DNS (ms)** - ドメインを IP アドレスに解決するまでの時間
- **Connect (ms)** - TCP 接続を確立するまでの時間
- **TLS (ms)** - TLS ハンドシェイクにかかる時間（HTTPS のみ）
- **TTFB (ms)** - 最初のバイトまでの時間（サーバー処理を含む）
- **Transfer (ms)** - レスポンスボディをダウンロードするまでの時間
- **Total (ms)** - エンドツーエンドのリクエスト所要時間

### ネットワーク情報

- **IP Address** - 解決された IP アドレスとファミリ（IPv4/IPv6）
- **TLS Version** - プロトコルバージョン（TLS 1.2、TLS 1.3）
- **Cipher Suite** - ネゴシエートされた暗号スイート
- **Certificate CN** - サーバー証明書の Common Name
- **Certificate Expiry** - 証明書が期限切れになるまでの日数

## 例

### 基本的なヘルスチェック

```bash
httptap https://httpbin.io/status/200
```

### 認証付きの API リクエスト

```bash
httptap \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Accept: application/json" \
  https://httpbin.io/bearer
```

### リダイレクトチェーンを追跡する

```bash
httptap --follow https://httpbin.io/redirect/3
```

### 分析用にエクスポートする

```bash
httptap --json analysis.json --follow https://httpbin.io/redirect/2
```

### ファイルにログを出力する

```bash
httptap --metrics-only https://httpbin.io/delay/1 >> api-latency.log
```

---

## 次のステップ

<div class="grid cards" markdown>

-   :material-palette:{ .lg .middle } **[出力形式](output-formats.md)**

    ---

    リッチ、コンパクト、JSON、メトリクスの各モード

-   :material-cog:{ .lg .middle } **[高度な機能](advanced.md)**

    ---

    カスタムコンポーネントとプログラムからの利用

-   :material-api:{ .lg .middle } **[API リファレンス](../api/overview.md)**

    ---

    プロトコルで httptap を拡張する

</div>
