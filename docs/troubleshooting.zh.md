---
title: 故障排查与常见问题
description: 运行 httptap 时的常见问题、错误信息与诊断。
---

# 故障排查与常见问题

本页汇集了用户在运行 `httptap` 时最常遇到的问题和错误。如果你的问题未在此列出，请
[提交 issue](https://github.com/ozeranskii/httptap/issues)，并附上确切的
命令、JSON 导出（如有）以及相关的终端输出。

## TLS 与证书

### `TLS handshake failed: CERTIFICATE_VERIFY_FAILED`

服务器出示了一个你的信任库无法识别的证书。

- **非生产主机上的自签名或过期证书** —— 添加 `--ignore-ssl`
  （禁用校验，仅在可信网络中使用）。
- **内部 CA** —— 将 `--cacert`（别名 `--ca-bundle`）指向你的 PEM 包。
- **系统信任库已过时** —— 在 Linux 上更新 `ca-certificates`，或
  刷新你 Python 环境中的 `certifi`（`uv pip install --upgrade certifi`）。

JSON 导出会显示 `network.tls_verified: false`，且在使用 `--cacert` 时会显示
`network.tls_custom_ca: true`。

### 证书显示 `cert_days_left: null` 或负值

`cert_days_left` 从叶证书的 `notAfter` 字段解析而来。`null`
值表示无法获取/解析该证书——通常是 TLS
在收到证书前就已中止，或使用了 `--ignore-ssl`（禁用校验后，对端证书不会
以已解析字典的形式呈现，因此 `cert_cn`/`cert_days_left` 以及其他 `cert_*` 字段会保持
`null`，而 `tls_version`/`tls_cipher` 仍会报告）。**负**
值表示证书已过期。

### `--ignore-ssl` 仍以 `DH_KEY_TOO_SMALL` / `WRONG_VERSION_NUMBER` 失败

现代 OpenSSL 构建出于安全考虑移除了某些加密算法和 DH 参数。
`--ignore-ssl` 会放宽校验和协议约束，但无法找回
已从二进制文件中移除的加密套件（RC4、3DES、弱 DH）。
变通方案：使用较老的 curl、终止 TLS 的代理，或重新编译 OpenSSL。

## 代理

### `--proxy` 被忽略

显式的 `-x/--proxy` 参数始终优先于环境变量。请检查：

1. 你没有误传空字符串——`--proxy ""` 会**显式
   禁用**基于环境变量的代理并强制直连。
2. 协议方案与目标匹配——`HTTPS_PROXY` 用于 `https://` URL，
   `HTTP_PROXY` 用于 `http://`。
3. 目标主机未被 `NO_PROXY` 匹配。检查 JSON 导出中的 `proxy_source`
   字段；如果它显示 `NO_PROXY`，说明你的主机被排除了。

### `NO_PROXY` 模式参考

- 精确主机：`api.internal.example`
- 域名后缀：`.internal.example`（匹配 `foo.internal.example`）
- 通配符：`*`（排除一切）
- 多个条目：逗号分隔，去除首尾空白

**不**支持 IP/CIDR 匹配——这遵循广泛采用的 curl
行为。

## HTTP/2

### 即使未传 `--no-http2`，服务器仍以 HTTP/1.1 响应

HTTP/2 需要在 TLS 握手期间进行 ALPN 协商。如果：

- 服务器未在 ALPN 中通告 `h2`，**或**
- 目标使用纯 `http://`（不支持 h2c），

httptap 会回退到 HTTP/1.1。请检查 JSON 导出中的
`network.http_version`。

### 如何强制使用 HTTP/1.1？

使用 `--no-http2`（兼容 curl 的别名 `--http1.1`）。这会完全禁用 ALPN h2
协商。

## 计时

### `timing.is_estimated: true` —— 这是什么意思？

httptap 通常从 `httpcore` 的 trace 钩子获取各阶段计时。当这些
钩子不可用时（例如绕过它们的自定义 `RequestExecutor`，
或某些 HTTP/2 连接复用路径），httptap 会回退到用启发式方法拆分
总耗时。这样的分解在方向上仍然
正确，但不如默认路径精确。

### 为什么连续两次运行显示的 `dns_ms` 差异巨大？

系统解析器会缓存条目。第一次请求要支付到你 DNS 服务器的完整 RTT；
后续请求则命中缓存（往往是亚毫秒级）。
若要绕过缓存，请通过 Python API 提供自定义解析器，或刷新
本地缓存（例如 macOS 上的 `sudo dscacheutil -flushcache`，systemd 上的
`resolvectl flush-caches`）。

### `ttfb_ms` 为零或低于 `connect_ms`

在连接复用时（后续重定向步骤的 keep-alive、HTTP/2 流
多路复用），该步骤没有新的 TCP 连接——`connect_ms` 将为
`0` 或非常小。`ttfb_ms` 测量的是该特定请求上直到收到首个响应字节的
时间；跨步骤将其与 `connect_ms` 比较，看起来古怪是意料之中的。

## 输出

### 我的终端没有颜色

httptap 遵循 [`NO_COLOR`](https://no-color.org) 约定和 Rich 的
TTY 检测：

- 若设置了 `NO_COLOR`，请取消设置。
- 将 stdout 管道到文件或另一个进程会禁用颜色；设置
  `FORCE_COLOR=1` 可覆盖。
- `TERM=dumb` 同样会禁用渲染。

### `--metrics-only` 不再显示 `proxy=` 字段

它并没有——该字段始终存在。旧的截图/示例可能早于
该变更。预期格式：

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

`proxy` 的取值来源：`direct`、`none`（命中 NO_PROXY）、`disabled`（`--proxy ""`）、
带 `proxy_from=...` 提示的 `<url>`。

## 脚本化与 CI

### 我应该检查哪些退出码？

参见 README 中的 [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes)
部分。典型的 CI 模式：将 `75`（网络 / TLS，瞬时）视为
可重试，遇到 `64`（用法）、`70`（缺陷）和 `4`（若你提供了
`--slo` 的 SLO 违规）则直接失败。

### 即使请求很慢，我的 `--slo` 预算却从不触发。

请检查三件事：

1. 你设置的键映射到一个真实存在的计时阶段。有效的键是
   `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total`——其他任何
   值都会以退出码 `64`（SLO Error 面板）拒绝该命令。
2. SLO 是在**最终成功的步骤**上评估的，而非中间的
   重定向。如果 `--follow` 经过了若干跳，而最后一
   步很快，那么整个链的总时间不会被比较。请用 `total`
   对照终端请求的预算，或在需要逐步保证时从
   `--json` 手动聚合。
3. 如果每一步都出错，SLO 会被完全跳过——退出码
   反映的是网络故障（通常是 `75`）。此时 `--metrics-only` 输出中
   不会出现 `slo=` 标记。

### httptap 能输出 Prometheus 指标吗？

开箱即用尚不支持。请使用 `--metrics-only` 并用 `awk`/`jq` 做后处理，或
解析 `--json` 导出。专用的 exporter 已在路线图中——关注
[issue 跟踪器](https://github.com/ozeranskii/httptap/issues) 获取更新。

## Python API

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` 位于 `httptap.constants`，而非顶层命名空间：

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### 我的自定义解析器没有被调用

`HTTPTapAnalyzer` 仅将注入的解析器用于诊断性的 DNS 查询
计时。实际的连接解析仍由 `httpx`/`httpcore` 执行。
若要让真实连接经过你的解析器，还需实现自定义的
`RequestExecutor`。

---

## 仍未解决？

- 使用 `--metrics-only` 运行，并在你的报告中包含完整输出。
- 使用 `--json report.json` 运行并附上该报告（请脱敏认证请求头）。
- 确认版本——`httptap --version`——我们仅支持最新的
  次要版本。
