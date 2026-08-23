"""check_pipe_early_exit 单测：三犯原形拦截 / 安全等价形放行 / rc 语义。

对应用例（issue #30 验收标准 6）。负控制原则（steering/testing-standards
「自建关卡脚本的反作弊要求」）：先证明检查器会失败（三犯夹具 rc=1 且
报行号与规则），再证放行边界（消费全量形态 rc=0），最后证损坏路径
rc=2 绝不算通过。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "check_pipe_early_exit", _TOOLS / "check_pipe_early_exit.py")
assert _spec is not None and _spec.loader is not None
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

# 三犯原形（PR #9 `| true` / etf-radar#70 `grep -m1` 中位 / R2 head 中位
# + 反引号 `| true` 命令替换形态）
BAD = """#!/usr/bin/env bash
set -euo pipefail
changed="$(git diff main..HEAD | true)"
slug="$( { git remote; } | grep -m1 'github\\.com' | sed -E 's/x/y/')"
top="$(cat list | head -n 3 | wc -l)"
raw=`git diff | true`
"""

# 安全等价形：|| true（逻辑或层，非管道段）、sed -n '1p'（消费全量取首行）、
# head 末位（末位即目的）
OK = """#!/usr/bin/env bash
set -euo pipefail
out="$(git diff main 2>/dev/null || true)"
first="$(printf '%s\\n' "$x" | sed -n '1p')"
top="$(cat list | head)"
"""


def test_three_incident_forms_flagged_with_line_and_rule(tmp_path):
    f = tmp_path / "bad.sh"
    f.write_text(BAD, encoding="utf-8")
    v = M.check_file(f)
    rules = {msg.split(":", 1)[0] for _, msg in v}
    linenos = {ln for ln, _ in v}
    assert {"R1", "R2", "R3"} <= rules          # 三犯规则齐备
    assert {3, 4, 5, 6} <= linenos              # 行号指明（1 基）


def test_safe_equivalents_pass(tmp_path):
    f = tmp_path / "ok.sh"
    f.write_text(OK, encoding="utf-8")
    assert M.check_file(f) == []


def test_rc_semantics(tmp_path):
    """拦截 rc=1（stderr 带行号+规则）、干净 rc=0、损坏 rc=2。"""
    bad = tmp_path / "bad.sh"
    bad.write_text(BAD, encoding="utf-8")
    ok = tmp_path / "ok.sh"
    ok.write_text(OK, encoding="utf-8")
    checker = str(_TOOLS / "check_pipe_early_exit.py")

    r_bad = subprocess.run([sys.executable, checker, str(bad)],
                           capture_output=True, text=True)
    assert r_bad.returncode == 1
    assert "R1" in r_bad.stderr and "R2" in r_bad.stderr and "R3" in r_bad.stderr
    assert ":4:" in r_bad.stderr                # 行号指明

    r_ok = subprocess.run([sys.executable, checker, str(ok)],
                          capture_output=True, text=True)
    assert r_ok.returncode == 0

    r_missing = subprocess.run(
        [sys.executable, checker, str(tmp_path / "no-such-file")],
        capture_output=True, text=True)
    assert r_missing.returncode == 2            # 检查器损坏 ≠ 通过
