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
| 02 | 命名规范 | [02-naming.md](02-naming.md) | 类后缀/方法/注入/常量类 |
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

## 编号语义对照（双平台对应物核对）

> @date 2026-09-20｜核对方法：glob 实地核对 `.claude-plugin/`、`.codex-plugin/` 全树——两侧各仅含 plugin/marketplace manifest，无任何按编号镜像的规则文件；两平台 plugin.json 均以 `"skills": "./skills/"` 同字段引用共享技能源（[.claude-plugin/plugin.json](../../.claude-plugin/plugin.json):10、[.codex-plugin/plugin.json](../../.codex-plugin/plugin.json):8）。GTSP 规范不按编号进入插件负载，语义对齐发生在「共享单源」层：无逐编号副本，即无跨平台编号漂移面。发布面全量映射见 [docs/platform-matrix.md](../../docs/platform-matrix.md)。

| 编号 | 语义主题 | .claude-plugin 侧对应物 | .codex-plugin 侧对应物 | 状态 |
|---|---|---|---|---|
| 01 | 架构与分层 | 无逐编号对应（经共享 skills 源分发） | 无逐编号对应（同左） | 无对应（双侧一致，单源设计） |
| 02 | 命名规范 | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 03 | API 接口（Feign） | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 04 | 数据库与 MyBatis-Plus | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 05 | 日志规范 | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 06 | 异常处理与统一返回 | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 07 | 配置文件规范 | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 08 | 注释与废弃标记 | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |
| 09 | CR 检查清单与公共依赖 | 无逐编号对应 | 无逐编号对应 | 无对应（双侧一致，单源设计） |

> 已知描述层宣传口径漂移（claude 侧声明含 GTSP 与技能/规范计数，codex 侧未声明 GTSP 且计数口径更旧）不影响上表负载语义；明细与处置建议见 [docs/platform-matrix.md](../../docs/platform-matrix.md) §4 漂移上报，供人工 PR 裁决。
