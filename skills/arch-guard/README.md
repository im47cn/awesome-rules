# arch-guard

DDD 架构分层守护技能 — 检查分层依赖方向、Maven 模块依赖、领域层纯净度、命名后缀和 Adapter 隔离。

## 架构

两层设计，分工互补：

| 层级 | 工具 | 精度 | 适用场景 |
|---|---|---|---|
| **Tier 1** | `arch_check.py` 脚本 | 文件级 | CI 门禁、提交前自检 |
| **Tier 2** | `codebase-memory-mcp` Cypher 查询 | 方法级 (`qualified_name`) | 代码审查、深度审计、违规证据输出 |

## 快速使用

### 新项目接入（3 步）

```bash
# 1. 自动生成配置（从 pom.xml <groupId> 推断 project_package_prefix）
python3 scripts/arch_check.py . --init

# 2. 冻结当前违规为基线（历史容忍，增量零容忍）
python3 scripts/arch_check.py . --update-baseline .arch-guard-baseline.json

# 3. 此后每次提交仅检查增量
python3 scripts/arch_check.py . --baseline .arch-guard-baseline.json --strict
```

存量违规逐条偿还后，重新执行第 2 步更新基线——自然收敛到零。

### Tier 1: 脚本巡检

```bash
# 基础检查
python3 scripts/arch_check.py .

# 严格模式 + JSON 输出
python3 scripts/arch_check.py path/to/project/ --strict --format json
```

**退出码**：`0` = 通过，`1` = 有强制问题，`2` = 运行错误

### 项目配置

`--init` 自动生成最小 `.arch-guard.json`。也可手动创建：

```json
{
  "project_package_prefix": "com.acme",
  "layer_aliases": {},
  "domain_annotation_imports": [
    "org.springframework.stereotype",
    "org.springframework.transaction.annotation"
  ]
}
```

| 配置项 | 作用 |
|---|---|
| `project_package_prefix` | 依赖方向检查仅分析此前缀下的 import，避免第三方误报 |
| `layer_aliases` | 层路径别名（如 `interfaces` → `adapter`，默认已含） |
| `domain_annotation_imports` | 领域层额外允许的注解类框架包 |
| `module_suffixes` | Maven 模块后缀 → 层映射（覆盖默认） |

### Tier 2: 知识图谱深度审查

前提：项目已通过 `codebase-memory-mcp` 的 `index_repository` 建立索引。

列出可用的 Cypher 查询清单：

```bash
python3 scripts/arch_check.py --mode graph
```

查询按依赖规则矩阵过滤，输出精确到方法级的 caller → callee 违规证据。知识图谱天然不索引第三方包，无需额外过滤。

## 脚本检查覆盖

| 检查类别 | 检查内容 |
|---|---|
| Maven 模块依赖 | 同域内分层依赖矩阵校验 + 跨域仅允许通过 `-client` |
| 领域层纯净度 (POM) | domain 模块 pom.xml 禁止依赖 Spring Boot/MyBatis 等框架 |
| 领域层纯净度 (Java) | domain/ 下 Java 文件禁止 import 框架业务类（JPA 注解类除外） |
| 依赖方向 | 各层 Java import 逆向依赖检测（如 domain → adapter） |
| 命名后缀 | Inter/PO/DTO/Command/Mapper/Repository 等后缀是否在正确分层（对齐 02-naming） |
| Adapter 隔离 | adapter 层禁止直接 import 领域实体/值对象 |
| 状态泄漏 | adapter/infrastructure 层禁止直接改写状态（setStatus/changeStatus 等） |
| 状态机治理 | 有状态枚举但未引入状态机框架（Spring/Cola）→ 推荐级提醒 |

## 需人工补充的规则

读取 [`steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)（架构与分层：模块/业务域/分层/CQRS/状态机/扩展点），逐项核对脚本无法覆盖的规则：

| 自动检查覆盖 | 仍需人工判断 |
|---|---|
| 依赖方向（脚本 + Cypher） | 聚合设计是否合理（大小、边界） |
| 领域层纯净度（脚本 + POM） | 值对象是否不可变（setter 检查） |
| 命名后缀（脚本） | 应用服务是否包含业务逻辑 |
| 跨域 Maven 依赖（脚本） | 跨域通信是否应使用事件解耦而非 API 调用 |

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 检查脚本：[`scripts/arch_check.py`](scripts/arch_check.py)
- 单元测试：[`scripts/tests/test_arch_check.py`](scripts/tests/test_arch_check.py)（53 条）
- 架构规范：[`steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)
- 审查样例：[`badcase/`](badcase/)（4 组场景，覆盖 9 处违规）
