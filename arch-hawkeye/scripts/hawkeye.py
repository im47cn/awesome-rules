#!/usr/bin/env python3
"""
架构鹰眼 (Arch Hawkeye) — 全局架构观测与治理 CLI 入口

职责（见 arch-hawkeye/requirements.md）：
  - 多项目联邦聚合（消费各项目 CI 产出的 doc-manifest/）
  - 站点渲染复用 doc-gen 的 Astro 模板（数据归鹰眼，渲染借 doc-gen）

用法:
  python3 hawkeye.py aggregate projects.json --output site/ [--build]

projects.json 格式:
  {
    "title": "公司架构全景",
    "projects": [
      {"id": "order-system", "name": "订单系统", "manifest": "./order/doc-manifest/", "repo": "..."}
    ]
  }

后续规划（Phase 2+，见 requirements.md REQ-C/REQ-D）:
  - 跨仓库知识图谱（真实跨项目调用链）
  - 治理闭环（基线快照/趋势对比/责任归属/债务登记/超期告警）
"""

import argparse
import sys
from pathlib import Path

# 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import aggregate_projects  # noqa: E402


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

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "aggregate":
        aggregate_projects(args.projects_json, args.output, args.build, args.verbose)
        return


if __name__ == "__main__":
    main()
