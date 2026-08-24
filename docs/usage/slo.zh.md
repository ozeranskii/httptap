---
title: SLO 阈值校验
description: 使用 --slo 依据各阶段延迟预算，在 CI、cron 和就绪检查中对请求进行门禁校验。
---

# SLO 阈值校验

`httptap --slo` 会将测量到的计时与各阶段延迟预算进行比对，当任一预算被超出时以非零码退出。这将一次请求变成一个通过/失败的探针，适用于 CI 门禁、基于 cron 的合成监控、就绪检查以及部署后的冒烟测试——无需编写自定义的 shell 解析器。

## 快速示例

```shell
httptap --slo total=500,ttfb=200 https://api.example.com/health
```

- 当 `total_ms ≤ 500` **且** `ttfb_ms ≤ 200` 时以 `0` 退出。
- 当任一预算被超出时以 `4` 退出。
- 无论结果如何，都会继续打印完整的瀑布图和 JSON 导出，因此排查工作绝不会被门禁阻断。

## 规范语法

向 `--slo` 传入一个逗号分隔的 `KEY=MS` 对列表：

```
--slo KEY=MS[,KEY=MS]*
```

- `KEY` 是受支持的计时阶段之一（不区分大小写）。
- `MS` 是一个正的有限毫秒数（整数或浮点数）。
- 键和值周围的空白字符会被容忍。

### 支持的键

| Key       | Meaning                                                        |
|-----------|----------------------------------------------------------------|
| `dns`     | DNS 解析时间                                                    |
| `connect` | TCP 连接建立                                                    |
| `tls`     | TLS 握手（纯 HTTP 时为 `0`）                                     |
| `ttfb`    | 首字节时间（DNS + connect + TLS + 服务器等待）                    |
| `wait`    | 服务器处理时间（`ttfb - (dns + connect + tls)`）                 |
| `xfer`    | 响应体传输时间（`total - ttfb`）                                 |
| `total`   | 端到端请求耗时                                                  |

### 格式错误的规范

`--slo` 会拒绝以下情况并以 `64`（用法错误）退出：

- 空规范（`--slo ""`）。
- 未知键（`--slo foo=500` → `Unknown SLO key 'foo'`）。
- 重复键（`--slo total=500,total=600`）。
- 非数值（`--slo total=fast`）。
- 零、负值或非有限值（`--slo total=0`、`total=nan`、`total=inf`）。
- 缺少 `=`（`--slo total500`）。

具体错误会在 Rich 格式的面板中打印以供交互使用，并在 `--metrics-only` 下以纯文本打印。

## 评估规则

SLO 阈值针对请求链的**最终成功步骤**进行评估：

- 单次请求 → 针对该请求进行校验。
- 重定向链（`--follow`）→ 针对最终响应而非中间的重定向进行校验。其假设是用户关心的是实际为其请求提供服务的那个响应。
- 所有步骤均出错 → 完全跳过 SLO；退出码反映网络故障（见下文）。

当 `actual ≤ threshold` 时阈值通过。相等**不**计为违规。违规项会按其键的字母顺序报告，以获得确定性的输出。

## 退出码

`--slo` 与 `httptap` 的整体退出码优先级相集成：

| Priority | Condition                               | Exit code |
|:--------:|-----------------------------------------|:---------:|
| 1        | 参数无效（`--slo` 规范错误）             | `64`      |
| 2        | 任一步骤上的网络 / TLS 故障              | `75`      |
| 3        | 内部错误                                | `70`      |
| 4        | 最终成功步骤上的 SLO 违规               | `4`       |
| 5        | 成功                                    | `0`       |

网络错误始终优先于 SLO 违规，因此故障的主机不会在 CI 日志中伪装成延迟回归。

## 输出格式

### Rich（默认）

在瀑布图和任何重定向摘要之后，`httptap` 会打印一个总结 SLO 评估的面板：

```
╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms, ttfb≤200ms            │
│ Violations:                                    │
│   • total: 723.4ms > 500ms (+223.4ms)          │
│   • ttfb: 315.2ms > 200ms (+115.2ms)          │
╰────────────────────────────────────────────────╯
```

面板边框和图标与状态匹配：通过时为绿色 `✓`，失败时为红色 `✗`。

### 紧凑

`--compact` 会为每个步骤打印一行人类可读的信息，随后是与默认模式下相同的 Rich SLO 面板：

```
Step 1: 200 GET https://api.example.com | dns=3.3ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=900.0ms | 1.2 KB

╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms                        │
│ Violations:                                    │
│   • total: 900.0ms > 500ms (+400.0ms)          │
╰────────────────────────────────────────────────╯
```

### 仅指标

`--metrics-only` 会将 SLO 标记追加到最终成功步骤的标准 `key=value` 行：

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=900.0 ... slo=fail slo_violations=total,ttfb
```

通过的情况：

```
Step 1: ... proxy=direct slo=pass
```

中间的重定向步骤**不**携带 SLO 标记，从而保持行数不变。

### JSON 导出

`--json PATH` 会用一个 `slo` 对象扩展 `summary` 块：

```json
{
  "summary": {
    "total_time_ms": 900.0,
    "final_status": 200,
    "final_url": "https://api.example.com/health",
    "final_bytes": 128,
    "errors": 0,
    "slo": {
      "pass": false,
      "thresholds_ms": { "total": 500.0, "ttfb": 200.0 },
      "violations": [
        {
          "key": "total",
          "threshold_ms": 500.0,
          "actual_ms": 900.0,
          "delta_ms": 400.0
        }
      ]
    }
  }
}
```

每个违规项都携带键、用户提供的阈值、测量值以及超出量。`delta_ms` 严格为正，可用于按严重程度对违规项进行排序。

当未传入 `--slo` 参数时，`slo` 键将不存在——摘要的结构与现有的消费者保持向后兼容。

## 实用示例

### 基于 cron 的合成监控

```cron
* * * * * httptap --slo total=1000,ttfb=500 https://api.example.com/health \
  || curl -X POST https://alerts.example.com/page/oncall
```

### 部署后的 CI 门禁

```yaml
- name: Smoke-test staging latency
  run: |
    httptap --slo total=2000,tls=300,ttfb=800 \
      https://staging.example.com/
```

该步骤仅在退出码 `4` 或 `64` 时失败。网络错误（退出码 `75`）可以单独处理：

```yaml
- name: Smoke-test staging latency
  id: smoke
  continue-on-error: true
  run: httptap --slo total=2000 https://staging.example.com/
- name: Fail CI only on SLO violation
  if: steps.smoke.outcome == 'failure' && steps.smoke.conclusion != 'success'
  run: |
    if [ "${{ steps.smoke.outputs.exit_code }}" = "4" ]; then
      echo "SLO violation — failing build."
      exit 1
    fi
```

### Kubernetes 就绪探针

```yaml
readinessProbe:
  exec:
    command:
      - httptap
      - --slo
      - total=5000
      - http://localhost:8080/healthz
```

### 回归门槛

```shell
httptap --slo total=500,ttfb=200 --json regression.json https://prod.example.com/
jq '.summary.slo.violations' regression.json
```

### 多主机金丝雀

```shell
for host in prod-eu prod-us prod-ap; do
  httptap --slo total=1500 "https://${host}.example.com/health" || echo "${host}: SLO miss"
done
```

## 提示

- 先从 `--slo total=<P95 latency>` 开始，待你从 `--json` 导出获得基线数据后，再添加各阶段的预算。
- `xfer` 和 `wait` 是派生指标；它们的总和以 `total` 为上界。如果你设置了 `total` 预算，各个阶段就被隐式地设了上限。
- 与 `--timeout` 结合使用：`--slo` 在请求完成*之后*校验延迟；`--timeout` 会硬性终止一个挂起的请求。你通常两者都需要。
- SLO 输出与 [`httpstat` 的 `--slo`](https://github.com/reorx/httpstat#slo-thresholds) 格式一致（`slo=pass` / `slo=fail` 标记，退出码 `4`），因此脚本可以互换使用。
