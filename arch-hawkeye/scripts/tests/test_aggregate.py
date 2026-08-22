"""架构鹰眼聚合模块测试（自 skills/doc-gen/scripts/tests/ 迁移）。

覆盖：find_project_for_domain、generate_er_diagram、generate_panorama_diagram、
aggregate_projects 端到端（多项目 manifest 合并 / api-spec 合并 / 域文件复制）、
错误分支（配置缺失/非法 JSON/空 projects）、build=True 触发 build_astro。
"""

import json

import pytest

from aggregate import (
    aggregate_projects,
    generate_er_diagram,
    generate_panorama_diagram,
    find_project_for_domain,
)


def _make_project(base, pid, name, domains, tables=None, api_paths=None, cross=None,
                  dirty=False, revision="a" * 40):
    """构造单项目 doc-manifest 目录（符合 AH-MANIFEST 契约，可通过鹰眼 §6 校验）。"""
    dm = base / pid / "doc-manifest"
    dm.mkdir(parents=True)
    (dm / "index.json").write_text(json.dumps({
        "schema_version": 1,
        "domainCount": len(domains),
        "componentCount": sum(c for _d, c in domains),
        "tableCount": len(tables or []),
        "domains": [{"name": d, "componentCount": c, "layers": ["domain"],
                     "file": f"domains/{d}.json"} for d, c in domains],
    }), encoding="utf-8")
    dd = dm / "domains"
    dd.mkdir()
    for d, _c in domains:
        (dd / f"{d}.json").write_text(
            json.dumps({"name": d, "layers": {"domain": {"components": []}}}),
            encoding="utf-8")
    # meta.json — revision-pinned evidence（§6.3：dirty/无 revision 不进联邦索引）
    (dm / "meta.json").write_text(json.dumps({
        "project": {"name": name},
        "evidence": {"repo_url": None, "revision": revision,
                     "generatedAt": "2026-08-16T00:00:00+00:00", "dirty": dirty},
    }), encoding="utf-8")
    # 其余必选分片（缺任一即契约校验失败）
    (dm / "database.json").write_text(
        json.dumps({"tables": tables or [], "relationships": []}), encoding="utf-8")
    (dm / "state-machines.json").write_text(json.dumps([]), encoding="utf-8")
    (dm / "cross-domain.json").write_text(
        json.dumps(cross or []), encoding="utf-8")
    if api_paths is not None:
        (dm / "api-spec.json").write_text(json.dumps({"paths": api_paths}), encoding="utf-8")
    return dm


def _config(tmp_path, projects):
    pj = tmp_path / "projects.json"
    pj.write_text(json.dumps({"title": "全景", "projects": projects}), encoding="utf-8")
    return str(pj)


# ── 纯函数 ────────────────────────────────────────────────────────────────────

def test_find_project_for_domain():
    pdata = [{"id": "order", "name": "订单", "domains": [{"name": "order"}]}]
    assert find_project_for_domain(pdata, "order") == "订单"   # id 命中
    assert find_project_for_domain(pdata, "nope") is None


def test_generate_er_diagram_dedup_and_edge():
    tables = [{"name": "t_order"}, {"name": "t_order"}, {"name": "t_item"}]
    rels = [{"from": "t_item", "to": "t_order", "fk": "order_id", "cardinality": "||--o{"}]
    out = generate_er_diagram(tables, rels)
    assert out.startswith("erDiagram")
    assert out.count("t_order { }") == 1               # 同名去重
    assert "t_order ||--o{ t_item" in out              # 父→子关系边


def test_generate_panorama_diagram_with_cross_project():
    pdata = [
        {"id": "order", "name": "订单", "domainCount": 1, "componentCount": 3,
         "domains": [{"name": "order"}]},
        {"id": "logistics", "name": "物流", "domainCount": 1, "componentCount": 2,
         "domains": [{"name": "logistics"}]},
    ]
    cross = [{"fromDomain": "order", "toDomain": "logistics", "type": "client-api"}]
    diag = generate_panorama_diagram(pdata, cross)
    assert "PANORAMA" in diag["architectureOverview"]
    assert "click order" in diag["architectureOverview"]
    assert "flowchart LR" in diag["layeredDependency"]
    # 跨项目依赖矩阵
    assert diag["crossProjectDependencies"]


# ── aggregate_projects 端到端 ─────────────────────────────────────────────────

def test_aggregate_end_to_end(tmp_path):
    p1 = tmp_path / "p1"
    p2 = tmp_path / "p2"
    _make_project(p1, "order", "订单", [("order", 3)],
                  tables=[{"name": "t_order", "columns": []}],
                  api_paths={"/order": {"get": {}}},
                  cross=[{"fromDomain": "order", "toDomain": "logistics",
                          "type": "client-api"}])
    _make_project(p2, "logistics", "物流", [("logistics", 2)])
    pj = _config(tmp_path, [
        {"id": "order", "name": "订单", "manifest": str(p1 / "order" / "doc-manifest")},
        {"id": "logistics", "name": "物流", "manifest": str(p2 / "logistics" / "doc-manifest")},
    ])
    out = tmp_path / "site"
    aggregate_projects(pj, str(out), build=False, verbose=False)

    agg = out / "doc-manifest"
    idx = json.loads((agg / "index.json").read_text(encoding="utf-8"))
    assert idx["domainCount"] == 2
    assert idx["hasOpenApi"] is True
    assert idx["hasCrossDomain"] is True
    assert idx["project"]["name"] == "全景"
    # 数据库合并
    db = json.loads((agg / "database.json").read_text(encoding="utf-8"))
    assert any(t["name"] == "t_order" for t in db["tables"])
    # 域文件复制（顶级 + 项目级）
    assert (agg / "domains" / "order.json").exists()
    assert (agg / "projects" / "order" / "order.json").exists()
    # api-spec 合并 + diagrams 生成
    assert (agg / "api-spec.json").exists()
    assert (agg / "diagrams.json").exists()


def test_aggregate_missing_manifest_skipped(tmp_path, capsys):
    """manifest 不存在的项目被跳过（不中断）。"""
    _make_project(tmp_path / "p", "order", "订单", [("order", 1)])
    pj = _config(tmp_path, [
        {"id": "order", "name": "订单", "manifest": str(tmp_path / "p" / "order" / "doc-manifest")},
        {"id": "ghost", "name": "幽灵", "manifest": str(tmp_path / "nope" / "doc-manifest")},
    ])
    aggregate_projects(pj, str(tmp_path / "out"), False, False)
    idx = json.loads((tmp_path / "out" / "doc-manifest" / "index.json").read_text(encoding="utf-8"))
    assert idx["domainCount"] == 1                      # 仅 order


def test_aggregate_missing_config_exits(tmp_path):
    with pytest.raises(SystemExit):
        aggregate_projects(str(tmp_path / "no.json"), str(tmp_path / "out"), False, False)


def test_aggregate_invalid_json_exits(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{bad", encoding="utf-8")
    with pytest.raises(SystemExit):
        aggregate_projects(str(f), str(tmp_path / "out"), False, False)


def test_aggregate_empty_projects_exits(tmp_path):
    pj = _config(tmp_path, [])
    with pytest.raises(SystemExit):
        aggregate_projects(pj, str(tmp_path / "out"), False, False)


def test_aggregate_build_invokes_astro(tmp_path, monkeypatch):
    _make_project(tmp_path / "p", "x", "X", [("x", 1)])
    pj = _config(tmp_path, [
        {"id": "x", "name": "X", "manifest": str(tmp_path / "p" / "x" / "doc-manifest")}])
    called = {}

    def fake_build(out, md):
        called["ok"] = True
        return True

    monkeypatch.setattr("aggregate.build_astro", fake_build)
    aggregate_projects(pj, str(tmp_path / "site"), build=True, verbose=False)
    assert called.get("ok")


def test_aggregate_handles_corrupt_json(tmp_path, capsys):
    """契约校验失败（分片 JSON 损坏）→ 项目跳过 + 结构化告警，聚合不中断（§6.1）。"""
    dm = _make_project(tmp_path / "p", "x", "X", [("x", 1)])
    for fn in ("database.json", "cross-domain.json", "state-machines.json"):
        (dm / fn).write_text("{bad", encoding="utf-8")
    pj = _config(tmp_path, [{"id": "x", "name": "X", "manifest": str(dm)}])
    aggregate_projects(pj, str(tmp_path / "out"), False, False)   # 不抛异常
    out = capsys.readouterr().out
    assert "契约校验失败" in out                   # 结构化告警，非静默
    assert "database.json" in out
    agg_idx = json.loads(
        (tmp_path / "out" / "doc-manifest" / "index.json").read_text(encoding="utf-8"))
    assert agg_idx["domainCount"] == 0            # 违规项目未纳管


def test_aggregate_rejects_dirty_snapshot(tmp_path, capsys):
    """evidence.dirty=true 的快照不进入联邦索引（§6.3 revision 卫生）。"""
    _make_project(tmp_path / "p", "order", "订单", [("order", 1)], dirty=True)
    pj = _config(tmp_path, [
        {"id": "order", "name": "订单",
         "manifest": str(tmp_path / "p" / "order" / "doc-manifest")}])
    aggregate_projects(pj, str(tmp_path / "out"), False, False)
    out = capsys.readouterr().out
    assert "evidence.dirty=true" in out
    idx = json.loads(
        (tmp_path / "out" / "doc-manifest" / "index.json").read_text(encoding="utf-8"))
    assert idx["domainCount"] == 0


def test_aggregate_rejects_missing_revision(tmp_path, capsys):
    """revision=null（无 git 降级）的快照不进入联邦索引（§6.3）。"""
    _make_project(tmp_path / "p", "order", "订单", [("order", 1)], revision=None)
    pj = _config(tmp_path, [
        {"id": "order", "name": "订单",
         "manifest": str(tmp_path / "p" / "order" / "doc-manifest")}])
    aggregate_projects(pj, str(tmp_path / "out"), False, False)
    out = capsys.readouterr().out
    assert "revision 缺失" in out
    idx = json.loads(
        (tmp_path / "out" / "doc-manifest" / "index.json").read_text(encoding="utf-8"))
    assert idx["domainCount"] == 0


def test_aggregate_legacy_single_file_manifest(tmp_path, capsys):
    """manifest 目录无 index.json 但 parent 存在旧版单文件 → 提示重新扫描。"""
    dm = tmp_path / "p" / "x" / "doc-manifest"      # manifest 目录
    dm.mkdir(parents=True)
    (dm.parent / "doc-manifest.json").write_text("{}", encoding="utf-8")  # 旧版单文件在 parent
    pj = _config(tmp_path, [{"id": "x", "name": "X", "manifest": str(dm)}])
    aggregate_projects(pj, str(tmp_path / "out"), False, False)
    assert "旧版单文件" in capsys.readouterr().out
