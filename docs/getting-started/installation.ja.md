---
description: uvx、Homebrew、PyPI、コンテナ、またはソースから httptap をインストールし、シェル補完を有効にする。
---

# インストール

## 動作要件

httptap をインストールする前に、以下があることを確認してください:

- **Python 3.10-3.15**（CPython 推奨）
- **pip** または **uv** パッケージマネージャ
- **macOS、Linux、または Windows** オペレーティングシステム

標準的なネットワーク機能以外にシステム依存関係は不要です。

## uvx で実行する

恒久的なインストールなしで httptap を実行する最速の方法です。[`uvx`](https://docs.astral.sh/uv/guides/tools/)（[uv](https://docs.astral.sh/uv/) に同梱）は httptap を取得し、一時的で隔離された環境で実行します:

```bash
uvx --from "httptap[completion]" httptap https://example.com
```

!!! tip "手軽に試すのにおすすめ"
    `uvx` は事前のインストール手順が不要で、何も残しません — 単発のチェックや httptap を試すのに最適です。繰り返し使う場合は、以下のいずれかの方法でインストールしてください。

## Homebrew でインストールする

=== "macOS"

    ```bash
    brew install httptap
    ```

=== "Linux"

    ```bash
    brew install httptap
    ```

!!! tip "macOS/Linux ユーザーに便利"
    Homebrew でのインストールは最もシンプルな方法で、シェル補完の自動セットアップも含まれます。

## PyPI からインストールする

=== "uv を使う"

    ```bash
    uv pip install httptap
    ```

    または、グローバルツールとしてインストールします:

    ```bash
    uv tool install httptap
    ```

=== "pip を使う"

    ```bash
    pip install httptap
    ```

=== "pipx を使う"

    隔離された CLI ツールとしてインストールする場合:

    ```bash
    pipx install httptap
    ```

## コンテナ経由で実行する

署名済みのマルチアーキテクチャ（linux/amd64、linux/arm64）イメージが、リリースごとに GitHub Container Registry に公開されます:

```bash
docker run --rm ghcr.io/ozeranskii/httptap:latest https://example.com
```

イメージの署名を [cosign](https://docs.sigstore.dev/cosign/overview/)（keyless Sigstore）で検証します:

```bash
cosign verify ghcr.io/ozeranskii/httptap:latest \
  --certificate-identity-regexp 'https://github\.com/ozeranskii/httptap/\.github/workflows/release\.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

固定されたメジャー/マイナータグ（例: `:0`、`:0.6`、`:0.6.0`）も公開されています。

## ソースからインストールする

### リポジトリをクローンする

```bash
git clone https://github.com/ozeranskii/httptap.git
cd httptap
```

### uv でインストールする

```bash
uv sync
```

### pip でインストールする

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## インストールの確認

インストール後、httptap が正しくインストールされたことを確認します:

```bash
httptap --version
```

次のような出力が表示されるはずです:

```
httptap X.Y.Z
```

## アップグレード

httptap を最新バージョンにアップグレードするには:

=== "Homebrew を使う"

    ```bash
    brew upgrade httptap
    ```

=== "uv を使う"

    ```bash
    uv pip install --upgrade httptap
    ```

=== "pip を使う"

    ```bash
    pip install --upgrade httptap
    ```

## アンインストール

httptap をシステムから削除するには:

=== "Homebrew を使う"

    ```bash
    brew uninstall httptap
    ```

=== "uv を使う"

    ```bash
    uv pip uninstall httptap
    ```

=== "pip を使う"

    ```bash
    pip uninstall httptap
    ```

=== "pipx を使う"

    ```bash
    pipx uninstall httptap
    ```

---

## シェル補完

httptap は bash と zsh のシェル補完をサポートしています。

### Homebrew でのインストール

Homebrew 経由で httptap をインストールした場合、**補完は自動的に構成されます**。シェルを再起動するだけです:

```bash
# Restart your shell
exec $SHELL
```

Homebrew は補完スクリプトを自動的に次の場所に配置します:

- **Bash**: `$(brew --prefix)/etc/bash_completion.d/`
- **Zsh**: `$(brew --prefix)/share/zsh/site-functions/`

!!! success "追加のセットアップは不要"
    Homebrew はすべての補完セットアップを自動的に処理します。シェルを再起動して、Tab 補完を使い始めるだけです！

### Python パッケージでのインストール

httptap を `pip`、`uv`、または `pipx` 経由でインストールした場合、オプションの `completion` エクストラをインストールする必要があります:

=== "uv を使う"

    ```bash
    uv pip install "httptap[completion]"
    ```

=== "pip を使う"

    ```bash
    pip install "httptap[completion]"
    ```

=== "pipx を使う"

    ```bash
    pipx install "httptap[completion]"
    ```

#### 有効化

1. 仮想環境を有効化します（venv を使用している場合）:

    ```bash
    source .venv/bin/activate
    ```

2. bash/zsh の補完を有効にします。一度グローバルに登録するか:

    ```bash
    activate-global-python-argcomplete
    ```

    または、`httptap` のみで有効にするには、これをシェルの起動ファイル（例: `~/.bashrc` または `~/.zshrc`）に追加します:

    ```bash
    eval "$(register-python-argcomplete httptap)"
    ```

3. シェルを再起動します。

### 使い方

インストールして有効化すると、`Tab` を使ってコマンドやオプションを自動補完できます:

```bash
# Complete command options
httptap --<TAB>

# Complete after typing partial option
httptap --fol<TAB>
# Completes to: httptap --follow

# Complete multiple options
httptap --follow --time<TAB>
# Completes to: httptap --follow --timeout
```

!!! note
    グローバル有効化スクリプトが提供する引数補完は bash と zsh のみです。その他のシェルはこのスクリプトの対象外であり、別途構成する必要があります。

---

## 次のステップ

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **[クイックスタートガイド](quick-start.md)**

    ---

    シンプルな例で基本を学ぶ

-   :material-console:{ .lg .middle } **[基本的な使い方](../usage/basic.md)**

    ---

    コマンドラインの完全なリファレンス

-   :material-api:{ .lg .middle } **[API リファレンス](../api/overview.md)**

    ---

    httptap をプログラムから使う

</div>
