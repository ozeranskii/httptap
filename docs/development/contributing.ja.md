---
description: 開発環境をセットアップし、httptap にコード、テスト、ドキュメントをコントリビュートする方法。
---

# コントリビュート

httptap へのコントリビュートを歓迎します！このガイドは始めるのに役立ちます。

## 行動規範

このプロジェクトは [Contributor Covenant Code of Conduct](https://github.com/ozeranskii/httptap/blob/main/CODE_OF_CONDUCT.md) に従っていることに注意してください。参加することで、あなたはこの規範を遵守することが期待されます。

## はじめに

### 前提条件

- Python 3.11 以上（CPython）
- [uv](https://github.com/astral-sh/uv) パッケージマネージャー
- Git

### 開発環境のセットアップ

1. **リポジトリをフォークしてクローンする:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/httptap.git
   cd httptap
   ```

2. **依存関係をインストールする:**

   ```bash
   uv sync
   ```

3. **インストールを検証する:**

   ```bash
   uv run httptap --version
   ```

## 開発ワークフロー

### テストの実行

完全なテストスイートを実行する:

```bash
uv run pytest
```

カバレッジ付きで実行する:

```bash
uv run pytest --cov --cov-report=html
```

カバレッジレポートを表示する:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### コード品質

#### リンティング

Ruff リンターを実行する:

```bash
uv run ruff check
```

問題を自動修正する:

```bash
uv run ruff check --fix
```

#### フォーマット

フォーマットをチェックする:

```bash
uv run ruff format --check
```

コードを自動フォーマットする:

```bash
uv run ruff format .
```

#### 型チェック

mypy を実行する:

```bash
uv run mypy httptap
```

### ベンチマークの実行

パフォーマンスベンチマークは [pytest-codspeed](https://codspeed.io) を使用し、CI で自動的に実行されます:

```bash
# ベンチマークをローカルで実行する（正しさを検証、パフォーマンスデータなし）
uv run pytest tests/test_benchmarks.py --codspeed

# ローカルで実測時間を計測する、結果テーブル付き
uv run pytest tests/test_benchmarks.py --codspeed --codspeed-mode=walltime

# CodSpeed なしでベンチマークを実行する（通常のテストとして）
uv run pytest tests/test_benchmarks.py
```

ベンチマークは、models、formatters、utils、および exporter モジュールにわたる純粋な計算関数をカバーします。CI は CPU 命令（`simulation`）とメモリ割り当て（`memory`）を計測します。

CI を待たずにローカルで最適化を確認するには `--codspeed-mode=walltime` を使用してください; ベンチマークごとにおよそ 2 秒かかります。実測時間の数値は共有ハードウェア上では本質的にノイズが多いため、CI は代わりに `simulation` に依存します — ローカルの walltime 結果は、CI が報告する値としてではなく、方向性を示すシグナルとして扱ってください。

### エンドツーエンドテストの実行

`tests/e2e` のスイートは `httptap` CLI をサブプロセスとして実行し、ローカルの HTTP、TLS、プロキシ、SOCKS5、OTLP サーバーに対してテストします。通常の `uv run pytest` では収集されないため、ディレクトリを明示的に指定してください:

```bash
# ソースチェックアウトに対して実行する（OTLP テストには otel extra が必要）
uv run --extra otel pytest tests/e2e --no-cov -n auto

# インストール済みの wheel など、別のビルドに対して実行する
uv run pytest tests/e2e --no-cov -n auto --httptap /path/to/venv/bin/httptap
```

CI はビルドされた wheel とコンテナイメージに対して実行し、毎日実行される **E2E matrix** ワークフローが Linux、macOS、Windows 上の Python 3.11、3.13、3.14、3.14t、3.15、3.15t で繰り返します。Docker イメージに対する実行方法とすべてのオプションについては [tests/e2e/README.md](https://github.com/ozeranskii/httptap/blob/main/tests/e2e/README.md) を参照してください。

### ローカルでの実行

変更をテストする:

```bash
uv run httptap https://httpbin.io
```

または editable モードでインストールする:

```bash
uv pip install -e .
httptap https://httpbin.io
```

## 変更を加える

### ブランチの命名

説明的なブランチ名を使用してください:

- `feature/add-http2-support` - 新機能
- `fix/tls-timeout-issue` - バグ修正
- `docs/update-api-reference` - ドキュメント
- `refactor/extract-parser` - コードのリファクタリング

### コミットメッセージ

conventional commits 形式に従ってください:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**種類:**

- `feat` - 新機能
- `fix` - バグ修正
- `docs` - ドキュメントの変更
- `refactor` - コードのリファクタリング
- `test` - テストの追加/更新
- `chore` - メンテナンス作業
- `perf` - パフォーマンスの改善

**例:**

```
feat(cli): add --timeout flag for request timeout

Add command-line option to specify custom timeout for HTTP requests.
Defaults to 20 seconds if not specified.

Closes #123
```

```
fix(tls): handle certificate expiry edge case

Fix crash when certificate expiry date is in the past.
Now properly reports negative days and warns user.

Fixes #456
```

### コードスタイル

[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) に従ってください:

- すべての関数シグネチャに型ヒントを使用する
- すべての公開 API に docstring を書く
- 行を 120 文字未満に保つ
- 文字列にはダブルクォートを使用する
- PEP 8 の命名規則に従う

**例:**

```python
def resolve_hostname(host: str, timeout: float = 5.0) -> tuple[str, str]:
    """Resolve hostname to IP address.

    Args:
        host: Hostname to resolve.
        timeout: Maximum time to wait in seconds.

    Returns:
        Tuple of (ip_address, family).

    Raises:
        DNSError: If resolution fails.
    """
    pass
```

### テストのガイドライン

- すべての新機能にテストを書く
- コードカバレッジを維持または改善する
- 説明的なテスト名を使用する
- 外部依存関係（DNS、TLS、HTTP）をモックする
- 成功と失敗の両方のケースをテストする

**例:**

```python
def test_analyzer_follows_redirects(mock_http_client):
    """Test that analyzer follows redirect chains correctly."""
    analyzer = HTTPTapAnalyzer(follow_redirects=True)
    steps = analyzer.analyze_url("https://httpbin.io/redirect/3")

    assert len(steps) == 4  # Initial + 3 redirects
    assert steps[-1].response.status == 200
```

## プルリクエストのプロセス

1. **feature ブランチを作成する:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **変更を加えてコミットする:**

   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

3. **フォークにプッシュする:**

   ```bash
   git push origin feature/your-feature-name
   ```

4. **プルリクエストを作成する:**

    - [httptap リポジトリ](https://github.com/ozeranskii/httptap) に移動する
    - 「New Pull Request」をクリックする
    - ブランチを選択する
    - PR テンプレートに記入する

### PR チェックリスト

提出する前に、以下を確認してください:

- [ ] テストが通る（`uv run pytest`）
- [ ] コードがフォーマットされている（`uv run ruff format .`）
- [ ] リンターが通る（`uv run ruff check`）
- [ ] 型チェックが通る（`uv run mypy httptap`）
- [ ] ドキュメントが更新されている（必要な場合）
- [ ] コミットメッセージが conventional 形式に従っている（`CHANGELOG.md` はリリース時に git-cliff がコミットメッセージから生成するため、手動で編集しないでください）

## ドキュメント

### ドキュメントの更新

ドキュメントは `docs/` ディレクトリにあります:

```
docs/
├── getting-started/
├── usage/
├── api/
├── development/
└── about/
```

ドキュメントをローカルでビルドする:

```bash
uv sync --group docs
uv run mkdocs serve
```

以下で表示する: http://127.0.0.1:8000

### ドキュメントの標準

- 明確で簡潔な言葉を使用する
- コード例を含める
- 例を現実的かつ実用的に保つ
- 適切な Markdown フォーマットを使用する
- すべてのコード例をテストする

## コントリビュートの領域

### Good First Issues

[`good first issue`](https://github.com/ozeranskii/httptap/labels/good%20first%20issue) というラベルの付いた issue を探してください - これらは初心者に優しいものです。

### Help Wanted

[`help wanted`](https://github.com/ozeranskii/httptap/labels/help%20wanted) というラベルの付いた issue は、私たちが支援を歓迎する優先事項です。

### コントリビュートのアイデア

以下は[ロードマップ](https://github.com/ozeranskii/httptap/blob/main/ROADMAP.md)の対象範囲内のテーマに沿ったものです。ロードマップには非目標（負荷テスト、WebSocket や gRPC などの HTTP 以外のプロトコル、GUI/TUI、プラグインローダー）も記載されています:

- **タイミング精度** - トレースフックとフォールバック推定の改良
- **より多くのエクスポート形式** - 具体的なニーズに基づくさらなる機械可読エクスポーター（Prometheus と OpenTelemetry へのエクスポートはすでに提供済み）
- **SLO の拡張** - ベースラインに対する相対的な予算、ソフト SLO とハード SLO
- **より詳細な TLS 情報** - OCSP、証明書チェーンの分析
- **HTTP/3 サポート** - 上流で安定した Python サポートが提供され次第
- **ドキュメント** - 実践的な例、トラブルシューティングのレシピ、統合のクックブック

## ヘルプを得る

- **GitHub Issues** - バグ報告と機能リクエスト
- **Discussions** - 質問と一般的な議論
- **Discord** - リアルタイムチャット（近日公開）

## 謝辞

コントリビューターは以下で認められます:

- [CHANGELOG.md](https://github.com/ozeranskii/httptap/blob/main/CHANGELOG.md)
- GitHub Contributors ページ
- リリースノート

httptap へのコントリビュートありがとうございます！🎉
