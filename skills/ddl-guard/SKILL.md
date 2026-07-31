---
name: ddl-guard
description: >
  数据库设计规范与检查，包括审查DDL、建表语句、表结构设计、字段设计、索引设计、MySQL建表、
  审查Mapper SQL、PO类规范、数据库规范检查、SQL审核、数据库设计审查。
  提供两类能力：(1) 按规范设计新表，(2) 用脚本审查 DDL 文件和 MyBatis SQL 合规性。
---

# MySQL DDL 设计与审查

## 审查工作流

严格按以下步骤执行。

### 第 1 步：运行检查脚本

脚本位于本 SKILL.md 同级的 `scripts/` 子目录，以本文件所在路径为基准定位：

```bash
# DDL 审查（.sql 建表语句）
python3 scripts/ddl_check.py [--format json]

# MyBatis SQL 审查（*Mapper.xml + @TableName PO 类，Java 项目）
python3 scripts/sql_check.py [--format json]
```

- 退出码：`0`=通过，`1`=有强制问题，`2`=运行错误
- `sql_check.py` 自动扫描 mapper XML（解析 `<if>`/`<where>`/`<foreach>` 等动态标签和 `<include>` 引用）以及 MyBatis-Plus `@TableName` 注解的 PO 类（检查表名/字段命名规范、必含字段）

### 第 2 步：读取待审查文件

脚本自动扫描全部文件后，按以下原则读取：

- 小文件直接 `Read` 全文
- 大文件先用 `Read` 带 `limit` 参数看头部（DDL 的 CREATE TABLE 语句通常集中在文件前半部分）
- 仅问题密集且需要上下文判断的文件才扩大读取范围

> 优先使用 `codebase-memory-mcp` 的 `search_graph` / `get_code_snippet` 定位 SQL 文件和 PO 类。
> 优先使用 `smart_outline` 查看结构。

### 第 3 步：补充人工判断

读取以下文档，逐表核对脚本无法覆盖的规则：

- DDL 审查 → [`ddl-manual-rules.md`](ddl-manual-rules.md)
- SQL 审查 → [`sql-manual-rules.md`](sql-manual-rules.md)

### 第 4 步：输出报告

将脚本自动检查结果与人工判断合并，输出完整审查报告。

## 设计新表

读取 [`../../steering/database-design-specification.md`](../../steering/database-design-specification.md) 后按规范生成 DDL，再用上述脚本自检。
