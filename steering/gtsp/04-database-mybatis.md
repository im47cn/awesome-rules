---
title: 数据库与 MyBatis-Plus
scenario: PO/Mapper/XML/分页插件
---

# 数据库与 MyBatis-Plus 规范

> 适用：PO/Mapper/XML、分页插件。表结构设计（字段类型、索引、命名）见 `steering/database-design-specification.md`。

## 1. 实体类（PO）

- 禁止实现 `Serializable`（无需 `serialVersionUID`）
- `@TableName` 显式指定表名；`@TableId` 声明主键（同一服务主键策略保持一致，预生成 ID 用统一生成器，禁止手写时间戳拼接）
- Lombok `@Getter`+`@Setter`+`@Accessors(chain=true)`+`@ToString`，**不用 `@Data`**
- 非数据库字段标 `@TableField(exist = false)`
- 日期注解按层次区分：**PO 不加任何日期格式化注解**；**DTO 标 `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "+08:00")`**（ISO 8601 带时区，与 `openapi-standards.md` 一致，内外零转换；显式 `timezone` 避免依赖 JVM 默认时区）

## 2. Mapper

继承 `BaseMapper<PO>`，简单 CRUD 用继承方法不重复定义；自定义查询配合 XML。

## 3. MyBatis-Plus 配置

每个服务配置分页拦截器，`DbType.MYSQL` 显式指定。application.yml 关键项：`map-underscore-to-camel-case: true`、`auto-mapping-behavior: full`、`log-impl: ...Log4j2Impl`、`mapper-locations: classpath*:/mapper/**/*Mapper.xml`。

## 4. Mapper XML

- 位于 `src/main/resources/mapper/`（可按业务域建子目录）
- namespace 与 Mapper 接口全限定名一致
- 定义 `BaseResultMap` 和 `Base_Column_List` 复用
- 查询带 `del_flag = 0` 逻辑删除条件（如表有该字段）
