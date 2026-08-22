---
title: 命名规范
scenario: 类后缀/方法/注入/常量类
---

# 命名规范

> 适用：所有 Java 类、方法、常量命名。非领域类后缀与职责严格对应，禁止混用；**领域类（实体、值对象）无后缀，用业务名**。方法命名按层区分（§2）。

## 1. 类命名后缀

| 分类 | 后缀 | 所属层 | 示例 |
| --- | --- | --- | --- |
| Feign 接口 | `Inter` | client | `ProcessInter` |
| Controller | `Controller` | adapter.web | `FlowController` |
| 应用服务 | `AppService` | app.application.service | `FlowOperateAppService` |
| 装配器 | `Assembler` | app.application.assembler | `OrderCreateAssembler`（Entity↔DTO 转换，见 [01](01-project-structure.md) §7） |
| 命令/查询执行器 | `CmdExe`/`QryExe` | app.application.executor | `OrderCreateCmdExe`（见 [01](01-project-structure.md) CQRS） |
| 策略分发处理器 | `Handler` | app.application.handler | `PaymentHandler`（见 [01](01-project-structure.md) Handler） |
| 流程编排 | `Manager` | app.application.manager | `PaymentProcessManager` |
| 领域服务 | `DomainService` | domain.service | `CmdUserInfoDomainService` |
| 仓储接口 | `Repository` | domain.repository | `CmdCompanyInfoRepository` |
| 仓储实现 | `RepositoryImpl` | infrastructure.repository | `CmdCompanyInfoRepositoryImpl` |
| PO 转换器 | `Converter` | infrastructure.repository.converter | `CmdCompanyInfoConverter`（PO↔Entity 转换，见 [01](01-project-structure.md) §7） |
| Mapper | `Mapper` | infrastructure.repository.mapper | `CmdCompanyInfoMapper` |
| 持久化对象 | `PO` | infrastructure.repository.po | `PsProcessInstancePO` |
| 领域实体 | **无后缀** | domain.model.entity | `CmdCompanyInfo`（业务名） |
| 值对象 | **无后缀** | domain.model.valueobject | `Address`（不可变、无 setter） |
| 扩展点接口 | `ExtPt` | domain.extensionpoint | `SignStrategyExtPt` |
| 扩展点实现 | `Ext` | infrastructure.extension | `FddSignStrategyExt` |
| DTO | `DTO` | client.dto / adapter.web | `MdmCompanyInfoDTO` |
| 写操作入参 | `Command` | client.command / adapter.web | `ProcessStartCommand` |
| 查询条件 | `Query` | client.query / adapter.web | `MdmUserInfoQuery` |
| 常量类 | `Constant` | infrastructure.constant | `WeComConstant`（final class） |
| 领域状态枚举 | `Enum` | **domain**（`model/enum` 或领域服务同包） | `OrderStatusEnum`（被 DomainService 引用的状态/生命周期枚举；严禁放 infrastructure，否则 domain 逆向依赖） |
| 技术分类枚举 | `Enum` | infrastructure.enums | `OperatorStatusEnum`/`GenderEnum`（仅 infra/DTO 用的分类标志） |
| 异常枚举 | `Enum` | infrastructure.enums | `ExceptionEnum`（每域一个） |
| 异常类 | `Exception` | infrastructure.exception | `CoreMdmException`（继承 BaseException） |

> `PO`/`DTO`/`Command`/`Query` 等跨层/持久化对象保留后缀；仅 domain 实体、值对象无后缀。扩展点用法见 [01](01-project-structure.md) 扩展点。

## 2. 方法命名

按层区分：应用层（AppService）用业务语义，确需 CRUD 动词时遵循 COLA 约定；基础设施层（Mapper/RepositoryImpl）统一动词。

| 操作 | 应用层 AppService | 基础设施层 Mapper/RepositoryImpl |
| --- | --- | --- |
| 新增 | `create` | `insert` |
| 删除 | `remove` | `delete` |
| 修改 | `modify` | `update` |
| 分页查询 | `page` | `queryPage` |
| 查询单个 | `get` | `queryDetail`/`queryById` |
| 列表查询 | `list` | `queryList` |
| 统计 | `count` | `count` |
| 批量操作 | — | `batch`+动词 |

> 应用层优先业务语义方法名（`placeOrder`/`cancelOrder`/`syncCompanyInfo`）；基础设施层统一右列动词。两层动词差异是 CQRS 与依赖倒置的体现，勿混用。

## 3. 依赖注入

字段注入统一 `@Resource`（`javax.annotation.Resource`），不用 `@Autowired`。

## 4. 常量类

`final class` + `private` 构造方法，禁止用 `interface` 定义常量（interface 被继承/实现会导致常量泄露到子类型）。
