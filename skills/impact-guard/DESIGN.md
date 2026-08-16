# impact-guard 技术设计文档

> **定位**：本文档是 impact-guard 的**实现设计**（how），聚焦数据管道、接口、模块与实施路线。
> **完整论证**（动机、CodeSee XY 问题、职责边界、grill 7 决策 + 3 bug 修正、评审检查清单）见独立评审稿：
> [`../../docs/design/impact-guard-design.md`](../../docs/design/impact-guard-design.md)
> **维护原则**：本文档是 single source of truth。评审稿通过后归档，避免两份并行维护漂移。

---

## 1. 总览

impact-guard 回答 **"改这个，会波及谁？"**——给定变更点，沿图谱计算受影响范围（inbound），按「直接/间接」+ GTSP 业务边界分级。

```
变更点 (git diff / --changed)
    │
    ▼
ChangeExtractor
    │
    ▼
┌── Tier 2（主）: GraphTracer ─────────────────────────┐
│  head_sha 新鲜度检测 → 过期自动 reindex（--skip-reindex 可跳过）│
│  query_graph 动态 Cypher（主）+ trace_path（交互备选）          │
│  未 index → 降级 Tier 1                                        │
└────────────────────────────────────────────────────────┘
    │
    ▼
CriticalRanker（直接/间接分级） ──► Renderer (text / json / mermaid)
```

**架构**（grill 修订：v1 只做 Tier 2，Tier 1 降为 fallback）：

| 层级 | 实现 | 精度 | 定位 |
|---|---|---|---|
| **Tier 2（主）** | `codebase-memory-mcp` `query_graph` Cypher | 方法级 `qualified_name` | v1 核心路径 |
| **Tier 1（fallback）** | `impact_check.py`（import 反向索引，复用 JavaScanner） | 文件/类级 | 仅未 index 时降级 |

> 为何砍 Tier 1 独立实现：实测 GTSP 主流调用（@Autowired/Feign）有 import，Tier 1 本就能覆盖；Tier 1 与 Tier 2 差异是**粒度**而非盲区；且 11 个项目都已 index。详见评审稿 §4。

---

## 2. 数据管道

### 2.1 变更点提取（ChangeExtractor）

两种输入归一为 `List[ChangePoint]`：

- `--diff <ref>`（默认 `origin/master...HEAD`）：`git diff --name-only` + hunks → 文件 → 类（复用 `JavaScanner`）。v1 粒度：**类级**。
- `--changed <qn|file>`（可多次）：显式起点。

```python
@dataclass
class ChangePoint:
    qualified_name: str      # com.example.order.app.OrderCreateExecutor
    file_path: str
    layer: str               # adapter / app / domain / infra（复用 LayerIdentifier）
    change_type: str         # modified / added / deleted
```

### 2.2 Tier 1 fallback：import 反向索引

**索引构建**（一次性，复用 arch-guard `JavaScanner`，含 `project_package_prefix` 过滤）：

```
扫描所有 .java 的 import → reverse_index[被import的类] = {依赖方集合}
```

**传播**：以每个 `ChangePoint` 为根，沿 `reverse_index` BFS 至 `--depth`（默认 3），收集受影响方（inbound）。

**精度盲区**（grill 实测修正）：

> ⚠️ 原设计误把 @Autowired/Feign 列为盲区——这俩有 import，**Tier 1 能覆盖**。真盲区：反射 / 动态代理 / 多态集合分发的具体实现（Tier 2 图谱**同样盲**）。Tier 1 与 Tier 2 差异是**粒度（类 vs 方法）**，非盲区大小。

仅在项目未 index 且未 reindex 时启用，输出头部标注 `[Tier 1 only]`。

### 2.3 Tier 2（主）：query_graph + 影响方向 + 新鲜度

**主路径**：`--mode graph` 生成动态 Cypher，经 `query_graph` 反查多跳 caller 链。`trace_path` 仅作交互态备选（对完整 `qualified_name` 匹配不稳定）。

**影响方向**（grill 修订：诚实区分，不伪装）：

| 变更点类型 | 产出 | 说明 |
|---|---|---|
| 普通类（Service/Assembler/Executor） | `impact`（inbound 证据链） | 真正的影响传播 |
| 框架入口（Controller/MQ Listener/JobHandler/Callback 实现） | `无法分析影响` + `regression_scope`（下游树） | 图内无入边（框架驱动），不伪装成影响分析，另起回归建议 |

> 实测：`DongxinSmsCallbackHandler.handle`（List 注入分发）与 8 个 `@FeignClient` 接口均 `in_degree=0`——动态代理调用边图谱建不出。

**新鲜度**（grill 新增）：对比 `index head_sha` 与 `git HEAD`，过期自动 `index_repository` reindex；`--skip-reindex` 跳过。impact-guard 不实现索引逻辑，只编排"检测 → 触发"。

**Cypher 动态生成**（对齐 arch-guard `--mode graph`，不手抄）：

```bash
python3 scripts/impact_check.py --mode graph --config .impact-guard.json
```

### 2.4 关键路径分级（直接/间接 + 5 通道）

**5 通道 × 2 方向边界矩阵**（`--init` 扫描注解/SDK 调用动态生成）：

| 通道 | 入站入口（→ 回归范围） | 出站/落点（变更点=此→🔴 直接） |
|---|---|---|
| HTTP | `@RestController`/`@Controller` | Feign 客户端 |
| MQ | `@RocketMQMessageListener`/`@KafkaListener` | Producer 发送调用 |
| DB | — | `@Mapper` |
| 缓存 | — | `RedisUtil`/`@CachePut`/`@CacheEvict` |
| 定时 | `@XxlJob`/JobHandler | — |

**分级**（grill 修订：替代单一 🔴，避免门禁通胀）：

| 级别 | 触发 | `--strict` |
|---|---|---|
| 🔴 **直接** | 变更点本身是出站/落点（Producer/Mapper/Redis 写/Feign 出站/`-client`） | exit 1 |
| 🟠 **间接抵达** | 普通类变更，影响链 ≥1 跳抵达边界 | 不阻断，告警 + 回归建议 |
| 🟡 Warning | 穿越跨服务边界（本服务内）或触及聚合根 | — |
| 🟢 Info | 仅同层/内部实现 | — |

**跨服务**：变更点是 `@FeignClient`/`-client` → 🔴 直接 + 输出 `⚠️ 跨服务影响未分析`。跨服务传播列 v2。

### 2.5 渲染（Renderer）

- `text`：人读，分级标记 + 证据链。
- `json`：机读（CI / Agent），结构化 ImpactReport。
- `mermaid`：`graph RL`，DDD 泳道，classDef 四色（🔴直接/🟠间接/🟡/🟢），`[CHANGED]` 双线框，>20 节点折叠到聚合根。

---

## 3. 技术栈

- Python 3（对齐 arch-guard / doc-gen）。
- `arch-guard.JavaScanner` / `LayerIdentifier` / `SUFFIX_TYPE_MAP`（复用，见 §6）。
- `codebase-memory-mcp`（Tier 2 + reindex 编排）。
- 测试：pytest，覆盖率 >90%。

---

## 4. CLI 工具设计

```bash
python3 scripts/impact_check.py <project_root> [选项]
```

### 4.1 命令设计

| 参数 | 默认 | 作用 |
|---|---|---|
| `project_root`（位置） | `.` | 目标项目根 |
| `--diff <ref>` | `origin/master...HEAD` | 从 git diff 提取变更点 |
| `--changed <qn\|file>` | — | 显式变更起点（可多次） |
| `--depth <n>` | `3` | 影响传播深度 |
| `--mode {quick,graph}` | `quick` | quick=Tier1 fallback / graph=输出 Tier2 Cypher |
| `--format {text,json,mermaid}` | `text` | 输出格式 |
| `--strict` | off | 触及 🔴 直接则 exit 1 |
| `--config` | 自动查 `.impact-guard.json` | 配置文件 |
| `--init` | — | 扫描注解动态生成 boundaries 配置 |
| `--skip-reindex` | off | 跳过过期自动 reindex |

> 完整参数由脚本 `--help` 输出，不在此静态复制。

**退出码**：`0` = 无 🔴 直接影响 · `1` = 触及 🔴 直接（`--strict`）· `2` = 运行错误。

### 4.2 配置（grill 修订：动态生成）

> ⚠️ 原设计写死 glob（`**.adapter.**`）实测命中 0（GTSP Controller 在 `interfaces.facade.*`）。改为 `--init` 扫描生成。

```json
{
  "project_package_prefix": "com.acme",
  "boundaries": {
    "http_entry": ["@RestController", "@Controller"],
    "http_exit":  ["@FeignClient"],
    "mq_entry":   ["@RocketMQMessageListener", "@KafkaListener"],
    "mq_exit":    ["rocketMQTemplate.*", "kafkaTemplate.*"],
    "db_sink":    ["@Mapper"],
    "cache_sink": ["RedisUtil", "@CachePut", "@CacheEvict"],
    "job_entry":  ["@XxlJob"]
  },
  "highways": ["**Util", "**Assembler"],
  "ignore": ["**/test/**", "**/dto/**", "**/query/**"]
}
```

| 配置项 | 作用 | 来源 |
|---|---|---|
| `project_package_prefix` | 包前缀过滤 | `--init` 从 pom.xml 推断 |
| `boundaries` | 5 通道边界（驱动直接/间接判定） | `--init` 扫注解/SDK 调用 |
| `highways` | 高速通路白名单（影响面大但可控，降级） | 启发式 + 人工 |
| `ignore` | 不计入传播 | 手动 |

### 4.3 模块划分

```
scripts/
├── impact_check.py      # CLI 主入口 / 编排
├── change_extractor.py  # git diff / --changed → ChangePoint
├── impact_scanner.py    # Tier 1 fallback: import 反向索引（复用 JavaScanner）
├── graph_tracer.py      # Tier 2: query_graph Cypher + 影响方向 + 新鲜度/reindex
├── boundary_scanner.py  # --init: 扫描注解/SDK 生成 boundaries（5 通道）
├── critical_ranker.py   # 直接/间接分级
├── renderer.py          # text / json / mermaid 三态渲染
└── tests/
```

模块职责单一（SRP）：提取 / 扫描 / 图谱 / 边界 / 分级 / 渲染独立，CLI 仅编排。

---

## 5. 与 doc-gen 集成

**时态冲突**：doc-gen = 项目静态快照，impact-guard = 变更增量。集成方式为"在快照站点叠加增量影响视图"。

| 场景 | 形态 | v1 状态 |
|---|---|---|
| PR 描述 | `--format mermaid` 输出贴入 | 📋 v1 |
| CI 门禁 | `--strict`，触及 🔴 直接 fail + json 证据 | 📋 v1 |
| doc-gen 站点 | `/impact/` 交互页输入变更点 → 实时渲染 | 📋 v1.1 |

---

## 6. 与现有技能的复用

```
arch-guard (审查)          impact-guard (影响)
─────────────              ─────────────────
JavaScanner        ──共享──► impact_scanner.py（import 提取 + 包前缀过滤）
LayerIdentifier    ──共享──► change_extractor.py（变更点分层归属）
SUFFIX_TYPE_MAP    ──共享──► critical_ranker.py（后缀 → 层/聚合根）
--mode graph 惯例  ──对齐──► 动态 Cypher 生成（不手抄）
退出码 0/1/2       ──对齐──► 0/1/2 语义一致

doc-gen (文档)            impact-guard (影响)
─────────────              ─────────────────
cola-sample 风格  ──对齐──► fixtures/ddd-sample
状态标记惯例      ──对齐──► v1 范围表
```

**不重叠**：不做违规判定（arch-guard）、不生成全景文档（doc-gen）。

---

## 7. 实施路线

### 7.1 v1 范围

> 2026-08-16 v1 已实施 ✅（43 测试 / 覆盖率 95%）。

| 功能 | 状态 |
|---|---|
| git diff → 变更点（类级） | ✅ |
| `--changed` 显式起点 | ✅ |
| Tier 2 query_graph + 影响方向 | ✅（Cypher 生成 + 新鲜度指引，Agent 编排执行） |
| Tier 1 fallback（未 index 降级） | ✅（quick 模式独立可用） |
| 新鲜度检测 + 增量 reindex + `--skip-reindex` | ✅（graph 模式输出指引；reindex 由 Agent 持有的 MCP 工具执行） |
| `--init` 扫描注解生成 boundaries（5 通道） | ✅ |
| 直接/间接分级（🔴直接/🟠间接/🟡/🟢） | ✅ |
| 跨服务契约识别为 🔴 直接 + 强制告警 | ✅ |
| text / json / mermaid 输出 | ✅ |
| PR + CI `--strict` 门禁（只拦直接） | ✅ |
| doc-gen `/impact/` 站点内嵌 | 📋 v1.1 |
| 方法级 git diff 解析 | 📋 v2 |
| 跨服务传播（cross-repo-intelligence） | 📋 v2 |
| ~~baseline 噪声冻结~~ | ❌ 放弃（语义不通） |

**实施注记**：
- `JavaScanner`/`LayerIdentifier` 实际复用来源为 **doc-gen**（`scanner/java.py`、`generator/layers.py`），经 `scripts/_compat.py` sys.path 桥接；评审稿 §6 写 arch-guard 系笔误（arch-guard 为单文件 arch_check.py，从未含这两个类）。
- mermaid 渲染 >20 节点折叠为简化实现（folded 计数节点）。
- `--init` 生成的 `boundary_hits`（实际命中类清单）随配置保存，ranker 直接判定无需重扫。

### 7.2 测试策略

`fixtures/ddd-sample/` 复刻最小 DDD 项目（含 Controller/Mapper/Listener/Feign/RedisUtil 边界），覆盖率 >90%：

| 测试类 | 覆盖点 |
|---|---|
| 变更点识别 | `--diff`/`--changed`、文件→类 |
| 影响传播 | BFS 深度、inbound、`ignore` |
| 影响方向 | 普通类→impact；入口→无法分析+回归范围 |
| 关键路径分级 | 🔴直接/🟠间接/🟡/🟢、`--strict` |
| 边界扫描 | `--init` boundaries 生成（5 通道） |
| 新鲜度 | head_sha 一致/过期、reindex 触发、`--skip-reindex` |

### 7.3 可行性验证（已完成 ✅）

实测 `gtsp-base-message-center`（6661 节点）+ `crm-gtsp-crm-task`，结论：**v1 可落地，Tier 2 价值成立**。详见评审稿 §1.4 与 grill 记录。

---

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 快速使用：[`README.md`](README.md)
- 完整论证 / 评审稿（含 grill 决策）：[`../../docs/design/impact-guard-design.md`](../../docs/design/impact-guard-design.md)
- 架构规范：[`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)
- 复用来源：[`../arch-guard/scripts/arch_check.py`](../arch-guard/scripts/arch_check.py)
