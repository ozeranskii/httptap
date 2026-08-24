---
description: httptap 基于 GitHub Actions 的自动化发布流程，以及手动发布步骤。
---

# 发布流程

本文档描述 httptap 的自动化发布流程。

## 概述

发布完全通过 GitHub Actions 实现自动化。该工作流负责版本管理、变更日志生成、测试、
构建、签名、发布到 TestPyPI 和 PyPI，并将一个
已签名的容器镜像推送到 GHCR。

## 前置条件

在创建发布之前，请确保：

1. **GitHub Environments** —— 在仓库设置中已配置 `release`、`testpypi` 和 `pypi` 环境
2. **PyPI Trusted Publishing** —— 已为 PyPI 和 TestPyPI 配置（OIDC，无需令牌）
3. **Deploy Key** —— 具有写入权限的 SSH deploy key（用于绕过分支保护）
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

4. **已签名的提交与标签**
   ```bash
   git commit -S -m "chore: release v0.2.0"
   git tag -s v0.2.0 -m "Release v0.2.0"
   git push origin HEAD
   git push origin v0.2.0
   ```
   通过 [gitsign](https://github.com/sigstore/gitsign) 进行无密钥 Sigstore 签名：
   短生命周期的 Fulcio 证书通过工作流的 OIDC
   身份签发，因此无需长期保存的 GPG 密钥。

5. **构建**
   ```bash
   uv sync --locked --group test
   uv run pytest  # Full test suite
   uv build  # Create wheel and sdist
   ```

6. **发布到 TestPyPI**
    - 先通过 OIDC Trusted Publishing 上传到 TestPyPI，附带 PEP 740
      证明，作为投产推送前的冒烟测试。

7. **发布到 PyPI**
    - 使用 OIDC Trusted Publishing（无需令牌）
    - 上传 wheel 和源码分发包，附带 PEP 740 证明

8. **发布容器镜像到 GHCR**
    - 构建多架构（linux/amd64、linux/arm64）镜像
    - 推送到 `ghcr.io/ozeranskii/httptap`，带有 `{version}`、`{major}.{minor}`、
      `{major}` 和 `latest` 标签
    - 使用 cosign（无密钥 Sigstore）对镜像签名
    - 通过 `actions/attest-build-provenance` 附加 SLSA 构建来源证明

9. **GitHub Release**
    - 创建带有生成的发布说明的 release
    - 附上构建产物、SBOM、VEX 和 man 手册页

## 工作流配置

发布工作流定义于 `.github/workflows/release.yml`：

### 关键任务

#### 1. 准备发布

- 使用 deploy key 检出代码
- 配置 Python 和 uv
- 更新 pyproject.toml 中的版本
- 生成变更日志
- 提交并推送更改
- 创建并推送 git 标签

#### 2. 构建软件包

- 检出已打标签的版本
- 运行完整测试套件
- 构建 wheel 和 sdist
- 通过 [Syft](https://github.com/anchore/syft) 以 CycloneDX 和 SPDX JSON 格式生成 SBOM
- 将带版本号的 OpenVEX 文档从 `.vex/httptap.openvex.json` 复制到 `sbom/` 目录，命名为 `httptap-X.Y.Z.openvex.json`
- 使用 [argparse-manpage](https://github.com/praiskup/argparse-manpage) 生成经过 gzip 压缩的 `man(1)` 手册页
- 分别上传 `dist/`、`sbom/` 和 `man/` 产物

#### 3. 发布到 TestPyPI

- 下载 `dist/` 产物
- 通过 TestPyPI OIDC Trusted Publishing 发布，附带 PEP 740 证明

#### 4. 发布到 PyPI

- 仅在 TestPyPI 成功后运行
- 使用 Trusted Publishing 发布，附带 PEP 740 证明

#### 5. 发布容器镜像到 GHCR

- 使用 Buildx + QEMU 构建多架构镜像
- 使用 cosign（无密钥 Sigstore OIDC）签名
- 附加 SLSA 构建来源证明

#### 6. 创建 GitHub Release

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

## 手动发布步骤

如果你需要手动发布（不推荐）：

### 1. 更新版本

```bash
uv version 0.2.0
```

### 2. 重新生成锁文件

```bash
uv lock
```

### 3. 生成变更日志

```bash
git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
```

### 4. 提交更改

```bash
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release v0.2.0"
```

### 5. 创建标签

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
```

### 6. 推送

```bash
git push origin main
git push origin v0.2.0
```

### 7. 构建并发布

```bash
uv build
uv publish  # Requires PyPI credentials
```

### 8. 创建 GitHub Release

使用 `gh` CLI 或网页界面创建带有变更日志说明的 release。

## 故障排查

### 分支保护错误

如果因分支保护导致推送失败：

1. 验证 deploy key 具有写入权限
2. 检查 deploy key 是否在分支保护规则的绕过列表中
3. 确保工作流检出中已配置 `ssh-key`

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
