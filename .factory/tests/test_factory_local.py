"""M4 本地化外置的回归测试：guard/factory_lib 从 factory-local.json 载入
周界与判据措辞；fail-closed 语义（配置缺失/损坏 → 非零）；stamp 指纹
绑定（perimeter_blob / stamp_stale_banner / 全绿写入——纯函数部分）。

周界数据化后「改配置 = 改门」：evidence-stamp.json 记录 factory-local.json
的 git blob hash，run.py 启动比对宣告过期（设计 §11.3）。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mutations"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as mut  # noqa: E402
import guard  # noqa: E402
import factory_lib  # noqa: E402


class TestGuardLoadsPerimeterFromConfig:
    """guard.py 零本地化：PERIMETER 来自 factory-local.json（M4）。"""

    def test_perimeter_loaded_and_nonempty(self):
        assert len(guard.PERIMETER) > 10
        assert ".factory/" in guard.PERIMETER
        assert "steering/" in guard.PERIMETER

    def test_perimeter_consistent_with_config_file(self):
        cfg = json.loads(
            (Path(guard.__file__).parent / "factory-local.json").read_text(encoding="utf-8"))
        assert tuple(cfg["perimeter"]) == guard.PERIMETER

    def test_mission_self_check_passes(self):
        guard.self_check()  # 不抛 = PERIMETER 与 MISSION.md 一致且路径存在

    def test_fail_closed_on_missing_config(self, tmp_path):
        """配置缺失/损坏 → RuntimeError（guard main 捕获 → exit 2）。"""
        src = Path(guard.__file__).read_text(encoding="utf-8")
        fake = tmp_path / "guard.py"
        # 重写载入路径指向不存在的配置
        fake.write_text(src.replace(
            '"factory-local.json"', '"no-such-config.json"'), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(fake), "--files", "README.md"],
            capture_output=True, text=True, cwd=str(tmp_path))
        assert proc.returncode == 2  # fail-closed：门坏等同拦截


class TestRejectGuidanceFromConfig:
    """factory_lib.REJECT_GUIDANCE 来自 factory-local.json（M4）。"""

    def test_guidance_keys_loaded(self):
        assert set(factory_lib.REJECT_GUIDANCE) == {"a", "b", "c"}
        assert all(len(v) > 20 for v in factory_lib.REJECT_GUIDANCE.values())

    def test_receipt_uses_config_guidance(self):
        md = factory_lib.reject_receipt({"verdict": "reject",
                                         "reasons": ["判据a: 不通过"]})
        assert factory_lib.REJECT_GUIDANCE["a"] in md


class TestEvidenceSuitesDualLayout:
    """evidence_suites 双布局（skills + monorepo），零本地化（M4）。"""

    def test_skills_layout(self):
        assert factory_lib.evidence_suites(["skills/api-guard/scripts/a.py"]) == [
            "skills/api-guard/scripts"]

    def test_monorepo_layout(self):
        assert factory_lib.evidence_suites(["backend/src/x.py", "frontend/y.tsx"]) == [
            "backend", "frontend"]

    def test_non_project_files_no_suite(self):
        assert factory_lib.evidence_suites(["README.md", "docs/x.md"]) == []


class TestPerimeterStamp:
    """run.py 指纹绑定：perimeter_blob 与 stamp 横幅（纯函数契约）。"""

    def test_perimeter_blob_shape(self):
        blob = mut.perimeter_blob()
        if blob is not None:  # git 仓内 = 40 hex
            assert len(blob) == 40 and all(c in "0123456789abcdef" for c in blob)

    def test_stale_banner_silent_without_stamp(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(mut, "STAMP", tmp_path / "no-stamp.json")
        mut.stamp_stale_banner()  # 无 stamp：静默
        assert capsys.readouterr().out == ""

    def test_stale_banner_announces_drift(self, tmp_path, capsys, monkeypatch):
        stamp = tmp_path / "evidence-stamp.json"
        stamp.write_text(json.dumps({"perimeter_blob": "0" * 40}), encoding="utf-8")
        monkeypatch.setattr(mut, "STAMP", stamp)
        cur = mut.perimeter_blob()
        if cur is None:
            pytest.skip("无 git 环境")
        if cur != "0" * 40:
            mut.stamp_stale_banner()
            assert "周界指纹漂移" in capsys.readouterr().out

    def test_stale_banner_quiet_when_matching(self, tmp_path, capsys, monkeypatch):
        cur = mut.perimeter_blob()
        if cur is None:
            pytest.skip("无 git 环境")
        stamp = tmp_path / "evidence-stamp.json"
        stamp.write_text(json.dumps({"perimeter_blob": cur}), encoding="utf-8")
        monkeypatch.setattr(mut, "STAMP", stamp)
        mut.stamp_stale_banner()
        assert capsys.readouterr().out == ""
