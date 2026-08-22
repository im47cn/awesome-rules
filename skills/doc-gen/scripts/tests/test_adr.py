"""AdrScanner 测试。

覆盖：ADR 编号标题解析、状态/日期提取（默认 proposed/空）、h1 回退、
无标题返回 None、候选目录（docs/adr）、子目录 README/index 解析。
"""

from generator.adr import AdrScanner


def _adr(tmp_path, name, text):
    d = tmp_path / "docs" / "adr"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(text, encoding="utf-8")
    return f


def test_adr_basic(tmp_path):
    """完整 ADR：编号标题 + 状态 + 日期。"""
    _adr(tmp_path, "0001-use-cola.md",
         "# ADR-0001: 采用 COLA 架构\n\n**状态**: Accepted\n**日期**: 2025-01-01\n\n## 背景\n")
    result = AdrScanner(str(tmp_path)).scan()
    assert result["total"] == 1
    a = result["adrs"][0]
    assert a["number"] == "0001"
    assert a["title"] == "采用 COLA 架构"
    assert a["status"] == "accepted"
    assert a["date"] == "2025-01-01"


def test_adr_h1_fallback(tmp_path):
    """无 ADR 编号的 h1 标题 → number 为空，title 取 h1。"""
    _adr(tmp_path, "decision.md", "# 某个决策\n\n状态: Proposed\n")
    a = AdrScanner(str(tmp_path)).scan()["adrs"][0]
    assert a["number"] == ""
    assert a["title"] == "某个决策"
    assert a["status"] == "proposed"


def test_adr_no_title_returns_none(tmp_path):
    """无任何标题的文件 → 不计入。"""
    _adr(tmp_path, "note.md", "这是纯正文，没有标题。\n")
    assert AdrScanner(str(tmp_path)).scan()["total"] == 0


def test_adr_default_status_when_missing(tmp_path):
    """无状态行 → 默认 proposed；无日期 → 空。"""
    _adr(tmp_path, "0002-x.md", "# ADR 2 另一决策\n\n正文\n")
    a = AdrScanner(str(tmp_path)).scan()["adrs"][0]
    assert a["status"] == "proposed"
    assert a["date"] == ""


def test_adr_subdir_readme(tmp_path):
    """子目录 README.md 被解析；index.md 作为回退。"""
    d = tmp_path / "docs" / "adr"
    d.mkdir(parents=True)
    _adr(tmp_path, "0001-a.md", "# ADR-0001: A\n")          # docs/adr/0001-a.md
    sub = d / "0002-sub"
    sub.mkdir()
    (sub / "README.md").write_text("# ADR-0002: B\n", encoding="utf-8")
    result = AdrScanner(str(tmp_path)).scan()
    nums = sorted(a["number"] for a in result["adrs"])
    assert nums == ["0001", "0002"]


def test_adr_subdir_index_fallback(tmp_path):
    """子目录无 README.md 时回退到 index.md。"""
    d = tmp_path / "docs" / "adr"
    d.mkdir(parents=True)
    sub = d / "sub-x"
    sub.mkdir()
    (sub / "index.md").write_text("# ADR-0003: C\n", encoding="utf-8")
    result = AdrScanner(str(tmp_path)).scan()
    assert any(a["number"] == "0003" for a in result["adrs"])


def test_adr_to_dict_filters_none():
    """_adr_to_dict 过滤值为 None 的键。"""
    out = AdrScanner._adr_to_dict({"a": 1, "b": None, "c": "x"})
    assert out == {"a": 1, "c": "x"}
