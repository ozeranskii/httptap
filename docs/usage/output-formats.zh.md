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
- **响应元数据**，显示状态、响应体大小、`Server` 头和重定向目标

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
- **转义值**：必要时使用百分号编码，确保每个指标始终是单个 `key=value` 词元。

### 何时使用

- 脚本化和自动化
- 用于分析的数据采集
- 与监控工具集成
- 使用 awk/grep/sed 解析

### 与 `--compact` 同时使用

`--metrics-only` 优先于 `--compact`。同时传入两个参数时，仍会输出机器可读的
`key=value` 行（现有脚本不受影响），并在 stderr 上打印一条警告，提示 `--compact` 已被忽略。

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

将路径设为 `-` 即可把 JSON 写入 stdout（常规报告会被抑制）；状态消息会输出到 stderr：

```bash
httptap --json - https://httpbin.io | jq '.steps[0].timing'
```

### JSON 结构

```json
{
  "schema_version": 1,
  "httptap_version": "0.6.3",
  "timestamp": "2026-09-18T08:00:00Z",
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
        "cert_days_left": 41,
        "cert_sans": ["httpbin.io", "*.httpbin.io"],
        "cert_issuer": "WE1",
        "cert_serial": "05BB0F0AA84C8FECE0E72D805BA7A5D2B",
        "cert_not_before": "2026-08-01T00:00:00+00:00",
        "cert_not_after": "2026-10-30T00:00:00+00:00",
        "tls_verified": true,
        "tls_custom_ca": false,
        "proxy_url": null,
        "proxy_source": null
      },
      "response": {
        "status": 200,
        "bytes": 389,
        "content_type": "application/json",
        "server": "gunicorn/19.9.0",
        "date": "2026-09-18T07:59:59+00:00",
        "location": null,
        "headers": {
          "date": "Fri, 18 Sep 2026 07:59:59 GMT",
          "content-type": "application/json",
          "server": "gunicorn/19.9.0"
        }
      },
      "error": null,
      "note": null,
      "redirect_limit_reached": false,
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

### 字段参考

顶层元数据标识了报告格式及其生成时间。消费方应根据 `schema_version` 选择兼容的解析逻辑。

| Field             | Type    | Description                                                     |
| ----------------- | ------- | --------------------------------------------------------------- |
| `schema_version`  | integer | JSON 报告格式的版本。当前版本为 `1`。                           |
| `httptap_version` | string  | 生成该报告的 httptap 版本。                                     |
| `timestamp`       | string  | 导出的创建时间，采用 RFC 3339 UTC 格式，例如 `2026-09-18T08:00:00Z`。 |
| `initial_url`     | string  | 重定向前传给 httptap 的 URL。                                   |
| `total_steps`     | integer | `steps` 中的条目数。                                            |
| `steps`           | array   | 每个请求的测量数据，包括每一次被跟随的重定向。                  |
| `summary`         | object  | 本次导出的汇总值。                                              |

以 `_ms` 结尾的计时值单位为毫秒。请求和响应体大小的单位为字节。响应大小（`bytes`、`final_bytes`）统计的是线路上实际接收到的响应体，即 `Content-Encoding` 解码之前的大小，与 curl 的 `size_download` 一致。证书和响应中的日期在可用时为 ISO 8601/RFC 3339 时间戳。嵌套的 `steps` 和 `summary` 结构请参见上面的示例。

凭证会被遮蔽：步骤的 `url`、`response.location`、`Location` 和 `Content-Location` 响应头以及 `network.proxy_url` 中 userinfo 部分的密码（或单独的令牌）会被替换为 `****`，`Authorization`、`Set-Cookie` 等敏感请求头也会被遮蔽。

使用了 `--cacert` 时 `network.tls_custom_ca` 为 `true`，否则为 `false`。当 `--follow` 在某个步骤上因达到 10 次重定向上限而停止时，该步骤的`redirect_limit_reached` 为 `true`；这样的步骤也会计入 `summary.errors`。

带有 `error` 的步骤会保留失败前已收到的响应：如果状态行和响应头在失败前已经到达（例如响应体在 `-m/--max-time` 之后停滞），则会填充 `response.status`、`response.headers` 和 `response.bytes`（此前已收到的响应体字节数）。在状态行之前就失败的步骤，其 `response.status` 为 `null`。退出码仍然是网络错误码（`75`）。

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

## HAR 导出 { #har-export }

`--har PATH` 会将分析的请求链写成
[HTTP Archive (HAR) 1.2](http://www.softwareishard.com/blog/har-12-spec/)
文档，这是浏览器 DevTools 和 HAR 查看器可以读取的格式。将路径设为 `-` 可写入
stdout（常规报告会被抑制）；状态消息输出到 stderr：

```bash
httptap --follow --har run.har https://httpbin.io/redirect/2
httptap --har - https://httpbin.io/get | jq '.log.entries[].timings'
```

`--har` 和 `--json` 可以同时使用，但只能有一个写入 stdout。如果文件无法写入，
httptap 会像 `--json` 一样以代码 `73` 退出。

要在 Chrome DevTools 中打开该文件，请打开 **Network** 面板并使用 **Import HAR file**
（工具栏中的上传箭头），或将文件拖到面板上。Firefox DevTools 在 Network 面板的设置菜单中提供
**Import HAR**。

### HAR 结构

单个 HTTPS 请求的示例（已截取）：

```json
{
  "log": {
    "version": "1.2",
    "creator": { "name": "httptap", "version": "0.7.0" },
    "pages": [
      {
        "startedDateTime": "2026-10-06T08:00:00.000+00:00",
        "id": "page_1",
        "title": "https://httpbin.io/get",
        "pageTimings": { "onContentLoad": -1, "onLoad": -1 }
      }
    ],
    "entries": [
      {
        "pageref": "page_1",
        "startedDateTime": "2026-10-06T08:00:00.000+00:00",
        "time": 448.2,
        "request": {
          "method": "GET",
          "url": "https://httpbin.io/get",
          "httpVersion": "HTTP/2.0",
          "cookies": [],
          "headers": [],
          "queryString": [],
          "headersSize": -1,
          "bodySize": 0
        },
        "response": {
          "status": 200,
          "statusText": "OK",
          "httpVersion": "HTTP/2.0",
          "cookies": [],
          "headers": [{ "name": "content-type", "value": "application/json; charset=utf-8" }],
          "content": { "size": 389, "mimeType": "application/json; charset=utf-8" },
          "redirectURL": "",
          "headersSize": -1,
          "bodySize": 389,
          "_transferSize": 389
        },
        "cache": {},
        "timings": {
          "blocked": -1,
          "dns": 8.9,
          "connect": 291.6,
          "send": 0,
          "wait": 146.4,
          "receive": 1.3,
          "ssl": 194.6
        },
        "serverIPAddress": "44.211.11.205",
        "_tls": {
          "version": "TLSv1.2",
          "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
          "certCN": "httpbin.io",
          "certIssuer": "Amazon RSA 2048 M03",
          "certDaysLeft": 200,
          "verified": true
        }
      }
    ]
  }
}
```

文档包含：

- 本次运行的**一个页面**。其 `title` 是传给 httptap 的 URL；页面加载计时不适用，值为 `-1`。
- 按重定向链顺序，**每个请求一个条目**，每个条目通过 `pageref` 指向该页面。httptap
  测量的是持续时间而不是实际开始时间，因此条目首尾相接排列，最后一个条目在写入文件时结束。
- **请求**：方法、URL、协商的 HTTP 版本、httptap 收到的请求头（`-H` 以及由 `--data`
  推导出的 `Content-Type`）、解析后的查询字符串和 `bodySize`。请求体本身永远不会被写入。
- **响应**：状态码、HTTP 版本、响应头、`redirectURL`（`Location` 响应头）、`content.mimeType`
  （`Content-Type`，缺失时为 `x-unknown`）以及响应体大小。httptap 不解码响应体，因此
  `content.size` 和 `bodySize` 是在 `Content-Encoding` 解码之前、在网络上接收到的大小。
  响应体文本永远不会被包含。
- **`serverIPAddress`**：httptap 连接的地址。

`statusText` 为该状态码的标准原因短语（未知状态码时为空），`headersSize` 为 `-1`：httptap 不记录线上实际发送的原因短语和头部大小。`cookies` 数组为空；
`Cookie` 和 `Set-Cookie` 以掩码形式出现在头部中。

### 计时

| HAR 字段   | httptap 值             | 说明                                               |
| ---------- | ---------------------- | -------------------------------------------------- |
| `blocked`  | `-1`                   | 不测量。                                           |
| `dns`      | `dns_ms`               |                                                    |
| `connect`  | `connect_ms + tls_ms`  | 按照 HAR 规范的要求，包含 TLS 握手。               |
| `ssl`      | `tls_ms`               | 仅限 HTTPS，明文 HTTP 为 `-1`。已包含在 `connect` 中。 |
| `send`     | `0`                    | 不单独测量；发送请求的时间包含在 `wait` 中。       |
| `wait`     | `wait_ms`              | 服务器处理时间，直到收到响应的第一个字节。         |
| `receive`  | `xfer_ms`              | 响应体传输时间。                                   |

`time` 是 `blocked`、`dns`、`connect`、`send`、`wait` 和 `receive` 中非 `-1` 值的总和。
`ssl` 不会再次累加，因为 `connect` 已经包含它。数值单位为毫秒，四舍五入到小数点后三位。
当连接和 TLS 阶段是估算而非实测时（JSON 导出中的 `is_estimated`），`timings` 会带有
`"_estimated": true`。

### 失败的请求

失败的步骤仍会被导出。其 `response.status` 为 `0`，或者是失败前已经收到的状态码（例如响应体停滞超过
`-m/--max-time` 时），错误消息位于 `response._error` 中，Chrome DevTools 在导入 HAR 时会从这里读取。
由于失败的步骤没有已测量的阶段，其 `dns`、`connect` 和 `ssl` 为 `-1`，`send`、`wait` 和
`receive` 为 `0`，`time` 为 `0`。

### 自定义字段

HAR 规范将以 `_` 开头的字段保留给扩展使用。httptap 添加了：

| 字段                     | 位置       | 内容                                                                       |
| ------------------------ | ---------- | -------------------------------------------------------------------------- |
| `_tls`                   | 条目       | `version`、`cipher`、`certCN`、`certIssuer`、`certDaysLeft`、`verified`；仅限 HTTPS。 |
| `_proxy`                 | 条目       | 请求所经过代理的 `url`（凭据已掩码）和 `source`。                          |
| `_redirectLimitReached`  | 条目       | 当 `--follow` 在此步骤达到 10 次重定向上限而停止时为 `true`。              |
| `_estimated`             | `timings`  | 连接和 TLS 计时为估算值时为 `true`。                                       |
| `_transferSize`          | `response` | 在网络上接收到的响应体字节数，未收到响应时为 `-1`。                        |
| `_error`、`_errorKind`   | `response` | 失败步骤的错误消息及其类型（`network` 或 `internal`）。                    |

### 凭据脱敏

HAR 导出采用与 JSON 导出相同的掩码处理：URL userinfo 中的密码（或单独的令牌）在请求 URL、页面标题、
`redirectURL`、`Location` 和 `Content-Location` 头以及代理 URL 中会被替换为 `****`，`Authorization`、
`Cookie` 和 `Set-Cookie` 等敏感头也会被掩码。

!!! warning
    路径和查询字符串会被保留，而且 HAR 文件经常被附加到缺陷报告中。分享 HAR 文件之前，
    请检查其中是否包含敏感数据。

## Prometheus Textfile 导出 { #prometheus-textfile-export }

使用 `--prometheus PATH` 写出 node_exporter textfile collector 报告：

```bash
httptap --prometheus /var/lib/node_exporter/httptap.prom https://api.example.com/health
```

该文件以原子方式写入。每个样本都带有 `host` 标签（仅主机名）以及重定向链中的 `step`，因此多个探针可以共享同一个 textfile 目录。导出的 gauge：

| Metric                                  | Extra labels | Meaning                                         |
| --------------------------------------- | ------------ | ----------------------------------------------- |
| `httptap_request_success`               |              | 步骤完成时为 `1`，发生网络/TLS 错误时为 `0`     |
| `httptap_request_duration_seconds`      | `phase`      | `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total` |
| `httptap_response_status_code`          |              | 该步骤的 HTTP 状态码                            |
| `httptap_response_body_size_bytes`      |              | 线路上的响应体大小                              |
| `httptap_last_run_timestamp_seconds`    |              | 写入该文件时的 Unix 时间（仅带 `host`）         |

失败的步骤只会导出 `httptap_request_success 0`，因此故障绝不会看起来像是一次快速响应。路径和查询字符串绝不会被用作标签。

## OpenTelemetry 导出

`--otlp ENDPOINT` 会发送 OTLP/HTTP trace。请先安装可选的 extra：

```bash
pip install 'httptap[otel]'
httptap --otlp http://localhost:4318/v1/traces https://api.example.com/health
```

一次运行会导出为一条 trace：一个 `httptap.analysis` 根 span，其下每个重定向步骤一个 `http.request` span（按先后顺序依次排列），以及表示 DNS、连接、TLS、服务器等待和传输阶段的子 span。投递耗时受 `-m`/`--max-time` 限制；collector 错误会以警告形式报告，不会改变退出码。导出时会省略完整的请求 URL，因此查询参数不会被发送到 collector。

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
