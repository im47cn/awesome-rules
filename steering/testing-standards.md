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

## 禁止事项

- ❌ 用 `@Disabled` / `it.skip` 临时绕过失败
- ❌ `Thread.sleep()` / `setTimeout` 等固定等待
- ❌ 测试间共享可变状态（含修改 static 字段）
- ❌ Mock 领域对象
- ❌ 单个测试验证多个不相关功能
- ❌ 硬编码动态值到断言
- ❌ 测试实现细节而非可观测行为
