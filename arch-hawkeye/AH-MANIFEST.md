# AH-MANIFEST 公共契约 v1

> 架构鹰眼（Arch Hawkeye）与 doc-gen 之间的数据交换契约。
> 状态：**Active** · 契约版本：`schema_version: 1` · 关联需求：[[requirements]] REQ-A

## 1. 契约定位与真相源

**真相源（canonical）**：`skills/doc-gen/schemas/*.schema.json` —— 由生产者（doc-gen）维护，
架构鹰眼作为消费者引用并复用其校验器（`skills/doc-gen/scripts/validator.py`，零第三方依赖）。

契约所有权归生产者、语义冻结由双方共同认可。当出现第二个 manifest 生产者时，契约再抽离为独立包（YAGNI，暂不做）。

```
doc-gen（生产者）                          架构鹰眼（消费者）
schemas/*.schema.json ──── 唯一真相源 ────▶ 引用 + validator 复用
doc-manifest/ 分片目录 ──── 交换物 ────────▶ 联邦索引 → 知识图谱 → 治理
```

## 2. 分片清单

| 分片文件 | 契约 | 必选性 | 内容 |
|---|---|---|---|
| `index.json` | `index.schema.json` | **必选** | 域列表 + 统计 + schema_version 锁定 |
| `meta.json` | `meta.schema.json` | **必选** | 项目元信息 + revision-pinned evidence |
| `domains/{domain}.json` | `domain.schema.json` | **必选** | 每域分层/组件/聚合 |
| `database.json` | `database.schema.json` | **必选** | 表结构 + 关系 |
| `cross-domain.json` | `cross-domain.schema.json` | **必选** | 域间依赖 |
| `state-machines.json` | `state-machines.schema.json` | **必选** | 状态机 + 质量审查 |
| `diagrams.json` | —（Mermaid 自由文本） | 可选 | 仅要求 JSON 可解析 |
| `business-context.json` | `business-context.schema.json` | **可选** | 业务维度扩展块（§5） |
| `api-spec.json` | OpenAPI 3.0 上游规范 | 可选 | REST API |
| `risks.json` / `adrs.json` 等 | 本期范围外 | 可选 | 鹰眼 Phase 1+ 定义 |

**契约要点（跨项目链路，Phase 2 已落地）**：`feignInterface` 组件的 `endpoints` 字段
承载**消费侧调用声明**（`@FeignClient(path)` 类级前缀 + 方法级 mapping 拼接的完整路径），
与 `controller` 组件的 `endpoints`（provider 路由声明）同构——鹰眼据此做签名对齐，
产出 `cross-project.json` 聚合分片（confirmed/inferred 双置信度 + 双侧证据，见 §4.1）。

## 3. 版本规则

- 各分片 `schema_version` 为 **const 锁定**（当前 `1`），`additionalProperties: false` 拒绝未知字段——契约演进不靠宽容，靠显式 bump（archify 式版本锁定）。
- **添加可选字段 / 新增可选分片**（如本次 business-context）：非破坏性，不 bump。
- **删除/重命名字段、收紧约束**：破坏性，`schema_version` bump 2；消费者（鹰眼）须同时接纳新旧版本直至迁移完成（对应需求 AH-A04）。
- 生成端写后自检：doc-gen 每次产出 manifest 即跑 `validate_manifest_dir`，不过契约不出厂（劣质产物拦截在生成侧）。

## 4. 联邦聚合的契约支撑

| 需求 | 契约支撑 | 状态 |
|---|---|---|
| 增量聚合（AH-A03） | `meta.json` → `evidence.revision`（40 位 SHA）即项目指纹；聚合方缓存「项目 → revision」，revision 未变则跳过重算 | ✅ 现有字段够用 |
| 采集容错（AH-A05） | 校验失败的 manifest 被生成端拦截；聚合侧单项目失败仅告警不阻塞（消费者义务，§6） | ✅ |
| 项目身份标识 | `index.json` → `project` 为开放对象，**联邦注册时项目 ID 由注册方（CI 配置）显式提供**，manifest 不内嵌唯一 ID | ⚠️ 约定俗成，鹰眼侧注册表负责唯一性 |
| 脏工作区标注 | `meta.json` → `evidence.dirty=true` 的 manifest 不可作为联邦快照（SHA 与扫描内容对不上） | ✅ |
| 跨项目真实链路（AH-C01） | `controller.endpoints`（provider 路由）× `feignInterface.endpoints`（consumer 调用）签名对齐，无需读源码 | ✅ |

### 4.1 鹰眼聚合产物分片（`cross-project.json`）

由 `aggregate` 子命令产出（非 doc-gen 生产分片）：

```json
{"schema_version": 1,
 "edges": [{"from": "projB", "to": "projA", "type": "http",
            "confidence": "confirmed | inferred",
            "evidence": {"consumer": {"qualifiedName", "sourcePath", "call"},
                          "provider": {"project", "qualifiedName", "route"}}}],
 "stats": {"confirmed": n, "inferred": n, "internalCalls": n, "unmatchedConsumers": n}}
```

- HTTP `confirmed`：method + 归一化路径完全一致（`{var}` 统一为 `{}`）
- MQ `confirmed`（`type: "mq"`）：`component.mqChannels` 的 producer/consumer 声明
  （`@RocketMQMessageListener` 等订阅注解 + `xxxTemplate.send/syncSend` 发布调用），
  channel 精确匹配（topic 全局命名空间）；依赖方向与 HTTP 统一（订阅者 → 发布者）
- DB `confirmed`（`type: "db"`）：同名表出现在 ≥2 个项目的 `database.json` →
  共享存储耦合边（from/to 字典序稳定，无向单边；evidence 含双方来源 DDL/PO）
- `inferred`（AH-C04）：HTTP 路由未命中、`@FeignClient(name)` 近似项目 id 的推断边——不进入阻断级结论
- 项目内调用（from == to）排除并计入 `internalCalls`

## 5. businessContext 扩展块（业务维度）

**分片**：`business-context.json`（可选）。**输入约定**：项目仓库内 `business-context.md`（人工维护）。

### 5.1 markdown 输入模板（doc-gen 解析的受约束子集）

```markdown
# 业务上下文

## 客户
- **商户**：通过开放平台接入的平台商户，使用收单与对账能力

## 角色
- **运营管理员**：管理商品上下架与订单异常处理

## 业务场景
- **下单**：(order) 客户在门店扫码下单，等待商家接单
- **对账**：(settlement) 商户每日拉取对账单核对流水

## 业务流程
### 订单履约流程
1. 创建订单 → CreateOrderCmdExe
2. 支付 → PayOrderCmdExe
3. 履约发货 → DeliverOrderCmdExe
```

解析规则：
- 四个固定二级标题：`## 客户` / `## 角色` / `## 业务场景` / `## 业务流程`；其余节忽略
- 客户/角色/场景条目：`- **名称**：描述`；场景支持 `(域名)` 前缀后缀标注归属
- 流程：`### 流程名` + 有序列表步骤，`步骤名 → 锚点表达式`（锚定 qualifiedName / `METHOD /path` / 表名）
- **行为/动作不独立建模**：由 scenarios/flows 的 `anchors` 关联 `component.methods` / `endpoints` 承载（代码强信号已在 domains 分片）

### 5.2 来源标注与弱信号合并

| source | 含义 | 生成方式 |
|---|---|---|
| `manual` | 人工提供 | business-context.md 解析 |
| `code` | 代码弱信号 | 扫描器提取：`@PreAuthorize` 角色、状态机流程、executor 命令动作 |
| `hybrid` | 人工+锚定 | 人工条目 + 扫描器自动补 anchors |

合并策略：**md 条目优先**，同名字段被 md 覆盖；扫描器弱信号不与 md 冲突时合并（如为人工角色补 `@PreAuthorize` 锚点）。

## 6. 消费者义务（鹰眼侧）

1. **校验后再纳管**：接收 manifest 先跑 `validate_manifest_dir`；失败 → 跳过 + 结构化告警（AH-A05），不得静默降级纳管。
2. **可选分片宽容**：`business-context.json` / `api-spec.json` 等缺失不视为错误。
3. **revision 卫生**：`evidence.dirty=true` 或 `revision=null` 的快照不进入联邦索引。
4. **契约变更联动**：doc-gen bump `schema_version` 时鹰眼同步升级，新旧并存期最长一个季度（AH-A04）。
