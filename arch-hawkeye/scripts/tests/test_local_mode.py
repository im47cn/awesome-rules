"""本地双模式测试（AH-B01）：aggregate local_mode 接纳 dirty 工作区。"""

import json
from pathlib import Path

from aggregate import aggregate_projects


def _dirty_project(tmp_path, pid):
    md = tmp_path / pid / "doc-manifest"
    md.mkdir(parents=True)
    (md / "index.json").write_text(json.dumps(
        {"schema_version": 1, "domainCount": 1, "componentCount": 1, "tableCount": 0,
         "domains": [{"name": "d", "componentCount": 1, "layers": ["domain"],
                      "file": "domains/d.json"}]}), encoding="utf-8")
    (md / "domains").mkdir()
    (md / "domains" / "d.json").write_text(
        '{"name": "d", "layers": {"domain": {"components": []}}}', encoding="utf-8")
    # dirty 工作区快照（§6.3 联邦拒收项）
    (md / "meta.json").write_text(json.dumps(
        {"project": {"name": pid},
         "evidence": {"repo_url": None, "revision": "a" * 40,
                      "generatedAt": "2026-08-17T00:00:00+00:00", "dirty": True}}),
        encoding="utf-8")
    (md / "database.json").write_text('{"tables": [], "relationships": []}', encoding="utf-8")
    (md / "state-machines.json").write_text("[]", encoding="utf-8")
    (md / "cross-domain.json").write_text("[]", encoding="utf-8")
    return md


def test_local_mode_accepts_dirty_workspace(tmp_path):
    """local_mode=True：dirty 工作区是本地分析对象（B01），聚合接纳"""
    md = _dirty_project(tmp_path, "p1")
    pj = tmp_path / "projects.json"
    pj.write_text(json.dumps({"title": "t", "projects": [
        {"id": "p1", "name": "p1", "manifest": str(md)}]}), encoding="utf-8")
    aggregate_projects(str(pj), str(tmp_path / "site"), False, False, local_mode=True)
    assert (tmp_path / "site" / "doc-manifest" / "index.json").exists()
    assert (tmp_path / "site" / "doc-manifest" / "governance.json").exists()


def test_federate_mode_rejects_dirty_workspace(tmp_path, capsys):
    """local_mode=False（默认联邦）：dirty 快照拒收 + 告警（§6.3）"""
    md = _dirty_project(tmp_path, "p2")
    pj = tmp_path / "projects.json"
    pj.write_text(json.dumps({"title": "t", "projects": [
        {"id": "p2", "name": "p2", "manifest": str(md)}]}), encoding="utf-8")
    aggregate_projects(str(pj), str(tmp_path / "site"), False, False)
    out = capsys.readouterr().out
    assert "dirty" in out
    idx = json.loads((tmp_path / "site" / "doc-manifest" / "index.json")
                     .read_text(encoding="utf-8"))
    assert idx["domainCount"] == 0          # 项目被跳过


# ── 失败路径与防混叠（B01 健壮性）───────────────────────────────────────────

import local_mode


def _fake_aggregate(monkeypatch, projects_payload):
    """替身聚合：只写 run_local 空转检测所需的 index.json"""
    def fake(pj, out, build=False, verbose=False, local_mode=False):
        site = Path(out)
        (site / "doc-manifest").mkdir(parents=True, exist_ok=True)
        (site / "doc-manifest" / "index.json").write_text(
            json.dumps({"projects": projects_payload}), encoding="utf-8")
    monkeypatch.setattr("aggregate.aggregate_projects", fake)


def test_run_local_missing_dir(tmp_path):
    """目录不存在 → 立即失败"""
    assert local_mode.run_local([str(tmp_path / "nope")],
                                str(tmp_path / "out")) is False


def test_run_local_scan_failure_aborts(tmp_path, monkeypatch):
    """任一 scan 失败 → 全链路中止"""
    monkeypatch.setattr(local_mode, "_scan", lambda repo, out: False)
    (tmp_path / "repo").mkdir()
    assert local_mode.run_local([str(tmp_path / "repo")],
                                str(tmp_path / "out")) is False


def test_run_local_basename_conflict_disambiguated(tmp_path, monkeypatch, capsys):
    """同 basename 仓库编号去重并告警，不再互相覆盖"""
    monkeypatch.setattr(local_mode, "_scan", lambda repo, out: True)
    _fake_aggregate(monkeypatch, [{"id": "svc"}])
    (tmp_path / "a" / "svc").mkdir(parents=True)
    (tmp_path / "b" / "svc").mkdir(parents=True)
    ok = local_mode.run_local([str(tmp_path / "a" / "svc"),
                               str(tmp_path / "b" / "svc")],
                              str(tmp_path / "out"))
    assert ok is True
    out = capsys.readouterr().out
    assert "svc-2" in out and "冲突" in out
    ids = [p["id"] for p in json.loads(
        (tmp_path / "out" / "local-projects.json").read_text(encoding="utf-8"))["projects"]]
    assert ids == ["svc", "svc-2"]


def test_run_local_zero_aggregated_projects_fails(tmp_path, monkeypatch, capsys):
    """scan 全成功但聚合 0 项目（全部被契约校验拒收）→ 不再输出假成功"""
    monkeypatch.setattr(local_mode, "_scan", lambda repo, out: True)
    _fake_aggregate(monkeypatch, [])
    (tmp_path / "repo").mkdir()
    assert local_mode.run_local([str(tmp_path / "repo")],
                                str(tmp_path / "out")) is False
    assert "聚合 0 个项目" in capsys.readouterr().err
