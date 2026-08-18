# Guard Receipt 规范 v1 — 审查报告收据信封

> 适用：`arch-guard` / `impact-guard` 的报告输出（JSON + text）。
> 状态：v1 已实现（`arch_check.py` / `renderer.py`）。

## 1. 动机：报告即收据

守护报告的本质是一张**收据（receipt）**：下游读者（CI、Agent、评审人）需要凭它回答三个问题——

1. **结论从哪来？**（provenance：数据源、扫描范围、配置、基线）
2. **门禁为什么触发/放行？**（decision：gate + reason codes，可程序化解析）
3. **这份报告证明了什么、没证明什么？**（boundary：证据边界声明）

第三点最容易被忽略：一份不声明自身盲区的报告，会被读者当成全面事实。典型事故——
Tier 1 类级分析的结果被当作方法级精确结论引用；跨服务影响未分析却没有任何标记。

## 2. 信封结构

JSON 报告顶层增加 `receipt` 块（additive，不破坏现有消费者，`schema_version` 不变）：

```json
{
  "receipt": {
    "tool": "impact-guard | arch-guard",
    "schema_version": 1,
    "decision": {
      "gate": "pass | warn | block",
      "reason_codes": ["direct_boundary_hit", "cross_service_downstream_unanalyzed"]
    },
    "provenance": {
      "tier": 1,
      "...": "工具特定字段：数据源、扫描量、配置、基线"
    },
    "boundary": {
      "degraded": ["tier1_class_level"],
      "not_analyzed": ["cross_service_downstream", "reflection_dynamic_dispatch"]
    }
  }
}
```

| 字段 | 语义 |
|---|---|
| `decision.gate` | `block`=门禁阻断（exit 1）；`warn`=有风险但不阻断；`pass`=通过 |
| `decision.reason_codes` | 触发原因的稳定英文码（CI/IDE 可程序化匹配，对齐 `rule_code` 风格） |
| `provenance` | 数据从哪来：tier、diff 范围、扫描量、config/baseline 文件、抑制计数 |
| `boundary.degraded` | **降级声明**：本次分析精度低于技能上限（如 Tier 1 类级/文件级） |
| `boundary.not_analyzed` | **未覆盖声明**：结构性无法覆盖或需人工判断的范围，永不静默 |

## 3. 三态不变量

**每项声明的检查必须终结于三种可观测状态之一，不得静默消失：**

- `executed` — 已执行（结果进入 findings/issues）
- `skipped` — 按策略跳过（须在 `boundary.not_analyzed` 留痕）
- `rejected` — 因配置/输入非法拒绝（须 fail-closed，退出码 2）

现有实现中条件跳过的场景（impact 跨服务、arch 人工判断项）均通过 `not_analyzed`
留痕；未来新增条件跳过的检查时，**必须**同步登记 `not_analyzed`，否则视为规范违规。

## 4. 两技能字段映射

### impact-guard（`renderer.py build_receipt`）

| 位置 | 字段 |
|---|---|
| decision | `gate`：`--strict` 且 🔴 DIRECT → `block`；有 reason_codes → `warn`；否则 `pass` |
| decision | `reason_codes`：`direct_boundary_hit` / `cross_service_downstream_unanalyzed` / `entry_inbound_unanalyzable` |
| provenance | `diff_range`、`changed_points`、`scanned_classes`、`config_source`、`boundary_channels`（5 通道命中计数） |
| boundary.degraded | Tier 1 模式恒有 `tier1_class_level`（方法级证据需 Tier 2 图谱） |
| boundary.not_analyzed | 恒有 `reflection_dynamic_dispatch`；跨服务时加 `cross_service_downstream` |

### arch-guard（`arch_check.py _build_receipt`）

| 位置 | 字段 |
|---|---|
| decision | `gate`：mandatory_count > 0 → `block`；否则 `pass`；`reason_codes` = 强制问题的 `rule_code` 去重 |
| provenance | `java_files`（含 classified/unclassified）、`pom_files`、`baseline`（路径 + suppressed/retired 计数） |
| boundary.degraded | 恒有 `tier1_file_level_heuristic`；unclassified > 0 时加 `unclassified_java_files` |
| boundary.not_analyzed | `tier2_method_level_dependency` + SKILL.md「仍需人工」四项：`aggregate_design` / `value_object_immutability` / `application_service_business_logic` / `cross_domain_event_decoupling` |

## 5. text 输出的边界声明（人读投影）

JSON 信封的 `boundary` 在 text 报告末尾投影为「── 证据边界 ──」段，
对齐收据规范的可信度机制：**主动声明证据边界，区分验证过的事实与未覆盖的范围**。

## 6. 演进

- reason_codes 命名空间按工具前缀隔离，新增码只需追加（additive）
- `schema_version` 仅在不兼容变更（字段删除/语义变更）时递增
- Tier 2 落地后，`provenance` 增加 `graph_head_sha`（图谱新鲜度入收据）
