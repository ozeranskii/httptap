---
title: 安全保障论证
description: httptap 的威胁模型、信任边界、所应用的安全设计原则，以及已应对的实现弱点。
---

# 安全保障论证（Security Assurance Case）

本文档是 httptap 的安全保障论证。它阐述项目**为何**相信其安全属性成立，而不仅仅是这些属性**是什么**。文档结构遵循 OpenSSF Best Practices 银级（silver-level）的 `assurance_case` 准则。

**最近审阅：** 2026-04-13，针对 httptap 0.5.0。

保障论证是一份持续演进的文档；它会在每个大版本发布时、以及威胁态势或功能集发生实质性变化时接受审阅。修订提案以针对本文件的 pull request 形式受理。

## httptap 是什么

httptap 是一个命令行诊断工具。开发者提供单个 URL（并可选地附带请求头、请求体、代理、CA 包等），httptap 便执行一次 HTTP 请求（或一段简短的重定向链），并渲染每个阶段的计时与 TLS 信息。它**不会**：

- 接受来自不受信任对端的网络输入（它不是服务器）；
- 管理用户账户、会话或长期凭证；
- 执行远程代码或求值服务器提供的脚本；
- 在可选的 `--json` 导出之外持久化任何机密或用户数据。

## 安全需求

项目承诺以下可观测的安全属性。每一项都在下文各节中映射到相应的支撑论据。

| # | 需求 | 理由 |
|---|-------------|-----------|
| SR-1 | 对每个 HTTPS 目标默认启用 TLS 证书校验。 | 默认阻止被动和主动的中间人攻击（MITM）。 |
| SR-2 | 明文 HTTP、削弱的 TLS 或自定义 CA 包均需用户显式选择启用。 | 确保不安全的配置始终是有意为之。 |
| SR-3 | 用户提供的凭证（例如 `Authorization` 请求头）仅转发到原始 URL，不会泄露给位于不同主机上的重定向目标。 | 防止通过开放重定向窃取凭证。 |
| SR-4 | 工具不会执行远程主机所提供的内容。 | 服务器无从获得任何代码执行原语。 |
| SR-5 | 发布制品（PyPI wheel/sdist、容器镜像、git 标签和发布提交）均经过签名，且其构建来源可验证。 | 保护用户免受被篡改的分发包侵害。 |
| SR-6 | 所有 CI 工作流令牌均遵循最小权限并按 SHA 固定。 | 缩减构建流水线的攻击面。 |
| SR-7 | 对供应链（依赖、GitHub Actions、Docker 镜像）进行已知漏洞监控。 | 及时修补上游弱点。 |

## 信任边界

```
   ┌─────────────────────┐
   │ CLI user            │   trusted
   │ (argv, stdin, env)  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ httptap process     │   trusted
   │ (Python 3.10+)      │
   └──────────┬──────────┘
              │  TLS/HTTP  ◄─── untrusted: network, proxy, remote host
              ▼
   ┌─────────────────────┐
   │ Remote HTTP server  │   untrusted
   └─────────────────────┘
```

- **用户 → httptap** 是受信任的：假定用户有正当理由发起任何给定请求。输入校验仍会拒绝格式错误的 URL、方法、超时等，以防止操作者的失误。
- **httptap → 网络 → 远程服务器** 是不受信任的。所有跨越此边界的数据都被视为受攻击者控制：响应头、状态码、`Location` 值、TLS 证书、内容体。
- **构建流水线 → PyPI / GitHub Releases** 是一个独立的信任边界，由 GitHub OIDC（无长期密钥）、Sigstore 签名以及按 SHA 固定的 actions 加以保护。

## 威胁模型

以下威胁按适用于诊断型 HTTP 客户端的 STRIDE 类别列出。超出客户端范围的威胁（例如服务器端 DoS）作为非目标被明确排除。

| STRIDE | 威胁 | 缓解措施 |
|--------|--------|------------|
| **Spoofing（伪装）** | 攻击者冒充目标 HTTPS 服务器。 | 默认启用 TLS 证书校验（SR-1）；`--ignore-ssl` 需显式选择启用，并被记载为不安全（SR-2）。 |
| **Spoofing（伪装）** | 恶意的 PyPI 镜像提供被篡改的 wheel。 | PyPI 使用 TLS；发布制品经 Sigstore 签名并带有 SLSA v1.0 来源证明（SR-5）；用户可使用 `gh attestation verify` 进行验证。 |
| **Tampering（篡改）** | GitHub Releases 上被修改的制品。 | 同上——构建来源证明允许独立验证。 |
| **Tampering（篡改）** | CI 流水线因第三方 action 被攻陷而遭投毒。 | 每个 action 都按 SHA 固定（由 Scorecard Pinned-Dependencies 10/10 和 zizmor pedantic 强制执行）；Dependabot 提交 PR 以更新固定项（SR-6、SR-7）。 |
| **Repudiation（抵赖）** | — | 超出范围；httptap 不是多用户系统。 |
| **Information disclosure（信息泄露）** | `-H Authorization` 中的凭证泄露给位于不同主机上的重定向目标。 | 按 httpx 默认行为，重定向链保留按主机限定的请求头；跨源重定向会丢弃敏感请求头（SR-3）。 |
| **Information disclosure（信息泄露）** | `--json` 导出将认证请求头写入磁盘。 | SECURITY.md 和 docs/troubleshooting.md 建议用户在共享导出前对认证请求头进行脱敏。 |
| **Information disclosure（信息泄露）** | 在不安全的代理上发生 MITM。 | 代理 URL 的协议方案会被校验；对敏感目标推荐使用 `socks5h://` / `https://`；代理来源会在输出和 JSON 中报告以供审计。 |
| **Denial of service（拒绝服务）** | 恶意服务器流式发送无界的请求体。 | 通过 `--timeout` 设定每请求超时（默认 20 秒）；传输阶段受同一截止时限约束。 |
| **Denial of service（拒绝服务）** | 恶意服务器流式发送 zip 炸弹或巨大的请求体。 | httptap 除为计时指标统计字节数外，不会解码或持久化请求体，因此内存开销是线性的，并受超时约束。 |
| **Elevation of privilege（权限提升）** | 恶意响应体触发解析器 RCE。 | 请求体从不按内容解析——只读取其长度。不进行任何 HTML、JS 或内嵌脚本的解释（SR-4）。 |
| **Elevation of privilege（权限提升）** | 恶意 CLI 参数在下游调用中触发 shell 注入。 | 参数由 `argparse` 解析（无 shell），并作为 `list[str]` 转发给 `httpx`（无 shell）；请求路径中不存在任何 shell 调用。 |

### 超出范围的威胁

- **在开发者机器上拥有本地代码执行能力的攻击者。** 超出范围——该攻击者已然掌控了进程本身。
- **控制用户终端 / TTY 的攻击者。** 超出范围。
- **针对 TLS 本身的密码分析攻击。** 委托给 OpenSSL；缓解措施继承自系统 Python 构建。
- **后量子威胁。** 由上游跟踪（OpenSSL / Python）；对 httptap 自身而言超出范围。

## 所应用的安全设计原则

映射到 Saltzer & Schroeder（1975）及现代补充原则。

| 原则 | 在 httptap 中的应用 |
|-----------|-----------------------|
| 机制经济性（Economy of mechanism） | 代码库小（约 2 kLoC）、用途单一、无插件加载器、无运行时配置文件。 |
| 失败安全默认（Fail-safe defaults） | 默认启用 TLS 校验、合理的默认超时、优先使用 HTTP/2、默认不跟随重定向。 |
| 完全仲裁（Complete mediation） | 每个出站请求都经由 `HTTPClientRequestExecutor` 路由；不存在次要或遗留代码路径。 |
| 开放设计（Open design） | 整个代码库以 Apache-2.0 许可托管于 GitHub；不依赖隐晦性来保障安全。 |
| 权限分离（Separation of privilege） | 发布流水线与开发环境相分离；PyPI 发布使用由 OIDC 把关的 GitHub Environment。 |
| 最小权限（Least privilege） | 每个 CI 作业都声明显式的最小 `permissions:`；没有任何工作流使用 `write-all`。Token-Permissions 的 Scorecard 检查评分为 10/10。 |
| 最少公共机制（Least common mechanism） | 各次运行之间无共享状态（单请求工具）；无缓存或后台守护进程。 |
| 心理可接受性（Psychological acceptability） | 兼容 curl 的参数别名（`-X`、`-L`、`-k`、`-x`、`-H`）保持心智模型的熟悉感。 |
| 工作因子（Work factor） | 相较于开发者本地的 `curl` 调用，攻击者所能获得的收益基本为零——httptap 暴露的内容不比 curl 更多。 |
| 入侵记录（Compromise recording） | JSON 导出记录了完整的请求/响应元数据以及代理来源，因此事后取证十分直接。 |
| 纵深防御（Defense in depth） | 输入校验 + TLS 校验 + 固定的构建依赖 + SAST + 机密扫描 + Dependabot + 已签名的发布制品。 |

## 所应对的常见实现弱点

源自 [CWE Top 25 (2023)](https://cwe.mitre.org/top25/) 和 [OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/)。未列出的条目要么不适用于 HTTP 客户端，要么由上游处理。

| CWE | 弱点 | 应对措施 |
|-----|----------|----------------|
| CWE-20 | 不当的输入校验 | `argparse` 的枚举/类型强制转换；对 URL/方法/超时/代理进行显式检查。 |
| CWE-22 | 路径遍历（在 `@file` 数据加载器中） | 路径原样取自用户；从不使用服务器提供的路径来打开文件。 |
| CWE-78 | 操作系统命令注入 | 请求路径中不对用户可控数据调用 `subprocess`/`os.system`。 |
| CWE-79 | XSS | 不进行 HTML 渲染；输出为纯文本或经转义的 Rich 渲染标记。 |
| CWE-89 | SQL 注入 | 无数据库。 |
| CWE-94 | 代码注入 | 不使用 `eval`/`exec`；从不解析响应体。 |
| CWE-116 | 不当的输出编码 | Rich 安全地处理终端转义序列；JSON 导出使用带严格转义的 `json.dumps`。 |
| CWE-200 | 敏感信息泄露 | 认证请求头不会被复制到日志输出；SECURITY.md 与文档提醒用户在共享前对 JSON 导出脱敏。 |
| CWE-295 | 不当的证书校验 | 默认启用 TLS 校验；`--ignore-ssl` 仅在显式选择时启用，并有明确记载。 |
| CWE-319 | 明文传输 | 优先使用 HTTPS；纯 HTTP 需显式的 `http://` URL；代理来源会被报告。 |
| CWE-327 | 弱加密 | 委托给标准库 `ssl`；弱算法仅在诊断远程服务器时才浮现。 |
| CWE-330 | 随机性不足 | 除 OpenSSL 为 TLS 提供的 CSPRNG 外不使用任何 RNG。 |
| CWE-352 | CSRF | 不适用——httptap 是客户端，不是服务器。 |
| CWE-400 | 不受控的资源消耗 | 每请求超时；有界的重定向链（最多 10 次）。 |
| CWE-502 | 不安全的反序列化 | 仅使用 `json.loads`；不使用 pickle、yaml.load 或 marshal。 |
| CWE-601 | 开放重定向（凭证泄露） | 按主机限定的请求头处理继承自 httpx 的行为——跨源重定向会丢弃敏感的认证请求头。 |
| CWE-918 | SSRF | httptap 是客户端；它不代表其他系统代理请求。 |

## 供应链保障

支撑发布完整性属性（SR-5）：

- **发布**：通过 GitHub OIDC Trusted Publishing 发布到 PyPI（并以 TestPyPI 作为预生产冒烟测试）——任何地方都没有长期的 PyPI 令牌。PEP 740 证明在 PyPI 上以“Verified publisher”呈现。
- **容器镜像**：多架构（linux/amd64、linux/arm64）镜像使用 Buildx 构建并推送到 GHCR，使用 cosign 无密钥签名，并附带附加到镜像仓库的 SLSA 构建来源证明。
- **Git 签名**：发布提交和带注解的标签使用 [gitsign](https://github.com/sigstore/gitsign)（经 Fulcio 的 x.509 + Rekor 透明日志）以无密钥方式签名，采用发布工作流的 OIDC 身份。
- **签名**：通过 `actions/attest-build-provenance` 和 cosign 进行 Sigstore 无密钥签名。签名密钥是短期的，由 Fulcio 按每次运行签发，并可通过 Rekor 透明日志验证。
- **来源证明**：SLSA v1.0 证明伴随每个 wheel、sdist 和容器镜像摘要。
- **Dockerfile 检查**：`hadolint` 在每个 PR 上运行，失败阈值为警告级别。
- **固定（Pinning）**：每个工作流中的每个 GitHub Action 都按 SHA 固定；由 Scorecard Pinned-Dependencies 和 zizmor pedantic 在每个 PR 上强制执行。
- **依赖跟踪**：在发布期间生成 CycloneDX 和 SPDX 格式的 SBOM，并作为 GitHub Release 资产附上。
- **可利用性披露**：一份 OpenVEX 文档（`httptap-X.Y.Z.openvex.json`）随 SBOM 一同发布，为每个依赖的 CVE 声明 `httptap` 是否实际受影响。真实来源以版本化形式保存在 [`.vex/httptap.openvex.json`](https://github.com/ozeranskii/httptap/blob/main/.vex/httptap.openvex.json)；消费 VEX 的扫描器（Grype、Trivy、Snyk）借助它抑制针对不可达的脆弱代码路径的误报告警。

用户可以独立验证已下载的制品：

```shell
gh attestation verify dist/httptap-X.Y.Z-py3-none-any.whl \
  --repo ozeranskii/httptap
```

## 已知残余风险

以下风险是被记载而非缓解的。它们代表的是显式的权衡取舍，而非疏漏。

- **单一维护者。** Bus factor 为 1（在 GOVERNANCE.md 中跟踪）。连续性计划缓解了运营层面的单点故障，但未缓解代码审查层面的单点故障：单个审查者可以在没有第二双眼睛的情况下合并变更。Pre-commit、CI 门禁和公开的审计轨迹部分弥补了这一点。
- **无运行时沙箱。** httptap 以用户的全部权限运行。这对于开发者诊断工具而言是恰当的，但意味着 `httptap` 自身的缺陷会以用户的权限运行。
- **TLS 信任锚继承自操作系统。** 如果操作系统信任库被攻陷（例如企业 MITM 代理安装了私有 CA），httptap 无法察觉。JSON 导出中的 `network.tls_custom_ca` 和 `proxy_source` 字段会记录是否使用了自定义 CA 包或代理。

## 变更历史

| 日期 | 备注 |
|------|-------|
| 2026-04-12 | httptap 0.4.7 的首个保障论证（银级提交）。 |
| 2026-04-13 | 面向 0.5.0 的开源加固：gitsign 签名的发布提交/标签、TestPyPI 预检、带 SLSA 来源证明的已签名 GHCR 容器镜像、CI 中的 hadolint、man-page 制品。 |

---

## 参考资料

- [SECURITY.md](https://github.com/ozeranskii/httptap/blob/main/SECURITY.md) —— 漏洞报告流程与受支持的版本。
- [GOVERNANCE.md](https://github.com/ozeranskii/httptap/blob/main/GOVERNANCE.md) —— 项目角色、决策与连续性计划。
- [ROADMAP.md](https://github.com/ozeranskii/httptap/blob/main/ROADMAP.md) —— 范围、非目标与弃用策略。
- [故障排查与常见问题](../troubleshooting.md) —— 运维指引。
- [CWE Top 25](https://cwe.mitre.org/top25/) 和
  [OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/)
  —— 实现弱点的参考目录。
