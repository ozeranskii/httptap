---
description: 通过基础请求和常见命令行示例快速上手 httptap。
---

# 快速开始

本指南将带你了解 httptap 的基础用法。

## 基础请求

发起一次简单的 HTTP 请求并显示丰富的瀑布图视图：

```bash
httptap https://httpbin.io
```

这会输出一份详细的计时分解，展示：

- DNS 解析时间
- TCP 连接建立
- TLS 握手（针对 HTTPS）
- 首字节时间 (TTFB)
- 响应体传输时间

## 发起 POST 请求

向 API 发送 JSON 数据：

```bash
httptap --data '{"name": "John Doe", "email": "john@example.com"}' https://httpbin.io/post
```

!!! tip "自动 POST 行为"
    当提供了 `--data` 而未提供 `--method` 时，httptap 会自动切换为 POST（类似 curl）。

!!! tip "兼容 curl 的参数"
    最常见的 curl 参数可原样使用。使用 `-X/--request` 指定 HTTP 方法，`-L/--location` 跟随重定向，`-m/--max-time` 设置超时，`-k/--insecure` 禁用证书校验，`-x` 指定代理，`--http1.1` 强制使用 HTTP/1.1（等价于 `--no-http2`）。并非所有 curl 选项都受支持，因此替换命令时请只使用这些共有参数。

从文件加载数据：

```bash
echo '{"title": "New Post", "content": "Hello World"}' > post-data.json
httptap --data @post-data.json https://httpbin.io/post
```

## 使用其他 HTTP 方法

httptap 支持所有标准 HTTP 方法：

**PUT 请求：**
```bash
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put
```

**PATCH 请求：**
```bash
httptap --method PATCH --data '{"field": "value"}' https://httpbin.io/patch
```

**DELETE 请求：**
```bash
httptap --method DELETE https://httpbin.io/delete
```

**HEAD 请求（仅请求头）：**
```bash
httptap --method HEAD https://httpbin.io/get
```

## 添加自定义请求头

使用 `-H` 参数添加自定义 HTTP 请求头：

```bash
httptap -H "Accept: application/json" https://httpbin.io/json
```

可通过重复该参数添加多个请求头：

```bash
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://httpbin.io/bearer
```

## 跟随重定向

默认情况下，httptap 不会跟随重定向。若要跟随重定向链：

```bash
httptap --follow https://httpbin.io/redirect/3
```

这会展示重定向链中每一步的计时信息。

## 紧凑输出

若希望每一步以人类可读的单行呈现——适合终端日志以及通过 `grep` / `tee` 进行 tail：

```bash
httptap --compact https://httpbin.io/get
```

输出示例：

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

该行以 HTTP 状态开头，因此失败会格外醒目；计时会带 `ms` 后缀，响应大小则以合适的单位（`B`、`KB`、`MB`）渲染。重定向链仍会以完整的 `Redirect Chain Summary` 表格结尾，从而保持请求的整体形态可见。

若需要机器可解析的 `key=value` 输出（无单位，含 IP/地址族/TLS 字段），请使用下文的 `--metrics-only`。

## 仅指标模式

获取无格式的原始指标，非常适合脚本使用：

```bash
httptap --metrics-only https://httpbin.io
```

输出示例：

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

## JSON 导出

将完整的请求数据导出为 JSON 以便后续分析：

```bash
httptap --json output.json https://httpbin.io
```

该 JSON 文件将包含：

- 所有阶段的详细计时
- 网络信息（IP、TLS 版本、证书详情）
- 响应元数据（状态、请求头、响应体大小）
- 完整的重定向链（如果使用了 `--follow`）
- SLO 评估（如果提供了 `--slo`）

## SLO 阈值校验

使用 `--slo` 基于各阶段延迟预算为 CI 任务、cron 探针或 Kubernetes 就绪检查设置门禁：

```bash
httptap --slo total=500,ttfb=200 https://httpbin.io/get
```

当每个预算都通过时退出码为 `0`，当任一阈值被违反时退出码为 `4`。完整的瀑布图仍会被渲染，以便你看清校验*为何*失败。

!!! tip "支持的 SLO 键"
    `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total`——每一个都映射到一个计时阶段。完整规范与实用示例请参见专门的 [SLO 阈值校验](../usage/slo.md) 页面。

## 常见用例

### API 测试

测试一个完整的 REST API 工作流：

```bash
# Create a resource
httptap --data '{"title": "Test Post"}' https://httpbin.io/post

# Update the resource
httptap --method PUT --data '{"title": "Updated Post"}' https://httpbin.io/put

# Partial update
httptap --method PATCH --data '{"published": true}' https://httpbin.io/patch

# Delete the resource
httptap --method DELETE https://httpbin.io/delete
```

### 检查 API 延迟

```bash
httptap --compact https://httpbin.io/status/200
```

### 调试慢速响应

```bash
httptap https://httpbin.io/delay/3
```

瀑布图视图将帮助识别是哪个阶段导致了延迟（DNS、连接、TLS 或服务器处理）。

### 验证 TLS 配置

```bash
httptap https://httpbin.io
```

在输出中查看 TLS 版本、加密套件以及证书到期时间。

### 性能基准测试

建立性能基线并跟踪随时间的变化：

```bash
# Collect 10 samples and calculate statistics
for i in {1..10}; do
  httptap --metrics-only https://httpbin.io/delay/1
done | awk '/total=/ {
  # Extract total value
  for (i = 1; i <= NF; i++) {
    if ($i ~ /^total=/) {
      sub(/^total=/, "", $i)
      sum += $i
      values[++count] = $i
      break
    }
  }
}
END {
  if (count > 0) {
    avg = sum / count
    printf "Average: %.1f ms\n", avg
    printf "Samples: %d\n", count

    # Calculate min/max
    min = values[1]; max = values[1]
    for (i = 1; i <= count; i++) {
      if (values[i] < min) min = values[i]
      if (values[i] > max) max = values[i]
    }
    printf "Min: %.1f ms\n", min
    printf "Max: %.1f ms\n", max
    printf "Range: %.1f ms\n", (max - min)
  }
}'
```

输出示例：
```
Average: 1490.0 ms
Samples: 10
Min: 1445.4 ms
Max: 1532.4 ms
Range: 87.0 ms
```

这有助于识别性能波动并为回归测试建立可靠的基线。

---

## 下一步？

<div class="grid cards" markdown>

-   :material-console:{ .lg .middle } **[基础用法指南](../usage/basic.md)**

    ---

    完整的命令行参考

-   :material-palette:{ .lg .middle } **[输出格式](../usage/output-formats.md)**

    ---

    丰富、紧凑、JSON 以及指标模式

-   :material-api:{ .lg .middle } **[API 参考](../api/overview.md)**

    ---

    使用自定义组件扩展 httptap

</div>
