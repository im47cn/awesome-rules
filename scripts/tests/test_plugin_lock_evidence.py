"""plugin_lock evidence 指纹节单测——向后兼容是核心不变量。

旧锁文件（无 evidence 节）行为必须零变化；新节只增不改：
写入（--update）/ 内容漂移检测 / 悬空与未锁定点名。夹具为临时目录
（conftest 已剥 GIT_* 防真仓劫持），非 git 环境走 rglob/sha256 降级路径。
@date 2026-09-20
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location(
    "plugin_lock", SCRIPTS / "plugin_lock.py")
assert _spec and _spec.loader
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

from release_guard import compute_content_hash  # 单一真相源，不复制算法


@pytest.fixture()
def lockrepo(tmp_path, monkeypatch):
    """临时仓：plugin_lock 的 REPO_ROOT/LOCK_FILE 重定向到 tmp。"""
    monkeypatch.setattr(P, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(P, "LOCK_FILE", tmp_path / "plugin-lock.json")
    d = tmp_path / "skills" / "api-guard"
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text("# s\n", encoding="utf-8")
    (d / "scripts" / "run.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def write_legacy_lock(repo):
    """旧形状锁文件：只有 files 节，无 evidence。"""
    p = repo / "plugin-lock.json"
    p.write_text(json.dumps({"description": "旧锁", "files": {"a": "b"}}),
                 encoding="utf-8")
    return p


class TestBackwardCompat:
    def test_legacy_lock_evidence_check_noop(self, lockrepo):
        """旧锁文件（无 evidence 节）：evidence 校验必须完全跳过。"""
        write_legacy_lock(lockrepo)
        assert P.check_evidence_lock(P.load_lock()) == []

    def test_save_lock_omits_empty_evidence(self, lockrepo):
        """evidence 缺省/空时不写入该节——保持旧锁文件形状。"""
        P.save_lock({"a": "b"}, None)
        data = json.loads(P.LOCK_FILE.read_text(encoding="utf-8"))
        assert "evidence" not in data and data["files"] == {"a": "b"}
        P.save_lock({"a": "b"}, {})
        data = json.loads(P.LOCK_FILE.read_text(encoding="utf-8"))
        assert "evidence" not in data


class TestUpdateWritesEvidence:
    def test_update_includes_fingerprints(self, lockrepo, capsys):
        assert P.update() == 0
        data = json.loads(P.LOCK_FILE.read_text(encoding="utf-8"))
        assert data["evidence"] == {
            "api-guard": compute_content_hash(lockrepo, "api-guard")}
        assert "evidence 指纹" in capsys.readouterr().out


class TestDriftDetection:
    def test_skill_content_drift_named(self, lockrepo):
        P.update()
        (lockrepo / "skills" / "api-guard" / "SKILL.md").write_text("# 改\n")
        errs = P.check_evidence_lock(P.load_lock())
        assert any("漂移" in e and "api-guard" in e for e in errs)

    def test_new_skill_not_locked_named(self, lockrepo):
        P.update()
        d = lockrepo / "skills" / "new-guard"
        (d / "scripts").mkdir(parents=True)
        (d / "SKILL.md").write_text("# n\n", encoding="utf-8")
        (d / "scripts" / "x.py").write_text("1\n", encoding="utf-8")
        errs = P.check_evidence_lock(P.load_lock())
        assert any("未纳入" in e and "new-guard" in e for e in errs)

    def test_dangling_fingerprint_named(self, lockrepo):
        P.update()
        data = json.loads(P.LOCK_FILE.read_text(encoding="utf-8"))
        data["evidence"]["ghost"] = "sha256:" + "0" * 64
        P.LOCK_FILE.write_text(json.dumps(data), encoding="utf-8")
        errs = P.check_evidence_lock(P.load_lock())
        assert any("悬空" in e and "ghost" in e for e in errs)

    def test_unchanged_content_clean(self, lockrepo):
        P.update()
        assert P.check_evidence_lock(P.load_lock()) == []


class TestMalformedOrUnreadable:
    def test_malformed_evidence_section_clean_error(self, lockrepo):
        """手改为非 dict 真值节：干净报错而非 TypeError 崩溃。"""
        P.update()
        data = json.loads(P.LOCK_FILE.read_text(encoding="utf-8"))
        data["evidence"] = ["not", "a", "dict"]
        P.LOCK_FILE.write_text(json.dumps(data), encoding="utf-8")
        errs = P.check_evidence_lock(P.load_lock())
        assert len(errs) == 1 and "evidence 节格式非法" in errs[0]

    def test_non_utf8_content_clean_error(self, lockrepo):
        """技能内容不可读：归入错误清单而非崩溃。"""
        P.update()
        (lockrepo / "skills" / "api-guard" / "scripts"
         / "blob.bin").write_bytes(b"\xff\xfe\x00")
        errs = P.check_evidence_lock(P.load_lock())
        assert any("UTF-8" in e and "api-guard" in e for e in errs)
