"""guard 技能共享库 — 分级枚举/保留字表/文件发现/并发执行与报告骨架。

被 ddl-guard（ddl_check.py / sql_check.py）与 api-guard（api_check.py）复用，
单一真相源，替代原先三处近似复制且已漂移的代码（SKIP_DIRS、MYSQL_RESERVED）。

依赖方式：各脚本以 __file__ 相对定位本目录（skills/_shared/）注入 sys.path。
仅 Python 3.9 标准库。
"""

from __future__ import annotations  # 兼容 Python 3.9

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum


class Severity(Enum):
    MANDATORY = "强制"
    RECOMMENDED = "推荐"


# ── MySQL 保留字（常用子集）─────────────────────────────────────────────
# 单一真相源（原 ddl_check/sql_check 两份逐字复制，易漂移）。
# 注意：date/time/timestamp/text/blob/enum/json 等在 MySQL 8 中为非保留关键字，
# 本表按"禁止用作标识符"的从严口径收录。
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

# ── 非源码目录（文件发现时跳过）────────────────────────────────────────
# 统一超集（原三处漂移：api_check 含 test/tests、sql_check 不含、ddl_check 未用）。
# 测试目录不进审查范围：测试 mapper/契约是受控样例，报它们是噪音。
SKIP_DIRS = {
    "target", "build", ".git", "node_modules", ".idea", ".vscode",
    ".gradle", ".mvn", "dist", "out", ".next", ".nuxt", "test", "tests",
}


def find_files(path: str, accept) -> list:
    """按 accept(filename) 收集文件：path 为文件直接判定，为目录则递归
    （跳过 SKIP_DIRS，阻止 os.walk 递归进入）。"""
    matched = []
    if os.path.isfile(path):
        return [path] if accept(os.path.basename(path)) else []
    if os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            # 原地修改 dirnames 跳过非源码目录
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if accept(f):
                    matched.append(os.path.join(dirpath, f))
    return matched


def count_mandatory(issues: list) -> int:
    return sum(1 for i in issues if i.severity == Severity.MANDATORY)


def run_gate(targets: list, fmt: str, report_text, report_json) -> int:
    """并发执行检查并输出报告——guard 技能 main() 的统一骨架。

    targets: [(file_path, checker_fn)]，checker 返回 Issue 列表（域特定 Issue，
    须含 severity/rule/description/suggestion 属性）。
    report_text / report_json: 各技能的域特定报告格式函数 (file_path, issues)。
    返回退出码：1=有强制问题, 0=通过。
    """
    all_issues = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_file = {executor.submit(checker, f): f
                          for f, checker in targets}
        for future in as_completed(future_to_file):
            f = future_to_file[future]
            issues = future.result()
            if issues is not None:
                all_issues[f] = issues

    if fmt == "json":
        results = [json.loads(report_json(f, issues))
                   for f, issues in sorted(all_issues.items())]
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for f, issues in sorted(all_issues.items()):
            print(report_text(f, issues))
        total = sum(len(v) for v in all_issues.values())
        total_mandatory = sum(count_mandatory(v) for v in all_issues.values())
        print(f"{'='*60}")
        print(f"总计: {len(all_issues)} 个文件, {total} 个问题 ({total_mandatory} 个强制)")
        print(f"{'='*60}")

    return 1 if any(count_mandatory(v) for v in all_issues.values()) else 0
