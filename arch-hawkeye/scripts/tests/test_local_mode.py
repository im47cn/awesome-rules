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
