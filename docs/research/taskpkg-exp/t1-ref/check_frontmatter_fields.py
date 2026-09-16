#!/usr/bin/env python3
"""check_frontmatter_fields — steering 文档 frontmatter 必填字段 CI 门禁。

合规标准与 tools/gen_frontmatter_report.py 口径一致：frontmatter 同时包含
非空 ``title`` 与 ``scenario``（按第一个冒号切分、去首尾空白后非空）。
两者职责分离、实现不合并：报告生成器产出覆盖率文档并落盘，本工具只做
CI 门禁判定、不落盘任何文件。

用法:
    python3 tools/check_frontmatter_fields.py [扫描根目录]

缺省扫描仓库根的 steering/，递归含子目录。输出: 每处违规一行
``相对路径: 缺少非空 字段``（按路径字典序），末行汇总。
exit 0 = 全部合规；exit 1 = 存在违规；exit 2 = 用法/环境错误
（多传参数、根目录不存在、根目录下没有 .md 文件）。
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_FIELDS = ("title", "scenario")
DEFAULT_SCAN_ROOT = "steering"


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """解析 ``---`` 包裹、单行 ``key: value`` 的简易 frontmatter 块。

    返回字段映射；文件不以 ``---`` 开头、或块未闭合返回 None。
    按第一个冒号切分；空行与 ``#`` 注释行跳过；重复键首个生效。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        if key not in fields:
            fields[key] = value.strip()
    return None


def check_file(md: Path) -> list[str]:
    """单文件校验，返回违规消息清单（空 = 合规）。

    无 frontmatter 或块未闭合视同全部必填字段缺失。
    """
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [f"读取失败 {e}"]
    fields = parse_frontmatter(text) or {}
    return [
        f"缺少非空 {name}"
        for name in REQUIRED_FIELDS
        if not fields.get(name, "")
    ]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    if len(argv) > 1:
        print("用法: python3 tools/check_frontmatter_fields.py [扫描根目录]",
              file=sys.stderr)
        return 2
    repo_root = Path(__file__).resolve().parent.parent
    root = Path(argv[0]) if argv else repo_root / DEFAULT_SCAN_ROOT
    if not root.is_dir():
        print(f"错误: 不是目录: {root}", file=sys.stderr)
        return 2
    mds = sorted(root.rglob("*.md"),
                 key=lambda p: p.relative_to(root).as_posix())
    if not mds:
        print(f"错误: {root} 下没有 .md 文件", file=sys.stderr)
        return 2
    issues: list[str] = []
    for md in mds:
        rel = md.relative_to(root).as_posix()
        issues.extend(f"{rel}: {msg}" for msg in check_file(md))
    for line in issues:
        print(line)
    verdict = "通过" if not issues else "失败"
    print(f"frontmatter 门禁{verdict}: {len(mds)} 个文件, {len(issues)} 处违规")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
