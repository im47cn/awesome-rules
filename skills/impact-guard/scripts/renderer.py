"""Renderer — text / json / mermaid 三态渲染"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Optional, Tuple

from critical_ranker import LEVEL_ICONS


def _short(qn: str) -> str:
    return qn.rsplit(".", 1)[-1] if "." in qn else qn


def commit_binding(root) -> Tuple[Optional[str], Optional[bool]]:
    """项目 git 提交切面（guard-receipt-spec §4）：

    返回 (commit_sha, dirty)：HEAD 的 40 位原生 sha 与工作区相对 HEAD 是否有差异
    （含未跟踪文件——guard 按文件系统扫描，未跟踪文件同样进入分析）。
    非 git 仓库 / git 不可用 → (None, None)，消费方按 fail-closed 视为无权威性。
    """
    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        if sha.returncode != 0:
            return None, None
        st = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                            capture_output=True, text=True, timeout=10)
        return sha.stdout.strip() or None, bool(st.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return None, None


# ── json（机读：CI / Agent）───────────────────────────────────────────────────


def build_receipt(report, tier=1, strict=False, diff_range=None,
                  changed_points=0, scanned_classes=0,
                  config_source="auto", boundary_channels=None,
                  commit_sha=None, dirty=None):
    """构建收据信封（docs/design/guard-receipt-spec.md）：
    decision（门禁结论+原因码）/ provenance（数据来源）/ boundary（证据边界声明）/
    verified（§4 内容绑定：结论钉在项目 git 提交切面上，stale/dirty 即无权威性）。"""
    reason_codes = []
    if report.level == "DIRECT":
        reason_codes.append("direct_boundary_hit")
    if report.cross_service:
        reason_codes.append("cross_service_downstream_unanalyzed")
    if any(rc.is_entry for rc in report.changes):
        reason_codes.append("entry_inbound_unanalyzable")
    if strict and report.level == "DIRECT":
        gate = "block"
    elif reason_codes:
        gate = "warn"
    else:
        gate = "pass"
    not_analyzed = ["reflection_dynamic_dispatch"]
    if report.cross_service:
        not_analyzed.append("cross_service_downstream")
    verified = [{"check_id": "impact_analysis",
                 "subject": diff_range or "explicit --changed files",
                 "commit_sha": commit_sha, "dirty": dirty}]
    return {
        "tool": "impact-guard",
        "schema_version": 1,
        "decision": {"gate": gate, "reason_codes": reason_codes},
        "verified": verified,
        "provenance": {
            "tier": tier,
            "diff_range": diff_range,
            "changed_points": changed_points,
            "scanned_classes": scanned_classes,
            "config_source": config_source,
            "boundary_channels": {ch: len(qns)
                                  for ch, qns in (boundary_channels or {}).items()},
        },
        "boundary": {
            "degraded": ["tier1_class_level"] if tier == 1 else [],
            "not_analyzed": not_analyzed,
        },
    }


def _boundary_footer(report) -> list:
    """收据信封 boundary 的人读投影（render_text 末尾段）。"""
    r = getattr(report, "receipt", None)
    if not r:
        return []
    lines = ["── 证据边界 ──"]
    if "tier1_class_level" in r["boundary"]["degraded"]:
        lines.append("  分析精度: Tier 1 类级（import 反向索引）；"
                     "方法级证据需 Tier 2 图谱（--mode graph）")
    if "cross_service_downstream" in r["boundary"]["not_analyzed"]:
        lines.append(f"  未分析: 跨服务下游影响（{len(report.cross_service)} 个契约）"
                     f" → 需人工评估")
    if "reflection_dynamic_dispatch" in r["boundary"]["not_analyzed"]:
        lines.append("  结构盲区: 反射/动态代理/多态分发不在 import 索引内")
    return lines


def render_json(report, tier: int = 1) -> str:
    data = {
        "schema_version": 1,
        "tier": tier,
        "level": report.level,
        "cross_service": report.cross_service,
        "cross_service_contracts": report.cross_service_contracts,
        "warnings": report.warnings,
        "changes": [{
            "qualified_name": rc.change.qualified_name,
            "file_path": rc.change.file_path,
            "layer": rc.change.layer,
            "component_type": rc.change.component_type,
            "change_type": rc.change.change_type,
            "changed_methods": rc.change.changed_methods,
            "is_entry": rc.is_entry,
            "level": rc.level,
            "reasons": rc.reasons,
            "impact_count": len(rc.impacts),
            "impacts": [{
                "qualified_name": n.qualified_name, "layer": n.layer,
                "depth": n.depth, "path": n.path,
            } for n in rc.impacts],
            "regression_scope": rc.regression_scope,
        } for rc in report.changes],
    }
    if report.receipt:
        data["receipt"] = report.receipt
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── text（人读）───────────────────────────────────────────────────────────────


def render_text(report, tier: int = 1) -> str:
    lines = [f"影响分析 [Tier {tier}]，总级别 {LEVEL_ICONS[report.level]} {report.level}"]
    lines.append("")
    for rc in report.changes:
        c = rc.change
        icon = LEVEL_ICONS[rc.level]
        entry_mark = " · 入口组件" if rc.is_entry else ""
        methods_mark = f" · 方法: {', '.join(c.changed_methods)}" if c.changed_methods else ""
        lines.append(f"{icon} {c.qualified_name}"
                     f"（{c.layer}/{c.component_type} · {c.change_type}{entry_mark}{methods_mark}）")
        for r in rc.reasons:
            lines.append(f"    - {r}")
        if rc.impacts:
            shown = rc.impacts[:10]
            lines.append(f"    影响链（{len(rc.impacts)} 类，深度"
                         f" max {max(n.depth for n in rc.impacts)}）:")
            for n in shown:
                chain = " → ".join(_short(q) for q in n.path)
                lines.append(f"      d{n.depth} {n.qualified_name}  [{chain}]")
            if len(rc.impacts) > 10:
                lines.append(f"      ... 还有 {len(rc.impacts) - 10} 类")
        if rc.regression_scope:
            scope = ", ".join(_short(q) for q in rc.regression_scope[:8])
            more = f" (+{len(rc.regression_scope) - 8})" if len(rc.regression_scope) > 8 else ""
            lines.append(f"    回归范围: {scope}{more}")
        lines.append("")
    for w in report.warnings:
        lines.append(w)
    for qn, c in report.cross_service_contracts.items():
        eps = ", ".join(f"{e['http_method']} {e['path']}"
                        for e in c.get("endpoints", []))
        lines.append(f"🔗 跨服务契约: {_short(qn)} → {c['service']}"
                     + (f"（{eps}）" if eps else ""))
    lines.extend(_boundary_footer(report))
    return "\n".join(lines) + "\n"


# ── mermaid（PR 描述）────────────────────────────────────────────────────────


def _mm_id(qn: str) -> str:
    return "n" + re.sub(r"[^a-zA-Z0-9_]", "_", qn)


def render_mermaid(report) -> str:
    """graph RL + classDef 四色 + [CHANGED] 双线框；>20 节点折叠中跳。"""
    lines = ["flowchart RL"]
    lines.append("  classDef changed fill:#dc2626,color:#fff,stroke-width:3px")
    lines.append("  classDef direct fill:#dc2626,color:#fff")
    lines.append("  classDef indirect fill:#d97706,color:#fff")
    lines.append("  classDef warning fill:#ca8a04,color:#fff")
    lines.append("  classDef info fill:#16a34a,color:#fff")
    lines.append("  classDef entry fill:#7c3aed,color:#fff")

    node_count = 0
    MAX_NODES = 20
    for rc in report.changes:
        c = rc.change
        changed_id = _mm_id(c.qualified_name)
        node_count += 1
        entry_flag = " 🚪" if rc.is_entry else ""
        lines.append(f'  {changed_id}[["{_short(c.qualified_name)} [CHANGED]{entry_flag}"]]:::changed')

        for n in rc.impacts:
            if node_count >= MAX_NODES:
                hidden = sum(len(r.impacts) for r in report.changes) - (
                    node_count - 1 - sum(1 for r in report.changes))
                lines.append(f'  folded["… 另有节点已折叠（>20）"]:::info')
                lines.append("\n".join([""]))
                return _finish_mermaid(lines, report)
            nid = _mm_id(n.qualified_name)
            node_count += 1
            is_entry = " 🚪入口" if any(n.qualified_name in r.regression_scope
                                        and r.is_entry for r in report.changes) else ""
            cls = "entry" if n.qualified_name in _all_entries(report) else "info"
            label = f"{_short(n.qualified_name)}{is_entry}"
            lines.append(f'  {nid}["{label}"]:::{cls}')
            lines.append(f'  {nid} -->|d{n.depth}| {changed_id if n.depth == 1 else _mm_id(n.path[-2])}')

    return _finish_mermaid(lines, report)


def _all_entries(report) -> set:
    return {q for rc in report.changes if rc.is_entry
            for q in rc.regression_scope}


def _finish_mermaid(lines: list, report) -> str:
    lines.append("")
    lines.append(f"  %% 总级别: {report.level}；🔴直接/🟠间接/🟡/🟢；[CHANGED]=变更点（红双框）；🚪=框架入口")
    return "\n".join(lines) + "\n"
