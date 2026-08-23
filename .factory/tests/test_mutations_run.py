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
