---
description: httptap 基于 GitHub Actions 的自动化发布流程。
---

# 发布流程

本文档描述 httptap 的自动化发布流程。

## 概述

发布完全通过 GitHub Actions 实现自动化。该工作流负责版本管理、变更日志生成、测试、
构建、签名、发布到 TestPyPI 和 PyPI，并将一个
已签名的容器镜像推送到 GHCR。

## 前置条件

在创建发布之前，请确保：

1. **GitHub Environments** —— 在仓库设置中已配置 `release`、`testpypi` 和 `pypi` 环境，
   且均只允许从 `main` 部署；`pypi` 设有必需的审核人
2. **PyPI Trusted Publishing** —— 已为 PyPI 和 TestPyPI 配置（OIDC，无需令牌）
3. **Deploy Key** —— 具有写入权限的 SSH deploy key，仅作为 `release` 环境的 `DEPLOY_KEY` secret 保存，
   并被允许绕过 `main` 的分支保护以及保护 `refs/tags/v*` 的标签规则集
4. **GHCR access** —— release 任务上的 `packages: write` 权限（按工作流授予）
5. **所有测试通过** —— main 分支上的 CI 必须为绿色

## 发布工作流

发布流程通过 GitHub Actions 手动触发。

### 触发一次发布

1. 前往 **Actions** → **Release** 工作流
2. 点击 **Run workflow**
3. 选择版本策略：
    - **显式版本**：输入确切版本号（例如 `0.3.0`）
    - **语义化递增**：选择 `patch`、`minor` 或 `major`

### 语义化版本控制

| 递增类型 | 示例          | 使用场景                           |
|-----------|---------------|------------------------------------|
| `patch`   | 0.1.0 → 0.1.1 | 缺陷修复、小幅改进                  |
| `minor`   | 0.1.0 → 0.2.0 | 新功能，向后兼容                    |
| `major`   | 0.1.0 → 1.0.0 | 破坏性变更                          |

### 自动执行的操作

1. **版本更新**
   ```bash
   uv version 0.2.0  # or
   uv version --bump minor
   ```
   更新 `pyproject.toml` 中的 `version`

2. **锁文件刷新**
   ```bash
   uv lock
   ```
   重新生成 `uv.lock`，使其与新版本保持同步

3. **变更日志生成**
   ```bash
   git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
   ```
   基于约定式提交生成变更日志

4. **已签名的提交与标签（仅限本地）**
   ```bash
   git commit -S -m "chore: release v0.2.0"
   git tag -s v0.2.0 -m "Release v0.2.0"
   git bundle create release.bundle "^$GITHUB_SHA" HEAD refs/tags/v0.2.0
   ```
   通过 [gitsign](https://github.com/sigstore/gitsign) 进行无密钥 Sigstore 签名：
   短生命周期的 Fulcio 证书通过工作流的 OIDC
   身份签发，因此无需长期保存的 GPG 密钥。此时尚未推送任何内容：
   提交和标签以 git bundle 产物的形式传递给后续任务。

5. **构建**
   ```bash
   uv sync --locked --no-dev --group test
   uv run --no-sync pytest  # Full test suite
   uv build  # Create wheel and sdist
   uv venv "$RUNNER_TEMP/httptap-wheel"
   uv pip install --python "$RUNNER_TEMP/httptap-wheel" "$(echo dist/httptap-*.whl)[otel]"
   uv sync --locked --no-dev --no-install-project --group test --group e2e
   uv run --no-sync pytest tests/e2e --no-cov -n auto --httptap "$RUNNER_TEMP/httptap-wheel/bin/httptap"
   ```
   基于 bundle 中尚未推送的发布标签运行。随后，端到端测试套件针对以 `otel` extra 安装的已构建 wheel 运行 CLI，
   因此打包错误会在任何内容被证明或上传之前使发布失败。

6. **推送提交与标签**
   ```bash
   git push --atomic origin "v0.2.0^{commit}:refs/heads/main" refs/tags/v0.2.0:refs/tags/v0.2.0
   ```
   仅在构建和证明成功后执行。推送仅允许 fast-forward 且是原子的，因此如果发布期间
   `main` 有新的提交，分支和标签都不会更新，工作流会在此处停止，不会发布任何内容。

7. **发布到 TestPyPI**
    - 先通过 OIDC Trusted Publishing 上传到 TestPyPI，附带 PEP 740
      证明，作为投产推送前的冒烟测试。

8. **发布到 PyPI**
    - 使用 OIDC Trusted Publishing（无需令牌）
    - 上传 wheel 和源码分发包，附带 PEP 740 证明

9. **发布容器镜像到 GHCR**
    - 仅在发布到 PyPI 之后运行，因此会等待 `pypi` 的审核
    - 构建多架构（linux/amd64、linux/arm64）镜像
    - 推送到 `ghcr.io/ozeranskii/httptap`，带有 `{version}`、`{major}.{minor}`、
      `{major}` 和 `latest` 标签
    - 使用 cosign（无密钥 Sigstore）对镜像签名
    - 通过 `actions/attest-build-provenance` 附加 SLSA 构建来源证明

10. **GitHub Release**
    - 创建带有生成的发布说明的 release
    - 附上构建产物、SBOM、VEX 和 man 手册页

## 工作流配置

发布工作流定义于 `.github/workflows/release.yml`：

### 关键任务

#### 1. 准备发布

- 检出代码（只读，不使用 deploy key）
- 配置 Python 和 uv
- 更新 pyproject.toml 中的版本
- 生成变更日志
- 将本次发布加入 `.vex/httptap.openvex.json` 中 `fixed` 声明的产品列表，并递增文档版本
- 在本地创建已签名的发布提交和标签
- 将其作为 `release-bundle` 产物上传；不推送任何内容

#### 2. 构建软件包

- 从 bundle 中检出尚未推送的发布标签
- 运行完整测试套件
- 构建 wheel 和 sdist
- 针对以 `otel` extra 安装的已构建 wheel 运行端到端测试套件（`tests/e2e`）
- 通过 [Syft](https://github.com/anchore/syft) 以 CycloneDX 和 SPDX JSON 格式生成 SBOM
- 如果 `.vex/httptap.openvex.json` 中有 `fixed` 声明未列出本次发布则失败，随后将该文档复制到 `sbom/` 目录，命名为 `httptap-X.Y.Z.openvex.json`
- 使用 [argparse-manpage](https://github.com/praiskup/argparse-manpage) 生成经过 gzip 压缩的 `man(1)` 手册页
- 分别上传 `dist/`、`sbom/` 和 `man/` 产物

#### 3. 推送发布提交与标签

- 仅在构建和来源证明成功后运行
- 唯一写入 git 仓库的任务；它使用 `release` 环境的 deploy key 通过 SSH 推送，
  因此其工作流令牌是只读的（`contents: read`）
- 将 `main` fast-forward 到发布提交，并与标签一起在一次原子推送中完成；如果发布期间 `main`
  有新的提交，则失败且不发布任何内容

#### 4. 发布到 TestPyPI

- 下载 `dist/` 产物
- 通过 TestPyPI OIDC Trusted Publishing 发布，附带 PEP 740 证明

#### 5. 发布到 PyPI

- 仅在 TestPyPI 成功后运行
- 使用 Trusted Publishing 发布，附带 PEP 740 证明

#### 6. 发布容器镜像到 GHCR

- 仅在发布到 PyPI 之后运行，因此在 `pypi` 环境审核之前不会向 GHCR 发布任何内容
- 使用 Buildx + QEMU 构建多架构镜像
- 使用 cosign（无密钥 Sigstore OIDC）签名
- 附加 SLSA 构建来源证明

#### 7. 创建 GitHub Release

- 唯一拥有 `contents: write` 权限的任务，用于创建 release
- 下载 `dist/`、`sbom/` 和 `man/` 产物
- 创建带有变更日志说明的 GitHub release
- 附上 wheel、sdist、SBOM（`*.cdx.json`、`*.spdx.json`）、VEX（`*.openvex.json`）和 man 手册页

## 变更日志生成

变更日志基于约定式提交，使用 [git-cliff](https://git-cliff.org/) 自动生成。

### 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 支持的类型

| 类型       | 变更日志分区      | 示例                                     |
|------------|-------------------|------------------------------------------|
| `feat`     | Features          | `feat(cli): add --timeout flag`          |
| `fix`      | Bug Fixes         | `fix(tls): handle expired certificates`  |
| `perf`     | Performance       | `perf(dns): optimize resolver cache`     |
| `docs`     | Documentation     | `docs: update API reference`             |
| `refactor` | Refactor          | `refactor(core): extract analyzer logic` |
| `test`     | Testing           | `test: add integration tests`            |
| `chore`    | Miscellaneous     | `chore: update dependencies`             |

### 破坏性变更

在提交页脚中标记破坏性变更：

```
feat(api): redesign analyzer interface

BREAKING CHANGE: HTTPTapAnalyzer constructor signature changed
```

## 版本策略

httptap 遵循 [语义化版本控制](https://semver.org/)：

- **主版本号**（1.0.0）—— 破坏性变更
- **次版本号**（0.1.0）—— 新功能，向后兼容
- **修订版本号**（0.0.1）—— 缺陷修复

### 1.0 之前的开发

在 1.0 之前的开发阶段（0.x.x）：

- 次版本号可能包含破坏性变更
- 修订版本号用于缺陷修复和小功能
- 当 API 稳定后升级到 1.0.0

## 故障排查

### 分支保护错误

如果因分支保护导致推送失败：

1. 验证 deploy key 具有写入权限
2. 检查 deploy key 是否在分支保护规则和 `refs/tags/v*` 标签规则集的绕过列表中
3. 确保工作流检出中已配置 `ssh-key`
4. 检查 `DEPLOY_KEY` 是否为 `release` 环境的 secret，以及工作流是否从该环境唯一允许的分支 `main` 运行

### 变更日志为空

如果变更日志生成返回为空：

1. 确保提交遵循约定式格式
2. 检查 `.release/git-cliff.toml` 中的 git-cliff 配置
3. 验证标签尚不存在

### PyPI 发布失败

如果 PyPI 发布失败：

1. 验证 `pypi` 环境是否存在
2. 检查 PyPI 上是否已配置 Trusted Publishing
3. 确保工作流具有 `id-token: write` 权限

### 测试失败

如果发布期间测试失败：

1. 工作流会在发布前停止
2. 修复问题并重新运行工作流
3. 不会发生部分发布

## 发布之后

发布成功之后：

1. 在 PyPI 上验证软件包：https://pypi.org/project/httptap/
2. 检查 GitHub release：https://github.com/ozeranskii/httptap/releases
3. 测试安装：`uv pip install httptap=={version}`
4. 宣布发布（例如 GitHub Discussions、Telegram）

## 发布检查清单

在触发发布之前：

- [ ] main 上所有 CI 检查通过
- [ ] 没有已知的严重缺陷
- [ ] 文档已更新
- [ ] 破坏性变更已记录
- [ ] 迁移指南已编写（针对主版本）
- [ ] 依赖已更新
- [ ] 安全漏洞已处理

## 另见

- [约定式提交](https://www.conventionalcommits.org/)
- [语义化版本控制](https://semver.org/)
- [git-cliff 文档](https://git-cliff.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
