"""LayerIdentifier 测试。

覆盖：classify 各分支（包路径层段 > 类名后缀 > 路径关键字 > 注解）、
后缀优先级、无匹配返回 None、identify_domain_from_module 层后缀剥离。
"""

from generator.layers import LayerIdentifier


def _fi(class_name, qualified_name, file_path="x/X.java", annotations=None):
    return {"filePath": file_path, "className": class_name,
            "qualifiedName": qualified_name, "annotations": annotations or []}


def test_classify_by_package_layer_segment():
    """包路径层段最权威，comp_type 按后缀细化但不覆盖 layer。"""
    ident = LayerIdentifier()
    assert ident.classify(_fi("XController", "com.x.adapter.web.XController")) == ("adapter", "controller")
    assert ident.classify(_fi("App", "com.x.start.App"))[0] == "start"
    assert ident.classify(_fi("X", "com.x.infrastructure.repo.X"))[0] == "infrastructure"


def test_classify_by_suffix_when_no_layer_pkg():
    ident = LayerIdentifier()
    assert ident.classify(_fi("FooRepositoryImpl", "com.x.FooRepositoryImpl")) == ("infrastructure", "repositoryImpl")
    assert ident.classify(_fi("FooRepository", "com.x.FooRepository")) == ("domain", "repositoryInterface")
    assert ident.classify(_fi("FooDO", "com.x.FooDO")) == ("infrastructure", "dataObject")


def test_classify_by_path_keyword():
    """无层段、无后缀 → 路径关键字；comp_type = className.lower()。"""
    ident = LayerIdentifier()
    r = ident.classify(_fi("Plain", "com.x.Plain", file_path="a/web/Plain.java"))
    assert r == ("adapter", "plain")


def test_classify_by_controller_annotation():
    ident = LayerIdentifier()
    r = ident.classify(_fi("X", "com.x.X", annotations=["Controller"]))
    assert r == ("adapter", "controller")


def test_classify_by_startup_annotation():
    ident = LayerIdentifier()
    r = ident.classify(_fi("App", "com.x.App", annotations=["SpringBootApplication"]))
    assert r == ("start", "application")


def test_classify_returns_none_when_no_signal():
    ident = LayerIdentifier()
    assert ident.classify(_fi("X", "com.x.X")) is None


def test_identify_domain_strips_layer_suffixes():
    ident = LayerIdentifier()
    assert ident.identify_domain_from_module("order-app", {}) == "order"
    assert ident.identify_domain_from_module("order-start", {}) == "order"
    assert ident.identify_domain_from_module("order-infrastructure", {}) == "order"
    assert ident.identify_domain_from_module("order-common", {}) == "order"
    assert ident.identify_domain_from_module("plain", {}) == "plain"
