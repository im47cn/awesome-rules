"""dispatch 进程编排单测 —— 全部锚定 ADR-005 下沉动机（bash 进程原语缺陷类）。

缺陷→测试映射:
- jobs 表/wait 落空（0d947f60）→ TestChainPool：槽上限真并发测量（start/end
  时间戳区间重叠峰值）+ 全量收割 + 退出码可观测（bash 裸 wait 无 rc）
  + 日志目录缺省自建 + FACTORY_DISPATCHED 环境契约
- 锁原语（39b6b8ec 的 mkdir+PID 形态本体）→ TestDispatchLock：原子占 /
  陈锁接管 / 垃圾 pid 接管 / 活锁拒让 / 父目录缺省不误读
- REPO_SLUG 管道早退（a4d81930 / #30）与 heredoc 内联排序过滤（曾不可测）
  → TestDispatchParsers：纯函数直接测
"""

import os
import subprocess
from pathlib import Path

from factory_lib import (
    ChainPool,
    acquire_dispatch_lock,
    approved_prs,
    extract_slug,
    release_dispatch_lock,
    sort_by_priority,
)

# 测试链：输出带纪元时间戳——并发峰值必须按真实时序测，按 issue 分组拼接
# 日志会抹平交错（首版测试自身的缺陷，非被测代码缺陷）
_CHAIN = """#!/usr/bin/env bash
ts() { python3 -c 'import time; print(f"{time.time():.6f}")'; }
echo "start $1 $(ts)"
sleep "${CHAIN_SLEEP:-1}"
echo "end $1 $(ts)"
exit "${CHAIN_RC:-0}"
"""


def _factory_with_chain(tmp_path: Path) -> Path:
    f = tmp_path / "factory"
    f.mkdir()
    p = f / "fix-issue.sh"
    p.write_text(_CHAIN, encoding="utf-8")
    p.chmod(0o755)
    return f


def _lines(factory: Path, issue: int) -> list[str]:
    log = factory / "artifacts" / f"issue-{issue}" / "dispatch.log"
    return [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln]


class TestChainPool:
    def test_max_parallel_respected_and_all_ran(self, tmp_path):
        """MAX=2 派 5 链：按 start/end 时间戳区间算重叠峰值恰为 2
        （`jobs -rp | wc -l` 清点竞态在 Popen 句柄模型下不可表达），
        5 链全部跑完且各留下成对边界。"""
        f = _factory_with_chain(tmp_path)
        pool = ChainPool(f, max_parallel=2, poll_secs=0.05)
        for n in (1, 2, 3, 4, 5):
            pool.spawn(n)
        pool.wait_all()
        marks = []
        for n in range(1, 6):
            lines = _lines(f, n)
            assert len(lines) == 2 and lines[0].startswith("start") \
                and lines[1].startswith("end"), f"issue-{n} 链未完整跑完: {lines}"
            marks.append((float(lines[0].split()[2]), 1))   # 区间开
            marks.append((float(lines[1].split()[2]), -1))  # 区间闭
        marks.sort()
        running = peak = 0
        for _, delta in marks:
            running += delta
            peak = max(peak, running)
        assert peak == 2

    def test_wait_all_collects_exit_codes(self, tmp_path, monkeypatch):
        """bash 轮末裸 wait 无退出码 → done 收割 (issue, rc) 链路失败可观测。"""
        f = _factory_with_chain(tmp_path)
        monkeypatch.setenv("CHAIN_RC", "7")
        monkeypatch.setenv("CHAIN_SLEEP", "0")
        pool = ChainPool(f, max_parallel=2, poll_secs=0.05)
        pool.spawn(3)
        pool.wait_all()
        assert pool.done == [(3, 7)]

    def test_dispatch_log_appended_and_dir_autocreated(self, tmp_path, monkeypatch):
        """链输出尾追 artifacts/issue-N/dispatch.log；父目录缺省自建——
        bash `>>` 对缺目录静默死链（链从未起跑）的形态修复。"""
        f = _factory_with_chain(tmp_path)
        monkeypatch.setenv("CHAIN_SLEEP", "0")
        pool = ChainPool(f, max_parallel=1, poll_secs=0.05)
        pool.spawn(9)
        pool.wait_all()
        pool.spawn(9)
        pool.wait_all()
        assert len([ln for ln in _lines(f, 9)
                    if ln.startswith("start 9")]) == 2

    def test_spawn_env_marks_dispatched(self, tmp_path, monkeypatch):
        """FACTORY_DISPATCHED=1 必须进链环境（fix-issue 据此免获取手动互斥
        锁，防自锁——bash 版契约）。"""
        seen = {}

        def fake_popen(cmd, **kw):
            seen["env"] = kw.get("env")

            class _P:
                def poll(self):
                    return 0

                returncode = 0
            return _P()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        pool = ChainPool(tmp_path, max_parallel=2, poll_secs=0.05)
        pool.spawn(1)
        pool.wait_all()
        assert seen["env"]["FACTORY_DISPATCHED"] == "1"


class TestDispatchLock:
    def test_first_acquire_wins_live_holder_refuses(self, tmp_path):
        lock = tmp_path / "locks" / "dispatcher"
        assert acquire_dispatch_lock(lock, os.getpid()) is True
        assert acquire_dispatch_lock(lock, os.getpid()) is False  # 活持有者：拒让
        release_dispatch_lock(lock)
        assert acquire_dispatch_lock(lock, os.getpid()) is True  # 放锁后可再占

    def test_stale_pid_takeover(self, tmp_path):
        """持有者已死 → 接管陈锁（PID 活性检测的意义所在）。"""
        lock = tmp_path / "locks" / "dispatcher"
        p = subprocess.Popen(["sleep", "5"])
        p.terminate()
        p.wait()
        lock.mkdir(parents=True)
        (lock / "pid").write_text(str(p.pid), encoding="ascii")
        assert acquire_dispatch_lock(lock, os.getpid()) is True

    def test_garbage_pid_takeover(self, tmp_path):
        """垃圾 pid 文件 → kill -0 报错语义 → 按死接管（bash 同参）。"""
        lock = tmp_path / "locks" / "dispatcher"
        lock.mkdir(parents=True)
        (lock / "pid").write_text("not-a-pid", encoding="ascii")
        assert acquire_dispatch_lock(lock, os.getpid()) is True

    def test_empty_pid_file_means_busy(self, tmp_path):
        """mkdir 在而 pid 空：无法判定持有者死活，按忙退出（bash 同参：
        `[ -n "$pid" ]` 假 → 不接管）。"""
        lock = tmp_path / "locks" / "dispatcher"
        lock.mkdir(parents=True)
        (lock / "pid").write_text("", encoding="ascii")
        assert acquire_dispatch_lock(lock, os.getpid()) is False

    def test_missing_parent_not_misread_as_locked(self, tmp_path):
        """父目录不存在 → 自建（etf-radar PR#79：ENOENT 误读为锁被持而静默
        退出）。"""
        lock = tmp_path / "a" / "b" / "locks" / "dispatcher"
        assert acquire_dispatch_lock(lock, os.getpid()) is True

    def test_release_is_idempotent(self, tmp_path):
        lock = tmp_path / "locks" / "dispatcher"
        release_dispatch_lock(lock)  # 不存在也放：不抛
        acquire_dispatch_lock(lock, os.getpid())
        release_dispatch_lock(lock)
        release_dispatch_lock(lock)


class TestDispatchParsers:
    def test_sort_by_priority_full_ladder(self):
        issues = [
            {"number": 7, "labels": [{"name": "factory:accepted"}]},
            {"number": 2, "labels": [{"name": "priority:low"}]},
            {"number": 5, "labels": [{"name": "priority:critical"}]},
            {"number": 3, "labels": [{"name": "priority:medium"}, {"name": "x"}]},
            {"number": 4, "labels": [{"name": "priority:high"}]},
        ]
        assert sort_by_priority(issues) == [5, 4, 3, 2, 7]

    def test_sort_by_priority_tie_by_number_and_empty_labels(self):
        issues = [
            {"number": 9, "labels": [{"name": "priority:high"}]},
            {"number": 8, "labels": []},
            {"number": 6, "labels": [{"name": "priority:high"}]},
        ]
        assert sort_by_priority(issues) == [6, 9, 8]

    def test_approved_prs_filters_review_decision(self):
        prs = [
            {"number": 1, "mergeable": "MERGEABLE", "reviewDecision": "APPROVED"},
            {"number": 2, "mergeable": "MERGEABLE", "reviewDecision": "CHANGES_REQUESTED"},
            {"number": 3, "mergeable": "CONFLICTING", "reviewDecision": "APPROVED"},
        ]
        assert approved_prs(prs) == [(1, "MERGEABLE"), (3, "CONFLICTING")]

    def test_extract_slug_shapes(self):
        assert extract_slug(["git@github.com:owner/repo.git"]) == "owner/repo"
        assert extract_slug(["https://github.com/owner/repo"]) == "owner/repo"
        assert extract_slug(["ssh://git@github.com:443/owner/repo.git"]) == "owner/repo"
        assert extract_slug(["git@gitlab.com:a/b.git"]) == ""

    def test_extract_slug_first_github_wins(self):
        # github remote 行序在前（resolve_repo_slug 注入顺序保证），首条胜出
        assert extract_slug(["https://github.com/a/one.git",
                             "https://github.com/b/two.git"]) == "a/one"
        assert extract_slug(["git@gitlab.com:a/b.git",
                             "https://github.com/o/r.git"]) == "o/r"
