# Open API 脚本无法检查的规则

Open API（对外接口）规范的脚本外人工兜底清单：以下条款 `api_check.py` 无法自动检查，
审查按 [`steering/openapi-standards.md`](../../steering/openapi-standards.md) 设计的对外
接口时需人工逐条核对。脚本仅自动覆盖路径命名（kebab-case）、动作收敛（末段动词集）、
路径变量（禁止 path 传标识）与 DTO 时间注解（见 [`api-manual-rules.md`](api-manual-rules.md)）。

等级按规范原文标注：措辞为「必须/禁止/不得」的条款归【强制】，过渡性要求归【推荐】。

## API URI【强制】

| 规则 | 要点 |
|---|---|
| 四段式结构 | 路径必须为 `/{domain}/{version}/{resource}/{action}`，缺段、多段均不合规 |
| domain 命名 | 业务域（如 `logistics`/`settlement`/`invoice`），禁止渠道名或内部术语做命名空间 |
| version 语义 | 仅在破坏性变更（删字段/改语义/改必填）时递增；同时最多维护 2 个版本 |
| resource 与 action | resource 为名词；action 为动词且落在收敛集内（create/query/update/remove/cancel/sync/confirm/apply/push），四段归属需人工核对 |
| 统一 POST | 统一用 POST，禁止 GET/PUT/DELETE 承载业务接口 |

## 参数约定【强制】

| 规则 | 要点 |
|---|---|
| 字段命名 | 请求/响应字段统一 camelCase |
| 枚举传值 | 状态/类型类字段（status/type/state/level/kind 等）必须定义为枚举类型（Schema `enum`），禁止用裸 `String`/`Integer` 传魔法值（如 `status=1`）；枚举值须在文档完整列出 |
| 时间格式 | ISO 8601 带时区，如 `2026-07-18T11:49:52+08:00`；脚本只拦 `@JsonFormat(shape=NUMBER)`，pattern 合规性需人工核对 |
| 金额单位 | 统一为元并注明 |
| 分页请求 | `{ pageNum（从 1 开始）, pageSize（上限 2000）, condition }` |
| 分页响应 | `{ total, pages, pageNum, list }` |
| 强类型 | 禁止 `Map<String, Object>` 作为对外契约，必须有明确 DTO/Schema |

## 统一响应体【强制】

| 规则 | 要点 |
|---|---|
| 统一 HTTP 200 | 所有 API（含业务失败和平台异常）返回 200，仅限流 429、网关故障 5xx 除外 |
| 成功信封 | 含 `code`/`message`/`timestamp`/`traceId`/`model`，`code` 成功为 `SUCCESS` |
| 失败信封 | 以 `details` 数组替代 `model`（字段名 + 规则说明），失败响应不得含 `model` |
| 时间戳与追踪 | `timestamp` 为 ISO 8601 带时区；`traceId` 为全链路追踪 ID，排障必备 |

## 错误码【强制】

| 规则 | 要点 |
|---|---|
| 错误码格式 | `{层标识}_{分类}_{序号}`（下划线分隔），如 `LGI_OPEN_0001`、`GW_AUTH_001` |
| 分类段语义 | `GW_AUTH`/`GW_PARAM`/`GW_BIZ`/`GW_DEP`/`GW_SYS`/`GW_LIMIT` 按场景对号入座 |
| 集中注册与兜底 | 错误码集中注册，经全局 `@ExceptionHandler` 统一兜底，禁止逐方法手写 try-catch |
| 校验信息 | 参数校验失败须给出明确的参数名和规则要求 |

## 安全规范【强制】

| 规则 | 要点 |
|---|---|
| 日志脱敏 | 手机号/身份证保留前 3 后 4；银行卡号保留后 4；邮箱保留首字符和域名；Token/密钥/密码完全遮蔽 |
| 脱敏实现 | 日志用占位符 `{}` 传脱敏后的值，禁止字符串拼接敏感信息；网关层统一拦截脱敏，敏感字段在 `@RequestBody` 中标注 `@Sensitive` |
| 响应安全 | 禁止响应体返回内部系统名称、IP、端口等基础设施信息 |
| 网关基础安全 | 防重放、IP 黑白名单、签名校验须由网关层实现 |

## 幂等性【强制】

| 规则 | 要点 |
|---|---|
| 幂等键声明 | 定义 API 时必须声明业务幂等键字段 |
| 主键幂等 | 基于业务主键实现幂等保护（唯一索引、状态机校验） |
| 表达式与兜底键 | 幂等键口径因事件/接口而异时，支持按事件配置幂等键表达式并定义默认兜底键（未配置或解析失败按默认键计算）；双轨并行或灰度切换期间新旧链路须产出一致的幂等键 |

## 变更规范【强制】

| 规则 | 要点 |
|---|---|
| 只增不删 | 接口或字段只允许增加，不允许删除 |
| 废弃流程 | 废弃须标记 `@Deprecated` 并公告下线时间表 |

## 文档规范【推荐】

| 规则 | 要点 |
|---|---|
| OpenAPI 3 | 使用 `@Operation`/`@Schema`/`@Tag`（springdoc），逐步淘汰 Swagger 2 |
| 注解即文档 | 自动生成文档，禁止代码与文档两处维护 |
| 标注完整 | 每个 API 完整标注 summary + description + 参数 Schema + 响应示例 + 错误码枚举 |
