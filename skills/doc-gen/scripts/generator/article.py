"""手写深度文档扫描器。

扫描项目 docs/ 目录下的 .md 文档（adr/ 子目录由 AdrScanner 独立负责），
提取标题/摘要/分类，注入 Starlight frontmatter 生成可渲染页面 body，
供站点 sidebar 展示与 AI Agent 关键词检索。
"""

import re
from pathlib import Path
from typing import Optional


class ArticleScanner:
    """扫描项目 docs/*.md 手写深度文档，生成带 frontmatter 的页面数据"""

    # 分类关键词（按文件名匹配，顺序即优先级）。design 归入「接口与数据」
    # 以免 database-design 误命中「架构设计」。
    CATEGORY_RULES = [
        ("风险与审查", ("risk", "leak", "assessment", "violation", "orphan", "register", "captcha", "lock", "guard")),
        ("架构设计", ("architecture", "optimization", "overview")),
        ("接口与数据", ("api", "database", "ddl", "sql", "design")),
        ("索引", ("readme", "index")),
    ]
    DEFAULT_CATEGORY = "其他"

    H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def scan(self) -> dict:
        """扫描 docs/*.md，返回 {total, categories, articles}"""
        docs_dir = self.root_path / "docs"
        articles = []
        if docs_dir.is_dir():
            for md_file in sorted(docs_dir.glob("*.md")):
                article = self._parse_article(md_file)
                if article:
                    articles.append(article)

        categories: dict = {}
        for a in articles:
            categories[a["category"]] = categories.get(a["category"], 0) + 1

        return {"total": len(articles), "categories": categories, "articles": articles}

    def _parse_article(self, file_path: Path) -> Optional[dict]:
        """解析单个 md 文档，注入 frontmatter 生成 body"""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None
        if not content.strip():
            return None

        slug = file_path.stem
        title = self._extract_title(content) or slug
        body = self._inject_frontmatter(content, title)
        # searchText：去掉 frontmatter 的正文，供 AI Agent 关键词检索
        search_text = self.FRONTMATTER_RE.sub("", body, count=1).strip()

        return {
            "slug": slug,
            "title": title,
            "summary": self._extract_summary(content),
            "category": self._classify(slug),
            "wordCount": len(content),
            "sourcePath": str(file_path.relative_to(self.root_path)),
            "link": f"/articles/{slug}",
            "body": body,
            "searchText": search_text,
        }

    @staticmethod
    def _extract_title(content: str) -> str:
        """从首个 H1 提取标题"""
        m = ArticleScanner.H1_RE.search(content)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _extract_summary(content: str) -> str:
        """首个 > 引用块作为摘要；无则首个非标题/非 frontmatter 段落"""
        # 连续的 > 引用块
        quote_lines = []
        for line in content.splitlines():
            if line.startswith(">"):
                quote_lines.append(line.lstrip(">").strip())
            elif quote_lines:
                break
        if quote_lines:
            return " ".join(quote_lines)[:200]

        # 回退：首个有效段落
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "---", ">")):
                return stripped[:200]
        return ""

    @classmethod
    def _classify(cls, slug: str) -> str:
        """按文件名关键词启发式分类"""
        slug_lower = slug.lower()
        for category, keywords in cls.CATEGORY_RULES:
            if any(kw in slug_lower for kw in keywords):
                return category
        return cls.DEFAULT_CATEGORY

    @classmethod
    def _inject_frontmatter(cls, content: str, title: str) -> str:
        """注入 Starlight 必填的 title frontmatter（title 是唯一必填字段）。

        Starlight 会将 frontmatter.title 渲染为页面 H1，故需先剥离正文首个 H1，
        否则会与正文 H1 重复显示（双标题）。
        """
        content = cls._strip_first_h1(content)
        if content.lstrip().startswith("---"):
            return cls._ensure_title_in_frontmatter(content, title)
        escaped = title.replace('"', '\\"')
        return f'---\ntitle: "{escaped}"\n---\n\n{content.lstrip()}'

    @classmethod
    def _strip_first_h1(cls, content: str) -> str:
        """剥离正文首个 H1（标题已由 frontmatter.title 承载），消除双标题。"""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if cls.H1_RE.match(line):
                del lines[i]
                # 吸收紧随的空行，避免段落间出现多余空行
                if i < len(lines) and lines[i].strip() == "":
                    del lines[i]
                return "\n".join(lines)
        return content

    @staticmethod
    def _ensure_title_in_frontmatter(content: str, title: str) -> str:
        """已有 frontmatter 时，若缺 title 则补入"""
        m = re.match(r"\A---\n(.*?)\n---", content, re.DOTALL)
        if not m:
            return content
        fm = m.group(1)
        if re.search(r"^title\s*:", fm, re.MULTILINE):
            return content  # 已有 title
        escaped = title.replace('"', '\\"')
        return content[: m.start(1)] + f'title: "{escaped}"\n' + content[m.start(1):]
