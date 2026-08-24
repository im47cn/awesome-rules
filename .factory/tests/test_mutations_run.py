"""mutations/run.py 单测 —— 判定（judge）与配置校验（load_defects）的退出码语义。

不跑真实门（guard/tests 均为外部进程）：只锁纯函数契约——
testing-standards「退出码语义」：0=放行、1=击杀证据；其他退出码/超时
一律无效运行，既不奖励击杀也不奖励放行。
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mutations"))

import run as mut  # noqa: E402


def _defect(**kw) -> mut.Defect:
    base = dict(id="X-01", description="d", target="t", find="f", replace="r",
                gate="guard", expect_block=True)
    base.update(kw)
    return mut.Defect(**base)


class TestJudge:
    """退出码 → PASS/FAIL 判定表。"""

    def test_blocked_positive_pass(self):
        assert mut.judge(_defect(gate="guard", expect_block=True), 1)[0] == "PASS"

    def test_released_negative_pass(self):
        assert mut.judge(_defect(gate="guard", expect_block=False), 0)[0] == "PASS"

    def test_survived_mutation_fail(self):
        status, detail = mut.judge(_defect(gate="guard"), 0)
        assert status == "FAIL"
        assert "expect_block" in detail

    def test_blocked_negative_fail(self):
        assert mut.judge(_defect(gate="guard", expect_block=False), 1)[0] == "FAIL"

    def test_guard_fail_closed_rc2_counts_as_block(self):
        """guard rc=2 = fail-closed（门崩溃=拦截，G-03 语义），正例 PASS。"""
        assert mut.judge(_defect(gate="guard", expect_block=True), 2)[0] == "PASS"

    @pytest.mark.parametrize("expect_block", [True, False])
    def test_timeout_is_invalid_run_for_both_polarities(self, expect_block):
        """超时（rc=None）：正例不奖励击杀、负例不奖励放行。"""
        status, detail = mut.judge(_defect(gate="tests", expect_block=expect_block), None)
        assert status == "FAIL"
        assert "无效运行" in detail

    @pytest.mark.parametrize("rc", [2, 127])
    def test_tests_gate_rc_out_of_domain_invalid(self, rc):
        """run_tests.sh 退出码域为 0/1；域外 = 无效运行而非击杀。"""
        status, detail = mut.judge(_defect(gate="tests", expect_block=True), rc)
        assert status == "FAIL"
        assert "无效退出码" in detail


class TestLoadDefects:
    """配置校验：id 唯一、gate 枚举闭合。"""

    @staticmethod
    def _write(tmp_path: Path, defects: list[dict]) -> Path:
        p = tmp_path / "defects.json"
        p.write_text(json.dumps({"defects": defects}, ensure_ascii=False),
                     encoding="utf-8")
        return p

    def test_duplicate_id_rejected(self, tmp_path):
        p = self._write(tmp_path, [asdict(_defect(id="D-1")), asdict(_defect(id="D-1"))])
        with pytest.raises(ValueError, match="重复"):
            mut.load_defects(p)

    def test_unknown_gate_rejected(self, tmp_path):
        p = self._write(tmp_path, [asdict(_defect(gate="lint"))])
        with pytest.raises(ValueError, match="未知 gate"):
            mut.load_defects(p)

    def test_both_gates_accepted(self, tmp_path):
        p = self._write(tmp_path, [asdict(_defect(gate="guard")),
                                   asdict(_defect(id="X-2", gate="tests"))])
        assert len(mut.load_defects(p)) == 2

def _assert_group_dead(pgid: int, *, timeout: float = 10.0) -> None:
    """探活直到进程组消失（macOS 僵尸窗口安全）。

    EPERM = 组内仅剩待-reap 僵尸（macOS XNU 对含僵尸的组发信号报
    EPERM，同 UID 亦然；真活进程不会）——活进程已被杀，等 init 收尸
    后复探。ESRCH = 组彻底消失。探活成功 = 仍有真活成员，轮询至
    deadline 后判失败。
    """
    import os
    import time as _time
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)                   # 探活：组内是否仍有成员
        except ProcessLookupError:
            return                               # 组彻底消失（含 sleep 孙进程）
        except PermissionError:
            pass                                 # 仅剩待-reap 僵尸，复探等收尸
        _time.sleep(0.05)
    pytest.fail(f"进程组 {pgid} 在 {timeout}s 后仍有存活成员")

def _slow_gate(tmp_path):
    """夹具门：自报 pgid、派生 sleep 孙进程后挂起。"""
    pgid_file = tmp_path / "pgid"
    gate = tmp_path / "slow_gate.sh"
    gate.write_text(
        f"#!/bin/bash\necho $$ > {pgid_file}\nsleep 60 &\nwait\n",
        encoding="utf-8")
    gate.chmod(0o755)
    return pgid_file, gate

def test_timeout_kills_process_group(tmp_path, monkeypatch):
    """超时杀整个进程组（PR #33 审查）：只杀 bash 直子会留孤儿继续读
    注入中的 target，还原窗口被污染。夹具门自报 pgid（start_new_session
    下 == 自身 pid）、派生 sleep 孙进程后挂起；断言超时后整组无存活。"""
    import time as _time
    pgid_file, gate = _slow_gate(tmp_path)
    monkeypatch.setattr(mut, "TESTS", gate)
    monkeypatch.setattr(mut, "TESTS_TIMEOUT", 1)
    t0 = _time.monotonic()
    assert mut.run_gate("tests", "whatever") is None
    _assert_group_dead(int(pgid_file.read_text().strip()))


def test_timeout_sigkill_eperm_tolerated(tmp_path, monkeypatch):
    """run_gate 超时杀组遇 killpg(SIGKILL)=EPERM（macOS 组内仅剩待-reap
    僵尸）→ 容忍而非炸掉调用方，仍返回 None（无效运行语义不变），
    且组确已死透。"""
    import errno
    import os
    import signal
    pgid_file, gate = _slow_gate(tmp_path)
    real_killpg = os.killpg

    def killpg_then_eperm(pgid, sig):
        real_killpg(pgid, sig)              # 真杀，避免组残留污染用例
        if sig == signal.SIGKILL:
            raise PermissionError(errno.EPERM, "zombie-only pgroup")

    monkeypatch.setattr(os, "killpg", killpg_then_eperm)
    monkeypatch.setattr(mut, "TESTS", gate)
    monkeypatch.setattr(mut, "TESTS_TIMEOUT", 1)
    assert mut.run_gate("tests", "whatever") is None
    _assert_group_dead(int(pgid_file.read_text().strip()))


def test_probe_tolerates_macos_zombie_window(monkeypatch):
    """杀组断言的确定性规格（flake 回归锁）：探活序列 EPERM→EPERM→ESRCH
    ⟹ 通过——EPERM 即组内仅剩待-reap 僵尸，活进程已被杀。真实僵尸窗口
    依赖 launchd 收尸时序无法稳定复现，故 mock os.killpg 探活路径
    （sig==0），SIGKILL 等真实信号透传。"""
    import errno
    import os
    real_killpg = os.killpg
    probes = iter((PermissionError(errno.EPERM, "zombie"),
                   PermissionError(errno.EPERM, "zombie"),
                   ProcessLookupError(errno.ESRCH, "gone")))

    def fake_killpg(pgid, sig):
        if sig == 0:
            raise next(probes)
        real_killpg(pgid, sig)

    monkeypatch.setattr(os, "killpg", fake_killpg)
    _assert_group_dead(4242)                     # 走完序列 → ESRCH → 通过


def test_probe_fails_when_group_still_alive(monkeypatch):
    """负例：探活持续成功（组内真有活成员，杀组失效）→ deadline 后
    判失败，而非误判通过。"""
    import os
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: None)
    with pytest.raises(pytest.fail.Exception, match="存活"):
        _assert_group_dead(4242, timeout=0.2)
