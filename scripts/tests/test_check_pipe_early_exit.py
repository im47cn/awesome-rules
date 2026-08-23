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



def test_review_regressions_or_boundary(tmp_path):
    """`||` 后管道边界保留（Sourcery #32 评论1）：`false || true | cat`
    = false || (true | cat)，true 是真管道段 → R3；反向 `a | b || true`
    与裸 `x || true` 的 true 无管道邻接 → 放行。"""
    assert any(r == "R3" for r, _ in M.check_line("false || true | cat"))
    assert M.check_line("a | b || true") == []
    assert M.check_line("git diff || true") == []
    # `cat || grep -m1 x | sed`：grep -m1 是其后管道左端 → R1
    assert any(r == "R1" for r, _ in M.check_line("cat || grep -m1 x | sed s/a/b/"))
    # `grep -m1 x || cat y`：grep 未接管道 → 放行（旧版按段首误判）
    assert M.check_line("grep -m1 x || cat y") == []


def test_review_regressions_escape_and_comment(tmp_path):
    """转义管道与行内注释（评论2）：`\\|` 是字面量、词首 # 起注释；
    词中 #（`true#c`）仍是字面量，管道照判。"""
    assert M.check_line("printf x \\| true") == []
    assert M.check_line("echo ok # | true") == []
    assert any(r == "R3" for r, _ in M.check_line("cat f | true#c"))


def test_review_regressions_heredoc_suffix(tmp_path):
    """heredoc 起始带后缀（评论3）：`cat <<'EOF' | sed` 的体是数据，
    体中违规形态不作数；起始行自身的违规照判；同行双 heredoc 按序消费。"""
    f = tmp_path / "hd_ok.sh"
    f.write_text("#!/bin/bash\ncat <<'EOF' | sed s/a/b/\nthis | true\n"
                 "grep -m1 x | head\nEOF\necho done | wc -l\n", encoding="utf-8")
    assert M.check_file(f) == []

    f = tmp_path / "hd_bad.sh"
    f.write_text("cat <<EOF | true\nbody\nEOF\n", encoding="utf-8")
    v = M.check_file(f)
    assert len(v) == 1 and v[0][0] == 1 and v[0][1].startswith("R3"), v

    f = tmp_path / "hd_two.sh"
    f.write_text("cat <<A <<B | wc -l\nx | true\nA\ny | true\nB\necho ok\n",
                 encoding="utf-8")
    assert M.check_file(f) == []


def test_review_regression_non_utf8_dir_scan_rc2(tmp_path):
    """非 UTF-8 文件名（评论4）：git ls-files 输出解码失败 → rc=2
    （检查器损坏 ≠ 通过），不得裸 traceback。"""
    import os
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    # macOS APFS 拒绝创建非 UTF-8 文件名，走 index 直插（hash-object +
    sha = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                         input=b"#!/bin/sh\n", capture_output=True,
                         check=True).stdout.decode().strip()
    bad_name = os.fsdecode(b"bad\xff.sh")
    subprocess.run(["git", "-C", str(repo), "update-index", "--add", "--cacheinfo",
                    f"100644,{sha},{bad_name}"],
                   check=True, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"})
    checker = str(_TOOLS / "check_pipe_early_exit.py")
    r = subprocess.run([sys.executable, checker, str(repo)],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "检查器自身失败" in r.stderr
    assert "Traceback" not in r.stderr
