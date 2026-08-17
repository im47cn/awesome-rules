#!/usr/bin/env python3
"""
业务接口规范检查脚本
检查 Java 项目中业务 Controller（@RestController）的 API 定义是否符合规范。

仅覆盖业务接口通用规则（路径命名、禁止 path 传标识、时间注解），
不检查对外 Open API 四段式规范（四段式请见 steering/openapi-standards.md）。

用法:
  python3 api_check.py <file_or_dir> [--format text|json]

退出码: 0=通过, 1=有强制问题, 2=运行错误
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass

# guard 共享库（Severity / SKIP_DIRS / 报告骨架）
_SHARED = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from guard_lib import SKIP_DIRS, Severity, run_gate  # noqa: E402


@dataclass
class Issue:
    file: str
    endpoint: str
    http_method: str
    severity: Severity
    rule: str
    location: str
    description: str
    suggestion: str = ""


# ── 常量 ─────────────────────────────────────────────────────────────────

# 末段（action）允许的收敛动词集
ALLOWED_ACTIONS = {
    "create", "query", "update", "remove", "cancel", "sync", "confirm", "apply", "push",
}

PATH_VAR_PATTERN = re.compile(r"\{[^}]+\}")

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "REQUESTMAPPING"}

# 契约/持久化对象类名后缀（可能含时间字段 @JsonFormat），用于时间注解检查
CONTRACT_CLASS_RE = re.compile(r"\bclass\s+\w*(?:DTO|PO|Command|Query)\b")
PO_CLASS_RE = re.compile(r"\bclass\s+\w*PO\b")
# 废弃的时间戳序列化：@JsonFormat(shape = NUMBER) 或 @JsonFormat(shape = JsonFormat.Shape.NUMBER)
JSONFORMAT_NUMBER_RE = re.compile(
    r'@JsonFormat\s*\([^)]*\bshape\s*=\s*(?:JsonFormat\.Shape\.)?NUMBER',
    re.DOTALL,
)
JSONFORMAT_ANY_RE = re.compile(r'@JsonFormat')


# ── Java 文件解析 ────────────────────────────────────────────────────────


@dataclass
class ApiEndpoint:
    http_method: str
    path: str
    class_path: str
    method_name: str
    file_path: str
    line: int


def strip_java_comments(content: str) -> str:
    """移除 Java 注释，保留行号。"""
    content = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"),
                     content, flags=re.DOTALL)
    content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
    return content


def extract_endpoints(content: str, file_path: str):
    """从 Java 文件提取 @RequestMapping / @PostMapping 等注解定义的 API 端点。"""
    endpoints = []

    # 类级 @RequestMapping
    class_mapping = ""
    cm = re.search(r"class\s+\w+[^{]*?\{", content)
    if cm:
        before_class = content[: cm.start()]
        rm = re.search(
            r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]+)"', before_class
        )
        if rm:
            class_mapping = rm.group(1)

    # 方法级映射注解
    mapping_pattern = re.compile(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)'
        r'\s*\(\s*(?:value\s*=\s*|path\s*=\s*)?"([^"]*)"'
        r'([^)]*)\)',
        re.MULTILINE,
    )

    for m in mapping_pattern.finditer(content):
        # 跳过类级注解（后面跟 class 而非方法）
        after_match = content[m.end():m.end() + 200]
        if re.match(r"\s*(?:public\s+|abstract\s+)*class\s", after_match):
            continue

        ann_type = m.group(1)
        path = m.group(2)
        extra = m.group(3)

        http_method = {
            "GetMapping": "GET",
            "PostMapping": "POST",
            "PutMapping": "PUT",
            "DeleteMapping": "DELETE",
            "PatchMapping": "PATCH",
            "RequestMapping": "REQUESTMAPPING",
        }.get(ann_type, "")

        # @RequestMapping 的 method
        if ann_type == "RequestMapping":
            mm = re.search(r"method\s*=\s*(\w+\.\w+)", extra)
            if mm:
                method_name = mm.group(1).split(".")[-1].upper()
                if method_name in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    http_method = method_name

        full_path = (class_mapping or "") + path
        if not full_path.startswith("/"):
            full_path = "/" + full_path

        line = content[: m.start()].count("\n") + 1

        # 提取方法名
        after = content[m.end():]
        method_m = re.search(r"\w+\s+(\w+)\s*\(", after)
        method_name = method_m.group(1) if method_m else "(匿名)"

        endpoints.append(ApiEndpoint(
            http_method=http_method,
            path=full_path,
            class_path=class_mapping or "",
            method_name=method_name,
            file_path=file_path,
            line=line,
        ))

    return endpoints


# ── 规则检查 ─────────────────────────────────────────────────────────────


def check_kebab_case(ep: ApiEndpoint, issues: list):
    """路径全小写 kebab-case，禁止 camelCase。"""
    ctx = _ctx(ep)
    segments = [s for s in ep.path.split("/") if s]
    for seg in segments:
        if PATH_VAR_PATTERN.fullmatch(seg):
            continue
        if re.search(r"[A-Z]", seg):
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="路径命名",
                location=f"路径:{ep.path} 段:{seg}",
                description=f"路径段 '{seg}' 包含大写字母",
                suggestion="路径全小写 kebab-case，禁止 camelCase"))
            return
        if "_" in seg:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="路径命名",
                location=f"路径:{ep.path} 段:{seg}",
                description=f"路径段 '{seg}' 包含下划线",
                suggestion="路径使用 kebab-case（短横线），禁止下划线"))
            return


def check_path_variable(ep: ApiEndpoint, issues: list):
    """禁止 path 中传递唯一标识。"""
    ctx = _ctx(ep)
    if PATH_VAR_PATTERN.search(ep.path):
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="禁止path传标识",
            location=f"路径:{ep.path}",
            description="路径中包含路径变量 {var}",
            suggestion="禁止在 path 中传递唯一标识，改用请求体"))


def _not_converged_issue(ctx: dict, ep: ApiEndpoint, last: str) -> Issue:
    """末段不在收敛动词集 → 推荐级 issue。"""
    return Issue(**ctx, severity=Severity.RECOMMENDED, rule="动作收敛",
        location=f"路径:{ep.path}",
        description=f"末段 '{last}' 不在收敛动词集中",
        suggestion=f"动作收敛为: {', '.join(sorted(ALLOWED_ACTIONS))}")


def check_action_verb(ep: ApiEndpoint, issues: list):
    """末段（action）须使用收敛动词集，且动词后置（名词-动词序）。

    判定规则（camelCase 末段按大写边界拆词）：
    - 单字：在收敛动词集中即合规。
    - 多字：首个收敛动词位于首位 → 动词前置（违规）；
      位于非首位 → 名词-动词序（合规）；无收敛动词 → 动作不收敛。
    """
    ctx = _ctx(ep)
    segments = [s for s in ep.path.split("/") if s]
    if len(segments) < 2:
        return
    last = segments[-1]
    if PATH_VAR_PATTERN.fullmatch(last):
        return

    camel_parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', last).split()

    # 单字：直接判断是否在收敛动词集
    if len(camel_parts) == 1:
        if last not in ALLOWED_ACTIONS:
            issues.append(_not_converged_issue(ctx, ep, last))
        return

    # 多字：定位首个收敛动词的位置
    verb_idx = next(
        (i for i, p in enumerate(camel_parts) if p.lower() in ALLOWED_ACTIONS),
        None,
    )
    if verb_idx is None:
        issues.append(_not_converged_issue(ctx, ep, last))
        return

    if verb_idx == 0:
        # 动词在首位 → 动词前置，应为名词-动词序
        noun = ''.join(camel_parts[1:]).lower()
        verb = camel_parts[0].lower()
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="动词后置",
            location=f"路径:{ep.path}",
            description=f"动作 '{last}' 动词前置，应为名词-动词序",
            suggestion=f"动词后置：/{noun}/{verb}"))
    # verb_idx >= 1：动词后置（名词在前），合规


def _ctx(ep: ApiEndpoint) -> dict:
    return {
        "file": ep.file_path,
        "endpoint": ep.path,
        "http_method": ep.http_method,
    }


# 业务接口规范检查集：与段数无关的通用规则（命名 + 动作收敛 + path 变量）。
# 四段式结构 / 统一 POST / 版本段属对外 Open API 规范，不在此检查。
CHECKS = [
    check_kebab_case,
    check_action_verb,
    check_path_variable,
]


def check_endpoint(ep: ApiEndpoint) -> list:
    """对单个端点执行业务接口规范检查。"""
    issues = []
    for check in CHECKS:
        check(ep, issues)
    return issues


# ── 文件发现与检查 ───────────────────────────────────────────────────────


def is_controller(path: str) -> bool:
    """判断 Java 文件是否为 Controller（含 @RestController/@Controller）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(8192)
        return bool(re.search(r"@(Rest)?Controller\b", content))
    except (UnicodeDecodeError, OSError):
        return False


def find_controller_files(path: str) -> list:
    """查找含 API 映射注解的 Java Controller 文件。"""
    java_files = []

    if os.path.isfile(path):
        if path.endswith(".java") and is_controller(path):
            java_files = [path]
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".java"):
                    full = os.path.join(dirpath, fn)
                    if is_controller(full):
                        java_files.append(full)

    return java_files


def is_contract_file(path: str) -> bool:
    """判断 Java 文件是否为 DTO/PO/Command/Query 等契约/持久化对象（可能含时间字段注解）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(16384)
        return bool(CONTRACT_CLASS_RE.search(content))
    except (UnicodeDecodeError, OSError):
        return False


def find_contract_files(path: str) -> list:
    """查找 DTO/PO/Command/Query 契约对象文件。"""
    files = []
    if os.path.isfile(path):
        if path.endswith(".java") and is_contract_file(path):
            files = [path]
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".java"):
                    full = os.path.join(dirpath, fn)
                    if is_contract_file(full):
                        files.append(full)
    return files


def _extract_class_name(content: str) -> str:
    """提取首个类名，用于 Issue.endpoint 定位。"""
    m = re.search(r"\bclass\s+(\w+)", content)
    return m.group(1) if m else "(类级)"


def check_file(file_path: str) -> list:
    """检查单个 Controller 文件，返回 issues 列表。"""
    issues = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError) as e:
        issues.append(Issue(
            file=file_path, endpoint="(文件级)", http_method="",
            severity=Severity.MANDATORY, rule="文件读取错误",
            location=file_path, description=str(e),
        ))
        return issues

    content = strip_java_comments(content)
    endpoints = extract_endpoints(content, file_path)

    if not endpoints:
        return issues

    for ep in endpoints:
        issues.extend(check_endpoint(ep))

    return issues


def check_time_annotation(file_path: str, content: str) -> list:
    """检查 DTO/PO 时间字段注解（04-database-mybatis §1）：
    - 禁止 @JsonFormat(shape = NUMBER)（须 ISO 8601 pattern）
    - PO 禁止任何日期格式化注解
    """
    issues = []
    clean = strip_java_comments(content)
    class_name = _extract_class_name(clean)
    is_po = bool(PO_CLASS_RE.search(clean)) or "/infrastructure/repository/po/" in file_path

    for m in JSONFORMAT_NUMBER_RE.finditer(clean):
        line = clean[:m.start()].count("\n") + 1
        issues.append(Issue(
            file=file_path, endpoint=class_name, http_method="",
            severity=Severity.MANDATORY, rule="时间注解",
            location=f"{file_path}:{line}",
            description="时间格式须用 ISO 8601 pattern，禁止时间戳 shape=NUMBER",
            suggestion='改为 @JsonFormat(pattern = "yyyy-MM-dd\'T\'HH:mm:ss.SSSXXX", timezone = "+08:00")',
        ))

    if is_po:
        for m in JSONFORMAT_ANY_RE.finditer(clean):
            line = clean[:m.start()].count("\n") + 1
            issues.append(Issue(
                file=file_path, endpoint=class_name, http_method="",
                severity=Severity.MANDATORY, rule="PO禁日期注解",
                location=f"{file_path}:{line}",
                description="PO 禁止任何日期格式化注解（日期格式化由 DTO 层负责）",
                suggestion="删除 PO 上的 @JsonFormat",
            ))
    return issues


def check_contract_file(file_path: str) -> list:
    """检查单个契约对象文件的时间注解。"""
    issues = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError) as e:
        issues.append(Issue(
            file=file_path, endpoint="(文件级)", http_method="",
            severity=Severity.MANDATORY, rule="文件读取错误",
            location=file_path, description=str(e),
        ))
        return issues
    issues.extend(check_time_annotation(file_path, content))
    return issues


# ── 报告格式 ─────────────────────────────────────────────────────────────


def format_report_text(file_path: str, issues: list) -> str:
    if not issues:
        return f"✓ {file_path} — 检查通过\n"

    mandatory = [i for i in issues if i.severity == Severity.MANDATORY]
    recommended = [i for i in issues if i.severity == Severity.RECOMMENDED]

    lines = [
        f"{'='*60}",
        f"API 审查报告: {file_path}",
        f"{'='*60}",
        f"  【强制】问题: {len(mandatory)} 项",
        f"  【推荐】问题: {len(recommended)} 项",
        "",
    ]

    for issue in issues:
        lines.append(f"  [{issue.severity.value}] {issue.rule}")
        lines.append(f"    端点: {issue.http_method} {issue.endpoint}")
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
                "endpoint": i.endpoint,
                "http_method": i.http_method,
                "severity": i.severity.value,
                "rule": i.rule,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in issues
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── 主流程 ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="业务接口规范检查脚本 - 检查 Java Controller 的路径命名与 path 变量"
    )
    parser.add_argument("path", nargs="?", default=".", help="文件或项目目录路径（默认当前目录）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args()

    ctrl_files = find_controller_files(args.path)
    contract_files = find_contract_files(args.path)

    if not ctrl_files and not contract_files:
        print(f"未找到 Controller 或契约对象(DTO/PO/Command/Query)文件: {args.path}", file=sys.stderr)
        return 2

    all_targets = [(f, check_file) for f in ctrl_files]
    all_targets += [(f, check_contract_file) for f in contract_files]
    return run_gate(
        all_targets, args.format, format_report_text, format_report_json,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
