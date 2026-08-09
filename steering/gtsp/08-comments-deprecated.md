---
title: 注释与废弃标记
scenario: Javadoc/@Deprecated
---

# 注释与废弃标记

> 适用：类/方法/字段 Javadoc、废弃 API 标记。

## 1. 类注释

所有 Java 类必须含 Javadoc，包含 `@author` 和 `@date`（格式 `yyyy-MM-dd`）。

## 2. 方法注释

public 方法应有 Javadoc（功能说明 + `@param` + `@return`）。**Feign 接口方法和 Controller 方法必须注释。**

## 3. 字段注释

- PO/Entity/DTO 所有字段必须有 Javadoc
- 状态码/枚举值字段注释须说明码值映射（如 `1是 0否`）
- 用 `/** */`，不用单行 `//`

## 4. 废弃标记

废弃的接口方法/DTO 字段/枚举值必须标 `@Deprecated`，并附 `@deprecated` Javadoc 说明替代方案与计划移除时间。
