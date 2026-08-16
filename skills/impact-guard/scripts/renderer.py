"""Renderer — text / json / mermaid 三态渲染"""

import json
import re

from critical_ranker import LEVEL_ICONS


def _short(qn: str) -> str:
    return qn.rsplit(".", 1)[-1] if "." in qn else qn


# ── json（机读：CI / Agent）───────────────────────────────────────────────────


def render_json(report, tier: int = 1) -> str:
    data = {
        "schema_version": 1,
        "tier": tier,
        "level": report.level,
        "cross_service": report.cross_service,
        "warnings": report.warnings,
        "changes": [{
            "qualified_name": rc.change.qualified_name,
            "file_path": rc.change.file_path,
            "layer": rc.change.layer,
            "component_type": rc.change.component_type,
            "change_type": rc.change.change_type,
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
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── text（人读）───────────────────────────────────────────────────────────────


def render_text(report, tier: int = 1) -> str:
    lines = [f"影响分析 [Tier {tier}]，总级别 {LEVEL_ICONS[report.level]} {report.level}"]
    lines.append("")
    for rc in report.changes:
        c = rc.change
        icon = LEVEL_ICONS[rc.level]
        entry_mark = " · 入口组件" if rc.is_entry else ""
        lines.append(f"{icon} {c.qualified_name}"
                     f"（{c.layer}/{c.component_type} · {c.change_type}{entry_mark}）")
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
