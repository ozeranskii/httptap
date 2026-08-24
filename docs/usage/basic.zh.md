---
description: 从命令行运行 httptap，并读取任意 HTTP 请求的各阶段计时明细。
---

# 基础用法

## 命令行界面

`httptap` 命令行界面提供了多种选项，用于自定义你的 HTTP 请求和输出。

## 语法

```bash
httptap [OPTIONS] URL
```

## 选项

> **兼容 curl：** 常见的 curl 参数可作为别名接受。将 `curl` 替换为 `httptap`，并继续使用你熟悉的选项，如 `-X/--request`、`-L/--location`、`-m/--max-time`、`-k/--insecure`、`-x` 以及 `--http1.1`。这并非完整的 curl 克隆——请只使用此处列出的共有参数。

### 请求选项

#### `-X, --request, --method METHOD`

指定要使用的 HTTP 方法。支持的方法：GET、POST、PUT、PATCH、DELETE、HEAD、OPTIONS。

*兼容 curl 的别名：* `-X`、`--request`。

```bash
httptap --method POST https://httpbin.io/post
```

**默认行为：**
- 未提供 `--data`：默认为 GET
- 提供了 `--data` 但没有 `--method`：自动切换为 POST（类似 curl）
- 显式指定 `--method`：遵循所指定的方法

#### `-d, --data DATA`

发送请求体数据。可以是内联字符串，也可以使用 `@filename` 语法引用文件。

**内联 JSON 数据：**
```bash
httptap --data '{"name": "John", "email": "john@example.com"}' https://httpbin.io/post
```

**从文件加载：**
```bash
httptap --data @payload.json https://httpbin.io/post
```

**自动检测：**
- 自动检测 Content-Type（JSON、XML、纯文本）
- 首先检查文件扩展名（.json、.xml、.txt）
- 回退到 JSON 校验

**不同方法的示例：**
```bash
# POST（存在 --data 时自动检测）
httptap --data '{"key": "value"}' https://httpbin.io/post

# PUT
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put

# PATCH
httptap --method PATCH --data '{"field": "modified"}' https://httpbin.io/patch

# 带请求体的显式 GET（不常见，会触发警告）
httptap --method GET --data 'query-data' https://httpbin.io/get
```

#### `-H, --header`

为请求添加自定义 HTTP 请求头。可多次使用。

```bash
httptap -H "Accept: application/json" https://httpbin.io
```

```bash
httptap \
  -H "User-Agent: MyApp/1.0" \
  -H "Authorization: Bearer token123" \
  https://httpbin.io/bearer
```

#### `-L, --location, --follow`

跟随 HTTP 重定向，并显示链中每一步的计时（最多 10 次重定向）。

*兼容 curl 的别名：* `-L`、`--location`。

```bash
httptap --follow https://httpbin.io/redirect/3
```

默认情况下，httptap 不会跟随重定向，会在第一个重定向响应（3xx 状态码）处停止。

#### `-m, --max-time, --timeout SECONDS`

如果总耗时超过指定的秒数，则中止请求链。

*兼容 curl 的别名：* `-m`、`--max-time`。

```bash
httptap --timeout 10 https://httpbin.io/delay/2
```

默认超时为 20 秒。

#### `--no-http2` / `--http1.1`

禁用 HTTP/2 协商并强制使用 HTTP/1.1 连接。

```bash
httptap --no-http2 https://httpbin.io
```

默认情况下，如果服务器支持则启用 HTTP/2。

*兼容 curl 的别名：* `--http1.1`。

#### `-k, --insecure, --ignore-ssl`

禁用 TLS 证书校验。适用于调试自签名主机或已过期的证书。

```bash
httptap --ignore-ssl https://self-signed.badssl.com
```

!!! warning
    请仅在可信网络中使用此选项。它会禁用证书校验并放宽握手约束。

*兼容 curl 的别名：* `-k`、`--insecure`。

#### `-x, --proxy URL`

通过指定的代理转发请求。支持 HTTP、HTTPS、SOCKS5 和 SOCKS5H 协议。

*兼容 curl 的别名：* `-x`。

```bash
# HTTP 代理
httptap --proxy http://proxy.local:8080 https://httpbin.io/get

# SOCKS5 代理（由代理解析 DNS）
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get

# SOCKS5 代理（本地解析 DNS）
httptap --proxy socks5://proxy.local:1080 https://httpbin.io/get

# 忽略代理环境变量并直连
httptap --proxy "" https://httpbin.io/get
```

`--proxy` 参数优先于环境变量（`HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`）。使用 `--proxy ""` 可忽略所有代理环境变量并直连。有关代理协议、DNS 解析和环境变量配置的详细信息，请参见 [高级功能](advanced.md#using-proxies)。

#### `--cacert, --ca-bundle PATH`

使用自定义 CA 证书包（PEM 格式）进行 TLS 校验。适用于由私有 CA 签名的内部端点。

```bash
httptap --cacert ~/certs/company-ca.pem https://internal-api.example.com/health
```

与 `--ignore-ssl` 互斥。

### 输出选项

#### `--compact`

以紧凑的单行格式显示结果，适合日志记录。

```bash
httptap --compact https://httpbin.io/get
```

输出：

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

`--compact` 为每一步打印一行人类可读的信息（适合日志和重定向链追踪），同时仍会渲染分析头部和 `Redirect Chain Summary` 表格。响应大小会以适当的单位（`B`、`KB`、`MB`）显示。若需机器可解析的输出，请参见 `--metrics-only`。

#### `--metrics-only`

输出未经格式化的原始指标，非常适合脚本化和自动化。

```bash
httptap --metrics-only https://httpbin.io
```

输出：

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

#### `--json PATH`

将完整的请求数据导出到 JSON 文件。

```bash
httptap --json report.json https://httpbin.io
```

该 JSON 文件包含：

- 所有阶段的计时明细
- 网络信息（IP 地址、TLS 详情、证书信息）
- 响应元数据（状态、请求头、响应体大小）
- 完整的重定向链（使用 `--follow` 时）
- SLO 评估（提供 `--slo` 时）

#### `--slo KEY=MS[,KEY=MS...]`

根据各阶段的延迟预算校验最终成功的步骤。发生违规时 `httptap` 仍会渲染完整报告，但会以代码 `4` 退出，以便该结果可作为 CI 任务、cron 探针或 Kubernetes 就绪检查的门禁。

```bash
httptap --slo total=500,ttfb=200 https://httpbin.io/get
```

支持的键：`dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total`。有关完整规范、退出码优先级以及 CI/cron 实用示例，请参见专门的 [SLO 阈值校验](slo.md) 页面。

#### `--version`

显示 httptap 版本并退出。

```bash
httptap --version
```

## HTTP 方法

httptap 支持所有标准 HTTP 方法：

- **GET** —— 获取资源（未提供 `--data` 时的默认方法）
- **POST** —— 创建/提交资源（提供 `--data` 时自动选用）
- **PUT** —— 替换资源
- **PATCH** —— 部分更新资源
- **DELETE** —— 删除资源
- **HEAD** —— 仅获取请求头
- **OPTIONS** —— 查询允许的方法

### 方法选择逻辑

1. **显式方法：** `--method` 始终优先
2. **自动 POST：** 存在 `--data` 而没有 `--method` 时，默认为 POST
3. **默认 GET：** 未提供 `--data` 或 `--method` 时，使用 GET

### 按使用场景分类的示例

**API 测试：**
```bash
# 创建资源
httptap --data '{"title": "New Post"}' https://httpbin.io/post

# 更新资源
httptap --method PUT --data '{"title": "Updated"}' https://httpbin.io/put

# 部分更新
httptap --method PATCH --data '{"status": "published"}' https://httpbin.io/patch

# 删除资源
httptap --method DELETE https://httpbin.io/delete
```

**健康检查：**
```bash
# 快速检查（仅请求头）
httptap --method HEAD https://httpbin.io/status/200

# 完整响应
httptap https://httpbin.io/status/200
```

## 请求流程

每次 httptap 请求都会经历以下阶段：

1. **DNS 解析** —— 域名查找
2. **TCP 连接** —— 建立 TCP 连接
3. **TLS 握手** —— 协商安全连接（仅 HTTPS）
4. **服务器等待** —— 从请求发出到收到第一个响应字节之间的时间
5. **响应体传输** —— 下载响应体

## 理解输出

### 丰富模式（默认）

默认的丰富输出会显示一个瀑布图表格，包含：

- 阶段名称和持续时间
- 可视化进度条
- 网络详情（IP、TLS 版本、证书信息）
- 响应元数据（状态、大小、content-type）

### 计时明细

- **DNS (ms)** —— 将域名解析为 IP 地址的时间
- **Connect (ms)** —— 建立 TCP 连接的时间
- **TLS (ms)** —— TLS 握手的时间（仅 HTTPS）
- **TTFB (ms)** —— 首字节时间（包含服务器处理）
- **Transfer (ms)** —— 下载响应体的时间
- **Total (ms)** —— 端到端的请求耗时

### 网络信息

- **IP 地址** —— 解析出的 IP 地址及其地址族（IPv4/IPv6）
- **TLS 版本** —— 协议版本（TLS 1.2、TLS 1.3）
- **加密套件** —— 协商出的加密套件
- **证书 CN** —— 服务器证书中的通用名称（Common Name）
- **证书到期** —— 证书到期前的剩余天数

## 示例

### 基础健康检查

```bash
httptap https://httpbin.io/status/200
```

### 带认证的 API 请求

```bash
httptap \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Accept: application/json" \
  https://httpbin.io/bearer
```

### 跟随重定向链

```bash
httptap --follow https://httpbin.io/redirect/3
```

### 导出以供分析

```bash
httptap --json analysis.json --follow https://httpbin.io/redirect/2
```

### 记录到文件

```bash
httptap --metrics-only https://httpbin.io/delay/1 >> api-latency.log
```

---

## 接下来做什么？

<div class="grid cards" markdown>

-   :material-palette:{ .lg .middle } **[输出格式](output-formats.md)**

    ---

    丰富、紧凑、JSON 和指标模式

-   :material-cog:{ .lg .middle } **[高级功能](advanced.md)**

    ---

    自定义组件与编程用法

-   :material-api:{ .lg .middle } **[API 参考](../api/overview.md)**

    ---

    使用协议扩展 httptap

</div>
