---
name: arch-guard
description: >
  DDD 架构分层守护，两层架构：(1) 脚本快速巡检（CI 门禁，覆盖 pom 依赖、命名后缀、领域层框架引用），
  (2) 知识图谱深度审查（精确到 qualified_name 的层间逆向依赖证据链）。
  当用户提到：架构审查、架构检查、分层检查、包依赖检查、DDD 规范检查、架构守护、
  依赖方向、领域层纯净度、Maven 模块依赖时激活。
---

# DDD 架构分层守护

## 两层架构

| 层级                 | 工具                              | 精度                          | 适用场景                         |
| -------------------- | --------------------------------- | ----------------------------- | -------------------------------- |
| **Tier 1: 快速巡检** | `arch_check.py` 脚本              | 文件级，启发式字符串匹配      | CI 门禁、提交前自检              |
| **Tier 2: 深度审查** | `codebase-memory-mcp` Cypher 查询 | `qualified_name` 精确到方法级 | 代码审查、人工复核、违规证据输出 |

**分界原则**：Tier 1 覆盖脚本天然擅长的事项（pom.xml 解析、正则命名匹配、框架 import 检测）。Tier 2 覆盖脚本做不准的事项——层间依赖方向分析，因为知识图谱：

- 天然过滤第三方包（图只索引项目自身节点）
- 精确到方法级 qualified_name（而不仅是文件）
- 输出完整的证据链（caller → callee）

## 接入工作流（推荐）

存量项目优先使用基线机制——**历史债务容忍，增量腐化零容忍**。

```bash
# 1. 生成配置（自动从 pom.xml 推断 project_package_prefix）
python3 scripts/arch_check.py . --init

# 2. 冻结当前所有违规为基线（有意重置债务线时才用）
python3 scripts/arch_check.py . --refreeze .arch-guard-baseline.json

# 3. 此后 CI 仅报基线中不存在的【新增】违规
python3 scripts/arch_check.py . --baseline .arch-guard-baseline.json --strict --frozen
```

基线为 ratchet 语义（只缩不涨）：偿还一条存量 → 下次运行自动从基线剔除并写回，
自然收敛到零，无需重新生成；`--frozen` 三态校验：基线缺失/损坏 → exit 2（防 CI 误建吞违规/坏文件静默放行），合法空基线 = 债务已还清，正常放行（对齐 ArchUnit 空 store 全绿）。

## 审查工作流

### Tier 1: 快速巡检（脚本）

```bash
python3 scripts/arch_check.py <项目根目录> [--format json] [--strict] [--config .arch-guard.json]
```

- `--strict`：推荐问题升级为强制
- `--config`：配置文件路径（自动查找 `.arch-guard.json`）
- `--init`：自动生成最小配置（从 pom.xml `<groupId>` 推断 `project_package_prefix`）
- 退出码：`0`=通过，`1`=有强制问题，`2`=运行错误

脚本检查项（字符串匹配，文件级）：

| 检查项         | 说明                                                                            |
| -------------- | ------------------------------------------------------------------------------- |
| Maven 模块依赖 | 同域层依赖矩阵 + 跨域仅允许 `-client`                                           |
| 领域层框架引用 | pom.xml 禁止 Spring Boot/MyBatis；Java import 禁止框架业务类                    |
| 命名后缀       | Inter/PO/DTO/Command/Mapper/Repository 等后缀是否在正确分层（对齐 02-naming）   |
| 状态泄漏       | adapter/infrastructure 层禁止直接改写状态（setStatus/changeStatus 等）          |
| 状态机治理     | 有状态枚举但未引入状态机框架（Spring/Cola）→ 推荐级提醒                         |
| 结构性债务     | 契约对象（Command/DTO/Query）被跨层引用——单独计数，不计入门禁 `mandatory_count` |
| 报告输出       | `--mode graph` 输出 Tier 2 Cypher 查询清单（动态生成，适配 `layer_aliases`）    |

### Tier 2: 深度审查（知识图谱）

**前置条件**：目标项目已通过 `codebase-memory-mcp` 建立索引（`index_repository`）。

**Tier 2 的 Cypher 查询清单由脚本动态生成**，不再在本文档中手抄副本——脚本是 single source of truth，文档手动复制必然会漂移（如先前手抄的 `:Function` 标签导致 0 结果）。

获取最新查询清单：

```bash
python3 scripts/arch_check.py --mode graph
```

或带项目配置（生成适配本项目的层别名变体）：

```bash
python3 scripts/arch_check.py --mode graph --config .arch-guard.json
```

查询清单覆盖 6 个方向：(1) Domain→Infrastructure (2) Domain→Application (3) Adapter→Domain Entity (4) Infrastructure→Application (5) Application→Adapter (6) 跨层违规汇总（单条矩阵过滤）。

> **使用方式**：将 `--mode graph` 输出的任意查询粘贴到 `codebase-memory-mcp` 的 `query_graph` 工具中执行。结果中每行是一条违规，包含精确的 caller → callee 链路。
> 知识图谱天然不索引第三方包，一次查询拿到全部精确证据——不需要像脚本那样配置 `project_package_prefix`。

### 补充人工判断

读取 [`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)（架构与分层：模块/业务域/分层/CQRS/状态机/扩展点），逐项核对两轮自动检查无法覆盖的规则：

| 自动检查覆盖                      | 仍需人工                                         |
| --------------------------------- | ------------------------------------------------ |
| 依赖方向（脚本 + Cypher）         | 聚合设计合理性（大小、边界）                     |
| 领域层纯净度（脚本 import + pom） | 值对象是否不可变（setter 检查）                  |
| 命名后缀（脚本）                  | 应用服务是否包含业务逻辑                         |
| 跨域 Maven 依赖（脚本）           | 跨域通信是否使用了事件而非 API（应偏向事件解耦） |

## 配置文件

自动生成（推荐）：

```bash
python3 scripts/arch_check.py . --init     # 从 pom.xml 推断 prefix，生成 .arch-guard.json
```

或手动创建 `.arch-guard.json`：

```json
{
  "project_package_prefix": "com.acme",
  "layer_aliases": { "interfaces": "adapter" },
  "domain_annotation_imports": [
    "org.springframework.stereotype",
    "org.springframework.transaction.annotation"
  ]
}
```

| 配置项                      | 作用                                                    |
| --------------------------- | ------------------------------------------------------- |
| `project_package_prefix`    | 脚本依赖方向检查仅分析此前缀下的 import，避免第三方误报 |
| `layer_aliases`             | 层路径别名（如 `interfaces` → `adapter`）               |
| `domain_annotation_imports` | 领域层额外允许的注解类框架包（务实 DDD）                |
| `module_suffixes`           | Maven 模块后缀 → 层映射（覆盖默认）                     |

## CI 集成

```yaml
# Tier 1: 存量容忍，增量零容忍（推荐）
- name: 架构分层巡检
  run: |
    python3 skills/arch-guard/scripts/arch_check.py src/ \
      --baseline .arch-guard-baseline.json --strict --frozen

# 基线随项目提交（首次用 --refreeze 生成）
# ratchet 只缩不涨：偿还一条存量 → 下次运行基线自动少一条 → 自然收敛到零

# Tier 2: 深度审查（仅 main 分支合并时）
# 通过 codebase-memory-mcp 执行 --mode graph 输出的 Cypher 查询
```
