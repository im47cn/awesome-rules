#!/usr/bin/env python3
"""impact-guard — 变更影响分析（blast radius）CLI

回答"改这个，会波及谁？"：给定变更点，沿依赖计算受影响范围，
按 🔴直接/🟠间接/🟡/🟢 分级（GTSP 5 通道边界）。

用法:
  python3 impact_check.py <project> --changed com.x.Y       # 显式起点
  python3 impact_check.py <project> --diff origin/master...HEAD
  python3 impact_check.py <project> --init                  # 生成边界配置
  python3 impact_check.py <project> --mode graph --changed com.x.Y  # Tier 2 Cypher

退出码: 0=无🔴直接 · 1=触及🔴直接且 --strict · 2=运行错误
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from boundary_scanner import CHANNEL_TITLES, init_config
from change_extractor import ChangeExtractor, load_config
from cross_service import build_cross_service_cypher, extract_feign_contracts
from critical_ranker import CriticalRanker, RankedChange
from graph_tracer import render_graph_mode
from impact_scanner import ImpactScanner
from renderer import build_receipt, commit_binding, render_json, render_mermaid, render_text


def main():
    parser = argparse.ArgumentParser(
        description="impact-guard — 变更影响分析（blast radius）")
    parser.add_argument("project", help="目标项目根目录")
    parser.add_argument("--diff", default=None,
                        help="从 git diff 提取变更点（如 origin/master...HEAD）")
    parser.add_argument("--changed", action="append", default=[],
                        help="显式变更起点（qualified_name 或文件路径，可多次）")
    parser.add_argument("--depth", type=int, default=3, help="影响传播深度（默认 3）")
    parser.add_argument("--mode", choices=["quick", "graph"], default="quick",
                        help="quick=Tier1 import 索引 / graph=输出 Tier2 Cypher")
    parser.add_argument("--format", choices=["text", "json", "mermaid"],
                        default="text", help="输出格式（默认 text）")
    parser.add_argument("--strict", action="store_true",
                        help="触及 🔴 直接影响则 exit 1（CI 门禁）")
    parser.add_argument("--config", help="配置文件 .impact-guard.json")
    parser.add_argument("--init", action="store_true",
                        help="扫描注解/SDK 生成边界配置后退出")
    parser.add_argument("--skip-reindex", action="store_true",
                        help="graph 模式跳过过期 reindex 提示（告警继续）")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    if not root.is_dir():
        print(f"❌ 目录不存在: {args.project}", file=sys.stderr)
        sys.exit(2)

    config = load_config(root, args.config)

    # --init：扫描生成边界配置
    if args.init:
        scanner = ImpactScanner(str(root), config)
        infos = scanner.scan()
        if not infos:
            print("❌ 未扫描到 Java 类（检查 project_package_prefix）", file=sys.stderr)
            sys.exit(2)
        cfg = init_config(str(root), infos, args.config)
        hits = cfg.get("boundary_hits", {})
        print(f"✅ 配置已生成 → {root / '.impact-guard.json'}")
        print(f"  包前缀: {cfg['project_package_prefix'] or '(未推断)'}")
        for ch, qns in hits.items():
            print(f"  {CHANNEL_TITLES[ch]}: {len(qns)} 类")
        sys.exit(0)

    # 变更点归一
    if not args.diff and not args.changed:
        print("❌ 需要 --diff 或 --changed 之一", file=sys.stderr)
        sys.exit(2)

    scanner = ImpactScanner(str(root), config)
    infos = scanner.scan()

    extractor = ChangeExtractor(str(root), config)
    if args.diff:
        points = extractor.extract_from_diff(args.diff, infos)
    else:
        points = extractor.extract_explicit(args.changed, infos)

    if not points:
        print("ℹ️ 未识别到 Java 变更点（无影响可分析）")
        sys.exit(0)

    unknown = [p for p in points if not p.qualified_name]
    if unknown:
        print(f"⚠️ {len(unknown)} 个变更点无法解析类名（文件已删除且无扫描记录）",
              file=sys.stderr)

    qns = [p.qualified_name for p in points if p.qualified_name]

    # graph 模式：输出 Tier 2 Cypher（Agent 编排执行），不在此做影响计算
    if args.mode == "graph":
        changed_methods = {p.qualified_name: p.changed_methods
                           for p in points if p.qualified_name and p.changed_methods}
        print(render_graph_mode(str(root), qns, args.depth, args.skip_reindex,
                                changed_methods))
        # 跨服务段（v2b）：变更点中的 Feign 契约 → 下游 Route 匹配 Cypher
        contracts = []
        for p in points:
            info = infos.get(p.qualified_name)
            if info and any("FeignClient" in a for a in info.get("annotations", [])):
                c = extract_feign_contracts(str(root), info,
                                            p.changed_methods or None)
                if c:
                    contracts.append(c)
        if contracts:
            cypher = build_cross_service_cypher(contracts)
            if cypher:
                print("\n```cypher")
                print(cypher)
                print("```")
        sys.exit(0)

    # quick 模式（Tier 1）：影响方向 + 分级
    ranker = CriticalRanker(config, infos)
    ranked = []
    for p in points:
        if not p.qualified_name:
            continue
        outbound = None
        impacts = []
        if p.qualified_name in ranker.entry_qn:
            outbound = scanner.propagate_outbound(p.qualified_name, args.depth)
        else:
            impacts = scanner.propagate_inbound(p.qualified_name, args.depth)
        ranked.append(ranker.rank_change(p, impacts, outbound))

    report = ranker.rank(ranked)

    # 收据信封（guard-receipt-spec）：provenance + decision + 证据边界声明
    # + verified 内容绑定（§4：结论钉在项目 git 提交切面上，防 stale receipt 误用）
    commit_sha, dirty = commit_binding(root)
    report.receipt = build_receipt(
        report, tier=1, strict=args.strict, diff_range=args.diff,
        changed_points=len(qns), scanned_classes=len(scanner.infos),
        config_source=args.config or "auto (.impact-guard.json)",
        boundary_channels=config.get("boundary_hits"),
        commit_sha=commit_sha, dirty=dirty)

    # v2b 跨服务契约提取：DIRECT 跨服务变更点 → 契约明细（评估范围明确化）
    for qn in report.cross_service:
        info = infos.get(qn)
        p = next((x for x in points if x.qualified_name == qn), None)
        if info:
            contract = extract_feign_contracts(str(root), info,
                                               p.changed_methods if p else None)
            if contract:
                report.cross_service_contracts[qn] = contract

    if args.format == "json":
        out = render_json(report, tier=1)
    elif args.format == "mermaid":
        out = render_mermaid(report)
    else:
        out = render_text(report, tier=1)
    print(out)

    if args.strict and report.level == "DIRECT":
        print("❌ --strict 门禁：触及 🔴 直接影响", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
