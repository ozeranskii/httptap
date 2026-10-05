---
description: httptap の自動化された GitHub Actions リリースプロセス。
---

# リリースプロセス

この文書は httptap の自動化されたリリースプロセスを説明します。

## 概要

リリースは GitHub Actions を使用して完全に自動化されています。ワークフローは、バージョニング、変更履歴の生成、テスト、ビルド、署名、TestPyPI と PyPI への公開、および署名済みコンテナイメージの GHCR へのプッシュを処理します。

## 前提条件

リリースを作成する前に、以下を確認してください:

1. **GitHub Environments** - リポジトリ設定で `release`、`testpypi`、および `pypi` 環境が設定されており、いずれも `main` からのデプロイのみを許可している。`pypi` には必須レビュアーが設定されている
2. **PyPI Trusted Publishing** - PyPI と TestPyPI の両方に設定されている（OIDC、トークンなし）
3. **Deploy Key** - 書き込みアクセス権を持つ SSH デプロイキー。`release` 環境のシークレット `DEPLOY_KEY` としてのみ保存され、`main` のブランチ保護と `refs/tags/v*` を保護するタグルールセットをバイパスできる
4. **GHCR アクセス** - リリースジョブでの `packages: write` 権限（ワークフローごとに付与）
5. **すべてのテストが通過** - main ブランチで CI がグリーンでなければならない

## リリースワークフロー

リリースプロセスは GitHub Actions を介して手動でトリガーされます。

### リリースのトリガー

1. **Actions** → **Release** ワークフローに移動する
2. **Run workflow** をクリックする
3. バージョン戦略を選択する:
    - **明示的なバージョン**: 正確なバージョンを入力する（例: `0.3.0`）
    - **セマンティックバンプ**: `patch`、`minor`、または `major` を選択する

### セマンティックバージョニング

| バンプ種類 | 例       | ユースケース                           |
|-----------|---------------|------------------------------------|
| `patch`   | 0.1.0 → 0.1.1 | バグ修正、小さな改善      |
| `minor`   | 0.1.0 → 0.2.0 | 新機能、後方互換性あり |
| `major`   | 0.1.0 → 1.0.0 | 破壊的変更                   |

### 自動的に行われること

1. **バージョンの更新**
   ```bash
   uv version 0.2.0  # or
   uv version --bump minor
   ```
   `pyproject.toml` の `version` を更新する

2. **ロックファイルの更新**
   ```bash
   uv lock
   ```
   新しいバージョンと同期を保つように `uv.lock` を再生成する

3. **変更履歴の生成**
   ```bash
   git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
   ```
   conventional commits から変更履歴を生成する

4. **署名済みのコミットとタグ（ローカルのみ）**
   ```bash
   git commit -S -m "chore: release v0.2.0"
   git tag -s v0.2.0 -m "Release v0.2.0"
   git bundle create release.bundle "^$GITHUB_SHA" HEAD refs/tags/v0.2.0
   ```
   [gitsign](https://github.com/sigstore/gitsign) を介した鍵なしの Sigstore 署名: 短命の Fulcio 証明書がワークフローの OIDC アイデンティティを通じて発行されるため、長期間有効な GPG 鍵は不要である。この時点ではまだ何もプッシュされない: コミットとタグは git バンドルの成果物として後続のジョブに渡される。

5. **ビルド**
   ```bash
   uv sync --locked --no-dev --group test
   uv run --no-sync pytest  # Full test suite
   uv build  # Create wheel and sdist
   ```
   バンドルから取得した、まだプッシュされていないリリースタグ上で実行される。

6. **コミットとタグのプッシュ**
   ```bash
   git push --atomic origin "v0.2.0^{commit}:refs/heads/main" refs/tags/v0.2.0:refs/tags/v0.2.0
   ```
   ビルドと証明が成功した後にのみ行われる。プッシュは fast-forward のみかつアトミックであるため、リリース中に `main` が進んでいた場合、ブランチもタグも更新されず、ワークフローは何かが公開される前にここで停止する。

7. **TestPyPI への公開**
    - 本番プッシュの前のスモークテストとして、PEP 740 の証明書とともに OIDC Trusted Publishing を介してまず TestPyPI にアップロードする。

8. **PyPI への公開**
    - OIDC Trusted Publishing を使用する（トークン不要）
    - PEP 740 の証明書とともに wheel とソース配布物をアップロードする

9. **コンテナイメージの GHCR への公開**
    - PyPI への公開後にのみ実行されるため、`pypi` のレビューを待つ
    - マルチアーキテクチャ（linux/amd64、linux/arm64）イメージをビルドする
    - `{version}`、`{major}.{minor}`、`{major}`、および `latest` タグとともに `ghcr.io/ozeranskii/httptap` にプッシュする
    - cosign（鍵なし Sigstore）でイメージに署名する
    - `actions/attest-build-provenance` を介して SLSA ビルドプロベナンスを添付する

10. **GitHub Release**
    - 生成されたノートとともにリリースを作成する
    - ビルド成果物、SBOM、VEX、および man ページを添付する

## ワークフローの設定

リリースワークフローは `.github/workflows/release.yml` で定義されています:

### 主要なジョブ

#### 1. Prepare Release

- コードをチェックアウトする（読み取り専用、デプロイキーなし）
- Python と uv を設定する
- pyproject.toml のバージョンを更新する
- 変更履歴を生成する
- `.vex/httptap.openvex.json` の `fixed` ステートメントにリリースを追加し、文書のバージョンを上げる
- 署名済みのリリースコミットとタグをローカルで作成する
- それらを `release-bundle` 成果物としてアップロードする。何もプッシュしない

#### 2. Build Package

- バンドルから、まだプッシュされていないリリースタグをチェックアウトする
- 完全なテストスイートを実行する
- wheel と sdist をビルドする
- [Syft](https://github.com/anchore/syft) を介して CycloneDX および SPDX JSON 形式の SBOM を生成する
- `.vex/httptap.openvex.json` の `fixed` ステートメントにリリースが含まれていなければ失敗し、その後文書を `sbom/` ディレクトリに `httptap-X.Y.Z.openvex.json` としてコピーする
- [argparse-manpage](https://github.com/praiskup/argparse-manpage) を介して gzip 圧縮された `man(1)` ページを生成する
- `dist/`、`sbom/`、および `man/` の成果物を個別にアップロードする

#### 3. Push Release Commit and Tag

- ビルドとプロベナンスの証明が成功した後にのみ実行される
- git リポジトリに書き込む唯一のジョブである。`release` 環境のデプロイキーを使って SSH でプッシュするため、ワークフロートークンは読み取り専用（`contents: read`）である
- `main` をリリースコミットまで fast-forward し、タグとともに 1 回のアトミックなプッシュで送る。リリース中に `main` が進んでいた場合は、何も公開せずに失敗する

#### 4. Publish to TestPyPI

- `dist/` の成果物をダウンロードする
- PEP 740 の証明書とともに TestPyPI OIDC Trusted Publishing を介して公開する

#### 5. Publish to PyPI

- TestPyPI が成功した後にのみ実行される
- PEP 740 の証明書とともに Trusted Publishing を使用して公開する

#### 6. Publish container image to GHCR

- PyPI への公開後にのみ実行されるため、`pypi` 環境のレビュー前に GHCR へ何も公開されない
- Buildx + QEMU でマルチアーキテクチャイメージをビルドする
- cosign（鍵なし Sigstore OIDC）で署名する
- SLSA ビルドプロベナンスを添付する

#### 7. Create GitHub Release

- `contents: write` を持つ唯一のジョブであり、リリースの作成に必要とする
- `dist/`、`sbom/`、および `man/` の成果物をダウンロードする
- 変更履歴のノートとともに GitHub リリースを作成する
- wheel、sdist、SBOM（`*.cdx.json`、`*.spdx.json`）、VEX（`*.openvex.json`）、および man ページを添付する

## 変更履歴の生成

変更履歴は、conventional commits に基づいて [git-cliff](https://git-cliff.org/) を使用して自動的に生成されます。

### コミット形式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### サポートされる種類

| 種類       | 変更履歴のセクション | 例                                  |
|------------|-------------------|------------------------------------------|
| `feat`     | Features          | `feat(cli): add --timeout flag`          |
| `fix`      | Bug Fixes         | `fix(tls): handle expired certificates`  |
| `perf`     | Performance       | `perf(dns): optimize resolver cache`     |
| `docs`     | Documentation     | `docs: update API reference`             |
| `refactor` | Refactor          | `refactor(core): extract analyzer logic` |
| `test`     | Testing           | `test: add integration tests`            |
| `chore`    | Miscellaneous     | `chore: update dependencies`             |

### 破壊的変更

コミットのフッターで破壊的変更をマークします:

```
feat(api): redesign analyzer interface

BREAKING CHANGE: HTTPTapAnalyzer constructor signature changed
```

## バージョン戦略

httptap は [Semantic Versioning](https://semver.org/) に従います:

- **メジャーバージョン**（1.0.0） - 破壊的変更
- **マイナーバージョン**（0.1.0） - 新機能、後方互換性あり
- **パッチバージョン**（0.0.1） - バグ修正

### 1.0 以前の開発

1.0 以前の開発（0.x.x）の間:

- マイナーバージョンは破壊的変更を含む場合がある
- パッチバージョンはバグ修正と小さな機能のため
- API が安定したら 1.0.0 に移行する

## トラブルシューティング

### ブランチ保護エラー

ブランチ保護が原因でプッシュが失敗する場合:

1. デプロイキーが書き込みアクセス権を持っていることを検証する
2. デプロイキーがブランチ保護ルールと `refs/tags/v*` のタグルールセットのバイパスリストにあることを確認する
3. ワークフローのチェックアウトで `ssh-key` が設定されていることを確認する
4. `DEPLOY_KEY` が `release` 環境のシークレットであり、ワークフローが環境で許可された唯一のブランチである `main` から実行されたことを確認する

### 変更履歴が空

変更履歴の生成が空を返す場合:

1. コミットが conventional 形式に従っていることを確認する
2. `.release/git-cliff.toml` の git-cliff 設定を確認する
3. タグがすでに存在しないことを検証する

### PyPI 公開が失敗

PyPI 公開が失敗する場合:

1. `pypi` 環境が存在することを検証する
2. Trusted Publishing が PyPI で設定されていることを確認する
3. ワークフローが `id-token: write` 権限を持っていることを確認する

### テストの失敗

リリース中にテストが失敗する場合:

1. ワークフローは公開前に停止する
2. 問題を修正してワークフローを再実行する
3. 部分的なリリースは発生しない

## リリース後

リリースが成功した後:

1. PyPI でパッケージを検証する: https://pypi.org/project/httptap/
2. GitHub リリースを確認する: https://github.com/ozeranskii/httptap/releases
3. インストールをテストする: `uv pip install httptap=={version}`
4. リリースを告知する（例: GitHub Discussions、Telegram）

## リリースチェックリスト

リリースをトリガーする前に:

- [ ] main ですべての CI チェックが通過している
- [ ] 既知の重大なバグがない
- [ ] ドキュメントが更新されている
- [ ] 破壊的変更が文書化されている
- [ ] 移行ガイドが書かれている（メジャーバージョンの場合）
- [ ] 依存関係が更新されている
- [ ] セキュリティ脆弱性が対処されている

## 関連項目

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [git-cliff documentation](https://git-cliff.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
