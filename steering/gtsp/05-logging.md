---
title: 日志规范
scenario: SLF4J+Log4j2/链路追踪
---

# 日志规范

> 适用：日志框架选型、日志内容规范、Log4j2 与链路追踪配置。

## 1. 日志框架

必须使用 SLF4J + Log4j2，通过 Lombok `@Slf4j` 注解引入 Logger。禁止直接使用 Log4j2 API 或 `System.out.println`。

## 2. 日志内容

- 关键业务操作入口和出口应记录日志
- 日志必须使用占位符 `{}`，禁止字符串拼接
- 异常日志必须包含完整堆栈（`log.error(msg, e)` 第二参数传异常对象）
- 敏感信息（密码、token、身份证号等）禁止明文输出，含敏感字段的入参必须脱敏后打印
- Controller 入口日志格式统一为 `类名.方法名 param={入参JSON}`（如 `log.info("XxxController.method param={}", param)`），前缀固定为 `类名.方法名` 保证可 grep 精确定位
- 耗时操作记录起止时间或具体耗时（如 `log.info("XxxController.method 耗时={}ms", cost)`）

## 3. Log4j2 配置

使用链路追踪默认配置：启用 `wlyd-trace-context-spring-boot-starter` 后自动提供包含 `traceId`、`X-WLYD-TRACE-ID`、`X-WLYD-SPAN-ID` 三个 MDC 变量的日志格式和异步 Appender，无需在 `application.yml` 中配置 `logging.config`。日志滚动按时间和大小双策略，单文件上限 100MB、`max=100`，使用 `Async` Appender 包装 `bufferSize=512`、`blocking=false`。
