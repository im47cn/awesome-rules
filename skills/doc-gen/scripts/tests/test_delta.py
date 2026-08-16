"""delta 快照对比引擎测试

覆盖：
- canonical 归一化（key 顺序无关）
- 字段分组 → 状态分级（semantic/lifecycle/behavior/presentation）
- moved 两层启发式（确定迁移 + className 恒等推断 + 多对一保守回退）
- 六维度 diff（components/aggregates/tables/stateMachines/crossDomain/openapi）
- load_snapshot 分片加载 + render_markdown + CLI 门禁（schema_version）

设计依据 docs/design/doc-gen-contract-design.md §8。
"""

import json
from pathlib import Path

import pytest

from delta import (
    COMPONENT_FIELDS,
    _equal,
    diff_components,
    diff_snapshots,
    diff_tables,
    load_snapshot,
    render_markdown,
)


def _comp(qid, cls, **kw):
    d = {"type": "controller", "className": cls, "qualifiedName": qid,
         "description": "", "_domain": "order", "_layer": "adapter"}
    d.update(kw)
    return d


def _flat(overrides=None):
    base = {
        "a.b.OrderController": _comp("a.b.OrderController", "OrderController"),
    }
    if overrides:
        base.update(overrides)
    return base


def _changes_by_id(changes):
    return {c["id"]: c for c in changes}


# ── canonical ─────────────────────────────────────────────────────────────────


class TestCanonical:
    def test_key_order_irrelevant(self):
        assert _equal({"a": 1, "b": [1, 2]}, {"b": [2, 1], "a": 1})

    def test_nested_list_order_irrelevant(self):
        assert _equal({"endpoints": [{"path": "/x"}, {"path": "/y"}]},
                      {"endpoints": [{"path": "/y"}, {"path": "/x"}]})

    def test_value_difference_detected(self):
        assert not _equal({"a": 1}, {"a": 2})


# ── 组件状态分级 ───────────────────────────────────────────────────────────────


class TestComponentStatus:
    def test_added(self):
        changes = diff_components({}, _flat())
        assert changes[0]["status"] == "added"

    def test_removed(self):
        changes = diff_components(_flat(), {})
        assert changes[0]["status"] == "removed"

    def test_semantic_change_is_changed(self):
        base = _flat()
        head = _flat({"a.b.OrderController": base["a.b.OrderController"] | {"type": "consumer"}})
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "changed"
        assert "semantic" in c["classifications"]

    def test_lifecycle_flip_is_changed(self):
        base = _flat()
        head = _flat({"a.b.OrderController": base["a.b.OrderController"] | {"deprecated": True}})
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "changed"
        assert "lifecycle" in c["classifications"]

    def test_description_only_is_presentation_changed(self):
        base = _flat()
        head = _flat({"a.b.OrderController": base["a.b.OrderController"] | {"description": "新 Javadoc"}})
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "presentation-changed"

    def test_methods_change_is_changed_behavior(self):
        base = _flat()
        head = _flat({"a.b.OrderController": base["a.b.OrderController"] | {"methods": ["newApi"]}})
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "changed"
        assert "behavior" in c["classifications"]

    def test_identical_no_change(self):
        base = _flat()
        assert diff_components(base, _flat(dict(base))) == []


# ── moved 两层启发式 ──────────────────────────────────────────────────────────


class TestMoved:
    def test_domain_migration_is_moved(self):
        base = _flat()
        moved = base["a.b.OrderController"] | {"_domain": "order", "_layer": "adapter"}
        head = {"a.b.OrderController": moved | {"_domain": "logistics"}}
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "moved"
        assert c["changedFields"][0] == "order/adapter → logistics/adapter"
        assert "inferred" not in c

    def test_layer_migration_is_moved(self):
        base = _flat()
        head = {"a.b.OrderController":
                base["a.b.OrderController"] | {"_layer": "client"}}
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "moved"

    def test_move_plus_change_merges_classifications(self):
        base = _flat()
        head = {"a.b.OrderController":
                base["a.b.OrderController"] | {"_domain": "logistics", "type": "consumer"}}
        c = _changes_by_id(diff_components(base, head))["a.b.OrderController"]
        assert c["status"] == "moved"
        assert "semantic" in c["classifications"]  # 字段变化不丢失

    def test_rename_inferred_moved(self):
        """包重命名（qualifiedName 变 + className 同）→ moved + inferred"""
        base = _flat()
        head = {"c.d.OrderController": _comp("c.d.OrderController", "OrderController")}
        c = _changes_by_id(diff_components(base, head))["c.d.OrderController"]
        assert c["status"] == "moved"
        assert c["inferred"] is True

    def test_ambiguous_rename_stays_added_removed(self):
        """多对一同名：保守回退，不猜测"""
        base = {
            "a.b.Svc": _comp("a.b.Svc", "Svc"),
            "x.y.Svc": _comp("x.y.Svc", "Svc"),
        }
        head = {"c.d.Svc": _comp("c.d.Svc", "Svc")}
        changes = _changes_by_id(diff_components(base, head))
        assert changes["c.d.Svc"]["status"] == "added"
        assert changes["a.b.Svc"]["status"] == "removed"
        assert changes["x.y.Svc"]["status"] == "removed"


# ── 数据表 / 状态机 ───────────────────────────────────────────────────────────


class TestTables:
    def test_column_diff(self):
        base = {"t_order": {"name": "t_order", "columns": [
            {"name": "id", "type": "bigint"}, {"name": "memo", "type": "varchar"}]}}
        head = {"t_order": {"name": "t_order", "columns": [
            {"name": "id", "type": "bigint"},
            {"name": "memo", "type": "text"},          # 类型变
            {"name": "status", "type": "int"}]}}       # 新列
        c = diff_tables(base, head)[0]
        assert c["status"] == "changed"
        assert c["columnsAdded"] == ["status"]
        assert c["columnsRemoved"] == []
        assert c["columnsChanged"] == ["memo"]

    def test_table_added_removed(self):
        base = {"t_a": {"name": "t_a", "columns": []}}
        head = {"t_b": {"name": "t_b", "columns": []}}
        changes = _changes_by_id(diff_tables(base, head))
        assert changes["t_a"]["status"] == "removed"
        assert changes["t_b"]["status"] == "added"


# ── load_snapshot + 端到端 ────────────────────────────────────────────────────


def _write_manifest(md: Path, schema_version=1, *, revision="a" * 40,
                    components=None, api_paths=None):
    md.mkdir(parents=True, exist_ok=True)
    (md / "domains").mkdir(exist_ok=True)
    (md / "index.json").write_text(json.dumps({
        "schema_version": schema_version, "domains": [], "domainCount": 0,
        "componentCount": 0, "tableCount": 0}), encoding="utf-8")
    (md / "meta.json").write_text(json.dumps({
        "project": {},
        "evidence": {"revision": revision, "generatedAt": "2026", "dirty": False,
                     "repo_url": None}}), encoding="utf-8")
    (md / "database.json").write_text(json.dumps({"tables": []}), encoding="utf-8")
    (md / "state-machines.json").write_text("[]", encoding="utf-8")
    (md / "cross-domain.json").write_text("[]", encoding="utf-8")
    if components is not None:
        dom, layer = "order", "adapter"
        (md / "domains" / "order.json").write_text(json.dumps({
            "name": "order", "layers": {layer: {"components": components}}}),
            encoding="utf-8")
    if api_paths is not None:
        (md / "api-spec.json").write_text(json.dumps({
            "paths": {p: {"get": {"x": 1}} for p in api_paths}}), encoding="utf-8")


class TestLoadSnapshot:
    def test_loads_all_shards(self, tmp_path):
        _write_manifest(tmp_path / "base", components=[
            {"type": "controller", "className": "A", "qualifiedName": "a.A"}])
        snap = load_snapshot(tmp_path / "base")
        assert snap["schema_version"] == 1
        assert "a.A" in snap["components"]
        assert snap["components"]["a.A"]["_domain"] == "order"

    def test_missing_index_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_snapshot(tmp_path)

    def test_no_api_spec_gives_none(self, tmp_path):
        _write_manifest(tmp_path)
        assert load_snapshot(tmp_path)["openapi_endpoints"] is None

    def test_api_endpoints_extracted(self, tmp_path):
        _write_manifest(tmp_path, api_paths=["/x", "/y"])
        assert load_snapshot(tmp_path)["openapi_endpoints"] == {
            ("GET", "/x"), ("GET", "/y")}


class TestDiffSnapshotsEndToEnd:
    def _pair(self, tmp_path):
        _write_manifest(tmp_path / "base", revision="a" * 40, components=[
            {"type": "controller", "className": "A", "qualifiedName": "a.A"},
            {"type": "entity", "className": "E", "qualifiedName": "a.E"}],
            api_paths=["/x"])
        _write_manifest(tmp_path / "head", revision="b" * 40, components=[
            {"type": "controller", "className": "A", "qualifiedName": "a.A",
             "deprecated": True},   # lifecycle 翻转
            {"type": "entity", "className": "E", "qualifiedName": "b.E"}],  # 包重命名
            api_paths=["/x", "/y"])
        return load_snapshot(tmp_path / "base"), load_snapshot(tmp_path / "head")

    def test_summary_and_anchors(self, tmp_path):
        base, head = self._pair(tmp_path)
        receipt = diff_snapshots(base, head)
        assert receipt["base"]["revision"] == "a" * 40
        assert receipt["head"]["revision"] == "b" * 40
        assert receipt["summary"]["components"] == {"added": 0, "removed": 0,
                                                    "changed": 1, "moved": 1}
        assert receipt["summary"]["openapi"] == {"added": 1, "removed": 0}

    def test_presentation_not_in_summary(self, tmp_path):
        _write_manifest(tmp_path / "base", components=[
            {"type": "controller", "className": "A", "qualifiedName": "a.A"}])
        _write_manifest(tmp_path / "head", components=[
            {"type": "controller", "className": "A", "qualifiedName": "a.A",
             "description": "改文档"}])
        receipt = diff_snapshots(load_snapshot(tmp_path / "base"),
                                 load_snapshot(tmp_path / "head"))
        assert receipt["summary"]["components"]["changed"] == 0

    def test_markdown_renders_key_markers(self, tmp_path):
        base, head = self._pair(tmp_path)
        md = render_markdown(diff_snapshots(base, head))
        assert "架构演进 Delta" in md
        assert "`aaaaaaaaaaaa`" in md and "`bbbbbbbbbbbb`" in md
        assert "**moved**" in md and "*(inferred)*" in md
        assert "**changed**" in md
        assert "presentation-changed" in md  # 末尾契约说明


class TestDiffCliGate:
    def test_schema_version_mismatch_exits_two(self, tmp_path, monkeypatch):
        _write_manifest(tmp_path / "a", schema_version=1)
        _write_manifest(tmp_path / "b", schema_version=2)
        import doc_gen
        monkeypatch.setattr(sys := __import__("sys"), "argv", [
            "doc_gen.py", "diff", str(tmp_path / "a"), str(tmp_path / "b")])
        with pytest.raises(SystemExit) as e:
            doc_gen.main()
        assert e.value.code == 2

    def test_success_writes_receipt(self, tmp_path, monkeypatch, capsys):
        import doc_gen
        _write_manifest(tmp_path / "a")
        _write_manifest(tmp_path / "b", revision="b" * 40)
        out = tmp_path / "delta.json"
        monkeypatch.setattr(__import__("sys"), "argv", [
            "doc_gen.py", "diff", str(tmp_path / "a"), str(tmp_path / "b"),
            "--output", str(out), "--markdown", str(tmp_path / "d.md")])
        doc_gen.main()
        receipt = json.loads(out.read_text(encoding="utf-8"))
        assert receipt["schema_version"] == 1
        assert (tmp_path / "d.md").exists()
        assert "无变化" in capsys.readouterr().out
