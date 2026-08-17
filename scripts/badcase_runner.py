#!/usr/bin/env python3
"""
Badcase 回归测试工具

扫描所有技能的 badcase/ 目录，对每个 badcase 运行检查脚本，
将实际检出结果与 expected.md 中声明的期望规则进行比对。

每个 badcase 包含:
  - input/      : 共享待审查文件
  - expected.md : 期望结果（check 脚本 + 规则列表），只写一次
  - prompts.md  : 提示词集 + 已知问题（仅记录，不影响通过/失败）

expected.md 期望模型（双通道）:
  - 「## 预期检查输出」小节存在时，只认其中的 bullet：
      - 脚本自动检出：<规则>、<规则>…  → 拆分为期望规则，参与比对
      - 人工补充：<说明>              → 仅记录展示，不参与比对（脚本本就检不出）
  - 无该小节（旧式）：第一个 ## 标题前的顶层 bullet 作为期望规则

用法:
  python3 scripts/badcase_runner.py                     # 运行所有 badcase
  python3 scripts/badcase_runner.py --skill ddl-guard    # 只运行指定技能
  python3 scripts/badcase_runner.py --verbose            # 显示实际检出详情

退出码: 0=全部通过, 1=存在失败
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BadcaseResult:
    skill: str
    name: str
    path: str
    passed: bool = True
    expected_rules: list = field(default_factory=list)
    manual_rules: list = field(default_factory=list)
    actual_rules: list = field(default_factory=list)
    missing_rules: list = field(default_factory=list)
    scripts_run: list = field(default_factory=list)
    prompts: list = field(default_factory=list)
    known_issues: list = field(default_factory=list)
    error: str = ""


def find_project_root() -> Path:
    """通过查找 skills/ 目录定位项目根目录。"""
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "skills").is_dir():
            return p
        p = p.parent
    return Path(__file__).resolve().parent.parent


def find_check_scripts(skill_dir: Path):
    """查找技能 scripts/ 目录下所有 *_check.py 脚本。"""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(scripts_dir.glob("*_check.py"))


def parse_expected(expected_path: Path):
    """解析 expected.md，返回 (check_script, expected_rules, manual_rules)。

    双通道期望模型（见模块 docstring）：脚本自动检出参与比对，
    人工补充仅记录不比对——把人工审查项计入失败会让 runner 永远红着。
    """
    if not expected_path.is_file():
        return None, [], []

    text = expected_path.read_text(encoding="utf-8")

    check_script = None
    m = re.search(r"(?:check|脚本)\s*[:：]\s*(\S+\.py)", text)
    if m:
        check_script = m.group(1).strip()

    expected_rules, manual_rules = [], []

    def _split_rules(payload: str):
        return [p.strip() for p in re.split(r"[、,，;；]", payload) if p.strip()]

    section = re.search(r"##\s*预期检查输出\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL)
    if section:
        # 新式：只认「预期检查输出」小节的 bullet
        for line in section.group(1).split("\n"):
            m = re.match(r"^[-*]\s+(.+)", line.strip())
            if not m:
                continue
            item = m.group(1).strip()
            if item.startswith("脚本自动检出"):
                expected_rules.extend(_split_rules(
                    re.split(r"[:：]", item, 1)[-1]))
            elif item.startswith("人工补充"):
                manual_rules.append(re.split(r"[:：]", item, 1)[-1].strip())
            elif item and not item.startswith("#"):
                expected_rules.append(item)
    else:
        # 旧式：第一个 ## 标题前的顶层 bullet（违规语句/改进建议等
        # 小节里的 bullet 是给人工看的叙述，不是脚本期望）
        head = re.split(r"\n##\s", text, 1)[0]
        for line in head.split("\n"):
            m = re.match(r"^[-*]\s+(.+)", line.strip())
            if m:
                rule = m.group(1).strip()
                if rule and not rule.startswith("#"):
                    expected_rules.append(rule)

    return check_script, expected_rules, manual_rules


def parse_prompts(prompts_path: Path):
    """解析 prompts.md，返回 (prompts, known_issues)。"""
    if not prompts_path.is_file():
        return [], []

    text = prompts_path.read_text(encoding="utf-8")

    # 提取"已知问题"section
    known_section = ""
    km = re.search(r"##\s*已知问题\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL)
    if km:
        known_section = km.group(1).strip()
        # 从 text 中移除已知问题部分，避免解析到 prompts
        text = text[: km.start()] + text[km.end():]

    prompts = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^[-*]\s+(.+)", line)
        if m:
            prompt = m.group(1).strip()
            if prompt:
                prompts.append(prompt)

    known_issues = []
    for line in known_section.split("\n"):
        line = line.strip()
        m = re.match(r"^[-*]\s+(.+)", line)
        if m:
            known_issues.append(m.group(1).strip())

    return prompts, known_issues


def run_check_script(script_path: Path, input_dir: Path):
    """运行检查脚本，返回 (issues, error)。"""
    try:
        result = subprocess.run(
            ["python3", str(script_path), str(input_dir), "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return [], f"脚本超时: {script_path.name}"
    except Exception as e:
        return [], f"脚本执行异常: {e}"

    if result.returncode == 2:
        stderr = result.stderr.strip()
        if "未找到" in stderr or "not found" in stderr.lower():
            return [], ""
        return [], f"脚本运行错误: {stderr}"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], "无法解析脚本输出 (JSON 格式错误)"

    issues = []
    if isinstance(data, list):
        for file_result in data:
            issues.extend(file_result.get("issues", []))
    elif isinstance(data, dict):
        issues.extend(data.get("issues", []))

    return issues, ""


def rule_matches(expected_rule: str, actual_rules: list) -> bool:
    """检查期望规则是否被实际检出（子串匹配）。"""
    expected_lower = expected_rule.lower()
    for actual in actual_rules:
        actual_lower = actual.lower()
        if expected_lower in actual_lower or actual_lower in expected_lower:
            return True
    return False


def run_badcase(skill_name, case_name, case_dir: Path, project_root: Path):
    """运行单个 badcase，返回结果。"""
    skill_dir = project_root / "skills" / skill_name
    input_dir = case_dir / "input"
    expected_path = case_dir / "expected.md"
    prompts_path = case_dir / "prompts.md"

    prompts, known_issues = parse_prompts(prompts_path)
    check_script, expected_rules, manual_rules = parse_expected(expected_path)

    result = BadcaseResult(
        skill=skill_name, name=case_name, path=str(case_dir),
        expected_rules=expected_rules, manual_rules=manual_rules,
        prompts=prompts, known_issues=known_issues,
    )

    # 无 expected.md → 跳过
    if not expected_path.is_file():
        result.error = "无 expected.md，跳过"
        result.passed = True
        return result

    # 确定运行哪些脚本
    all_scripts = find_check_scripts(skill_dir)
    if check_script:
        scripts_to_run = [s for s in all_scripts if s.name == check_script]
        if not scripts_to_run:
            candidate = skill_dir / "scripts" / check_script
            if candidate.is_file():
                scripts_to_run = [candidate]
    else:
        scripts_to_run = all_scripts

    if not scripts_to_run:
        result.error = "未找到检查脚本"
        result.passed = False
        return result

    # 运行脚本（对共享 input 只跑一次）
    all_issues = []
    scripts_run = []
    errors = []
    for script_path in scripts_to_run:
        issues, err = run_check_script(script_path, input_dir)
        if err:
            errors.append(f"{script_path.name}: {err}")
        else:
            scripts_run.append(script_path.name)
        all_issues.extend(issues)

    result.scripts_run = scripts_run

    actual_rules = list(dict.fromkeys(
        i.get("rule", "") for i in all_issues if i.get("rule")
    ))
    result.actual_rules = actual_rules

    if errors:
        result.error = "; ".join(errors)

    # 比对期望规则
    if expected_rules:
        missing = [r for r in expected_rules if not rule_matches(r, actual_rules)]
        result.missing_rules = missing
        result.passed = len(missing) == 0
    else:
        result.passed = True

    return result


def print_result(result: BadcaseResult, verbose=False):
    """打印单个 badcase 结果。"""
    green, red, dim, reset = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
    use_color = sys.stdout.isatty()

    def c(text, color):
        return f"{color}{text}{reset}" if use_color else text

    status = "✓ PASS" if result.passed else "✗ FAIL"
    status_colored = c(status, green if result.passed else red)

    print(f"\n{'─'*55}")
    print(f"  {status_colored}  [{result.skill}] {result.name}")
    print(f"{'─'*55}")

    if result.error:
        print(f"  {c('⚠', red)} {result.error}")

    if result.scripts_run:
        print(f"  脚本: {', '.join(result.scripts_run)}")

    # 提示词
    if result.prompts:
        print(f"  提示词 ({len(result.prompts)} 条):")
        for p in result.prompts:
            preview = p if len(p) <= 55 else p[:52] + "..."
            print(f"    {c('•', dim)} {preview}")

    # 已知问题
    if result.known_issues:
        print(f"  {c('已知问题', dim)}:")
        for issue in result.known_issues:
            preview = issue if len(issue) <= 65 else issue[:62] + "..."
            print(f"    {c('!', dim)} {preview}")

    # 期望规则
    if result.expected_rules:
        print(f"  期望检出 {len(result.expected_rules)} 条规则:")
        for rule in result.expected_rules:
            if rule in result.missing_rules:
                print(f"    {c('✗', red)} {rule} {c('(未检出)', red)}")
            else:
                print(f"    {c('✓', green)} {rule}")

    # 人工补充（双通道期望模型：不参与比对，仅提示人工审查范围）
    if result.manual_rules:
        print(f"  {c('人工补充（不参与脚本比对）', dim)}:")
        for rule in result.manual_rules:
            print(f"    {c('•', dim)} {rule}")

    # 实际检出
    if verbose or not result.passed:
        if result.actual_rules:
            print(f"  实际检出 {len(result.actual_rules)} 条规则:")
            for rule in result.actual_rules:
                print(f"    {c('→', dim)} {rule}")


def discover_badcases(project_root: Path, skill_filter=None):
    """发现所有 badcase 目录。"""
    badcases = []
    skills_dir = project_root / "skills"
    if not skills_dir.is_dir():
        return badcases

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        if skill_filter and skill_name != skill_filter:
            continue

        badcase_dir = skill_dir / "badcase"
        if not badcase_dir.is_dir():
            continue

        for case_dir in sorted(badcase_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            if not (case_dir / "input").is_dir():
                continue
            badcases.append((skill_name, case_dir.name, case_dir))

    return badcases


def main():
    parser = argparse.ArgumentParser(
        description="Badcase 回归测试工具 — 对所有 badcase 运行检查脚本并比对期望结果"
    )
    parser.add_argument("--skill", help="只运行指定技能的 badcase")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示实际检出详情")
    args = parser.parse_args()

    project_root = find_project_root()
    badcases = discover_badcases(project_root, args.skill)

    if not badcases:
        print("未找到 badcase 目录。")
        scan_path = f"{project_root}/skills/*/badcase/*/"
        print(f"  扫描路径: {scan_path}")
        return 0

    print(f"{'='*55}")
    print(f"  Badcase 回归测试")
    print(f"  共 {len(badcases)} 个 badcase")
    print(f"{'='*55}")

    results = []
    for skill_name, case_name, case_dir in badcases:
        result = run_badcase(skill_name, case_name, case_dir, project_root)
        results.append(result)
        print_result(result, args.verbose)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    green, red, reset = "\033[32m", "\033[31m", "\033[0m"
    use_color = sys.stdout.isatty()

    print(f"\n{'='*55}")
    summary = f"总计: {len(results)} 个 badcase, {passed} 通过, {failed} 失败"
    color = green if failed == 0 else red
    print(f"  {color}{summary}{reset}" if use_color else f"  {summary}")
    print(f"{'='*55}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
