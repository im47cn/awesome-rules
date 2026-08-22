# 数据库设计与审查：ddl-guard

## 1. 背景

看到团队小伙伴根据 DBA 反馈整改 SQL 语句，在深入了解后发现数据库设计有规范但缺乏落地工具，导致团队协作和研发过程的低效。结合研发同学已经大面积使用 AI 编程工具的实际现状，特整理并发布"数据库设计与自动审查 skills"。

- 公司规范：https://doc.weixin.qq.com/doc/w3_AGkAPwadAMsCNa4E6E7GMSkGy6Jak?scode=ANMAyAcrABERs7BLtKAXwABganAJc
- 审查实务：DB 建表审核规则

## 2. 目标

- 在数据库设计阶段符合 DBA 制定的设计规范和审查标准
- 自动完成数据库设计的审查和整改

## 3. 它能检查什么

脚本自动覆盖 20+ 条规则（粗筛），AI 再补充人工判断（精审）：

| 检查类别 | 检查项示例 |
|---|---|
| 必含字段 | 表名前缀、审计字段命名（`last_updater_id` 等） |
| 字段类型 | 禁用 TEXT/BLOB，禁用 bigint DEFAULT '' |
| 索引规范 | 前缀统一 `ix_`、命名清晰 |
| 类型一致性 | 同概念字段跨表类型必须一致 |
| 注释规范 | 表注释、字段注释、枚举值风格 |
| 字段命名 | 禁复数、禁泛化词、一词一义 |
| DML 审查 | MyBatis Mapper.xml 动态 SQL、`@TableName` PO 类 |

> 人工补充规则（拆表建议、字段语义判断等）见 `ddl-manual-rules.md` / `sql-manual-rules.md`。

## 4. 特点

- **标准**：封装公司数据库设计规范
- **敏捷**：支持插件化安装、渐进式加载，**脚本化处理过程（8 线程并发），不仅节约 token，还能避免敏感信息泄露**——脚本做粗筛（不上传代码），AI 只看摘要做精审
- **全面**：支持 DDL（`*.sql` 文件）、DML（支持 MyBatis 的 Mapper.xml 文件、基于 MyBatis-Plus 用 `@TableName` 注解的 PO 类）的审查
- **质量**：测试覆盖率 98%，pytest 90% 门禁守护，回归防退化
- **共创**：支持贡献 badcase；同时提供了回归测试脚本，可以自己调优提示词后再提交代码仓库

## 5. 风险提示

本工具旨在减少审查交互次数、提前规避常见问题，不能完全替代 DBA 审核环节。

## 6. 安装方法

见《【Skills Hub】awesome-rules 做懂技术集团的 AI 搭子》。

---

## 7. 数据库设计案例

### 案例 1：从需求到合规 DDL

**背景**：需要设计一张"应用权限点"关联表，记录应用与权限点的绑定关系。

**第 1 步**：跟 AI 描述需求

> 帮我设计一张表，记录应用和权限点的绑定关系，包含授权时间、授权人。

**第 2 步**：使用 `ddl-guard` 技能设计

AI 读取 `steering/database-design-specification.md` 规范后，生成合规 DDL：

```sql
CREATE TABLE `gdc_plf_app_permission` (
  `id`                BIGINT(20)   NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `app_pk_id`         BIGINT(20)   NOT NULL DEFAULT '0'    COMMENT 'App表主键id',
  `perm_id`           VARCHAR(128) NOT NULL DEFAULT ''     COMMENT '权限点编码',
  `grant_time`        DATETIME     NOT NULL                 COMMENT '授权时间',
  `last_updater_id`   VARCHAR(64)  NOT NULL DEFAULT ''     COMMENT '最后更新人',
  `last_update_time`  DATETIME     NOT NULL                 COMMENT '最后更新时间',
  `del_flag`          TINYINT(1)   NOT NULL DEFAULT '0'    COMMENT '逻辑删除(0-有效 1-删除)',
  PRIMARY KEY (`id`),
  INDEX `ix_app_pk_id` (`app_pk_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用权限点关联表';
```

**为什么这样设计？**

| 检查项 | 是否合规 | 说明 |
|---|---|---|
| 表名前缀 | ✅ | `gdc_plf_` 统一前缀 |
| 必含字段 | ✅ | `last_updater_id` / `last_update_time` / `del_flag` |
| 字段类型 | ✅ | 无 TEXT/BLOB，无 bigint DEFAULT '' |
| 索引前缀 | ✅ | `ix_` 前缀 |
| 注释 | ✅ | 表注释 + 字段注释，枚举值用 `0-xxx 1-xxx` 风格 |

**第 3 步**：脚本自检

```bash
python3 skills/ddl-guard/scripts/ddl_check.py app_permission.sql
```

退出码 `0`，通过。

---

## 8. 审查数据库设计案例

### 案例 1：审查 DDL

> 8 张表，脚本 1 秒扫出 34 项强制问题——这在过去需要 DBA 逐表检查半小时。

```bash
# 使用 ddl-guard 技能审查 *.sql
python3 skills/ddl-guard/scripts/ddl_check.py 202607071777.sql
```

**审查报告：202607071777.sql**

- 审查日期：2026-07-29
- 表数量：8
- 【强制】问题：34 项
- 【推荐】问题：4 项
- 结论：❌ 不可通过审核

**问题汇总（按类型聚合）**：

#### 1. 必含字段名不合规（全部 8 张表）【强制】

所有表的 `updater_id` / `update_time` 不符合必含字段规范，必须改名：

| 当前字段名 | 正确字段名 |
|---|---|
| `updater_id` | `last_updater_id` |
| `update_time` | `last_update_time` |

涉及全部 8 张表，共 16 处。

#### 2. 索引命名前缀错误（6 张表，7 处）【强制】

前缀不符合规范，应统一改为 `ix_`：

| 表 | 当前索引名 | 正确索引名 |
|---|---|---|
| gdc_plf_company | `idx_credit_code` | `ix_credit_code` |
| gdc_plf_company | `idx_company_name` | `ix_company_name` |
| gdc_plf_app | `idx_company_id` | `ix_company_id` |
| gdc_plf_api | `idx_api_code` | `ix_api_code` |
| gdc_plf_api_param | `idx_api_id` | `ix_api_id` |
| gdc_plf_permission_point | `idx_perm_code` | `ix_perm_code` |
| gdc_plf_field_mapping | `idx_app_id_api_id_direction` | `ix_app_id_api_id_direction` |

#### 3. 禁用类型 TEXT（gdc_plf_api，3 处）【强制】

| 字段 | 当前类型 | 建议 |
|---|---|---|
| `req_example` | text | varchar(500) 或拆表 |
| `resp_example` | text | varchar(500) 或拆表 |
| `detail_desc` | text | varchar(500) 或拆表 |

#### 4. bigint 类型 DEFAULT '' 不合法（2 张表，3 处）【强制】

字段不能用空字符串做默认值，应改为 `DEFAULT 0`：

| 表 | 字段 | 当前定义 |
|---|---|---|
| gdc_plf_app_permission | `app_id` | `bigint(20) NOT NULL DEFAULT ''` |
| gdc_plf_app_permission | `perm_id` | `bigint(20) NOT NULL DEFAULT ''` |
| gdc_plf_field_mapping | `app_id` | `bigint(20) NOT NULL DEFAULT ''` |

#### 5. 同概念字段类型不一致（2 张表）【强制】

`perm_id`（权限点主键）在两张表中类型矛盾：

| 表 | 字段 | 类型 |
|---|---|---|
| gdc_plf_permission_api_rel | `perm_id` | varchar(128) |
| gdc_plf_app_permission | `perm_id` | bigint(20) |

存储相同数据的字段类型必须一致，否则导致隐式转换、索引失效。

#### 6. 一词多义（3 张表）【强制】

`app_id` 在不同表中语义不同，造成歧义：

| 表 | 字段 | 实际含义 |
|---|---|---|
| gdc_plf_app | `app_id varchar(64)` | AppID 字符串（业务标识） |
| gdc_plf_app_permission | `app_id bigint(20)` | App 表主键 id |
| gdc_plf_field_mapping | `app_id bigint(20)` | App 表主键 id |

引用 app 表主键的应命名为 `app_pk_id` 或统一为 bigint 引用 id，app 表内的 AppID 字段改名如 `app_code`。

#### 7. 注释格式问题（4 处）【强制】

| 表 | 字段 | 当前注释 | 问题 | 建议 |
|---|---|---|---|---|
| gdc_plf_api | `api_version` | `接口版本(V1/V2)` | 枚举值用了圆括号 | 枚举值统一风格 |
| gdc_plf_api_param | `parent_id` | `父节点id,0为根` | 补充信息未用圆括号 | `父节点id(0表示根节点)` |
| gdc_plf_api_param | `param_scope` | `参数范围[10-Header,...]` | 枚举值混合英文 | 选定一个名称，另一个放括号 |
| gdc_plf_field_mapping | `prior_value` | `优先值/默认值` | 含义模糊，"/"表达不清 | 明确语义 |

#### 8. 字段名复数形式（1 处）【推荐】

| 表 | 字段 | 建议 |
|---|---|---|
| gdc_plf_company | `biz_lines` | 改为 `biz_line`（不使用复数） |

#### 9. del_flag 缺失（2 张表）【推荐】

| 表 | 说明 |
|---|---|
| gdc_plf_permission_api_rel | 无逻辑删除字段 |
| gdc_plf_app_permission | 无逻辑删除字段 |

如确为纯关联表不做逻辑删除可豁免，但需确认业务需求。

#### 10. 字段未设 NOT NULL 及默认值（1 处）【推荐】

| 表 | 字段 | 当前定义 | 建议 |
|---|---|---|---|
| gdc_plf_app_permission | `grant_time` | `datetime DEFAULT NULL` | 设 NOT NULL 或指定默认值 |

#### 11. 泛化词「业务」【参考】

多张表的 `biz_line` 字段及注释含「业务线」。属行业通用术语，可保留；若严格执行泛化词规避，可考虑改为 `trade_line` 等。

**按表分布**：

| 表 | 强制 | 推荐 | 小计 |
|---|---|---|---|
| gdc_plf_company | 4 | 1 | 5 |
| gdc_plf_app | 3 | 0 | 3 |
| gdc_plf_api | 6 | 0 | 6 |
| gdc_plf_api_param | 3 | 0 | 3 |
| gdc_plf_permission_point | 3 | 0 | 3 |
| gdc_plf_permission_api_rel | 3 | 1 | 4 |
| gdc_plf_app_permission | 5 | 2 | 7 |
| gdc_plf_field_mapping | 5 | 0 | 5 |
| 跨表（perm_id/app_id） | 2 | 0 | 2 |
| **合计** | **34** | **4** | **38** |

> **结论**：不可通过审核。核心问题是必含字段命名（全量）、索引前缀（全量）和 TEXT 类型，修复后需重新提交。

---

### 案例 2：审查 DML（MyBatis SQL + PO 类）

```bash
# 审查数据库设计（如果不好使就明确使用 skill）
python3 skills/ddl-guard/scripts/sql_check.py src/
```

脚本自动扫描：

- Mapper XML 文件（解析 `<if>` / `<where>` / `<foreach>` 等动态标签和 `<include>` 引用）
- MyBatis-Plus `@TableName` 注解的 PO 类（检查表名/字段命名规范、必含字段）

> 众人拾柴火焰高——欢迎大家贡献更多 DML 审查案例。
