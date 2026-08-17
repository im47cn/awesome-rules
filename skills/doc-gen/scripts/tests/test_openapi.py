"""OpenAPIGenerator 测试。

覆盖：generate（controller 端点→paths、路径参数、deprecated、requestBody/responseBody schema）、
_java_to_oas_schema（基本类型/泛型 List/单字母/类引用带字段/枚举/外部类型）、
无 controller → 空 paths、
超阈值 tag 按 URI 前缀细分（一级拆分/递归下钻/下钻到底/变量段归其余/无域 tag/小 tag 保留）。
"""

from generator.openapi import OpenAPIGenerator, MAX_OPS_PER_TAG
from doctypes import (
    ComponentDoc, DocManifest, DomainDoc, EndpointDoc, FieldDoc, LayerDoc,
)


def _manifest_with_controller() -> DocManifest:
    m = DocManifest()
    m.meta = {"project": {"name": "SVC", "description": "desc"}}
    domain = DomainDoc(name="order", displayName="订单", description="d")
    adapter = LayerDoc()
    adapter.components.append(ComponentDoc(
        type="controller", className="OrderController",
        endpoints=[EndpointDoc(method="GET", path="/orders/{id}", summary="获取订单",
                               requestBody="CreateCmd", responseBody="OrderCO", deprecated=True)]))
    domain.layers["adapter"] = adapter
    # CreateCmd 在 client 层、带字段 → schema 填充真实字段
    client = LayerDoc()
    client.components.append(ComponentDoc(
        type="command", className="CreateCmd",
        fields=[FieldDoc(name="qty", type="Integer", comment="数量")]))
    domain.layers["client"] = client
    m.domains.append(domain)
    return m


def test_generate_paths_and_params():
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_controller())
    assert spec["openapi"] == "3.0.3"
    assert "/orders/{id}" in spec["paths"]
    op = spec["paths"]["/orders/{id}"]["get"]
    assert "OrderController" in op["operationId"]
    assert op["deprecated"] is True                      # @Deprecated
    # 路径参数
    assert op["parameters"][0]["name"] == "id"
    # requestBody → CreateCmd 去后缀 → Create schema 含字段
    assert "#/components/schemas/Create" in op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert spec["components"]["schemas"]["Create"]["properties"]["qty"]["type"] == "integer"
    # tag
    assert spec["tags"][0]["name"] == "订单"


def test_generate_no_controller_returns_empty_paths():
    m = DocManifest()
    m.meta = {"project": {"name": "X"}}
    m.domains.append(DomainDoc(name="d"))
    spec = OpenAPIGenerator("/tmp").generate(m)
    assert spec["paths"] == {}


def test_java_to_oas_basic_types():
    g = OpenAPIGenerator("/tmp")
    s, r = {}, set()
    assert g._java_to_oas_schema("String", s, r) == {"type": "string"}
    assert g._java_to_oas_schema("Long", s, r) == {"type": "integer"}


def test_java_to_oas_list_is_plain_array():
    """List 先命中 JAVA_TO_OAS_TYPE(→array)，不解析泛型参数。"""
    g = OpenAPIGenerator("/tmp")
    assert g._java_to_oas_schema("List<Order>", {}, set()) == {"type": "array"}


def test_java_to_oas_generic_set_resolves_items():
    """Set/Collection 不在基本映射 → generic 分支解析内部类型。"""
    g = OpenAPIGenerator("/tmp")
    g.comp_index = {}
    out = g._java_to_oas_schema("Set<Order>", {}, set())
    assert out["type"] == "array"
    assert out["items"] == {"$ref": "#/components/schemas/Order"}


def test_java_to_oas_single_letter_generic():
    g = OpenAPIGenerator("/tmp")
    assert g._java_to_oas_schema("T", {}, set()) == {"type": "object"}


def test_java_to_oas_enum():
    g = OpenAPIGenerator("/tmp")
    g.comp_index = {"Status": ComponentDoc(
        type="enum", className="Status", classType="enum", enumValues=["A", "B"])}
    schemas, refs = {}, set()
    out = g._java_to_oas_schema("Status", schemas, refs)
    assert out == {"$ref": "#/components/schemas/Status"}
    assert schemas["Status"]["enum"] == ["A", "B"]


def test_java_to_oas_external_type():
    g = OpenAPIGenerator("/tmp")
    g.comp_index = {}
    schemas, refs = {}, set()
    out = g._java_to_oas_schema("FooBar", schemas, refs)
    assert out == {"$ref": "#/components/schemas/FooBar"}
    assert "外部依赖类型" in schemas["FooBar"]["description"]


# ── 超阈值 tag 按 URI 前缀细分 ──

def _manifest_with_bulk_endpoints(paths: list, tag: str = "订单") -> DocManifest:
    """单 controller 挂大量端点，模拟域划分粒度过粗的项目"""
    m = DocManifest()
    m.meta = {"project": {"name": "SVC"}}
    domain = DomainDoc(name="order", displayName=tag, description="d")
    adapter = LayerDoc()
    adapter.components.append(ComponentDoc(
        type="controller", className="BulkController",
        endpoints=[EndpointDoc(method="GET", path=p) for p in paths]))
    domain.layers["adapter"] = adapter
    m.domains.append(domain)
    return m


def _op_tags(spec) -> dict:
    """path/method → tag 名"""
    return {
        (p, m): op["tags"][0]
        for p, ops in spec["paths"].items()
        for m, op in ops.items() if isinstance(op, dict)
    }


def test_oversized_tag_split_by_first_prefix():
    """单域超过阈值 → 按一级前缀拆分为 "域 · 前缀"，顶层 tags 重建"""
    paths = [f"/{prefix}/item{i}" for prefix in ("signFlow", "msgLog", "sealMgmt")
             for i in range(MAX_OPS_PER_TAG)]  # 3 组 × 20 = 60 > 20
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_bulk_endpoints(paths))
    tags = _op_tags(spec)
    assert tags[("/signFlow/item0", "get")] == "订单 · signFlow"
    assert tags[("/msgLog/item0", "get")] == "订单 · msgLog"
    assert tags[("/sealMgmt/item0", "get")] == "订单 · sealMgmt"
    top_names = [t["name"] for t in spec["tags"]]
    assert top_names == ["订单 · msgLog", "订单 · sealMgmt", "订单 · signFlow"]
    assert "按 URI 前缀自动细分" in spec["tags"][0]["description"]


def test_oversized_prefix_drills_deeper():
    """一级前缀组仍超阈值且下层段为资源名（高重复）→ 下钻形成层级"""
    paths = [f"/msg/statistics/task-send/on{i}" for i in range(MAX_OPS_PER_TAG + 1)] \
        + [f"/msg/sms/{i}" for i in range(3)]
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_bulk_endpoints(paths))
    tags = _op_tags(spec)
    assert tags[("/msg/statistics/task-send/on0", "get")] == "订单 · msg/statistics/task-send"
    assert tags[("/msg/sms/0", "get")] == "订单 · msg/sms"


def test_instance_id_layer_stops_drilling():
    """下层段为实例 ID（取值全唯一，如 /root/5）→ 无聚合度，停钻保持单组"""
    paths = [f"/root/{i}" for i in range(MAX_OPS_PER_TAG + 5)]
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_bulk_endpoints(paths))
    tags = _op_tags(spec)
    assert set(tags.values()) == {"订单 · root"}


def test_mixed_unique_majority_stops_drilling():
    """少数重复前缀混大量唯一方法名（下钻后大半接口落单）→ 停钻防碎组长名"""
    paths = [f"/batch/common{i}" for i in range(8)] \
        + [f"/batch/uniqueMethod{i}" for i in range(14)]  # 22 个，唯一 14 > 11
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_bulk_endpoints(paths))
    tags = _op_tags(spec)
    assert set(tags.values()) == {"订单 · batch"}


def test_variable_segment_falls_to_rest():
    """首段为路径变量 {var} → 不作为分组键，归入「其余」组"""
    paths = [f"/{{tenantId}}/item{i}" for i in range(MAX_OPS_PER_TAG + 1)]
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_bulk_endpoints(paths))
    tags = _op_tags(spec)
    assert set(tags.values()) == {"订单 · 其余"}


def test_no_tag_grouped_by_pure_prefix():
    """无域信息（tag 缺失）→ 纯前缀分组，不带 "域 ·" 前缀"""
    m = _manifest_with_bulk_endpoints(
        [f"/a/{i}" for i in range(MAX_OPS_PER_TAG)] + [f"/b/{i}" for i in range(5)])
    spec = OpenAPIGenerator("/tmp").generate(m)
    for ops in spec["paths"].values():
        for op in ops.values():
            op["tags"] = []  # 模拟无域信息
    OpenAPIGenerator("/tmp")._regroup_oversized_tags(spec)
    tags = _op_tags(spec)
    assert tags[("/a/0", "get")] == "a"
    assert tags[("/b/0", "get")] == "b"


def test_small_tag_untouched():
    """不超阈值的 tag 原样保留，description 不加细分标注"""
    spec = OpenAPIGenerator("/tmp").generate(_manifest_with_controller())
    assert spec["tags"][0]["name"] == "订单"
    assert spec["tags"][0]["description"] == "d"
    assert spec["paths"]["/orders/{id}"]["get"]["tags"] == ["订单"]
