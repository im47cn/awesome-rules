# SQL 脚本无法检查的规则

以下规则 `sql_check.py` 无法自动检查，审查 MyBatis mapper 时需人工判断。

## 语义判断【强制】

| 规则 | 要点 | 操作指引 |
|---|---|---|
| NULL vs 空字符串 | `''`（空字符串）与 `NULL` 语义不同，业务逻辑需正确区分 | 审查 SQL 中 `IS NULL`、`IS NOT NULL`、`= ''`、`<> ''` 的使用是否符合业务语义。例如：未填写的手机号应为 `NULL` 而非 `''` |
| 字段前缀正确性 | 脚本能检测多表关联时字段是否带前缀，但无法判断前缀是否指向正确的表 | 审查多表关联时，每个字段前缀是否指向正确的表。例如 `t_order o JOIN t_buyer b ON o.buyer_id = b.id` 中，`o.buyer_id` 应指向订单表的买家id，`b.id` 应指向买家表的主键 |

## 查询合理性【推荐】

| 规则 | 要点 | 操作指引 |
|---|---|---|
| 过度查询 | 脚本无法判断是否检索了不必要的字段或行数 | 审查 SELECT 字段是否包含业务不需要的字段。例如只需 `order_no` 和 `order_status`，却 SELECT 了所有字段。审查 WHERE 条件是否限制了足够的行数 |
| JOIN 表数量 | 脚本能检测 JOIN 过多（>5），但合理的关联数量需结合业务判断 | 审查 JOIN 的每张表是否真的需要关联。例如 3 张表的 JOIN 可能合理，但 4-5 张表的 JOIN 需谨慎评估是否可以通过子查询或应用层组装替代 |
| 别名含义 | 脚本能拦截 t1/a/b 等无意义别名，但其他别名是否清晰需人工判断 | 审查表别名是否清晰表达表含义。例如 `t_order o` 中 `o` 不够清晰，可改为 `t_order ord`；`t_buyer buyer` 比 `t_buyer b` 更清晰 |

## 需运行时验证【强制】

| 规则 | 要点 | 操作指引 |
|---|---|---|
| SQL 压测 | 以生产数据量 2-3 倍验证，执行 < 1s；< 10 万条时执行 < 500ms | 1. 获取生产环境各表的数据量<br>2. 在测试环境构造 2-3 倍数据量的测试数据<br>3. 执行目标 SQL，记录执行时间<br>4. 执行时间 > 1s 或 < 10 万条时 > 500ms 需优化<br>5. 优化方向：添加索引、改写 SQL、拆分子查询 |
| 索引有效性 | 索引字段须与查询条件一致，需 EXPLAIN 验证 | 1. 对每条 SQL 执行 `EXPLAIN` 或 `EXPLAIN ANALYZE`<br>2. 确认 `type` 列不为 `ALL`（全表扫描）<br>3. 确认 `key` 列确实使用了预期索引<br>4. 确认 `rows` 列与预期扫描行数一致<br>5. 确认 `Extra` 列无 `Using filesort`、`Using temporary` 等性能警告 |

## PO 类规则（MyBatis-Plus）【强制】

脚本自动检查 `@TableName` 表名/字段命名规范和必含字段，以下需人工判断：

| 规则 | 要点 | 操作指引 |
|---|---|---|
| 字段类型一致性 | PO 字段的 Java 类型须与 DDL 列类型匹配（如 `varchar(36)` → `String`，`datetime` → `LocalDateTime`） | 逐字段核对 PO 类字段类型与 DDL 列类型是否匹配：<br>- `int/bigint` → `Integer/Long`<br>- `varchar/char` → `String`<br>- `decimal` → `BigDecimal`<br>- `datetime/timestamp` → `LocalDateTime`<br>- `tinyint(1)` → `Boolean`<br>- `tinyint` → `Integer` |
| 继承字段完整性 | 若 PO 继承 `BaseEntity` 等基础类，需确认父类确实包含 id/creator_id/create_time 等必含字段 | 审查 PO 类的继承关系，确认父类（如 `BaseEntity`、`BaseDO`）确实包含所有必含字段。如果父类缺失某个必含字段，需在当前 PO 中显式声明 |
| `@TableLogic` 配置 | 逻辑删除字段须标注 `@TableLogic`，且全局配置 `logic-delete-value`/`logic-not-delete-value` 与 `del_flag` 取值一致 | 审查 PO 类中 `del_flag` 字段是否标注 `@TableLogic`。检查全局配置 `mybatis-plus.global-config.db-config.logic-delete-value` 和 `logic-not-delete-value` 是否与 `del_flag` 的取值（0-否, 1-是）一致 |
| 字段映射完整性 | 每个数据库列都须在 PO 中有对应字段（或显式声明 `@TableField(exist = false)`），避免隐式遗漏 | 逐字段核对 DDL 列名与 PO 类字段映射关系。确保每个数据库列在 PO 中都有对应字段，或显式声明 `@TableField(exist = false)` 表示非数据库列 |

## 审查清单（逐语句核对）

对每个 mapper XML 文件中的每条 SQL 语句，按以下顺序逐条核对：

1. **脚本检查**：运行 `sql_check.py`，处理所有自动检出的问题
2. **语义判断**：NULL vs 空字符串是否正确？字段前缀是否指向正确的表？
3. **查询合理性**：是否检索了不必要的字段或行数？JOIN 表数量是否合理？别名是否清晰？
4. **运行时验证**：SQL 压测是否达标？索引有效性是否通过 EXPLAIN 验证？
5. **PO 类核对**：字段类型是否一致？继承字段是否完整？`@TableLogic` 是否配置？字段映射是否完整？