"""DocManifest 快照对比引擎 — 架构演进 delta（借鉴 archify delta 的三机制）

核心设计（对应 docs/design/doc-gen-contract-design.md §8）：
1. 字段分组 → 状态分级：变化分类决定 added/removed/changed/moved，不是所有变化等权
2. presentation 与语义分离：description 等 Javadoc 噪声单独报告，不计入 summary
3. stable ID 对齐 + 诚实失败：qualifiedName 是扫描产物天然稳定 ID；
   两份快照 schema_version 不相等时由 CLI 层拒绝（exit 2）

对外入口:
  load_snapshot(manifest_dir) -> dict          # 分片目录 → 展平快照
  diff_snapshots(base, head) -> dict           # 完整 delta receipt
"""

import json
from pathlib import Path


# ── canonical 归一化（key 顺序无关的深度比较基础）─────────────────────────────


def _canonical(value):
    """递归归一化：dict 按 key 排序、list 排序（列表视为集合语义）。"""
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonical(v) for v in sorted(value, key=lambda x: json.dumps(_canonical(x), ensure_ascii=False))]
    return value


def _equal(left, right) -> bool:
    return _canonical(left) == _canonical(right)


# ── 字段分组（信噪比分级的单一真相源）────────────────────────────────────────

COMPONENT_FIELDS = {
    "semantic":  ["type", "qualifiedName"],   # 架构事实：组件类型/身份
    "lifecycle": ["deprecated"],              # 废弃翻转是治理事件
    "behavior":  ["methods", "fields", "endpoints", "interfaces"],  # 中权重
    "presentation": ["description", "sublabel", "tag"],  # Javadoc 噪声，隔离
}
AGGREGATE_FIELDS = {
    "semantic": ["kind", "rootEntity", "entities", "valueObjects",
                 "domainServices", "domainEvents"],
    "presentation": ["description"],
}
_CHANGED_GROUPS = ("semantic", "lifecycle", "behavior")


def _field_group_changes(base, head, groups) -> tuple[list[str], list[str]]:
    """返回 (发生变化的分组名列表, 变化字段路径列表)"""
    classifications, changed_fields = [], []
    for group, fields in groups.items():
        changed = [f for f in fields
                   if not _equal(base.get(f), head.get(f))]
        if changed:
            classifications.append(group)
            changed_fields.extend(f"/{f}" for f in changed)
    return sorted(classifications), sorted(changed_fields)


def _status_for(classifications: list[str]) -> str:
    if any(g in _CHANGED_GROUPS for g in classifications):
        return "changed"
    if "presentation" in classifications:
        return "presentation-changed"
    return "same"


# ── 快照加载与展平 ────────────────────────────────────────────────────────────


def load_snapshot(manifest_dir) -> dict:
    """分片目录 → 展平快照。

    结构: {schema_version, evidence, components: {qid: {...}},
           aggregates: {(domain,name): {...}}, tables: {name: {...}},
           state_machines: {name: {...}}, cross_domain: {key: {...}},
           openapi_endpoints: {(method,path)}}
    """
    md = Path(manifest_dir)

    def _read(name):
        p = md / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    index = _read("index.json")
    if index is None:
        raise FileNotFoundError(f"缺少 index.json: {md}")

    # 组件展平：qualifiedName → {**component, domain, layer}
    components = {}
    aggregates = {}
    domains_dir = md / "domains"
    if domains_dir.is_dir():
        for df in sorted(domains_dir.glob("*.json")):
            domain = json.loads(df.read_text(encoding="utf-8"))
            dname = domain["name"]
            for layer_name, layer in (domain.get("layers") or {}).items():
                for c in layer.get("components", []):
                    qid = c.get("qualifiedName") or c.get("className") or ""
                    if qid:
                        components[qid] = {**c, "_domain": dname, "_layer": layer_name}
                for agg in layer.get("aggregates", []):
                    aggregates[(dname, layer_name, agg["name"])] = agg

    # 数据库 / 状态机 / 跨域
    tables = {t["name"]: t for t in (_read("database.json") or {}).get("tables", [])}
    state_machines = {sm["name"]: sm for sm in (_read("state-machines.json") or [])}
    cross_domain = {
        f"{d['fromDomain']}→{d['toDomain']}:{d['type']}": d
        for d in (_read("cross-domain.json") or [])
    }

    # OpenAPI 端点集合（method+path 粒度）；无 api-spec.json → None（维度 skipped）
    api_spec = _read("api-spec.json")
    openapi_endpoints = None
    if api_spec is not None:
        spec = api_spec.get("default", api_spec)  # 兼容 {"default": spec} 包装
        openapi_endpoints = {
            (method.upper(), path)
            for path, ops in (spec.get("paths") or {}).items()
            for method in ops if isinstance(ops[method], dict)
        }

    meta = _read("meta.json") or {}
    return {
        "manifest_dir": str(md),
        "schema_version": index.get("schema_version"),
        "project": index.get("project") or {},
        "evidence": meta.get("evidence") or {},
        "components": components,
        "aggregates": aggregates,
        "tables": tables,
        "state_machines": state_machines,
        "cross_domain": cross_domain,
        "openapi_endpoints": openapi_endpoints,
    }


# ── 组件维度（含 moved 两层启发式）───────────────────────────────────────────


def diff_components(base_comps: dict, head_comps: dict) -> list[dict]:
    """组件对比。moved 判定：
    1. qualifiedName 相同 + (domain,layer) 变 → moved（确定）
    2. className 恒等 + 一端 removed 一端 added（包重命名）→ moved + inferred: true
       多对一时保守回退为 added/removed（不猜测）
    """
    changes = []
    removed, added = {}, {}

    for qid in sorted(set(base_comps) | set(head_comps)):
        b, h = base_comps.get(qid), head_comps.get(qid)
        if b and not h:
            removed[qid] = b
        elif h and not b:
            added[qid] = h
        else:
            groups, fields = _field_group_changes(b, h, COMPONENT_FIELDS)
            status = _status_for(groups)
            if b["_domain"] != h["_domain"] or b["_layer"] != h["_layer"]:
                # 迁移 + 字段同时变化：以 moved 为主状态，字段变化分组合并不丢失
                cls = ["position"] + [g for g in groups if g != "presentation"]
                changes.append(_entry(qid, b, h, "moved", cls,
                                      [f"{b['_domain']}/{b['_layer']} → "
                                       f"{h['_domain']}/{h['_layer']}"] + fields))
            elif status != "same":
                changes.append(_entry(qid, b, h, status, groups, fields))

    # 启发式 2：className 一一对应的 removed/added 对 → moved(inferred)
    rem_by_cn = _group_by_class_name(removed)
    add_by_cn = _group_by_class_name(added)
    for cn in sorted(set(rem_by_cn) & set(add_by_cn)):
        if len(rem_by_cn[cn]) == 1 and len(add_by_cn[cn]) == 1:  # 严格一一对应
            rq, aq = rem_by_cn[cn][0], add_by_cn[cn][0]
            b, h = removed.pop(rq), added.pop(aq)
            changes.append(_entry(aq, b, h, "moved", ["position"], [f"{rq} → {aq}"],
                                  inferred=True))
    changes.extend(_entry(q, removed[q], None, "removed", ["semantic"], [])
                   for q in sorted(removed))
    changes.extend(_entry(q, None, added[q], "added", ["semantic"], [])
                   for q in sorted(added))
    return changes


def _group_by_class_name(comps: dict) -> dict:
    groups = {}
    for qid, c in comps.items():
        groups.setdefault(c.get("className", qid), []).append(qid)
    return groups


def _entry(key, base, head, status, classifications, fields, inferred=False) -> dict:
    e = {
        "id": key,
        "className": (head or base).get("className", key),
        "status": status,
        "classifications": classifications,
        "changedFields": fields,
    }
    loc = (head or base)
    if status != "removed":
        e["location"] = f"{loc.get('_domain', '?')}/{loc.get('_layer', '?')}"
    if status != "added":
        e["wasLocation"] = f"{base.get('_domain', '?')}/{base.get('_layer', '?')}"
    if inferred:
        e["inferred"] = True
    return e


# ── 其余维度 ─────────────────────────────────────────────────────────────────


def diff_keyed(base_map: dict, head_map: dict, fields: dict,
               describe) -> list[dict]:
    """通用 keyed 集合对比（aggregates/tables/state_machines/cross_domain 共用）。"""
    changes = []
    for key in sorted(set(base_map) | set(head_map), key=str):
        b, h = base_map.get(key), head_map.get(key)
        if b and not h:
            changes.append(describe(key, b, None, "removed", ["semantic"], []))
        elif h and not b:
            changes.append(describe(key, None, h, "added", ["semantic"], []))
        else:
            groups, fields_changed = _field_group_changes(b, h, fields)
            status = _status_for(groups)
            if status != "same":
                changes.append(describe(key, b, h, status, groups, fields_changed))
    return changes


def diff_sets(base_set, head_set) -> tuple[set, set]:
    """集合语义 diff：返回 (added, removed)"""
    if base_set is None or head_set is None:
        return set(), set()
    return head_set - base_set, base_set - head_set


def diff_tables(base_tables: dict, head_tables: dict) -> list[dict]:
    """表级对比，列/索引变化内嵌。"""
    def describe(name, b, h, status, groups, fields):
        e = {"id": name, "status": status, "classifications": groups,
             "changedFields": fields}
        if status == "changed":
            bcols = {c["name"]: c for c in b.get("columns", [])}
            hcols = {c["name"]: c for c in h.get("columns", [])}
            e["columnsAdded"] = sorted(set(hcols) - set(bcols))
            e["columnsRemoved"] = sorted(set(bcols) - set(hcols))
            e["columnsChanged"] = sorted(
                n for n in set(bcols) & set(hcols) if not _equal(bcols[n], hcols[n]))
        return e
    return diff_keyed(base_tables, head_tables, {"semantic": ["columns", "indexes"]},
                      describe)


def diff_state_machines(base_sms: dict, head_sms: dict) -> list[dict]:
    """状态机对比：状态/转换集合变化 + 新增质量 issue。"""
    def describe(name, b, h, status, groups, fields):
        e = {"id": name, "status": status, "classifications": groups,
             "changedFields": fields}
        if status == "changed":
            bt = {(t.get("source"), t.get("target"), t.get("event"))
                  for t in b.get("transitions", [])}
            ht = {(t.get("source"), t.get("target"), t.get("event"))
                  for t in h.get("transitions", [])}
            e["transitionsAdded"] = sorted(map(list, ht - bt))
            e["transitionsRemoved"] = sorted(map(list, bt - ht))
            bi = {(i.get("type"), i.get("message")) for i in b.get("issues", [])}
            hi = {(i.get("type"), i.get("message")) for i in h.get("issues", [])}
            e["newIssues"] = sorted(map(list, hi - bi))
        return e
    return diff_keyed(base_sms, head_sms,
                      {"semantic": ["framework", "states", "transitions"],
                       "presentation": ["sourceClass", "managedEnum"]},
                      describe)


# ── 汇总 ─────────────────────────────────────────────────────────────────────


_SUMMARY_STATUSES = ("added", "removed", "changed", "moved")


def _summarize(changes: list[dict]) -> dict:
    s = {st: 0 for st in _SUMMARY_STATUSES}
    for c in changes:
        if c["status"] in s:
            s[c["status"]] += 1
    return s


def diff_snapshots(base: dict, head: dict) -> dict:
    """完整 delta receipt。presentation-changed 不计入 summary（信噪比契约）。"""
    changes = {
        "components": diff_components(base["components"], head["components"]),
        "aggregates": diff_keyed(
            base["aggregates"], head["aggregates"], AGGREGATE_FIELDS,
            lambda key, b, h, st, g, f: {"id": f"{key[0]}/{key[2]}",
                                         "status": st, "classifications": g,
                                         "changedFields": f}),
        "tables": diff_tables(base["tables"], head["tables"]),
        "stateMachines": diff_state_machines(base["state_machines"],
                                             head["state_machines"]),
        "crossDomain": diff_keyed(
            base["cross_domain"], head["cross_domain"],
            {"semantic": ["evidence"], "presentation": ["description"]},
            lambda key, b, h, st, g, f: {"id": key, "status": st,
                                         "classifications": g, "changedFields": f}),
    }

    oapi_added, oapi_removed = diff_sets(base["openapi_endpoints"],
                                         head["openapi_endpoints"])

    return {
        "schema_version": 1,
        "base": {"revision": base["evidence"].get("revision"),
                 "generatedAt": base["evidence"].get("generatedAt"),
                 "manifestDir": base["manifest_dir"]},
        "head": {"revision": head["evidence"].get("revision"),
                 "generatedAt": head["evidence"].get("generatedAt"),
                 "manifestDir": head["manifest_dir"]},
        "summary": {
            "components": _summarize(changes["components"]),
            "aggregates": _summarize(changes["aggregates"]),
            "tables": _summarize(changes["tables"]),
            "stateMachines": _summarize(changes["stateMachines"]),
            "crossDomain": _summarize(changes["crossDomain"]),
            "openapi": {"added": len(oapi_added), "removed": len(oapi_removed)},
        },
        "changes": changes,
        "openapi": {"added": sorted([m, p] for m, p in oapi_added),
                    "removed": sorted([m, p] for m, p in oapi_removed)},
    }


# ── Markdown 渲染（PR comment 友好）───────────────────────────────────────────

_DIM_TITLES = {
    "components": "组件", "aggregates": "聚合", "tables": "数据表",
    "stateMachines": "状态机", "crossDomain": "跨域依赖", "openapi": "API 端点",
}


def _short(revision) -> str:
    return revision[:12] if revision else "?"


def render_markdown(receipt: dict) -> str:
    """渲染 delta receipt 为 Markdown 摘要（presentation-changed 默认折叠不列）。"""
    s = receipt["summary"]
    lines = [
        "# 架构演进 Delta",
        "",
        f"**基准** `{_short(receipt['base']['revision'])}` → "
        f"**当前** `{_short(receipt['head']['revision'])}`",
        "",
        "| 维度 | added | removed | changed | moved |",
        "| --- | --- | --- | --- | --- |",
    ]
    for dim, title in _DIM_TITLES.items():
        d = s[dim]
        if dim == "openapi":
            lines.append(f"| {title} | {d['added']} | {d['removed']} | - | - |")
        else:
            lines.append(
                f"| {title} | {d['added']} | {d['removed']} | {d['changed']} | {d['moved']} |")
    lines.append("")

    for dim in ("components", "aggregates", "tables", "stateMachines", "crossDomain"):
        entries = [c for c in receipt["changes"][dim] if c["status"] != "presentation-changed"]
        if not entries:
            continue
        lines.append(f"## {_DIM_TITLES[dim]}（{len(entries)}）")
        lines.append("")
        for c in entries:
            flag = " *(inferred)*" if c.get("inferred") else ""
            detail = ""
            if c["status"] == "moved" and c["changedFields"]:
                detail = f" — {c['changedFields'][0]}"
            elif c["status"] == "changed":
                detail = f" — {', '.join(c['changedFields'])}"
            loc = c.get("location") or c.get("wasLocation", "")
            lines.append(f"- **{c['status']}** `{c['id']}`{flag}"
                         + (f"（{loc}）" if loc else "") + detail)
        lines.append("")

    oa = receipt["openapi"]
    if oa["added"] or oa["removed"]:
        lines.append("## API 端点")
        lines.append("")
        for m, p in oa["added"]:
            lines.append(f"- **added** `{m} {p}`")
        for m, p in oa["removed"]:
            lines.append(f"- **removed** `{m} {p}`")
        lines.append("")

    total = sum(sum(v.values()) for v in s.values())
    lines.append(f"> 共 {total} 处变化。presentation-changed（描述文本）未计入。")
    return "\n".join(lines) + "\n"
