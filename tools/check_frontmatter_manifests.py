#!/usr/bin/env python3
"""check_frontmatter_manifests — frontmatter 清单门禁（M1/M2）

单一解析器 tools/frontmatter_lib.py 的门禁侧消费者（ADR-6 单实现）：
  M1 steering 族（steering/*.md 与 steering/gtsp/*.md）：title/scenario
     必填、单行、非空
  M2 skills 族（skills/*/SKILL.md）：name 必填；files 必填（断链单向 +
     路径围栏，见 frontmatter_lib.validate_skill）

非规范文档（docs/、README 等无 frontmatter 消费者的文件族）不在覆盖
范围（ADR-4：只为已验证的消费场景立法）。
无 frontmatter 的 steering 规范文件同样违规（索引注入依赖它）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter_lib  # noqa: E402


def main(argv: list) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".")
    errors: list = []

    steering = sorted((root / "steering").glob("*.md"))
    steering += sorted((root / "steering" / "gtsp").glob("*.md"))
    for path in steering:
        rel = path.relative_to(root)
        try:
            fm = frontmatter_lib.parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"M1 {rel}: {exc}")
            continue
        if not fm:
            errors.append(f"M1 {rel}: 缺少 frontmatter（title + scenario 必填）")
            continue
        errors += frontmatter_lib.validate_steering(fm, str(rel))

    for path in sorted((root / "skills").glob("*/SKILL.md")):
        rel = path.relative_to(root)
        skill_dir = path.parent
        try:
            fm = frontmatter_lib.parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"M2 {rel}: {exc}")
            continue
        if not fm:
            errors.append(f"M2 {rel}: 缺少 frontmatter（name + files 必填）")
            continue
        errors += frontmatter_lib.validate_skill(fm, str(rel), skill_dir)

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print(f"frontmatter-manifests: {len(errors)} 处违规", file=sys.stderr)
        return 1
    print(f"frontmatter-manifests: OK（steering {len(steering)} 份 + skills "
          f"{len(list((root / 'skills').glob('*/SKILL.md')))} 份）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
