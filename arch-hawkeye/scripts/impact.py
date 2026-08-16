"""跨项目变更影响分析（AH-C03）。

输入：聚合 manifest 目录（aggregate 产物）+ 变更实体（类名 / 限定名 / 路由 "METHOD /path"）
图：  跨项目边（cross-project.json，confirmed/inferred，Phase 2 产物）
      + 项目内依赖边（component.deps = import 的本项目 qn，反向邻接）
分级：🔴 direct   跨项目边直接命中（变更 provider → 受影响的跨项目 consumer）
      🟠 indirect 项目内反向依赖链（BFS，按跳数裁剪）
语义对齐 impact-guard（同仓库技能）：只对 confirmed 边计入"直接"，inferred 降级标注。
"""

import json
import re
from collections import deque
from pathlib import Path

from crossproject import normalize_path

_ROUTE_RE = re.compile(r"^(GET|POST|PUT|DELETE|PATCH|REQUEST|\*)\s+(/\S*)$", re.IGNORECASE)


# ── 图加载 ────────────────────────────────────────────────────────────────────


def _iter_components(domain_data: dict):
    """产出 (domain, layer, comp)：层组件 + 聚合内部组件（根/实体/VO/服务/事件）"""
    dname = domain_data.get("name", "")
    for lname, layer in (domain_data.get("layers") or {}).items():
        for comp in layer.get("components", []):
            yield dname, lname, comp
        for agg in layer.get("aggregates", []):
            if agg.get("rootEntity"):
                yield dname, lname, agg["rootEntity"]
            for key in ("entities", "valueObjects", "domainServices", "domainEvents"):
                for c in agg.get(key, []):
                    yield dname, lname, c


def load_graph(agg_dir) -> dict:
    """加载聚合图谱。agg_dir = aggregate 输出目录（含 doc-manifest/）"""
    dm = Path(agg_dir) / "doc-manifest"
    g = {
        "components": {},   # qn -> {project, className, type, layer, domain, sourcePath}
        "by_class": {},     # className -> [qn...]
        "rev_deps": {},     # 被依赖 qn -> [依赖者 qn...]（component.deps 反向）
        "routes": {},       # (METHOD, norm_path) -> provider qn
        "cross_edges": [],  # cross-project.json edges
    }

    projects_root = dm / "projects"
    proj_dirs = sorted(p for p in projects_root.iterdir() if p.is_dir()) \
        if projects_root.is_dir() else []
    for pd in proj_dirs:
        pid = pd.name
        for f in sorted(pd.glob("*.json")):
            try:
                domain = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for dname, lname, comp in _iter_components(domain):
                qn = comp.get("qualifiedName") or comp.get("className", "")
                if not qn:
                    continue
                g["components"][qn] = {
                    "project": pid, "domain": dname, "layer": lname,
                    "className": comp.get("className", ""),
                    "type": comp.get("type", ""),
                    "sourcePath": comp.get("sourcePath", ""),
                }
                g["by_class"].setdefault(comp.get("className", ""), []).append(qn)
                for dep in comp.get("deps", []):
                    g["rev_deps"].setdefault(dep, []).append(qn)
                if comp.get("type") == "controller":
                    for ep in comp.get("endpoints", []):
                        key = (ep.get("method", "").upper(),
                               normalize_path(ep.get("path", "")))
                        g["routes"][key] = qn

    cp_file = dm / "cross-project.json"
    if cp_file.exists():
        try:
            g["cross_edges"] = json.loads(
                cp_file.read_text(encoding="utf-8")).get("edges", [])
        except (json.JSONDecodeError, OSError):
            pass
    return g


# ── 实体定位 ──────────────────────────────────────────────────────────────────


def locate_entity(g: dict, entity: str):
    """定位变更实体：路由 → 类名精确 → 限定名包含。返回 (qn, how) 或 (None, 错误)"""
    route_m = _ROUTE_RE.match(entity.strip())
    if route_m:
        key = (route_m.group(1).upper(), normalize_path(route_m.group(2)))
        if key in g["routes"]:
            return g["routes"][key], f"route {entity}"
        return None, f"路由未命中任何 provider: {entity}"

    qns = g["by_class"].get(entity.strip())
    if qns:
        return qns[0], "className" if len(qns) == 1 else f"className（{len(qns)} 个同名，取首个）"

    tail_hits = [qn for qn in g["components"] if qn.endswith("." + entity.strip())]
    if len(tail_hits) == 1:
        return tail_hits[0], "qualifiedName"

    for qn in g["components"]:
        if entity.strip() in qn:
            return qn, "qualifiedName（包含匹配）"
    return None, f"未找到实体: {entity}"


# ── 影响分析 ──────────────────────────────────────────────────────────────────


def analyze_impact(g: dict, entity: str, max_hops: int = 3) -> dict:
    """变更实体的影响面：🔴 direct（跨项目边）+ 🟠 indirect（项目内反向依赖 BFS）"""
    qn, how = locate_entity(g, entity)
    if qn is None:
        return {"ok": False, "error": how}

    info = g["components"][qn]

    # 🔴 direct：跨项目边中 provider 侧命中（变更被依赖方 → 受影响的 consumer）
    direct = []
    for edge in g["cross_edges"]:
        prov = edge.get("evidence", {}).get("provider", {})
        if prov.get("qualifiedName") == qn:
            consumer = edge["evidence"]["consumer"]
            direct.append({
                "project": edge["from"],
                "entity": consumer.get("qualifiedName", ""),
                "via": consumer.get("call", ""),
                "confidence": edge.get("confidence", ""),
            })
    direct.sort(key=lambda d: d["confidence"] != "confirmed")

    # 🟠 indirect：项目内反向依赖 BFS（谁 import 了我 → 谁又 import 了它）
    indirect = []
    visited = {qn}
    queue = deque([(qn, 0)])
    while queue:
        cur, hops = queue.popleft()
        if hops >= max_hops:
            continue
        for dependent in g["rev_deps"].get(cur, []):
            if dependent in visited:
                continue
            visited.add(dependent)
            d_info = g["components"].get(dependent, {})
            indirect.append({
                "project": d_info.get("project", "?"),
                "entity": dependent,
                "hops": hops + 1,
                "via": "deps",
            })
            queue.append((dependent, hops + 1))

    return {
        "ok": True,
        "entity": {"qualifiedName": qn, **info, "matchedBy": how},
        "direct": direct,
        "indirect": indirect,
        "stats": {"direct": len(direct),
                  "directConfirmed": sum(1 for d in direct if d["confidence"] == "confirmed"),
                  "indirect": len(indirect)},
    }


def render_text(result: dict) -> str:
    """终端渲染（🔴/🟠 分级，对齐 impact-guard 语义）"""
    if not result.get("ok"):
        return f"❌ {result.get('error', '定位失败')}"
    e = result["entity"]
    s = result["stats"]
    lines = [f"🎯 变更实体: {e['qualifiedName']}",
             f"   {e.get('project')} / {e.get('domain')} 域 / {e.get('layer')} 层"
             f"（匹配方式: {e.get('matchedBy')}）", ""]
    lines.append(f"🔴 直接影响（跨项目）: {s['direct']}"
                 f"（confirmed {s['directConfirmed']} / inferred {s['direct'] - s['directConfirmed']}）")
    for d in result["direct"]:
        flag = "✅" if d["confidence"] == "confirmed" else "⚠️ "
        lines.append(f"   {flag} [{d['project']}] {d['entity']} ← {d['via']}")
    lines.append(f"🟠 间接影响（项目内依赖链）: {s['indirect']}")
    for d in result["indirect"]:
        lines.append(f"   [{d['project']}] {d['entity']}（{d['hops']} 跳, via {d['via']}）")
    return "\n".join(lines)
