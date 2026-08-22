"""ArticleScanner 测试。

覆盖：分类规则、标题提取、摘要（引用块/段落）、frontmatter 注入、
首个 H1 剥离（消除双标题）、已有 frontmatter 补 title、端到端 scan、空文件。
"""

import pytest

from generator.article import ArticleScanner


# ── 分类规则 ─────────────────────────────────────────────────────────────────

def test_classify_rules():
    C = ArticleScanner._classify
    assert C("risk-assessment") == "风险与审查"
    assert C("captcha-lock") == "风险与审查"          # lock
    assert C("architecture-overview") == "架构设计"
    assert C("api-design") == "接口与数据"
    assert C("database-ddl") == "接口与数据"            # design 不误命中架构设计
    assert C("readme") == "索引"
    assert C("random-notes") == "其他"


# ── 标题/摘要提取 ─────────────────────────────────────────────────────────────

def test_extract_title():
    assert ArticleScanner._extract_title("# 标题\n正文") == "标题"
    assert ArticleScanner._extract_title("无标题正文") == ""


def test_extract_summary_quote_then_paragraph():
    s = ArticleScanner._extract_summary("> 引用摘要\n> 第二行\n\n正文段")
    assert s == "引用摘要 第二行"
    # 无引用块 → 首个有效段落
    s2 = ArticleScanner._extract_summary("# T\n\n---\n\n首个段落")
    assert s2 == "首个段落"
    assert ArticleScanner._extract_summary("# 仅标题") == ""


# ── frontmatter 注入 / H1 剥离 ────────────────────────────────────────────────

def test_strip_first_h1():
    out = ArticleScanner._strip_first_h1("# 标题\n\n正文")
    assert out == "正文"
    # 无 H1 → 原样
    assert ArticleScanner._strip_first_h1("正文") == "正文"


def test_inject_frontmatter_no_existing():
    body = ArticleScanner._inject_frontmatter("正文内容", "标题")
    assert body.startswith('---\ntitle: "标题"\n---')
    assert "正文内容" in body


def test_inject_frontmatter_existing_without_title():
    content = "---\ndescription: x\n---\n\n正文"
    body = ArticleScanner._inject_frontmatter(content, "标题")
    # 已有 frontmatter 但缺 title → 补入
    assert 'title: "标题"' in body


def test_inject_frontmatter_existing_with_title_unchanged():
    content = '---\ntitle: "已有"\n---\n\n正文'
    body = ArticleScanner._inject_frontmatter(content, "新标题")
    assert 'title: "已有"' in body
    assert "新标题" not in body


def test_inject_frontmatter_escapes_quote():
    body = ArticleScanner._inject_frontmatter("正文", '含"引号')
    assert '\\"' in body


# ── 端到端 scan ───────────────────────────────────────────────────────────────

def test_scan_end_to_end(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api-spec.md").write_text("# API 规范\n> 摘要内容\n正文段落\n", encoding="utf-8")
    (docs / "notes.md").write_text("# 备注\n", encoding="utf-8")
    result = ArticleScanner(str(tmp_path)).scan()
    assert result["total"] == 2
    assert result["categories"]["接口与数据"] == 1
    arts = {a["slug"]: a for a in result["articles"]}
    assert arts["api-spec"]["title"] == "API 规范"
    assert arts["api-spec"]["summary"] == "摘要内容"
    assert arts["api-spec"]["category"] == "接口与数据"
    # body 注入 frontmatter 并剥离正文首个 H1（无双标题）
    assert arts["api-spec"]["body"].startswith('---\ntitle: "API 规范"')
    assert "# API 规范" not in arts["api-spec"]["body"]
    assert arts["api-spec"]["link"] == "/articles/api-spec"


def test_parse_article_empty_returns_none(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "empty.md"
    f.write_text("   ", encoding="utf-8")
    assert ArticleScanner(str(tmp_path))._parse_article(f) is None


def test_scan_no_docs_dir(tmp_path):
    assert ArticleScanner(str(tmp_path)).scan() == {
        "total": 0, "categories": {}, "articles": []}
