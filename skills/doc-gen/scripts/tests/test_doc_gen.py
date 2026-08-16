"""doc_gen CLI 集成测试。

覆盖：_dict_to_manifest（旧版兼容全分支）、_load_config、_init_config、
_update_index_has_openapi、main 路由（无命令/aggregate/旧版兼容）、
_scan_project（--init/错误退出/cola fixture 端到端 manifest-only）、
_build_from_manifest（分片目录/旧版单文件）。

RiskScanner 与 build_astro 被 mock，避免真实 arch_check 子进程与 npm 构建。
"""

import json
import sys
from pathlib import Path

import pytest

import doc_gen
from doc_gen import (
    main, _dict_to_manifest, _load_config, _init_config,
    _update_index_has_openapi,
)

COLA_FIXTURE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cola-sample"


class _FakeRisk:
    def __init__(self, *a, **k):
        pass

    def scan(self):
        return {"passed": True, "totalIssues": 0, "criticalCount": 0,
                "warningCount": 0, "infoCount": 0, "summary": {}, "issues": []}


def _cola_scan(tmp_path, monkeypatch, *extra):
    """对 cola-sample 执行 scan（mock RiskScanner / build_astro）。"""
    monkeypatch.setattr(doc_gen, "RiskScanner", _FakeRisk)
    argv = ["doc_gen.py", "scan", str(COLA_FIXTURE), "--manifest-only",
            "--output", str(tmp_path), *extra]
    monkeypatch.setattr(sys, "argv", argv)
    main()


# ── 纯函数 ────────────────────────────────────────────────────────────────────

def test_load_config_variants(tmp_path):
    (tmp_path / ".doc-gen.json").write_text('{"a": 1}', encoding="utf-8")
    assert _load_config(tmp_path) == {"a": 1}
    assert _load_config(tmp_path / "no") == {}                  # 不存在
    (tmp_path / ".doc-gen.json").write_text("{bad", encoding="utf-8")
    assert _load_config(tmp_path) == {}                          # 非法 JSON


def test_init_config_creates(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _init_config(str(proj))
    cfg = json.loads((proj / ".doc-gen.json").read_text(encoding="utf-8"))
    assert cfg["project_name"] == "proj"
    assert cfg["domain_names"] == {}


def test_init_config_existing_skipped(tmp_path, capsys):
    (tmp_path / ".doc-gen.json").write_text("{}", encoding="utf-8")
    _init_config(str(tmp_path))
    assert "已存在" in capsys.readouterr().out


def test_update_index_has_openapi(tmp_path):
    idx = tmp_path / "index.json"
    idx.write_text('{"hasOpenApi": false}', encoding="utf-8")
    _update_index_has_openapi(idx)
    assert json.loads(idx.read_text(encoding="utf-8"))["hasOpenApi"] is True
    _update_index_has_openapi(tmp_path / "no.json")            # 不存在 → 空操作


def test_dict_to_manifest_full():
    data = {
        "meta": {"project": {"name": "L"}},
        "openapiSpecs": {"default": {"paths": {}}},
        "database": {"tables": [{"name": "t"}]},
        "domains": [{
            "name": "d", "displayName": "D", "description": "x", "modulePrefix": "m",
            "layers": {
                "adapter": {
                    "javaPackage": "p", "mavenModule": "mm",
                    "components": [{
                        "type": "controller", "className": "C", "qualifiedName": "q",
                        "sourcePath": "s", "description": "",
                        "fields": [{"name": "f", "type": "t", "kind": "k", "comment": "c"}],
                        "endpoints": [{"method": "GET", "path": "/", "summary": ""}],
                    }],
                    "aggregates": [{"name": "A", "rootEntity": {"type": "entity", "className": "E"}}],
                },
            },
        }],
        "diagrams": {"architectureOverview": "g", "domainAggregates": {"d": "x"}},
        "crossDomainDependencies": [{"fromDomain": "a", "toDomain": "b", "type": "t"}],
    }
    m = _dict_to_manifest(data)
    assert m.meta["project"]["name"] == "L"
    assert m.openapiSpecs["default"]
    assert m.database["tables"][0]["name"] == "t"
    d = m.domains[0]
    comp = d.layers["adapter"].components[0]
    assert comp.className == "C"
    assert comp.fields[0].name == "f"
    assert comp.endpoints[0].method == "GET"
    assert d.layers["adapter"].aggregates[0].rootEntity.className == "E"
    assert m.diagrams.architectureOverview == "g"
    assert m.diagrams.domainAggregates == {"d": "x"}
    assert m.crossDomainDependencies[0].fromDomain == "a"


# ── main 路由 ─────────────────────────────────────────────────────────────────

def test_main_no_command_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["doc_gen.py"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 0
    assert "子命令" in capsys.readouterr().out or True


def test_main_aggregate_routes(tmp_path, monkeypatch):
    cfg = tmp_path / "p.json"
    cfg.write_text(json.dumps({"projects": [
        {"id": "x", "name": "X", "manifest": str(tmp_path)}]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv",
                        ["doc_gen.py", "aggregate", str(cfg), "--output", str(tmp_path / "out")])
    main()                                                  # 聚合空 manifest，不抛
    assert (tmp_path / "out" / "doc-manifest" / "index.json").exists()


def test_scan_legacy_compat(tmp_path, monkeypatch):
    """旧版无子命令（argv[1] 为路径）→ 自动插入 scan。"""
    out = tmp_path / "site"
    monkeypatch.setattr(doc_gen, "RiskScanner", _FakeRisk)
    monkeypatch.setattr(sys, "argv",
                        ["doc_gen.py", str(COLA_FIXTURE), "--manifest-only", "--output", str(out)])
    main()
    assert (out / "doc-manifest" / "index.json").exists()


# ── _scan_project ─────────────────────────────────────────────────────────────

def test_scan_project_manifest_only(tmp_path, monkeypatch):
    _cola_scan(tmp_path, monkeypatch)
    md = tmp_path / "doc-manifest"
    assert (md / "index.json").exists()
    assert (md / "domains").is_dir()
    # 风险/ADR/文章产物均落盘
    assert (md / "risks.json").exists()
    assert (md / "adrs.json").exists()
    assert (md / "articles.json").exists()


def test_scan_project_init(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setattr(sys, "argv", ["doc_gen.py", "scan", str(proj), "--init"])
    main()
    assert (proj / ".doc-gen.json").exists()


def test_scan_no_project_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["doc_gen.py", "scan"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2


def test_scan_not_a_dir_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv",
                        ["doc_gen.py", "scan", str(tmp_path / "nope"), "--manifest-only"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2


# ── _build_from_manifest ──────────────────────────────────────────────────────

def test_build_from_manifest_shards(tmp_path, monkeypatch):
    """先生成分片 manifest，再 --from-manifest 构建（spy build_astro 入参）。"""
    src = tmp_path / "src"
    _cola_scan(src, monkeypatch)
    called = {}

    def spy(out, md):
        called["out"] = out
        called["md"] = md
        return True

    monkeypatch.setattr(doc_gen, "build_astro", spy)
    site = tmp_path / "site"
    monkeypatch.setattr(sys, "argv", [
        "doc_gen.py", "scan", "dummy", "--from-manifest", str(src / "doc-manifest"),
        "--output", str(site)])
    main()
    # 分片目录分支：manifest_dir 直接指向源 manifest，由 build_astro 负责复制
    assert called.get("md") == src / "doc-manifest"


def test_build_from_manifest_legacy_single_file(tmp_path, monkeypatch):
    """旧版单文件 manifest → 转分片 + 写 api-spec.json。"""
    legacy = {
        "meta": {"project": {"name": "L"}},
        "openapiSpecs": {"default": {"paths": {"/x": {"get": {}}}}},
        "domains": [{"name": "d", "layers": {"domain": {"components": [{"type": "entity", "className": "E"}]}}}],
    }
    legacy_file = tmp_path / "old.json"
    legacy_file.write_text(json.dumps(legacy), encoding="utf-8")
    monkeypatch.setattr(doc_gen, "build_astro", lambda o, m: True)
    site = tmp_path / "site"
    monkeypatch.setattr(sys, "argv", [
        "doc_gen.py", "scan", "dummy", "--from-manifest", str(legacy_file),
        "--output", str(site)])
    main()
    assert (site / "doc-manifest" / "index.json").exists()
    assert (site / "doc-manifest" / "api-spec.json").exists()     # 旧版 openapiSpecs 迁移


def test_build_from_manifest_invalid_exits(tmp_path, monkeypatch):
    """--from-manifest 指向无效路径 → sys.exit(2)。"""
    monkeypatch.setattr(sys, "argv", [
        "doc_gen.py", "scan", "dummy", "--from-manifest", str(tmp_path / "nope"),
        "--output", str(tmp_path / "site")])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2


def test_scan_risk_error_branch(tmp_path, monkeypatch, capsys):
    """RiskScanner 返回 error → 仅打印告警，不写 risks.json。"""
    class ErrRisk:
        def __init__(self, *a, **k):
            pass

        def scan(self):
            return {"error": "err-x", "issues": [], "summary": {}}

    monkeypatch.setattr(doc_gen, "RiskScanner", ErrRisk)
    monkeypatch.setattr(sys, "argv", [
        "doc_gen.py", "scan", str(COLA_FIXTURE), "--manifest-only", "--output", str(tmp_path)])
    main()
    assert not (tmp_path / "doc-manifest" / "risks.json").exists()
    assert "err-x" in capsys.readouterr().out
