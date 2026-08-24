---
title: httptap
description: 基于 Rich 的命令行工具，将一次 HTTP 请求拆解为每个有意义的阶段
---

<p align="center">
  <img src="assets/httptap-banner.svg" alt="httptap" style="width: 100%; max-width: 1280px; height: auto;" />
</p>

# httptap

<div style="text-align: center; margin-bottom: 2em;">
  <p>
    <a href="https://pypi.org/project/httptap/"><img src="https://img.shields.io/pypi/v/httptap?color=3775A9&label=PyPI&logo=pypi" alt="PyPI" /></a>
    <a href="https://pypi.org/project/httptap/"><img src="https://img.shields.io/pypi/pyversions/httptap?logo=python" alt="Python Versions" /></a>
    <a href="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml"><img src="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
    <a href="https://codecov.io/github/ozeranskii/httptap"><img src="https://codecov.io/github/ozeranskii/httptap/graph/badge.svg?token=OFOHOI1X5J" alt="Coverage" /></a>
  </p>
</div>

`httptap` 是一个基于 Rich 的命令行工具，它将一次 HTTP 请求拆解为每个有意义的阶段——DNS 解析、TCP 连接、TLS
握手、服务器等待、以及响应体传输，并以时间线表格、紧凑摘要或机器友好的指标形式呈现结果。它专为交互式故障排查、回归分析
以及性能基线记录而设计。

!!! tip "特别优惠"
    <div style="text-align: center; margin-bottom: 0.6em;">
      :gift:{ style="font-size: 1.5em; margin-right: 0.35em; vertical-align: middle;" } <span style="font-weight: 700; font-size: 1.05em;">GitKraken Pro 立省 50%</span>
    </div>

    <div style="text-align: center; font-size: 0.95em; margin-bottom: 1em; line-height: 1.5;">
      将 GitKraken Client、用于 VS Code 的 GitLens 以及强大的 CLI 工具组合在一起，加速每一次仓库工作流。
    </div>

    <div style="display: block; text-align: center; margin-top: 1em; margin-bottom: 0.8em;">
      [:fontawesome-solid-bolt: 领取 50% 折扣](https://gitkraken.cello.so/vY8yybnplsZ){ .md-button .md-button--primary style="font-size: 0.95em; padding: 0.6em 1.8em; font-weight: 600; letter-spacing: 0.01em; background: linear-gradient(135deg, #3949ab 0%, #5e35b1 100%); border: none; box-shadow: 0 2px 8px rgba(57, 73, 171, 0.3);" }
    </div>

    <small style="display: block; margin-top: 0.6em; opacity: 0.75; font-size: 0.85em; text-align: center;">*httptap 社区专享*</small>

## 亮点

- **分阶段计时** —— 基于 httpcore 的 trace 钩子进行精确测量（当底层数据不可用时提供合理的回退估算）。
- **全部 HTTP 方法** —— GET、POST、PUT、PATCH、DELETE、HEAD、OPTIONS，均支持请求体。
- **请求体支持** —— 内联或从文件发送 JSON、XML 或任意数据，并自动检测 Content-Type。
- **IPv4/IPv6 感知** —— 解析器与 TLS 检查器会同时报告地址及其地址族。
- **TLS 洞察** —— 证书 CN、SAN、颁发者、序列号、有效期窗口与到期倒计时，以及加密套件和协议版本，均直接从当前连接自动采集（无需额外握手）。
- **多种输出模式** —— 丰富的瀑布图视图、紧凑的单行摘要，或用于脚本化的 `--metrics-only`。
- **JSON 导出** —— 持久化完整的分步数据（包含重定向链）以便后续处理。
- **可扩展** —— 为 DNS、TLS、计时、可视化和导出提供清晰的 Protocol 接口，便于插入自定义行为。

## 快速示例

**GET 请求：**
```bash
httptap https://httpbin.io/get
```

**带 JSON 数据的 POST 请求：**
```bash
httptap --data '{"name": "John"}' https://httpbin.io/post
```

![Sample Output](assets/sample-output.png)

## 核心特性

### 丰富的瀑布图可视化

借助基于 Rich 的精美终端 UI，查看 HTTP 请求各阶段的详细计时分解。

### 多种输出格式

- **Rich 模式**（默认）：带颜色和格式的精美瀑布图表格
- **紧凑模式**（`--compact`）：适合日志的单行摘要
- **指标模式**（`--metrics-only`）：用于脚本化和自动化的原始指标
- **JSON 导出**（`--json`）：包含重定向链的完整请求数据

### 高级网络洞察

- 带 IP 地址族检测（IPv4/IPv6）的 DNS 解析计时
- TCP 连接建立计时
- 带证书信息的 TLS 握手分析
- 首字节时间（TTFB）测量
- 响应体传输计时

### 重定向链支持

使用 `--follow` 参数跟随 HTTP 重定向，并查看链中每一步的计时分解。

## 下一步？

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **[安装](getting-started/installation.md)**

    ---

    数秒内开始使用 httptap

-   :material-lightning-bolt:{ .lg .middle } **[快速开始](getting-started/quick-start.md)**

    ---

    通过简单示例学习基础用法

-   :material-console:{ .lg .middle } **[使用指南](usage/basic.md)**

    ---

    探索所有特性与选项

-   :material-api:{ .lg .middle } **[API 参考](api/overview.md)**

    ---

    用自定义组件扩展 httptap

</div>

## 环境要求

- Python 3.10-3.15
- macOS、Linux 或 Windows
- 除标准网络能力外无系统依赖

## 许可证

Apache License 2.0 © Sergei Ozeranskii

## 联系

关注作者，获取来自真实经验的洞见：

- :fontawesome-brands-telegram:{ .telegram } **[Telegram 频道](https://t.me/sergeiozeranskii)** —— 开发、DevOps、架构与安全。真实经验与务实洞见，绝无废话。
- :fontawesome-brands-github: **[GitHub](https://github.com/ozeranskii)** —— 开源项目与贡献

## 致谢

构建于众多出色的库之上：

- [httpx](https://www.python-httpx.org/) —— 现代 HTTP 客户端
- [httpcore](https://github.com/encode/httpcore) —— 底层 HTTP 协议实现
- [dnspython](https://www.dnspython.org/) —— Python 的 DNS 工具包
- [Rich](https://github.com/Textualize/rich) —— 精美的终端格式化
