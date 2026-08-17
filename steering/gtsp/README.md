---
title: GTSP 总入口
scenario: GTSP 工程规范总索引
---

# GTSP 工程规范

> GTSP 团队 Java / Spring Cloud 微服务工程规范，按维度拆分以支持按需加载。
> 采用 COLA DDD 架构（业务域隔离；完整档 6 模块 / 轻量档包分层，见 [01](01-project-structure.md) §3）；URI 结构、版本策略与 [`../openapi-standards.md`](../openapi-standards.md) 统一。GTSP 编码读本目录，对外 Open API 设计读 [`../openapi-standards.md`](../openapi-standards.md)。

- 父 POM：`com.acme:gtsp-parent:2.0.0-SNAPSHOT`
- 约束分级：维度文件（01-08）不逐条分级，阐述设计与工程规范；[09](09-cr-checklist.md) 为 CR 合并门禁清单（不通过则不予合并）

## 维度索引

| # | 维度 | 文件 | 适用场景 |
|---|---|---|---|
| 01 | 架构与分层 | [01-project-structure.md](01-project-structure.md) | 架构设计/业务域/模块档位/分层/CQRS/状态机/扩展点 |
| 02 | 命名规范 | [02-naming.md](02-naming.md) | 类后缀/方法分层/扩展点/常量类 |
| 03 | API 接口（Feign） | [03-api-feign.md](03-api-feign.md) | Feign/URL 版本/参数校验 |
| 04 | 数据库与 MyBatis-Plus | [04-database-mybatis.md](04-database-mybatis.md) | PO/Mapper/XML/分页插件 |
| 05 | 日志规范 | [05-logging.md](05-logging.md) | SLF4J+Log4j2/链路追踪 |
| 06 | 异常处理与统一返回 | [06-exception.md](06-exception.md) | ResultMode/BaseException/ErrorType |
| 07 | 配置文件规范 | [07-config.md](07-config.md) | bootstrap/application.yml |
| 08 | 注释与废弃标记 | [08-comments-deprecated.md](08-comments-deprecated.md) | Javadoc/@Deprecated |
| 09 | CR 检查清单与公共依赖 | [09-cr-checklist.md](09-cr-checklist.md) | CR 清单/公共依赖速查 |

## 使用方式

- 遇到对应场景时，先 `Read` 相关维度文件，再开始编码
- 合并门禁见 [09-cr-checklist.md](09-cr-checklist.md)，不通过则不予合并
