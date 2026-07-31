---
inclusion: always
---

# DDD 架构规范

> 基于 COLA 4.0，结合团队实践裁剪。

## 架构总览：二维分解【强制】

DDD 架构有两个正交的分解维度，必须同时遵守：

| 维度 | 含义 | 物理体现 | 示例 |
|---|---|---|---|
| **垂直（分层）** | 技术职责分离 | Maven 模块后缀 | `-adapter`, `-domain`, `-infrastructure` |
| **水平（业务域）** | 业务边界隔离 | Maven 模块前缀 / 顶层目录 | `order/`, `logistics/`, `settlement/` |

```
{platform}/                         # 父 POM（统一版本管理）
│
├── platform-common/               # 跨域共享（非业务、纯技术：工具类、通用配置）
│
├── order/                          # 业务域：订单
│   ├── order-adapter/
│   ├── order-client/              # 对外契约，零内部依赖
│   ├── order-start/               # 启动引导（仅本域），独立可部署
│   ├── order-app/
│   ├── order-domain/
│   └── order-infrastructure/
│
├── logistics/                      # 业务域：物流
│   ├── logistics-adapter/
│   ├── logistics-client/
│   ├── logistics-start/
│   ├── logistics-app/
│   ├── logistics-domain/
│   └── logistics-infrastructure/
│
└── settlement/                     # 业务域：结算
    └── ...
```

### 业务域的判定标准【强制】

一个**业务域**满足以下全部条件：
- 有独立的业务语言（同一个词在不同域含义不同，如"运单"在订单域 vs 物流域）
- 可独立演进（一个域的变更不影响另一个域的发版节奏）
- 有自己的聚合根（不与其他域共享写入操作）

一个**子域**（Bounded Context）满足以下条件：
- 在父域内的业务子领域，共享部分业务语言
- 通常 1 个开发小组负责 1-2 个子域
- 子域之间通过**领域事件**或 **Client API（`ServiceI`）** 解耦，禁止直接 import

### 子域的包体现

子域不独立为 Maven 模块，而是通过**包路径**体现：

```
order-domain/src/main/java/com/{company}/order/domain/
├── waybill/                  # 子域：运单
│   ├── entity/WaybillE.java
│   ├── repository/WaybillRepository.java
│   └── service/WaybillDomainService.java
├── tracking/                 # 子域：轨迹
│   ├── entity/TrackingE.java
│   └── event/WaybillTrackedEvent.java
└── shared/                   # 域内共享（非跨域！）
    └── valueobject/AddressV.java
```

> **关键区分**：子域包 vs 独立业务域——子域间允许互相 import（同在 `order-domain` 模块内），业务域间禁止互相 import（通过事件或 API 解耦）。当子域膨胀到需要独立演进和独立团队时，升级为独立业务域。

### 跨域依赖【强制】

**禁止跨业务域的直接 Maven 依赖**：

```
❌ order-domain/pom.xml → 依赖 logistics-domain
❌ order-app/pom.xml    → 依赖 settlement-app
```

跨域通信仅允许以下三种方式（编译期零耦合）：

| 方式 | 适用场景 | 耦合度 |
|---|---|---|
| 引入目标域的 `-client` 模块调用 `ServiceI` | 同步查询 | 仅依赖 API 契约 |
| 订阅目标域的领域事件 | 异步通知 | 完全解耦 |
| 复制一份值对象定义（必要时） | DTO 跨域传输 | 零耦合 |

```xml
<!-- ✅ 允许：order-app 通过 client 调用 logistics -->
<dependency>
    <groupId>com.{company}</groupId>
    <artifactId>logistics-client</artifactId>
</dependency>
```

### 模块依赖矩阵【强制 — `pom.xml` 编译期校验】

以下为**单个业务域内部**的依赖矩阵（跨域仅允许通过 `-client`，已在上述规则中约束）：

| 模块 → 可依赖 | adapter | client | app | domain | infrastructure |
|---|---|---|---|---|---|
| **adapter** | — | ✅ | ✅ | ❌ | ❌ |
| **client** | ❌ | — | ❌ | ❌ | ❌ |
| **app** | ❌ | ✅ | — | ✅ | ✅ |
| **domain** | ❌ | ❌ | ❌ | — | ❌ |
| **infrastructure** | ❌ | ✅ | ❌ | ✅ | — |

```xml
<!-- ✅ {project}-app/pom.xml -->
<dependency>
    <groupId>com.{company}</groupId>
    <artifactId>{project}-domain</artifactId>
</dependency>
<dependency>
    <groupId>com.{company}</groupId>
    <artifactId>{project}-infrastructure</artifactId>
</dependency>

<!-- ❌ 禁止：{project}-adapter/pom.xml 依赖 domain -->
```

> **关键约束**：`client` 模块的 POM 不允许出现任何本项目其他模块的 `<dependency>`。`domain` 模块的 POM 中不允许出现 Spring Boot Starter、MyBatis 等框架依赖。

### 包约定（模块内部结构）

Maven 模块内部包路径遵循 `com.{company}.{project}.{layer}`：

```
{project}-adapter/src/main/java/com/{company}/{project}/adapter/
├── controller/
├── consumer/
└── scheduler/

{project}-client/src/main/java/com/{company}/{project}/client/
├── api/           # ServiceI 接口
├── dto/           # CO（Client Object）
├── command/       # Cmd（写操作入参）
└── query/         # Query（读操作入参）

{project}-app/src/main/java/com/{company}/{project}/application/
├── executor/      # CmdExe
│   └── query/     # QryExe
├── assembler/     # Assembler
├── validator/
└── interceptor/

{project}-domain/src/main/java/com/{company}/{project}/domain/
├── entity/         # 后缀 E
├── valueobject/    # 后缀 V，必须不可变
├── service/        # 后缀 DomainService
├── repository/     # 仓储接口
├── event/          # 领域事件
└── extensionpoint/ # 后缀 ExtPt

{project}-infrastructure/src/main/java/com/{company}/{project}/infrastructure/
├── persistence/    # DO、Mapper、RepositoryImpl
├── external/       # ACL（防腐层）
├── extension/      # 后缀 Ext
└── config/
```

> **架构决策 1**：Maven module > 包约定——模块依赖在编译期物理阻断违规引用，包约定仅阻止同模块内的路径违规。
> **架构决策 2**：Adapter 层独立——Controller 仅做参数解析和返回值包装，禁止业务逻辑。编排一律在 Application Executor。
> **架构决策 3**：Client 层独立——零内部依赖，可单独发布为 JAR 供调用方引入。

## 务实 DDD 约定【强制】

领域层允许使用 `@Entity` 标注聚合根，是团队对开发效率与 DDD 纯度的明确权衡。若后续引入 CQRS 读写分离或更换持久化方案，注解迁移到基础设施层。依赖倒置原则不变：仓储接口在领域层，实现在基础设施层。

## 依赖方向【强制】

```
Adapter → Client → Application → Domain ← Infrastructure
```

领域层不 import Spring/MyBatis 类（`@Entity`、`@Transient` 等 JPA 标注注解除外）。

## CQRS 读写分离【强制】

| | 写操作（增删改） | 读操作（查询） |
|---|---|---|
| 入参 | `xxxCmd` | `xxxQuery` |
| 执行器 | `xxxCmdExe` | `xxxQryExe` |
| 数据路径 | Application → Domain → Repository → Mapper | Application → Mapper（直接查，**可绕过 Domain 层**） |

> **关键决策**：查询无需经过领域对象转换，QryExe 直接调用 Mapper 返回 DO → Assembler → CO。这是 CQRS 的核心收益——读模型与写模型分离。

## 命名规范【强制】

### 类名后缀

| 后缀 | 含义 | 所在层 |
|---|---|---|
| `xxxCmd` | 写操作入参 | `client/command/` |
| `xxxQuery` | 读操作入参 | `client/query/` |
| `xxxCO` | Client Object（对外 DTO） | `client/dto/` |
| `xxxServiceI` | API 服务接口 | `client/api/` |
| `xxxCmdExe` | 命令执行器 | `application/executor/` |
| `xxxQryExe` | 查询执行器 | `application/executor/query/` |
| `xxxE` | 领域实体 | `domain/entity/` |
| `xxxV` | 值对象 | `domain/valueobject/` |
| `xxxDomainService` | 领域服务 | `domain/service/` |
| `xxxRepository` | 仓储接口 | `domain/repository/` |
| `xxxDO` | 数据对象 | `infrastructure/persistence/` |
| `xxxAssembler` | 对象组装器 | `application/assembler/` |
| `xxxExtPt` | 扩展点接口 | `domain/extensionpoint/` |
| `xxxExt` | 扩展点实现 | `infrastructure/extension/` |

### CRUD 方法名（应用层 vs 基础设施层）

| 操作 | Application | Infrastructure |
|---|---|---|
| 新增 | `create` | `insert` |
| 删除 | `remove` | `delete` |
| 修改 | `modify` | `update` |
| 查询单个 | `get` | `selectById` |
| 分页 | `page` | `selectPage` |
| 统计 | `count` | `selectCount` |

> 应用层优先使用业务语义（`placeOrder`、`cancelOrder`），不直接使用 CRUD 动词。

## 扩展点【推荐】

多业务线、多租户差异化定制时使用，替代 if-else：

```java
// 定义（domain/extensionpoint/）
public interface XxxExtPt extends ExtensionPointI { }

// 实现（infrastructure/extension/）
@Extension(bizId = "CN", useCase = "order", scenario = "vip")
public class XxxExt implements XxxExtPt { }

// 调用（application/executor/）
extensionExecutor.execute(XxxExtPt.class,
    ExtCoordinate.of(bizId, useCase, scenario),
    ext -> ext.doSomething());
```

三维定位 `bizId + useCase + scenario`，框架扫描 `@Extension` 注册，运行时按坐标路由。

## 应用服务 vs 领域服务【容易混淆】

| | 应用服务 | 领域服务 |
|---|---|---|
| 是什么 | CmdExe/QryExe | DomainService |
| 管什么 | 用例编排、事务、权限 | 跨聚合的业务规则 |
| 在哪里 | `application/executor/` | `domain/service/` |

> **判定标准**：去掉这个方法后业务规则是否仍成立？成立→应用服务；不成立→领域服务。

## 禁止事项

- ❌ Adapter 层写业务逻辑（包括判断、编排、默认值决策）
- ❌ 写操作中 Application 绕过 Domain 直接调 Mapper
- ❌ 领域层 import Spring/MyBatis 类（JPA 标注注解除外）
- ❌ 领域对象直接返回给 Adapter（必须 Assembler → CO）
- ❌ 值对象有 setter
- ❌ 跨聚合对象引用（只允许 ID 引用）
