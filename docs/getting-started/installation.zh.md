---
description: 使用 uvx、Homebrew、PyPI、容器或源码安装 httptap，并启用 shell 自动补全。
---

# 安装

## 环境要求

在安装 httptap 之前，请确保你具备：

- **Python 3.10-3.15**（推荐 CPython）
- **pip** 或 **uv** 包管理器
- **macOS、Linux 或 Windows** 操作系统

除标准网络能力外，无需任何系统依赖。

## 使用 uvx 运行

无需永久安装即可运行 httptap 的最快方式。[`uvx`](https://docs.astral.sh/uv/guides/tools/)（随 [uv](https://docs.astral.sh/uv/) 一同提供）会获取 httptap 并在一个临时的、隔离的环境中运行它：

```bash
uvx --from "httptap[completion]" httptap https://example.com
```

!!! tip "推荐用于快速试用"
    `uvx` 无需任何预先的安装步骤，且不会留下任何残留——非常适合一次性检查或试用 httptap。若需反复使用，请用下列方法之一进行安装。

## 通过 Homebrew 安装

=== "macOS"

    ```bash
    brew install httptap
    ```

=== "Linux"

    ```bash
    brew install httptap
    ```

!!! tip "适合 macOS/Linux 用户"
    Homebrew 安装是最简单的方法，并包含自动的 shell 自动补全设置。

## 从 PyPI 安装

=== "使用 uv"

    ```bash
    uv pip install httptap
    ```

    或作为全局工具安装：

    ```bash
    uv tool install httptap
    ```

=== "使用 pip"

    ```bash
    pip install httptap
    ```

=== "使用 pipx"

    用于隔离式的 CLI 工具安装：

    ```bash
    pipx install httptap
    ```

## 通过容器运行

已签名的多架构（linux/amd64、linux/arm64）镜像会在每次发布时发布到 GitHub Container Registry：

```bash
docker run --rm ghcr.io/ozeranskii/httptap:latest https://example.com
```

使用 [cosign](https://docs.sigstore.dev/cosign/overview/)（无密钥 Sigstore）校验镜像签名：

```bash
cosign verify ghcr.io/ozeranskii/httptap:latest \
  --certificate-identity-regexp 'https://github\.com/ozeranskii/httptap/\.github/workflows/release\.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

固定的主/次版本标签（例如 `:0`、`:0.6`、`:0.6.0`）也会一并发布。

## 从源码安装

### 克隆仓库

```bash
git clone https://github.com/ozeranskii/httptap.git
cd httptap
```

### 使用 uv 安装

```bash
uv sync
```

### 使用 pip 安装

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## 验证安装

安装完成后，验证 httptap 是否正确安装：

```bash
httptap --version
```

你应该会看到类似如下的输出：

```
httptap X.Y.Z
```

## 升级

将 httptap 升级到最新版本：

=== "使用 Homebrew"

    ```bash
    brew upgrade httptap
    ```

=== "使用 uv"

    ```bash
    uv pip install --upgrade httptap
    ```

=== "使用 pip"

    ```bash
    pip install --upgrade httptap
    ```

## 卸载

从系统中移除 httptap：

=== "使用 Homebrew"

    ```bash
    brew uninstall httptap
    ```

=== "使用 uv"

    ```bash
    uv pip uninstall httptap
    ```

=== "使用 pip"

    ```bash
    pip uninstall httptap
    ```

=== "使用 pipx"

    ```bash
    pipx uninstall httptap
    ```

---

## Shell 自动补全

httptap 支持 bash 和 zsh 的 shell 自动补全。

### Homebrew 安装

如果你通过 Homebrew 安装了 httptap，**补全会自动配置好**。只需重启你的 shell：

```bash
# Restart your shell
exec $SHELL
```

Homebrew 会自动将补全脚本放置到：

- **Bash**：`$(brew --prefix)/etc/bash_completion.d/`
- **Zsh**：`$(brew --prefix)/share/zsh/site-functions/`

!!! success "无需额外设置"
    Homebrew 会自动处理所有补全设置。只需重启你的 shell，即可开始使用 Tab 补全！

### Python 包安装

如果你通过 `pip`、`uv` 或 `pipx` 安装了 httptap，则需要安装可选的 `completion` 附加项：

=== "使用 uv"

    ```bash
    uv pip install "httptap[completion]"
    ```

=== "使用 pip"

    ```bash
    pip install "httptap[completion]"
    ```

=== "使用 pipx"

    ```bash
    pipx install "httptap[completion]"
    ```

#### 激活

1. 激活你的虚拟环境（如果使用 venv）：

    ```bash
    source .venv/bin/activate
    ```

2. 为 bash/zsh 启用补全。可以一次性进行全局注册：

    ```bash
    activate-global-python-argcomplete
    ```

    或者，若只想为 `httptap` 启用补全，请将下面这行加入你的 shell 启动文件（例如 `~/.bashrc` 或 `~/.zshrc`）：

    ```bash
    eval "$(register-python-argcomplete httptap)"
    ```

3. 重启你的 shell。

### 用法

安装并激活后，你可以使用 `Tab` 来自动补全命令和选项：

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
    全局激活脚本仅为 bash 和 zsh 提供参数补全。其他 shell 不在该脚本覆盖范围内，需单独配置。

---

## 下一步？

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **[快速开始指南](quick-start.md)**

    ---

    通过简单示例学习基础用法

-   :material-console:{ .lg .middle } **[基础用法](../usage/basic.md)**

    ---

    完整的命令行参考

-   :material-api:{ .lg .middle } **[API 参考](../api/overview.md)**

    ---

    以编程方式使用 httptap

</div>
