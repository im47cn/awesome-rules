---
name: ddl-review
description: >
  MySQL DDL 设计与规范审查。触发词：设计表结构、建表、DDL审核、审查SQL脚本、
  检查建表语句、数据库规范。提供两类能力：(1) 按规范设计新表，(2) 用脚本审查
  DDL 文件合规性。
---

# MySQL DDL 设计与审查

## 审查 DDL 文件

运行检查脚本（规则已内置，无需读取规范文件）：

```bash
python3 scripts/ddl_check.py [file_or_dir] [--format json]
```

退出码：0=通过，1=有强制问题，2=运行错误。

运行后，读取 [`ddl-manual-rules.md`](ddl-manual-rules.md) 逐表补充人工判断。

## 审查 MyBatis SQL（Java 项目）

```bash
python3 scripts/sql_check.py [mapper_xml_or_project_dir] [--format json]
```

支持自动扫描 Java 项目目录中的 mapper XML，解析动态标签（`<if>`/`<where>`/`<foreach>` 等）和 `<include>` 引用。

运行后，读取 [`sql-manual-rules.md`](sql-manual-rules.md) 补充人工判断。

## 设计新表

读取 `../../steering/database-design-specification.md` 后生成 DDL，再用上述脚本自检。
