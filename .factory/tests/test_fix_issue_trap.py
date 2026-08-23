"""fix-issue.sh EXIT trap 行为回归——提取真实 trap 载荷在沙箱中执行。

锚定两类事故（不 mock 断言文本，跑真 trap 字符串）：
- #23 / etf-radar#57：trap 内首命令非零（write_ledger 竞态 141）→ set -e
  中止清理链 → 标签/worktree/台账三重残留 → 队列死锁。根治 = trap 首动作
  set +e，失败模式收敛为"多打日志"。
- #14 / #5 三轮事故：失败链 implement 产出随 worktree 强删湮灭。根治 =
  失败且分支有新提交时 push 抢救；推送失败不得阻断后续清理（二次放大）。
"""

import re
import subprocess
import tempfile
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[1]

# 链 trap（含 write_ledger）；同文件还有一个早期放锁 trap，靠内容区分
_TRAPS = re.findall(r"trap '(.*?)' EXIT", (FACTORY / "fix-issue.sh").read_text(encoding="utf-8"), re.S)
PAYLOAD = next(t for t in _TRAPS if "write_ledger" in t)

SANDBOX = r"""#!/usr/bin/env bash
set -euo pipefail
REPO="__REPO__"
WT="__WT__"
BRANCH="factory/issue-99"
ISSUE="99"
MANUAL_LOCK=1
LOCKDIR="__LOCKDIR__"
CALLS="__CALLS__"
WR_RC=__WR_RC__
PUSH_RC=__PUSH_RC__
COUNT=__COUNT__
write_ledger() { echo "ledger:$1" >> "$CALLS"; return "$WR_RC"; }
git() {
  echo "git:$*" >> "$CALLS"
  case "$*" in
    *rev-list*) echo "$COUNT"; return 0 ;;
    *push*) return "$PUSH_RC" ;;
  esac
  return 0
}
issue_label() { echo "label:$*" >> "$CALLS"; }
trap '__PAYLOAD__' EXIT
exit __RC__
"""


def _run_trap(rc, wr_rc=0, push_rc=0, count="3"):
    """跑真实 trap 载荷一次，返回 (calls 行列表, LOCKDIR 是否已释放)。"""
    with tempfile.TemporaryDirectory() as tmp:
        lockdir = Path(tmp) / "dispatcher"
        lockdir.mkdir()
        (lockdir / "pid").write_text("42")
        calls = Path(tmp) / "calls"
        script = (SANDBOX
                  .replace("__REPO__", tmp)
                  .replace("__WT__", str(Path(tmp) / "wt"))
                  .replace("__LOCKDIR__", str(lockdir))
                  .replace("__CALLS__", str(calls))
                  .replace("__WR_RC__", str(wr_rc))
                  .replace("__PUSH_RC__", str(push_rc))
                  .replace("__COUNT__", count)
                  .replace("__RC__", str(rc))
                  .replace("__PAYLOAD__", PAYLOAD))
        sh = Path(tmp) / "sandbox.sh"
        sh.write_text(script)
        subprocess.run(["/bin/bash", str(sh)], capture_output=True)
        lines = calls.read_text().splitlines() if calls.exists() else []
        return lines, not lockdir.exists()


def _kinds(lines):
    return {ln.split(":", 1)[0] for ln in lines}


def test_trap_first_command_failure_still_cleans():
    """#23 核心：write_ledger 非零不得中止 trap——标签复位/worktree 回收/放锁全达成。"""
    lines, lock_released = _run_trap(rc=1, wr_rc=1)
    assert "ledger:1" in lines                       # 失败的命令确实执行过
    assert "label" in _kinds(lines)
    assert any("worktree" in l and "remove" in l for l in lines)
    assert lock_released                              # 清理链走到了最后一环


def test_salvage_push_on_failure():
    """#14 核心：失败 + 分支有新提交 → push 抢救（--force --no-verify）。"""
    lines, _ = _run_trap(rc=1, count="3")
    push = [l for l in lines if l.startswith("git:") and "push" in l]
    assert push and "--force" in push[0] and "--no-verify" in push[0]


def test_push_failure_does_not_block_cleanup():
    """#14 验收3：push 失败（网络）仅降级——后续 worktree 回收/标签/放锁照常。"""
    lines, lock_released = _run_trap(rc=1, push_rc=1)
    assert any(l.startswith("git:") and "push" in l for l in lines)
    assert any("worktree" in l and "remove" in l for l in lines)
    assert "label" in _kinds(lines)
    assert lock_released


def test_no_salvage_push_on_success():
    """成功路径（rc=0）不 push——成功路径推送在步骤 8（既有行为不变）。"""
    lines, lock_released = _run_trap(rc=0, count="3")
    assert not any(l.startswith("git:") and "push" in l for l in lines)
    assert any("worktree" in l and "remove" in l for l in lines)
    assert lock_released                          # 旧 set -e 形态此处会中断放锁


def test_no_salvage_when_branch_has_no_commits():
    """分支无新提交（main.."${BRANCH}" 计数 0，早期失败）不产生空推送。"""
    lines, _ = _run_trap(rc=1, count="0")
    assert not any(l.startswith("git:") and "push" in l for l in lines)
    assert "label" in _kinds(lines)
