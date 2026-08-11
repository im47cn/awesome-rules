"""OpenAPIGenerator 测试。

覆盖：generate（controller 端点→paths、路径参数、deprecated、requestBody/responseBody schema）、
_java_to_oas_schema（基本类型/泛型 List/单字母/类引用带字段/枚举/外部类型）、
无 controller → 空 paths。
"""

from generator.openapi import OpenAPIGenerator
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
