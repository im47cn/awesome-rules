---
title: 测试规范
scenario: 编写/审查测试代码
inclusion: always
---

# 测试规范

## 分类定义与边界判定

| 分类 | 定义 | 性能要求 |
| --- | --- | --- |
| 单元测试 | 不启动容器，所有外部依赖 Mock | < 100ms/用例 |
| 集成测试 | 启动轻量容器（H2/内存数据库），含 `@SpringBootTest`、`@DataJpaTest`、`@WebMvcTest` | < 500ms/用例 |
| E2E 测试 | 启动完整应用，模拟真实用户操作 | < 30s/用例 |

> 关键边界：使用 H2 但启动 Spring Context 的测试仍属集成测试，不适用单元测试性能指标。

## 覆盖率阈值

- Java 实现代码【强制】：以 JaCoCo 执行全量（存量+新增）行/分支覆盖率门禁 ≥ 98%；统计前先按「覆盖率统计范围与排除实践」剔除生成代码——lombok 生成成员、MapStruct `*ConverterImpl`（如 `WopGatewayAclConverterImpl`）等不进分母，98% 只约束手写实现代码；增量 `diff-cover --compare-branch` 仅作为补充检查（变更行 java ≥98% / 非 Java ≥90），不替代全量门槛
- 非 Java 新增代码：分支/行覆盖率 ≥ 90%
- 非 Java 核心业务逻辑：≥ 98%

> 理由：剔除生成代码后剩余均为手写实现逻辑，98% 意味着未覆盖部分至多约为总量的 2%，且须由 CR 逐条解释，不得整块豁免兜底。

## 测试范围

- 多份工件必须同步的配置（如分片 yml 区间端点、datetime 界限、DDL 预建表集合）应纳入测试范围：编写一致性守护测试解析各端并断言对齐，任一漂移即 CI 失败，把人工多处同步的漂移风险固化为防回归护栏；注意此类守护只护「对齐」不护「过期」，时间上界仍需另行提前扩界。
- 配置一致性守护测试：当同一约束散落在多处配置（如分片区间 yml、datetime 上下界限、DDL 预建表清单）时，应编写守护测试解析各方配置并断言一致，任一方漂移即测试失败，把配置漂移类风险固化为防回归护栏（参考 AccessLogShardingConsistencyTest 三方对齐模式）。

- 必须测：Service 业务逻辑、Util 工具方法、复杂算法、状态机/策略模式、异常处理器、网关过滤器链等正确性关键路径
- 可选测：Controller（已有集成测试覆盖时）、简单 CRUD（无业务逻辑时）
- 禁止测：Getter/Setter、纯配置类、纯 DTO/Entity（不含逻辑方法）、自动生成代码

## 覆盖率统计范围与排除实践

> 原则：排除是"让度量对准真实风险"，不是刷分工具。每次排除须有可陈述理由，排除清单纳入 CR 审查。

### 不计入覆盖率的代码（三类）

| 类别 | 内容 | 排除机制 |
| --- | --- | --- |
| **生成代码** | Lombok 生成成员；MapStruct Impl（`*ConverterImpl`，如 `WopGatewayAclConverterImpl`）；代码生成器产物（PO/Mapper）；WSDL/OpenAPI 客户端桩 | 注解驱动：`lombok.config` 开 `addLombokGeneratedAnnotation`（JaCoCo 0.8.2+ 对任何名为 `Generated` 的注解自动免计）；门禁校验 JaCoCo 插件版本 ≥ 0.8.2，随类走零误伤 |
| **声明式/装配代码** | `@Configuration` Bean 装配；`@ConfigurationProperties` 绑定类；Application 主类；常量类；Feign 接口/标记接口（无方法体本就不计） | pom jacoco `excludes`（按包/类名模式），如 `**/*Application*`、`**/config/**` |
| **边界壳（逐案定夺）** | MQ Listener/定时任务纯转发薄壳；Controller 薄壳 | 优先测而非排除（`@WebMvcTest`/消息驱动测试）；确不测的用 diff-cover `--exclude` 豁免门禁但保留报告真实 |

### 边界判定红线

- 壳含 try-catch/重试/幂等/异常映射逻辑 → **必须测**，不得以"壳"名义排除
- 按包排除会连带包内真实逻辑 → 排除粒度最小化，宁可类级不包级
- 枚举带行为方法（如 `ofCode` 反查）→ 测；纯码值枚举 → 随 lombok 免计

### 决策顺序

1. 代码是生成的？→ 用注解机制（Generated），一劳永逸
2. 整类无逻辑纯装配？→ pom excludes，模式尽量窄
3. 有逻辑但暂不测？→ diff-cover 豁免 + 显式 TODO 债务标记，还清即移除豁免

### 卫生要求

- excludes 清单季度审计一次，债务清偿即删
- 禁止为提升数字而扩大排除范围；整体覆盖率上升只能是副产品
- lombok.config / pom excludes 变更视同源码变更，走 CR

## CRAP 变更风险度量与门禁

> 定位：CRAP（Change Risk Anti-Patterns，[crap4j FAQ](https://web.archive.org/web/20211020043803/http://www.crap4j.org/faq.html)）度量「改这段代码出事的概率」，不是「代码写得好不好」。复杂度本身不产生风险，**未被测试覆盖的复杂度**才产生风险；覆盖率门禁（≥98%）回答「测了多少」，CRAP 回答「剩余风险压在哪、用哪个杠杆拆」。适用于存量风险评估与测试编写优先级排序。

### 公式与阈值

`CRAP(m) = comp² × (1 − cov)³ + comp`（comp = 方法圈复杂度；cov = covered / (missed + covered) ∈ [0,1]，JaCoCo 显示的百分比如 50% 代入前须转为 0.5）

阈值 **CRAP ≥ 30 需要处理**（crap4j 经典口径），校准直觉：

| 方法覆盖率 | 达到 30 需要的 CC | 含义 |
| --- | --- | --- |
| 0% | CC 5（5²+5=30 恰好达标） | 未测代码只容忍 CC ≤ 4 |
| 50% | CC 12（12²×0.125+12=30 恰好达标） | 覆盖一半即可容忍复杂度翻倍以上 |
| 90% | ≈30 | 三次方已把惩罚压平 |
| 100% | CC 30 | 纯复杂度问题 |

两条直觉线：**cov ≥ 90% 时 CRAP ≈ CC + 噪声；cov ≈ 0% 时 CRAP ≈ CC² + CC**（cov 上升时二次惩罚项按 (1−cov)³ 快速衰减，cov 49% 时系数仅 0.13——gtsp-wop-gateway 2026-09-05 实证：全库 INSTRUCTION 99.38% 覆盖下 ΣCRAP 1431.6 vs ΣCC 1430——覆盖债只贡献 1.6 个风险点，风险几乎全是结构性复杂度而非测试债）。

### 四形态决策规则【强制】

按 comp × cov 两维读数决定动作，禁止对着 CRAP 榜单无差别「补测试」：

| 形态 | 读数 | 动作 |
| --- | --- | --- |
| 复杂但已驯服 | CC 高、cov 高 | CRAP < 30 才可不急；若 ≥ 30 门禁失败仍须整改，高覆盖下通常选重构，测试已是保护网（如 `FieldMappingEngine` ΣCRAP 114 / cov 98.6%） |
| 简单但裸奔 | CC 低、cov 0 | 先问该不该存在：死代码删除，不为它写测试 |
| 又复杂又缺覆盖 | CC 高、cov < 90% | 先补测试（三次方项让覆盖收益最大） |
| 复杂且覆盖够仍居榜首 | CC 高、cov ≥ 95% | 杠杆是重构拆分，补测几乎不动数字 |

- 一句话判据：**CRAP 高且 cov < 90% → 写测试；CRAP 高且 cov ≥ 95% → 拆方法**——整改手段按 cov 定，但无论何种手段，**CRAP ≥ 30 方法计数清零（= 0）是硬性退出条件**（同日实证：`RateLimitFilter.doPre` CC 18 / cov 89.2% → CRAP 18.4，补满覆盖也只降到 18 仍居榜首——该方法的改进杠杆是拆分不是补测）
- 死代码识别三征：cov 0% + CC > 0 + 全仓零调用 → 删除而非补测（同日实证：`AccessLogFilter.truncate` 私有方法 CC 3 / cov 0% / 零调用，删除后风险整体消失——无法变更不存在的代码）

### 度量纪律【强制】

- CRAP 必须基于**绿套件的全新覆盖率产物**计算：红/被跳过的测试虚抬风险，先修绿再度量；红线套件上的 CRAP 是噪声不是信号（同日实证：18 个 NPE 红测试把 `GatewayDispatchAppService` ΣCRAP 从 29.0 虚抬到 38.8、cov 82%；接线修复后 cov 100%、ΣCRAP 回落）
- 方法级口径：comp 取 JaCoCo XML 方法 `COMPLEXITY` missed+covered 之和，cov 取 INSTRUCTION 覆盖率（LINE 兜底）；类级用 ΣCRAP 找风险聚集地，项目级用 **CRAP ≥ 30 方法计数**做门禁指标——平均覆盖率会被大量简单访问器稀释，CRAP 计数不会
- 集成测试不必然降 CRAP：只重走单测已覆盖路径的集成用例对覆盖率零贡献（同日实证：17 个 RealRedis 集成用例全部执行 2.5s，覆盖率逐字节不变）。降 CRAP 的增量来自**故障注入**（畸形 Lua verdict、熔断分支等错误路径），不是「换更真的环境」

### 环境门用例的可见性

- `@EnabledIf` 环境探针默认静默跳过会让整块路径从度量里消失：套件须显式核对 skip 计数与跳过清单，环境门用例是否真实执行要可观测（同日实证：RealRedis 套件默认端点 192.168.0.167:26379 TCP 可连但协议层即断——sentinel 端口陷阱，TCP 通 ≠ 协议通；探针必须验证协议层 PING 而非 TCP 连接成功）
- 环境门集成用例只清理自有 key（按业务前缀删），不得假设独占实例、不得 flush 共享库

### 质量门禁【强制】

- 覆盖率红线已由「覆盖率阈值」定为 Java 全量行/分支 ≥98%；适用项目应在本地 pre-push/CI 门禁脚本中落地第二道门禁 **CRAP ≥ 30 方法计数 = 0**（解析 JaCoCo XML 方法级 COMPLEXITY/INSTRUCTION，口径同「度量纪律」；本规范仓库为治理文档，不承载 Java 构建执行）——覆盖率约束总量、CRAP 计数定位单点：单方法覆盖率跌破越线水位（如 CC 12 的方法 cov <50%）时总量门禁可能未破，但该方法的变更风险已越线，CRAP 计数是更早的单点报警器（同日实证：gtsp-wop-gateway 144 类 / 607 方法按此口径通过，榜首 18.4）
- 常量类命中门禁时按本规范「覆盖率统计范围与排除实践」的声明式代码通道排除，不为常量写测试
- 风险红测试（已知缺陷待修复、带原因标注的 `@Disabled`）不改变绿套件口径，也不豁免对应修复——与「禁止用 `@Disabled` 临时绕过失败」的边界在于：必须注明缺陷单与修复计划，且不参与覆盖率/CRAP 度量基线

## Mock 边界

- 进程内全链路验证优先通过组件的公共执行入口驱动真实调用链（如过滤器洋葱链 `filter(exchange, chain)`），不绕过入口手动调用 protected 分段方法（`doPre`/`doPost`）；核心业务逻辑（加解密、验签等）零 mock，仅替身最外层边界（如下游服务）
- 第三方流式链式 API（如 hutool `HttpRequest.header(...)` 链）用 `RETURNS_SELF` 打桩可能失效返回 null，NPE 会落入被测代码的 catch 分支造成错误误判；流式链应逐环显式打桩（如 `when(req.header(any(), any())).thenReturn(req)`），个别用例未消费全部桩时用 `@MockitoSettings(strictness = LENIENT)` 或 `lenient()` 抑制 strict stubs 报错，而非删桩。

- 对已打桩为 `thenThrow` 的 mock 重新打桩时，禁止再用 `when(mock.method()).thenReturn(...)` 语法——`when()` 内的方法调用会先触发旧桩直接抛异常，新桩永远建立不起来；必须改用 `doReturn(...).when(mock).method()` 形式（`doThrow`/`doAnswer` 同理）。
- Mock 响应的形状必须对齐消费端适配逻辑的隐式契约（如根节点包装、字段映射、成功码判定），并以最终消费效果（渲染结果、路由注册、下游调用）验证 mock 有效性；不能只验证 mock 接口自身返回 200 且结构自洽，否则数据会被适配层静默丢弃而表现为「页面为空/路由缺失」

- Mock 系统边界：Repository/Dao、HTTP 客户端、MQ、文件系统、外部 SDK
- 禁止 Mock 领域对象：Entity、DTO、VO、值对象
- 禁止 Spy 被测类：不对被测对象使用 `@SpyBean` / `spyOn` 部分替换

## 测试数据
- 构造用于统计断言（相关系数、标准差等）的测试数据时，禁止使用零方差序列（如等差序列的逐期变化为常数）：统计量分母为 0 会返回 NaN，断言失真且易被误判为实现缺陷；夹具数据应先保证有实际波动

- 允许：常量 fixture（用户名、邮箱前缀等标识性数据）
- 禁止：动态值（时间、随机 ID、自增主键）硬编码到断言中——用相对时间或 `assertNotNull()`
- 集成测试：必须 `@Transactional` + `@Rollback`，每个用例自动回滚

## 前端
- vitest 必须在前端工程目录内运行：`test.environment`（jsdom）等配置就近生效于 `vite.config.ts`，从仓库根/父目录运行会静默丢失 DOM 环境，造成整批用例 `document is not defined` 假失败；受 cwd 不稳定限制时用 `npm --prefix <前端目录> test` 显式定位

- 定位方式：统一使用 `data-testid`，禁止 CSS 选择器或 class
- Mock：Mock API 调用，不 Mock 组件内部方法
- 测试行为而非实现：验证可观测结果（返回值、事件），不验证内部方法调用次数

## 参数化测试【推荐】

`should{期望行为}_when{条件}` 命名天然适合参数化，对同一逻辑的多组输入/预期值使用 `@ParameterizedTest` / `@CsvSource` 或 `it.each`，禁止复制粘贴测试方法。

## 失败处理

| 级别 | 策略 |
| --- | --- |
| 单元测试失败 | 立即修复，不允许跳过 |
| 集成测试失败 | 24 小时内修复或回滚 |
| E2E 测试失败 | 先排除环境问题，非环境问题按集成测试处理 |
- 脚本/组件改名时全量 grep 引用面（LaunchAgent plist、CI workflow、cron、文档示例）并逐处更新：调度器指向旧名是 exit 127 静默失败，无告警无产出，只能靠产物缺失（如 metrics 文件不增长）间接发现（2026-08 实证：日回归调度器死了 3 天才被盘点抓出）。改名 PR 应附引用面清理清单。
- 构建信号以 Maven 实际编译/测试为准：LSP 在未启用 Lombok 注解处理器时对 builder/getter/setter 等生成成员的报错属于误报，不作为失败依据
- 全量门禁失败时，先判定失败项属于本次变更还是 HEAD 既有（对 HEAD 版本重跑或核对本次未触碰的路径），归因后再决定修复策略，不默认揽责也不默认跳过
- 既有 lint 告警按仓内惯例处置（如 shellcheck 逐条 `# shellcheck disable=SCxxxx` 指令并注明理由——字面 markdown 反引号属刻意单引号防展开），修复后复跑全量验证，不因"非本次引入"而留红
- 全量门禁失败时，先判定失败项属于本次变更还是 HEAD 既有（对 HEAD 版本重跑或核对本次未触碰的路径），归因后再决定修复策略，不默认揽责也不默认跳过
- 既有 lint 告警按仓内惯例处置（如 shellcheck 逐条 `# shellcheck disable=SCxxxx` 指令并注明理由——字面 markdown 反引号属刻意单引号防展开），修复后复跑全量验证，不因"非本次引入"而留红
- 新增用例后核对通过数与编写的测试函数数一致：编辑事故可能静默吞掉整个测试函数（套件全绿但计数缩水是唯一暴露信号）
- 门禁/CI 间歇性失败先定性再处置：单测隔离复现 + 在 main 上同跑判定是否本分支引入 → 全量套件复现 → 修复后满载压力连跑验证；定性为与变更无关的时序 flake 才可重试推送，禁止盲目重试掩盖根因

## CI/CD 门禁
- 验证门禁/检查器组件自身的行为时，正道与负道用例缺一不可：正道证明放行链路可走通，负道证明拒绝链路真实生效；仅单侧通过不构成门禁正确性的证据。

- 协议适配、渠道移植类迁移项目，应建设录制-回放-比对测试设施：golden 样本按「渠道×事件」版本化管理，作为迁移每批次准入门禁；样本比对不一致的批次不得进入灰度。
- 变更行覆盖率的本地自验须与门禁同口径：直接复用门禁工具（如 diff-cover）及其产物，不自写脚本旁路核算，避免实现差异（如 lcov `DA:行号,命中数` 未按逗号拆分）产出 100% 通过的假象

- 本地 pre-commit/pre-push 门禁的 lint 与测试范围、口径必须与 CI 完全同口径或更宽，并随 CI 演进同步维护；任一侧范围缺失都会产生「本地绿、CI 红」的假信号，问题要到 CI 才暴露、浪费一轮流水线
- 协议适配、渠道移植类迁移项目，应建设录制-回放-比对测试设施：golden 样本按「渠道×事件」版本化管理，作为迁移每批次准入门禁；样本比对不一致的批次不得进入灰度。

- 基于覆盖率产物的增量门禁（diff-cover 等）复用本地 lcov/xml 文件：补充测试后必须重新生成覆盖率产物再提交，陈旧产物会把已覆盖代码误判为缺失导致门禁误拦
- lint/工具自动改写（Sourcery、docstring 回填等）提交后复查两件事：① 覆盖率是否无解释下降——改写可能落入度量工具盲区（wop-python-sdk 2026-08-31：coverage.py 对 walrus+yield 生成器的 break 弧不记录，Sourcery 改写致 99.78%，最小探针隔离复现后回退 4 行恢复 100%）；② 行号锚定的配置（覆盖率白名单、报告定位）是否漂移——同日 docstring 插入使 2 条白名单行号漂移，失配告警当场拦截；结构性辅助提交与锚定配置不得盲过

- 全部测试必须通过
- 覆盖率门禁与「覆盖率阈值」同口径：Java 以 JaCoCo 报告级计数执行全量（存量+新增）行/分支 ≥ 98% 红线（剔除生成代码后），增量 diff-cover 变更行 java ≥ 98% / 非 Java ≥ 90% 为补充检查；非 Java 核心业务 ≥ 98% 由 CR 把关
- 测试总耗时不超过最近 main 分支全量运行的 120%

## 变异测试纪律

- 变异数字本身不是证据：击杀率达标后须抽样手动复放（注入变异 → 测试红 → 还原 → md5 校验闭环）确认击杀真实；`mvn -q` 下 Maven 增量编译可能不重编改动的 main 类，变异 class 未生效会产出「测试全绿」假象——复放前必须 touch 源文件并确认 `Compiling … source files` 日志行，否则击杀证据无效（2026-09-01 实证：unbindApi BooleanTrueReturn 补杀一度被误判存活）
- 存活变异体逐条归因：补杀、或附等价论证入白名单（论证随白名单入库）；不为「全灭」数字编写断言非行为的测试
- flaky 变异体不追杀：静态状态/ThreadLocal/测试顺序敏感类单次运行存活属并行调度波动，复跑 2~3 次确认波动后由 mutationThreshold 吸收（阈值取最低观测分 −1.5pt）
- BooleanTrueReturn 类变异唯一杀法：stub 领域方法返回 false 并用 `assertFalse` 断言；`assertTrue` 对 return true 变异无判别力，补测前先核对断言极性
- 变异注入按文本偏移定位时须核验切点落在真实代码上：字符偏移错切多字节边界可能把变异体落进中文注释——产出假存活与假击杀并存的双假象，抽样复放样本可当场暴露（wop-python-sdk 2026-08-29 实证：98.05% 击杀率达标蒙混两轮）
- 击杀/存活结论的复放验证集必须覆盖此后新增的测试文件：回退到旧测试集复跑会缺新用例、复现旧结论（wop-python-sdk 2026-08-29 教训：第二轮复验因回退测试集缺新文件重演出第一轮错误结论）

## 自建关卡脚本的反作弊要求

- 用 `re.sub` 写回 JSON/代码产物时 replacement 必须走 `lambda m: s` 形式：re.sub 的 replacement 字符串层会解释 `\n`、`\g<1>` 等转义序列，`json.dumps` 产物里的 `\n` 两字符序列会被改写成裸换行直接破坏 JSON 合法性（2026-09 提案编辑事故实证，改 lambda 闭包后消失）。
- mutations 注入运行期间不得并发执行其他门禁/检查：变异体临时落盘会污染并发进程读到的工作区视图（2026-08-28 实证：gauntlet 并发跑出 ddl_check.py 假红），须等 mutations 结束且确认变异全部恢复后串行重验

- **ast 解析的 SyntaxWarning 泄漏**：用 `ast.parse` 扫描 `.py` 的静态门须局部抑制 `SyntaxWarning`（被扫文件 docstring 的无效转义会泄成层输出噪音）；`SyntaxError` 仍正常上抛走 rc=2，不弱化 fail-closed。
- 负控制的输出断言必须在夹具落盘并重跑检查器之后抓取：若 grep 的是夹具创建前的旧输出文件，断言必然落空而成空断言假绿，负控制自身失去判别力

- `set -e` 脚本里 `var=$(cmd)` 赋值会继承命令退出码：grep 无命中 rc=1 即静默杀掉当前函数（门禁层无声退出，形同放行）；当判定基于输出内容而非 rc 时，须显式中和退出码（如 `_hits=$(... || true)`）
- 门禁/检查脚本的仓库扫描面用 `git ls-files`（tracked 面）枚举，禁止手工维护排除目录清单或顶层 `glob("*.sh")` 式枚举：手工清单与 .gitignore 脱节会把 gitignored 运行时产物当仓库内容扫出假阳性（曾炸穿 pre-push 门禁），顶层 glob 导致新增深层脚本从未入门；确需排除 tracked 的 vendored 内容时显式列出并在注释注明理由；输入目录非 git 仓库时 fail-closed 拒判，不得降级放行

- 新门禁脚本交付验收除单测全绿外，须加一道 retrospective 复验：用促使其诞生的真实事故按当时事实重演跑门，门必须红并逐一点名当时靠人眼才发现的漏网文件（owner_check 落地即以此验收，--base 复现 4 条零派发改动）
- **ast 解析的 SyntaxWarning 泄漏**：用 `ast.parse` 扫描 `.py` 的静态门须局部抑制 `SyntaxWarning`（被扫文件 docstring 的无效转义会泄成层输出噪音）；`SyntaxError` 仍正常上抛走 rc=2，不弱化 fail-closed。

> 适用：自建门禁/检查脚本（变异测试 harness、grep 扫描、覆盖率门禁包装脚本、guard 检查脚本）。
> 原则：一个只会放行的检查器不是门禁——每个检查器必须先证明自己**会失败**，才配拦截别人。

### 负控制【强制】
- 缺陷修复附带的回归测试应做拦截力反向验证：先在未修复基线代码上运行新测试确认会失败（红），再在修复后运行确认通过（绿）；只验证过绿、未验证过红的测试不能作为修复拦截力证据

- 检查器上线前必须喂**已知坏输入**并断言其退出码非零；仅验证"好输入能通过"不构成证明
- 变异 harness 必须内置负控制对：一个必被击杀的变异 + 一个**严格等价**的变异，harness 对二者必须给出不同判定；等价性须可论证（如无副作用操作的交换律），"当前测试下等价"不合格——未来某测试 pin 住该行为时会误报
- 碰撞类风险（缓存复用、字节码继承）用**确定性构造**复现（固定 mtime 等固定输入使碰撞必然发生），不得依赖"碰巧同秒"的概率性触发

### 测试密封性（git 环境隔离）【强制】

- 凡测试/门禁脚本调用 `git`，所在套件 conftest 必须在 **import 期**从 `os.environ` 剥离 `GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE`、`GIT_OBJECT_DIRECTORY`、`GIT_ALTERNATE_OBJECT_DIRECTORIES`、`GIT_COMMON_DIR`、`GIT_NAMESPACE`——显式环境变量优先于 cwd 发现，hook（lefthook pre-push 等）注入的 `GIT_DIR` 会把 `cwd=tmp_path` 的 `git init/add/commit` 劫持到注入仓（2026-08-22 事故：真仓被改写、389 文件删除）。import 期最早且确定，先于任何测试执行；不建共享库，各 conftest 重复几行可接受
- 入库时必须有**负控制回归测试**：以牺牲仓注入 `GIT_DIR` 跑真实套件代码路径，断言牺牲仓 `rev-list --all --count == 0` 且真仓 `status --porcelain` 前后不变（范式见 `scripts/tests/test_hermetic_git.py`）。注意 `GIT_DIR` 须指向非裸 gitdir——裸仓只触发 fatal 假红，演示不了静默劫持
- 新增含 git 调用的测试须同步登记到负控制用例表；CI/hook 链路验证密封的判定证据是 `env GIT_DIR=<牺牲仓> bash scripts/run_tests.sh` 全绿且牺牲仓零对象

### 进程组信号的平台语义（macOS 僵尸窗口）【强制】

> 适用：任何调用 `os.killpg` / `kill -pgid` / 探活信号（sig=0）的测试与门禁脚本（变异 harness 杀组、超时兜底等）。
> 背景：2026-08-24 PR #36——孙进程被 SIGKILL 后变僵尸、由 launchd 异步收尸，窗口内 macOS XNU 对含僵尸的进程组发信号（含 sig=0 探活）报 `EPERM` 而非 `ESRCH`，同 UID 亦然；Linux 上僵尸不触发此差异。

- **杀组路径**：`killpg(SIGKILL)` 的 except 须同时容忍 `(ProcessLookupError, PermissionError)`——僵尸无需再杀（SIGKILL 对僵尸是 no-op），未捕获的 `EPERM` 会炸掉调用方而非走"超时=无效运行"语义
- **探活断言**：禁止 `pytest.raises(ProcessLookupError)` 单发判定；须带 deadline 轮询等组消失——`EPERM` = 组内仅剩待-reap 僵尸（同 UID 下真活进程不可能 `EPERM`）复探等收尸，`ESRCH` = 组彻底消失；探活成功（rc=0）仅表示信号调用成功、组仍有成员（Linux 上未收尸僵尸同样探活成功），不得据此断言真活成员，需区分真活/僵尸时用显式子进程状态（waitpid/ps）判定，组未在 deadline 内消失才判失败
- **时序窗口 mock 化**：真实僵尸窗口依赖 launchd 收尸时序无法稳定复现，规格须以确定性 mock 锁定（`EPERM→…→ESRCH` 序列通过 + 探活持续成功超时失败），范式见 `.factory/tests/test_mutations_run.py::_assert_group_dead`
- **机器执行层**：`tools/check_killpg_strict.py`（gauntlet 层 `lint-killpg-strict`，扫描面 = tracked *.py）静态拦截 K1（`os.killpg` 缺 EPERM 容忍）与 K2（`raises(ProcessLookupError)` 单发探活）；负控制 NC8 见 `tools/test_gauntlet_checks.sh`

### 泄漏断言的 tempdir 隔离【强制】

> 适用：任何对临时目录做枚举/差集断言的测试（泄漏检测、产物清点、after-before 差集等）。
> 背景：PR #137——mktemp 泄漏断言对共享系统 tempdir glob 同模板文件，套件外进程瞬时写入同模板即随机打破差集（pre-push 闸两次 flake，隔离重跑绿证实环境性）；该未隔离形态已扩散至 8 个下游仓。

- **注入而非枚举**：测试不得观测系统共享 tempdir——用 `monkeypatch.setenv("TMPDIR", str(private_tmp))` 把被测面对齐 pytest 私有目录（范式 `.factory/tests/conftest.py::private_tmp`），断言 glob 对注入目录；外部写者不再可见，泄漏检测语义不变
- **禁止硬编码系统目录**：测试代码禁 `gettempdir()`（tempfile 按进程缓存首次取值，TMPDIR 注入只达子进程，测试进程内恒取系统共享目录）与以 `/tmp` 字面量为对象的直接枚举调用（`glob.glob`/裸 `glob`/`x.glob`/`os.listdir`/`Path("/tmp").iterdir()|glob()`）；shell 侧等价要求 = `"${TMPDIR:-/tmp}"` 默认值形态（尊重注入）
- **机器执行层**：`tools/check_tempdir_usage.py`（gauntlet 层 `lint-tempdir-isolation`，扫描面 = tracked 测试文件 test_*.py / conftest.py）静态拦截 R1（`gettempdir(`）与 R2（`/tmp` 字面量枚举调用），检查器损坏恒 rc=2 绝不算通过；负控制 NC17/NC17b/NC17c 见 `tools/test_gauntlet_checks.sh`

### Tripwire：前提失效硬失败【强制】

- 脚本依赖的环境前提（环境变量、缓存清理、工具版本）修复后必须留后验：前提不成立时直接 raise / 退出非零，禁止静默降级继续——静默降级的偏差方向永远是"虚假通过"，不会以红色形式暴露
- 恢复操作用**读回比对**（写回后重读与原件不等即失败），不靠肉眼 diff

### 退出码语义【强制】
- 校验/关卡命令禁止以 `| head`、`| tail` 等管道截断作为命令结尾来判断成败——管道退出码取自最后一个命令，前置命令的真实失败会被吞成 0；需要截断输出时用 `set -o pipefail`、`${PIPESTATUS[0]}`，或先完整执行再单独判断退出码（2026-08-26 MR #168 补丁校验实测踩坑）。

- 只有"检查确实执行且判定失败"（如 pytest rc=1）计为击杀/证据；rc=0 计为通过；**其他退出码一律视为无效运行**——不计通过、不计失败，且使整次结论作废
- 门禁脚本 fail-closed：`set -e`、禁 `|| true` / `2>/dev/null`、启动即清旧产物；grep 退出码显式分支（1=无匹配即通过，0=命中即失败，≥2=检查自身损坏即失败）
- 覆盖率层必须带阈值门（`--cov-fail-under` / `--fail-under`），无阈值的覆盖率层只打印数字、退出码恒为 0，是 fail-open 层

### 等价项处理【推荐】

- 被判定等价的项（等价变异、行为不可区分的重构）须附论证与差分测试证据后豁免；禁止为"全灭"数字编写断言非行为的测试

## 禁止事项
- 禁止用「现状钉住」（断言缺陷现状行为）的测试充当缺陷修复的验收依据：修复前后结果均绿，对缺陷是否存在零判别力。缺陷修复必须交付断言期望行为的红测（修复前红、修复后转绿）；钉住当前正确行为的回归保护用例允许保留，但须与验收红测分层标注，不得混淆。

❌ ❌ - 禁止在启用 `set -o pipefail` 的脚本中把 `grep -m<N>`、`head`、`true` 等提前关读端的命令放在管道非末位——上游收 SIGPIPE(141) 静默炸穿（本仓三犯：`| true` 吞退出码、trap 清理链中止、`grep -m1` SIGPIPE）；取首行/前 N 行用消费全量输入的 `sed -n '1p'` / `sed -n '1,5p'`，吞错误用 `|| true` 而非管道接 `true`
❌ - 断言 checkout 目录名等环境特定值（如 `root.name == "awesome-rules"`）：对 worktree/CI 等任意 checkout 形态是假红源；应断言结构不变量（判定根为入口文件的祖先目录 + 标志资产存在），并配负例断言（非根祖先不含标志资产）防判据退化为永真，以异名目录 worktree 实跑验证。

- ❌ 用 `@Disabled` / `it.skip` 临时绕过失败
- ❌ `Thread.sleep()` / `setTimeout` 等固定等待
- ❌ 测试间共享可变状态（含修改 static 字段）
- ❌ Mock 领域对象
- ❌ 单个测试验证多个不相关功能
- ❌ 硬编码动态值到断言
- ❌ 测试实现细节而非可观测行为
- ❌ 检查器只验证"能通过"，不验证"会失败"（缺负控制）
- ❌ 环境前提失效时静默降级继续（缺 tripwire）
