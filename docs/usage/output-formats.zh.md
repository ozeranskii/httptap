---
description: 在丰富、紧凑、仅指标和 JSON 输出模式之间选择，以适应调试或自动化场景。
---

# 输出格式

httptap 支持多种输出格式，以适应从交互式故障排查到自动化脚本化的不同使用场景。

## 丰富模式（默认）

默认的输出格式使用 [Rich](https://github.com/Textualize/rich) 库在你的终端中显示一个精美的瀑布图表格。

```bash
httptap https://httpbin.io
```

### 特性

- **带语法高亮的彩色输出**
- **计时阶段的可视化进度条**
- **便于阅读的结构化表格**
- **网络详情**，包括 IP、TLS 版本和证书信息
- **响应元数据**，显示状态、请求头和响应体大小

### 何时使用

- 交互式调试会话
- 请求性能的可视化检查
- 向利益相关者展示计时数据

## 紧凑模式

每一步一行人类可读的信息，专为终端日志和重定向链追踪而设计。

```bash
httptap --compact https://httpbin.io/get
```

### 示例输出

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

### 特性

- **每步单行** —— 先是 HTTP 状态，然后是方法和 URL，再是各阶段计时，最后是人类可读的响应体大小。
- **计时带 `ms` 后缀**，因此与散文式日志条目并排时读起来更自然。
- **响应大小**会以适当的单位（`B`、`KB`、`MB`）格式化。
- **重定向摘要表格**仍会在各步骤行之后打印，以便整条链的整体形态保持可见。

### 何时使用

- 追加到日志文件
- 快速的性能比较
- CI / CD 流水线输出，同时你仍希望看到 URL 和状态
- 当完整瀑布图过于嘈杂时的终端友好摘要

## 仅指标模式

未经格式化的原始指标，为其他工具的解析而优化。

```bash
httptap --metrics-only https://httpbin.io
```

### 示例输出

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

### 特性

- **机器可解析**的格式
- **完整指标**，包括网络详情
- **一致的结构**，便于提取
- **无颜色或格式化**字符

### 何时使用

- 脚本化和自动化
- 用于分析的数据采集
- 与监控工具集成
- 使用 awk/grep/sed 解析

### 解析示例

```bash
# 提取 TTFB 值
httptap --metrics-only https://httpbin.io/delay/1 | grep -oP 'ttfb=\K[0-9.]+'

# 获取所有计时指标
httptap --metrics-only https://httpbin.io/get | \
  awk '{for(i=1;i<=NF;i++){if($i ~ /=/) print $i}}'
```

## JSON 导出

将完整的请求数据导出为结构化 JSON，以便进行全面分析。

```bash
httptap --json output.json https://httpbin.io
```

### JSON 结构

```json
{
  "initial_url": "https://httpbin.io",
  "total_steps": 1,
  "steps": [
    {
      "url": "https://httpbin.io",
      "step_number": 1,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 8.947,
        "connect_ms": 96.977,
        "tls_ms": 194.566,
        "ttfb_ms": 445.951,
        "total_ms": 447.344,
        "wait_ms": 145.461,
        "xfer_ms": 1.392,
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
        "status": 200,
        "bytes": 389,
        "content_type": "application/json",
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": null,
        "headers": {
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-type": "application/json",
          "server": "gunicorn/19.9.0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    }
  ],
  "summary": {
    "total_time_ms": 447.344,
    "final_status": 200,
    "final_url": "https://httpbin.io",
    "final_bytes": 389,
    "errors": 0
  }
}
```

### 特性

- **所有阶段的完整数据导出**
- **结构化格式**，便于解析
- **重定向链支持**，包含多个步骤
- **元数据保留**（请求头、时间戳）
- **错误信息**（请求失败时）

### 何时使用

- 后处理分析
- 与数据管道集成
- 长期性能跟踪
- 详细的调试会话
- 与团队成员共享结果

### 处理示例

使用 `jq` 提取特定字段：

```bash
# 获取总时间
jq '.summary.total_time_ms' output.json

# 提取所有 TTFB 值
jq '.steps[].timing.ttfb_ms' output.json

# 获取证书到期信息
jq '.steps[0].network.cert_days_left' output.json

# 筛选失败的请求
jq 'select(.summary.errors > 0)' output.json
```

## 重定向链

使用 `--follow` 时，所有输出格式都会包含重定向链中每一步的数据。

### 丰富模式

显示一个包含整条链合计值的摘要表格。

```bash
httptap --follow https://httpbin.io/redirect/3
```

### 紧凑模式

每个重定向步骤输出一行，随后是重定向链摘要表格。

```bash
httptap --follow --compact https://httpbin.io/redirect/2
```

输出：

```
Step 1: 302 GET https://httpbin.io/redirect/2 | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 0 B
Step 2: 302 GET https://httpbin.io/relative-redirect/1 | dns=2.7ms connect=97.5ms tls=194.0ms ttfb=400.2ms total=400.6ms | 0 B
Step 3: 200 GET https://httpbin.io/get | dns=2.6ms connect=97.4ms tls=197.3ms ttfb=403.2ms total=404.0ms | 389 B
```

### JSON 导出

在 `steps` 数组中包含所有步骤，附带完整的计时和元数据。

```bash
httptap --follow --json redirect-chain.json https://httpbin.io/redirect/3
```

## 组合选项

输出格式选项可与其他参数组合使用：

```bash
# 跟随重定向并使用紧凑输出
httptap --follow --compact https://httpbin.io/redirect/2

# 将重定向链导出为 JSON 并显示指标
httptap --follow --json chain.json --metrics-only https://bit.ly/example
```

!!! note
    当 `--json` 与显示模式（`--compact`、`--metrics-only`）同时使用时，显示模式会输出到 stdout，而 JSON 会写入文件。

---

## SLO 阈值叠加

`--slo KEY=MS[,KEY=MS...]` 会为每种输出模式增加一个通过/失败的判定，该判定针对最终成功的请求进行评估。

- **丰富模式** —— 瀑布图后会打印一个带边框的面板。通过时边框为绿色，失败时为红色，且每个违规项都会以毫秒列出实际值、阈值和超出量。
- **紧凑模式** —— 行为与上述丰富模式相同；SLO 面板仍会在单行步骤摘要之后打印。
- **仅指标** —— 最终成功步骤的那一行会新增 `slo=pass` 或 `slo=fail slo_violations=<keys>` 标记。中间的重定向步骤保持不变。
- **JSON** —— `summary.slo` 包含 `pass`、`thresholds_ms` 以及 `violations[]`（每项带有 `key`、`threshold_ms`、`actual_ms`、`delta_ms`）。未提供 `--slo` 时不存在此块。

发生违规会使 `httptap` 以代码 `4` 退出，同时仍渲染完整输出，从而为事后复盘保留证据。

有关规范语法、评估规则、退出码优先级以及 CI / cron 实用示例，请参见专门的 [SLO 阈值校验](slo.md) 页面。

---

## 接下来做什么？

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } **[高级功能](advanced.md)**

    ---

    自定义组件、监控、批量分析

-   :material-api:{ .lg .middle } **[API 参考](../api/overview.md)**

    ---

    编程用法与扩展

</div>
