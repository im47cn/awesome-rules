"""ManifestGenerator 补强测试（覆盖 test_manifest 未触及的分支）。

覆盖：_find_domain（Maven 多模块/深层兜底）、_extract_endpoints（完整端点提取/
无文件/不可读/类级回退）、_method_name_to_summary、_guess_package、
_build_aggregates（Repository 背书）、_infer_er_relationships（同义词/未匹配）、
_generate_diagrams（行为域/值对象/状态机/ER）、_render_state_diagram（raw/spring 去重）、
_compute_layer_edges（跳过未分类）、跨域依赖（Maven/import 类型分类）、to_json。
"""

from pathlib import Path

from generator.manifest import ManifestGenerator
from doctypes import (
    AggregateDoc, ComponentDoc, DomainDoc, DocManifest, FieldDoc, LayerDoc,
    StateMachineDoc, StateTransitionDoc, TableDoc, TableColumnDoc,
)


# ── _find_domain ──────────────────────────────────────────────────────────────

def test_find_domain_maven_module():
    g = ManifestGenerator("/tmp")
    modules = {"order-app": {"path": "order-app"}}
    fi = {"filePath": "order-app/src/X.java", "qualifiedName": "com.x.X", "className": "X"}
    assert g._find_domain(fi, modules) == "order"


def test_find_domain_deep_fallbacks():
    g = ManifestGenerator("/tmp")
    # parts[layer_idx-1] 命中 com/org/cn/net → 回退 parts[2]
    assert g._find_domain(
        {"qualifiedName": "com.org.domain", "className": "X", "filePath": "x"}, {}) == "domain"
    # layer 段=domain 且深层兜底 → shared-kernel
    assert g._find_domain(
        {"qualifiedName": "com.domain", "className": "X", "filePath": "x"}, {}) == "shared-kernel"


# ── _extract_endpoints ────────────────────────────────────────────────────────

CTRL_JAVA = """package com.x;
@RestController
@RequestMapping(value = "/api/orders")
public class OrderController {
    @GetMapping("/{id}")
    public OrderCO get(@PathVariable String id) { return null; }

    @PostMapping
    @ApiOperation(value = "创建订单")
    public String create(@RequestBody OrderCmd cmd) { return ""; }

    @DeleteMapping("/{id}")
    @Deprecated
    public void delete(String id) {}
}
"""


def test_extract_endpoints_full(tmp_path):
    (tmp_path / "OrderController.java").write_text(CTRL_JAVA, encoding="utf-8")
    g = ManifestGenerator(str(tmp_path))
    eps = g._extract_endpoints(
        {"filePath": "OrderController.java", "className": "OrderController",
         "annotations": ["RestController"]})
    by = {e.method: e for e in eps}
    assert {"GET", "POST", "DELETE"} <= by.keys()
    # 类级 @RequestMapping 前缀
    assert by["GET"].path == "/api/orders/{id}"
    # requestBody + @ApiOperation summary
    assert by["POST"].requestBody == "OrderCmd"
    assert by["POST"].summary == "创建订单"
    # 方法级 @Deprecated
    assert by["DELETE"].deprecated is True


def test_extract_endpoints_no_file(tmp_path):
    g = ManifestGenerator(str(tmp_path))
    assert g._extract_endpoints(
        {"filePath": "no.java", "className": "C", "annotations": []}) == []


def test_extract_endpoints_unreadable(tmp_path, monkeypatch):
    f = tmp_path / "C.java"
    f.write_text("class C {}", encoding="utf-8")
    g = ManifestGenerator(str(tmp_path))
    orig = Path.read_text

    def boom(self, *a, **k):
        if self == f:
            raise OSError("x")
        return orig(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    assert g._extract_endpoints({"filePath": "C.java", "className": "C"}) == []


def test_extract_endpoints_class_level_fallback(tmp_path):
    """Controller 无方法级 HTTP 注解 → 类级注解回退（method=*）。"""
    f = tmp_path / "C.java"
    f.write_text("@RestController\nclass C { public void m() {} }", encoding="utf-8")
    g = ManifestGenerator(str(tmp_path))
    eps = g._extract_endpoints(
        {"filePath": "C.java", "className": "C", "annotations": ["RestController"]})
    assert len(eps) == 1
    assert eps[0].method == "*"


# ── 小工具方法 ────────────────────────────────────────────────────────────────

def test_method_name_to_summary_variants():
    f = ManifestGenerator._method_name_to_summary
    assert f("createOrder") == "创建"          # rest 首字母大写 → 仅中文
    assert f("getById") == "查询"
    assert f("listUsers") == "列表查询"
    assert f("randomName") == "randomName"     # 无匹配 → 原名


def test_guess_package_empty():
    g = ManifestGenerator("/tmp")
    assert g._guess_package([], "order", "domain") == "com.example.order.domain"


def test_build_aggregates_repo_backed():
    """有对应 Repository 的实体才成聚合根（repo_backed 命中）。"""
    g = ManifestGenerator("/tmp")
    entity = ComponentDoc(type="entity", className="OrderEntity", fields=[FieldDoc(name="x", type="String")])
    repo = ComponentDoc(type="repositoryInterface", className="OrderRepository")
    aggs = g._build_aggregates([entity, repo])
    assert any(a.name == "Order" and a.repositoryInterface is repo for a in aggs)


# ── _infer_er_relationships ───────────────────────────────────────────────────

def test_infer_er_relationships():
    g = ManifestGenerator("/tmp")
    order = TableDoc(name="t_order", columns=[TableColumnDoc(name="id", type="bigint", primaryKey=True)])
    item = TableDoc(name="t_item", columns=[TableColumnDoc(name="order_id", type="bigint")])
    msg = TableDoc(name="t_msg", columns=[TableColumnDoc(name="tmpl_id", type="bigint")])
    tmpl = TableDoc(name="t_template", columns=[])
    task = TableDoc(name="t_task", columns=[TableColumnDoc(name="send_task_id", type="bigint")])
    send_task = TableDoc(name="t_send_task", columns=[])
    other = TableDoc(name="t_user", columns=[TableColumnDoc(name="ghost_no", type="varchar")])

    rels, unmatched = g._infer_er_relationships([order, item, msg, tmpl, task, send_task, other])
    # 直接前缀匹配
    assert any(r["from"] == "t_item" and r["to"] == "t_order" for r in rels)
    # 同义词组 tmpl↔template
    assert any(r["from"] == "t_msg" and r["to"] == "t_template" for r in rels)
    # 同义词组 send_task↔task
    assert any(r["to"] == "t_send_task" for r in rels)
    # 无匹配外键
    assert any(u["column"] == "ghost_no" for u in unmatched)


# ── 图表生成 ──────────────────────────────────────────────────────────────────

def test_generate_diagrams_behavior_valueobjects_state_er():
    g = ManifestGenerator("/tmp")
    domain = DomainDoc(name="order")
    domain.layers["domain"] = LayerDoc(aggregates=[
        AggregateDoc(name="send", kind="behavior"),                       # 行为域 → skip
        AggregateDoc(
            name="order",
            rootEntity=ComponentDoc(type="entity", className="OrderEntity",
                                    fields=[FieldDoc(name="id", type="Long")]),
            valueObjects=[ComponentDoc(type="valueObject", className="Money")]),
    ])
    manifest = DocManifest()
    manifest.domains.append(domain)
    manifest.stateMachines = [StateMachineDoc(
        name="SM", framework="spring", initialState="A", endStates=["B"],
        transitions=[StateTransitionDoc(source="A", target="B", event="go"),
                     StateTransitionDoc(source="A", target="B", event="go")],  # 重复 → 去重
        states=["A", "B", "C"])]
    manifest.database = {"tables": [{"name": "t_x"}],
                         "relationships": [{"from": "t_y", "to": "t_x", "fk": "x_id"}],
                         "inferred": True}

    ds = g._generate_diagrams(manifest)
    # 聚合类图：root + 值对象（行为域被跳过，order 内容写入）
    assert "order" in ds.domainAggregates
    assert "OrderEntity" in ds.domainAggregates["order"]
    assert "Money" in ds.domainAggregates["order"]            # 值对象关系
    # 状态机图（重复转换去重）
    assert "SM" in ds.stateMachines
    assert ds.stateMachines["SM"].count("A --> B : go") == 1
    # ER 图（表 + 关系边 + 推断注释）
    assert "erDiagram" in ds.erDiagram
    assert "t_x ||--o{ t_y" in ds.erDiagram


def test_render_state_diagram_raw():
    g = ManifestGenerator("/tmp")
    sm = StateMachineDoc(name="S", framework="raw", initialState="A",
                         transitions=[StateTransitionDoc(source="A", target="B", event="x")],
                         states=["A", "B", "C"])
    out = g._render_state_diagram(sm)
    assert out.startswith("flowchart TD")
    assert "A -->|x| B" in out
    assert 'C("C")' in out                       # 孤立状态带框


# ── 层依赖 ────────────────────────────────────────────────────────────────────

def test_compute_layer_edges_skips_unclassified():
    g = ManifestGenerator("/tmp")
    edges = g._compute_layer_edges([
        {"qualifiedName": "com.x.Plain", "className": "Plain", "filePath": "a", "imports": []},
        {"qualifiedName": "com.x.adapter.XController", "className": "XController",
         "filePath": "b", "imports": ["com.x.domain.YEntity"]},
    ])
    assert edges.get(("adapter", "domain")) == 1


# ── 跨域依赖 ──────────────────────────────────────────────────────────────────

def test_find_cross_domain_maven():
    g = ManifestGenerator("/tmp")
    modules = {
        "order-app": {"path": "order-app", "dependencies": []},
        "order-client": {"path": "order-client", "dependencies": []},
        "logistics-app": {"path": "logistics-app",
                          "dependencies": [{"artifactId": "order-client"}]},
    }
    deps = g._find_cross_domain_deps([], modules)
    assert any(d.fromDomain == "logistics" and d.toDomain == "order"
               and d.type == "client-api" for d in deps)


def test_find_cross_domain_imports_types():
    g = ManifestGenerator("/tmp")
    java_files = [
        {"qualifiedName": "com.x.order.domain.entity.OrderEntity", "className": "OrderEntity",
         "filePath": "a", "imports": []},
        {"qualifiedName": "com.x.send.domain.service.SendService", "className": "SendService",
         "filePath": "b", "imports": [
             "com.x.order.client.api.OrderServiceI",
             "com.x.order.domain.event.OrderCreatedEvent",
             "com.x.order.domain.entity.OrderEntity",
         ]},
    ]
    deps = g._find_cross_domain_from_imports(java_files, {})
    types = {d.type for d in deps}
    assert {"client-api", "domain-event", "domain-coupling"} <= types


def test_to_json_roundtrip():
    g = ManifestGenerator("/tmp")
    m = DocManifest()
    m.domains.append(DomainDoc(name="d"))
    s = g.to_json(m)
    assert isinstance(s, str)
    assert '"d"' in s
    assert g.to_json(m, pretty=False).endswith("}") or '"d"' in g.to_json(m, pretty=False)
