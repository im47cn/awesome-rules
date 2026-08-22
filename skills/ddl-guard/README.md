# ddl-guard

MySQL DDL 设计与规范审查技能。

## 能力

1. **审查 DDL 文件** — 运行检查脚本自动检查 20+ 条规则，再补充人工判断
2. **设计新表** — 按规范生成合规建表语句

## 快速使用

```bash
# 审查所有 DDL 文件
python3 scripts/ddl_check.py

# 审查指定 DDL 文件
python3 scripts/ddl_check.py path/to/file.sql

# 审查所有 MyBatis SQL 和 PO 类（Java 项目）
python3 scripts/sql_check.py

# 审查指定路径
python3 scripts/sql_check.py path/to/mapper_or_project/

# JSON 格式输出
python3 scripts/ddl_check.py path/to/file.sql --format json
python3 scripts/sql_check.py path/to/project/ --format json
```

**退出码**：`0` = 通过，`1` = 有强制问题，`2` = 运行错误

## 需人工补充的规则

脚本无法覆盖全部规范，以下文档列出了各自需要人工核对的规则，**审查时务必逐项检查**：

| 脚本 | 未覆盖规则文档 |
|---|---|
| `ddl_check.py` | [`ddl-manual-rules.md`](ddl-manual-rules.md) |
| `sql_check.py` | [`sql-manual-rules.md`](sql-manual-rules.md) |

## 协作流程

```
开发人员编写 DDL
       │
       ▼
运行 ddl_check.py 自检 ──── 通过 ──→ 提交审核
       │
     未通过
       │
       ▼
按报告修复 ──→ 重新自检
```

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 检查脚本：[`scripts/ddl_check.py`](scripts/ddl_check.py)（DDL）、[`scripts/sql_check.py`](scripts/sql_check.py)（MyBatis SQL + PO 类）
- DDL 人工规则：[`ddl-manual-rules.md`](ddl-manual-rules.md)
- SQL 人工规则：[`sql-manual-rules.md`](sql-manual-rules.md)
- 设计规范：[`steering/database-design-specification.md`](../../steering/database-design-specification.md)
- 审查样例：[`test/`](test/)
