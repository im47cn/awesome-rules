"""frontmatter_lib 行内列表语义单测（PR #201 前零覆盖）。

核心判别用例：空段过滤。旧实现 `[s.strip() for s in inner.split(",")]`
会保留 `[a,,b]` 的空串段；本套件钉死滤空语义，回退旧实现即红。
"""
import frontmatter_lib


def _parse_one(text: str):
    fm = frontmatter_lib.parse_frontmatter(f"---\nkey: {text}\n---\nbody")
    return fm["key"]


def test_inline_list_basic():
    assert _parse_one("[a, b, c]") == ["a", "b", "c"]


def test_inline_list_empty_bracket_variants():
    # `[]` 与全空白段 `[ ]` 均归约空列表
    assert _parse_one("[]") == []
    assert _parse_one("[ ]") == []
    assert _parse_one("[,]") == []


def test_inline_list_empty_segments_filtered():
    # 判别用例（负控制）：旧实现返回 ["a", "", "b"]
    assert _parse_one("[a,,b]") == ["a", "b"]
    assert _parse_one("[a, , b]") == ["a", "b"]
    assert _parse_one("[a,b,]") == ["a", "b"]


def test_inline_list_strips_items():
    assert _parse_one("[ foo , bar ]") == ["foo", "bar"]
