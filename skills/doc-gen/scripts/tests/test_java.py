"""JavaScanner 测试。

覆盖：_parse_java_file（package/类/注解/import/方法/字段/枚举/嵌套枚举）、
_should_scan（SKIP_DIRS）、_strip_comments（块/行注释、字符串与字符字面量保留、
未闭合注释、@deprecated 转写）、_deprecated_above、无类/不可读/越界路径分支。
"""

from pathlib import Path

from scanner.java import JavaScanner


JAVA = """package com.x;
import java.util.List;

/** 类说明 */
@RestController
public class OrderController {
    public void doSomething(String a) {}
    private String name;
}
"""


def test_parse_full(tmp_path):
    f = tmp_path / "OrderController.java"
    f.write_text(JAVA, encoding="utf-8")
    r = JavaScanner(str(tmp_path))._parse_java_file(f)
    assert r["package"] == "com.x"
    assert r["className"] == "OrderController"
    assert r["classType"] == "class"
    assert "RestController" in r["annotations"]
    assert "java.util.List" in r["imports"]
    assert any(m["name"] == "doSomething" for m in r["methods"])
    assert any(fl["name"] == "name" for fl in r["fields"])
    assert r["filePath"] == "OrderController.java"


def test_enum_values(tmp_path):
    f = tmp_path / "Status.java"
    f.write_text("package com.x;\npublic enum Status { ACTIVE, INACTIVE }\n", encoding="utf-8")
    r = JavaScanner(str(tmp_path))._parse_java_file(f)
    assert r["classType"] == "enum"
    assert r["enumValues"] == ["ACTIVE", "INACTIVE"]


def test_nested_enum(tmp_path):
    f = tmp_path / "Order.java"
    f.write_text("package com.x;\npublic class Order {\n  public enum Color { RED, GREEN }\n}\n",
                 encoding="utf-8")
    r = JavaScanner(str(tmp_path))._parse_java_file(f)
    assert r["classType"] == "class"
    assert any(ne["name"] == "Color" and "RED" in ne["values"] for ne in r["nestedEnums"])


def test_should_scan(tmp_path):
    s = JavaScanner(str(tmp_path))
    assert s._should_scan(tmp_path / "src" / "X.java") is True
    assert s._should_scan(tmp_path / "target" / "X.java") is False


def test_parse_no_class_returns_none(tmp_path):
    f = tmp_path / "A.java"
    f.write_text("package x;\n// 仅注释，无类\n", encoding="utf-8")
    assert JavaScanner(str(tmp_path))._parse_java_file(f) is None


def test_parse_unreadable_returns_none(tmp_path, monkeypatch):
    f = tmp_path / "A.java"
    f.write_text("package x;", encoding="utf-8")
    orig = Path.read_text

    def boom(self, *a, **k):
        if self == f:
            raise OSError("x")
        return orig(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    assert JavaScanner(str(tmp_path))._parse_java_file(f) is None


def test_relative_path_outside_root(tmp_path):
    """file_path 不在 root_path 下 → relative_to 抛 ValueError → 回退全路径。"""
    f = tmp_path / "A.java"
    f.write_text("package x;\npublic class A {}\n", encoding="utf-8")
    scanner = JavaScanner(str(tmp_path / "sub"))        # root 是 sub，f 在外
    r = scanner._parse_java_file(f)
    assert r["filePath"] == str(f)


# ── _strip_comments 分支 ──────────────────────────────────────────────────────

def test_strip_block_comment():
    out = JavaScanner._strip_comments("int a; /* c */ int b;")
    assert "/* c */" not in out
    assert "int b;" in out


def test_strip_deprecated_javadoc_rewritten():
    out = JavaScanner._strip_comments("/** @deprecated 旧 */ class X")
    assert "@Deprecated" in out                      # @deprecated Javadoc → @Deprecated


def test_strip_string_preserves_inner():
    out = JavaScanner._strip_comments('String s = "a // not c";')
    assert '"a // not c"' in out                     # 字符串内 // 保留


def test_strip_char_literal_preserved():
    out = JavaScanner._strip_comments("char c = 'a';")
    assert "'a'" in out


def test_strip_unclosed_block():
    # 等长空格化（v2）：未闭合块注释 → 等长空白，长度与换行位置不变
    assert JavaScanner._strip_comments("/* 未闭合") == " " * len("/* 未闭合")


def test_strip_length_preserved():
    """等长契约：任意输入下 len 与换行位置不变（方法行号的正确性根基）"""
    src = """package p; // 注释
/**
 * @deprecated 旧
 */
class A { /* b */ int x; }
String s = "a // not c";
// 尾注释
"""
    out = JavaScanner._strip_comments(src)
    assert len(out) == len(src)
    assert [i for i, c in enumerate(out) if c == "\n"] == \
           [i for i, c in enumerate(src) if c == "\n"]
    assert "@Deprecated" in out and "not c" in out


def test_strip_line_comment():
    out = JavaScanner._strip_comments("int a; // c\nint b;")
    assert "// c" not in out
    assert "int b;" in out


def test_strip_unclosed_line_comment():
    out = JavaScanner._strip_comments("int a; // c")
    assert "// c" not in out


# ── _deprecated_above ─────────────────────────────────────────────────────────

def test_deprecated_above_true_and_false():
    content = "@Deprecated public class X"
    assert JavaScanner._deprecated_above(content, content.index("public")) is True
    content2 = "public class X"
    assert JavaScanner._deprecated_above(content2, content2.index("public")) is False
