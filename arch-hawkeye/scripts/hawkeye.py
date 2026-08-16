#!/usr/bin/env python3
"""
架构鹰眼 (Arch Hawkeye) — 全局架构观测与治理 CLI 入口

职责（见 arch-hawkeye/requirements.md）：
  - 多项目联邦聚合（消费各项目 CI 产出的 doc-manifest/）
  - 站点渲染复用 doc-gen 的 Astro 模板（数据归鹰眼，渲染借 doc-gen）

用法:
  python3 hawkeye.py aggregate projects.json --output site/ [--build]
  python3 hawkeye.py impact <聚合目录> --entity DemoController [--max-hops 3] [--json]

projects.json 格式:
  {
    "title": "公司架构全景",
    "projects": [
      {"id": "order-system", "name": "订单系统", "manifest": "./order/doc-manifest/", "repo": "..."}
    ]
  }

impact 变更实体支持：类名 / 限定名 / 路由 "GET /path"。
🔴 direct = 跨项目边直接命中（confirmed/inferred 分级）；
🟠 indirect = 项目内反向依赖链（deps BFS，按跳数裁剪）。
"""

import argparse
import json
import sys
from pathlib import Path

# 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import aggregate_projects  # noqa: E402
from impact import analyze_impact, load_graph, render_text  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="架构鹰眼 — 全局架构观测与治理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # aggregate — 多项目联邦聚合
    agg_parser = sub.add_parser("aggregate", help="聚合多个项目到架构鹰眼站点",
        epilog="示例: hawkeye.py aggregate hawkeye-projects.json --output site/ --build")
    agg_parser.add_argument("projects_json", help="项目列表 JSON 文件路径")
    agg_parser.add_argument("--output", "-o", default="./hawkeye-site", help="站点输出目录")
    agg_parser.add_argument("--build", action="store_true", help="聚合后立即构建站点")
    agg_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # impact — 跨项目变更影响分析（AH-C03）
    imp_parser = sub.add_parser("impact", help="跨项目变更影响分析（🔴直接/🟠间接）",
        epilog='示例: hawkeye.py impact ./site --entity DemoController\n'
               '      hawkeye.py impact ./site --entity "GET /demo/v1/orders/{id}"')
    imp_parser.add_argument("agg_dir", help="aggregate 输出目录（含 doc-manifest/）")
    imp_parser.add_argument("--entity", "-e", required=True,
                            help="变更实体：类名 / 限定名 / 路由 'METHOD /path'")
    imp_parser.add_argument("--max-hops", type=int, default=3,
                            help="项目内依赖链 BFS 最大跳数（默认 3）")
    imp_parser.add_argument("--json", action="store_true", help="输出 JSON（供 CI 消费）")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "aggregate":
        aggregate_projects(args.projects_json, args.output, args.build, args.verbose)
        return

    if args.command == "impact":
        result = analyze_impact(load_graph(args.agg_dir), args.entity,
                                max_hops=args.max_hops)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(render_text(result))
        sys.exit(0 if result.get("ok") else 2)
        return


if __name__ == "__main__":
    main()
