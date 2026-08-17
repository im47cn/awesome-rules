---
title: API 接口（Feign）
scenario: Feign/URL 版本/参数校验
---

# API 接口规范（Feign）

> 适用：Feign 接口契约、URL 路径与版本、参数校验。约束 GTSP 内部微服务间 Feign 调用；URI 结构/版本/action 动词与 [`../openapi-standards.md`](../openapi-standards.md) 统一（`/{domain}/{version}/{resource}/{action}`，动词 `create`/`query`/`update`/`remove` 等）。URI/版本/错误码/时间格式与对外规范已统一，内部接口经网关对外时仅响应体需由网关映射适配。

## 1. Feign 接口定义

- `@FeignClient` 必须声明四属性：`url`（配置占位符）、`name`（服务名）、`contextId`（唯一标识）、`path`（服务根路径，即 domain）
- 方法路径 `/{version}/{resource}/{action}`，action 优先用 `create`/`query`/`update`/`remove`；CRUD 无法表达业务语义时用业务动作动词（`cancel`/`sync`/`confirm`/`apply`/`push` 等，见 §2）
- 只定义新结构路径，**禁止多路径匹配**；**禁止 `@PathVariable`**

## 2. URL 路径与版本

完整路径 = 服务根(domain) + `/{version}/{resource}/{action}`，全小写 kebab-case。

| 组成 | 规则 | 示例 |
| --- | --- | --- |
| domain | `context-path`，与服务名一致 | `/gtsp-admin-mdm` |
| version | 破坏性变更递增 | `v1` |
| resource | 名词，kebab-case | `cmd-user-info` |
| action | `create`/`update`/`remove`/`query`；业务动作 `cancel`/`sync`/`confirm`/`apply`/`push` 等 | `query` |

版本策略：仅破坏性变更（删字段/改语义/改必填）递增 version；非破坏性变更（加字段/加接口）不递增，保持兼容。同时最多 2 个版本。

## 3. 参数校验与统一返回

- 写操作（create/update/remove）的 `@RequestBody` 必须标 `@Valid`/`@Validated`；Command 必填字段用 `javax.validation`（`@NotNull`/`@NotBlank`/`@NotEmpty`/`@Length`）
- 返回类型：client（Feign）`ResponseMessage<T>`，全局响应包装自动转换，禁止裸返回业务对象（见 [06](06-exception.md)）
