"""ManifestWriter 测试。

覆盖：write 全分片输出（meta/diagrams/database/state-machines/cross-domain/domains/index）、
_write_domain_file（含 aggregates 各子分支、空层跳过）、_serialize_component（全部可选字段）、
_serialize 递归、_custom_serializer（注册 dataclass/普通 dataclass/不可序列化）。
"""

import json
from dataclasses import dataclass

import pytest

from builder.writer import ManifestWriter, _custom_serializer
from doctypes import (
    AggregateDoc, ComponentDoc, CrossDomainDep, DiagramSet, DocManifest,
    DomainDoc, EndpointDoc, FieldDoc, LayerDoc, StateMachineDoc,
)


def _rich_manifest() -> DocManifest:
    m = DocManifest()
    m.meta = {"project": {"name": "X"}, "schemaVersion": "2.0", "generator": "g"}
    domain = DomainDoc(name="order", displayName="订单", description="d", modulePrefix="m")
    adapter = LayerDoc(javaPackage="p", mavenModule="mm")
    adapter.components.append(ComponentDoc(
        type="controller", className="OrderController", qualifiedName="q",
        sourcePath="s", description="desc", deprecated=True, annotations=["@Rest"],
        methods=["m"],
        fields=[FieldDoc(name="f", type="String", kind="identifier", comment="c", deprecated=True)],
        endpoints=[EndpointDoc(method="GET", path="/o", summary="s",
                               requestBody="Req", responseBody="Resp", deprecated=True)],
        interfaces=["I"],
    ))
    domain.layers["adapter"] = adapter
    domain.layers["domain"] = LayerDoc(aggregates=[AggregateDoc(
        name="Order", kind="aggregate",
        rootEntity=ComponentDoc(type="entity", className="OrderEntity"),
        entities=[ComponentDoc(type="entity", className="OrderItem")],
        valueObjects=[ComponentDoc(type="valueObject", className="Money")],
        domainServices=[ComponentDoc(type="domainService", className="OrderService")],
        domainEvents=[ComponentDoc(type="domainEvent", className="OrderCreated")],
    )])
    m.domains.append(domain)
    m.diagrams = DiagramSet(architectureOverview="graph",
                            domainAggregates={"order": "x"}, stateMachines={"sm": "g"})
    m.database = {"tables": [{"name": "t", "columns": []}]}
    m.crossDomainDependencies.append(
        CrossDomainDep(fromDomain="a", toDomain="b", type="client-api", description="d", evidence="e"))
    m.stateMachines.append(StateMachineDoc(name="SM", states=["A", "B"]))
    m.openapiSpecs = {"default": {}}              # 触发 hasOpenApi
    return m


def test_write_full(tmp_path):
    ManifestWriter(tmp_path).write(_rich_manifest())
    md = tmp_path / "doc-manifest"
    for f in ("meta.json", "diagrams.json", "database.json",
              "state-machines.json", "cross-domain.json", "index.json"):
        assert (md / f).exists()

    idx = json.loads((md / "index.json").read_text(encoding="utf-8"))
    assert idx["domainCount"] == 1
    assert idx["componentCount"] == 1
    assert idx["hasOpenApi"] is True
    assert idx["hasCrossDomain"] is True
    assert idx["schemaVersion"] == "2.0"

    dom = json.loads((md / "domains" / "order.json").read_text(encoding="utf-8"))
    comp = dom["layers"]["adapter"]["components"][0]
    assert comp["className"] == "OrderController"
    assert comp["deprecated"] is True
    assert comp["annotations"] == ["@Rest"]
    assert comp["methods"] == ["m"]
    assert comp["fields"][0]["name"] == "f"
    assert comp["endpoints"][0]["method"] == "GET"
    assert comp["interfaces"] == ["I"]

    agg = dom["layers"]["domain"]["aggregates"][0]
    assert agg["name"] == "Order"
    assert agg["rootEntity"]["className"] == "OrderEntity"
    assert [e["className"] for e in agg["entities"]] == ["OrderItem"]
    assert agg["valueObjects"][0]["className"] == "Money"
    assert agg["domainServices"][0]["className"] == "OrderService"
    assert agg["domainEvents"][0]["className"] == "OrderCreated"

    # state-machines / cross-domain 内容
    sms = json.loads((md / "state-machines.json").read_text(encoding="utf-8"))
    assert sms[0]["name"] == "SM"
    cd = json.loads((md / "cross-domain.json").read_text(encoding="utf-8"))
    assert cd[0]["fromDomain"] == "a"


def test_write_empty_domain_skips_layers(tmp_path):
    """无组件/聚合的层被跳过；域至少保留一层非空（schema minProperties=1，
    完全空域由自检拒绝——空域文件无信息价值，视为生成器 bug）。"""
    m = DocManifest()
    d = DomainDoc(name="sparse")
    d.layers["domain"].aggregates.append(AggregateDoc(
        name="Order", kind="aggregate",
        rootEntity=ComponentDoc(type="entity", className="OrderEntity")))
    m.domains.append(d)  # adapter 层空 → 应被跳过
    ManifestWriter(tmp_path).write(m)
    dom = json.loads((tmp_path / "doc-manifest" / "domains" / "sparse.json").read_text(encoding="utf-8"))
    assert "adapter" not in dom["layers"]
    assert list(dom["layers"]) == ["domain"]


def test_serialize_component_minimal():
    """无任何可选字段的组件 → 仅基础 5 字段。"""
    d = ManifestWriter._serialize_component(
        ComponentDoc(type="x", className="C"))
    assert d["className"] == "C"
    assert "deprecated" not in d
    assert "fields" not in d


def test_serialize_recursive_diagramset():
    out = ManifestWriter._serialize(DiagramSet(architectureOverview="g", erDiagram="er"))
    assert out["architectureOverview"] == "g"
    assert out["erDiagram"] == "er"


def test_custom_serializer_registered_dataclass():
    out = _custom_serializer(ComponentDoc(type="x", className="C"))
    assert out["className"] == "C"


def test_custom_serializer_generic_dataclass():
    @dataclass
    class Other:
        a: int = 1

    assert _custom_serializer(Other()) == {"a": 1}


def test_custom_serializer_unserializable_raises():
    with pytest.raises(TypeError):
        _custom_serializer(object())
