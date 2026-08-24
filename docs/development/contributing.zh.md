---
description: 如何搭建开发环境，并为 httptap 贡献代码、测试和文档。
---

# 贡献指南

我们欢迎对 httptap 的贡献！本指南将帮助你上手。

## 行为准则

请注意，本项目遵循 [Contributor Covenant 行为准则](https://github.com/ozeranskii/httptap/blob/main/CODE_OF_CONDUCT.md)。参与本项目即表示你应当维护此准则。

## 开始

### 前置条件

- Python 3.10 或更高版本（CPython）
- [uv](https://github.com/astral-sh/uv) 包管理器
- Git

### 搭建开发环境

1. **Fork 并克隆仓库：**

   ```bash
   git clone https://github.com/YOUR_USERNAME/httptap.git
   cd httptap
   ```

2. **安装依赖：**

   ```bash
   uv sync
   ```

3. **验证安装：**

   ```bash
   uv run httptap --version
   ```

## 开发工作流

### 运行测试

运行完整测试套件：

```bash
uv run pytest
```

带覆盖率运行：

```bash
uv run pytest --cov --cov-report=html
```

查看覆盖率报告：

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### 代码质量

#### 代码检查（Linting）

运行 Ruff linter：

```bash
uv run ruff check
```

自动修复问题：

```bash
uv run ruff check --fix
```

#### 格式化

检查格式：

```bash
uv run ruff format --check
```

自动格式化代码：

```bash
uv run ruff format .
```

#### 类型检查

运行 mypy：

```bash
uv run mypy httptap
```

### 运行基准测试

性能基准测试使用 [pytest-codspeed](https://codspeed.io)，并在 CI 中自动运行：

```bash
# 在本地运行基准测试（验证正确性，不产生性能数据）
uv run pytest tests/test_benchmarks.py --codspeed

# 在本地测量墙钟时间，并输出结果表
uv run pytest tests/test_benchmarks.py --codspeed --codspeed-mode=walltime

# 不使用 CodSpeed 运行基准测试（作为普通测试）
uv run pytest tests/test_benchmarks.py
```

基准测试覆盖 models、formatters、utils 和 exporter 模块中的纯计算函数。CI 会测量 CPU 指令数（`simulation`）和内存分配（`memory`）。

使用 `--codspeed-mode=walltime` 可在本地检查某项优化而无需等待 CI；每个基准大约耗时两秒。墙钟数值在共享硬件上本质上是有噪声的，因此 CI 转而依赖 `simulation`——请将本地的墙钟结果视为方向性信号，而非 CI 将报告的数值。

### 在本地运行

测试你的更改：

```bash
uv run httptap https://httpbin.io
```

或以可编辑模式安装：

```bash
uv pip install -e .
httptap https://httpbin.io
```

## 进行更改

### 分支命名

使用具有描述性的分支名称：

- `feature/add-http2-support` - 新功能
- `fix/tls-timeout-issue` - 缺陷修复
- `docs/update-api-reference` - 文档
- `refactor/extract-parser` - 代码重构

### 提交信息

遵循 conventional commits 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型（Types）：**

- `feat` - 新功能
- `fix` - 缺陷修复
- `docs` - 文档更改
- `refactor` - 代码重构
- `test` - 添加/更新测试
- `chore` - 维护任务
- `perf` - 性能改进

**示例：**

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

### 代码风格

遵循 [Google Python 风格指南](https://google.github.io/styleguide/pyguide.html)：

- 为所有函数签名使用类型提示
- 为所有公共 API 编写文档字符串
- 保持每行不超过 120 个字符
- 字符串使用双引号
- 遵循 PEP 8 命名约定

**示例：**

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

### 测试指引

- 为所有新功能编写测试
- 维持或提升代码覆盖率
- 使用具有描述性的测试名称
- Mock 外部依赖（DNS、TLS、HTTP）
- 同时测试成功和失败的情形

**示例：**

```python
def test_analyzer_follows_redirects(mock_http_client):
    """Test that analyzer follows redirect chains correctly."""
    analyzer = HTTPTapAnalyzer(follow_redirects=True)
    steps = analyzer.analyze_url("https://httpbin.io/redirect/3")

    assert len(steps) == 4  # Initial + 3 redirects
    assert steps[-1].response.status == 200
```

## Pull Request 流程

1. **创建功能分支：**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **进行更改并提交：**

   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

3. **推送到你的 fork：**

   ```bash
   git push origin feature/your-feature-name
   ```

4. **创建 Pull Request：**

    - 前往 [httptap 仓库](https://github.com/ozeranskii/httptap)
    - 点击 “New Pull Request”
    - 选择你的分支
    - 填写 PR 模板

### PR 检查清单

在提交之前，请确保：

- [ ] 测试通过（`uv run pytest`）
- [ ] 代码已格式化（`uv run ruff format .`）
- [ ] Linter 通过（`uv run ruff check`）
- [ ] 类型检查通过（`uv run mypy httptap`）
- [ ] 文档已更新（如有需要）
- [ ] CHANGELOG.md 已更新（针对重要更改）
- [ ] 提交信息遵循 conventional 格式

## 文档

### 更新文档

文档位于 `docs/` 目录：

```
docs/
├── getting-started/
├── usage/
├── api/
├── development/
└── about/
```

在本地构建文档：

```bash
uv sync --group docs
uv run mkdocs serve
```

访问：http://127.0.0.1:8000

### 文档规范

- 使用清晰、简洁的语言
- 包含代码示例
- 保持示例真实且实用
- 使用正确的 Markdown 格式
- 测试所有代码示例

## 可贡献的方向

### 适合新手的 Issue

寻找标记为 [`good first issue`](https://github.com/ozeranskii/httptap/labels/good%20first%20issue) 的 issue——这些对新手友好。

### 需要帮助

标记为 [`help wanted`](https://github.com/ozeranskii/httptap/labels/help%20wanted) 的 issue 是我们非常希望获得协助的优先事项。

### 贡献创意

- **HTTP/3 支持** - 扩展到最新的协议版本
- **更多导出格式** - CSV、XML、Prometheus 指标
- **额外的可视化** - 火焰图、图表
- **性能优化** - 更快的 DNS、连接池
- **更多 TLS 细节** - OCSP、证书链分析
- **自定义报告器** - Slack、webhook 通知
- **额外的协议** - WebSocket、gRPC 计时

## 获取帮助

- **GitHub Issues** - 缺陷报告和功能请求
- **Discussions** - 提问与一般性讨论
- **Discord** - 实时聊天（即将推出）

## 致谢

贡献者会在以下位置得到认可：

- [CHANGELOG.md](https://github.com/ozeranskii/httptap/blob/main/CHANGELOG.md)
- GitHub 贡献者页面
- 发布说明

感谢你为 httptap 做出贡献！🎉
