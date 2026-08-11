"""RiskScanner 测试。

覆盖：arch_check 路径解析优先级（构造传入/环境变量/配置/默认）、
subprocess 成功（风险富化 + 严重性排序 + 计数）、returncode 异常、
超时、JSON 解析失败、环境变量指向不存在路径。
"""

import json
import subprocess

from generator.risks import RiskScanner


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _priority1(ext, path):
    """设置优先级 1（构造传入），清空 2/3 干扰。"""
    ext._arch_check_path = str(path)
    ext._arch_check_env = ""
    ext._config_path = ""
    return ext


def test_default_location_name():
    """_default_location 兜底返回 arch_check.py 占位/真实路径。"""
    p = RiskScanner("/tmp")._default_location()
    assert p.name == "arch_check.py"


def test_scan_enrich_and_sort(tmp_path, monkeypatch):
    """优先级 1：subprocess 成功 → 富化 + 严重性排序 + 计数。"""
    fake = tmp_path / "arch_check.py"
    fake.write_text("#", encoding="utf-8")
    ext = _priority1(RiskScanner(str(tmp_path)), fake)
    data = {"passed": False, "issues": [
        {"severity": "推荐", "rule_code": "R1", "description": "d1"},
        {"severity": "强制", "rule_code": "R2", "description": "d2"},
        {"severity": "其它", "rule_code": "R3", "description": "d3"},
    ], "summary": {"total": 3}}
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _FakeProc(stdout=json.dumps(data)))
    r = ext.scan()
    assert r["passed"] is False
    assert r["totalIssues"] == 3
    assert r["criticalCount"] == 1          # 强制
    assert r["warningCount"] == 1           # 推荐
    assert r["infoCount"] == 1              # 未知 → info
    assert r["issues"][0]["level"] == "critical"   # 排序后 critical 在前
    assert r["issues"][0]["rule"] == "R2"


def test_scan_returncode_error(tmp_path, monkeypatch):
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    ext = _priority1(RiskScanner(str(tmp_path)), fake)
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _FakeProc(returncode=2, stderr="boom"))
    r = ext.scan()
    assert "error" in r and "执行失败" in r["error"]


def test_scan_timeout(tmp_path, monkeypatch):
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    ext = _priority1(RiskScanner(str(tmp_path)), fake)

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ac", timeout=60)

    monkeypatch.setattr(subprocess, "run", boom)
    r = ext.scan()
    assert r["error"] == "arch_check.py 执行超时"


def test_scan_json_decode_error(tmp_path, monkeypatch):
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    ext = _priority1(RiskScanner(str(tmp_path)), fake)
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _FakeProc(stdout="not json"))
    r = ext.scan()
    assert r["error"] == "arch_check.py 输出解析失败"


def test_scan_env_invalid_path():
    """优先级 2：ARCH_CHECK_PATH 指向不存在 → error。"""
    ext = RiskScanner("/tmp")
    ext._arch_check_path = ""
    ext._arch_check_env = "/no/such/file.py"
    ext._config_path = ""
    r = ext.scan()
    assert "error" in r and "不存在" in r["error"]


def test_scan_config_path(tmp_path, monkeypatch):
    """优先级 3：.doc-gen.json 配置 arch_check_path → 命中并执行。"""
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"arch_check_path": str(fake)}), encoding="utf-8")
    ext = RiskScanner(str(tmp_path))
    ext._arch_check_path = ""
    ext._arch_check_env = ""
    ext._config_path = str(cfg)
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _FakeProc(stdout=json.dumps(
                            {"passed": True, "issues": []})))
    r = ext.scan()
    assert r["passed"] is True and r["totalIssues"] == 0


def test_scan_generic_exception(tmp_path, monkeypatch):
    """subprocess 抛非预期异常 → 兜底 error（str(e)[:500]）。"""
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    ext = _priority1(RiskScanner(str(tmp_path)), fake)

    def boom(*a, **k):
        raise RuntimeError("boom-x")

    monkeypatch.setattr(subprocess, "run", boom)
    r = ext.scan()
    assert "error" in r and "boom-x" in r["error"]


# ── _resolve_arch_check（路径解析，不依赖 subprocess）─────────────────────────


def _bare(ext):
    ext._arch_check_path = ""
    ext._arch_check_env = ""
    ext._config_path = ""
    return ext


def test_resolve_priority1_constructor(tmp_path):
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    ext = _bare(RiskScanner(str(tmp_path)))
    ext._arch_check_path = str(fake)
    assert ext._resolve_arch_check() == fake.resolve()


def test_resolve_env_invalid_returns_none(tmp_path):
    """环境变量显式指定但不存在 → 返回 None（早停，不回退）。"""
    ext = _bare(RiskScanner(str(tmp_path)))
    ext._arch_check_env = "/no/such/file.py"
    assert ext._resolve_arch_check() is None


def test_resolve_priority3_config(tmp_path):
    fake = tmp_path / "ac.py"
    fake.write_text("#", encoding="utf-8")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"arch_check_path": str(fake)}), encoding="utf-8")
    ext = _bare(RiskScanner(str(tmp_path)))
    ext._config_path = str(cfg)
    assert ext._resolve_arch_check() == fake.resolve()


def test_resolve_config_corrupt_json_falls_to_default(tmp_path):
    """配置文件非法 JSON → 跳过优先级 3，回退默认位置。"""
    cfg = tmp_path / "bad.json"
    cfg.write_text("{bad", encoding="utf-8")
    ext = _bare(RiskScanner(str(tmp_path)))
    ext._config_path = str(cfg)
    p = ext._resolve_arch_check()
    assert p is not None and p.name == "arch_check.py"


def test_resolve_default_when_nothing_set():
    ext = _bare(RiskScanner("/tmp"))
    p = ext._resolve_arch_check()
    assert p is None or p.name == "arch_check.py"


def test_not_found_hint_variants(tmp_path):
    ext = _bare(RiskScanner("/tmp"))
    assert "ARCH_CHECK_PATH" in ext._not_found_hint()           # 默认提示
    ext._arch_check_env = "/nope/x.py"
    assert "/nope/x.py" in ext._not_found_hint()                # env 触发
    cfg = tmp_path / "c.json"
    cfg.write_text("{}", encoding="utf-8")
    ext._arch_check_env = ""
    ext._config_path = str(cfg)
    assert ".doc-gen.json" in ext._not_found_hint()             # config 触发
