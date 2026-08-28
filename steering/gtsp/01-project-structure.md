---
title: 架构与分层
scenario: 架构设计/业务域/模块档位/分层/CQRS/状态机/扩展点
---

# 架构与分层

> 适用：业务域划分、模块档位（完整档/轻量档）、分层职责、CQRS/状态机/扩展点、包结构、启动类。命名后缀见 [02](02-naming.md)。

## 1. 二维分解

| 维度 | 含义 | 物理体现 | 示例 |
| --- | --- | --- | --- |
| 垂直（分层） | 技术职责分离 | Maven 模块层后缀/包路径 | `adapter`/`application`/`domain`/`infrastructure` |
| 水平（业务域） | 业务边界隔离 | Maven 模块业务域前缀 | `gtsp-admin-iam`、`gtsp-token-service` |
- 设计新系统的技术方案时，应以目标需求为第一性输入从零推导架构；对存量系统的代码梳理仅作为现状证据与迁移约束输入，不得以「演进统一、不另起炉灶」为由让新架构沿用存量实现的形态与缺陷。ADR 决策记录中须区分「目标驱动的选择」与「兼容存量的妥协」两类理由。
- 设计新系统的技术方案时，应以目标需求为第一性输入从零推导架构；对存量系统的代码梳理仅作为现状证据与迁移约束输入，不得以「演进统一、不另起炉灶」为由让新架构沿用存量实现的形态与缺陷。ADR 决策记录中须区分「目标驱动的选择」与「兼容存量的妥协」两类理由。

## 2. 业务域与子域

**业务域**判定（全部满足）：有独立业务语言（同词异义）、可独立演进（变更不影响他域发版）、有自己的聚合根（不与他域共享写入）。

**子域**（Bounded Context）：父域内业务子领域，共享部分语言；子域间通过**领域事件**或 **client 模块 Inter 接口**解耦，禁止直接 import。子域不独立为 Maven 模块，通过 domain 模块内的包路径体现：

```
gtsp-{域}-domain/.../domain/
├── waybill/                  # 子域：运单（model/entity、repository、service）
├── tracking/                 # 子域：轨迹
└── shared/                   # 域内共享（非跨域）：model/valueobject
```

> **关键区分**：子域间允许互相 import（同在 domain 内）；业务域间禁止互相 import（通过事件或 client 解耦）。子域膨胀到需独立演进/独立团队时，升级为独立业务域。
>
> **领域类无后缀**：domain 层实体、值对象用业务名（`Waybill`/`Address`），不加 `Entity`/`VO` 后缀；其他层保留后缀，见 [02](02-naming.md)。

## 3. 档位选择：完整档 vs 轻量档

**选择原则**：新项目根据服务复杂度与演进预期决定；既有项目以现有结构为准，保持一致，不混用。

## 4. 完整档（6 模块）

每个业务域拆 6 个 Maven 模块，每层一个，编译期强制依赖。

| 模块 | 命名 | 职责 |
| --- | --- | --- |
| adapter | `gtsp-{域}-adapter` | HTTP 入口（Controller/Consumer/Scheduler） |
| client | `gtsp-{域}-client` | 对外契约（Inter/DTO/Command/Query），零内部依赖 |
| start | `gtsp-{域}-start` | 启动引导，独立可部署 |
| app | `gtsp-{域}-app` | 应用层（AppService/Assembler/CmdExe/Handler/Manager） |
| domain | `gtsp-{域}-domain` | 领域层（实体/值对象/DomainService/Repository/ExtPt） |
| infrastructure | `gtsp-{域}-infrastructure` | 基础设施层（PO/Mapper/RepositoryImpl/Ext） |

> 所有服务继承 `com.acme:gtsp-parent:2.0.0-SNAPSHOT`，公共依赖版本在父 POM 统一管理，子模块禁止硬编码版本号。跨域复用的业务模型（DTO/值对象）放 `gtsp-common-model`；公共框架类（`ResponseMessage`/`PagingInfo`/`ResultMode` 等）由 `fss-common` 提供（见 [06](06-exception.md)）。

## 5. 轻量档（api+service 两模块）

用**包分层**代替 Maven 模块分层，不强制模块依赖约束。service 模块内包结构：

```
gtsp-{域}-service/src/main/java/com/acme/{module}/
├── adapter/web/                            # Controller
├── application/{service,executor,assembler,handler,manager}
├── domain/{model/{entity,valueobject}, repository, service}
└── infrastructure/repository/{mapper,po,converter}, exchange

gtsp-{域}-api/src/main/java/com/acme/{module}/
└── client/
```

分层依赖方向同完整档，靠**包约定 + arch-guard 脚本**守护。

## 6. 依赖矩阵与跨域

**完整档模块依赖**（pom.xml 编译期校验，单业务域内部）：

| 模块 → 可依赖 | adapter | client | start | app | domain | infrastructure |
| --- | --- | --- | --- | --- | --- | --- |
| **adapter** | — | ✅ | ❌ | ✅ | ❌ | ❌ |
| **client** | ❌ | — | ❌ | ❌ | ❌ | ❌ |
| **start** | ✅ | ✅ | — | ✅ | ❌ | ✅ |
| **app** | ❌ | ✅ | ❌ | — | ✅ | ✅ |
| **domain** | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| **infrastructure** | ❌ | ✅ | ❌ | ❌ | ✅ | — |

关键约束：`client` 零内部依赖（可单独发布 JAR）；`domain` 不依赖 Spring Boot Starter/MyBatis；`start` 仅启动装配不含业务代码；`app` 通过 `-client` 调用他域，禁止直接依赖他域 `-app`/`-domain`/`-infrastructure`。

**跨域**：禁止跨业务域直接 Maven 依赖（如 `gtsp-admin-iam-domain` 依赖 `gtsp-token-service-domain`）。仅允许三种通信（编译期零耦合）：

| 方式 | 适用 | 耦合度 |
| --- | --- | --- |
| 引入目标域 `-client` 调 `Inter` 接口 | 同步查询 | 仅 API 契约 |
| 订阅目标域领域事件 | 异步通知 | 完全解耦 |
| 复制值对象定义 | DTO 跨域传输 | 零耦合 |

## 7. 分层职责与依赖方向

依赖方向：`adapter → app → domain ← infrastructure`（domain 不依赖任何模块，infrastructure 实现其接口，禁止反向）。Controller 只调 AppService，禁止直接注入 Mapper/Repository。

| 层级 | 模块.包 | 职责 | 禁止 |
| --- | --- | --- | --- |
| Controller | `adapter.web` | HTTP 入口、参数校验、调 AppService | 含业务逻辑、直接调 Mapper |
| AppService | `app.application.service` | 用例编排、事务边界、事件通知 | 含数据库访问（读 CQRS 除外，§9） |
| DomainService | `domain.service` | 核心业务逻辑、规则校验 | `@Transactional`、直接调 Mapper |
| Repository 接口 | `domain.repository` | 数据访问契约 | 含实现 |
| RepositoryImpl | `infrastructure.repository` | 数据访问实现、PO↔Entity 转换 | 含业务逻辑 |
| Mapper | `infrastructure.repository.mapper` | MyBatis 数据访问 | 含业务逻辑 |

> **依赖倒置与 @Entity 豁免**：仓储接口在 `domain.repository`、实现在 `infrastructure.repository`；领域层不 import Spring/MyBatis，但允许 `@Entity`/`@Transient` 等 JPA 标注聚合根（效率与纯度的权衡，换持久化方案时再迁移）。

## 8. Controller 层（项目约束）

- 类上 `@RequestMapping("/{resource}")` 定义资源根路径
- 返回 `ResultMode<T>`（见 [06](06-exception.md)）
- 不写 try-catch，异常交全局处理器

## 9. Application Service 层
- 编排链路中过滤/短路判定应前置于高成本操作：先完成事件级过滤与订阅命中判定，确认存在有效下游后再发起补数等外部调用，避免补数后才发现无订阅或事件被过滤，造成无效处理与逻辑不内聚。

- 事务边界在 AppService：写方法标 `@Transactional(rollbackFor = Exception.class)`，不得标在 DomainService/Controller
- **Handler / Manager（可选）**：策略分发过多或跨用例编排复杂时，拆 `handler/`（后缀 `Handler`，按渠道/功能域实现策略）与 `manager/`（后缀 `Manager`，跨 Handler 编排）。AppService 持事务边界与分发入口，Handler/Manager 不开新事务；简单场景不引入（命名见 [02](02-naming.md)）

## 10. Repository 实现模式

优先手动实现 RepositoryImpl（PO↔Entity 明确转换）。仅复杂 MyBatis-Plus 链式仓储才用 `ServiceImpl`（模式 B）——注意：用 `@Service` 非 `@Repository`，PO 直接暴露、缺 Entity 转换。

## 11. CQRS 读写分离

写操作经 Domain 保业务规则，读操作可直连 Mapper 绕过 Domain（避免无谓转换）。

| | 写（增删改） | 读（查询） |
| --- | --- | --- |
| 入参 | `xxxCommand` | `xxxQuery` |
| AppService 方法 | `create`/`modify`/`remove` | `get`/`page`/`count` |
| 数据路径 | AppService→DomainService→Repository→Mapper | AppService→Mapper（**可绕过 Domain**） |

读可绕过 Domain，但事务边界仍在 AppService；写**禁止**绕过 Domain 直调 Mapper。用例复杂时可引入执行器 `CmdExe`/`QryExe`（命名见 [02](02-naming.md)），AppService 仅分发。

## 12. 状态机
- 终态与自动化清理防死循环：机器不可继续的失败（熔断、轮次耗尽）应转入人工终态，且落标/落库须先于锁与租约的释放；重试与清理流程不得剥除人工终态标记——否则会形成「清标回零态 → 自动重派 → 再次失败」的静默死循环。

核心域对象生命周期建模为显式状态机（Cola Statemachine / 状态枚举+流转），非散落 if-else。状态流转属领域知识，收敛在 Domain 层，AppService 编排触发，adapter 只传事件不判断。

**质量红线**：❌死状态（无入边出边） ❌不可达状态 ❌缺失流转（状态未在任何转换 source/target 出现） ❌状态泄漏（adapter/infrastructure 持有或改写 domain 状态枚举）

## 13. 扩展点

多业务线/租户/渠道差异化用扩展点替代 if-else：

- 接口在 `domain.extensionpoint`（后缀 `ExtPt`）
- 实现在 `infrastructure.extension`（后缀 `Ext`），`@Extension(bizId, useCase, scenario)` 三维定位
- AppService 内 `extensionExecutor.execute(...)` 调用

> 扩展点面向"业务身份维度"差异化，与 `application/handler` 策略分发互补（handler 面向"功能域/渠道"分发）。

## 14. 应用服务 vs 领域服务

| | 应用服务 AppService | 领域服务 DomainService |
| --- | --- | --- |
| 管什么 | 用例编排、事务、权限 | 跨聚合业务规则 |
| 在哪里 | `app.application.service` | `domain.service` |

判定：去掉该方法后业务规则是否仍成立？成立→应用服务；不成立→领域服务。

## 15. 包结构

包路径 `com.acme.{模块标识}.{层}`（轻量档去掉模块标识层）。模块标识 = 业务域去连字符小写。

```
client/        api/(Inter) dto/ command/ query/
adapter/       web/(Controller) model/(可选)
application/   service/(AppService) executor/(可选) assembler/ handler/(可选) manager/(可选)
domain/        model/{entity,valueobject,condition} extensionpoint/(ExtPt) repository/(接口) service/(DomainService) event/
infrastructure/ repository/{mapper,po,converter} extension/(Ext) exchange/ exception/ config/ constant/ enums/ util/
```

> infrastructure 持久化包用 `repository/{mapper,po,converter}`，以兼容 `@EnableCustomConfig` 的 `@MapperScan("com.acme.**.infrastructure.repository.mapper")`。
>
> 易混包说明：`domain/model/condition` — 领域内复用的查询条件对象（区别于 `client.query` 下对外契约 `Query`）；`domain/event` — 领域事件定义（跨域经事件解耦，见 §6）；`infrastructure/exchange` — 领域事件对外发布 / MQ 投递的适配实现。

## 16. 启动类与命名

- 启动类放 `com.acme` 根包（完整档在 `-start` 模块，轻量档在服务根包），命名 `{业务域}Application`（禁止泛化如 `Application`）
- 标注 `@EnableCustomConfig`（框架提供，组成：`@MapperScan("com.acme.**.infrastructure.repository.mapper")` + `@EnableAspectJAutoProxy(exposeProxy=true)` + `@EnableAsync` + `@EnableDiscoveryClient` + `@EnableTransactionManagement` + `@EnableFeignClients`）；`@MapperScan` 须覆盖到 infrastructure 的 Mapper 包
- 新服务统一 `gtsp-` 前缀，业务域格式 `gtsp-{业务域}`；`fss-` 前缀不再用于新服务；前缀一旦确定不可更改

## 17. 禁止事项

- ❌ Adapter 写业务逻辑（判断/编排/默认值）
- ❌ 写操作绕过 Domain 直调 Mapper
- ❌ 领域层 import Spring/MyBatis（JPA 标注豁免）
- ❌ 领域对象直接返回 Adapter（须 Assembler→DTO）
- ❌ 值对象有 setter（必须不可变）
- ❌ 跨聚合对象引用（只允许 ID 引用）
- ❌ Adapter/Infrastructure 改写领域状态枚举（状态泄漏）
