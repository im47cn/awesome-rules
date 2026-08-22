"""evo_patrol 单测：解析真实 plugin list 输出 / 节流 / 告警与恢复 / CLI 接线。

不打真 claude：run_plugin_list 被 monkeypatch 为夹具文本。
"""
import json
from pathlib import Path

import evo
import evo_config as C
import evo_patrol as PT

# 截取自真实 `claude plugin list` 输出（awesome-rules 曾 failed to load）
FIXTURE = """Installed plugins:

  ❯ agent-teams@claude-code-workflows
    Version: 1.0.3
    Scope: user
    Status: ✔ enabled

  ❯ awesome-rules@awesome-rules
    Version: 1.0.0
    Scope: user
    Status: ✘ failed to load
    Error: Hook load failed: Duplicate hooks file detected: ./hooks/hooks.json resolves to already-loaded file /Users/x/awesome-rules/hooks/hooks.json.

  ❯ figma@claude-plugins-official
    Version: 2.2.96
    Scope: project
    Status: ✘ disabled
"""


def make_cfg(tmp_path):
    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    return cfg


def test_parse_failures_extracts_only_failed():
    fs = PT.parse_failures(FIXTURE)
    assert len(fs) == 1
    f = fs[0]
    assert f["id"] == "awesome-rules@awesome-rules"
    assert f["version"] == "1.0.0"
    assert f["scope"] == "user"
    assert f["error"].startswith("Hook load failed: Duplicate hooks file")


def test_parse_failures_empty_and_malformed():
    assert PT.parse_failures("") == []
    assert PT.parse_failures("无关文本\n❯ 孤儿头") == []  # 无 Status 视为无故障


def test_run_plugin_list_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise OSError("no claude")
    monkeypatch.setattr(PT.subprocess, "run", boom)
    assert PT.run_plugin_list("claude") == ""


def test_patrol_new_failure_alerts_and_persists(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: FIXTURE)
    logs = []
    report = PT.patrol(cfg, force=True, log=logs.append)
    assert report is not None and len(report["failures"]) == 1
    assert any("patrol 告警" in x for x in logs)
    data = json.loads((tmp_path / "ar" / "patrol.json").read_text(encoding="utf-8"))
    assert data["failures"][0]["id"] == "awesome-rules@awesome-rules"
    assert data["failures"][0]["first_seen"]


def test_patrol_throttles_within_interval(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    calls = []
    monkeypatch.setattr(PT, "run_plugin_list",
                        lambda *a, **k: calls.append(1) or FIXTURE)
    assert PT.patrol(cfg, force=True) is not None
    assert PT.patrol(cfg) is None          # 窗口内：不执行
    assert PT.patrol(cfg, force=True) is not None  # force 越过
    assert len(calls) == 2


def test_patrol_error_change_and_recovery(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    other = FIXTURE.replace("Duplicate hooks file", "别的错误")
    healthy = "Installed plugins:\n\n  ❯ a@b\n    Version: 1\n    Scope: user\n    Status: ✔ enabled\n"
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: FIXTURE)
    logs: list[str] = []
    PT.patrol(cfg, force=True, log=logs.append)
    # 错误文本变化 → 再次告警（first_seen 秒级精度，同秒内不可比，改断言告警计数）
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: other)
    PT.patrol(cfg, force=True, log=logs.append)
    data = json.loads((tmp_path / "ar" / "patrol.json").read_text(encoding="utf-8"))
    assert "别的错误" in data["failures"][0]["error"]
    assert sum("patrol 告警" in x for x in logs) == 2
    # 恢复 → 恢复日志，台账清空
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: healthy)
    PT.patrol(cfg, force=True, log=logs.append)
    assert any("patrol 恢复" in x for x in logs)
    assert PT.load_alerts(cfg) == []


def test_patrol_no_output_returns_none(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: "")
    logs = []
    assert PT.patrol(cfg, force=True, log=logs.append) is None
    assert any("无输出" in x for x in logs)


def test_patrol_bad_timestamp_treated_as_stale(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    (tmp_path / "ar").mkdir(parents=True)
    (tmp_path / "ar" / "patrol.json").write_text(
        json.dumps({"checked_at": "不是时间戳", "failures": []}), encoding="utf-8")
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: FIXTURE)
    assert PT.patrol(cfg) is not None  # 坏时间戳不阻塞巡检


def test_cli_run_piggybacks_patrol(tmp_path, monkeypatch):
    """run 末尾搭车巡检；--no-patrol 跳过。"""
    cfg = make_cfg(tmp_path)
    cfg["scope_dirs"] = [str(tmp_path)]
    monkeypatch.setattr(evo.C, "load_config", lambda: cfg)
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: FIXTURE)
    called = []
    monkeypatch.setattr(PT, "patrol",
                        lambda c, force=False, log=None: called.append(1) or {})
    rc = evo.main_with_args(["run", "--no-omp"]) if hasattr(
        evo, "main_with_args") else None
    if rc is None:  # 无 main_with_args 则走 argparse
        import sys
        sys.argv = ["evo", "run", "--no-omp"]
        try:
            evo.main()
            rc = 0
        except SystemExit as e:
            rc = e.code
    assert rc == 0 and called


def test_cli_patrol_command(tmp_path, monkeypatch, capsys):
    cfg = make_cfg(tmp_path)
    monkeypatch.setattr(evo.C, "load_config", lambda: cfg)
    monkeypatch.setattr(PT, "run_plugin_list", lambda *a, **k: FIXTURE)
    import sys
    sys.argv = ["evo", "patrol", "--force"]
    try:
        rc = evo.main()
    except SystemExit as e:
        rc = e.code
    out = capsys.readouterr().out
    assert rc == 1  # 有故障 → 非零退出
    assert "awesome-rules@awesome-rules" in out
