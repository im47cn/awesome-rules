#!/usr/bin/env python3
"""ddl_check.py 单元测试

将 badcase 行为固化为断言式测试，并覆盖 DDL 解析与命名/注释/索引检查逻辑。
运行: python3 -m pytest tests/ -v
"""

import os
import sys
import tempfile

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
        assert not any(i.rule == "表注释缺失" for i in issues)
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
