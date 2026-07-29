---
name: ddl-guard
description: >
  数据库 DDL 设计与规范审查。当用户提到以下任意意图时激活：审查数据库设计、
  审查DDL、审查SQL、审查建表语句、审查Mapper、审查PO类、数据库设计、设计表结构、
  建表、表结构设计、字段设计、索引设计、检查SQL规范、数据库规范审查、DDL审核、
  SQL审核。提供两类能力：(1) 按规范设计新表，(2) 用脚本审查 DDL 文件和 MyBatis
  SQL 的合规性（含 @TableName PO 类）。
---

# MySQL DDL 设计与审查

## 审查工作流

收到审查请求后，按以下步骤执行。

> ⚠️ **直接运行脚本，不要手动搜索或逐个打开 `.sql` / `*Mapper.xml` 文件。**
> 脚本会自动扫描目标路径中的全部文件。

### 第 1 步：运行检查脚本

脚本位于本 SKILL.md 同级的 `scripts/` 子目录。请根据本文件的实际路径定位脚本（不是用户项目的当前工作目录）。将用户项目中待审查的文件或目录路径作为参数传入：

**DDL 审查**（`.sql` 建表语句）：

```bash
python3 scripts/ddl_check.py <目标文件或目录> [--format json]
```

**MyBatis SQL 审查**（`*Mapper.xml`，Java 项目）：

```bash
python3 scripts/sql_check.py <目标文件或目录> [--format json]
```

- `<目标文件或目录>`：用户项目中待审查的路径；不传则默认扫描当前目录
- 退出码：`0`=通过，`1`=有强制问题，`2`=运行错误
- `sql_check.py` 自动扫描 mapper XML（解析 `<if>`/`<where>`/`<foreach>` 等动态标签和 `<include>` 引用）以及 MyBatis-Plus `@TableName` 注解的 PO 类（检查表名/字段命名规范、必含字段）

### 第 2 步：补充人工判断

读取以下文档，逐表核对脚本无法覆盖的规则：

- DDL 审查 → [`ddl-manual-rules.md`](ddl-manual-rules.md)
- SQL 审查 → [`sql-manual-rules.md`](sql-manual-rules.md)

### 第 3 步：输出报告

将脚本自动检查结果与人工判断合并，输出完整审查报告。

## 设计新表

读取 [`../../steering/database-design-specification.md`](../../steering/database-design-specification.md) 后按规范生成 DDL，再用上述脚本自检。
