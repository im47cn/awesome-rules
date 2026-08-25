---
title: Open API 设计规范
scenario: 设计/审查对外 Open API
inclusion: always
---

# Open API 设计与安全规范

## 1. 设计原则

1. **务实收敛**：统一用 POST，路径标准化（版本、命名空间、kebab-case、动词后置）
2. **增量严格、存量渐进**：新 API 必须 100% 合规；存量按优先级分批收敛
3. **单一契约**：一套返回体、一套错误码、一套文档规范
4. **语义可读**：路径、字段、错误码让开发者不看文档也能理解
5. **面向外部**：不暴露内部术语（渠道名、系统缩写），命名以外部可理解为最高优先

## 2. API URI

格式：`/{domain}/{version}/{resource}/{action}`

| 组成 | 规则 |
| --- | --- |
| domain | 业务域，如 `logistics`、`settlement`、`invoice`；禁止用渠道名或内部术语 |
| version | 仅在破坏性变更（删字段/改语义/改必填）时递增；同时最多维护 2 个版本 |
| resource | 名词 |
| action | 动词，收敛为：`create`/`query`/`update`/`remove`/`cancel`/`sync`/`confirm`/`apply`/`push` |

- 路径全小写 kebab-case，禁止 camelCase
- 禁止 path 中传递唯一标识或渠道名等变量

```
✅ /logistics/v1/waybill/sync
✅ /settlement/v1/payment/apply
❌ /zhejiangzhongyou/order    ← 渠道名做命名空间
❌ /syncWaybill               ← 动词前置 + camelCase
❌ /payment/v1/cancel/132     ← path 传标识
```

## 3. 参数约定

- **命名**：字段统一 camelCase
- **时间**：ISO 8601 带时区，如 `2026-07-18T11:49:52+08:00`
- **金额**：统一单位为元并注明
- **分页请求**：`{ pageNum（从 1 开始）, pageSize（上限 2000）, condition }`
- **分页响应**：`{ total, pages, pageNum, list }`
- **强类型**：禁止 `Map<String, Object>` 作为对外契约，必须有明确 DTO/Schema
- **枚举传值**【强制】：状态/类型类字段（status/type/state/level/kind 等）必须定义为枚举类型（Schema `enum`），禁止用裸 `String`/`Integer` 传魔法值（如 `status=1`）；枚举值须在文档完整列出

分页响应示例：

```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "timestamp": "2026-07-18T11:49:52+08:00",
  "traceId": "c0a80101-8c43-11e3-bc3d-000c2915b432",
  "model": {
    "pageNum": 1,
    "pageSize": 20,
    "total": 100,
    "pages": 5,
    "list": [
      { "orderNo": "T202607170001", "status": "PAID" },
      { "orderNo": "T202607170002", "status": "PENDING" }
    ]
  }
}
```

## 4. 统一响应体

所有 API（包括业务失败和平台异常）统一返回 **HTTP 200**，仅限流 429、网关故障 5xx 除外。

### 成功响应

```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "timestamp": "2026-07-18T11:49:52+08:00",
  "traceId": "c0a80101-8c43-11e3-bc3d-000c2915b432",
  "model": {
    "orderNo": "T202607170001",
    "status": "PAID"
  }
}
```

### 失败响应

```json
{
  "code": "GW_PARAM_001",
  "message": "操作失败",
  "details": [
    { "field": "orderNo", "message": "订单号不能为空" }
  ],
  "timestamp": "2026-07-18T11:49:52+08:00",
  "traceId": "c0a80101-8c43-11e3-bc3d-000c2915b432"
}
```

| 字段 | 说明 |
| --- | --- |
| code | 业务状态码，`SUCCESS` 表示成功，其余为错误码 |
| message | 面向商户的中文消息 |
| details | 校验错误明细（字段名 + 规则说明），仅校验失败时返回 |
| timestamp | ISO 8601 带时区时间戳 |
| traceId | 全链路追踪 ID，排障必备 |
| model | 业务数据（失败时无此字段） |

## 5. 错误码

格式：`{层标识}_{分类}_{序号}`，下划线分隔，如 `LGI_OPEN_0001`、`GW_AUTH_001`。与 GTSP 内部 `ExceptionEnum`（`{系统}_{模块}_{序号}`，见 [06-exception](gtsp/06-exception.md)）风格统一，便于在枚举类中集中维护。

| 分类段 | 含义 | 典型场景 |
| --- | --- | --- |
| `GW_AUTH_xxx` | 鉴权/认证 | 密钥无效、签名错误、防重放失败、IP 黑白名单 |
| `GW_PARAM_xxx` | 参数校验 | 必填缺失、格式错误、枚举非法 |
| `GW_BIZ_xxx` | 业务规则 | 状态不允许、额度不足、权限不足 |
| `GW_DEP_xxx` | 依赖方异常 | 下游系统超时、第三方不可达 |
| `GW_SYS_xxx` | 平台内部 | 网关异常、配置缺失 |
| `GW_LIMIT_xxx` | 限流/降级 | 配额耗尽、熔断中 |

> 层标识：`GW` = 网关层；`{业务域缩写}`（如 `LGI` 物流）= 业务层。业务错误码由各域 `ExceptionEnum` 维护，网关错误码由网关集中注册。内外错误码同风格（下划线），业务异常码可直接对外或经网关同风格映射。
> 错误码集中注册，通过全局 `@ExceptionHandler` 统一兜底，禁止逐方法手写 try-catch；参数校验信息须给出明确的参数名和规则要求。

## 6. 安全规范

### 6.1 日志脱敏

禁止在日志中明文打印认证信息、敏感字段。具体规则：

| 数据类型 | 脱敏规则 | 示例 |
|---|---|---|
| 手机号 | 保留前 3 后 4 | `138****5678` |
| 身份证 | 保留前 3 后 4 | `330****1234` |
| 银行卡号 | 保留后 4 | `****1234` |
| 邮箱 | 保留首字符和域名 | `a***@example.com` |
| Token/密钥 | 完全遮蔽 | `****` |
| 密码 | 完全遮蔽 | `****` |

- 日志中使用占位符 `{}` 传递脱敏后的值，禁止字符串拼接敏感信息
- 网关层统一拦截并脱敏，业务层按需补充
- 敏感字段在 `@RequestBody` 中需标注 `@Sensitive` 注解（或等效机制）

### 6.2 其他安全要求

- 禁止在响应体中返回内部系统名称、IP、端口等基础设施信息
- 网关层须实现防重放、IP 黑白名单、签名校验等基础安全能力

## 7. 幂等性
- 幂等键口径因事件/接口而异时，应支持按事件配置幂等键表达式，并定义默认兜底键（未配置或表达式解析失败时按默认键计算）；双轨并行或灰度切换期间，新旧链路须产出一致的幂等键。

- 业务系统必须基于业务主键实现幂等保护（唯一索引、状态机校验）
- 定义 API 时必须声明**业务幂等键字段**

## 8. 变更规范

- 接口或字段**只允许增加，不允许删除**
- 废弃时须标记 `@Deprecated` 并公告下线时间表

## 9. 文档规范

- 使用 **OpenAPI 3**（`@Operation`/`@Schema`/`@Tag`，springdoc），逐步淘汰 Swagger 2
- 注解即文档源：自动生成文档，禁止代码与文档两处维护
- 每个 API 必须完整标注：summary + description + 参数 Schema + 响应示例 + 错误码枚举
