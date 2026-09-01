#!/usr/bin/env python3
"""ddl_check.py 单元测试

将 badcase 行为固化为断言式测试，并覆盖 DDL 解析与命名/注释/索引检查逻辑。
运行: python3 -m pytest tests/ -v
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ddl_check
from ddl_check import Severity

BADCASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "badcase")
)


def _badcase(name):
    return os.path.join(BADCASE_DIR, name, "input", "example.sql")


def _mandatory(issues):
    return [i for i in issues if i.severity == Severity.MANDATORY]


# ── badcase 集成断言（行为固化）────────────────────────────────────────────

def test_badcase_001_forbidden_type_and_comment():
    """禁用类型 + 缺失注释：至少检出问题。"""
    issues = ddl_check.check_file(_badcase("001-forbidden-type-and-missing-comment"))
    assert len(issues) >= 1
    assert {i.rule for i in issues}  # 规则名非空


def test_badcase_004_bad_index():
    issues = ddl_check.check_file(_badcase("004-bad-index"))
    assert len(_mandatory(issues)) >= 1


def test_badcase_005_bad_naming():
    issues = ddl_check.check_file(_badcase("005-bad-naming"))
    assert len(_mandatory(issues)) >= 2


def test_badcase_006_bad_comment():
    issues = ddl_check.check_file(_badcase("006-bad-comment"))
    assert len(_mandatory(issues)) >= 10


def test_composite_index_column_limit():
    """联合索引字段数 > 5 → 推荐；≤ 5 → 不报。"""
    def ddl_for(n):
        fields = "\n".join(f"  c{i} VARCHAR(16) COMMENT '列{i}'," for i in range(n))
        cols = ", ".join(f"c{i}" for i in range(n))
        return (f"CREATE TABLE t_ix (\n  id BIGINT COMMENT '主键',\n"
                f"{fields}\n  KEY ix_cols ({cols})\n) COMMENT='测试';\n")

    assert all(i.rule != "联合索引字段数" for i in _issues_for(ddl_for(5)))
    hit = [i for i in _issues_for(ddl_for(6)) if i.rule == "联合索引字段数"]
    assert len(hit) == 1 and "6" in hit[0].description


# ── DDL 解析 ────────────────────────────────────────────────────────────────

def test_strip_sql_comments_removes_inline():
    """strip_sql_comments 处理 -- 行注释（块注释不在其职责内）。"""
    out = ddl_check.strip_sql_comments("id BIGINT -- inline comment\n, name VARCHAR")
    assert "--" not in out
    assert "id" in out and "name" in out


def test_extract_tables_finds_create_table():
    tables = ddl_check.extract_tables(
        "CREATE TABLE t_order (\n  id BIGINT\n);\n")
    assert any(t.name == "t_order" for t in tables)


def test_extract_tables_handles_backtick():
    tables = ddl_check.extract_tables(
        "CREATE TABLE `t_user` (\n  id BIGINT\n);\n")
    assert any(t.name == "t_user" for t in tables)


# ── check_file 入口 ─────────────────────────────────────────────────────────

def test_check_file_returns_list_for_minimal_ddl():
    """最小 DDL：返回 list（结构正确，不抛异常）。"""
    ddl = (
        "CREATE TABLE t_demo (\n"
        "  id BIGINT COMMENT '主键',\n"
        "  name VARCHAR(64) COMMENT '名称'\n"
        ") COMMENT='演示表';\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(ddl)
        path = f.name
    try:
        issues = ddl_check.check_file(path)
        assert isinstance(issues, list)
        # 表名/注释合规时应无"表注释缺失"
        assert all(i.rule != "表注释缺失" for i in issues)
    finally:
        os.unlink(path)


def test_check_file_detects_reserved_table_name():
    """表名命中保留字应报强制问题。"""
    ddl = (
        "CREATE TABLE `order` (\n"
        "  id BIGINT COMMENT '主键'\n"
        ") COMMENT='订单表';\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(ddl)
        path = f.name
    try:
        issues = ddl_check.check_file(path)
        assert any(i.rule == "保留字" and i.severity == Severity.MANDATORY
                   for i in issues)
    finally:
        os.unlink(path)


# ── 辅助：写临时 DDL 并检查 ───────────────────────────────────────────────

def _issues_for(ddl_text):
    """写临时 DDL 文件并返回 check_file 结果。"""
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(ddl_text)
        path = f.name
    try:
        return ddl_check.check_file(path)
    finally:
        os.unlink(path)


def _ddl_with_field(field_line, table="t_demo"):
    """生成含指定字段行、其余必含字段齐全的最小 DDL。"""
    return (
        f"CREATE TABLE {table} (\n"
        "  id bigint COMMENT '主键',\n"
        f"  {field_line},\n"
        "  creator_id varchar(36) NOT NULL DEFAULT '' COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL DEFAULT '' COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'\n"
        ") COMMENT='demo';\n"
    )


# ── 行尾 -- 分隔线误报修复 ─────────────────────────────────────────────────

def test_comment_style_separator_not_flagged():
    """`-- ----` / `-- ===` 分隔线不得误报为注释格式违规。"""
    ddl = (
        "-- ============================================================\n"
        "-- ------------------------------------------------------------\n"
        "CREATE TABLE t_ok (\n"
        "  id bigint COMMENT '主键',\n"
        "  creator_id varchar(36) NOT NULL DEFAULT '' COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL DEFAULT '' COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'\n"
        ") COMMENT='ok';\n"
    )
    issues = _issues_for(ddl)
    assert all(i.rule != "注释格式" for i in issues)


def test_comment_style_no_space_still_flagged():
    """`--xxx`（无空格真违规）仍应报。"""
    ddl = (
        "--这行注释后没有空格\n"
        "CREATE TABLE t_bad (\n"
        "  id bigint COMMENT '主键'\n"
        ") COMMENT='bad';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "注释格式" for i in issues)


def test_comment_style_inline_after_code_flagged():
    """代码后行内 `--xxx`（无空格）→ 报，即使该行含 COMMENT。"""
    ddl = (
        "CREATE TABLE t_bad (\n"
        "  id bigint COMMENT '主键'\n"
        ") COMMENT='bad'--注释后没有空格\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "注释格式" for i in issues)


def test_comment_style_dash_in_string_not_flagged():
    """COMMENT 字符串内的 `--` → 不报。"""
    ddl = (
        "CREATE TABLE t_ok (\n"
        "  id bigint COMMENT 'a--b',\n"
        "  creator_id varchar(36) NOT NULL DEFAULT '' COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL DEFAULT '' COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'\n"
        ") COMMENT='ok';\n"
    )
    issues = _issues_for(ddl)
    assert all(i.rule != "注释格式" for i in issues)


# ── COL032 注释补充信息格式 ────────────────────────────────────────────────

def test_field_comment_paren_comma_flagged():
    """补充信息圆括号闭合后用逗号追加 → 报。"""
    issues = _issues_for(_ddl_with_field("parent_id bigint COMMENT '父参数id(0=根),支持嵌套'"))
    assert any(i.rule == "注释补充信息格式" for i in issues)


def test_field_comment_paren_ok():
    """补充信息全在圆括号内 → 不报。"""
    issues = _issues_for(_ddl_with_field("parent_id bigint COMMENT '父参数id(0=根,支持嵌套)'"))
    assert all(i.rule != "注释补充信息格式" for i in issues)


# ── COL018 泛化字段名 ──────────────────────────────────────────────────────

def test_generic_field_name_flagged():
    """泛化单一名词（remark）→ 报推荐。"""
    issues = _issues_for(_ddl_with_field("remark varchar(200) COMMENT '备注'"))
    assert any(i.rule == "泛化字段名" and i.severity == Severity.RECOMMENDED for i in issues)


def test_generic_field_name_prefixed_ok():
    """加主体前缀（merchant_remark）→ 不报。"""
    issues = _issues_for(_ddl_with_field("merchant_remark varchar(200) COMMENT '备注'"))
    assert all(i.rule != "泛化字段名" for i in issues)


# ── NAM002 缩写字典 ────────────────────────────────────────────────────────

def test_abbreviation_field_flagged():
    """字段名含未规范化写法（direction）→ 报。"""
    issues = _issues_for(_ddl_with_field("direction tinyint COMMENT '方向'"))
    assert any(i.rule == "缩写未规范化" for i in issues)


def test_abbreviation_table_flagged():
    """表名含未规范化写法（message）→ 报。"""
    issues = _issues_for(_ddl_with_field("ext varchar(50) COMMENT '扩展'", table="t_message_log"))
    assert any(i.rule == "缩写未规范化" and "表名" in i.location for i in issues)


def test_abbreviation_std_ok():
    """已用标准缩写（dir）→ 不报。"""
    issues = _issues_for(_ddl_with_field("dir tinyint COMMENT '方向'"))
    assert all(i.rule != "缩写未规范化" for i in issues)


# ── 日志/流水表必含字段豁免 ─────────────────────────────────────────────────

def test_log_table_exempt_updater_fields():
    """日志表缺 last_updater_id/last_update_time → 不报必含字段。"""
    ddl = (
        "CREATE TABLE call_log (\n"
        "  id bigint COMMENT '主键',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  content varchar(100) COMMENT '内容'\n"
        ") COMMENT='日志表';\n"
    )
    issues = _issues_for(ddl)
    assert all(i.rule != "必含字段缺失" for i in issues)


def test_log_table_still_requires_create_time():
    """日志表缺 create_time → 仍报。"""
    ddl = (
        "CREATE TABLE call_flow (\n"
        "  id bigint COMMENT '主键',\n"
        "  content varchar(100) COMMENT '内容'\n"
        ") COMMENT='流水表';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "必含字段缺失" and "create_time" in i.description for i in issues)


def test_non_log_table_requires_all():
    """普通表缺更新人字段 → 仍报。"""
    ddl = (
        "CREATE TABLE t_order (\n"
        "  id bigint COMMENT '主键',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'\n"
        ") COMMENT='订单表';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "必含字段缺失" and "last_updater_id" in i.description for i in issues)


# ── 唯一索引启发式 ─────────────────────────────────────────────────────────

def test_unique_hint_when_comment_says_unique():
    """注释含「唯一」+ 普通索引 → 建议唯一索引。"""
    ddl = (
        "CREATE TABLE t_ability (\n"
        "  id bigint COMMENT '主键',\n"
        "  ability_code varchar(36) COMMENT '能力编码(唯一)',\n"
        "  creator_id varchar(36) NOT NULL DEFAULT '' COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL DEFAULT '' COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',\n"
        "  PRIMARY KEY (id),\n"
        "  KEY ix_ability_code (ability_code)\n"
        ") COMMENT='能力表';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "建议唯一索引" and i.severity == Severity.RECOMMENDED for i in issues)


def test_unique_hint_silent_when_unique_index_exists():
    """已建 UNIQUE 索引 → 不报。"""
    ddl = (
        "CREATE TABLE t_ability (\n"
        "  id bigint COMMENT '主键',\n"
        "  ability_code varchar(36) COMMENT '能力编码(唯一)',\n"
        "  creator_id varchar(36) NOT NULL DEFAULT '' COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL DEFAULT '' COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',\n"
        "  PRIMARY KEY (id),\n"
        "  UNIQUE KEY uk_ability_code (ability_code)\n"
        ") COMMENT='能力表';\n"
    )
    issues = _issues_for(ddl)
    assert all(i.rule != "建议唯一索引" for i in issues)


# ── 解析器与工具函数 ──────────────────────────────────────────────────────

def test_strip_sql_comments_preserves_quoted():
    """引号内的 -- 保留，引号外的行尾注释去除。"""
    out = ddl_check.strip_sql_comments("a 'b--c' d -- real")
    assert "b--c" in out          # 引号内 -- 保留
    assert "real" not in out      # 引号外注释去除
    assert "a" in out and "d" in out


def test_extract_table_comment_no_paren():
    """无闭括号时返回 None。"""
    assert ddl_check.extract_table_comment("no closing paren here") is None


def test_parse_unique_constraint():
    """UNIQUE CONSTRAINT 能解析为唯一索引。"""
    ddl = (
        "CREATE TABLE t_uc (\n"
        "  id bigint COMMENT '主键',\n"
        "  code varchar(36) COMMENT '码',\n"
        "  UNIQUE CONSTRAINT uc_code (code)\n"
        ") COMMENT='uc';\n"
    )
    tbl = ddl_check.extract_tables(ddl)[0]
    assert any(i.is_unique for i in tbl.indexes)


def test_parse_skips_constraint_and_fk_lines():
    """CONSTRAINT / FOREIGN KEY 行不解析为字段或索引。"""
    ddl = (
        "CREATE TABLE t_fk (\n"
        "  id bigint COMMENT '主键',\n"
        "  oid bigint COMMENT '外键',\n"
        "  CONSTRAINT ck1 CHECK (oid > 0),\n"
        "  FOREIGN KEY (oid) REFERENCES o(id)\n"
        ") COMMENT='fk';\n"
    )
    tbl = ddl_check.extract_tables(ddl)[0]
    assert len(tbl.fields) == 2
    assert all("CONSTRAINT" not in i.raw_definition.upper() for i in tbl.indexes)


def test_parse_field_line_unparseable():
    """无法解析的行返回 None。"""
    assert ddl_check._parse_field_line(") COMMENT='x'", 1) is None
    assert ddl_check._parse_field_line("", 1) is None


def test_parse_index_line_returns_none():
    """无法识别的索引行返回 None。"""
    assert ddl_check._parse_index_line("garbage line", 1) is None


# ── 禁用子句 ─────────────────────────────────────────────────────────────

def test_forbidden_clauses_detected():
    """CHARACTER SET / COLLATE / AUTO_INCREMENT / ENGINE / ROW_FORMAT 全检出。"""
    ddl = (
        "CREATE TABLE t_bad (\n"
        "  id bigint COMMENT '主键'\n"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci "
        "AUTO_INCREMENT=100 ROW_FORMAT=DYNAMIC COMMENT='bad';\n"
    )
    issues = _issues_for(ddl)
    rules = {i.rule for i in issues}
    assert {
        "去除字符集子句", "去除字符序子句", "去除 auto_increment 子句",
        "去除 engine 子句", "去除 row_format 子句",
    } <= rules


def test_partition_detected():
    issues = _issues_for(
        "CREATE TABLE t_p (id bigint COMMENT '主键') COMMENT='p' PARTITION BY HASH(id);\n")
    assert any(i.rule == "禁止分区表" for i in issues)


def test_change_column_detected():
    issues = _issues_for("ALTER TABLE t CHANGE COLUMN a b int;\n")
    assert any(i.rule == "禁止 CHANGE COLUMN" for i in issues)


# ── 表名 / 表注释违规分支 ────────────────────────────────────────────────

TABLE_NAME_CASES = [
    ("t" + "a" * 30, "表名长度"),
    ("_bad", "表名开头"),
    ("t__u", "连续下划线"),
    ("Tbad", "表名字符"),
]


@pytest.mark.parametrize("name,rule", TABLE_NAME_CASES)
def test_table_name_violation(name, rule):
    ddl = f"CREATE TABLE {name} (\n  id bigint COMMENT '主键'\n) COMMENT='x';\n"
    issues = _issues_for(ddl)
    assert any(i.rule == rule for i in issues)


def test_table_comment_too_long():
    ddl = f"CREATE TABLE t_c (\n  id bigint COMMENT '主键'\n) COMMENT='{'表' * 65}';\n"
    issues = _issues_for(ddl)
    assert any(i.rule == "表注释长度" for i in issues)


def test_table_comment_special_char():
    ddl = "CREATE TABLE t_s (\n  id bigint COMMENT '主键'\n) COMMENT='表★注释';\n"
    issues = _issues_for(ddl)
    assert any(i.rule == "表注释特殊字符" for i in issues)


# ── 字段违规分支 ─────────────────────────────────────────────────────────

def test_field_count_too_many():
    cols = "\n".join(f"  c{i:02d} varchar(10) COMMENT '字段{i}'," for i in range(42))
    ddl = f"CREATE TABLE t_many (\n{cols}\n  id bigint COMMENT '主键'\n) COMMENT='多字段';\n"
    issues = _issues_for(ddl)
    assert any(i.rule == "字段数量" for i in issues)


FIELD_NAME_CASES = [
    ("x" * 31, "字段名长度"),
    ("_bad", "字段名开头"),
    ("a__b", "连续下划线"),
    ("Name", "字段名字符"),
]


@pytest.mark.parametrize("name,rule", FIELD_NAME_CASES)
def test_field_name_violation(name, rule):
    ddl = (
        "CREATE TABLE t_f (\n"
        f"  {name} varchar(50) COMMENT 'x',\n"
        "  id bigint COMMENT '主键'\n"
        ") COMMENT='f';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == rule for i in issues)


def test_field_comment_too_long():
    ddl = f"CREATE TABLE t_l (\n  id bigint COMMENT '{'注' * 129}'\n) COMMENT='l';\n"
    issues = _issues_for(ddl)
    assert any(i.rule == "字段注释长度" for i in issues)


def test_varchar_too_long():
    issues = _issues_for(_ddl_with_field("big varchar(600) COMMENT '长'"))
    assert any(i.rule == "varchar长度" for i in issues)


def test_char_too_long():
    issues = _issues_for(_ddl_with_field("c char(30) COMMENT '定长'"))
    assert any(i.rule == "char长度" for i in issues)


def test_field_type_unparseable_base():
    """字段类型无法识别时不抛异常（走 fallback）。"""
    issues = _issues_for(_ddl_with_field("weird xyz COMMENT '怪'"))
    assert isinstance(issues, list)


def test_parse_table_body_blank_line():
    """表体内空行被跳过，不影响字段解析。"""
    ddl = (
        "CREATE TABLE t_b (\n"
        "  id bigint COMMENT '主键',\n"
        "\n"
        "  ext varchar(50) COMMENT '扩展'\n"
        ") COMMENT='b';\n"
    )
    tbl = ddl_check.extract_tables(ddl)[0]
    assert len(tbl.fields) == 2


def test_field_name_reserved_word():
    """字段名为 MySQL 保留字（desc）→ 报保留字。"""
    ddl = (
        "CREATE TABLE t_r (\n"
        "  `desc` varchar(50) COMMENT '降序',\n"
        "  id bigint COMMENT '主键'\n"
        ") COMMENT='r';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "保留字" for i in issues)


def test_field_type_empty_string_no_crash():
    """字段类型为空（base_type_match 为 None）时静默返回。"""
    f = ddl_check.FieldInfo(name="x", raw_definition="x", line=1, type="")
    issues = []
    ddl_check.check_field_type(f, "t", issues)
    assert not issues


# ── 主键 / 外键 / 无建表 ─────────────────────────────────────────────────

def test_foreign_key_detected():
    ddl = (
        "CREATE TABLE t_fk (\n"
        "  id bigint COMMENT '主键',\n"
        "  oid bigint COMMENT '外键',\n"
        "  FOREIGN KEY (oid) REFERENCES o(id)\n"
        ") COMMENT='fk';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "外键约束" for i in issues)


def test_primary_key_not_int():
    ddl = (
        "CREATE TABLE t_pk (\n"
        "  id varchar(36) COMMENT '主键',\n"
        "  creator_id varchar(36) NOT NULL DEFAULT '' COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL DEFAULT '' COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',\n"
        "  PRIMARY KEY (id)\n"
        ") COMMENT='pk';\n"
    )
    issues = _issues_for(ddl)
    assert any(i.rule == "主键类型" for i in issues)


def test_no_create_table():
    issues = _issues_for("-- only a comment, no table\n")
    assert any(i.rule == "无建表语句" for i in issues)


# ── 报告格式化 ───────────────────────────────────────────────────────────

def test_format_report_text_with_and_without_issues():
    issues = [ddl_check.Issue(table="t", severity=Severity.MANDATORY, rule="r",
                              location="L", description="d", suggestion="s")]
    text = ddl_check.format_report_text("f.sql", issues)
    assert "DDL 审查报告" in text and "r" in text and "s" in text
    assert "检查通过" in ddl_check.format_report_text("f.sql", [])


def test_format_report_json():
    issues = [ddl_check.Issue(table="t", severity=Severity.MANDATORY, rule="r",
                              location="L", description="d")]
    data = json.loads(ddl_check.format_report_json("f.sql", issues))
    assert data["summary"]["total"] == 1
    assert data["issues"][0]["rule"] == "r"


# ── main 入口（文件/目录/空目录/json）────────────────────────────────────

def _write_tmp_sql(content):
    f = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False)
    f.write(content)
    f.close()
    return f.name


def test_main_single_file_text(monkeypatch, capsys):
    path = _write_tmp_sql("CREATE TABLE t (id bigint COMMENT '主键') COMMENT='t';\n")
    try:
        monkeypatch.setattr(sys, "argv", ["ddl_check", path])
        rc = ddl_check.main()
        assert "DDL 审查报告" in capsys.readouterr().out
        assert rc == 1   # 缺必含字段 → 有强制问题
    finally:
        os.unlink(path)


def test_main_json_format(monkeypatch, capsys):
    path = _write_tmp_sql("CREATE TABLE t (id bigint COMMENT '主键') COMMENT='t';\n")
    try:
        monkeypatch.setattr(sys, "argv", ["ddl_check", path, "--format", "json"])
        rc = ddl_check.main()
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list) and data
        assert rc == 1
    finally:
        os.unlink(path)


def test_main_directory(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "a.sql"), "w") as fh:
            fh.write("CREATE TABLE t (id bigint COMMENT '主键') COMMENT='t';\n")
        monkeypatch.setattr(sys, "argv", ["ddl_check", d])
        rc = ddl_check.main()
        assert "总计" in capsys.readouterr().out
        assert rc == 1


def test_main_no_sql_files(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(sys, "argv", ["ddl_check", d])
        rc = ddl_check.main()
        assert "未找到" in capsys.readouterr().err
        assert rc == 2


# ── 解析层放宽（表名/字段名非法字符可达 + 跨行/注释异常）────────────────────

def test_table_name_chars_reachable():
    """表名含非法字符 '-' → 「表名字符」检出；表本身仍被解析。"""
    issues = _issues_for(
        "CREATE TABLE t-order-info (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL COMMENT '最后更新时间',\n"
        "  del_flag tinyint(4) NOT NULL DEFAULT 0 COMMENT '删除标志'\n"
        ") COMMENT = 'x';\n"
    )
    rules = {i.rule for i in issues}
    assert "表名字符" in rules
    assert "无建表语句" not in rules


def test_table_name_chars_schema_qualified():
    """schema 限定的非法表名 db.t-order 同样可达。"""
    issues = _issues_for(
        "CREATE TABLE db.t-order (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL COMMENT '最后更新时间',\n"
        "  del_flag tinyint(4) NOT NULL DEFAULT 0 COMMENT '删除标志'\n"
        ") COMMENT = 'x';\n"
    )
    assert "表名字符" in {i.rule for i in issues}


def test_field_name_chars_reachable():
    """字段名含非法字符 '-' → 「字段名字符」检出。"""
    issues = _issues_for(_ddl_with_field("order-status varchar(10) COMMENT '订单状态'"))
    assert "字段名字符" in {i.rule for i in issues}


def test_backtick_bad_chars_reachable():
    """反引号包裹的非法字符表名/字段名同样可达（非反引号名不受影响）。"""
    ddl = (
        "CREATE TABLE `t-order` (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  `user-name` varchar(20) NOT NULL COMMENT '用户名',\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL COMMENT '最后更新时间',\n"
        "  del_flag tinyint(4) NOT NULL DEFAULT 0 COMMENT '删除标志'\n"
        ") COMMENT = 'x';\n"
    )
    rules = {i.rule for i in _issues_for(ddl)}
    assert "表名字符" in rules and "字段名字符" in rules


def test_create_table_paren_next_line_parsed():
    """CREATE TABLE t\\n( 跨行：表体起点扫描不吞并后续语句。"""
    tables = ddl_check.extract_tables(
        "CREATE TABLE t_a\n(\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间'\n"
        ") COMMENT = 'x';\n"
    )
    assert len(tables) == 1 and tables[0].name == "t_a"
    assert any(f.name == "creator_id" for f in tables[0].fields)


def test_multiple_tables_not_merged():
    """多建表语句：前一表体闭合后不得吞并后续 CREATE TABLE。"""
    tables = ddl_check.extract_tables(
        "CREATE TABLE t_one (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id'\n"
        ");\n"
        "CREATE TABLE t_two (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  name varchar(20) NOT NULL COMMENT '名称'\n"
        ") COMMENT = 'x';\n"
    )
    assert len(tables) == 2
    one = next(t for t in tables if t.name == "t_one")
    two = next(t for t in tables if t.name == "t_two")
    assert len(one.fields) == 1
    assert len(two.fields) == 2  # t_two 字段未被 t_one 吞掉


def test_field_continuation_no_bogus_field():
    """字段跨行定义（NOT NULL 续行）不产生垃圾字段。"""
    issues = _issues_for(
        "CREATE TABLE t_a (\n"
        "  id bigint(20)\n"
        "  NOT NULL COMMENT '主键id',\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL COMMENT '最后更新时间',\n"
        "  del_flag tinyint(4) NOT NULL DEFAULT 0 COMMENT '删除标志'\n"
        ") COMMENT = 'x';\n"
    )
    rules = {i.rule for i in issues}
    assert "字段数量" not in rules          # 续行行未变成伪字段
    assert "字段名开头" not in rules        # NOT NULL 未被当字段名


def test_hash_comment_stripped():
    """# 行注释剥除：# 行内容不污染解析；「注释符号」仍独立检出。"""
    issues = _issues_for(
        "# 用户表\n"
        "CREATE TABLE t_a (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  # 这是字段级 # 注释\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL COMMENT '最后更新时间',\n"
        "  del_flag tinyint(4) NOT NULL DEFAULT 0 COMMENT '删除标志'\n"
        ") COMMENT = 'x';\n"
    )
    rules = {i.rule for i in issues}
    assert "注释符号" in rules              # # 注释本身仍报违规
    assert "无建表语句" not in rules        # # 注释行未干扰 CREATE 解析
    assert all(i.rule != "字段数量" for i in issues)


def test_index_name_with_dash_parsed():
    """索引名含非法字符 '-' 仍被解析（命名规则可达）。"""
    issues = _issues_for(
        "CREATE TABLE t_a (\n"
        "  id bigint(20) NOT NULL COMMENT '主键id',\n"
        "  order_no varchar(36) NOT NULL COMMENT '订单编号',\n"
        "  creator_id varchar(36) NOT NULL COMMENT '创建人id',\n"
        "  create_time datetime NOT NULL COMMENT '创建时间',\n"
        "  last_updater_id varchar(36) NOT NULL COMMENT '最后更新人id',\n"
        "  last_update_time datetime NOT NULL COMMENT '最后更新时间',\n"
        "  del_flag tinyint(4) NOT NULL DEFAULT 0 COMMENT '删除标志',\n"
        "  UNIQUE KEY uk-order-no (order_no)\n"
        ") COMMENT = 'x';\n"
    )
    assert "唯一索引命名" in {i.rule for i in issues}


def test_create_table_no_body_skipped():
    """CREATE TABLE 后无表体 '('（孤立语句）→ 跳过该行，仍报「无建表语句」。"""
    issues = _issues_for("CREATE TABLE t_a;\n")
    assert "无建表语句" in {i.rule for i in issues}
