#!/usr/bin/env python3
"""
Open API 规范检查脚本
检查 Java 项目中的 API 定义是否符合 Open API 设计与安全规范。

用法:
  python3 api_check.py <file_or_dir> [--format text|json]

退出码: 0=通过, 1=有强制问题, 2=运行错误
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    MANDATORY = "强制"
    RECOMMENDED = "推荐"


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

ALLOWED_ACTIONS = {
    "create", "query", "update", "cancel", "sync", "confirm", "apply", "push",
}

PATH_VAR_PATTERN = re.compile(r"\{[^}]+\}")

SKIP_DIRS = {
    "target", "build", ".git", "node_modules", ".idea", ".vscode",
    ".gradle", ".mvn", "dist", "out", ".next", ".nuxt", "test", "tests",
}

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "REQUESTMAPPING"}


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


def check_path_structure(ep: ApiEndpoint, issues: list):
    """检查路径结构 /{domain}/{version}/{resource}/{action}。"""
    ctx = _ctx(ep)
    segments = [s for s in ep.path.split("/") if s]

    if len(segments) < 4:
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="路径结构不完整",
            location=f"路径:{ep.path}",
            description=f"路径段数 {len(segments)} 不足，标准格式 /domain/version/resource/action",
            suggestion="路径须为 /{domain}/{version}/{resource}/{action}"))


def check_http_method(ep: ApiEndpoint, issues: list):
    """统一用 POST。"""
    ctx = _ctx(ep)
    if ep.http_method and ep.http_method != "POST":
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="统一POST",
            location=f"路径:{ep.path} 方法:{ep.http_method}",
            description=f"使用了 {ep.http_method}，规范要求统一 POST",
            suggestion="所有 API 统一使用 POST 请求方式"))


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


def check_action_verb(ep: ApiEndpoint, issues: list):
    """末段（action）须使用收敛动词集。"""
    ctx = _ctx(ep)
    segments = [s for s in ep.path.split("/") if s]
    if len(segments) < 2:
        return
    last = segments[-1]
    if PATH_VAR_PATTERN.fullmatch(last):
        return

    # 检查是否动词前置（如 syncWaybill）
    camel_pattern = re.compile(r"^([a-z]+)([A-Z]\w+)$")
    cm = camel_pattern.match(last)
    if cm:
        verb = cm.group(1).lower()
        noun = cm.group(2).lower()
        if verb in ALLOWED_ACTIONS or noun in ALLOWED_ACTIONS:
            issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="动词后置",
                location=f"路径:{ep.path}",
                description=f"动作 '{last}' 动词前置，应为名词-动词序",
                suggestion=f"动词后置：/{noun}/{verb}"))
            return

    if last not in ALLOWED_ACTIONS:
        issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="动作收敛",
            location=f"路径:{ep.path}",
            description=f"末段 '{last}' 不在收敛动词集中",
            suggestion=f"动作收敛为: {', '.join(sorted(ALLOWED_ACTIONS))}"))


def check_path_variable(ep: ApiEndpoint, issues: list):
    """禁止 path 中传递唯一标识。"""
    ctx = _ctx(ep)
    if PATH_VAR_PATTERN.search(ep.path):
        issues.append(Issue(**ctx, severity=Severity.MANDATORY, rule="禁止path传标识",
            location=f"路径:{ep.path}",
            description="路径中包含路径变量 {var}",
            suggestion="禁止在 path 中传递唯一标识，改用请求体"))


def check_version_segment(ep: ApiEndpoint, issues: list):
    """第二段须为版本号（v1, v2...）。"""
    ctx = _ctx(ep)
    segments = [s for s in ep.path.split("/") if s]
    if len(segments) < 2:
        return
    version = segments[1]
    if not re.match(r"^v\d+$", version):
        issues.append(Issue(**ctx, severity=Severity.RECOMMENDED, rule="版本段",
            location=f"路径:{ep.path}",
            description=f"第二段 '{version}' 不是标准版本号（v1/v2...）",
            suggestion="路径第二段须为版本号，如 v1"))


def _ctx(ep: ApiEndpoint) -> dict:
    return {
        "file": ep.file_path,
        "endpoint": ep.path,
        "http_method": ep.http_method,
    }


ALL_CHECKS = [
    check_path_structure,
    check_http_method,
    check_kebab_case,
    check_action_verb,
    check_path_variable,
    check_version_segment,
]


def check_endpoint(ep: ApiEndpoint) -> list:
    """对单个端点执行全部检查。"""
    issues = []
    for check in ALL_CHECKS:
        check(ep, issues)
    return issues


# ── 文件发现与检查 ───────────────────────────────────────────────────────


def is_controller(path: str) -> bool:
    """判断 Java 文件是否为 Controller（含 @RestController/@Controller）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(4096)
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
        description="Open API 规范检查脚本 - 检查 Java Controller 中的 API 定义"
    )
    parser.add_argument("path", nargs="?", default=".", help="文件或项目目录路径（默认当前目录）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args()

    files = find_controller_files(args.path)

    if not files:
        print(f"未找到 Controller 文件: {args.path}", file=sys.stderr)
        return 2

    all_issues = {}
    total_mandatory = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_file = {executor.submit(check_file, f): f for f in sorted(files)}
        for future in as_completed(future_to_file):
            f = future_to_file[future]
            issues = future.result()
            all_issues[f] = issues
            total_mandatory += sum(
                1 for i in issues if i.severity == Severity.MANDATORY
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
