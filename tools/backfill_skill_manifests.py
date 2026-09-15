#!/usr/bin/env python3
"""backfill_skill_manifests — skills files 声明存量程序化补全（ADR-5）

程序化全量枚举（CLAUDE.md 枚举原则）：每个 skill 的 files 声明 =
该目录下全部 git 跟踪文件，除 SKILL.md 自身（它是声明载体，不是被声明物）。
幂等：已存在的 files 键整块替换，其余 frontmatter 字段原样保留。

新 skill 起草时可直接复跑本脚本生成基线清单，再按需裁剪——
但裁剪须在 PR 中说明（门禁只查断链，不查多声明，ADR-3）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter_lib  # noqa: E402


def tracked_files(skill_dir: Path, repo_root: Path) -> list:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", str(skill_dir.relative_to(repo_root))],
        capture_output=True, check=True, cwd=repo_root,
    ).stdout.decode("utf-8")
    prefix = f"{skill_dir.relative_to(repo_root).as_posix()}/"
    files = [rel for line in out.split("\0")
             if line.startswith(prefix) and (rel := line[len(prefix):]) != "SKILL.md"]
    return sorted(files)


def render_files_block(files: list) -> str:
    if not files:
        return "files: []"
    lines = ["files:"]
    lines += [f"  - {f}" for f in files]
    return "\n".join(lines)


def backfill(skill_md: Path, repo_root: Path) -> bool:
    content = skill_md.read_text(encoding="utf-8")
    fm = frontmatter_lib.split_frontmatter(content)
    if fm is None:
        print(f"跳过（无 frontmatter）: {skill_md.parent.name}", file=sys.stderr)
        return False
    # 键级幂等：只移除旧 files 键及其紧随的缩进列表项，其余字段
    # （含 description: > 折叠块的缩进续行）原样保留
    kept = []
    skipping = False
    for ln in fm.splitlines():
        if ln.startswith("files:"):
            skipping = True
        elif skipping and (ln.startswith("  ") or ln.strip() == ""):
            pass  # 旧 files 键及其紧随列表项，移除
        else:
            skipping = False
            kept.append(ln)
    files = tracked_files(skill_md.parent, repo_root)
    new_fm = "\n".join(kept) + "\n" + render_files_block(files)
    start = content.index("---") + 3
    end = content.index("\n---", start)
    new_content = content[:start] + new_fm + content[end:]
    if new_content != content:
        skill_md.write_text(new_content, encoding="utf-8")
        print(f"{skill_md.parent.name}: files ← {len(files)} 项")
        return True
    print(f"{skill_md.parent.name}: 已最新（{len(files)} 项）")
    return False


def main(argv: list) -> int:
    default_root = Path(__file__).resolve().parent.parent
    repo_root = Path(argv[1] if len(argv) > 1 else default_root).resolve()
    changed = sum(backfill(skill_md, repo_root)
                  for skill_md in sorted((repo_root / "skills").glob("*/SKILL.md")))
    print(f"共更新 {changed} 个 SKILL.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
