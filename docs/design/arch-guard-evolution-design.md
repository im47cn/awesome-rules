# arch-guard 演进路线与技术设计（评审稿）

> **状态**：调研完成 ✅ · 待评审 · 评审通过后按 Phase 顺序落地
> **范围**：arch-guard 从"正则巡检引擎"演进为"规则编排层 + 确定性引擎外挂 + LLM 语义层"
> **依据**：arch-guard vs ArchUnit vs ArchGuard 对比调研（2026-08-15）
> **日期**：2026-08-15

---

## 1. 背景与结论

### 1.1 对比调研结论

arch-guard、ArchUnit、ArchGuard 是三个物种（AI 技能 / 测试断言库 / 治理平台），**错位竞争**：

| | arch-guard（现状） | ArchUnit | ArchGuard |
|---|---|---|---|
| 分析引擎 | import 正则 + pom XML 解析 | 字节码（ASM） | Chapi/ANTLR AST（9 语言） |
| 证据精度 | 文件/import 级 | 类/方法/成员级 | 模块/包/类/方法级 |
| 范围 | 单仓 Java（GTSP） | 单 JVM classpath | 组织级多仓 |
| 独有资产 | GTSP 域规则、steering 联动、LLM 语义审查、badcase 闭环 | 基线 ratchet 工程化 | 服务/DB/API 依赖地图、架构指标 |

**核心判断**：arch-guard 的护城河不在 Tier 1 正则引擎——它在用文本匹配做字节码分析早已解决的问题。真正的资产是 GTSP 领域规则知识（`_DEPENDENCY_RULES`/`_SUFFIX_RULES`/跨域 `-client`/状态机治理）和 LLM 语义层。演进方向是**正则引擎让位给确定性引擎，arch-guard 升级为规则编排层**。

### 1.2 必须演进的两个实证缺口

1. **证据精度**（Tier 1 是 CI 门禁，误报/漏报直接侵蚀规则公信力）：
   - `^import\s+([\w.]+)`（`arch_check.py:284`）对 `import static` **漏报**——领域层纯净度拦不住静态导入的框架类；
   - `import com.foo.*` 通配捕获到 `com.foo`，层归属失真；
   - 注释/字符串字面量命中 `CLASS_PATTERN`/`_STATUS_WRITE_RE`，存在误报面；
   - 字段类型、方法签名、注解使用、继承不可见；无循环依赖检测。
2. **基线非 ratchet**：`--update-baseline` 全量重冻——偿还存量时重跑一次，**重建时刻的全部违规（含新增）都被吞掉**。ArchUnit `FreezingArchRule` 的语义是只缩不涨。

### 1.3 明确不做的（同源自对比结论）

- ❌ 不自建多语言解析器（不重写 Chapi/ASM 的路）。
- ❌ 不部署 ArchGuard 平台。**触发条件**：组织级跨服务依赖地图（服务依赖、共享 DB 检测）成为真实痛点时，单独立项试点，不在本路线内。
- ❌ 不引入 FKlang/设计态 DSL。

---

## 2. 目标与非目标

### 2.1 目标

| # | 目标 | 验证方式 |
|---|---|---|
| G1 | 证据精度升至字节码级：依赖方向、循环依赖（新增能力）、命名分层、状态泄漏 | 试点项目 ArchUnit 违规集 ⊇ Tier 1 违规集 |
| G2 | 基线 ratchet 单向化：偿还自动收缩、重冻须显式 `--refreeze` | 单测：修一条 → 基线自动少一条；新增一条 → 报 |
| G3 | arch-guard 降级为编排层：`.arch-guard.json` + 内置规则矩阵 → 生成 ArchUnit 测试，配置是唯一源 | 生成物与配置一致性校验通过 |
| G4 | 保留 Python 强项：pom.xml 检查（ArchUnit 无构建文件视角）、配置校验、未迁移项目兜底 | 现有 53 条单测全绿 |
| G5 | LLM 语义规则正式化：聚合边界、贫血服务、事件解耦进 badcase 回归集 | badcase 场景数 4 → ≥8 |
| G6 | 不破坏 impact-guard 复用契约（`JavaScanner`/`LayerIdentifier`/`SUFFIX_TYPE_MAP`） | impact-guard 回归通过 |

### 2.2 非目标（v1 排除）

- ❌ 多语言支持（GTSP 是 Java 单语言场景）。
- ❌ 可视化平台 / C4 图（doc-gen 已有 Mermaid 出口）。
- ❌ IDE 实时插件（Agent 会话 + CI 已覆盖）。
- ❌ 方法级 diff 影响（impact-guard v2 职责，不混入）。
- ❌ 替换或废弃 Tier 2 图谱审查（方法级证据链保留在审查工作流）。

---

## 3. 目标架构：三层职责

| 层 | 载体 | 职责 | 运行时机 |
|---|---|---|---|
| **L1 确定性引擎** | ArchUnit（字节码）+ Python（pom.xml） | 二元对错判定，证据到类/方法级 | `mvn test`（随项目测试流水线） |
| **L2 规则编排** | `arch_check.py` | 从配置生成 ArchUnit 规则、校验生成物、pom/配置检查、兜底巡检 | CI 门禁 / 提交前 |
| **L3 语义审查** | LLM + Tier 2 Cypher + badcase | 引擎表达不了的判断：聚合边界、贫血服务、事件解耦偏好 | 代码审查 / Agent 会话 |

**职责原则**：确定性规则必须落在可复现引擎（字节码 > 正则）；LLM 只做引擎表达不了的语义判断；规则知识只存一份（`_DEPENDENCY_RULES` 等代码化矩阵），steering 规范与生成物都从它单向派生。

---

## 4. 演进路线

> 每个 Phase 自包含、可独立交付、可在新会话中执行。依赖关系：Phase 0/1 相互独立可并行；Phase 2 依赖 1（基线语义先定）；Phase 3 依赖 2；Phase 4 持续。

### Phase 0：止血——Tier 1 已知盲区修复（预估 0.5~1 天）

**What**（改动均在 `skills/arch-guard/scripts/arch_check.py`，不改对外接口）：

1. `IMPORT_PATTERN` 修复静态导入：`^import\s+(?:static\s+)?([\w.]+)`；对 `static` 成员导入按"宿主类归属层"判定。
2. 通配导入 `xxx.*`：无法定位目标类 → 记为 `STRUCTURAL_DEBT` 级"待 ArchUnit 复核"，不猜层。
3. 误报抑制：`CLASS_PATTERN`/`_STATUS_WRITE_RE` 命中行先剥离行注释/块注释/Javadoc 与字符串字面量再判定（轻量预处理器，不建 AST）。

**验证**：新增 badcase 场景（静态导入框架类进 domain、注释里的 `class XxxDTO`、字符串 `"updateStatus()"`）；`pytest skills/arch-guard/scripts/tests/` 全绿；对 fixtures/cola-sample 巡检输出不回退。

**反模式**：不借机重写扫描器（那是 Phase 2 之后的存量退役对象）；不引入 Java parser 依赖。

### Phase 1：基线 ratchet 单向化（预估 1 天）

**What**：

1. `filter_by_baseline` 改为**双向对账**：本次未出现的基线指纹自动剔除并写回（偿还即收缩，对齐 ArchUnit `allowStoreUpdate=true`）；新增违规照报。
2. `--update-baseline` 语义拆分：保留别名但打印 deprecation 提示，新增显式 `--refreeze`（有意重置债务线时才用，对齐 ArchUnit `freeze.refreeze`）。
3. 新增 `--frozen`（CI 模式）：基线文件不存在/为空时拒绝创建（对齐 `allowStoreCreation=false`），exit 2。

**验证**：单测覆盖三个场景——修一条存量→基线自动缩、新增一条→报且基线不变、`--frozen` 无基线文件→exit 2；README/SKILL.md 工作流三步文案同步。

**反模式**：不做指纹格式变更（sha1(file+rule+description) 保留），不做跨工具基线转换器。

### Phase 2：ArchUnit 规则生成器（核心，预估 spike 1~2 天 + 生成器 3~5 天）

#### 2a. Spike：试点项目手工验证（先证明，后投入）

选一个已索引的 GTSP 项目，**手写**一份 `ArchitectureGuardTest.java` 跑通：JUnit5 `@ArchTest` + `layeredArchitecture()` + `FreezingArchRule.freeze()` + `archunit.properties`。确认：JDK/gtsp-parent 兼容性、`mvn test` 时长可接受、违规输出可读。**Spike 不满足（如依赖冲突不可解/时长不可接受）则停在此处，Tier 1 + Phase 0/1 即终态**。

**Spike 结果（2026-08-18，试点 = `gtsp-cont-task`，✅ GO）**：

| 验证点 | 结果 |
|---|---|
| JDK/gtsp-parent 兼容 | ✅ JDK 17 + gtsp-parent（**source 级别 Java 8**）+ ArchUnit 1.2.1（本地 .m2 全离线可解析） |
| 四类规则可表达 | ✅ `layeredArchitecture` + `FreezingArchRule.freeze` + 命名后缀 + 状态泄漏 `callCodeUnitWhere(target(nameMatching(...)))` + `slices().beFreeOfCycles()` 全部编译运行通过 |
| ratchet 语义 | ✅ 首跑建 store 全绿 → 制造 `infrastructure→interfaces` 反向依赖 → 红且证据到**构造器参数类型/字段类型**（Tier 1 import 正则盲区实证）→ 删除后复绿，store 未污染 |
| 时长 | ✅ 4 规则 0.44s，单模块 mvn 总时长 ~2.3s |
| 违规输出可读 | ✅ `Architecture Violation [Priority: MEDIUM] - Rule '<规则全文>'` + 每条 class:line 证据 |

**踩坑记录（生成器必须吸收）**：
1. **试点项目 pom 不完备**：fss-common 的 lombok 是 `provided`（不传递），纯 `mvn test` 从未跑通过（团队靠 IDE）。生成器接入指引须含"补 lombok provided"一步。
2. **Java 8 语法约束**：gtsp-parent `-source 8`，生成代码禁用 `var`/匿名类钻石 `<>`/`List.of` 等。
3. **`failOnEmptyShould` 默认 true**：后缀规则在无匹配类的项目会红——每条命名规则须 `.allowEmptyShould(true)`。
4. 实际包名 ≠ 规范（`interfaces` 非 `adapter`，`infrastructure.domain.dto` 非标准 client）——再次印证 `layer_aliases` 必须是生成器一等输入。

**2b go/no-go 判据数据**（判据：手写成本 < 半天且项目数 < 4 时放弃生成器）：手写一份验证过的规则集实际耗时 ~0.5h（含排错）；已索引 GTSP 项目 12 个 ≥ 4。**判据不满足放弃条件 → 生成器路线 GO**（价值在于规则演进时 12 个项目同步再生成的规模效应，而非首写成本）。

Spike 产物存档：`skills/arch-guard/templates/archunit-spike/`（ArchitectureGuardTest.java + archunit.properties，作为 2b 生成器模板基线）。

#### 2b. 生成器：`--mode archunit`


> **2b 状态（2026-08-18，✅ 生成器已落地）**：`--mode archunit [--output <dir>|--verify]` 已实现并测试。
> 验证：生成器单测 15 条（矩阵映射/别名展开/白名单/Java 8 语法守卫/verify 三态）；
> 生成物经 `javac --release 8` + ArchUnit 1.2.1 真实编译零错误（期间抓出 `that()` 子句无
> `doNotHaveNameMatching` 的 API 错误，改用 `DescribedPredicate.not(nameMatching(...))`）；
> 全量 138 测试通过（覆盖率 96.8%），impact-guard 56 测试无回归（其 LayerIdentifier 为独立副本，
> 无共享符号契约）。试点项目双跑对比（Tier 1 ⊆ ArchUnit 违规集归因）归入 Phase 3 门禁切换执行。

**What**：`arch_check.py --mode archunit [--output <dir>]`，从配置生成三类产物（stdout 或 `--output` 目录，**不自动注入目标项目 pom**——pom 变更以输出指引由人执行）：

1. `ArchitectureGuardTest.java`——头部 `// DO NOT EDIT — 由 skills/arch-guard 生成，重跑 --mode archunit 更新`；
2. `archunit.properties`——`freeze.store.default.path=src/test/resources/archguard-store`、`allowStoreCreation=true`；
3. 接入指引（pom 需增 `archunit-junit5` test 依赖 + CI 片段）。

**规则映射表**（生成器唯一依据 = 现有代码化矩阵，不新增规则源）：

| 现状规则 | ArchUnit 生成表达 | 配置/代码源 |
|---|---|---|
| 依赖方向 `_DEPENDENCY_RULES` | `layeredArchitecture().consideringOnlyDependenciesInLayers().layer("domain").definedBy(..domain..).whereLayer(...)...` | `_DEPENDENCY_RULES` + `layer_aliases` |
| 领域层纯净度 | `noClasses().that().resideInAPackage(..domain..).should().dependOnClassesThat(resideInAnyPackage("org.springframework..","org.mybatis..",...))`，白名单排除 `domain_annotation_imports` + JPA 豁免 | `check_domain_purity` 框架包清单 |
| 命名后缀 | 每条规则一行：`classes().that().haveSimpleNameEndingWith("DTO").should().resideInAPackage(..client..)` | `_SUFFIX_RULES` |
| 状态泄漏 | `noClasses().that().resideInAnyPackage(..adapter..,..infrastructure..).should().callCodeUnitWhere(target 名匹配 set/change/update/modify*Status)`（API 以 userguide 为准，spike 确认） | `_STATUS_WRITE_RE` |
| **循环依赖（新增）** | `freeze(slices().matching("<prefix>.(*)..").should().beFreeOfCycles())` | `project_package_prefix` |
| 值对象 setter（升级候选） | 值对象包内 `noClasses().should().haveSetter...` 类条件（API spike 确认；不确定则留 L3） | steering §17 禁止事项 |
| pom.xml 检查 | **不生成**——保留 Python（ArchUnit 无构建文件视角） | `check_maven_modules`/`DOMAIN_PURITY_POM` |
| 状态机治理 | **不生成**——全局启发式，保留 Python | `check_state_machine_governance` |

**双档位生成策略**（关键洞察：完整档模块级违规已被 Maven 编译期拦截，`_MAVEN_DEP_MATRIX` 是静态重复校验；ArchUnit 的增量价值在**模块内包分层**与循环依赖）：

- **完整档**：只在 `-start` 模块生成一份聚合测试类（start 传递依赖全部模块，单 classpath 全覆盖），分析模块内包分层 + 全局循环依赖；
- **轻量档**：在 `-service` 模块生成包分层测试类。

**生成物防漂移**：`--mode archunit --verify`——重生成内容与目标项目已提交的生成物 diff，不一致 exit 1（配置改了没重生成 → CI 拦截）。

**验证**：生成器单测（配置矩阵 → 生成代码断言）；试点项目双跑对比——Tier 1 违规集 ⊆ ArchUnit 违规集，偏差逐条归因（ArchUnit 误报→调规则；Tier 1 漏报→记为修复证据）；`--verify` 对手工篡改的生成物报 exit 1。

> **Phase 3 试点状态（2026-08-18，✅ 三项目接入完成）**：cont-task / gtsp-wop-gateway / gtsp-wop-service(core) 全部
> 27 规则绿 + freeze store 建立存量基线（45/84/754 条）。双跑对比结论：Tier 1 每条违规在 ArchUnit 均有对应且
> 证据更细（field/method/constructor 级），Tier 1 ⊆ ArchUnit 成立。试点新增三条生成器修正（已进 v2 产物与单测）：
> ① `ImportOption.DoNotIncludeTests` 排除测试类（gateway 教训：测试类在 domain 包下调用 infrastructure 被误判）；
> ② 按项目实际层裁剪 `layeredArchitecture` 定义（cont-task 教训：两层项目生成五层规则产生 "Layer X is empty" 假违规）；
> ③ 多模块项目 `.arch-guard.json` 在仓库根时需 `--config` 显式指定。试点另发现两项目 HEAD 自带坏测试
> （gateway `RateLimitFilterTest` int→Long、wop `PlfBizLineExchangeServiceTest` 缺符号——依赖版本漂移），
> 验证时临时移出已复原，属项目自身债务与本技能无关。

**反模式**：不硬编码包名（impact-guard 实测教训：GTSP 实际 Controller 在 `interfaces.facade.*`，规范写 `adapter.web`——`layer_aliases` 必须进生成器）；不改 `JavaScanner`/`LayerIdentifier`/`SUFFIX_TYPE_MAP` 签名（impact-guard 复用契约）；生成器不解析 Java 源码（只消费配置与内置矩阵）。

### Phase 3：门禁切换与文档（预估 1~2 天）

**What**：

1. CI 双门禁模板（SKILL.md 更新）：`python3 arch_check.py <root> --frozen --strict`（pom/配置/兜底）+ `mvn test -Dtest=ArchitectureGuardTest`（字节码规则，CI 侧 `-Darchunit.freeze.store.default.allowStoreCreation=false` 防误建基线）。
2. README/SKILL.md 重写为三层架构表（§3）；`.arch-guard.json` 配置表补充生成器相关项。
3. badcase：新增"生成器配置→规则"映射场景。

**验证**：在试点项目仓库走一遍 MR 流程（新增违规 → ArchUnit 测试红 → 修复 → 绿 → 基线自动收缩）；本仓库 `pytest` + `badcase_runner.py` 全绿。


**反模式**：不删 Tier 1 的 Java 检查（未迁移项目兜底，退役另立项）；不改退出码语义（0/1/2 全链路兼容）。

### Phase 4：LLM 语义规则正式化（持续）

**What**：SKILL.md"需人工补充"表逐项转化：

| 语义规则 | 去向 |
|---|---|
| 值对象 setter | 2b 若 API 可表达 → L1；否则 badcase |
| 聚合设计合理性（大小/边界） | L3 badcase 场景（输入含多聚合 domain，expected 要求指出边界问题） |
| 应用服务贫血/含业务逻辑 | L3 badcase 场景 |
| 跨域应事件解耦而非 API 调用 | L3 badcase 场景 + Tier 2 Cypher 辅助证据 |
| Controller 直调 Mapper | ArchUnit 可表达（`noClasses().that().resideInAPackage(..adapter..).should().dependOnClassesThat().resideInAPackage(..mapper..)`）→ L1 |

**验证**：badcase 场景 4 → ≥8，`badcase_runner.py` 全绿；每条 L3 场景有 expected.md 判定标准。

---

## 5. 基线迁移策略

`.arch-guard-baseline.json`（sha1 指纹）与 ArchUnit ViolationStore（class+dependency 文本行）**格式语义不同，不写转换器**：

- 迁移项目：首次 `allowStoreCreation=true` 冻结，重新对齐现状（一次性重置债务线，属显式决策）；
- 未迁移项目：旧基线机制随 Tier 1 兜底继续存活；
- 旧基线退役：全部目标项目迁移完成后另立小改动删除。

---

## 6. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| 1 | ArchUnit 与 gtsp-parent/JDK 兼容性未知 | 2a spike 前置，不满足即止损（Tier 1 + Phase 0/1 为可接受终态） |
| 2 | 规范包名与实际偏差（`interfaces.facade` ≠ `adapter.web`，impact-guard 实测） | 生成器只消费 `layer_aliases` + 配置，禁止硬编码 |
| 3 | 规则双源漂移（steering ↔ `_DEPENDENCY_RULES` ↔ 生成物） | 单一源 = 代码化矩阵；`--verify` 拦截生成物漂移；CONTRIBUTING 注明 steering 变更须同步矩阵 |
| 4 | 生成物被目标项目手改 | DO NOT EDIT 头 + `--verify` CI 校验 |
| 5 | impact-guard 复用契约破坏 | Phase 2 只增 mode 不改共享组件签名；合入前跑 impact-guard 测试 |
| 6 | 大项目 `mvn test` 时长增加 | 测试类独立可拆；必要时 `-Parch-guard` profile 按需触发；spike 实测量化 |
| 7 | 团队对 ArchUnit 生成规则的信任成本 | 双跑对比报告作为采纳证据；迁移期 Tier 1 结果保留展示 |

---

## 7. 里程碑与验收

| 里程碑 | 内容 | 版本建议 |
|---|---|---|
| M1 | Phase 0 + 1（盲区修复 + ratchet） | 0.4.0 |
| M2 | Phase 2 + 3（生成器 + 门禁切换 + 1 个试点项目迁移） | 0.5.0 |
| M3 | Phase 4 首批 badcase（≥8 场景）+ 第 2~3 个项目推广 | 0.6.x |

**总验收**：试点项目上，架构违规的发现证据 = 字节码级（import 正则盲区归零）、基线只缩不涨、GTSP 独有规则（pom 纯净度/跨域 client/状态机）无一丢失、LLM 语义规则有回归闭环。
