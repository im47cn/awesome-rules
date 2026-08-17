# 架构鹰眼 (Arch Hawkeye)

> 全局架构观测与治理 — 消费各项目 doc-gen 产出的 `doc-manifest/`，把"多个项目的文档拼在一起"
> 升级为"全局观测 + 治理闭环"。

## 定位

| | doc-gen（生产者） | 架构鹰眼（本项目） |
|---|---|---|
| 目标 | 新人 5 分钟看懂一个项目 | 全公司看清架构健康度 |
| 范围 | 单项目入门文档（业务+技术全维度） | 多项目聚合 / 跨项目链路 / 治理闭环 |
| 交接物 | `doc-manifest/`（AH-MANIFEST 契约） | — |

## 当前能力（Phase 1–2）

```bash
# 聚合多个项目 manifest 到架构鹰眼站点（渲染复用 doc-gen 的 Astro 模板）
python3 scripts/hawkeye.py aggregate projects.json --output site/ --build
```

`projects.json`：

```json
{
  "title": "公司架构全景",
  "projects": [
    {"id": "order-system", "name": "订单系统", "manifest": "./order/doc-manifest/", "repo": "..."}
  ]
}
```

产出：公司级全景拓扑图、合并 ER 图与 API 规范的静态站点，以及——

**跨项目真实链路（Phase 2 ✅，AH-C01/C04）**：`cross-project.json` 分片——
Feign 调用签名 × Controller 路由签名对齐（不靠域名猜测），每条边附双侧证据：

- HTTP 边：method+路径完全匹配（路径变量归一化），consumer/provider 证据齐全
- MQ 边（`type: "mq"`）：`mqChannels` 声明对齐——订阅注解
  （`@RocketMQMessageListener`/`@KafkaListener`/`@RabbitListener`）×
  发布调用（`xxxTemplate.syncSend/send/convertAndSend`），topic 精确匹配
- DB 边（`type: "db"`）：同名表跨项目交集 = 共享存储耦合（最隐蔽的耦合——
  无接口签名可对齐）；impact 支持表名输入（`--entity t_order` → 共享方列表）
- 缓存边（`type: "cache"`）：`cacheKeys` 声明对齐——key 字面量相等 confirmed /
  `:` 分段前缀包含 inferred（同 key 空间），Redis 共享缓存耦合
- 定时资产：`schedules`（`@XxlJob`/`@Scheduled`）统计入 `stats.jobAssets`，
  不造假跨项目边（调度中心依赖代码不可见）
- `inferred`：路由未命中但 `@FeignClient(name)` 近似项目 id 的推断边（低置信度）
- 项目内调用自动排除；`diagrams.json.crossProjectEdges` 同步供前端渲染

> GTSP 5 通道全覆盖：HTTP ✅ MQ ✅ DB ✅ 缓存 ✅ 定时（资产形态）✅

**跨项目变更影响分析（Phase 2 ✅，AH-C03）**：

```bash
# 变更实体支持：类名 / 限定名 / 路由；🔴直接（跨项目边）/ 🟠间接（项目内依赖 BFS）
python3 scripts/hawkeye.py impact ./site --entity DemoController
python3 scripts/hawkeye.py impact ./site --entity "GET /demo/v1/orders/{id}" --max-hops 3
python3 scripts/hawkeye.py impact ./site --entity DemoController --json   # CI 消费
```

影响面与图谱实际可达边一致（无虚构）：direct 仅来自跨项目边 provider 侧命中，
indirect 沿 `component.deps` 反向 BFS（跳数裁剪、环安全）。

## 路线图

> 历史需求编号（AH-A02、AH-C01 等）源自初期 EARS 需求规格，该文件已随演进移除，
> 编号仅作阶段溯源用。

| 阶段 | 能力 | 关键需求 | 状态 |
|---|---|---|---|
| Phase 1 | 联邦聚合：多项目 manifest 聚合（`evidence.revision` 指纹就绪，CI 自注册待接入） | AH-A02/A03 · D01/D02 | 🚧 |
| Phase 2 | 跨项目真实链路：confirmed/inferred 边构建 ✅；变更影响分析 ✅；可查询架构图待做 | AH-C01–C04 | 🚧 |
| Phase 3 | 治理闭环 ✅：基线/趋势/blame 归属/债务登记/超期告警/增量零容忍门禁 | AH-D01–D07 | ✅ |
| Phase 4 | 双模式：本地运行（零 LLM token）+ 集中处理 | AH-B01–B03 | 📋 |

## 治理闭环（Phase 3 ✅，REQ-D 全落地）

```bash
# D01 建基线（存量违规自动登记债务，owner 取 git blame 归属）
python3 scripts/hawkeye.py baseline ./doc-manifest --name 2026H2

# D02 趋势（added/removed/retained + D06 消除自动关债）
python3 scripts/hawkeye.py trend ./doc-manifest --baseline 2026H2

# D07 增量零容忍门禁（基线之上新增违规 → exit 1；--warn-only 灰度）
python3 scripts/hawkeye.py gate ./doc-manifest --baseline 2026H2 [--warn-only]

# D04/D05 债务登记表（list / overdue / exempt --fp x --reason 必填）
python3 scripts/hawkeye.py debt ./doc-manifest list
python3 scripts/hawkeye.py debt ./doc-manifest overdue
```

- **fingerprint** = `sha1(file + ruleCode + description)`：行漂移不影响身份，
  同点重复违规合并为一条债务
- **D03 归属**：doc-gen risks 生成时逐条 `git blame`（author + introducedAt，
  失败降级 null）；**D06 闭环**：违规消失 → 债务自动 repaid；**豁免强制理由**
- 真实仓库验证：mc 273 违规 → 269 条带归属（liyufei/renshibo 等），
  建基线/演进/门禁阻断（exit 1）/灰度放行（exit 0）全流程通过

## 目录结构

```
arch-hawkeye/
├── AH-MANIFEST.md       # 公共契约（真相源在 skills/doc-gen/schemas/）
└── scripts/
    ├── hawkeye.py       # CLI 入口
    ├── aggregate.py     # 多项目聚合（自 doc-gen 迁移）
    └── tests/           # pytest
```

## 相关文档

- 数据契约：[AH-MANIFEST.md](AH-MANIFEST.md)
- 数据生产者：[../skills/doc-gen/SKILL.md](../skills/doc-gen/SKILL.md)
