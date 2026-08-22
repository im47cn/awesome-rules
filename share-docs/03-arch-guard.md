# DDD 架构守护：arch-guard

## 1. 背景

DDD 分层架构能控制复杂度，但"分层规范"在落地时几乎全靠 Code Review 人肉把关——reviewer 疲于检查 import 方向、模块依赖，却经常漏掉。随着项目迭代，架构腐化悄然发生：领域层混入 Spring 注解、Adapter 直接依赖领域实体、跨域调用不走事件……

arch-guard 把架构规范变成可执行的两层检查，让"增量零容忍"成为可能。

## 2. 目标

- 检查 DDD 分层依赖方向是否正确（领域层不依赖基础设施，Adapter 不直接碰领域实体）
- 守护领域层纯净度（pom.xml 禁依赖框架、Java import 禁引入框架业务类）
- 校验命名后缀规范（CmdExe / E / CO / DO 等是否在正确分层）

## 3. 两层架构：脚本 + 知识图谱

| 层级 | 工具 | 精度 | 适用场景 |
|---|---|---|---|
| **Tier 1: 快速巡检** | `arch_check.py` 脚本 | 文件级，启发式匹配 | CI 门禁、提交前自检 |
| **Tier 2: 深度审查** | 知识图谱 Cypher 查询 | 方法级 `qualified_name` | 代码审查、违规证据输出 |

**分界原则**：Tier 1 做脚本擅长的（pom.xml 解析、正则命名匹配、框架 import 检测），Tier 2 做脚本做不准的（层间依赖方向分析——知识图谱天然过滤第三方包，精确到方法级，输出完整 caller → callee 证据链）。

## 4. 核心机制：基线 + 增量零容忍

存量项目不可能一次性整改完。arch-guard 提供**基线机制**——冻结当前所有违规，此后只报新增：

```
历史债务容忍 ──── 逐条偿还 ──── 自然收敛到零
增量腐化零容忍 ── CI 门禁拦截 ── 不再恶化
```

## 5. 特点

- **标准**：封装公司 DDD 架构规范
- **敏捷**：Python 3 标准库脚本，无第三方依赖；CI 友好
- **精确**：知识图谱精确到方法级，输出完整证据链
- **务实**：基线机制兼容存量项目，不强求一步到位
- **质量**：测试覆盖率 99%，pytest 90% 门禁守护，回归防退化
- **共创**：支持贡献 badcase，提供回归测试脚本

## 6. 风险提示

本工具覆盖脚本可检查的分层规则和知识图谱可查的依赖方向，**聚合设计合理性、值对象不可变性等仍需人工判断**，不能完全替代架构评审。

## 7. 安装方法

见《【Skills Hub】awesome-rules 做懂技术集团的 AI 搭子》。

---

## 8. 接入案例

### 案例 1：存量项目接入（3 步）

**第 1 步**：自动生成配置（从 pom.xml 推断包前缀）

```bash
python3 scripts/arch_check.py . --init
```

输出 `.arch-guard.json`，自动推断 `project_package_prefix`。

**第 2 步**：冻结当前违规为基线

```bash
python3 scripts/arch_check.py . --update-baseline .arch-guard-baseline.json
```

此刻所有现存违规被记录为"历史债务"，不再报警。

**第 3 步**：此后每次提交仅检查增量

```bash
python3 scripts/arch_check.py . --baseline .arch-guard-baseline.json --strict
```

> 存量违规逐条偿还后，重新执行第 2 步更新基线——自然收敛到零。

---

### 案例 2：Tier 1 脚本巡检

**输入**：一个存在典型分层违规的项目（domain 层依赖了 adapter）。

```bash
python3 scripts/arch_check.py . --format json
```

**脚本检查覆盖**：

| 检查类别 | 检查内容 |
|---|---|
| Maven 模块依赖 | 同域内分层依赖矩阵 + 跨域仅允许 `-client` |
| 领域层纯净度 (POM) | domain 模块 pom.xml 禁止依赖 Spring Boot / MyBatis |
| 领域层纯净度 (Java) | domain 层禁止 import 框架业务类 |
| 依赖方向 | 各层 Java import 逆向依赖检测 |
| 命名后缀 | CmdExe / E / CO / DO 等 14 种后缀是否在正确分层 |
| Adapter 隔离 | adapter 层禁止直接 import 领域实体 / 值对象 |

---

### 案例 3：Tier 2 知识图谱深度审查

**前提**：项目已通过 `codebase-memory-mcp` 建立索引。

**第 1 步**：生成 Cypher 查询清单

```bash
python3 scripts/arch_check.py --mode graph
```

查询清单覆盖 6 个依赖方向（Domain→Infrastructure、Domain→Application、Adapter→Domain Entity 等）。

**第 2 步**：将查询粘贴到 `codebase-memory-mcp` 执行

结果中每行是一条违规，包含精确的 **caller → callee** 链路。知识图谱天然不索引第三方包，一次查询拿到全部精确证据。

> 知识图谱的优势：精确到方法级 `qualified_name`，而不仅是文件级；天然过滤第三方包，不需要配置 `project_package_prefix`。
