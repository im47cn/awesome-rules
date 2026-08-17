---
title: CR 检查清单与公共依赖
scenario: CR 清单/公共依赖速查
---

# CR 检查清单与公共依赖

> **适用场景**：Code Review 与提交前自查、公共依赖选型。

## 1. CR 合规检查清单

分级标注与仓库总则一致：【强制】项不通过则不予合并；【推荐】项应尽可能遵守，未遵守需在 CR 中说明理由。

**模块结构**

- [ ]【强制】完整档：COLA 6 模块（`gtsp-{域}-{adapter/client/start/app/domain/infrastructure}`），依赖矩阵合规（`client`/`domain` 零内部依赖，pom.xml 编译期校验）
- [ ]【强制】轻量档：api+service 两模块，service 内包分层（`adapter/application/domain/infrastructure` 作为包），靠 arch-guard 脚本守护依赖方向
- [ ]【强制】启动类在 `-start` 模块（完整档）或 `com.acme` 根包（轻量档），命名 `{Domain}Application`，标注 `@EnableCustomConfig`
- [ ]【强制】依赖方向 `adapter → app → domain ← infrastructure`
- [ ]【强制】Controller 不直接调用 Mapper 或 Repository

**命名与方法**

- [ ]【强制】领域类（实体/值对象）**无后缀**，用业务名；其他类后缀与职责对应（Inter/Controller/AppService/Repository/RepositoryImpl/Mapper/PO/DTO/Command/Query/ExtPt/Ext）
- [ ]【强制】adapter 包用 `web`（非 `facade`）
- [ ]【强制】方法命名分层：应用层用业务语义或 `create/remove/modify/get/page`，基础设施层用 `insert/update/delete/queryPage/queryList/queryDetail`
- [ ]【强制】常量类使用 `final class` + private 构造方法，不使用 `interface`
- [ ]【强制】依赖注入使用 `@Resource`，不使用 `@Autowired`

**CQRS / 状态机 / 扩展点**

- [ ]【强制】写操作经 Domain（AppService → DomainService → Repository），禁止绕过 Domain 直接调 Mapper
- [ ]【强制】读操作可绕过 Domain 直接查 Mapper（CQRS），事务边界仍在 AppService
- [ ]【推荐】复杂场景使用 `CmdExe`/`QryExe` 执行器
- [ ]【强制】核心域对象状态机无死状态 / 不可达 / 缺失流转 / 状态泄漏
- [ ]【强制】多渠道/多租户差异化用扩展点（ExtPt/Ext），非 if-else

**API 与 Controller**

- [ ]【强制】Feign 接口（client 模块）声明 url/name/contextId/path 四属性，方法路径 `/v1/{resource}/{action}`
- [ ]【强制】action 动词统一 `create`/`query`/`update`/`remove`（与 Open API 一致，便于网关直接对外）
- [ ]【强制】版本策略：仅破坏性变更递增 version，同时最多 2 个版本
- [ ]【强制】写操作参数标注 `@Valid` 或 `@Validated`
- [ ]【强制】Controller 使用 `@PostMapping`/`@GetMapping`，不使用 `@RequestMapping(method=...)`
- [ ]【强制】Controller 返回 `ResultMode<T>`，Feign 返回 `ResponseMessage<T>`，Controller 中无 try-catch

**数据库与实体**

- [ ]【强制】PO 类禁止实现 `Serializable`，标注 `@TableName`，用 `@Getter`+`@Setter`+`@Accessors(chain=true)`+`@ToString`（非 `@Data`）
- [ ]【强制】非数据库字段标注 `@TableField(exist = false)`
- [ ]【强制】PO 无日期格式化注解，DTO 用 `@JsonFormat` 输出 ISO 8601 带时区（`timezone = "+08:00"`，与 openapi-standards 一致）
- [ ]【强制】Mapper 继承 `BaseMapper<PO>`，分页拦截器配置 `DbType.MYSQL`
- [ ]【强制】Mapper XML 在 `resources/mapper/` 下，namespace 与接口全限定名一致，查询带 `del_flag = 0`

**日志与异常**

- [ ]【强制】使用 `@Slf4j` + Log4j2，不使用 `System.out`
- [ ]【强制】日志使用占位符 `{}`，异常日志含完整堆栈，敏感信息脱敏
- [ ]【强制】日志格式含 traceId / X-WLYD-TRACE-ID / X-WLYD-SPAN-ID（链路追踪默认配置）
- [ ]【强制】异常继承 `BaseException`，含 `ErrorType errorType` 字段，不直接抛 `RuntimeException`
- [ ]【强制】`ExceptionEnum` 含 desc/type/solution 三字段，枚举常量名作错误码，命名 `{系统}_{模块}_{序号}`
- [ ]【强制】全局异常处理器按 errorType 定日志级别（SYS/EXT→error，DAT/BIZ→warn，未知→error 含堆栈）

**配置与注释**

- [ ]【强制】`context-path` 与 `application.name` 一致，`wlyd.trace.enabled: true`
- [ ]【强制】公共依赖版本由父 POM 管理，敏感信息不硬编码
- [ ]【推荐】类注释含 `@author` 和 `@date`（格式 yyyy-MM-dd）
- [ ]【推荐】PO/DTO 字段有 Javadoc 注释，枚举字段说明码值映射
- [ ]【强制】废弃方法/字段标注 `@Deprecated` 并说明替代方案

## 2. 公共依赖速查

| 场景 | 依赖 | 说明 |
| --- | --- | --- |
| 公共框架 | `fss-common` | ResultMode、BaseException、PagingInfo、ErrorType |
| ORM | `mybatis-plus-boot-starter` | BaseMapper、Wrappers、PaginationInnerInterceptor |
| 连接池 | `druid-spring-boot-starter` | 数据库连接池 |
| 链路追踪 | `wlyd-trace-context-spring-boot-starter` | traceId 注入、Log4j2 默认配置 |
| 消息队列 | `rocketmq-v5-client-spring-boot-starter` | RocketMQ |
| 定时任务 | `xxl-job-core` | XXL-JOB |
| 监控 | `spring-boot-starter-actuator` | health/metrics/prometheus |
| 代码简化 | `lombok` | @Getter/@Setter、@Slf4j、@Accessors |
