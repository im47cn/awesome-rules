"""跨项目变更影响分析测试（AH-C03）。

覆盖：图加载（组件/deps 反向边/跨项目边）、实体定位（路由/类名/限定名包含）、
direct（跨项目 provider 命中 + confirmed/inferred 分级）、indirect（BFS 反向
依赖链 + 跳数裁剪 + 环安全）、未命中报错、真实聚合产物端到端。
"""

import json
from pathlib import Path

import pytest

from impact import analyze_impact, load_graph, render_text

# ── 聚合目录构造（aggregate 产物结构）─────────────────────────────────────────


def _write_agg(tmp_path: Path) -> Path:
    dm = tmp_path / "site" / "doc-manifest"

    # projA：provider（DemoController）+ executor 依赖链 executor→feign
    pa = dm / "projects" / "projA"
    pa.mkdir(parents=True)
    (pa / "demo.json").write_text(json.dumps({
        "name": "demo",
        "layers": {
            "adapter": {"components": [{
                "type": "controller", "className": "DemoController",
                "qualifiedName": "com.pa.DemoController",
                "sourcePath": "a/DemoController.java",
                "endpoints": [{"method": "GET", "path": "/demo/v1/orders/{id}"}],
            }]},
            "application": {"components": [{
                "type": "executor", "className": "DemoCmdExe",
                "qualifiedName": "com.pa.DemoCmdExe",
                "deps": ["com.pa.DemoInter"],
            }]},
            "client": {"components": [{
                "type": "feignInterface", "className": "DemoInter",
                "qualifiedName": "com.pa.DemoInter",
                "deps": ["com.pa.DemoController"],
            }]},
        },
    }), encoding="utf-8")

    # projB：consumer（Feign 调 projA 的路由）+ 下游依赖它的 executor
    pb = dm / "projects" / "projB"
    pb.mkdir(parents=True)
    (pb / "demo.json").write_text(json.dumps({
        "name": "demo",
        "layers": {
            "application": {"components": [{
                "type": "executor", "className": "SyncCmdExe",
                "qualifiedName": "com.pb.SyncCmdExe",
                "deps": ["com.pb.BizInter"],
            }]},
            "client": {"components": [{
                "type": "feignInterface", "className": "BizInter",
                "qualifiedName": "com.pb.BizInter",
            }]},
        },
    }), encoding="utf-8")

    # 跨项目边：projB.BizInter → projA.DemoController（confirmed）
    (dm / "cross-project.json").write_text(json.dumps({
        "schema_version": 1,
        "edges": [{
            "from": "projB", "to": "projA", "type": "http",
            "confidence": "confirmed",
            "evidence": {
                "consumer": {"qualifiedName": "com.pb.BizInter",
                             "sourcePath": "b/BizInter.java",
                             "call": "GET /demo/v1/orders/{id}"},
                "provider": {"project": "projA",
                             "qualifiedName": "com.pa.DemoController",
                             "route": "GET /demo/v1/orders/{id}"},
            },
        }],
        "stats": {"confirmed": 1, "inferred": 0, "internalCalls": 0,
                  "unmatchedConsumers": 0},
    }), encoding="utf-8")
    return tmp_path / "site"


# ── 实体定位 ──────────────────────────────────────────────────────────────────


def test_locate_by_route_and_class_and_qn(tmp_path):
    from impact import locate_entity
    g = load_graph(_write_agg(tmp_path))
    qn, how = locate_entity(g, "GET /demo/v1/orders/{identifier}")
    assert qn == "com.pa.DemoController" and "route" in how
    qn, how = locate_entity(g, "DemoCmdExe")
    assert qn == "com.pa.DemoCmdExe" and how.startswith("className")
    qn, how = locate_entity(g, "com.pb.SyncCmdExe")
    assert qn == "com.pb.SyncCmdExe"


def test_locate_not_found(tmp_path):
    g = load_graph(_write_agg(tmp_path))
    result = analyze_impact(g, "Ghost")
    assert result["ok"] is False
    assert "未找到实体" in result["error"]


# ── direct / indirect ─────────────────────────────────────────────────────────


def test_impact_direct_and_indirect(tmp_path):
    """改 projA.DemoController：🔴 跨项目 consumer projB.BizInter；
    🟠 项目内反向链 DemoInter(1 跳) → DemoCmdExe(2 跳)"""
    g = load_graph(_write_agg(tmp_path))
    result = analyze_impact(g, "DemoController", max_hops=3)
    assert result["ok"]
    # direct：跨项目边 provider 命中
    assert len(result["direct"]) == 1
    d = result["direct"][0]
    assert d["project"] == "projB"
    assert d["entity"] == "com.pb.BizInter"
    assert d["confidence"] == "confirmed"
    # indirect：deps 反向 BFS（com.pa.DemoInter 依赖 controller → DemoCmdExe 依赖 feign）
    by_qn = {i["entity"]: i["hops"] for i in result["indirect"]}
    assert by_qn.get("com.pa.DemoInter") == 1
    assert by_qn.get("com.pa.DemoCmdExe") == 2
    assert result["stats"]["directConfirmed"] == 1


def test_impact_max_hops_prunes(tmp_path):
    """max_hops=1 裁掉 2 跳的 DemoCmdExe"""
    g = load_graph(_write_agg(tmp_path))
    result = analyze_impact(g, "DemoController", max_hops=1)
    hops = {i["entity"]: i["hops"] for i in result["indirect"]}
    assert "com.pa.DemoInter" in hops
    assert "com.pa.DemoCmdExe" not in hops


def test_impact_consumer_perspective_no_direct(tmp_path):
    """改 projB.BizInter（consumer 视角）：无跨项目 direct（没人调它），仅项目内下游"""
    g = load_graph(_write_agg(tmp_path))
    result = analyze_impact(g, "BizInter")
    assert result["ok"]
    assert result["direct"] == []          # provider 侧未命中任何边
    assert {i["entity"] for i in result["indirect"]} == {"com.pb.SyncCmdExe"}


def test_impact_cycle_safe(tmp_path):
    """依赖环（A deps B, B deps A）不死循环"""
    site = _write_agg(tmp_path)
    f = site / "doc-manifest" / "projects" / "projB" / "demo.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["layers"]["application"]["components"][0]["deps"].append("com.pb.BizInter")
    data["layers"]["client"]["components"][0]["deps"] = ["com.pb.SyncCmdExe"]
    f.write_text(json.dumps(data), encoding="utf-8")
    g = load_graph(site)
    result = analyze_impact(g, "BizInter", max_hops=5)
    assert result["ok"]
    entities = [i["entity"] for i in result["indirect"]]
    assert len(entities) == len(set(entities))   # 无重复（visited 防环）


def test_render_text(tmp_path):
    g = load_graph(_write_agg(tmp_path))
    text = render_text(analyze_impact(g, "DemoController"))
    assert "🔴" in text and "🟠" in text
    assert "com.pb.BizInter" in text
    assert "✅" in text                            # confirmed 标记
