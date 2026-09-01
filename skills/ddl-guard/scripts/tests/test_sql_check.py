#!/usr/bin/env python3
"""sql_check.py 单元测试

将 badcase 行为固化为断言式测试，并覆盖各检查规则与 MyBatis XML 解析逻辑。
运行: python3 -m pytest tests/ -v
"""

import os
import sys
import tempfile

# 确保脚本在 Python path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sql_check
from sql_check import Severity

BADCASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "badcase")
)


def _badcase(name, filename):
    return os.path.join(BADCASE_DIR, name, "input", filename)


def run_statement(sql, stmt_type="select", stmt_id="testStmt"):
    """通过 check_statement 跑全部检查，返回 issues。"""
    issues = []
    sql_check.check_statement(sql, stmt_type, stmt_id, "f.xml", issues)
    return issues


# ── badcase 集成断言（行为固化）────────────────────────────────────────────

def test_badcase_002_where_function():
    """WHERE 函数转换：P2 修复后精确 7 条推荐问题，每语句各 1 条不重复。"""
    issues = sql_check.check_file(_badcase("002-bad-where-function", "test_mapper.xml"))
    where_issues = [i for i in issues if i.rule == "WHERE避免函数转换"]
    assert len(where_issues) == 7
    assert all(i.severity == Severity.RECOMMENDED for i in where_issues)
    # 7 个违规语句各命中 1 条
    assert len({i.statement_id for i in where_issues}) == 7


def test_badcase_003_bad_join_has_mandatory():
    """坏 JOIN：含强制问题（多表关联字段前缀等）。"""
    issues = sql_check.check_file(_badcase("003-bad-join", "test_mapper.xml"))
    mandatory = [i for i in issues if i.severity == Severity.MANDATORY]
    assert len(mandatory) >= 3


# ── 单规则检出（通过 check_statement 覆盖全部 check_*）─────────────────────

def test_select_star_mandatory():
    issues = run_statement("SELECT * FROM t_user")
    assert any(i.rule == "禁止SELECT *" and i.severity == Severity.MANDATORY
               for i in issues)


def test_count_field_mandatory():
    issues = run_statement("SELECT COUNT(name) FROM t_user")
    assert any(i.rule == "禁止count(字段)" for i in issues)


def test_where_required_mandatory():
    issues = run_statement("SELECT id FROM t_user")
    assert any(i.rule == "必须带WHERE" for i in issues)


def test_where_function_date():
    issues = run_statement(
        "SELECT id FROM t_order WHERE DATE_FORMAT(create_time, '%Y%m') = '202401'")
    assert any(i.rule == "WHERE避免函数转换" for i in issues)


def test_where_function_left_no_duplicate():
    """P2 修复回归：left/right 检出且不与通用函数重复告警。"""
    issues = run_statement("SELECT id FROM t_order WHERE LEFT(order_no, 3) = 'ORD'")
    fns = [i for i in issues if i.rule == "WHERE避免函数转换"]
    assert len(fns) == 1


def test_bad_alias_recommended():
    issues = run_statement(
        "SELECT a.id FROM t_order a JOIN t_user b ON a.uid = b.id")
    assert any(i.rule == "别名含义清晰" for i in issues)


def test_left_like_recommended():
    issues = run_statement("SELECT id FROM t_user WHERE name LIKE '%abc'")
    assert any(i.rule == "避免左模糊" for i in issues)


def test_right_join_recommended():
    issues = run_statement(
        "SELECT a.id FROM t_order a RIGHT JOIN t_user b ON a.uid = b.id")
    assert any(i.rule == "避免RIGHT JOIN" for i in issues)


def test_inner_join_abbreviation():
    issues = run_statement(
        "SELECT a.id FROM t_order a JOIN t_user b ON a.uid = b.id")
    assert any(i.rule == "INNER JOIN 不简写" for i in issues)


def test_insert_columns_mandatory():
    issues = run_statement("INSERT INTO t_order VALUES (1, 2)", stmt_type="insert")
    assert any(i.rule == "INSERT列字段" for i in issues)


def test_ddl_in_app_mandatory():
    issues = run_statement("ALTER TABLE t_order ADD COLUMN x INT", stmt_type="update")
    assert any(i.rule == "禁止DDL操作" for i in issues)


def test_clean_select_no_issue():
    issues = run_statement("SELECT id, name FROM t_user WHERE id = 1")
    assert issues == []


# ── MyBatis XML 解析与 check_file ───────────────────────────────────────────

def test_check_file_clean_xml():
    clean = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.T">
  <select id="q" resultType="T">SELECT id, name FROM t_user WHERE id = 1</select>
</mapper>"""
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(clean)
        path = f.name
    try:
        assert sql_check.check_file(path) == []
    finally:
        os.unlink(path)


def test_check_file_parse_error():
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write("<mapper><select id='x'>")
        path = f.name
    try:
        issues = sql_check.check_file(path)
        assert len(issues) == 1
        assert issues[0].rule == "XML解析错误"
        assert issues[0].severity == Severity.MANDATORY
    finally:
        os.unlink(path)


def test_strip_dynamic_tags_resolves_where_tag():
    """<where> 作为子元素时解析为 WHERE 子句，去除前导 AND/OR。"""
    import xml.etree.ElementTree as ET
    xml_str = "<select id='q'><where><if test='x'>AND a = 1</if></where></select>"
    root = ET.fromstring(xml_str)
    sql = sql_check.strip_dynamic_tags(root)
    assert "WHERE" in sql.upper()
    assert "a = 1" in sql


# ── PO 类检查（@TableName 解析与命名规范）──────────────────────────────────

def test_camel_to_snake():
    assert sql_check.camel_to_snake("userName") == "user_name"
    assert sql_check.camel_to_snake("UserPO") == "user_po"


def test_parse_po_class_extracts_table_and_fields():
    java = '''@TableName("t_user")
public class UserPO {
    @TableId("id")
    private Long id;
    private String userName;
}'''
    po = sql_check.parse_po_class(java, "UserPO.java")
    assert po is not None
    assert po.table_name == "t_user"
    assert po.class_name == "UserPO"
    cols = {f.column_name for f in po.fields}
    assert "id" in cols and "user_name" in cols


def test_parse_po_class_empty_annotation_infers_from_class():
    """@TableName() 空参时从类名推断（UserPO → user）。"""
    java = '''@TableName()
public class UserPO {
    private Long id;
}'''
    po = sql_check.parse_po_class(java, "x.java")
    assert po is not None
    assert po.table_name == "user"


def test_parse_po_class_non_po_returns_none():
    assert sql_check.parse_po_class("public class X { }", "x.java") is None


def _write_tmp_java(content):
    with tempfile.NamedTemporaryFile("w", suffix=".java", delete=False) as f:
        f.write(content)
        return f.name


def test_check_po_file_table_name_too_long():
    long_table = "t_" + "a" * 30  # 超过 30 字符
    path = _write_tmp_java(
        f'@TableName("{long_table}")\npublic class XPO {{\n'
        '    @TableId("id")\n    private Long id;\n}}')
    try:
        issues = sql_check.check_po_file(path)
        assert any(i.rule == "PO表名长度" for i in issues)
    finally:
        os.unlink(path)


def test_check_po_file_clean_returns_list():
    java = '''@TableName("t_user")
public class UserPO {
    @TableId("id")
    private Long id;
    private String name;
}'''
    path = _write_tmp_java(java)
    try:
        issues = sql_check.check_po_file(path)
        assert isinstance(issues, list)
    finally:
        os.unlink(path)


def test_check_po_file_non_po_returns_none():
    path = _write_tmp_java("public class NotPo { private Long id; }")
    try:
        assert sql_check.check_po_file(path) is None
    finally:
        os.unlink(path)


# ── <include> 解析与 mapper 识别 ────────────────────────────────────────────

def _write_tmp_xml(content):
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(content)
        return f.name


def test_resolve_includes_exact_refid():
    """策略1: <include refid> 精确匹配 <sql id> 并内联其子元素。"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(
        '<mapper>'
        '<sql id="cond"><if test="x">a = 1</if></sql>'
        '<select id="q">SELECT 1 <include refid="cond"/></select>'
        '</mapper>')
    sql = sql_check.extract_sql_from_element(root.find("select"), root)
    assert "a = 1" in sql


def test_resolve_includes_short_name_with_namespace():
    """策略2: refid 含命名空间前缀，按短名（最后一段）匹配。"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(
        '<mapper>'
        '<sql id="cond"><if test="x">b = 2</if></sql>'
        '<select id="q">SELECT 1 <include refid="com.example.Mapper.cond"/></select>'
        '</mapper>')
    sql = sql_check.extract_sql_from_element(root.find("select"), root)
    assert "b = 2" in sql


def test_resolve_includes_unmatched_runs_multilevel_suffix():
    """策略3: refid 短名无匹配时遍历多级后缀（覆盖循环体）；仍未匹配则不内联。"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(
        '<mapper>'
        '<sql id="cond"><if test="x">c = 3</if></sql>'
        '<select id="q">SELECT 1 <include refid="foo.bar"/></select>'
        '</mapper>')
    sql = sql_check.extract_sql_from_element(root.find("select"), root)
    assert "c = 3" not in sql  # refid=foo.bar 无匹配，片段未内联


def test_resolve_includes_skips_sql_without_id():
    """无 id 的 <sql> 片段被跳过，不影响后续匹配。"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(
        '<mapper>'
        '<sql>no id here</sql>'
        '<sql id="cond"><if test="x">ok</if></sql>'
        '<select id="q">SELECT 1 <include refid="cond"/></select>'
        '</mapper>')
    sql = sql_check.extract_sql_from_element(root.find("select"), root)
    assert "ok" in sql


def test_resolve_includes_skips_include_without_refid():
    """无 refid 的 <include> 被跳过，不抛异常。"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(
        '<mapper><select id="q">SELECT 1 <include/></select></mapper>')
    sql = sql_check.extract_sql_from_element(root.find("select"), root)
    assert "SELECT 1" in sql


def test_is_mapper_detects_statement():
    path = _write_tmp_xml('<mapper><select id="q">SELECT 1</select></mapper>')
    try:
        assert sql_check.is_mapper(path) is True
    finally:
        os.unlink(path)


def test_is_mapper_rejects_plain_xml():
    path = _write_tmp_xml('<root><x>1</x></root>')
    try:
        assert sql_check.is_mapper(path) is False
    finally:
        os.unlink(path)


def test_is_mapper_rejects_non_xml(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("select")
    assert sql_check.is_mapper(str(f)) is False


def test_is_mapper_rejects_broken_xml():
    path = _write_tmp_xml('<mapper><select>')  # 未闭合
    try:
        assert sql_check.is_mapper(path) is False
    finally:
        os.unlink(path)


def test_find_mybatis_files_single(tmp_path):
    f = tmp_path / "m.xml"
    f.write_text('<mapper><select id="q">SELECT 1</select></mapper>')
    assert sql_check.find_mybatis_files(str(f)) == [str(f)]


def test_find_mybatis_files_dir_filters_non_mapper(tmp_path):
    (tmp_path / "m.xml").write_text('<mapper><select id="q">SELECT 1</select></mapper>')
    (tmp_path / "plain.xml").write_text('<root/>')
    found = sql_check.find_mybatis_files(str(tmp_path))
    assert any("m.xml" in p for p in found)
    assert all("plain.xml" not in p for p in found)


# ── strip_dynamic_tags 各动态标签分支 ──────────────────────────────────────

def _strip(xml_str):
    import xml.etree.ElementTree as ET
    return sql_check.strip_dynamic_tags(ET.fromstring(xml_str))


def test_strip_set_tag():
    sql = _strip("<update id='u'><set><if test='x'>a=1,</if></set></update>")
    assert "SET" in sql.upper() and "a=1" in sql


def test_strip_foreach_tag():
    sql = _strip("<select id='q'><foreach collection='c' item='i'>#{i}</foreach></select>")
    assert "(" in sql and ")" in sql


def test_strip_choose_when_otherwise():
    sql = _strip(
        "<select id='q'><choose><when test='x'>a=1</when>"
        "<otherwise>b=2</otherwise></choose></select>")
    assert "a=1" in sql


def test_strip_trim_tag():
    sql = _strip("<select id='q'><trim prefix='WHERE'><if test='x'>a=1</if></trim></select>")
    assert "a=1" in sql


def test_strip_when_otherwise_direct():
    sql = _strip("<select id='q'><when test='x'>a=1</when></select>")
    assert "a=1" in sql


def test_strip_unknown_tag_passthrough():
    sql = _strip("<select id='q'><custom>x = 1</custom></select>")
    assert "x = 1" in sql


# ── parse_po_class 注解各形式 ─────────────────────────────────────────────

def test_parse_po_class_value_form_tableid():
    """TableId value='id' 形式（覆盖 658-660 分支）。"""
    java = '''@TableName("t_user")
public class UserPO {
    @TableId(value = "user_id")
    private Long id;
}'''
    po = sql_check.parse_po_class(java, "x.java")
    assert po.fields[0].column_name == "user_id"
    assert po.fields[0].is_id is True


def test_parse_po_class_tablefield_value_and_plain():
    """TableField value= 与 plain 两种形式。"""
    java = '''@TableName("t_user")
public class UserPO {
    @TableField(value = "nick_name")
    private String name;
    @TableField("age_val")
    private Integer age;
}'''
    po = sql_check.parse_po_class(java, "x.java")
    cols = {f.column_name for f in po.fields}
    assert "nick_name" in cols and "age_val" in cols


def test_parse_po_class_tablefield_exist_false_skipped():
    """@TableField(exist = false) 字段不入列。"""
    java = '''@TableName("t_user")
public class UserPO {
    @TableField(exist = false)
    private String transientField;
    @TableId("id")
    private Long id;
}'''
    po = sql_check.parse_po_class(java, "x.java")
    cols = {f.column_name for f in po.fields}
    assert "transient_field" not in cols


def test_parse_po_class_extends_base_detected():
    """继承 Base/Entity/Model 基类的 PO → extends_base=True。"""
    java = '''@TableName("t_user")
public class UserPO extends BaseEntity {
    @TableId("id")
    private Long id;
}'''
    po = sql_check.parse_po_class(java, "x.java")
    assert po.extends_base is True


def test_parse_po_class_static_field_skipped():
    """static 字段不入列（覆盖 646 分支）。"""
    java = '''@TableName("t_user")
public class UserPO {
    public static final String CONST = "x";
    @TableId("id")
    private Long id;
}'''
    po = sql_check.parse_po_class(java, "x.java")
    cols = {f.column_name for f in po.fields}
    assert "const" not in cols


# ── check_po_table_name / field_names / required_fields 各规则 ─────────────

def _po(table="t_user", fields=None, extends_base=False):
    flds = fields or [sql_check.PoFieldInfo("id", "id", "Long", True)]
    return sql_check.PoClassInfo(table, "XPO", "x.java", flds, extends_base)


def test_check_po_table_name_prefix_and_underscore():
    issues = []
    sql_check.check_po_table_name(_po(table="Desc__Order"), issues)
    rules = {i.rule for i in issues}
    assert "PO表名开头" in rules
    assert "PO表名连续下划线" in rules


def test_check_po_table_name_reserved():
    """表名恰为保留字（lower 后精确匹配）。"""
    issues = []
    sql_check.check_po_table_name(_po(table="desc"), issues)
    assert any(i.rule == "PO表名保留字" for i in issues)


def test_check_po_table_name_bad_chars():
    issues = []
    sql_check.check_po_table_name(_po(table="t-user"), issues)  # 含连字符
    assert any(i.rule == "PO表名字符" for i in issues)


def test_check_po_field_names_prefix_underscore_dup():
    issues = []
    sql_check.check_po_field_names(_po(fields=[
        sql_check.PoFieldInfo("id", "id", "Long", True),
        sql_check.PoFieldInfo("x", "Desc__Col", "String"),  # 大写开头 + 连续下划线
        sql_check.PoFieldInfo("dup", "id", "int"),  # 与 id 重复
    ]), issues)
    rules = {i.rule for i in issues}
    assert "PO字段名开头" in rules
    assert "PO字段名连续下划线" in rules
    assert "PO字段重复" in rules


def test_check_po_field_names_reserved():
    """列名恰为保留字（lower 后精确匹配）。"""
    bad = sql_check.PoFieldInfo("x", "desc", "String")
    issues = []
    sql_check.check_po_field_names(_po(fields=[bad]), issues)
    assert any(i.rule == "PO字段名保留字" for i in issues)


def test_check_po_required_fields_missing():
    """未继承基类且缺必含字段 → 报缺失。"""
    issues = []
    sql_check.check_po_required_fields(_po(extends_base=False), issues)
    rules = {i.rule for i in issues}
    assert "PO必含字段缺失" in rules
    assert "PO缺少del_flag" in rules


def test_check_po_required_fields_extends_base_skipped():
    """继承基类 → 跳过必含字段检查。"""
    issues = []
    sql_check.check_po_required_fields(_po(extends_base=True), issues)
    assert not issues


# ── find_po_files / check_po_file 异常 ─────────────────────────────────────

def test_find_po_files_single_file(tmp_path):
    f = tmp_path / "A.java"
    f.write_text('@TableName("t_a")\npublic class APO {}')
    assert sql_check.find_po_files(str(f)) == [str(f)]


def test_find_po_files_dir(tmp_path):
    (tmp_path / "A.java").write_text('@TableName("t_a") class APO {}')
    (tmp_path / "B.java").write_text('class B {}')  # 非 PO
    found = sql_check.find_po_files(str(tmp_path))
    assert any("A.java" in p for p in found)
    assert all("B.java" not in p for p in found)


def test_find_po_files_nonexistent_path():
    assert sql_check.find_po_files("/nonexistent/path_xyz") == []


def test_check_po_file_read_error_returns_none(tmp_path):
    """文件不可读（目录）→ 返回 None。"""
    assert sql_check.check_po_file(str(tmp_path)) is None


# ── format_report_text / format_report_json ────────────────────────────────

def test_format_report_text_clean():
    assert "检查通过" in sql_check.format_report_text("f.xml", [])


def test_format_report_text_with_issues():
    issues = [sql_check.Issue("f.xml", "q", "select", Severity.MANDATORY,
                              "禁止SELECT *", "loc", "desc", "sug")]
    text = sql_check.format_report_text("f.xml", issues)
    assert "强制" in text
    assert "禁止SELECT *" in text
    assert "建议" in text


def test_format_report_json_structure():
    issues = [sql_check.Issue("f.xml", "q", "select", Severity.RECOMMENDED,
                              "避免RIGHT JOIN", "loc", "desc", "sug")]
    import json
    data = json.loads(sql_check.format_report_json("f.xml", issues))
    assert data["summary"]["total"] == 1
    assert data["summary"]["recommended"] == 1
    assert data["issues"][0]["rule"] == "避免RIGHT JOIN"


# ── main() CLI 全分支 ──────────────────────────────────────────────────────

def test_main_no_targets_exit2(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sql_check.py", str(tmp_path)])
    assert sql_check.main() == 2


def test_main_text_output_with_violations(tmp_path, monkeypatch, capsys):
    (tmp_path / "m.xml").write_text(
        '<mapper><select id="q">SELECT * FROM t_user</select></mapper>')
    monkeypatch.setattr(sys, "argv", ["sql_check.py", str(tmp_path)])
    code = sql_check.main()
    out = capsys.readouterr().out
    assert code == 1  # 有强制问题
    assert "总计" in out


def test_main_json_output(tmp_path, monkeypatch, capsys):
    (tmp_path / "m.xml").write_text(
        '<mapper><select id="q">SELECT id FROM t_user</select></mapper>')
    monkeypatch.setattr(sys, "argv", ["sql_check.py", str(tmp_path), "--format", "json"])
    code = sql_check.main()
    import json
    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == 1  # 缺 WHERE 强制
    assert isinstance(data, list)


def test_main_clean_po_dir_exit0(tmp_path, monkeypatch, capsys):
    """合规 PO 类目录 → exit 0。"""
    (tmp_path / "User.java").write_text(
        '@TableName("t_user")\n'
        'public class UserPO extends BaseEntity {\n'
        '    @TableId("id")\n    private Long id;\n}')
    monkeypatch.setattr(sys, "argv", ["sql_check.py", str(tmp_path)])
    assert sql_check.main() == 0


def test_bad_alias_backtick_table():
    """反引号包裹表名的别名检查可达（`t-order` 表名不阻断别名规则）。"""
    issues = run_statement("SELECT * FROM `t-order` t1 WHERE id = 1")
    assert any(i.rule == "别名含义清晰" for i in issues)


def test_insert_columns_backtick_table():
    """反引号包裹表名的 INSERT 缺字段列表仍检出。"""
    issues = run_statement("INSERT INTO `t-order` VALUES (1, 2)", stmt_type="insert")
    assert any(i.rule == "INSERT列字段" for i in issues)
