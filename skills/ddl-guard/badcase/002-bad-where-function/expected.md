# ddl-guard badcase 002 — WHERE 中对字段使用函数

check: sql_check.py

## 违规语句

| 语句 ID | 违规函数 | 问题 |
|---|---|---|
| `selectByDateFormat` | `DATE_FORMAT(create_time, ...)` | WHERE 中对字段使用了日期函数 |
| `selectBySubstringIndex` | `SUBSTRING_INDEX(order_no, ...)` | WHERE 中对字段使用了字符串函数 |
| `selectByReplace` | `REPLACE(order_no, ...)` | WHERE 中对字段使用了字符串函数 |
| `selectByUpper` | `UPPER(order_status)` | WHERE 中对字段使用了字符串函数 |
| `selectByConcat` | `CONCAT(first_name, last_name)` | WHERE 中对字段使用了字符串函数 |
| `selectByCast` | `CAST(order_amount AS ...)` | WHERE 中对字段使用了类型转换函数 |
| `selectByIfnull` | `IFNULL(discount_code, '')` | WHERE 中对字段使用了空值处理函数 |

## 合规语句

| 语句 ID | 说明 |
|---|---|
| `selectByExactMatch` | 字段值与常量比较（推荐写法） |
| `selectByCoveringIndex` | 使用覆盖索引精确匹配 |

## 改进建议

1. **日期函数**：改为范围查询 `create_time >= '2024-01-01' AND create_time < '2024-02-01'`
2. **字符串函数**：尽量改为精确匹配或使用覆盖索引
3. **类型转换**：确保字段类型与查询值类型一致，避免隐式转换
4. **空值处理**：确保字段 NOT NULL 或有合理的默认值

## 预期检查输出

7 个违规语句各检出 1 条，0 个违规语句通过检查。

- 脚本自动检出：WHERE避免函数转换
- 人工补充：类型转换与空值处理（见改进建议）