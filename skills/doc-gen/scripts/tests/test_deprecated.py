"""@Deprecated 废弃标记全链路测试。

覆盖三层 + 序列化：
- 类级：@Deprecated 标注整个类 → ComponentDoc.deprecated
- 方法级：@Deprecated 标注 Controller 接口 → EndpointDoc.deprecated（@GetMapping 前/后两种写法 + 带参形式）
- 字段级：@Deprecated 标注字段 → FieldDoc.deprecated
- 序列化：ManifestWriter 输出 / OpenAPIGenerator 置 deprecated:true

设计依据见 scanner/java.py（DEPRECATED_RE 回看）与 generator/manifest.py
（_build_component 类级判定 + _extract_endpoints 方法级成员边界回看）。
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from scanner.java import JavaScanner  # noqa: E402
from generator.manifest import ManifestGenerator  # noqa: E402
from generator.openapi import OpenAPIGenerator  # noqa: E402
from builder.writer import ManifestWriter  # noqa: E402
from doctypes import (  # noqa: E402
    ComponentDoc, EndpointDoc, FieldDoc, DocManifest, DomainDoc, LayerDoc,
)


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return f


def _scan_one(tmp_path: Path, class_name: str):
    files = JavaScanner(str(tmp_path)).scan_java_files()
    return next(f for f in files if f["className"] == class_name)


# ── 类级 ──────────────────────────────────────────────────

def test_class_level_deprecated(tmp_path):
    _write(tmp_path, "domain/foo/FooEntity.java",
           "package com.x.foo.domain;\n"
           "@Deprecated\n"
           "public class FooEntity {\n"
           "    private String name;\n"
           "}\n")
    fi = _scan_one(tmp_path, "FooEntity")
    assert "Deprecated" in fi["annotations"]
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "entity", "domain")
    assert comp.deprecated is True


def test_class_level_not_deprecated_by_default(tmp_path):
    _write(tmp_path, "domain/foo/BarEntity.java",
           "package com.x.foo.domain;\n"
           "public class BarEntity {\n"
           "    private String name;\n"
           "}\n")
    fi = _scan_one(tmp_path, "BarEntity")
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "entity", "domain")
    assert comp.deprecated is False


# ── 方法级（Controller endpoint）──────────────────────────

def test_endpoint_deprecated_after_mapping(tmp_path):
    """@Deprecated 在 @GetMapping 之后（紧邻方法签名）。"""
    _write(tmp_path, "adapter/web/OldController.java",
           "package com.x.foo.adapter.web;\n"
           "import org.springframework.web.bind.annotation.*;\n"
           "@RestController\n"
           "@RequestMapping(\"/api\")\n"
           "public class OldController {\n"
           "    @GetMapping(\"/old\")\n"
           "    @Deprecated\n"
           "    public String oldApi() { return \"\"; }\n"
           "\n"
           "    @GetMapping(\"/new\")\n"
           "    public String newApi() { return \"\"; }\n"
           "}\n")
    fi = _scan_one(tmp_path, "OldController")
    eps = ManifestGenerator(str(tmp_path))._extract_endpoints(fi)
    by_path = {e.path: e.deprecated for e in eps}
    assert by_path.get("/api/old") is True
    assert by_path.get("/api/new") is False


def test_endpoint_deprecated_before_mapping(tmp_path):
    """@Deprecated 在 @GetMapping 之前 —— 验证「回看到成员边界」能覆盖此写法。"""
    _write(tmp_path, "adapter/web/OldController2.java",
           "package com.x.foo.adapter.web;\n"
           "import org.springframework.web.bind.annotation.*;\n"
           "@RestController\n"
           "@RequestMapping(\"/api\")\n"
           "public class OldController2 {\n"
           "    @Deprecated\n"
           "    @GetMapping(\"/legacy\")\n"
           "    public String legacyApi() { return \"\"; }\n"
           "}\n")
    fi = _scan_one(tmp_path, "OldController2")
    eps = ManifestGenerator(str(tmp_path))._extract_endpoints(fi)
    by_path = {e.path: e.deprecated for e in eps}
    assert by_path.get("/api/legacy") is True


def test_endpoint_deprecated_with_params(tmp_path):
    """@Deprecated(since=..., forRemoval=true) 带参形式同样识别。"""
    _write(tmp_path, "adapter/web/OldController3.java",
           "package com.x.foo.adapter.web;\n"
           "import org.springframework.web.bind.annotation.*;\n"
           "@RestController\n"
           "@RequestMapping(\"/api\")\n"
           "public class OldController3 {\n"
           "    @GetMapping(\"/v1\")\n"
           "    @Deprecated(since = \"1.2\", forRemoval = true)\n"
           "    public String v1Api() { return \"\"; }\n"
           "}\n")
    fi = _scan_one(tmp_path, "OldController3")
    eps = ManifestGenerator(str(tmp_path))._extract_endpoints(fi)
    by_path = {e.path: e.deprecated for e in eps}
    assert by_path.get("/api/v1") is True


# ── 字段级 ────────────────────────────────────────────────

def test_field_level_deprecated(tmp_path):
    _write(tmp_path, "infrastructure/foo/FooPO.java",
           "package com.x.foo.infrastructure;\n"
           "public class FooPO {\n"
           "    private String id;\n"
           "\n"
           "    @Deprecated\n"
           "    private String oldField;\n"
           "}\n")
    fi = _scan_one(tmp_path, "FooPO")
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "persistentObject", "infrastructure")
    fields = {f.name: f.deprecated for f in comp.fields}
    assert fields.get("oldField") is True
    assert fields.get("id") is False


# ── 序列化 ────────────────────────────────────────────────

def test_serialize_component_deprecated():
    """ManifestWriter 透传类/接口/字段三级 deprecated 到 JSON。"""
    comp = ComponentDoc(type="controller", className="OldCtrl", deprecated=True)
    comp.endpoints.append(EndpointDoc(method="GET", path="/old", deprecated=True))
    comp.fields.append(FieldDoc(name="oldField", type="String", deprecated=True))
    d = ManifestWriter._serialize_component(comp)
    assert d["deprecated"] is True
    assert d["endpoints"][0]["deprecated"] is True
    assert d["fields"][0]["deprecated"] is True


def test_openapi_deprecated_flag():
    """废弃接口在 OpenAPI spec 中置 deprecated:true（Scalar 据此渲染删除线）。"""
    comp = ComponentDoc(type="controller", className="OldCtrl")
    comp.endpoints.append(EndpointDoc(method="GET", path="/old", deprecated=True))
    layer = LayerDoc()
    layer.components.append(comp)
    domain = DomainDoc(name="foo", displayName="Foo")
    domain.layers["adapter"] = layer
    manifest = DocManifest()
    manifest.domains.append(domain)
    spec = OpenAPIGenerator(".", "test").generate(manifest)
    op = spec["paths"]["/old"]["get"]
    assert op.get("deprecated") is True


# ── 问题1：Javadoc @deprecated 标签（无 @Deprecated 注解）──

def test_class_level_javadoc_deprecated(tmp_path):
    """仅 Javadoc @deprecated 标签的类也应识别（_strip_comments 转写为 @Deprecated）。"""
    _write(tmp_path, "domain/foo/DocOnlyEntity.java",
           "package com.x.foo.domain;\n"
           "/**\n"
           " * @deprecated 改用 {@link NewEntity}\n"
           " */\n"
           "public class DocOnlyEntity {\n"
           "    private String name;\n"
           "}\n")
    fi = _scan_one(tmp_path, "DocOnlyEntity")
    assert fi["deprecated"] is True
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "entity", "domain")
    assert comp.deprecated is True


def test_field_level_javadoc_deprecated(tmp_path):
    """仅 Javadoc @deprecated 标签字段也应识别。"""
    _write(tmp_path, "infrastructure/foo/DocPO.java",
           "package com.x.foo.infrastructure;\n"
           "public class DocPO {\n"
           "    /** @deprecated 改用 newField */\n"
           "    private String oldField;\n"
           "    private String keep;\n"
           "}\n")
    fi = _scan_one(tmp_path, "DocPO")
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "persistentObject", "infrastructure")
    fields = {f.name: f.deprecated for f in comp.fields}
    assert fields.get("oldField") is True
    assert fields.get("keep") is False


def test_endpoint_javadoc_deprecated(tmp_path):
    """Controller 方法仅 Javadoc @deprecated 标签也应识别（_extract_endpoints 读 raw）。"""
    _write(tmp_path, "adapter/web/DocController.java",
           "package com.x.foo.adapter.web;\n"
           "import org.springframework.web.bind.annotation.*;\n"
           "@RestController\n"
           "@RequestMapping(\"/api\")\n"
           "public class DocController {\n"
           "    /**\n"
           "     * @deprecated 改用 /api/v2\n"
           "     */\n"
           "    @GetMapping(\"/v1\")\n"
           "    public String v1() { return \"\"; }\n"
           "}\n")
    fi = _scan_one(tmp_path, "DocController")
    eps = ManifestGenerator(str(tmp_path))._extract_endpoints(fi)
    by_path = {e.path: e.deprecated for e in eps}
    assert by_path.get("/api/v1") is True


# ── 问题2：字段 @Deprecated 夹在其他注解之间 ──────────────

def test_field_deprecated_between_other_annotations(tmp_path):
    """@Deprecated 非紧邻声明（夹在其他注解间），「成员边界回看」应识别两种顺序。"""
    _write(tmp_path, "infrastructure/foo/MultiAnnoPO.java",
           "package com.x.foo.infrastructure;\n"
           "public class MultiAnnoPO {\n"
           "    @TableField(\"old_col\")\n"
           "    @Deprecated\n"
           "    private String legacy;\n"
           "\n"
           "    @Deprecated\n"
           "    @TableField(\"old2\")\n"
           "    private String legacy2;\n"
           "\n"
           "    private String keep;\n"
           "}\n")
    fi = _scan_one(tmp_path, "MultiAnnoPO")
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "persistentObject", "infrastructure")
    fields = {f.name: f.deprecated for f in comp.fields}
    assert fields.get("legacy") is True    # @Deprecated 在 @TableField 之后
    assert fields.get("legacy2") is True   # @Deprecated 在 @TableField 之前
    assert fields.get("keep") is False


def test_class_not_deprecated_when_only_field_deprecated(tmp_path):
    """类本身未废弃、仅字段废弃时，类级不应被误判（规避全文件 annotations 提取的陷阱）。"""
    _write(tmp_path, "domain/foo/MixedEntity.java",
           "package com.x.foo.domain;\n"
           "public class MixedEntity {\n"
           "    private String keep;\n"
           "\n"
           "    @Deprecated\n"
           "    private String oldField;\n"
           "}\n")
    fi = _scan_one(tmp_path, "MixedEntity")
    assert fi["deprecated"] is False
    comp = ManifestGenerator(str(tmp_path))._build_component(fi, "entity", "domain")
    assert comp.deprecated is False
    fields = {f.name: f.deprecated for f in comp.fields}
    assert fields.get("oldField") is True
