---
title: 异常处理与统一返回
scenario: ResultMode/BaseException/ErrorType
---

# 异常处理与统一返回

> 适用：Controller 返回值、业务异常、异常枚举、全局异常处理器。

## 1. 统一返回格式

返回类型按模块裁决：client 模块（Feign 接口）统一 `ResponseMessage<T>`；adapter 模块（Controller）统一 `ResultMode<T>`（由 `fss-common` 提供）。禁止裸返回业务对象。

`ResultMode<T>` 主要字段：`model`（业务数据）、`total`（分页总数）、`succeed`、`errMsg`、`message`、`errCode`。常用静态方法：`success(data)`、`successPageList(list, total)`、`fail(code, msg)`。对外 Open API 响应体结构（含 `details`/`timestamp`/`traceId`，见 [`../openapi-standards.md`](../openapi-standards.md)）与内部 `ResultMode` 不同，两者映射由 API 网关完成，业务层无需关心。

## 2. 异常体系

- 所有业务异常继承 `BaseException`（`framework.fsscommon`），禁止直接抛 `RuntimeException`/`Exception`
- 每个业务域定义自己的异常类（如 `CoreMdmException`），接收 `ExceptionEnum`，super 设置父类字段
- `BaseException` 必须含 `ErrorType errorType` 字段（枚举，`fss-common` 提供）。全局处理器据 `errorType` 定日志级别：

| ErrorType | 含义 | 日志级别 | 含堆栈 |
| --- | --- | --- | --- |
| `SYS` | 系统异常（空指针、类型转换、DB 连接） | error | 是 |
| `EXT` | 外部调用异常（Feign 失败、第三方超时） | error | 是 |
| `DAT` | 数据异常（不存在、重复、格式不符） | warn | 是 |
| `BIZ` | 业务异常（校验失败、规则不满足） | warn | 否 |

## 3. 异常枚举

- 每个业务域定义 `ExceptionEnum`（infrastructure 模块 enums 包），枚举项含 `desc`/`type`(ErrorType)/`solution` 三字段
- 枚举常量名即错误码，**无需单独 code 字段**
- 命名 `{系统标识}_{模块}_{序号}`，如 `LS_Q1_0001`；系统标识取服务前缀大写（`UA`/`LS`），模块 2-4 位缩写，序号 4 位从 `0001` 起，按子功能分组注释
- 风格与对外 [`../openapi-standards.md`](../openapi-standards.md) 错误码统一（下划线分隔），业务异常码可直接作为对外错误码或经网关同风格映射

## 4. 全局异常处理

每个服务配置 `@RestControllerAdvice` 全局处理器，拦截 `BaseException` 与未知异常，返回标准 `ResultMode`。日志级别遵循 §2 表格；未知异常（非 BaseException）error + 堆栈兜底，返回 `fail("SYS_ERROR", "系统繁忙")`。
