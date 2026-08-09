#!/usr/bin/env python3
"""
DDL 规范检查脚本
用法:
  python3 ddl_check.py <file_or_dir> [--spec <spec_file>] [--format text|json]

检查规则参照 steering/database-design-specification.md
退出码: 0=通过(无强制问题), 1=有强制问题, 2=运行错误
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    MANDATORY = "强制"
    RECOMMENDED = "推荐"


@dataclass
class Issue:
    table: str
    severity: Severity
    rule: str
    location: str
    description: str
    suggestion: str = ""


@dataclass
class TableInfo:
    name: str
    raw_name: str
    name_line: int
    comment: Optional[str] = None
    comment_line: Optional[int] = None
    fields: list = field(default_factory=list)
    indexes: list = field(default_factory=list)
    full_text: str = ""
    is_create_table: bool = True


@dataclass
class FieldInfo:
    name: str
    raw_definition: str
    line: int
    type: str = ""
    comment: Optional[str] = None
    is_primary_key: bool = False


@dataclass
class IndexInfo:
    name: str
    raw_definition: str
    line: int
    columns: list = field(default_factory=list)
    is_unique: bool = False


# ── MySQL 保留字（常用子集）─────────────────────────────────────────────
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
    "longtext", "loop", "low_priority", "master_bind", "master_ssl_verify_server_cert",
    "match", "maxvalue", "mediumblob", "mediumint", "mediumtext", "middleint",
    "minute_microsecond", "minute_second", "mod", "modifies", "natural", "not",
    "no_write_to_binlog", "null", "numeric", "on", "optimize", "optimizer_costs",
    "option", "optionally", "or", "order", "out", "outer", "outfile", "over",
    "partition", "precision", "primary", "procedure", "purge", "range", "read",
    "read_write", "reads", "real", "recursive", "references", "regexp",
    "release", "rename", "repeat", "replace", "require", "resignal", "restrict",
    "return", "revoke", "right", "rlike", "rows", "schema", "schemas",
    "second_microsecond", "select", "sensitive", "separator", "set", "show",
    "signal", "smallint", "spatial", "specific", "sql", "sqlexception",
    "sqlstate", "sqlwarning", "sql_big_result", "sql_calc_found_rows",
    "sql_small_result", "ssl", "starting", "stored", "straight_join", "system",
    "table", "terminated", "then", "tinyblob", "tinyint", "tinytext", "to",
    "trailing", "trigger", "true", "undo", "union", "unique", "unlock",
    "unsigned", "update", "usage", "use", "using", "utc_date", "utc_time",
    "utc_timestamp", "values", "varbinary", "varchar", "varcharacter", "varying",
    "virtual", "when", "where", "while", "window", "with", "write", "xor",
    "year_month", "zerofill", "date", "time", "timestamp", "text", "blob",
    "enum", "json", "geometry", "point", "linestring", "polygon",
    "multipoint", "multilinestring", "multipolygon", "geometrycollection",
}

# ── 禁用类型 ────────────────────────────────────────────────────────────
FORBIDDEN_TYPES = {
    "text": "禁止使用 TEXT 类型，改用 varchar 或拆表存储",
    "longtext": "禁止使用 LONGTEXT 类型，改用 varchar 或拆表存储",
    "mediumtext": "禁止使用 MEDIUMTEXT 类型，改用 varchar 或拆表存储",
    "tinytext": "禁止使用 TINYTEXT 类型，改用 varchar",
    "blob": "禁止使用 BLOB 类型，静态资源应使用文件系统，数据库仅存 URL",
    "longblob": "禁止使用 LONGBLOB 类型，静态资源应使用文件系统",
    "mediumblob": "禁止使用 MEDIUMBLOB 类型，静态资源应使用文件系统",
    "tinyblob": "禁止使用 TINYBLOB 类型，静态资源应使用文件系统",
    "json": "禁止使用 JSON 类型，改用 varchar 存储序列化字符串",
    "enum": "禁止使用 ENUM 类型，改用 tinyint 配合注释枚举值",
    "set": "禁止使用 SET 类型，改用 tinyint 或关联表",
    "timestamp": "禁止使用 TIMESTAMP 类型(timestamp 范围仅1970-2038)，改用 datetime",
    "float": "禁止使用 FLOAT 类型，改用 decimal 或 bigint",
    "double": "禁止使用 DOUBLE 类型，改用 decimal",
    "real": "禁止使用 REAL 类型(等同 double)，改用 decimal",
    "clob": "禁止使用 CLOB 类型，改用 varchar 或拆表存储",
    "lob": "禁止使用 LOB 类型，改用 varchar 或拆表存储",
}

# ── 必含字段 ────────────────────────────────────────────────────────────
REQUIRED_FIELDS = {
    "id": {"type_pattern": r"(int|bigint)", "desc": "主键id"},
    "creator_id": {"type_pattern": r"varchar\s*\(\s*36\s*\)", "desc": "创建人id"},
    "create_time": {"type_pattern": r"datetime", "desc": "创建时间"},
    "last_updater_id": {"type_pattern": r"varchar\s*\(\s*36\s*\)", "desc": "最后更新人id"},
    "last_update_time": {"type_pattern": r"datetime", "desc": "最后更新时间"},
}

# ── 全角字符范围检测 ────────────────────────────────────────────────────
FULLWIDTH_RE = re.compile(r"[\uff00-\uffef\u3000-\u303f\u2018-\u201f\u2026\u00b7]")


def strip_sql_comments(text: str) -> str:
    """Remove -- comments and /* */ comments but keep line structure for line number tracking."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # Remove -- comment (but not inside quotes)
        result = []
        in_quote = False
        quote_char = None
        i = 0
        while i < len(line):
            ch = line[i]
            if in_quote:
                result.append(ch)
                if ch == quote_char and (i == 0 or line[i - 1] != "\\"):
                    in_quote = False
                i += 1
            else:
                if ch in ("'", '"', "`"):
                    in_quote = True
                    quote_char = ch
                    result.append(ch)
                    i += 1
                elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
                    break  # rest is comment
                else:
                    result.append(ch)
                    i += 1
        cleaned.append("".join(result))
    return "\n".join(cleaned)


def extract_tables(raw_text: str) -> list:
    """Parse CREATE TABLE statements from SQL text."""
    lines = raw_text.split("\n")
    tables = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Match CREATE TABLE
        m = re.match(
            r"(?i)create\s+(?:temporary\s+)?\s*table\s+(?:if\s+not\s+exists\s+)?"
            r"(?:`?(\w+)`?\.)?`?(\w+)`?\s*\(",
            line,
        )
        if m:
            table_name = m.group(2) or m.group(1)
            table = TableInfo(
                name=table_name,
                raw_name=table_name,
                name_line=i + 1,
                full_text="",
                is_create_table=True,
            )
            # Extract table comment from same line or subsequent lines
            # Look for COMMENT='...' or COMMENT '...' after the closing paren
            # First, gather the full table definition
            paren_depth = line.count("(") - line.count(")")
            full_lines = [line]
            j = i + 1
            while j < len(lines) and paren_depth > 0:
                full_lines.append(lines[j])
                paren_depth += lines[j].count("(") - lines[j].count(")")
                j += 1

            full_text = "\n".join(full_lines)
            table.full_text = full_text

            # Extract table comment
            table_comment_match = re.search(
                r"(?i)\)\s*(?:.*?)*?comment\s*=?\s*'([^']*)'", full_text
            )
            if not table_comment_match:
                # Try inline comment on CREATE TABLE line
                pass

            # Parse fields and indexes from within parens
            _parse_table_body(table, full_lines)

            # Find table comment
            table.comment_line = j  # approximate
            tables.append(table)
            i = j
        else:
            i += 1
    return tables


def _parse_table_body(table: TableInfo, body_lines: list):
    """Parse field and index definitions from CREATE TABLE body lines."""
    # Skip first line (CREATE TABLE ...) and process until closing paren
    base_line = table.name_line

    for idx, raw_line in enumerate(body_lines):
        line_no = base_line + idx
        line = raw_line.strip().rstrip(",")

        # Skip the CREATE TABLE line
        if idx == 0:
            continue

        # Skip closing paren or options after it
        if line.startswith(")") or line.startswith("ENGINE") or line.startswith("DEFAULT"):
            continue

        if not line:
            continue

        # Check if this is a constraint/index definition
        if re.match(r"(?i)^(primary\s+key|unique\s+key|unique\s+index|unique\s+constraint)\s*", line):
            # Unique index or primary key
            idx_info = _parse_index_line(line, line_no)
            if idx_info:
                table.indexes.append(idx_info)
            continue

        if re.match(r"(?i)^(key|index)\s+", line):
            idx_info = _parse_index_line(line, line_no)
            if idx_info:
                table.indexes.append(idx_info)
            continue

        if re.match(r"(?i)^(constraint|foreign\s+key|check|fulltext|spatial)\s+", line):
            continue

        # Regular field definition
        field_info = _parse_field_line(line, line_no)
        if field_info:
            table.fields.append(field_info)


def _parse_index_line(line: str, line_no: int) -> Optional[IndexInfo]:
    """Parse an index definition line."""
    # Primary key
    pk_match = re.match(r"(?i)primary\s+key\s*(?:\(\s*([^)]+)\s*\))?", line)
    if pk_match:
        cols_str = pk_match.group(1) or ""
        cols = [c.strip().strip("`") for c in cols_str.split(",") if c.strip()]
        return IndexInfo(
            name="PRIMARY",
            raw_definition=line,
            line=line_no,
            columns=cols,
            is_unique=False,
        )

    # Unique key
    uk_match = re.match(r"(?i)unique\s+(?:key|index)\s+`?(\w+)`?\s*\(\s*([^)]+)\s*\)", line)
    if uk_match:
        name = uk_match.group(1)
        cols_str = uk_match.group(2)
        cols = [c.strip().strip("`") for c in cols_str.split(",") if c.strip()]
        return IndexInfo(
            name=name,
            raw_definition=line,
            line=line_no,
            columns=cols,
            is_unique=True,
        )

    # Unique constraint
    uc_match = re.match(r"(?i)unique\s+constraint\s+`?(\w+)`?\s*\(\s*([^)]+)\s*\)", line)
    if uc_match:
        name = uc_match.group(1)
        cols_str = uc_match.group(2)
        cols = [c.strip().strip("`") for c in cols_str.split(",") if c.strip()]
        return IndexInfo(
            name=name,
            raw_definition=line,
            line=line_no,
            columns=cols,
            is_unique=True,
        )

    # Regular key/index
    k_match = re.match(r"(?i)(?:key|index)\s+`?(\w+)`?\s*\(\s*([^)]+)\s*\)", line)
    if k_match:
        name = k_match.group(1)
        cols_str = k_match.group(2)
        cols = [c.strip().strip("`") for c in cols_str.split(",") if c.strip()]
        return IndexInfo(
            name=name,
            raw_definition=line,
            line=line_no,
            columns=cols,
            is_unique=False,
        )

    return None


def _parse_field_line(line: str, line_no: int) -> Optional[FieldInfo]:
    """Parse a field definition line."""
    # Match: `field_name` type(...) ...
    m = re.match(r"`?(\w+)`?\s+(.+)", line)
    if not m:
        return None

    name = m.group(1)
    rest = m.group(2)

    # Extract type (first word + optional length/precision)
    type_match = re.match(
        r"(\w+(?:\s*\([^)]+\))?|int\s*\(\s*\d+\s*\)|bigint\s*\(\s*\d+\s*\)|"
        r"tinyint\s*\(\s*\d+\s*\)|smallint\s*\(\s*\d+\s*\)|mediumint\s*\(\s*\d+\s*\)|"
        r"varchar\s*\(\s*\d+\s*\)|char\s*\(\s*\d+\s*\)|decimal\s*\(\s*\d+\s*,\s*\d+\s*\)|"
        r"datetime|date|time)",
        rest,
        re.IGNORECASE,
    )

    field_type = type_match.group(0).strip() if type_match else rest.split()[0] if rest.split() else ""

    # Extract comment
    comment_match = re.search(r"comment\s+'((?:[^'\\]|\\.)*)'", rest, re.IGNORECASE)
    comment = comment_match.group(1) if comment_match else None

    # Check if primary key
    is_pk = bool(re.search(r"(?i)primary\s+key", rest))

    return FieldInfo(
        name=name,
        raw_definition=line,
        line=line_no,
        type=field_type,
        comment=comment,
        is_primary_key=is_pk,
    )


def extract_table_comment(full_text: str) -> Optional[str]:
    """Extract table-level COMMENT from the full CREATE TABLE text.
    The table comment appears AFTER the final closing paren of the CREATE TABLE.
    """
    last_paren = full_text.rfind(")")
    if last_paren == -1:
        return None
    suffix = full_text[last_paren:]
    m = re.search(r"comment\s*=?\s*'((?:[^'\\]|\\.)*)'", suffix, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ── 规则检查函数 ────────────────────────────────────────────────────────


def check_forbidden_clauses(text: str, issues: list, file_path: str):
    """Check for forbidden clauses in raw DDL text."""
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        upper = line.upper()
        if re.search(r"CHARACTER\s+SET\s*=", upper, re.IGNORECASE) or re.search(
            r"CHARSET\s*=", upper, re.IGNORECASE
        ):
            issues.append(Issue(
                table="(文件级)", severity=Severity.MANDATORY, rule="去除字符集子句",
                location=f"{file_path}:{i}", description="包含 CHARACTER SET / CHARSET 子句",
                suggestion="提交审核的 DDL 须去除 CHARACTER SET 子句",
            ))
        if re.search(r"COLLATE\s*=", upper, re.IGNORECASE) or re.search(
            r"COLLATE\s+\w+", upper, re.IGNORECASE
        ):
            issues.append(Issue(
                table="(文件级)", severity=Severity.MANDATORY, rule="去除字符序子句",
                location=f"{file_path}:{i}", description="包含 COLLATE 子句",
                suggestion="提交审核的 DDL 须去除 COLLATE 子句",
            ))
        if re.search(r"AUTO_INCREMENT\s*=\s*\d+", upper):
            issues.append(Issue(
                table="(文件级)", severity=Severity.MANDATORY, rule="去除 auto_increment 子句",
                location=f"{file_path}:{i}", description="包含 auto_increment=N 子句",
                suggestion="提交审核的 DDL 须去除 auto_increment=N 子句",
            ))
        if re.search(r"ENGINE\s*=", upper):
            issues.append(Issue(
                table="(文件级)", severity=Severity.MANDATORY, rule="去除 engine 子句",
                location=f"{file_path}:{i}", description="包含 ENGINE= 子句",
                suggestion="提交审核的 DDL 须去除 ENGINE 子句",
            ))
        if re.search(r"ROW_FORMAT\s*=", upper):
            issues.append(Issue(
                table="(文件级)", severity=Severity.MANDATORY, rule="去除 row_format 子句",
                location=f"{file_path}:{i}", description="包含 ROW_FORMAT= 子句",
                suggestion="提交审核的 DDL 须去除 ROW_FORMAT 子句",
            ))


def check_comment_style(text: str, issues: list, file_path: str):
    """Check comment style (# or /* */ instead of -- ).

    检查两种注释风格问题：
    1. 使用 # 注释（应改为 --）
    2. 使用 -- 注释但 -- 后没有空格（不规范，应改为 -- 空格）
    """
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        # 检查 # 注释（排除 shebang #!）
        if stripped.startswith("#") and not stripped.startswith("#!"):
            issues.append(Issue(
                table="(文件级)", severity=Severity.MANDATORY, rule="注释符号",
                location=f"{file_path}:{i}", description="使用了 # 注释",
                suggestion="注释统一使用 '-- '(注意 -- 后有一个空格)",
            ))
        # 检查 -- 注释但 -- 后没有空格（常见错误）
        # 需要排除 SQL 关键字中的 --（如 column name 包含 -- 的情况）
        # 匹配行首或括号后的 -- 注释，且 -- 后紧跟非空格字符
        if re.search(r"(?<![\w\x27\x60])(--)(?![\s\-\x27\x60])", stripped, re.IGNORECASE):
            # 排除 COMMENT 定义中的 --（如 COMMENT 'xxx--yyy'）
            if not re.search(r"(?i)comment\s*['\"]", stripped):
                issues.append(Issue(
                    table="(文件级)", severity=Severity.MANDATORY, rule="注释格式",
                    location=f"{file_path}:{i}", description="-- 注释后缺少空格（应为 '-- '）",
                    suggestion="-- 后必须跟一个空格，如 '-- 注释内容'，否则可能被误解析",
                ))


def check_partition(text: str, issues: list, file_path: str):
    """Check for partition usage."""
    if re.search(r"(?i)\bpartition\s+by\b", text):
        lines = text.split("\n")
        for i, line in enumerate(lines, 1):
            if re.search(r"(?i)\bpartition\s+by\b", line):
                issues.append(Issue(
                    table="(文件级)", severity=Severity.MANDATORY, rule="禁止分区表",
                    location=f"{file_path}:{i}", description="使用了分区表(PARTITION BY)",
                    suggestion="不得使用分区表",
                ))
                break


def check_change_column(text: str, issues: list, file_path: str):
    """Check for CHANGE COLUMN usage."""
    if re.search(r"(?i)\bchange\s+column\b", text):
        lines = text.split("\n")
        for i, line in enumerate(lines, 1):
            if re.search(r"(?i)\bchange\s+column\b", line):
                issues.append(Issue(
                    table="(文件级)", severity=Severity.MANDATORY, rule="禁止 CHANGE COLUMN",
                    location=f"{file_path}:{i}", description="使用了 CHANGE COLUMN 修改字段",
                    suggestion="使用 MODIFY 或 RENAME 语句分别修改属性和字段名",
                ))


def check_table_name(table: TableInfo, issues: list):
    """Check table naming conventions."""
    name = table.name

    # Length
    if len(name) > 30:
        issues.append(Issue(
            table=name, severity=Severity.MANDATORY, rule="表名长度",
            location=f"表名:{name}", description=f"表名长度 {len(name)} 超过 30",
            suggestion="表名长度不得超过 30，过长时可缩写",
        ))

    # Must start with letter
    if not re.match(r"^[a-z]", name):
        issues.append(Issue(
            table=name, severity=Severity.MANDATORY, rule="表名开头",
            location=f"表名:{name}", description="表名必须以小写英文字母开头",
            suggestion="表名必须以英文字母开头",
        ))

    # Only lowercase letters, underscores, digits
    if not re.match(r"^[a-z0-9_]+$", name):
        issues.append(Issue(
            table=name, severity=Severity.MANDATORY, rule="表名字符",
            location=f"表名:{name}", description="表名必须使用小写英文字母、下划线及数字",
            suggestion="表名仅使用小写字母、下划线和数字",
        ))

    # No consecutive underscores
    if "__" in name:
        issues.append(Issue(
            table=name, severity=Severity.MANDATORY, rule="连续下划线",
            location=f"表名:{name}", description="表名中不得出现连续下划线",
            suggestion="移除连续下划线",
        ))

    # Reserved word
    if name.lower() in MYSQL_RESERVED:
        issues.append(Issue(
            table=name, severity=Severity.MANDATORY, rule="保留字",
            location=f"表名:{name}", description=f"'{name}' 是 MySQL 保留字",
            suggestion="避免使用数据库保留字作为表名",
        ))


def check_table_comment(table: TableInfo, issues: list):
    """Check table comment."""
    comment = extract_table_comment(table.full_text)
    table.comment = comment

    if not comment:
        issues.append(Issue(
            table=table.name, severity=Severity.MANDATORY, rule="表注释缺失",
            location=f"表:{table.name}", description="表缺少注释",
            suggestion="每个表必须有注释，且长度不超过 64",
        ))
    else:
        if len(comment) > 64:
            issues.append(Issue(
                table=table.name, severity=Severity.MANDATORY, rule="表注释长度",
                location=f"表:{table.name}", description=f"表注释长度 {len(comment)} 超过 64",
                suggestion="表注释长度不得超过 64",
            ))
        # Check special characters: allow CJK, basic Latin, digits, common punctuation
        _allowed = re.compile(
            r"[\w\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"
            r"\(\)\[\]\u3001\u3002\uff0c\uff1b\uff1a\uff01\uff1f"
            r"\u201c\u201d\u2018\u2019\-_/.,:;!?@+#&]+"
        )
        stripped = _allowed.sub("", comment).strip()
        if stripped:
            issues.append(Issue(
                table=table.name, severity=Severity.MANDATORY, rule="表注释特殊字符",
                location=f"表:{table.name}", description=f"表注释含特殊字符: {comment}",
                suggestion="表注释中不得出现特殊字符",
            ))


def check_required_fields(table: TableInfo, issues: list):
    """Check for required system fields."""
    field_names = {f.name.lower() for f in table.fields}

    for req_name, _req_info in REQUIRED_FIELDS.items():
        if req_name not in field_names:
            issues.append(Issue(
                table=table.name, severity=Severity.MANDATORY, rule="必含字段缺失",
                location=f"表:{table.name}", description=f"缺少必含字段 '{req_name}'",
                suggestion=f"新表必须包含字段: {req_name}",
            ))


def check_field_count(table: TableInfo, issues: list):
    """Check field count."""
    if len(table.fields) > 40:
        issues.append(Issue(
            table=table.name, severity=Severity.MANDATORY, rule="字段数量",
            location=f"表:{table.name}", description=f"字段数量 {len(table.fields)} 超过 40",
            suggestion="单表字段数不超过 40，超出需重构或经技术委员会评审",
        ))


def check_field_name(field: FieldInfo, table_name: str, issues: list):
    """Check field naming conventions."""
    name = field.name

    # Length
    if len(name) > 30:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="字段名长度",
            location=f"表:{table_name} 字段:{name}", description=f"字段名长度 {len(name)} 超过 30",
            suggestion="字段名长度不得超过 30",
        ))

    # Must start with letter
    if not re.match(r"^[a-z]", name):
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="字段名开头",
            location=f"表:{table_name} 字段:{name}", description="字段名必须以英文字母开头",
            suggestion="字段名必须以英文字母开头",
        ))

    # Only lowercase letters, underscores, digits
    if not re.match(r"^[a-z0-9_]+$", name):
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="字段名字符",
            location=f"表:{table_name} 字段:{name}", description="字段名必须使用小写字母、下划线及数字",
            suggestion="字段名仅使用小写字母、下划线和数字",
        ))

    # No consecutive underscores
    if "__" in name:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="连续下划线",
            location=f"表:{table_name} 字段:{name}", description="字段名中不得出现连续下划线",
            suggestion="移除连续下划线",
        ))

    # Reserved word
    if name.lower() in MYSQL_RESERVED:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="保留字",
            location=f"表:{table_name} 字段:{name}", description=f"'{name}' 是 MySQL 保留字",
            suggestion="避免使用数据库保留字作为字段名",
        ))


def check_field_comment(field: FieldInfo, table_name: str, issues: list):
    """Check field comment."""
    if not field.comment:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="字段注释缺失",
            location=f"表:{table_name} 字段:{field.name}", description="字段缺少注释",
            suggestion="所有字段必须有注释",
        ))
        return

    comment = field.comment

    # Length
    if len(comment) > 128:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="字段注释长度",
            location=f"表:{table_name} 字段:{field.name}", description=f"字段注释长度 {len(comment)} 超过 128",
            suggestion="字段注释长度不超过 128",
        ))

    # Full-width characters
    fw_matches = FULLWIDTH_RE.findall(comment)
    if fw_matches:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="全角字符",
            location=f"表:{table_name} 字段:{field.name}", 
            description=f"字段注释含全角字符: {''.join(set(fw_matches))}",
            suggestion="注释中不应包含全角字符，中文标点改英文标点",
        ))


def check_field_type(field: FieldInfo, table_name: str, issues: list):
    """Check for forbidden field types."""
    type_lower = field.type.lower().strip()

    # Extract base type name
    base_type_match = re.match(r"(\w+)", type_lower)
    if not base_type_match:
        return
    base_type = base_type_match.group(1)

    if base_type in FORBIDDEN_TYPES:
        issues.append(Issue(
            table=table_name, severity=Severity.MANDATORY, rule="禁用类型",
            location=f"表:{table_name} 字段:{field.name}", 
            description=f"字段 {field.name} 使用了禁用类型 {field.type}",
            suggestion=FORBIDDEN_TYPES[base_type],
        ))


def check_varchar_length(field: FieldInfo, table_name: str, issues: list):
    """Check varchar/char length limits."""
    type_lower = field.type.lower()
    vm = re.match(r"varchar\s*\(\s*(\d+)\s*\)", type_lower)
    cm = re.match(r"char\s*\(\s*(\d+)\s*\)", type_lower)

    if vm:
        length = int(vm.group(1))
        if length > 500:
            issues.append(Issue(
                table=table_name, severity=Severity.RECOMMENDED, rule="varchar长度",
                location=f"表:{table_name} 字段:{field.name}", 
                description=f"varchar({length}) 长度超过 500",
                suggestion="varchar 长度不宜超过 500",
            ))
    elif cm:
        length = int(cm.group(1))
        if length > 20:
            issues.append(Issue(
                table=table_name, severity=Severity.RECOMMENDED, rule="char长度",
                location=f"表:{table_name} 字段:{field.name}", 
                description=f"char({length}) 长度超过 20",
                suggestion="char 长度建议最大 20",
            ))


def check_del_flag(table: TableInfo, issues: list):
    """Check del_flag field naming and comment."""
    for f in table.fields:
        if f.name.lower() in ("del_flag", "delete_flag", "is_deleted", "is_del", "deleted"):
            if f.name.lower() != "del_flag":
                issues.append(Issue(
                    table=table.name, severity=Severity.MANDATORY, rule="逻辑删除字段名",
                    location=f"表:{table.name} 字段:{f.name}", 
                    description=f"逻辑删除字段名 '{f.name}' 不符合规范",
                    suggestion="逻辑删除字段统一使用 del_flag",
                ))
            if f.comment and "删除标志[0-否,1-是]" not in f.comment:
                issues.append(Issue(
                    table=table.name, severity=Severity.MANDATORY, rule="逻辑删除字段注释",
                    location=f"表:{table.name} 字段:{f.name}", 
                    description=f"逻辑删除字段注释 '{f.comment}' 不符合规范",
                    suggestion="注释统一为: 删除标志[0-否,1-是]",
                ))
            return


def check_index_naming(table: TableInfo, issues: list):
    """Check index naming conventions."""
    for idx in table.indexes:
        if idx.name == "PRIMARY":
            continue

        # Length
        if len(idx.name) > 64:
            issues.append(Issue(
                table=table.name, severity=Severity.MANDATORY, rule="索引名长度",
                location=f"表:{table.name} 索引:{idx.name}", 
                description=f"索引名长度 {len(idx.name)} 超过 64",
                suggestion="索引名长度不超过 64",
            ))

        # Unique index should start with uk_
        if idx.is_unique and not idx.name.lower().startswith("uk_"):
            issues.append(Issue(
                table=table.name, severity=Severity.MANDATORY, rule="唯一索引命名",
                location=f"表:{table.name} 索引:{idx.name}", 
                description=f"唯一索引 '{idx.name}' 未以 uk_ 开头",
                suggestion="唯一索引命名规则: uk_字段列表",
            ))

        # Regular index should start with ix_
        if not idx.is_unique and not idx.name.lower().startswith("ix_"):
            issues.append(Issue(
                table=table.name, severity=Severity.MANDATORY, rule="普通索引命名",
                location=f"表:{table.name} 索引:{idx.name}", 
                description=f"普通索引 '{idx.name}' 未以 ix_ 开头",
                suggestion="普通索引命名规则: ix_字段列表",
            ))


def check_index_on_id(table: TableInfo, issues: list):
    """Check for redundant indexes on id field."""
    id_indexes = []
    for idx in table.indexes:
        if idx.name == "PRIMARY":
            continue
        if "id" in [c.lower() for c in idx.columns]:
            id_indexes.append(idx)

    for idx in id_indexes:
        issues.append(Issue(
            table=table.name, severity=Severity.MANDATORY, rule="id重复索引",
            location=f"表:{table.name} 索引:{idx.name}", 
            description=f"id 字段已有主键索引，索引 '{idx.name}' 中包含 id",
            suggestion="id 字段已有主键索引，不再建普通索引或参与联合索引",
        ))


def check_index_count(table: TableInfo, issues: list):
    """Check index count."""
    non_pk_indexes = [i for i in table.indexes if i.name != "PRIMARY"]
    if len(non_pk_indexes) > 5:
        issues.append(Issue(
            table=table.name, severity=Severity.RECOMMENDED, rule="索引数量",
            location=f"表:{table.name}", 
            description=f"索引数量 {len(non_pk_indexes)} 超过 5",
            suggestion="单表索引个数建议最多 5 个",
        ))

    for idx in non_pk_indexes:
        if len(idx.columns) > 5:
            issues.append(Issue(
                table=table.name, severity=Severity.RECOMMENDED, rule="联合索引字段数",
                location=f"表:{table.name} 索引:{idx.name}", 
                description=f"联合索引 '{idx.name}' 包含 {len(idx.columns)} 个字段，超过 5",
                suggestion="索引中包含的字段个数建议最多 5 个",
            ))


def check_foreign_key(table: TableInfo, issues: list):
    """Check for foreign key constraints."""
    if re.search(r"(?i)\bforeign\s+key\b", table.full_text):
        issues.append(Issue(
            table=table.name, severity=Severity.MANDATORY, rule="外键约束",
            location=f"表:{table.name}", description="使用了外键约束(FOREIGN KEY)",
            suggestion="不得使用外键约束",
        ))


def check_primary_key_int(table: TableInfo, issues: list):
    """Check that primary key id is integer type."""
    for f in table.fields:
        if f.name.lower() == "id":
            type_lower = f.type.lower()
            if not re.search(r"(int|bigint)", type_lower):
                issues.append(Issue(
                    table=table.name, severity=Severity.MANDATORY, rule="主键类型",
                    location=f"表:{table.name} 字段:id", 
                    description=f"主键 id 类型为 {f.type}，应为整型",
                    suggestion="主键 id 字段类型必须为整型(int/bigint)",
                ))


# ── 主检查流程 ──────────────────────────────────────────────────────────


def check_file(file_path: str) -> list:
    """Run all checks on a single file, return list of Issue."""
    issues = []

    with open(file_path, "r", encoding="utf-8") as fh:
        raw_text = fh.read()

    # File-level checks on raw text
    check_forbidden_clauses(raw_text, issues, file_path)
    check_comment_style(raw_text, issues, file_path)
    check_partition(raw_text, issues, file_path)
    check_change_column(raw_text, issues, file_path)

    # Parse tables
    tables = extract_tables(raw_text)

    if not tables:
        issues.append(Issue(
            table="(文件级)", severity=Severity.MANDATORY, rule="无建表语句",
            location=file_path, description="文件中未找到 CREATE TABLE 语句",
            suggestion="DDL 文件应包含 CREATE TABLE 语句",
        ))

    for table in tables:
        check_table_name(table, issues)
        check_table_comment(table, issues)
        check_required_fields(table, issues)
        check_field_count(table, issues)
        check_primary_key_int(table, issues)
        check_del_flag(table, issues)
        check_foreign_key(table, issues)

        for field in table.fields:
            check_field_name(field, table.name, issues)
            check_field_comment(field, table.name, issues)
            check_field_type(field, table.name, issues)
            check_varchar_length(field, table.name, issues)

        check_index_naming(table, issues)
        check_index_on_id(table, issues)
        check_index_count(table, issues)

    return issues


def format_report_text(file_path: str, issues: list) -> str:
    """Format issues as readable text report."""
    if not issues:
        return f"✓ {file_path} — 检查通过，无规范问题\n"

    mandatory = [i for i in issues if i.severity == Severity.MANDATORY]
    recommended = [i for i in issues if i.severity == Severity.RECOMMENDED]

    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"DDL 审查报告: {file_path}")
    lines.append(f"{'='*60}")
    lines.append(f"  【强制】问题: {len(mandatory)} 项")
    lines.append(f"  【推荐】问题: {len(recommended)} 项")
    lines.append("")

    # Group by table
    tables = sorted(set(i.table for i in issues))
    for table_name in tables:
        table_issues = [i for i in issues if i.table == table_name]
        if not table_issues:
            continue
        lines.append(f"  ── {table_name} ──")
        for idx, issue in enumerate(table_issues, 1):
            severity_tag = f"[{issue.severity.value}]"
            lines.append(
                f"    {idx}. {severity_tag} {issue.rule}"
            )
            lines.append(f"       位置: {issue.location}")
            lines.append(f"       问题: {issue.description}")
            if issue.suggestion:
                lines.append(f"       建议: {issue.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_report_json(file_path: str, issues: list) -> str:
    """Format issues as JSON."""
    data = {
        "file": file_path,
        "summary": {
            "total": len(issues),
            "mandatory": sum(1 for i in issues if i.severity == Severity.MANDATORY),
            "recommended": sum(1 for i in issues if i.severity == Severity.RECOMMENDED),
        },
        "issues": [
            {
                "table": i.table,
                "severity": i.severity.value,
                "rule": i.rule,
                "location": i.location,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in issues
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="DDL 规范检查脚本 - 检查 MySQL DDL 文件是否符合数据库设计开发规范"
    )
    parser.add_argument("path", nargs="?", default=".", help="SQL 文件或目录路径（默认当前目录）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args()

    # Find SQL files
    sql_files = []
    if os.path.isfile(args.path):
        sql_files = [args.path]
    elif os.path.isdir(args.path):
        for root, _dirs, files in os.walk(args.path):
            for f in files:
                if f.endswith(".sql"):
                    sql_files.append(os.path.join(root, f))

    if not sql_files:
        print("未找到 .sql 文件", file=sys.stderr)
        return 2

    all_issues = {}
    total_mandatory = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_file = {executor.submit(check_file, f): f for f in sorted(sql_files)}
        for future in as_completed(future_to_file):
            sql_file = future_to_file[future]
            issues = future.result()
            all_issues[sql_file] = issues
            total_mandatory += sum(1 for i in issues if i.severity == Severity.MANDATORY)

    # Output
    if args.format == "json":
        results = []
        for f, issues in sorted(all_issues.items()):
            results.append(json.loads(format_report_json(f, issues)))
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for f, issues in sorted(all_issues.items()):
            print(format_report_text(f, issues))

        # Summary
        print(f"{'='*60}")
        print(f"总计: {len(sql_files)} 个文件, {sum(len(v) for v in all_issues.values())} 个问题"
              f" ({total_mandatory} 个强制)")
        print(f"{'='*60}")

    return 1 if total_mandatory > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
