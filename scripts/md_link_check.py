#!/usr/bin/env python3
"""md_link_check — Markdown 链接完整性统一门禁（链接有效性 + README 索引零漂移）

合并原 readme_index_check（磁盘→README 索引完整性）与 md_link_check
（全部 .md 的链接有效性），双向闭环：

A. 链接有效性（覆盖仓库内全部 .md，排除 node_modules 等产物目录）
   1. 相对链接/图片目标文件必须存在（URL 解码后解析）
   2. .md 目标带 #锚点（含页内裸锚）时，锚点须命中目标实际标题
      （GitHub 风格 slug：小写、去标点、空白→连字符，中文按 \w 保留）
   3. 外部地址（http(s)/mailto）与代码围栏/行内代码内的示例链接不校验
B. README 索引零漂移（README.md 内以链接登记的资产须与磁盘一致）
   1. skills/：每个含 README.md 或 SKILL.md 的技能目录须有 `skills/<name>/` 链接
   2. steering/*.md（直接子文件；gtsp/ 子目录走总入口不逐个校验）
   3. docs/design/*.md

背景：README 索引靠人肉同步必然滞后（实测漏登记 4 处）；索引先于被索引文件
推送造成远端死链（实测 2026-08-20 skills/skill-evo/README.md）。确定性校验，
不做生成——发现漂移即 exit 1，由人工（或 skill-evo 提案）补齐。

用法:
  python3 scripts/md_link_check.py            # check（默认，仓库根自动定位）
  python3 scripts/md_link_check.py <repo_root>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

# 产物/依赖目录：仓库自身文档之外的海量第三方 md，结构性排除
_EXCLUDE_PARTS = {"node_modules", ".git", "dist", "build", ".codebase-memory"}
# 形如 http:// https:// mailto: 的目标不做网络校验
_EXTERNAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", re.I)
_FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# [text](target) / ![alt](target)；不匹配转义括号与裸 () 强调
_LINK_RE = re.compile(r"\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\))?\s*\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)


# ── A. 链接有效性 ────────────────────────────────────────────────────────────

def _strip_code(text: str) -> str:
    """剥离代码围栏与行内代码：示例链接不代表真实链接意图。"""
    text = _FENCE_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", text)


def _slug(heading: str) -> str:
    """GitHub 风格锚点 slug（中文按 \w 保留，标点剔除，空白→连字符）。"""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s", "-", s)


def _anchors_of(text: str) -> set:
    """文件内全部标题锚点（剥离代码块后取标题行）。"""
    return {_slug(m.group(2)) for m in _HEADING_RE.finditer(_strip_code(text))}


def iter_md_files(root: Path):
    for p in sorted(root.rglob("*.md")):
        if _EXCLUDE_PARTS & set(p.parts):
            continue
        yield p


def check_file(md: Path, root: Path) -> list:
    """单文件链接校验，返回问题清单（空 = 通过）。"""
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [f"{md.relative_to(root)}: 读取失败 {e}"]
    issues = []
    stripped = _strip_code(text)
    for lineno, line in enumerate(stripped.splitlines(), 1):
        for m in _LINK_RE.finditer(line):
            target = m.group(1)
            if _EXTERNAL_RE.match(target):
                continue
            path_part, _, anchor = target.partition("#")
            if path_part:
                resolved = (md.parent / unquote(path_part)).resolve()
                if not resolved.exists():
                    issues.append(f"{md.relative_to(root)}:{lineno}: 目标不存在 → {target}")
                    continue
            if anchor and (not path_part or resolved.suffix.lower() == ".md"):
                # 页内锚，或指向 md 的锚点：须命中实际标题
                target_text = text if not path_part else resolved.read_text(
                    encoding="utf-8", errors="replace")
                if _slug(unquote(anchor)) not in _anchors_of(target_text):
                    issues.append(f"{md.relative_to(root)}:{lineno}: 锚点未命中 → {target}")
    return issues


def check_links(root: Path) -> list:
    issues = []
    for md in iter_md_files(root):
        issues.extend(check_file(md, root))
    return issues


# ── B. README 索引零漂移 ─────────────────────────────────────────────────────

def check_readme_index(root: Path) -> list:
    """磁盘资产 ↔ README 登记一致性，返回漂移清单（空 = 通过）。"""
    readme = root / "README.md"
    if not readme.is_file():
        return [f"缺少 {readme}"]
    linked = set(re.findall(r"\]\(([^)#?]+)\)", readme.read_text(encoding="utf-8")))
    drift = []

    # 1) skills/<name>/：有 README.md 或 SKILL.md 的目录（链接可指向目录或其中文件）
    skills = root / "skills"
    if skills.is_dir():
        for d in sorted(skills.iterdir()):
            if d.is_dir() and ((d / "README.md").is_file() or (d / "SKILL.md").is_file()):
                rel = f"skills/{d.name}/"
                if not any(l == rel or l == rel.rstrip("/") or l.startswith(rel)
                           for l in linked):
                    drift.append(f"技能未登记 README 索引：{rel}")

    # 2) steering/*.md 直接子文件（gtsp/ 子目录走总入口，不逐个校验）
    steering = root / "steering"
    if steering.is_dir():
        for f in sorted(steering.glob("*.md")):
            if f"steering/{f.name}" not in linked:
                drift.append(f"规范未登记 README 索引：steering/{f.name}")

    # 3) docs/design/*.md
    design = root / "docs" / "design"
    if design.is_dir():
        for f in sorted(design.glob("*.md")):
            if f"docs/design/{f.name}" not in linked:
                drift.append(f"设计文档未登记 README 索引：docs/design/{f.name}")

    return drift


# ── 门禁入口 ─────────────────────────────────────────────────────────────────

def main() -> int:
    root = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent)
    failed = False
    n = len(list(iter_md_files(root)))
    links = check_links(root)
    if links:
        print(f"❌ 链接有效性：{len(links)} 处失效（扫描 {n} 个 .md）：")
        for i in links:
            print(f"  - {i}")
        failed = True
    else:
        print(f"✅ 链接有效性通过（{n} 个 .md，相对链接与锚点全部有效）")
    drift = check_readme_index(root)
    if drift:
        print(f"❌ README 索引零漂移：{len(drift)} 处：")
        for d in drift:
            print(f"  - {d}")
        failed = True
    else:
        print("✅ README 索引与磁盘一致（skills/steering/design 全登记）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
