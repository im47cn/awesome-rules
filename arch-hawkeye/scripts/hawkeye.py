#!/usr/bin/env python3
"""
架构鹰眼 (Arch Hawkeye) — 全局架构观测与治理 CLI 入口

职责（见 arch-hawkeye/AH-MANIFEST.md）：
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

    # baseline — 冻结违规清单为命名基线（D01，存量自动登记债务）
    bl_parser = sub.add_parser("baseline", help="冻结当前违规清单为治理基线")
    bl_parser.add_argument("manifest_dir", help="doc-manifest/ 目录（含 risks.json）")
    bl_parser.add_argument("--name", "-n", required=True, help="基线名（如 2026H2）")

    # trend — 趋势对比（D02：added/removed/retained + 债务闭环）
    tr_parser = sub.add_parser("trend", help="当前违规 vs 基线趋势对比")
    tr_parser.add_argument("manifest_dir", help="doc-manifest/ 目录")
    tr_parser.add_argument("--baseline", "-b", required=True, help="基线名")
    tr_parser.add_argument("--json", action="store_true", help="输出 JSON")

    # gate — 增量零容忍门禁（D07，--warn-only 灰度）
    gt_parser = sub.add_parser("gate", help="治理门禁：新增违规零容忍（CI 用）")
    gt_parser.add_argument("manifest_dir", help="doc-manifest/ 目录")
    gt_parser.add_argument("--baseline", "-b", required=True, help="基线名")
    gt_parser.add_argument("--warn-only", action="store_true", help="灰度：仅告警不阻断")
    gt_parser.add_argument("--json", action="store_true", help="输出 JSON（exit code 语义不变）")

    # local — 本地双模式（B01）：仓库路径列表 → scan → 聚合 → 治理视图
    lc_parser = sub.add_parser("local", help="本地模式：本地仓库 scan+聚合+治理（零服务依赖）",
        epilog="示例: hawkeye.py local ~/sources/projA ~/sources/projB --baseline 2026H2")
    lc_parser.add_argument("repos", nargs="+", help="各项目仓库根目录路径")
    lc_parser.add_argument("--output", "-o", default="./hawkeye-local", help="输出目录")
    lc_parser.add_argument("--baseline", "-b", help="对含基线的项目执行 trend（治理视图）")
    lc_parser.add_argument("--build", action="store_true", help="聚合后构建站点")

    # debt — 债务登记表（D04/D05：list / exempt）
    dt_parser = sub.add_parser("debt", help="技术债务登记表")
    dt_parser.add_argument("manifest_dir", help="doc-manifest/ 目录")
    dt_parser.add_argument("action", choices=["list", "overdue", "exempt"])
    dt_parser.add_argument("--fp", help="债务 fingerprint（exempt 用）")
    dt_parser.add_argument("--reason", help="豁免理由（exempt 必填）")
    dt_parser.add_argument("--until", help="豁免到期日（ISO 日期，如 2026-12-31；"
                                           "到期进入 overdue 复核视野，缺省永久")

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

    if args.command == "baseline":
        from governance import create_baseline
        try:
            info = create_baseline(args.manifest_dir, args.name)
        except (FileExistsError, FileNotFoundError, RuntimeError) as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(2)
        print(f"📍 基线 '{info['baseline']}' 已冻结: {info['totalIssues']} 条违规，"
              f"{info['debts']} 条债务登记")
        return
    if args.command == "trend":
        from governance import (diff_risks, load_baseline, load_risks_status,
                                sync_ledger)
        try:
            baseline = load_baseline(args.manifest_dir, args.baseline)
        except FileNotFoundError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(2)
        current, risk_status = load_risks_status(args.manifest_dir)
        if risk_status != "ok":
            print(f"❌ risks 数据不可信（{risk_status}），趋势无意义——"
                  f"先修复 doc-gen scan", file=sys.stderr)
            sys.exit(2)
        diff = diff_risks(baseline, current)
        closed = sync_ledger(args.manifest_dir, current)
        diff["ledgerClosed"] = closed["closedCount"]
        if args.json:
            print(json.dumps(diff, ensure_ascii=False, indent=2))
        else:
            st = diff["stats"]
            print(f"📈 趋势 vs 基线 {args.baseline}: "
                  f"{st['baseline']} → {st['current']}"
                  f"（新增 {st['added']} / 消除 {st['removed']} / 净 {st['net']:+d}）")
            for i in diff["added"][:10]:
                print(f"   🔴 [{i.get('severity')}] {i.get('file')}:{i.get('line')}")
            if closed["closedCount"]:
                print(f"   ✅ 债务自动关闭 {closed['closedCount']} 条（D06）")
        return

    if args.command == "gate":
        from governance import gate, load_baseline, render_gate
        try:
            load_baseline(args.manifest_dir, args.baseline)
        except FileNotFoundError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(2)
        result = gate(args.manifest_dir, args.baseline, warn_only=args.warn_only)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(render_gate(result))
        sys.exit(1 if result["blocked"] else 0)
        return

    if args.command == "local":
        from local_mode import run_local
        ok = run_local(args.repos, args.output, baseline=args.baseline,
                       build=args.build)
        sys.exit(0 if ok else 1)
        return

    if args.command == "debt":
        from governance import exempt_debt, load_ledger, overdue_debts
        if args.action == "list":
            ledger = load_ledger(args.manifest_dir)
            by_status = {}
            for d in ledger["debts"]:
                by_status.setdefault(d["status"], []).append(d)
            for status, items in sorted(by_status.items()):
                print(f"{status}: {len(items)}")
                for d in items[:5]:
                    print(f"   {d['fingerprint'][:12]} [{d['severity']}] "
                          f"{d['file']} ← {d['owner']}"
                          + (f" due={d['dueDate']}" if d.get("dueDate") else ""))
        elif args.action == "overdue":
            items = overdue_debts(args.manifest_dir)
            print(f"⚠️ 超期未偿还: {len(items)} 条（D05）")
            for d in items[:10]:
                print(f"   🔴 {d['fingerprint'][:12]} [{d['severity']}] "
                      f"{d['file']} ← {d['owner']}（超期 {d['overdueDays']} 天）")
        elif args.action == "exempt":
            if not args.fp or not args.reason:
                print("❌ exempt 需要 --fp 与 --reason", file=sys.stderr)
                sys.exit(2)
            try:
                d = exempt_debt(args.manifest_dir, args.fp, args.reason,
                                until=args.until)
                print(f"✅ 已豁免 {d['fingerprint'][:12]}: {args.reason}"
                      + (f"（至 {args.until}）" if args.until else "（永久）"))
            except (KeyError, ValueError) as e:
                print(f"❌ {e}", file=sys.stderr)
                sys.exit(2)
        return


if __name__ == "__main__":
    main()
