---
title: 故障排查与常见问题
description: 运行 httptap 时的常见问题、错误信息与诊断。
---

# 故障排查与常见问题

本页汇集了用户在运行 `httptap` 时最常遇到的问题和错误。如果你的问题未在此列出，请[提交 issue](https://github.com/ozeranskii/httptap/issues)，并附上确切的命令、JSON 导出（如有）以及相关的终端输出。

## TLS 与证书

### `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed`

服务器出示了一个你的信任库无法识别的证书。失败的步骤会报告类似
`Request failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1077)`
的错误；冒号后的原因（自签名、已过期、无法获取本地颁发者证书、主机名不匹配）以及 `_ssl.c` 的行号会有所不同。

- **非生产主机上的自签名或过期证书** —— 添加 `--ignore-ssl`（禁用校验，仅在可信网络中使用）。
- **内部 CA** —— 将 `--cacert`（别名 `--ca-bundle`）指向你的 PEM 包。
- **系统信任库已过时** —— 在 Linux 上更新 `ca-certificates`，或刷新你 Python 环境中的 `certifi`（`uv pip install --upgrade certifi`）。

httptap 仅会在不校验证书的情况下重试一次诊断性 TLS 握手，并在失败步骤中报告所出示证书的 CN、SAN、颁发者、有效期以及到期时间。请求本身仍会校验失败。当启用代理时，会跳过直连的诊断探测，以免 httptap 绕过代理。

### 证书显示 `cert_days_left: null` 或负值

`cert_days_left` 从叶证书的 `notAfter` 字段解析而来。`null` 值表示无法获取/解析该证书——通常是 TLS 在收到证书前就已中止、目标是纯 `http://`，或者请求在 TLS 握手之前就已失败。`--ignore-ssl` 不会导致该值为空：禁用校验时，httptap 会从对端证书的 DER 形式解析证书，因此 `cert_cn`、`cert_days_left` 以及其他 `cert_*` 字段仍会被报告。**负**值表示证书已过期。

### `--ignore-ssl` 仍以 `DH_KEY_TOO_SMALL` / `WRONG_VERSION_NUMBER` 失败

现代 OpenSSL 构建出于安全考虑移除了某些加密算法和 DH 参数。`--ignore-ssl` 会放宽校验和协议约束，但无法找回已从二进制文件中移除的加密套件（RC4、3DES、弱 DH）。变通方案：使用较老的 curl、终止 TLS 的代理，或重新编译 OpenSSL。

## 代理

### `--proxy` 被忽略

显式的 `-x/--proxy` 参数始终优先于环境变量。请检查：

1. 你没有误传空字符串——`--proxy ""` 会**显式禁用**基于环境变量的代理并强制直连。
2. 协议方案与目标匹配——`HTTPS_PROXY` 用于 `https://` URL，`HTTP_PROXY` 用于 `http://`。
3. 目标主机未被 `NO_PROXY` 匹配。检查 JSON 导出中的 `proxy_source` 字段；如果它显示 `NO_PROXY`，说明你的主机被排除了。

### `NO_PROXY` 模式参考

- 主机及其子域名：`api.internal.example`（也匹配 `v1.api.internal.example`）
- 仅子域名：`.internal.example`（匹配 `foo.internal.example`，不匹配 `internal.example`）
- 通配符：`*`（排除一切）
- 多个条目：逗号分隔，去除首尾空白，不区分大小写

IP 地址按普通主机名进行比较。**不**支持 CIDR 范围（curl 自 7.86.0 起支持）和带端口的条目。

## HTTP/2

### 即使未传 `--no-http2`，服务器仍以 HTTP/1.1 响应

HTTP/2 需要在 TLS 握手期间进行 ALPN 协商。如果：

- 服务器未在 ALPN 中通告 `h2`，**或**
- 目标使用纯 `http://`（不支持 h2c），

httptap 会回退到 HTTP/1.1。请检查 JSON 导出中的 `network.http_version`。

### 如何强制使用 HTTP/1.1？

使用 `--no-http2`（兼容 curl 的别名 `--http1.1`）。这会完全禁用 ALPN h2 协商。

## 计时

### `timing.is_estimated: true` —— 这是什么意思？

httptap 通常从 `httpcore` 的 trace 钩子获取各阶段计时。当这些钩子没有为某个请求报告任何连接/TLS 事件时（例如某个不发出 `httpcore` trace 事件的传输层），httptap 会回退到用启发式方法拆分 DNS 与首个响应字节之间的时间（HTTPS 下为 30% 连接、70% TLS）。这样的分解在方向上仍然正确，但不如默认路径精确。

### 为什么连续两次运行显示的 `dns_ms` 差异巨大？

系统解析器会缓存条目。第一次请求要支付到你 DNS 服务器的完整 RTT；后续请求则命中缓存（往往是亚毫秒级）。若要绕过缓存，请通过 Python API 提供自定义解析器，或刷新本地缓存（例如 macOS 上的 `sudo dscacheutil -flushcache`，systemd 上的 `resolvectl flush-caches`）。

### 每个重定向步骤都显示完整的 `connect_ms` 和 `tls_ms`

httptap 会为每个请求（包括每个重定向步骤）打开一个新连接，因此连接从不复用，每个步骤都要各自完成 TCP 连接和 TLS 握手。`ttfb_ms` 从 DNS 解析开始时计起，因此它已经包含了 `dns_ms`、`connect_ms` 和 `tls_ms`；服务器自身的处理时间是 `wait_ms`。如果某个步骤的计时全部为 `0`，说明它在收到响应之前就已失败——请检查其 `error` 字段。

## 输出

### 我的终端没有颜色

httptap 遵循 [`NO_COLOR`](https://no-color.org) 约定和 Rich 的 TTY 检测：

- 若设置了 `NO_COLOR`，请取消设置。
- 将 stdout 管道到文件或另一个进程会禁用颜色；设置 `FORCE_COLOR=1` 可覆盖。
- `TERM=dumb` 同样会禁用渲染。

### `--metrics-only` 不再显示 `proxy=` 字段

它并没有——该字段在每个收到响应的步骤中都存在。旧的截图/示例可能早于该变更。失败的步骤会输出为 `Step N: ERROR - <message>`，不包含指标和 `proxy=` 字段。成功步骤的预期格式：

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

可能的取值：

- `proxy=<url> proxy_from=arg` —— 通过 `-x/--proxy` 设置的代理。
- `proxy=<url> proxy_from=env:<VAR>` —— 取自 `https_proxy` 或 `HTTPS_PROXY` 等环境变量的代理。
- `proxy=none proxy_from=env:no_proxy` —— 主机命中了 `NO_PROXY`。
- `proxy=disabled proxy_from=arg` —— 通过 `--proxy ""` 禁用了代理。
- `proxy=direct proxy_from=no_scheme_match` —— 设置了代理变量，但没有一个适用于该 URL 的协议方案。
- `proxy=direct` —— 未配置代理。

如果某些值会破坏 `key=value` 的分词，则会对其进行百分号编码。

## 脚本化与 CI

### 我应该检查哪些退出码？

参见 README 中的 [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes) 部分。典型的 CI 模式：将 `75`（网络 / TLS，瞬时）视为可重试，遇到 `64`（用法）、`70`（缺陷）、`47`（使用 `--follow` 时达到重定向上限）、`73`（未能写入 `--json` 文件）、`22`（使用 `--fail` 时收到 HTTP 4xx/5xx）和 `4`（若你提供了 `--slo` 的 SLO 违规）则直接失败。当多个条件同时满足时，优先级最高的退出码胜出；参见[优先级表](usage/slo.md#exit-codes)。

### 即使请求很慢，我的 `--slo` 预算却从不触发。

请检查三件事：

1. 你设置的键映射到一个真实存在的计时阶段。有效的键是 `dns`、`connect`、`tls`、`ttfb`、`wait`、`xfer`、`total`——其他任何值都会以退出码 `64`（SLO Error 面板）拒绝该命令。
2. SLO 是在**最终成功的步骤**上评估的，而非中间的重定向。如果 `--follow` 经过了若干跳，而最后一步很快，那么整个链的总时间不会被比较。请用 `total` 对照最后一个请求的预算，或在需要逐步保证时从 `--json` 手动聚合。达到重定向上限时，被评估的步骤是最后一个 `3xx` 响应。
3. 如果每一步都出错，SLO 会被完全跳过——退出码反映的是网络故障（通常是 `75`）。此时 `--metrics-only` 输出中不会出现 `slo=` 标记。

### httptap 能输出 Prometheus 指标吗？

可以。使用 `--prometheus PATH` 写出 node_exporter textfile collector 文件。指标名称和标签参见[输出格式](usage/output-formats.md#prometheus-textfile-export)。

## Python API

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` 位于 `httptap.constants`，而非顶层命名空间：

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### 我的自定义解析器没有被调用

`HTTPTapAnalyzer` 会在直连和本地 DNS 解析的 SOCKS5 代理中使用注入的解析器。HTTP、HTTPS 和 SOCKS5H 代理会在远端解析目标主机；如需改变这一行为，请使用自定义的 `RequestExecutor`。

---

## 仍未解决？

- 使用 `--metrics-only` 运行，并在你的报告中包含完整输出。
- 使用 `--json report.json` 运行并附上该报告（请脱敏认证请求头）。
- 确认版本——`httptap --version`——我们仅支持最新的次要版本。
