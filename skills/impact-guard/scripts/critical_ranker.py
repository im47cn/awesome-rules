"""CriticalRanker — 直接/间接分级（grill 修订：避免门禁通胀）

| 🔴 DIRECT   | 变更点本身是出站/落点（http_exit/db_sink/cache_sink/mq_exit）| --strict 阻断 |
| 🟠 INDIRECT | 影响链 ≥1 跳抵达入站入口                                       | 告警 + 回归建议 |
| 🟡 WARNING  | 触及聚合根（domain entity）                                    | 不阻断 |
| 🟢 INFO     | 仅内部实现                                                     | 不阻断 |

影响方向（诚实区分）：入口组件变更 = 无法分析影响（图内无入边）+ regression_scope。
跨服务契约（@FeignClient / -client）→ 🔴 直接 + 强制告警"跨服务影响未分析"。
"""

from dataclasses import dataclass, field

from boundary_scanner import scan_boundary_hits

LEVEL_ORDER = {"INFO": 0, "WARNING": 1, "INDIRECT": 2, "DIRECT": 3}
LEVEL_ICONS = {"DIRECT": "🔴", "INDIRECT": "🟠", "WARNING": "🟡", "INFO": "🟢"}

ENTRY_CHANNELS = ("http_entry", "mq_entry", "job_entry")
EXIT_CHANNELS = ("http_exit", "mq_exit", "db_sink", "cache_sink")


@dataclass
class RankedChange:
    change: object                       # ChangePoint
    is_entry: bool = False               # 框架入口（inbound 不可见）
    level: str = "INFO"
    reasons: list[str] = field(default_factory=list)
    impacts: list = field(default_factory=list)       # inbound ImpactNode 列表
    regression_scope: list = field(default_factory=list)  # 入口的下游树 / 间接抵达的入口
    regression_paths: list = field(default_factory=list)  # 抵达入口的证据链


@dataclass
class ImpactReport:
    changes: list[RankedChange]
    level: str
    cross_service: list[str] = field(default_factory=list)   # 跨服务未分析告警
    cross_service_contracts: dict = field(default_factory=dict)  # v2b: {qn: {service, endpoints}}
    warnings: list[str] = field(default_factory=list)


def _max_level(levels: list[str]) -> str:
    return max(levels, key=lambda l: LEVEL_ORDER.get(l, 0)) if levels else "INFO"


class CriticalRanker:

    def __init__(self, config: dict, infos: dict):
        self.config = config
        self.infos = infos
        hits = config.get("boundary_hits")
        self.hits = hits if hits is not None else scan_boundary_hits(infos)
        self.entry_qn: dict[str, str] = {
            qn: ch for ch in ENTRY_CHANNELS for qn in self.hits.get(ch, [])
        }

    def rank_change(self, change, impacts: list, outbound_tree: list | None = None) -> RankedChange:
        """分级单个变更点。impacts=inbound 节点（入口组件时为空），
        outbound_tree=入口组件的下游树（regression_scope）。"""
        rc = RankedChange(change=change, impacts=impacts)
        qn = change.qualified_name
        reasons = []

        # 1. 入口组件：图内无入边 → 无法分析影响 + 回归范围（诚实区分）
        if qn in self.entry_qn:
            rc.is_entry = True
            rc.regression_scope = [n.qualified_name for n in (outbound_tree or [])]
            reasons.append(f"框架入口（{self.entry_qn[qn]}），inbound 不可见，"
                           f"给出回归范围而非影响分析")
            rc.level = "WARNING"
            rc.reasons = reasons
            return rc

        # 2. 出站/落点：变更点本身是 🔴 直接
        for ch in EXIT_CHANNELS:
            if qn in self.hits.get(ch, []):
                reasons.append(f"变更点是{ch}（出站/落点）")
        # 跨服务契约
        if qn in self.hits.get("http_exit", []) or _is_client_contract(qn):
            reasons.append("跨服务契约（@FeignClient / -client）")
        if reasons:
            rc.level = "DIRECT"
            rc.reasons = reasons
            return rc

        # 3. 间接抵达：inbound 链上存在入站入口
        entry_impacts = [n for n in impacts if n.qualified_name in self.entry_qn]
        if entry_impacts:
            rc.level = "INDIRECT"
            rc.regression_scope = sorted({n.qualified_name for n in entry_impacts})
            rc.regression_paths = [n.path for n in entry_impacts]
            reasons.append(f"影响链 {entry_impacts[0].depth} 跳抵达 "
                           f"{self.entry_qn[entry_impacts[0].qualified_name]}")

        # 4. 触及聚合根 → 至少 WARNING
        if change.component_type == "entity" or change.layer == "domain":
            if _max_level(["WARNING", rc.level]) == "WARNING":
                rc.level = "WARNING"
            reasons.append("触及聚合根/领域层")

        rc.reasons = reasons or ["仅内部实现变更"]
        return rc

    def rank(self, ranked: list[RankedChange]) -> ImpactReport:
        level = _max_level([rc.level for rc in ranked]) if ranked else "INFO"
        cross = [rc.change.qualified_name for rc in ranked
                 if any("跨服务" in r for r in rc.reasons)]
        warnings = []
        for rc in ranked:
            if rc.is_entry:
                warnings.append(f"{rc.change.qualified_name} 为框架入口，"
                                f"影响不可分析（回归范围 {len(rc.regression_scope)} 类）")
        if cross:
            warnings.append("⚠️ 跨服务影响未分析，需人工评估下游服务: "
                            + ", ".join(cross))
        return ImpactReport(changes=ranked, level=level,
                            cross_service=cross, warnings=warnings)


def _is_client_contract(qn: str) -> bool:
    """-client 包下的接口（GTSP 对外契约：xxx-client 模块）。"""
    return ".client." in qn or qn.endswith("Client")
