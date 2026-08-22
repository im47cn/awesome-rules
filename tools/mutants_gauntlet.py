#!/usr/bin/env python3
"""手动变异冒烟：对 gauntlet 门自身注入缺陷，证明自测能抓到语义被破坏。

用法: python3 tools/mutants_gauntlet.py
退出码 0 当且仅当全部变异被击杀。

语义（与 testing-standards.md「退出码语义」一致）：
- 自测 rc=1（确实跑了且有失败）→ KILLED
- rc=0 → SURVIVED（门被破坏但自测放行——最严重）
- 其他 rc → 无效运行，本次结论作废
还原：内存备份 + finally 写回 + 读回比对，绝不使用 git 还原（工作树可能含
人工未提交修改）。模式唯一性 count==1 前置校验，防替换落错位置。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (名称, 目标文件, 原文, 变异文, 抓它的自测)
MUTANTS = [
    (
        "M1 run_layer 吞掉层失败（|| true 化）",
        "tools/gauntlet.sh",
        '    "$@"\n',
        '    "$@" || true\n',
        ["sh", "tools/test_gauntlet_orchestration.sh"],
    ),
    (
        "M2 require_dir 失效（缺失目录静默放行）",
        "tools/gauntlet.sh",
        'if [ ! -d "$_d" ]; then',
        "if false; then",
        ["sh", "tools/test_gauntlet_orchestration.sh"],
    ),
    (
        "M3 陈旧产物不清理（读取上次运行残留）",
        "tools/gauntlet.sh",
        "find . -name .coverage -type f -not -path './.git/*' -delete",
        ":",
        ["sh", "tools/test_gauntlet_orchestration.sh"],
    ),
    (
        "M4 must_not_match 命中/无匹配分支互换（拦的放行、放的拦截）",
        "tools/must_not_match.sh",
        'if [ "$_rc" -eq 0 ]; then',
        'if [ "$_rc" -eq 1 ]; then',
        ["sh", "tools/test_gauntlet_checks.sh"],
    ),
]


def run() -> int:
    killed = 0
    errors = 0
    for name, rel, old, new, test_cmd in MUTANTS:
        target = ROOT / rel
        original = target.read_text()
        if original.count(old) != 1:
            print(f"{name}: ERROR 模式不唯一（count={original.count(old)}），跳过该变异，本次运行无效")
            errors += 1
            continue
        try:
            target.write_text(original.replace(old, new))
            proc = subprocess.run(test_cmd, cwd=ROOT, capture_output=True, text=True)
            rc = proc.returncode
        finally:
            target.write_text(original)
        if target.read_text() != original:
            print(f"{name}: FATAL 还原后字节不一致，需人工介入")
            return 3
        if rc == 1:
            verdict = "KILLED"
            killed += 1
        elif rc == 0:
            verdict = "SURVIVED"
        else:
            verdict = f"ERROR (自测 rc={rc}，无有效验证)"
            errors += 1
        print(f"{name}: {verdict}")
    print(f"\n{killed}/{len(MUTANTS)} mutants killed")
    if errors:
        print(f"{errors} 个无效运行——本次结论作废")
        return 1
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(run())
