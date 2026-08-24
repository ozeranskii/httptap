<p align="center">
  <img src="docs/assets/httptap-banner.svg" alt="httptap" width="100%" />
</p>

# httptap

<table>
  <tr>
    <th>Releases</th>
    <th>CI &amp; Quality</th>
    <th>Security</th>
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
      <a href="https://codecov.io/github/ozeranskii/httptap">
        <img src="https://codecov.io/github/ozeranskii/httptap/graph/badge.svg?token=OFOHOI1X5J" alt="Coverage" />
      </a><br />
      <a href="https://codspeed.io/ozeranskii/httptap?utm_source=badge">
        <img src="https://img.shields.io/endpoint?url=https://codspeed.io/badge.json" alt="CodSpeed Badge" />
      </a>
    </td>
    <td>
      <a href="https://github.com/ozeranskii/httptap/actions/workflows/codeql.yml">
        <img src="https://github.com/ozeranskii/httptap/actions/workflows/codeql.yml/badge.svg" alt="CodeQL" />
      </a><br />
      <a href="https://scorecard.dev/viewer/?uri=github.com/ozeranskii/httptap">
        <img src="https://api.scorecard.dev/projects/github.com/ozeranskii/httptap/badge" alt="OpenSSF Scorecard" />
      </a><br />
      <a href="https://www.bestpractices.dev/projects/12474">
        <img src="https://www.bestpractices.dev/projects/12474/badge" alt="OpenSSF Best Practices" />
      </a><br />
      <a href="https://www.bestpractices.dev/projects/12474">
        <img src="https://www.bestpractices.dev/projects/12474/baseline" alt="OpenSSF Baseline" />
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

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | <b>日本語</b> | <a href="README.es.md">Español</a>
</p>

> **注記:** これはコミュニティによる翻訳であり、英語版より古い場合があります。内容に相違がある場合は [英語版 README](README.md) を正とします。

`httptap` は Rich を活用した CLI で、HTTP リクエストを意味のある各フェーズ——名前解決（DNS）、TCP 接続、TLS
ハンドシェイク、サーバー待機、ボディ転送——に分解し、その結果をタイムライン表、コンパクトな概要、あるいは機械処理に
適したメトリクスとして表示します。インタラクティブなトラブルシューティング、回帰分析、そしてパフォーマンスの
ベースライン記録のために設計されています。

---

## 目次

- [ハイライト](#ハイライト)
- [他ツールとの比較](#他ツールとの比較)
- [要件](#要件)
- [インストール](#インストール)
  - [Homebrew を使用（macOS/Linux）](#homebrew-を使用macoslinux)
  - [`uvx` を使用（推奨）](#uvx-を使用推奨)
  - [`uv` を使用](#uv-を使用)
  - [`pip` を使用](#pip-を使用)
  - [コンテナイメージ](#コンテナイメージ)
  - [ソースから](#ソースから)
  - [シェル補完](#シェル補完)
- [クイックスタート](#クイックスタート)
  - [基本的な GET リクエスト](#基本的な-get-リクエスト)
  - [データ付きの POST リクエスト](#データ付きの-post-リクエスト)
  - [その他の HTTP メソッド](#その他の-http-メソッド)
  - [カスタムヘッダー](#カスタムヘッダー)
  - [リダイレクトと JSON エクスポート](#リダイレクトと-json-エクスポート)
  - [出力モード](#出力モード)
  - [高度な使い方](#高度な使い方)
- [SLO しきい値チェック](#slo-しきい値チェック)
- [環境変数](#環境変数)
- [終了コード](#終了コード)
- [リリース](#リリース)
- [サンプル出力](#サンプル出力)
- [JSON エクスポート構造](#json-エクスポート構造)
- [メトリクスのみのスクリプト化](#メトリクスのみのスクリプト化)
- [高度な使い方](#高度な使い方-1)
- [開発](#開発)
- [コントリビュート](#コントリビュート)
- [ライセンス](#ライセンス)
- [謝辞](#謝辞)
- [Star History](#star-history)

---

## ハイライト

- **フェーズごとの計時** —— httpcore の trace フックから構築された精密な計測（低レベルのデータが利用できない場合は
  合理的なフォールバックを使用）。
- **すべての HTTP メソッド** —— GET、POST、PUT、PATCH、DELETE、HEAD、OPTIONS をリクエストボディ対応で。
- **リクエストボディ対応** —— JSON、XML、または任意のデータをインラインまたはファイルから送信し、Content-Type を
  自動検出。
- **IPv4/IPv6 対応** —— リゾルバーと TLS インスペクターがアドレスとそのファミリーの両方をレポートします。
- **TLS の洞察** —— 証明書の CN、SAN、発行者、シリアル、有効期間と有効期限までのカウントダウン、加えて暗号スイートと
  プロトコルバージョンが、稼働中の接続から自動的に取得されます（追加のハンドシェイクは不要）。
- **複数の出力モード** —— リッチなウォーターフォールビュー、コンパクトな単一行の概要、あるいはスクリプト向けの
  `--metrics-only`。
- **JSON エクスポート** —— 後続の処理のために完全なステップデータ（リダイレクトチェーンを含む）を永続化します。
- **SLO しきい値チェック** —— `--slo total=500,ttfb=200` は、フェーズごとのレイテンシ予算に基づいて CI ジョブ、cron
  プローブ、レディネスチェックにゲートを設けます。違反時には非ゼロで終了しつつ、完全なレポートは引き続き
  レンダリングします。
- **拡張可能** —— DNS、TLS、計時、可視化、エクスポートのためのクリーンな Protocol インターフェースを備え、カスタムな
  挙動を差し込めます。

> 📣 <strong>httptap ユーザー限定：</strong> <a href="https://gitkraken.cello.so/vY8yybnplsZ"><strong>GitKraken Pro</strong></a> が 50% オフ。GitKraken Client、VS Code 向けの GitLens、そして強力な CLI ツールをひとまとめにして、あらゆるリポジトリのワークフローを加速します。

---

## 他ツールとの比較

| 機能                                      | `httptap` | `curl -w`              | [`httpstat`](https://github.com/reorx/httpstat) | `httpie`          |
|------------------------------------------|:---------:|:----------------------:|:-----------------------------------------------:|:-----------------:|
| フェーズごとの計時（DNS/TCP/TLS/TTFB）      | ✅        | ✅（書式文字列）        | ✅                                              | ❌                |
| Rich によるウォーターフォール可視化          | ✅        | ❌                     | ⚠️ テキストバー                                  | ❌                |
| ステップごとの計時付きリダイレクトチェーン     | ✅        | ❌                     | ❌                                              | ❌                |
| JSON エクスポート（機械可読）                | ✅        | ✅ (`-w '%{json}'`)    | ✅ (`--format json/jsonl`, v1 schema)           | ❌（メトリクスなし） |
| スクリプト向けのメトリクスのみモード          | ✅        | ✅                     | ✅ (`--format json`)                            | ❌                |
| SLO しきい値チェック                        | ✅ (`--slo`) | ❌                  | ✅ (`--slo total=500,...`)                      | ❌                |
| TLS 証明書の検査（CN、有効期限）             | ✅        | ⚠️ `-v` 経由           | ❌                                              | ❌                |
| IPv4/IPv6 のレポート                       | ✅ アドレスファミリー | ⚠️ `remote_ip` 経由で IP  | ⚠️ IP のみ (`remote_ip`/`remote_port`)          | ❌                |
| HTTP/2 サポート                           | ✅        | ✅                     | ⚠️ curl パススルー経由                           | ⚠️ プラグインのみ  |
| 送信元の帰属付きプロキシ                     | ✅        | ⚠️ 帰属なし             | ⚠️ curl パススルー経由                           | ⚠️ 帰属なし        |
| カスタム CA バンドル                        | ✅        | ✅                     | ⚠️ curl パススルー経由                           | ✅                |
| 拡張可能な Python API                      | ✅        | ❌（pycurl ≠ 同一 API） | ❌                                              | ⚠️ requests 経由   |
| curl 互換フラグ                            | ✅        | —                      | ✅（パススルー）                                 | ❌                |
| システム依存ゼロ                           | ✅        | ✅                      | curl が必要                                     | ✅                |

**どれを選ぶべきか：**
- **`httptap`** —— インタラクティブなトラブルシューティング、回帰分析、そして構造化 JSON を伴うスクリプト化された
  ベースライン。
- **`curl -w`** —— curl がすでに依存関係にある場合の、一度きりの shell チェック。
- **`httpstat`** —— 既存の curl インストール上での手早い視覚的な内訳。
- **`httpie`** —— レイテンシのプロファイリングではなく、汎用的なリクエスト/レスポンスの探索。

---

## 要件

- Python 3.10-3.15 (CPython)
- macOS、Linux、または Windows（CPython でテスト済み）
- 標準的なネットワーク機能を超えるシステム依存はありません
- コードは Google Python Style Guide（docstring、フォーマット）に従う必要があります。
  [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) を参照してください

---

## インストール

### Homebrew を使用（macOS/Linux）

```shell
brew install httptap
```

### `uvx` を使用（推奨）

```shell
uvx --from "httptap[completion]" httptap https://example.com
```

### `uv` を使用

```shell
uv pip install httptap
```

### `pip` を使用

```shell
pip install httptap
```

### コンテナイメージ

```shell
docker run --rm ghcr.io/ozeranskii/httptap:latest https://example.com
```

マルチアーキテクチャ（linux/amd64、linux/arm64）で、cosign（キーレスの Sigstore）により署名され、SLSA ビルド
プロベナンスが付属します。

### ソースから

```shell
git clone https://github.com/ozeranskii/httptap.git
cd httptap
uv venv
uv pip install .
```

---

### シェル補完

#### Homebrew でのインストール

httptap を Homebrew でインストールした場合、シェル補完はインストール後に自動的に利用可能になります。シェルを
再起動するだけです：

```shell
# Restart your shell or reload configuration
exec $SHELL
```

Homebrew は補完を自動的に次の場所へインストールします：
- Bash: `$(brew --prefix)/etc/bash_completion.d/`
- Zsh: `$(brew --prefix)/share/zsh/site-functions/`

#### Python パッケージでのインストール

httptap を `pip` または `uv` でインストールした場合、オプションの補完 extras をインストールする必要があります：

1. 補完 extras をインストールします：

   ```shell
   uv pip install "httptap[completion]"
   # or
   pip install "httptap[completion]"
   ```

2. 仮想環境を有効化します：

   ```shell
   source .venv/bin/activate
   ```

3. 引数補完のためにグローバル有効化スクリプトを実行します：

   ```shell
   activate-global-python-argcomplete
   ```

4. シェルを再起動します。これで bash と zsh の両方で補完が動作するはずです。

**注記：** グローバル有効化スクリプトが提供する引数補完は bash と zsh のみです。その他のシェルはこのスクリプトの
対象外であり、個別に設定する必要があります。

#### 使用例

補完をインストールすれば、`Tab` を使ってコマンドやオプションを自動補完できます：

```shell
# Complete command options
httptap --<TAB>
# Shows: --method, --data, --follow, --timeout, --no-http2, --ignore-ssl, --cacert, --proxy, --header, --compact, --metrics-only, --json, --version, --help

# Complete after typing partial option
httptap --fol<TAB>
# Completes to: httptap --follow

# Complete multiple options
httptap --follow --time<TAB>
# Completes to: httptap --follow --timeout
```

---

## クイックスタート

### 基本的な GET リクエスト

単一のリクエストを実行し、Rich なウォーターフォールを表示します：

```shell
httptap https://httpbin.io/get
```

### データ付きの POST リクエスト

JSON データを送信します（Content-Type を自動検出）：

```shell
httptap https://httpbin.io/post --data '{"name": "John", "email": "john@example.com"}'
```

**注記：** `--method` なしで `--data` が指定された場合、httptap は自動的に POST へ切り替えます（curl と同様）。

**curl 互換フラグ：** httptap は最も一般的な curl の構文を受け付けるため、多くの場合 `curl` を `httptap` へそのまま
置き換えられます。エイリアスには、`--method` に対する `-X/--request`、`--follow` に対する `-L/--location`、
`--timeout` に対する `-m/--max-time`、`--ignore-ssl` に対する `-k/--insecure`、`--proxy` に対する `-x`、そして
`--no-http2` に対する `--http1.1` が含まれます。（すべての curl オプションがサポートされているわけではありません——
コマンドを置き換える際は、これらの共通フラグにとどめてください。）

ファイルからデータを読み込みます：

```shell
httptap https://httpbin.io/post --data @payload.json
```

メソッドを明示的に指定します（自動 POST を回避）：

```shell
httptap https://httpbin.io/post --method POST --data '{"status": "active"}'
```

### その他の HTTP メソッド

PUT リクエスト：

```shell
httptap https://httpbin.io/put --method PUT --data '{"key": "value"}'
```

PATCH リクエスト：

```shell
httptap https://httpbin.io/patch --method PATCH --data '{"field": "updated"}'
```

DELETE リクエスト：

```shell
httptap https://httpbin.io/delete --method DELETE
```

### カスタムヘッダー

カスタムヘッダーを追加します（複数の値には `-H` を繰り返します）：

```shell
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer super-secret" \
  https://httpbin.io/bearer
```

### リダイレクトと JSON エクスポート

リダイレクトチェーンを追跡し、メトリクスを JSON にダンプします：

```shell
httptap --follow --json out/report.json https://httpbin.io/redirect/2
```

### 出力モード

ログに適したコンパクト（単一行）な計時を収集します：

```shell
httptap --compact https://httpbin.io/get
```

スクリプト向けに生のメトリクスを出力します：

```shell
httptap --metrics-only https://httpbin.io/get | tee timings.log
```

### 高度な使い方

プログラムから利用するユーザーは、高度なシナリオ向けにカスタムエグゼキューターを注入できます。リクエストの実行方法を
変更する必要がある場合（例えば、別の HTTP スタックを組み込む、あるいはトレーシングを追加する場合）は、独自の
`RequestExecutor` 実装を提供してください。

#### TLS 証明書オプション

自己署名エンドポイントのトラブルシューティング時に TLS 検証を回避します：

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

このフラグは証明書の検証を無効化し、多くのハンドシェイクの制約を緩和することで、レガシーな
エンドポイント（有効期限切れ／自己署名／ホスト名の不一致、弱いハッシュ、古い TLS バージョン）でも接続を完了できる
ようにします。最新の OpenSSL ビルドから削除された一部のアルゴリズム（例えば RC4 や 3DES）は、依然として利用
できない場合があります。このモードは信頼できるネットワークでのみ使用してください。

内部 API 向けにカスタム CA 証明書バンドルを使用します：

```shell
httptap --cacert /path/to/company-ca.pem https://internal-api.company.com
```

これは、システムのデフォルトのトラストストアに含まれないカスタム認証局（CA）によって署名された証明書を使用する
内部サービスをテストする際に役立ちます。`--cacert` オプション（`--ca-bundle` としても利用可能）は、PEM 形式の CA
証明書バンドルへのパスを受け付けます。

**注記：** `--ignore-ssl` と `--cacert` は排他的です。すべての検証を無効化するには `--ignore-ssl` を、カスタム CA
バンドルで検証するには `--cacert` を使用してください。

`--cacert` を使用した場合、CLI 出力は接続を `TLS CA: custom bundle` と示し、JSON エクスポートには
`network.tls_custom_ca: true` が含まれるため、自動化処理はカスタムトラスト構成を検出できます。

トラフィックを HTTP/SOCKS プロキシ経由でルーティングします（明示的な上書きは環境変数 `HTTP_PROXY`、`HTTPS_PROXY`、
`NO_PROXY` より優先されます）：

```shell
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get
```

すべてのプロキシ環境変数を無視し、直接接続します：

```shell
httptap --proxy "" https://httpbin.io/get
```

出力と JSON エクスポートにはプロキシ URI とその送信元が含まれるため、どの経路が使用されたかを確認できます
（例：`(from arg --proxy)`、`(from env HTTPS_PROXY)`、`(bypassed by env no_proxy)`）。

---

## SLO しきい値チェック

`--slo KEY=MS[,KEY=MS...]` を使って、フェーズごとのレイテンシ予算に基づき CI ジョブ、cron プローブ、Kubernetes の
レディネスチェックにゲートを設けます：

```shell
httptap --slo total=500,ttfb=200 https://api.example.com/health
```

- すべてのしきい値をパスした場合、`0` で終了します。
- **最後に成功したステップ**で少なくとも 1 つのしきい値を超過した場合、`4` で終了します（途中のリダイレクトは
  評価されません）。
- 仕様の書式が不正な場合（不明なキー、重複キー、正でない値、不正な構文）、`64` で終了します。
- 完全なウォーターフォール／コンパクト／JSON の出力は常にレンダリングされるため、回帰の証拠は保持されます。

サポートされるキー：`dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total`。

出力の拡張：

- **Rich／コンパクト** —— ウォーターフォールの後に表示される枠付きパネルが、しきい値と違反（実測値、しきい値、
  超過分）を一覧表示します。
- **`--metrics-only`** —— 最後に成功したステップに `slo=pass` または `slo=fail slo_violations=<keys>` トークンが
  付きます。
- **`--json`** —— `summary.slo` ブロックには `pass`、`thresholds_ms`、および違反ごとの
  `{key, threshold_ms, actual_ms, delta_ms}` が含まれます。

```shell
# CI gate — fail only on SLO violation, tolerate transient network errors
httptap --slo total=2000,tls=300,ttfb=800 https://staging.example.com/
case $? in
  0) echo "healthy" ;;
  4) echo "SLO violation"; exit 1 ;;
  75) echo "network flake, retrying later" ;;
esac
```

完全な仕様、評価ルール、およびレシピ：
[docs.httptap.dev/usage/slo](https://docs.httptap.dev/usage/slo/)。

---

## 環境変数

httptap は実行時に次の環境変数を読み取ります。これらはすべて CLI フラグで上書き可能であり、各リクエストで実際に
使用された送信元は出力と JSON エクスポートに記録されます。

| 変数                                   | 用途                                                                                                          | 上書き元              |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------|-----------------------|
| `HTTP_PROXY` / `http_proxy`           | `http://` ターゲットに使用されるプロキシ URL。                                                                  | `-x/--proxy`          |
| `HTTPS_PROXY` / `https_proxy`         | `https://` ターゲットに使用されるプロキシ URL。                                                                 | `-x/--proxy`          |
| `ALL_PROXY` / `all_proxy`             | スキーム固有の変数が未設定の場合のフォールバックプロキシ URL。                                                    | `-x/--proxy`          |
| `NO_PROXY` / `no_proxy`               | カンマ区切りの除外リスト（`*`、先頭の `.`、完全一致をサポート）。バイパスされたエントリは直接接続します。            | `--proxy ""`          |
| `NO_COLOR`                            | すべての Rich 出力で ANSI カラーを無効化します（[NO_COLOR](https://no-color.org) の慣習に従います）。              | —                     |
| `FORCE_COLOR`                         | stdout が TTY でない場合でも色付き出力を強制します（Rich の慣習）。                                              | —                     |
| `TERM=dumb`                           | Rich がプレーンテキストのレンダリングにダウングレードします。                                                     | —                     |

> プロキシ設定の優先順位：明示的な `-x/--proxy` → `--proxy ""`（環境変数を無効化）→
> `HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY`（スキーム一致）→ `NO_PROXY` による除外 → 直接接続。

---

## 終了コード

httptap は BSD の `sysexits.h` の慣習に従うため、shell パイプライン、CI ジョブ、systemd サービスとクリーンに統合
できます。

| コード | シンボル                | 意味                                                        |
|:-----:|-------------------------|------------------------------------------------------------|
| `0`   | `EX_OK`                 | 成功。                                                     |
| `4`   | —                       | SLO しきい値違反（リクエストは成功したが遅すぎる）。            |
| `64`  | `EX_USAGE`              | 不正なコマンドライン引数。                                    |
| `70`  | `EX_SOFTWARE`           | 内部エラー（予期しない例外、バグ）。                          |
| `75`  | `EX_TEMPFAIL`           | ネットワーク／TLS エラー（部分的な出力がレンダリングされる場合があります）。 |
| `128 + N` | シグナルオフセット    | シグナル `N` によって終了（例：`SIGINT`／Ctrl-C の場合は `130`）。 |

例 —— 一時的なネットワークの問題は許容しつつ、使用方法のエラー時のみ CI ジョブを失敗させます：

```shell
httptap --metrics-only https://api.example.com/health
rc=$?
if [ "$rc" = 64 ] || [ "$rc" = 70 ]; then
  exit "$rc"
fi
```

---


## リリース

### 前提条件

- リポジトリ設定で GitHub Environment `pypi` を構成しておく必要があります
- `ozeranskii/httptap` 向けに PyPI Trusted Publishing を構成しておく必要があります

### 手順

1. GitHub Actions から **Release** ワークフローをトリガーします：
   - 正確なバージョンを指定する（例：`0.3.0`）、または
   - バンプの種類を選択する：`patch`、`minor`、または `major`
2. ワークフローは次を行います：
   - `uv version` を使って `pyproject.toml` のバージョンを更新する
   - `git-cliff` で変更履歴を生成し、`CHANGELOG.md` を更新する
   - 変更をコミットし、git タグを作成する
   - タグ付けされたバージョンで全テストスイートを実行する
   - wheel とソース配布物をビルドする
   - Syft を使って CycloneDX および SPDX 形式の SBOM を生成する
   - 現在の OpenVEX ドキュメント（`.vex/httptap.openvex.json`）を添付する
   - Trusted Publishing（OIDC）経由で PyPI に公開する
   - wheel、sdist、SBOM、VEX のアセットを含む GitHub Release を作成する

---

## サンプル出力

![sample-output.png](docs/assets/sample-output.png)

リダイレクトの概要には合計行が含まれます：
![sample-follow-redirects-output.png](docs/assets/sample-follow-redirects-output.png)

---

## JSON エクスポート構造

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

## メトリクスのみのスクリプト化

```shell
httptap --metrics-only https://httpbin.io/get
```

```terminaloutput
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

---

## 高度な使い方

### カスタム実装

独自のリゾルバーや TLS インスペクターを差し替えます（`httptap.interfaces` の Protocol を満たすものであれば
何でも）：

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver


class HardcodedDNS(SystemDNSResolver):
    def resolve(self, host, port, timeout):
        return "93.184.216.34", "IPv4", 0.1


analyzer = HTTPTapAnalyzer(dns_resolver=HardcodedDNS())
steps = analyzer.analyze_url("https://httpbin.io")
```

---

## 開発

```shell
git clone https://github.com/ozeranskii/httptap.git
cd httptap
uv sync
uv run pytest
uv run ruff check
uv run ruff format .
```

テストは外向きのネットワークアクセスを前提としています。オフラインで実行する場合は、`SystemDNSResolver` /
`SocketTLSInspector` をモックできます。

---

## コントリビュート

1. リポジトリをフォークしてクローンします。
2. フィーチャーブランチを作成します。
3. コミット前に `pytest` と `ruff` を実行します。
4. 明確な説明と、関連するスクリーンショットやベンチマークを添えてプルリクエストを送信します。

バグ報告、機能提案、ドキュメント改善、そして創造的な新しい可視化やエクスポーターを歓迎します。

---

## ライセンス

Apache License 2.0 © Sergei Ozeranskii。詳細は [LICENSE](https://github.com/ozeranskii/httptap/blob/main/LICENSE)
を参照してください。

---

## 謝辞

- 素晴らしいライブラリの上に構築されています：[httpx](https://www.python-httpx.org/)、
  [httpcore](https://github.com/encode/httpcore)、[dnspython](https://www.dnspython.org/)、および
  [Rich](https://github.com/Textualize/rich)。
- Web パフォーマンスまわりのツールエコシステム（例：DevTools のウォーターフォール、`curl --trace`）から着想を
  得ています。
- Issue を立て、アイデアを共有し、パッチを提供してくださるすべての方々に特別な感謝を。

---

## Star History

<a href="https://www.star-history.com/?repos=ozeranskii%2Fhttptap&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ozeranskii/httptap&type=date&theme=dark&legend=top-left&sealed_token=l9nG3PE0bX5aj34TLoeySlfh-_SB3q51PgWOaU2CmnMGqBBvE8afuR1znzOdI0Vffj7Eh07VC1QPIOro5aeWb1B8BVdWOtnFhVcsJ22WFSfZkZWNx0v74LF--vP-rnm_WSMwooWGpUCQK24Anw5-qoqR2ItPauLxdsBhDZwLKJMEX0J46yaHWtJ-D1jc" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ozeranskii/httptap&type=date&legend=top-left&sealed_token=l9nG3PE0bX5aj34TLoeySlfh-_SB3q51PgWOaU2CmnMGqBBvE8afuR1znzOdI0Vffj7Eh07VC1QPIOro5aeWb1B8BVdWOtnFhVcsJ22WFSfZkZWNx0v74LF--vP-rnm_WSMwooWGpUCQK24Anw5-qoqR2ItPauLxdsBhDZwLKJMEX0J46yaHWtJ-D1jc" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ozeranskii/httptap&type=date&legend=top-left&sealed_token=l9nG3PE0bX5aj34TLoeySlfh-_SB3q51PgWOaU2CmnMGqBBvE8afuR1znzOdI0Vffj7Eh07VC1QPIOro5aeWb1B8BVdWOtnFhVcsJ22WFSfZkZWNx0v74LF--vP-rnm_WSMwooWGpUCQK24Anw5-qoqR2ItPauLxdsBhDZwLKJMEX0J46yaHWtJ-D1jc" />
 </picture>
</a>
