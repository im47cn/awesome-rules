# ddl-review

MySQL DDL 设计与规范审查技能。

## 能力

1. **审查 DDL 文件** — 运行检查脚本自动检查 20+ 条规则，再补充人工判断
2. **设计新表** — 按规范生成合规建表语句

## 快速使用

```bash
# 审查单个文件
python3 scripts/ddl_check.py path/to/file.sql

# 审查目录下所有 .sql 文件
python3 scripts/ddl_check.py path/to/dir/

# JSON 格式输出
python3 scripts/ddl_check.py path/to/file.sql --format json
```

**退出码**：`0` = 通过，`1` = 有强制问题，`2` = 运行错误

## 脚本检查覆盖

| 类别 | 检查项 |
|---|---|
| 文件级 | engine/charset/collate/auto_increment/row_format 子句、注释符号、分区表、CHANGE COLUMN |
| 表级 | 表名（长度/字符/下划线/保留字）、表注释（缺失/长度/特殊字符）、必含 5 字段、字段数 ≤40、外键约束 |
| 字段级 | 字段名（同表名规则）、注释（缺失/长度/全角字符）、禁用类型、varchar/char 长度、主键整型、del_flag 统一 |
| 索引级 | uk_/ix_ 命名、id 重复索引、索引数量、联合索引字段数 |

## 需人工补充的规则

脚本无法检查以下规则，需逐表人工判断：

- **命名语义**：字段名是否细化到属性级别（不得用主体名当属性名）
- **泛化词**：「关联」「业务」等无信息量的词应替换
- **方/人区分**：专指人用 `er`，含机构用 `pty`
- **拼音**：表名/字段名是否误用拼音而非英文
- **注释补充信息**：圆括号内容是否为必要补充
- **索引有效性**：索引字段是否与查询条件匹配（需 EXPLAIN 验证）
- **SQL 压测**：性能是否达标

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 检查脚本：[`scripts/ddl_check.py`](scripts/ddl_check.py)
- 设计规范：[`steering/database-design-specification.md`](../../steering/database-design-specification.md)
- 审查样例：[`test/`](test/)
