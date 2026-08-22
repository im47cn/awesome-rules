"""ImpactScanner — Tier 1 fallback：import 反向索引 + 双向 BFS

精度口径（DESIGN §2.2 grill 修正）：@Autowired/Feign 有 import，Tier 1 能覆盖；
真盲区（反射/动态代理/多态分发）Tier 2 图谱同样盲——差异是粒度（类 vs 方法），非盲区。
"""

from dataclasses import dataclass, field

from _compat import JavaScanner


@dataclass
class ImpactNode:
    """一个受影响方：深度 + 证据链（变更点 → ... → 该类）"""
    qualified_name: str
    layer: str = ""
    component_type: str = ""
    depth: int = 0
    path: list[str] = field(default_factory=list)


class ImpactScanner:

    def __init__(self, project_root: str, config: dict):
        self.root = project_root
        self.config = config
        self.infos: dict[str, dict] = {}        # qn -> FileInfo
        self.reverse_index: dict[str, set] = {} # 被依赖 qn -> {依赖方 qn}（inbound 边）
        self.forward_index: dict[str, set] = {} # qn -> {它依赖的 qn}（outbound 边）
        self._layer_cache: dict[str, tuple] = {}

    def scan(self) -> dict[str, dict]:
        """扫描全项目，建立类索引与双向 import 索引。"""
        files = JavaScanner(self.root).scan_java_files()
        prefix = self.config.get("project_package_prefix", "")
        for f in files:
            qn = f.get("qualifiedName", "")
            if not qn:
                continue
            if prefix and not qn.startswith(prefix):
                continue
            self.infos[qn] = f
        for qn, info in self.infos.items():
            deps = {imp.strip().rstrip(";") for imp in info.get("imports", [])
                    if imp.strip().rstrip(";") in self.infos}
            self.forward_index[qn] = deps
            for dep in deps:
                self.reverse_index.setdefault(dep, set()).add(qn)
        return self.infos

    def _ignored(self, qn: str) -> bool:
        import fnmatch
        for pattern in self.config.get("ignore", []):
            if fnmatch.fnmatch(qn, pattern):
                return True
        return False

    def propagate_inbound(self, change_qn: str, depth: int = 3) -> list[ImpactNode]:
        """谁调用了我（inbound）：沿 reverse_index BFS。"""
        return self._bfs(change_qn, depth, self.reverse_index, "inbound")

    def propagate_outbound(self, start_qn: str, depth: int = 3) -> list[ImpactNode]:
        """我调用了谁（outbound）：入口组件的回归范围（下游树）。"""
        return self._bfs(start_qn, depth, self.forward_index, "outbound")

    def _bfs(self, start: str, depth: int, index: dict, direction: str) -> list[ImpactNode]:
        result: dict[str, ImpactNode] = {}
        frontier = [(start, [start])]
        visited = {start}
        for hop in range(1, depth + 1):
            next_frontier = []
            for qn, path in frontier:
                for nb in sorted(index.get(qn, ())):
                    if nb in visited or self._ignored(nb):
                        continue
                    visited.add(nb)
                    layer, comp_type = self._layer_of(nb)
                    result[nb] = ImpactNode(
                        qualified_name=nb, layer=layer, component_type=comp_type,
                        depth=hop, path=path + [nb])
                    next_frontier.append((nb, path + [nb]))
            frontier = next_frontier
            if not frontier:
                break
        return sorted(result.values(), key=lambda n: (n.depth, n.qualified_name))

    def _layer_of(self, qn: str) -> tuple[str, str]:
        if qn not in self._layer_cache:
            from generator.layers import LayerIdentifier
            result = LayerIdentifier().classify(self.infos.get(qn, {}))
            self._layer_cache[qn] = result if result else ("", "")
        return self._layer_cache[qn]
