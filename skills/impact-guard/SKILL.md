---
name: impact-guard
description: >
  变更影响分析（blast radius）。给定变更点，沿图谱计算受影响范围，按「直接/间接」+ GTSP
  业务边界（HTTP/MQ/DB/缓存/定时 5 通道）分级。当用户提到：变更影响、影响范围、影响分析、
  改这个会影响谁、波及范围、blast radius、变更前评估、impact 分析、回归范围、改动的风险、
  这次改动会影响什么时激活。提供两类能力：(1) 提交前/改码前的影响预估，(2) PR/CI 的关键
  路径门禁（只拦直接高风险）。
---

# 变更影响分析 (impact-guard)

> **状态**：✅ v1 + v2 已实现（v2：方法级 diff + 跨服务契约传播，56 测试 / 覆盖率 94%）。技术设计见 [`DESIGN.md`](DESIGN.md)、完整论证见[评审稿](../../docs/design/impact-guard-design.md)。

## 定位

回答 **"改这个，会波及谁？"**。与现有技能分工（底层共享、提问不同）：

| 技能 | 问题 | 时态 |
|---|---|---|
| arch-guard | 这代码违规了吗？ | 静态现状 |
| doc-gen | 架构长什么样？ | 项目快照 |
| **impact-guard** | **这次改动会影响谁？** | **变更增量** |

底层复用 arch-guard `JavaScanner` / `LayerIdentifier`，Tier 2 复用 `codebase-memory-mcp` 图谱。

## 架构：Tier 2 主 + Tier 1 fallback

| 层级 | 工具 | 精度 | 何时用 |
|---|---|---|---|
| **Tier 2（主）** | `codebase-memory-mcp` `query_graph` Cypher | 方法级 | 默认路径 |
| **Tier 1（fallback）** | `impact_check.py`（import 反向索引） | 文件/类级 | 仅项目未 index 时降级，头部告警 `[Tier 1 only]` |

## 工作流

### 决策树

1. 目标项目是否已 index？（`list_projects`）
   - **是** → Tier 2，查影响方向（下一步）
   - **否** → 触发 reindex 或降级 Tier 1（精度告警）
2. 变更点是什么组件？→ 决定产出形态（见下"影响方向"）
3. 变更点是否命中 🔴 直接边界？→ 决定门禁

### 接入（新项目）

```bash
# 1. 扫描注解动态生成配置（5 通道边界 + highways，不写死 glob）
python3 scripts/impact_check.py . --init

# 2. 分析本次变更影响（默认 origin/master...HEAD；过期图谱自动 reindex）
python3 scripts/impact_check.py . --diff origin/master...HEAD --strict

# 3. 指定变更点（不依赖 git）
python3 scripts/impact_check.py . --changed com.example.order.app.OrderCreateExecutor
```

> 完整参数由脚本实时输出，不在此静态复制：`python3 scripts/impact_check.py --help`

### 影响方向（关键，诚实区分）

| 变更点类型 | 产出 |
|---|---|
| 普通类（Service/Assembler/Executor） | `impact`：谁调用了我（inbound 证据链） |
| 框架入口（Controller/MQ Listener/JobHandler/Callback 实现） | `无法分析影响` + `regression_scope`（下游树，**回归建议**）——不伪装成影响分析 |

入口组件被 Spring/MQ 驱动，图内无入边，inbound 不可见符合预期。

### 关键路径分级（直接/间接）

| 级别 | 触发 | 门禁 |
|---|---|---|
| 🔴 **直接** | 变更点本身是出站/落点：Feign 出站 / Mapper / Redis 写 / MQ Producer / `-client` 对外 API | `--strict` 阻断 |
| 🟠 **间接抵达** | 普通类变更，影响链 ≥1 跳抵达边界 | 告警 + 回归建议，不阻断 |
| 🟡 Warning | 穿越跨服务边界（本服务内）/ 触及聚合根 | 不阻断 |
| 🟢 Info | 仅内部实现 | 不阻断 |

**5 通道边界**（HTTP/MQ/DB/缓存/定时）由 `--init` 扫描注解 + SDK 调用生成，glob 仅手动覆盖。完整矩阵见 [`DESIGN.md` §2.4](DESIGN.md)。

### 不沉默原则

碰到以下情况**强制告警**，绝不假装权威：
- **跨服务契约**：变更触及 `@FeignClient`/`-client` → 🔴 直接 + `⚠️ 跨服务影响未分析，需人工评估下游服务`
- **过期图谱**：`head_sha` 与 HEAD 不一致 → 自动 reindex（或 `--skip-reindex` 跳过 + 告警）
- **入口组件**：inbound 无法分析 → 明确标注 + 给回归范围

### 报告收据（receipt）

JSON 报告顶层携带 `receipt` 收据信封（规范：[`../../docs/design/guard-receipt-spec.md`](../../docs/design/guard-receipt-spec.md)）——`decision`（gate + 稳定原因码，CI 可程序化匹配）/ `provenance`（diff 范围、扫描量、5 通道命中计数）/ `boundary`（降级与未覆盖声明）。text 报告末尾投影为「── 证据边界 ──」段：**报告主动声明自身精度与盲区，防止被读者当成全面事实**。

### Tier 2 深度审查

```bash
# 动态生成本项目适配的 Cypher 清单（不手抄，避免漂移）
python3 scripts/impact_check.py --mode graph --config .impact-guard.json
```

输出查询粘贴到 `query_graph` 执行，拿方法级证据链。

## 相关文件

- 技术设计：[`DESIGN.md`](DESIGN.md)
- 快速使用：[`README.md`](README.md)
- 完整论证 / 评审稿（含 grill 决策）：[`../../docs/design/impact-guard-design.md`](../../docs/design/impact-guard-design.md)
- 架构规范：[`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)
- 复用来源：[`../arch-guard/scripts/arch_check.py`](../arch-guard/scripts/arch_check.py)
