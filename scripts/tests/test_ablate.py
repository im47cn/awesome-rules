"""ablate 配置面单测：臂名白名单（PR #53 审查⑧）。

build_prompt 把一切非 "with" 值当 WITHOUT 臂——拼错臂名（如 witih）曾
静默跑错实验并以错名记录。计划期拒绝 = rc 2；合法臂照常进入计划/dry-run。
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def run_ablate(*args):
    return subprocess.run(
        [sys.executable, "scripts/ablate/ablate.py", *args],
        cwd=REPO, capture_output=True, text=True)


def test_invalid_arm_rejected_at_plan_time():
    r = run_ablate("--skills", "api-guard", "--arms", "witih")
    assert r.returncode == 2
    assert "无效" in r.stderr and "witih" in r.stderr


def test_valid_arms_reach_plan():
    r = run_ablate("--skills", "api-guard", "--arms", "with,without",
                   "--limit", "1", "--dry-run")
    assert r.returncode == 0, r.stderr
