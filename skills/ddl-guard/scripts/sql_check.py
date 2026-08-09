#!/usr/bin/env python3
"""
MyBatis SQL 规范检查脚本
检查 MyBatis mapper XML 中的 DQL/DML 语句和 MyBatis-Plus PO 类（@TableName）
是否符合数据库设计开发规范。

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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """解析 <include refid='...'> 标签，将引用的 <sql> 片段内联。

    refid 匹配方式（按优先级）：
    1. 精确匹配：refid='baseColumns' 匹配 id='baseColumns'
    2. 短名匹配（按 id 末段）：支持命名空间前缀与反向匹配
       - refid='com.example.mapper.baseColumns' 匹配 id='baseColumns'
       - refid='baseColumns' 匹配 id='com.example.mapper.baseColumns'
    """
    sql_fragments = {}  # 完整 id → Element
    sql_fragments_by_short = {}  # 短名（最后一段）→ [Element, ...]

    for sql_el in root.findall(".//sql"):
        sid = sql_el.get("id")
        if not sid:
            continue
        sql_fragments[sid] = sql_el
        # 提取短名（最后一段，支持 namespace.id 格式）
        short_name = sid.split(".")[-1]
        if short_name not in sql_fragments_by_short:
            sql_fragments_by_short[short_name] = []
        sql_fragments_by_short[short_name].append(sql_el)

    def _resolve(e: ET.Element):
        for child in list(e):
            if child.tag.lower() == "include":
                refid = child.get("refid", "")
                if not refid:
                    continue

                frag = None
                # 策略 1: 精确匹配完整 refid
                frag = sql_fragments.get(refid)
                # 策略 2: 尝试去掉 refid 的命名空间前缀后匹配
                if frag is None:
                    refid_short = refid.split(".")[-1]
                    frag_list = sql_fragments_by_short.get(refid_short, [])
                    if frag_list:
                        # 如果有多个匹配，取第一个（通常是最精确的）
                        frag = frag_list[0]
                # 注：原“策略3 多级后缀匹配”已移除——其成功路径与策略2 互斥
                # （suffix 命中完整 id 时，refid 末段必等于该 id 末段，策略2 必先命中），
                # 属不可达 dead code。
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
    """WHERE 中不对字段做函数转换。

    覆盖以下常见函数（对字段操作导致索引失效）：
    字符串：upper/lower/ltrim/rtrim/trim/concat/concat_ws/substring/substr/
             substring_index/replace/locate/instr/length/char_length/
             lcase/ucase/regexp_replace/regexp_substr/replace/translate/
    日期：date_format/str_to_date/year/month/day/hour/minute/second/
          datediff/timestampdiff/interval/date/adddate/adddate/
    数值：abs/round/ceil/floor/mod/ceil/mod/power/sqrt/log/
    类型转换：cast/convert/convert_tz/
    其他：ifnull/nvl/coalesce/if/if/case/
    """
    # 提取 WHERE 子句
    m = re.search(r"(?i)\bwhere\b\s+(.+?)(\border\s+by|\bgroup\s+by|\blimit\b|$)", sql)
    if not m:
        return
    where_clause = m.group(1)

    # 检测字段上包了函数: func(field_name) op value
    # 扩展函数列表，覆盖更多常见字符串/日期/数值函数
    # 使用更宽松的正则，支持多参数和复杂表达式
    func_patterns = [
        # 字符串函数（支持多参数和复杂表达式）
        (r"(?i)\b(upper|lower|left|right|ltrim|rtrim|trim|concat|concat_ws|substring|substr|substring_index|replace|locate|instr|length|char_length|lcase|ucase|regexp_replace|regexp_substr|translate)\s*\(", "WHERE 条件中对字段使用了字符串函数"),
        # 日期函数（支持多参数和复杂表达式）
        (r"(?i)\b(date_format|str_to_date|year|month|day|hour|minute|second|datediff|timestampdiff|to_date|to_timestamp|from_unixtime|unix_timestamp)\s*\(", "WHERE 条件中对字段使用了日期函数"),
        # 数值函数（支持多参数和复杂表达式）
        (r"(?i)\b(abs|round|ceil|ceiling|floor|mod|power|sqrt|log|sign)\s*\(", "WHERE 条件中对字段使用了数值函数"),
        # 类型转换（支持多参数和复杂表达式）
        (r"(?i)\b(cast|convert|convert_tz)\s*\(", "WHERE 条件中对字段使用了类型转换函数"),
        # 空值处理（支持多参数和复杂表达式）
        (r"(?i)\b(ifnull|nvl|coalesce)\s*\(", "WHERE 条件中对字段使用了空值处理函数"),
    ]
    for pattern, desc in func_patterns:
        if re.search(pattern, where_clause):
            issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="WHERE避免函数转换",
                description=desc,
                suggestion="WHERE 中尽量不对字段进行函数转换，会降低性能。建议改为字段值与常量比较，或使用覆盖索引"))


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
    """判断 XML 文件是否为 MyBatis mapper。

    使用 iter() 搜索所有后代元素，而非仅搜索直接子元素。
    修复 find() 无法找到嵌套在深层的 select/insert/update/delete 标签的问题。
    """
    if not path.endswith(".xml"):
        return False
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for tag in STATEMENT_TAGS:
            # 使用 iter() 搜索所有后代元素（修复 find() 仅搜索直接子元素的问题）
            if list(root.iter(tag)):
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


# ── MyBatis-Plus PO 类解析与检查 ────────────────────────────────────────

MYSQL_RESERVED = {
    "add", "all", "alter", "and", "as", "asc", "between", "bigint", "binary",
    "blob", "both", "by", "call", "cascade", "case", "char", "check", "column",
    "condition", "constraint", "continue", "convert", "create", "cross",
    "current_date", "current_time", "current_timestamp", "cursor", "database",
    "databases", "day_hour", "day_microsecond", "day_minute", "day_second",
    "decimal", "declare", "default", "delete", "desc", "describe", "distinct",
    "distinctrow", "div", "double", "drop", "dual", "else", "enclosed",
    "escaped", "exists", "exit", "explain", "false", "fetch", "float", "float4",
    "float8", "for", "force", "foreign", "from", "fulltext", "get", "grant",
    "group", "grouping", "groups", "having", "high_priority", "hour_microsecond",
    "hour_minute", "hour_second", "if", "ignore", "in", "index", "infile",
    "inner", "inout", "insensitive", "insert", "int", "int1", "int2", "int3",
    "int4", "int8", "integer", "interval", "into", "io_after_gtids",
    "io_before_gtids", "is", "iterate", "join", "json_table", "key", "keys",
    "kill", "leading", "leave", "left", "like", "limit", "linear", "lines",
    "load", "localtime", "localtimestamp", "lock", "long", "longblob",
    "longtext", "loop", "low_priority", "master_bind",
    "master_ssl_verify_server_cert", "match", "maxvalue", "mediumblob",
    "mediumint", "mediumtext", "middleint", "minute_microsecond",
    "minute_second", "mod", "modifies", "natural", "not", "no_write_to_binlog",
    "null", "numeric", "on", "optimize", "optimizer_costs", "option",
    "optionally", "or", "order", "out", "outer", "outfile", "over", "partition",
    "precision", "primary", "procedure", "purge", "range", "read", "read_write",
    "reads", "real", "recursive", "references", "regexp", "release", "rename",
    "repeat", "replace", "require", "resignal", "restrict", "return", "revoke",
    "right", "rlike", "rows", "schema", "schemas", "second_microsecond",
    "select", "sensitive", "separator", "set", "show", "signal", "smallint",
    "spatial", "specific", "sql", "sqlexception", "sqlstate", "sqlwarning",
    "sql_big_result", "sql_calc_found_rows", "sql_small_result", "ssl",
    "starting", "stored", "straight_join", "system", "table", "terminated",
    "then", "tinyblob", "tinyint", "tinytext", "to", "trailing", "trigger",
    "true", "undo", "union", "unique", "unlock", "unsigned", "update", "usage",
    "use", "using", "utc_date", "utc_time", "utc_timestamp", "values",
    "varbinary", "varchar", "varcharacter", "varying", "virtual", "when",
    "where", "while", "window", "with", "write", "xor", "year_month", "zerofill",
    "date", "time", "timestamp", "text", "blob", "enum", "json", "geometry",
    "point", "linestring", "polygon", "multipoint", "multilinestring",
    "multipolygon", "geometrycollection",
}

PO_REQUIRED_FIELDS = [
    "id", "creator_id", "create_time", "last_updater_id", "last_update_time",
]
PO_DEL_FLAG = "del_flag"


@dataclass
class PoFieldInfo:
    java_name: str
    column_name: str
    java_type: str = ""
    is_id: bool = False


@dataclass
class PoClassInfo:
    table_name: str
    class_name: str
    file_path: str
    fields: list
    extends_base: bool = False


def camel_to_snake(name: str) -> str:
    """驼峰命名转下划线命名（MyBatis-Plus 默认策略）。"""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1).lower()


def parse_po_class(content: str, file_path: str):
    """解析带 @TableName 注解的 Java PO 类，提取表名与字段映射。返回 None 表示非 PO 类。"""
    if "@TableName" not in content:
        return None

    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)

    # 提取表名
    table_name = None
    m = re.search(r'@TableName\s*\(\s*(?:"([^"]+)"|value\s*=\s*"([^"]+)")', content)
    if m:
        table_name = m.group(1) or m.group(2)
    elif re.search(r"@TableName\s*\(\s*\)", content):
        class_m = re.search(r"class\s+(\w+)", content)
        if class_m:
            cn = class_m.group(1)
            for suffix in ("PO", "DO", "Entity", "BO", "DTO"):
                if cn.endswith(suffix) and len(cn) > len(suffix):
                    cn = cn[: -len(suffix)]
                    break
            table_name = camel_to_snake(cn)

    if not table_name:
        return None

    class_m = re.search(r"class\s+(\w+)", content)
    class_name = class_m.group(1) if class_m else ""

    extends_base = False
    ext_m = re.search(r"class\s+\w+\s+extends\s+(\w+)", content)
    if ext_m and re.search(r"(Base|Entity|Model|Abstract)", ext_m.group(1)):
        extends_base = True

    brace_start = content.find("{")
    body = content[brace_start:] if brace_start != -1 else content

    field_pattern = re.compile(
        r"((?:@[\w.]+(?:\([^)]*\))?\s*)*)"  # 前置注解
        r"(?:public|private|protected)\s+"
        r"((?:\w+\s+)*?)"  # 其他修饰符
        r"([\w.]+(?:<[^>]+>)?(?:\[\])*)\s+"  # 类型
        r"(\w+)\s*[;=]",  # 字段名
    )

    fields = []
    for fm in field_pattern.finditer(body):
        annotations_str = fm.group(1)
        modifiers = fm.group(2)
        java_type = fm.group(3)
        java_name = fm.group(4)

        if "static" in modifiers:
            continue

        column_name = None
        is_id = False
        exist = True

        for ann_m in re.finditer(r"@([\w.]+)(?:\(([^)]*)\))?", annotations_str):
            ann_name = ann_m.group(1).split(".")[-1]
            ann_args = ann_m.group(2) or ""

            if ann_name == "TableId":
                is_id = True
                vm = re.search(r'value\s*=\s*"([^"]+)"', ann_args)
                if vm:
                    column_name = vm.group(1)
                else:
                    pm = re.match(r'\s*"([^"]+)"', ann_args)
                    if pm:
                        column_name = pm.group(1)
            elif ann_name == "TableField":
                if re.search(r"exist\s*=\s*false", ann_args, re.IGNORECASE):
                    exist = False
                    continue
                vm = re.search(r'value\s*=\s*"([^"]+)"', ann_args)
                if vm:
                    column_name = vm.group(1)
                else:
                    pm = re.match(r'\s*"([^"]+)"', ann_args)
                    if pm:
                        column_name = pm.group(1)

        if not exist:
            continue

        if column_name is None:
            column_name = camel_to_snake(java_name)

        fields.append(PoFieldInfo(
            java_name=java_name, column_name=column_name,
            java_type=java_type, is_id=is_id,
        ))

    return PoClassInfo(
        table_name=table_name, class_name=class_name,
        file_path=file_path, fields=fields, extends_base=extends_base,
    )


def check_po_table_name(po: PoClassInfo, issues: list):
    """检查 @TableName 表名规范。"""
    name = po.table_name
    ctx = {"file": po.file_path, "statement_id": po.class_name, "statement_type": "PO"}

    if len(name) > 30:
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO表名长度",
            location=f"@TableName:{name}", description=f"表名长度 {len(name)} 超过 30",
            suggestion="表名长度不得超过 30"))

    if not re.match(r"^[a-z]", name):
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO表名开头",
            location=f"@TableName:{name}", description="表名必须以小写英文字母开头",
            suggestion="表名必须以英文字母开头"))

    if not re.match(r"^[a-z0-9_]+$", name):
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO表名字符",
            location=f"@TableName:{name}", description="表名必须使用小写英文字母、下划线及数字",
            suggestion="表名仅使用小写字母、下划线和数字"))

    if "__" in name:
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO表名连续下划线",
            location=f"@TableName:{name}", description="表名中不得出现连续下划线",
            suggestion="移除连续下划线"))

    if name.lower() in MYSQL_RESERVED:
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO表名保留字",
            location=f"@TableName:{name}", description=f"'{name}' 是 MySQL 保留字",
            suggestion="避免使用数据库保留字作为表名"))


def check_po_field_names(po: PoClassInfo, issues: list):
    """检查 PO 字段映射的列名规范。"""
    ctx = {"file": po.file_path, "statement_id": po.class_name, "statement_type": "PO"}
    seen = set()

    for f in po.fields:
        name = f.column_name
        loc = f"字段:{name} (Java:{f.java_name})"

        if name in seen:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO字段重复",
                location=loc, description=f"列名 '{name}' 在 PO 类中重复",
                suggestion="检查 @TableField 映射，避免列名冲突"))
        seen.add(name)

        if len(name) > 30:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO字段名长度",
                location=loc, description=f"列名长度 {len(name)} 超过 30",
                suggestion="字段名长度不得超过 30"))

        if not re.match(r"^[a-z]", name):
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO字段名开头",
                location=loc, description="列名必须以英文字母开头",
                suggestion="字段名必须以英文字母开头"))

        if not re.match(r"^[a-z0-9_]+$", name):
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO字段名字符",
                location=loc, description="列名必须使用小写字母、下划线及数字",
                suggestion="字段名仅使用小写字母、下划线和数字"))

        if "__" in name:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO字段名连续下划线",
                location=loc, description="列名中不得出现连续下划线",
                suggestion="移除连续下划线"))

        if name.lower() in MYSQL_RESERVED:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO字段名保留字",
                location=loc, description=f"'{name}' 是 MySQL 保留字",
                suggestion="避免使用数据库保留字作为字段名"))


def check_po_required_fields(po: PoClassInfo, issues: list):
    """检查 PO 类是否包含必含字段。继承基础实体类时跳过。"""
    if po.extends_base:
        return

    ctx = {"file": po.file_path, "statement_id": po.class_name, "statement_type": "PO"}
    column_names = {f.column_name.lower() for f in po.fields}

    for req in PO_REQUIRED_FIELDS:
        if req not in column_names:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO必含字段缺失",
                location=f"@TableName:{po.table_name}",
                description=f"PO 类缺少必含字段 '{req}'",
                suggestion=f"PO 类须包含字段: {req}（或在基础实体类中定义）"))

    if PO_DEL_FLAG not in column_names:
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="PO缺少del_flag",
            location=f"@TableName:{po.table_name}",
            description="PO 类缺少 del_flag 字段",
            suggestion="PO 类须包含 del_flag 字段（或在基础实体类中定义）"))


def find_po_files(path: str) -> list:
    """查找带 @TableName 注解的 Java 文件。"""
    java_files = []

    if os.path.isfile(path):
        if path.endswith(".java"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if "@TableName" in f.read():
                        java_files = [path]
            except (UnicodeDecodeError, OSError):
                pass
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".java"):
                    full = os.path.join(dirpath, fn)
                    try:
                        with open(full, "r", encoding="utf-8") as f:
                            if "@TableName" in f.read():
                                java_files.append(full)
                    except (UnicodeDecodeError, OSError):
                        continue

    return java_files


def check_po_file(file_path: str):
    """检查单个 Java PO 类文件。返回 issues 列表；非 PO 类返回 None。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError):
        return None

    po = parse_po_class(content, file_path)
    if po is None:
        return None

    issues = []
    check_po_table_name(po, issues)
    check_po_field_names(po, issues)
    check_po_required_fields(po, issues)

    return issues


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
        description="MyBatis SQL 规范检查脚本 - 检查 mapper XML 和 MyBatis-Plus PO 类"
    )
    parser.add_argument("path", nargs="?", default=".", help="文件或项目目录路径（默认当前目录）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args()

    xml_files = find_mybatis_files(args.path)
    po_files = find_po_files(args.path)

    if not xml_files and not po_files:
        print(f"未找到 MyBatis mapper XML 或 @TableName PO 类: {args.path}", file=sys.stderr)
        return 2

    all_issues = {}
    total_mandatory = 0

    def _check(file_path, is_po):
        return check_po_file(file_path) if is_po else check_file(file_path)

    all_target_files = [(f, False) for f in xml_files] + [(f, True) for f in po_files]
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_file = {
            executor.submit(_check, f, is_po): f
            for f, is_po in all_target_files
        }
        for future in as_completed(future_to_file):
            f = future_to_file[future]
            result = future.result()
            if result is not None:
                all_issues[f] = result
                total_mandatory += sum(
                    1 for i in result if i.severity == Severity.MANDATORY
                )

    if args.format == "json":
        results = []
        for f, issues in sorted(all_issues.items()):
            results.append(json.loads(format_report_json(f, issues)))
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for f, issues in sorted(all_issues.items()):
            print(format_report_text(f, issues))
        print(f"{'='*60}")
        print(f"总计: {len(all_issues)} 个文件, {sum(len(v) for v in all_issues.values())} 个问题 ({total_mandatory} 个强制)")
        print(f"{'='*60}")

    return 1 if total_mandatory > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
