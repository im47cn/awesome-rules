# API 脚本无法检查的规则

以下规则 `api_check.py` 无法自动检查，审查 API 时需人工判断。

## 响应体规范【强制】

| 规则 | 要点 |
|---|---|
| 统一 HTTP 200 | 所有 API（含失败）返回 200，仅限流 429、网关 5xx 除外 |
| 响应信封 | 成功须含 `code`/`message`/`timestamp`/`traceId`/`model`；失败用 `details` 数组替代 `model` |
| 错误码格式 | 须为 `{层标识}_{分类}_{序号}`，如 `LGI_OPEN_0001` / `GW_AUTH_001`（下划线，内外统一） |

## 参数约定【强制】

| 规则 | 要点 |
|---|---|
| 字段命名 | 请求/响应字段统一 camelCase |
| 时间格式 | ISO 8601 带时区，如 `2026-07-18T11:49:52+08:00`（DTO `@JsonFormat` shape=NUMBER 已脚本化拦截；缺 pattern 仍需人工核对） |
| 金额单位 | 统一为元并注明 |
| 强类型约束 | 禁止 `Map<String, Object>` 作为对外契约，须有明确 DTO |
| 分页结构 | 请求 `{ pageNum, pageSize, condition }`，响应 `{ total, pages, pageNum, list }` |

## 业务规范【强制】

| 规则 | 要点 |
|---|---|
| 幂等性 | 必须基于业务主键实现幂等保护，API 定义中须声明幂等键字段 |
| 变更规范 | 字段只增不删；废弃须标记 `@Deprecated` 并公告下线时间 |
| 统一兜底 | 通过全局 `@ExceptionHandler` 统一兜底，禁止逐方法手写 try-catch |

## 文档规范【推荐】

| 规则 | 要点 |
|---|---|
| OpenAPI 3 | 使用 `@Operation`/`@Schema`/`@Tag`（springdoc），淘汰 Swagger 2 |
| 注解完整 | summary + description + 参数 Schema + 响应示例 + 错误码枚举 |
| 注解即文档 | 自动生成文档，禁止代码与文档两处维护 |

## 安全规范【强制】

| 规则 | 要点 |
|---|---|
| 日志脱敏 | 手机号(前3后4)、身份证(前3后4)、银行卡(后4)、邮箱(首字符+域名)、Token/密码完全遮蔽；网关层统一拦截脱敏 |
| URL 安全 | 禁止 URL path 中传递 token 或认证信息 |
| 响应安全 | 禁止响应体返回内部系统名称、IP、端口等基础设施信息 |
