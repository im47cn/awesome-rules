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
python3 skills/ddl-review/scripts/ddl_check.py <file_or_dir> [--format json]
```

退出码：0=通过，1=有强制问题，2=运行错误。

脚本覆盖 20+ 条可自动化规则（表名/字段名/类型/注释/索引/禁用子句等）。但以下规则脚本无法检查，需逐表补充人工判断：

- **命名语义**：字段名是否细化到属性级别（不得用主体名当属性名）
- **泛化词**：「关联」「业务」等无信息量的词应替换
- **方/人区分**：专指人用 `er`，含机构用 `pty`
- **拼音**：表名/字段名是否误用拼音而非英文
- **注释补充信息**：圆括号内容是否为必要补充（非冗余、不让含义混淆）
- **索引有效性**：索引字段是否与查询条件匹配（需 EXPLAIN 验证）
- **SQL 压测**：性能是否达标

将脚本报告与人工判断合并输出。

## 设计新表

完整规范见 `steering/database-design-specification.md`，生成 DDL 后务必用上述脚本自检。

容易遗漏的要点：
- 去除 engine/charset/collate/auto_increment/row_format 子句
- 含 5 个必含字段：`id`、`creator_id`、`create_time`、`last_updater_id`、`last_update_time`
- 含 `del_flag tinyint NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]'`
- 禁用类型：TEXT/JSON/timestamp/float/double/enum/set/BLOB
- 注释格式：`中文名(补充信息)[枚举信息]`，无则不写括号
- 索引前缀：唯一 `uk_`，普通 `ix_`
