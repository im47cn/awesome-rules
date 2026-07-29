#!/usr/bin/env python3
"""
MyBatis SQL 规范检查脚本
检查 MyBatis mapper XML 中的 DQL/DML 语句是否符合数据库设计开发规范。

用法:
  python3 sql_check.py <file_or_dir> [--format text|json]

退出码: 0=通过, 1=有强制问题, 2=运行错误
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum



class Severity(Enum):
    MANDATORY = "强制"
    RECOMMENDED = "推荐"


@dataclass
class Issue:
    file: str
    statement_id: str
    statement_type: str  # select / insert / update / delete
    severity: Severity
    rule: str
    location: str
    description: str
    suggestion: str = ""


# ── MyBatis SQL 提取 ────────────────────────────────────────────────────


def strip_dynamic_tags(elem: ET.Element) -> str:
    """递归提取 Element 的文本内容，将 MyBatis 动态标签转换为等效 SQL 片段。"""
    parts = []
    if elem.text:
        parts.append(elem.text)

    for child in elem:
        tag = child.tag.lower()

        if tag == "if":
            inner = strip_dynamic_tags(child)
            if inner.strip():
                parts.append(f" {inner} ")
        elif tag == "where":
            inner = strip_dynamic_tags(child).strip()
            inner = re.sub(r"^(AND|OR)\s+", "", inner, flags=re.IGNORECASE).strip()
            if inner:
                parts.append(f" WHERE {inner} ")
        elif tag == "set":
            inner = strip_dynamic_tags(child).strip()
            inner = re.sub(r",\s*$", "", inner).strip()
            if inner:
                parts.append(f" SET {inner} ")
        elif tag == "foreach":
            inner = strip_dynamic_tags(child).strip()
            parts.append(f" ({inner}) ")
        elif tag in ("choose",):
            for sub in child:
                if sub.tag.lower() in ("when", "otherwise"):
                    parts.append(f" {strip_dynamic_tags(sub)} ")
                    break
        elif tag in ("when", "otherwise"):
            parts.append(f" {strip_dynamic_tags(child)} ")
        elif tag == "trim":
            inner = strip_dynamic_tags(child)
            parts.append(f" {inner} ")
        elif tag == "include":
            pass  # refid 已在外部解析
        elif tag == "bind":
            pass
        elif tag == "sql":
            pass
        else:
            parts.append(f" {strip_dynamic_tags(child)} ")

        if child.tail:
            parts.append(child.tail)

    return "".join(parts)


def resolve_includes(elem: ET.Element, root: ET.Element) -> ET.Element:
    """解析 <include refid='...'> 标签，将引用的 <sql> 片段内联。"""
    sql_fragments = {}
    for sql_el in root.findall(".//sql"):
        sid = sql_el.get("id")
        if sid:
            sql_fragments[sid] = sql_el

    def _resolve(e: ET.Element):
        for child in list(e):
            if child.tag.lower() == "include":
                refid = child.get("refid", "")
                # 尝试去前缀匹配（namespace.id → id）
                refid_short = refid.split(".")[-1]
                frag = sql_fragments.get(refid)
                if frag is None:
                    frag = sql_fragments.get(refid_short)
                if frag is not None:
                    idx = list(e).index(child)
                    e.remove(child)
                    for i, sub in enumerate(list(frag)):
                        e.insert(idx + i, sub)
                        _resolve(sub)
            else:
                _resolve(child)

    _resolve(elem)
    return elem


def extract_sql_from_element(elem: ET.Element, root: ET.Element) -> str:
    """从 MyBatis XML 元素提取纯 SQL 文本。"""
    elem = resolve_includes(elem, root)
    raw = strip_dynamic_tags(elem)
    # 移除 XML 注释
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    # 移除 SQL 行注释 (-- ...)
    lines = raw.split("\n")
    cleaned = []
    for line in lines:
        # 不在引号内的 -- 注释
        stripped = re.sub(r"(?<!['\"])--.*$", "", line)
        cleaned.append(stripped)
    raw = "\n".join(cleaned)
    # 合并多行、压缩空白
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def normalize_sql(sql: str) -> str:
    """将 MyBatis #{} / ${} 占位符替换为通用占位符，便于后续正则匹配。"""
    sql = re.sub(r"#\{[^}]*\}", "?", sql)
    sql = re.sub(r"\$\{[^}]*\}", "?", sql)
    return sql


# ── 规则检查函数 ────────────────────────────────────────────────────────


def check_select_star(sql: str, issues: list, ctx: dict):
    """禁止 SELECT *。"""
    # 匹配 SELECT 后紧跟 *
    if re.search(r"(?i)\bselect\s+\*\s+(from|;|$)", sql) or re.search(
        r"(?i)\bselect\s+\*\s*,", sql
    ):
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="禁止SELECT *",
            description="使用了 SELECT *",
            suggestion="明确指定查询字段，禁止 SELECT *"))


def check_count_field(sql: str, issues: list, ctx: dict):
    """禁止 count(字段)，用 count(*) 或 count(1)。"""
    matches = re.findall(r"(?i)\bcount\s*\(\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\)", sql)
    for m in matches:
        if m.lower() not in ("*", "1"):
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="禁止count(字段)",
                description=f"使用了 count({m})",
                suggestion="使用 count(*) 或 count(1)，禁止 count(字段)"))


def check_where_required(sql: str, issues: list, ctx: dict, stmt_type: str):
    """SELECT/UPDATE/DELETE 必须带 WHERE。"""
    if stmt_type in ("select",):
        # 子查询的 select 也要有 where 吗? 只检查最外层
        if not re.search(r"(?i)\bwhere\b", sql) and re.search(r"(?i)\bfrom\b", sql):
            # 排除 SELECT ... INTO 或纯常量查询
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="必须带WHERE",
                description="SELECT 语句缺少 WHERE 条件",
                suggestion="SQL 必须带有 WHERE 条件"))
    elif stmt_type in ("update", "delete"):
        if not re.search(r"(?i)\bwhere\b", sql):
            issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="缺少WHERE",
                description=f"{stmt_type.upper()} 语句缺少 WHERE 条件",
                suggestion=f"{stmt_type.upper()} 语句注意添加 WHERE 条件，避免误伤"))


def check_invalid_where(sql: str, issues: list, ctx: dict):
    """WHERE 不得为 1=1 等无效条件（仅作为唯一条件时报出）。"""
    # 检查 WHERE 后只有 1=1
    m = re.search(r"(?i)\bwhere\s+(.+?)(\border\b|\bgroup\b|\blimit\b|$)", sql)
    if m:
        condition = m.group(1).strip()
        if re.fullmatch(r"(?i)\s*1\s*=\s*1\s*", condition):
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="无效WHERE条件",
                description="WHERE 条件为 1=1 等无效形式",
                suggestion="WHERE 不得为 1=1 等无效条件"))


def check_table_alias_prefix(sql: str, issues: list, ctx: dict):
    """多表关联时，SELECT 字段须带表名/别名前缀。"""
    # 检测是否有 JOIN
    join_count = len(re.findall(r"(?i)\bjoin\b", sql))
    if join_count == 0:
        return

    # 提取 SELECT ... FROM 之间的字段列表
    m = re.search(r"(?i)\bselect\s+(distinct\s+)?(.*?)\s+from\b", sql)
    if not m:
        return
    fields_str = m.group(2)

    # 如果是 *，跳过（已由 check_select_star 报出）
    if fields_str.strip() == "*":
        return

    # 拆分字段
    raw_fields = split_sql_fields(fields_str)
    for field in raw_fields:
        field = field.strip()
        if not field or field == "*":
            continue
        # 跳过聚合函数内的内容
        if re.match(r"(?i)(count|sum|avg|max|min|group_concat)\s*\(", field):
            continue
        # 检查是否有别名前缀 (xxx.field 或 xxx AS yyy)
        # 提取字段名部分（AS 之前）
        field_name = re.split(r"(?i)\bas\b", field)[0].strip()
        # 去掉函数包装
        field_name = re.sub(r"^.*\((.*)\).*$", r"\1", field_name)
        field_name = field_name.strip()

        if "." not in field_name and field_name not in ("?",):
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="多表关联字段前缀",
                description=f"多表关联查询中字段 '{field.strip()}' 未带表名/别名前缀",
                suggestion="多表关联时 SELECT 字段须带表名或表别名前缀，如 tb.id"))


def split_sql_fields(fields_str: str) -> list:
    """按逗号拆分 SELECT 字段列表，忽略括号内的逗号。"""
    parts = []
    depth = 0
    current = []
    for ch in fields_str:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def check_right_join(sql: str, issues: list, ctx: dict):
    """能用 LEFT JOIN 则不使用 RIGHT JOIN。"""
    if re.search(r"(?i)\bright\s+join\b", sql):
        issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="避免RIGHT JOIN",
            description="使用了 RIGHT JOIN",
            suggestion="能用 LEFT JOIN 则不使用 RIGHT JOIN"))


def check_inner_join_abbreviation(sql: str, issues: list, ctx: dict):
    """内连接写 INNER JOIN，不简写成 JOIN。"""
    # 匹配 JOIN 但前面没有 INNER/LEFT/RIGHT/CROSS/FULL
    matches = re.finditer(r"(?i)(?<!inner\s)(?<!left\s)(?<!right\s)(?<!cross\s)(?<!full\s)(?<!outer\s)\bjoin\b", sql)
    found = False
    for m in matches:
        prefix = sql[max(0, m.start() - 10):m.start()]
        if not re.search(r"(?i)(inner|left|right|cross|full|outer)\s*$", prefix):
            found = True
            break
    if found:
        issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="INNER JOIN 不简写",
            description="使用了简写 JOIN 而非 INNER JOIN",
            suggestion="内连接写 INNER JOIN，不简写为 JOIN"))


def check_bad_alias(sql: str, issues: list, ctx: dict):
    """别名应含义清晰，避免 t1/a/b 等无意义别名。"""
    # 匹配 FROM table [AS] alias 和 JOIN table [AS] alias
    # 匹配 FROM/JOIN 后的 表名 [AS] 别名（不含 AS 时别名紧跟表名）
    # 模式1: table AS alias
    m1 = re.findall(r"(?i)(?:from|join)\s+[\w.]+\s+as\s+(\w+)", sql)
    # 模式2: table alias（两个词，第二个是别名）
    m2 = re.findall(r"(?i)(?:from|join)\s+([\w.]+)\s+(?!where|on|inner|left|right|join|order|group|limit|set|values|using)(\w+)", sql)
    aliases = list(m1) + [a for a in m2]
    bad_patterns = re.compile(r"^(t\d+|[a-z])$")
    for alias in aliases:
        if isinstance(alias, tuple):
            alias = alias[-1]
        if bad_patterns.match(alias.lower()):
            issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="别名含义清晰",
                description=f"使用了无意义别名 '{alias}'",
                suggestion="别名应含义清晰，避免 t1/a/b 等单字符或序号别名"))


def check_left_like(sql: str, issues: list, ctx: dict):
    """不用左模糊 LIKE '%abc'。"""
    matches = re.findall(r"(?i)like\s+'(%[^']*?)'", sql)
    for pattern in matches:
        if pattern.startswith("%"):
            issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="避免左模糊",
                description=f"使用了左模糊匹配 LIKE '%...'",
                suggestion="左模糊匹配无法利用索引，应避免"))


def check_where_function(sql: str, issues: list, ctx: dict):
    """WHERE 中不对字段做函数转换。"""
    # 提取 WHERE 子句
    m = re.search(r"(?i)\bwhere\b\s+(.+?)(\border\s+by|\bgroup\s+by|\blimit\b|$)", sql)
    if not m:
        return
    where_clause = m.group(1)

    # 检测字段上包了函数: func(field_name) op value
    func_patterns = [
        (r"(?i)\b(upper|lower|ltrim|rtrim|substring|substr|left|right|date_format|str_to_date|convert|cast|year|month|day|hour|concat|trim|replace|abs|round|ceil|floor)\s*\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\)", "WHERE 条件中对字段使用了函数"),
    ]
    for pattern, desc in func_patterns:
        if re.search(pattern, where_clause):
            issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="WHERE避免函数转换",
                description=desc,
                suggestion="WHERE 中尽量不对字段进行函数转换，会降低性能"))


def check_insert_columns(sql: str, issues: list, ctx: dict):
    """INSERT 必须列出字段列表。"""
    # 匹配 INSERT INTO table VALUES (不带字段列表)
    if re.search(r"(?i)\binsert\s+into\s+\w+(\s*,\s*\w+)*\s+values\s*\(", sql):
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="INSERT列字段",
            description="INSERT 语句未列出字段列表",
            suggestion="INSERT 必须列举出被插入字段的列表"))


def check_ddl_in_app(sql: str, issues: list, ctx: dict):
    """应用程序中禁止 DDL 操作。"""
    ddl_keywords = re.search(
        r"(?i)\b(alter\s+table|create\s+table|drop\s+table|truncate\s+table|rename\s+table)\b",
        sql,
    )
    if ddl_keywords:
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="禁止DDL操作",
            description=f"mapper 中包含 DDL 语句: {ddl_keywords.group()}",
            suggestion="应用程序中禁止任何 DDL 操作"))


def check_excessive_joins(sql: str, issues: list, ctx: dict):
    """减少表关联数量。"""
    join_count = len(re.findall(r"(?i)\bjoin\b", sql))
    if join_count > 5:
        issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="减少JOIN",
            description=f"关联了 {join_count} 张表",
            suggestion="尽量减少表关联数量，关联越多越容易降低性能"))


# ── 主检查流程 ──────────────────────────────────────────────────────────


def check_statement(
    sql: str, stmt_type: str, stmt_id: str, file_path: str, issues: list
):
    """对单条 SQL 语句执行全部检查。"""
    norm = normalize_sql(sql)
    ctx = {
        "file": file_path,
        "statement_id": stmt_id,
        "statement_type": stmt_type,
        "location": f"{stmt_type}:{stmt_id}",
    }

    check_select_star(norm, issues, ctx)
    check_count_field(norm, issues, ctx)
    check_where_required(norm, issues, ctx, stmt_type)
    check_invalid_where(norm, issues, ctx)
    check_table_alias_prefix(norm, issues, ctx)
    check_right_join(norm, issues, ctx)
    check_inner_join_abbreviation(norm, issues, ctx)
    check_bad_alias(norm, issues, ctx)
    check_left_like(norm, issues, ctx)
    check_where_function(norm, issues, ctx)
    check_insert_columns(norm, issues, ctx)
    check_ddl_in_app(norm, issues, ctx)
    check_excessive_joins(norm, issues, ctx)


STATEMENT_TAGS = {"select", "insert", "update", "delete"}


def check_file(file_path: str) -> list:
    """检查单个 MyBatis XML 文件。"""
    issues = []

    try:
        tree = ET.parse(file_path)
    except ET.ParseError as e:
        issues.append(Issue(
            file=file_path, statement_id="(文件级)", statement_type="",
            severity=Severity.MANDATORY, rule="XML解析错误",
            location=file_path, description=f"XML 解析失败: {e}",
            suggestion="检查 XML 语法是否正确",
        ))
        return issues

    root = tree.getroot()

    for tag in STATEMENT_TAGS:
        for elem in root.iter(tag):
            stmt_id = elem.get("id", "(未命名)")
            sql = extract_sql_from_element(elem, root)
            if sql.strip():
                check_statement(sql, tag, stmt_id, file_path, issues)

    return issues


SKIP_DIRS = {
    "target", "build", ".git", "node_modules", ".idea", ".vscode",
    ".gradle", ".mvn", "dist", "out", ".next", ".nuxt",
}


def is_mapper(path: str) -> bool:
    """判断 XML 文件是否为 MyBatis mapper。"""
    if not path.endswith(".xml"):
        return False
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for tag in STATEMENT_TAGS:
            if root.find(f".//{tag}") is not None:
                return True
        return False
    except Exception:
        return False


def find_mybatis_files(path: str) -> list:
    """查找 MyBatis mapper XML 文件。"""
    xml_files = []

    if os.path.isfile(path):
        if is_mapper(path):
            xml_files = [path]
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            # 原地修改 dirnames 跳过非源码目录（阻止 os.walk 递归进入）
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if f.endswith(".xml"):
                    full = os.path.join(dirpath, f)
                    if is_mapper(full):
                        xml_files.append(full)

    return xml_files


# ── 报告格式 ────────────────────────────────────────────────────────────


def format_report_text(file_path: str, issues: list) -> str:
    if not issues:
        return f"✓ {file_path} — 检查通过\n"

    mandatory = [i for i in issues if i.severity == Severity.MANDATORY]
    recommended = [i for i in issues if i.severity == Severity.RECOMMENDED]

    lines = [
        f"{'='*60}",
        f"SQL 审查报告: {file_path}",
        f"{'='*60}",
        f"  【强制】问题: {len(mandatory)} 项",
        f"  【推荐】问题: {len(recommended)} 项",
        "",
    ]

    for issue in issues:
        lines.append(f"  [{issue.severity.value}] {issue.rule}")
        lines.append(f"    语句: {issue.statement_type} ({issue.statement_id})")
        lines.append(f"    问题: {issue.description}")
        if issue.suggestion:
            lines.append(f"    建议: {issue.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_report_json(file_path: str, issues: list) -> str:
    data = {
        "file": file_path,
        "summary": {
            "total": len(issues),
            "mandatory": sum(1 for i in issues if i.severity == Severity.MANDATORY),
            "recommended": sum(1 for i in issues if i.severity == Severity.RECOMMENDED),
        },
        "issues": [
            {
                "statement_id": i.statement_id,
                "statement_type": i.statement_type,
                "severity": i.severity.value,
                "rule": i.rule,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in issues
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="MyBatis SQL 规范检查脚本 - 检查 mapper XML 中的 DQL/DML 语句"
    )
    parser.add_argument("path", nargs="?", default=".", help="MyBatis XML 文件或项目目录路径（默认当前目录）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args()

    files = find_mybatis_files(args.path)

    if not files:
        print(f"未找到 MyBatis mapper XML 文件: {args.path}", file=sys.stderr)
        return 2

    all_issues = {}
    total_mandatory = 0

    for f in sorted(files):
        issues = check_file(f)
        all_issues[f] = issues
        total_mandatory += sum(1 for i in issues if i.severity == Severity.MANDATORY)

    if args.format == "json":
        results = []
        for f, issues in all_issues.items():
            results.append(json.loads(format_report_json(f, issues)))
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for f, issues in all_issues.items():
            print(format_report_text(f, issues))
        print(f"{'='*60}")
        print(f"总计: {len(files)} 个文件, {sum(len(v) for v in all_issues.values())} 个问题 ({total_mandatory} 个强制)")
        print(f"{'='*60}")

    return 1 if total_mandatory > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
