"""跨项目真实链路构建器测试（AH-C01/C04）。

覆盖：路径归一化、provider 索引、confirmed 边（签名对齐 + 双侧证据）、
项目内调用排除、inferred 边（@FeignClient name 近似项目 id）、
无匹配计数、跨域依赖聚合端到端（真实 doc-gen fixture → 鹰眼）。
"""

import json
from pathlib import Path

from crossproject import (
    build_cross_project_edges,
    build_provider_index,
    normalize_path,
)

# ── 路径归一化 ────────────────────────────────────────────────────────────────


def test_normalize_path():
    assert normalize_path("/a/{id}") == normalize_path("/a/{userId}") == "/a/{}"
    assert normalize_path("a//b/") == "/a/b"
    assert normalize_path("") == "/"
    assert normalize_path("/{x}/y/{z}") == "/{}/y/{}"


# ── 测试数据构造 ──────────────────────────────────────────────────────────────


def _domain(provider_path=None, provider_route=("GET", "/demo/v1/orders/{id}"),
            feign_name=None, consumer_path=None):
    """构造单域 manifest：adapter(controller) + client(feignInterface)"""
    layers = {}
    if provider_path is not None:
        layers["adapter"] = {"components": [{
            "type": "controller", "className": "DemoController",
            "qualifiedName": f"com.x.{provider_path}.DemoController",
            "sourcePath": f"src/{provider_path}/DemoController.java",
            "endpoints": [{"method": provider_route[0], "path": provider_route[1]}],
        }]}
    if consumer_path is not None:
        annotations = []
        if feign_name:
            annotations = [f'@FeignClient(url="${{x.url}}", name="{feign_name}", '
                           f'contextId="i", path="/prefix")']
        layers["client"] = {"components": [{
            "type": "feignInterface", "className": "DemoInter",
            "qualifiedName": "com.x.DemoInter",
            "sourcePath": "src/DemoInter.java",
            "annotations": annotations,
            "endpoints": [{"method": "GET", "path": consumer_path}],
        }]}
    return {"name": "demo", "layers": layers}


def _project(tmp_path, pid, domains):
    mdir = tmp_path / pid / "doc-manifest"
    (mdir / "domains").mkdir(parents=True)
    for d in domains:
        (mdir / "domains" / f"{d['name']}.json").write_text(
            json.dumps(d), encoding="utf-8")
    # manifest 需符合 AH-MANIFEST 契约（鹰眼 §6 校验后纳管）
    (mdir / "index.json").write_text(json.dumps({
        "schema_version": 1,
        "domainCount": len(domains),
        "componentCount": 0,
        "tableCount": 0,
        "domains": [{"name": d["name"], "componentCount": 0,
                     "layers": list(d["layers"]),
                     "file": f"domains/{d['name']}.json"} for d in domains],
    }), encoding="utf-8")
    (mdir / "meta.json").write_text(json.dumps({
        "project": {"name": pid},
        "evidence": {"repo_url": None, "revision": "b" * 40,
                     "generatedAt": "2026-08-16T00:00:00+00:00", "dirty": False},
    }), encoding="utf-8")
    (mdir / "database.json").write_text(
        json.dumps({"tables": [], "relationships": []}), encoding="utf-8")
    (mdir / "state-machines.json").write_text(json.dumps([]), encoding="utf-8")
    (mdir / "cross-domain.json").write_text(json.dumps([]), encoding="utf-8")
    return (pid, mdir)


# ── provider 索引 ─────────────────────────────────────────────────────────────


def test_provider_index(tmp_path):
    projects = [_project(tmp_path, "a", [_domain(provider_path="a")])]
    idx = build_provider_index(projects)
    assert ("GET", "/demo/v1/orders/{}") in idx
    prov = idx[("GET", "/demo/v1/orders/{}")][0]
    assert prov["project"] == "a"
    assert prov["route"] == "GET /demo/v1/orders/{id}"


# ── confirmed 边 ──────────────────────────────────────────────────────────────


def test_confirmed_edge_with_evidence(tmp_path):
    """B 项目 Feign 调用签名与 A 项目 Controller 路由对齐 → confirmed 边 + 双侧证据"""
    projects = [
        _project(tmp_path, "a", [_domain(provider_path="a")]),
        _project(tmp_path, "b", [_domain(consumer_path="/demo/v1/orders/{orderId}",
                                         feign_name="a-service")]),
    ]
    result = build_cross_project_edges(projects)
    confirmed = [e for e in result["edges"] if e["confidence"] == "confirmed"]
    assert len(confirmed) == 1
    edge = confirmed[0]
    assert edge["from"] == "b" and edge["to"] == "a"
    # 双侧证据（AH-C01 验收）
    assert edge["evidence"]["consumer"]["qualifiedName"] == "com.x.DemoInter"
    assert "GET" in edge["evidence"]["consumer"]["call"]
    assert edge["evidence"]["provider"]["qualifiedName"].endswith("DemoController")
    assert edge["evidence"]["provider"]["route"] == "GET /demo/v1/orders/{id}"


def test_internal_call_not_cross_project(tmp_path):
    """项目内 Feign 调用（from == to）不算跨项目边，计入 internalCalls"""
    projects = [_project(tmp_path, "a", [
        _domain(provider_path="a", consumer_path="/demo/v1/orders/{id}",
                feign_name="a-service"),
    ])]
    result = build_cross_project_edges(projects)
    confirmed = [e for e in result["edges"] if e["confidence"] == "confirmed"]
    assert confirmed == []
    assert result["stats"]["internalCalls"] == 1


def test_method_mismatch_no_edge(tmp_path):
    """路径一致但 method 不同 → 不构成 confirmed"""
    projects = [
        _project(tmp_path, "a", [_domain(provider_path="a",
                                         provider_route=("POST", "/demo/v1/orders"))]),
        _project(tmp_path, "b", [_domain(consumer_path="/demo/v1/orders",
                                         feign_name="zz-unknown")]),
    ]
    result = build_cross_project_edges(projects)
    assert [e for e in result["edges"] if e["confidence"] == "confirmed"] == []
    assert result["stats"]["unmatchedConsumers"] == 1


# ── inferred 边（AH-C04）──────────────────────────────────────────────────────


def test_inferred_edge_by_feign_name(tmp_path):
    """路由未命中但 @FeignClient name 近似项目 id → inferred 低置信度边"""
    projects = [
        _project(tmp_path, "a", [_domain(provider_path="a",
                                         provider_route=("GET", "/other/path"))]),
        _project(tmp_path, "b", [_domain(consumer_path="/absent/route",
                                         feign_name="a-service")]),
    ]
    result = build_cross_project_edges(projects)
    inferred = [e for e in result["edges"] if e["confidence"] == "inferred"]
    assert len(inferred) == 1
    assert inferred[0]["from"] == "b" and inferred[0]["to"] == "a"
    assert inferred[0]["evidence"]["provider"]["route"] is None
    assert inferred[0]["evidence"]["provider"]["service"] == "a-service"


def test_no_match_no_infer(tmp_path):
    """Feign name 无法近似任何项目 → unmatched 计数，无边"""
    projects = [
        _project(tmp_path, "a", [_domain(provider_path="a")]),
        _project(tmp_path, "b", [_domain(consumer_path="/absent/route",
                                         feign_name="ghost-service")]),
    ]
    result = build_cross_project_edges(projects)
    assert result["edges"] == []
    assert result["stats"]["unmatchedConsumers"] == 1


# ── 聚合端到端 ────────────────────────────────────────────────────────────────


def test_aggregate_writes_cross_project_shard(tmp_path, monkeypatch):
    """aggregate_projects 端到端产出 cross-project.json 分片"""
    import aggregate as agg_mod
    from aggregate import aggregate_projects

    # 双项目：a 提供 provider，b 的 Feign 与真实 fixture 路径对齐
    projects = [
        _project(tmp_path, "pa", [_domain(provider_path="pa")]),
        _project(tmp_path, "pb", [_domain(consumer_path="/demo/v1/orders/{id}",
                                          feign_name="pa-svc")]),
    ]
    pj = tmp_path / "projects.json"
    pj.write_text(json.dumps({"title": "t", "projects": [
        {"id": pid, "name": pid, "manifest": str(mdir)} for pid, mdir in projects
    ]}), encoding="utf-8")
    # 不触发真实 astro 构建
    monkeypatch.setattr(agg_mod, "build_astro", lambda out, md: True)

    aggregate_projects(str(pj), str(tmp_path / "site"), build=False, verbose=False)
    cp = json.loads((tmp_path / "site" / "doc-manifest" / "cross-project.json")
                    .read_text(encoding="utf-8"))
    assert cp["stats"]["confirmed"] == 1
    diagrams = json.loads((tmp_path / "site" / "doc-manifest" / "diagrams.json")
                          .read_text(encoding="utf-8"))
    assert len(diagrams["crossProjectEdges"]) == 1


# ── MQ 边（domain-event 签名对齐）─────────────────────────────────────────────


def _mq_domain(mq_channels):
    """构造含 mqChannels 的组件域（application=producer, adapter=consumer）"""
    return {"name": "demo", "layers": {
        "application": {"components": [{
            "type": "executor", "className": "PubExe",
            "qualifiedName": "com.p.PubExe",
            "sourcePath": "p/PubExe.java",
            "mqChannels": mq_channels,
        }]},
    }}


def test_mq_confirmed_edge(tmp_path):
    """跨项目同 topic 的 producer×consumer → confirmed MQ 边（依赖方向：订阅者→发布者）"""
    projects = [
        _project(tmp_path, "pub", [_mq_domain([
            {"role": "producer", "channel": "order-created",
             "framework": "rocketmq", "via": "syncSend"}])]),
        _project(tmp_path, "sub", [_mq_domain([
            {"role": "consumer", "channel": "order-created",
             "framework": "rocketmq", "via": "RocketMQMessageListener"}])]),
    ]
    result = build_cross_project_edges(projects)
    mq = [e for e in result["edges"] if e["type"] == "mq"]
    assert len(mq) == 1
    edge = mq[0]
    assert edge["from"] == "sub" and edge["to"] == "pub"
    assert edge["confidence"] == "confirmed"
    assert edge["evidence"]["provider"]["route"].startswith("publish order-created")
    assert "subscribe" in edge["evidence"]["consumer"]["call"]
    assert result["stats"]["mqEdges"] == 1
    assert result["stats"]["httpEdges"] == 0


def test_mq_channel_mismatch_no_edge(tmp_path):
    """topic 名不一致 → 无 MQ 边（channel 全局精确匹配，不做模糊）"""
    projects = [
        _project(tmp_path, "a", [_mq_domain([
            {"role": "producer", "channel": "topic-a",
             "framework": "rocketmq", "via": "syncSend"}])]),
        _project(tmp_path, "b", [_mq_domain([
            {"role": "consumer", "channel": "topic-b",
             "framework": "rocketmq", "via": "RocketMQMessageListener"}])]),
    ]
    result = build_cross_project_edges(projects)
    assert [e for e in result["edges"] if e["type"] == "mq"] == []


def test_mq_internal_excluded(tmp_path):
    """同项目内 producer→consumer 不算跨项目边，计入 internalCalls"""
    projects = [_project(tmp_path, "solo", [_mq_domain([
        {"role": "producer", "channel": "t", "framework": "rocketmq", "via": "syncSend"},
        {"role": "consumer", "channel": "t",
         "framework": "rocketmq", "via": "RocketMQMessageListener"},
    ])])]
    result = build_cross_project_edges(projects)
    assert [e for e in result["edges"] if e["type"] == "mq"] == []
    assert result["stats"]["internalCalls"] == 1


# ── DB 边（共享表耦合）────────────────────────────────────────────────────────


def _db_project(tmp_path, pid, tables, source="DDL (.sql)"):
    mdir = tmp_path / pid / "doc-manifest"
    (mdir / "domains").mkdir(parents=True)
    (mdir / "domains" / "demo.json").write_text('{"name": "demo", "layers": {}}',
                                                encoding="utf-8")
    (mdir / "index.json").write_text('{"domains": [{"name": "demo", "componentCount": 0, "layers": [], "file": "domains/demo.json"}]}', encoding="utf-8")
    (mdir / "database.json").write_text(json.dumps(
        {"tables": [{"name": t, "columns": []} for t in tables],
         "relationships": [], "source": source}), encoding="utf-8")
    return (pid, mdir)


def test_db_shared_table_edge(tmp_path):
    """同名表跨项目 → db 边（字典序稳定，证据含双方来源）"""
    projects = [
        _db_project(tmp_path, "pb", ["t_order", "t_only_b"]),
        _db_project(tmp_path, "pa", ["t_order", "t_only_a"], source="MyBatis-Plus @TableName"),
    ]
    result = build_cross_project_edges(projects)
    db = [e for e in result["edges"] if e["type"] == "db"]
    assert len(db) == 1
    assert db[0]["from"] == "pa" and db[0]["to"] == "pb"   # 字典序
    assert db[0]["evidence"]["table"] == "t_order"
    assert db[0]["evidence"]["via"]["pa"] == "MyBatis-Plus @TableName"
    assert result["stats"]["dbEdges"] == 1
    assert result["stats"]["sharedTables"] == 1


def test_db_no_overlap_no_edge(tmp_path):
    projects = [
        _db_project(tmp_path, "a", ["t_a"]),
        _db_project(tmp_path, "b", ["t_b"]),
    ]
    result = build_cross_project_edges(projects)
    assert [e for e in result["edges"] if e["type"] == "db"] == []


# ── 缓存边 / 定时资产 ─────────────────────────────────────────────────────────


def _rt_project(tmp_path, pid, cache_keys, schedules=None):
    mdir = tmp_path / pid / "doc-manifest"
    (mdir / "domains").mkdir(parents=True)
    comp = {"type": "executor", "className": "Exe", "qualifiedName": f"com.{pid}.Exe"}
    if cache_keys:
        comp["cacheKeys"] = [{"key": k, "via": "redisTemplate"} for k in cache_keys]
    if schedules:
        comp["schedules"] = [{"handler": h, "cron": "", "via": "XxlJob"}
                             for h in schedules]
    (mdir / "domains" / "demo.json").write_text(json.dumps(
        {"name": "demo", "layers": {"application": {"components": [comp]}}}),
        encoding="utf-8")
    (mdir / "index.json").write_text('{"domains": [{"name": "demo", "componentCount": 1, "layers": ["application"], "file": "domains/demo.json"}]}', encoding="utf-8")
    return (pid, mdir)


def test_cache_equal_key_confirmed_edge(tmp_path):
    """同 key 字面量 → confirmed cache 边（字典序无向单边）"""
    projects = [
        _rt_project(tmp_path, "pa", ["order:detail:v2"]),
        _rt_project(tmp_path, "pb", ["order:detail:v2"]),
    ]
    result = build_cross_project_edges(projects)
    cache = [e for e in result["edges"] if e["type"] == "cache"]
    assert len(cache) == 1
    assert cache[0]["confidence"] == "confirmed"
    assert cache[0]["from"] == "pa" and cache[0]["to"] == "pb"
    assert result["stats"]["cacheEdges"] == 1


def test_cache_prefix_space_inferred_edge(tmp_path):
    """前缀空间共享（运行时拼接 key 的模式证据）→ inferred cache 边"""
    projects = [
        _rt_project(tmp_path, "pa", ["order:detail:"]),
        _rt_project(tmp_path, "pb", ["order:detail:v2"]),
    ]
    result = build_cross_project_edges(projects)
    cache = [e for e in result["edges"] if e["type"] == "cache"]
    assert len(cache) == 1
    assert cache[0]["confidence"] == "inferred"
    assert result["stats"]["cacheInferred"] == 1


def test_cache_no_overlap_no_edge(tmp_path):
    projects = [
        _rt_project(tmp_path, "pa", ["order:"]),
        _rt_project(tmp_path, "pb", ["user:"]),
    ]
    result = build_cross_project_edges(projects)
    assert [e for e in result["edges"] if e["type"] == "cache"] == []


def test_job_assets_counted_no_edge(tmp_path):
    """定时任务只统计资产（无跨项目边，调度中心依赖代码不可见不造假边）"""
    projects = [
        _rt_project(tmp_path, "pa", [], schedules=["syncJob", "cleanJob"]),
        _rt_project(tmp_path, "pb", ["k"]),
    ]
    result = build_cross_project_edges(projects)
    assert result["stats"]["jobAssets"] == {"pa": 2}
    assert not any(e["type"] == "job" for e in result["edges"])


def test_unmatched_grouped_by_structured_feign_name(tmp_path):
    """结构化 feignClient.name 驱动 unmatchedByService 分组（8 仓库实测修复：
    annotations 只存注解名，947 unmatched 曾全落"无 name"桶）"""
    projects = [
        _project(tmp_path, "pa", [_domain(provider_path="pa")]),
        _project(tmp_path, "pb", [_domain(consumer_path="/absent/1")]),
        _project(tmp_path, "pc", [_domain(consumer_path="/absent/2")]),
    ]
    # 给 pb/pc 的 Feign 组件加结构化元数据（doc-gen Phase2 产出形态）
    for pid in ("pb", "pc"):
        f = tmp_path / pid / "doc-manifest" / "domains" / "demo.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        comp = d["layers"]["client"]["components"][0]
        comp["feignClient"] = {"name": "gtsp-admin-mdm", "path": "",
                               "contextId": "", "url": ""}
        f.write_text(json.dumps(d), encoding="utf-8")
    result = build_cross_project_edges(projects)
    assert result["stats"]["unmatchedConsumers"] == 2
    assert result["stats"]["unmatchedByService"] == {"gtsp-admin-mdm": 2}
