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

- 新增代码：分支/行覆盖率 ≥ 70%
- 核心业务逻辑：≥ 80%

## 测试范围

- 必须测：Service 业务逻辑、Util 工具方法、复杂算法、状态机/策略模式、异常处理器、网关过滤器链等正确性关键路径
- 可选测：Controller（已有集成测试覆盖时）、简单 CRUD（无业务逻辑时）
- 禁止测：Getter/Setter、纯配置类、纯 DTO/Entity（不含逻辑方法）、自动生成代码

## 覆盖率统计范围与排除实践

> 原则：排除是"让度量对准真实风险"，不是刷分工具。每次排除须有可陈述理由，排除清单纳入 CR 审查。

### 不计入覆盖率的代码（三类）

| 类别 | 内容 | 排除机制 |
| --- | --- | --- |
| **生成代码** | Lombok 生成成员；MapStruct Impl；代码生成器产物（PO/Mapper）；WSDL/OpenAPI 客户端桩 | 注解驱动：`lombok.config` 开 `addLombokGeneratedAnnotation`（JaCoCo 0.8+ 对任何名为 `Generated` 的注解自动免计），随类走零误伤 |
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

## Mock 边界

- Mock 系统边界：Repository/Dao、HTTP 客户端、MQ、文件系统、外部 SDK
- 禁止 Mock 领域对象：Entity、DTO、VO、值对象
- 禁止 Spy 被测类：不对被测对象使用 `@SpyBean` / `spyOn` 部分替换

## 测试数据
- 构造用于统计断言（相关系数、标准差等）的测试数据时，禁止使用零方差序列（如等差序列的逐期变化为常数）：统计量分母为 0 会返回 NaN，断言失真且易被误判为实现缺陷；夹具数据应先保证有实际波动

- 允许：常量 fixture（用户名、邮箱前缀等标识性数据）
- 禁止：动态值（时间、随机 ID、自增主键）硬编码到断言中——用相对时间或 `assertNotNull()`
- 集成测试：必须 `@Transactional` + `@Rollback`，每个用例自动回滚

## 前端

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

## CI/CD 门禁
- 基于覆盖率产物的增量门禁（diff-cover 等）复用本地 lcov/xml 文件：补充测试后必须重新生成覆盖率产物再提交，陈旧产物会把已覆盖代码误判为缺失导致门禁误拦

- 全部测试必须通过
- 新增代码覆盖率 ≥ 70%，核心业务 ≥ 80%
- 测试总耗时不超过最近 main 分支全量运行的 120%

## 自建关卡脚本的反作弊要求

> 适用：自建门禁/检查脚本（变异测试 harness、grep 扫描、覆盖率门禁包装脚本、guard 检查脚本）。
> 原则：一个只会放行的检查器不是门禁——每个检查器必须先证明自己**会失败**，才配拦截别人。

### 负控制【强制】

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
- **探活断言**：禁止 `pytest.raises(ProcessLookupError)` 单发判定；须带 deadline 轮询——`EPERM` = 组内仅剩待-reap 僵尸（同 UID 下真活进程不可能 `EPERM`）复探等收尸，`ESRCH` = 组彻底消失，探活成功（rc=0）= 仍有真活成员，超时才判失败
- **时序窗口 mock 化**：真实僵尸窗口依赖 launchd 收尸时序无法稳定复现，规格须以确定性 mock 锁定（`EPERM→…→ESRCH` 序列通过 + 探活持续成功超时失败），范式见 `.factory/tests/test_mutations_run.py::_assert_group_dead`

### Tripwire：前提失效硬失败【强制】

- 脚本依赖的环境前提（环境变量、缓存清理、工具版本）修复后必须留后验：前提不成立时直接 raise / 退出非零，禁止静默降级继续——静默降级的偏差方向永远是"虚假通过"，不会以红色形式暴露
- 恢复操作用**读回比对**（写回后重读与原件不等即失败），不靠肉眼 diff

### 退出码语义【强制】

- 只有"检查确实执行且判定失败"（如 pytest rc=1）计为击杀/证据；rc=0 计为通过；**其他退出码一律视为无效运行**——不计通过、不计失败，且使整次结论作废
- 门禁脚本 fail-closed：`set -e`、禁 `|| true` / `2>/dev/null`、启动即清旧产物；grep 退出码显式分支（1=无匹配即通过，0=命中即失败，≥2=检查自身损坏即失败）
- 覆盖率层必须带阈值门（`--cov-fail-under` / `--fail-under`），无阈值的覆盖率层只打印数字、退出码恒为 0，是 fail-open 层

### 等价项处理【推荐】

- 被判定等价的项（等价变异、行为不可区分的重构）须附论证与差分测试证据后豁免；禁止为"全灭"数字编写断言非行为的测试

## 禁止事项

- ❌ 用 `@Disabled` / `it.skip` 临时绕过失败
- ❌ `Thread.sleep()` / `setTimeout` 等固定等待
- ❌ 测试间共享可变状态（含修改 static 字段）
- ❌ Mock 领域对象
- ❌ 单个测试验证多个不相关功能
- ❌ 硬编码动态值到断言
- ❌ 测试实现细节而非可观测行为
- ❌ 检查器只验证"能通过"，不验证"会失败"（缺负控制）
- ❌ 环境前提失效时静默降级继续（缺 tripwire）
