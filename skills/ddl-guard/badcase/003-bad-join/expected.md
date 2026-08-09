# ddl-guard badcase 003 — 不当的 JOIN 使用

check: sql_check.py

## 违规语句

| 语句 ID | 违规类型 | 问题 |
|---|---|---|
| `selectOverJoined` | 过度关联 | 关联了 8 张表（>5），影响性能 |
| `selectWithRightJoin` | RIGHT JOIN | 使用了 RIGHT JOIN，应改用 LEFT JOIN |
| `selectWithAbbreviatedJoin` | 简写 JOIN | 内连接写为 JOIN 而非 INNER JOIN |
| `selectWithoutPrefix` | 字段无前缀 | 多表关联时 SELECT 字段未带表名/别名前缀 |
| `selectWithBadAlias` | 无意义别名 | 使用了 t1, a 等无意义别名 |

## 合规语句

| 语句 ID | 说明 |
|---|---|
| `selectReasonableJoin` | 合理的 JOIN 数量（≤5），字段带前缀 |
| `selectWithLeftJoin` | 使用 LEFT JOIN 替代 RIGHT JOIN |
| `selectWithProperPrefix` | 字段带表名/别名前缀 |

## 预期检查输出

- 5 个违规语句（每个 1 个或多个问题）
- 3 个合规语句通过检查