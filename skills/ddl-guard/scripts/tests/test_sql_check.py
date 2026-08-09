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
    assert not any("plain.xml" in p for p in found)
