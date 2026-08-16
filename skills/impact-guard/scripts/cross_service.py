"""CrossService — 跨服务传播（v2b）：Feign 契约提取 + 下游追踪 Cypher

变更点命中 @FeignClient（http_exit）时：
1. quick 模式：提取契约明细（下游服务名 + 端点 path + Java 方法）——
   跨服务告警从"未分析"升级为"契约清单已提取，下游评估范围明确"
2. graph 模式：生成 cross-repo Cypher（在 cross-repo-intelligence 索引的
   Route 节点中匹配 path，定位下游服务的暴露路由）

方法级注解（@PostMapping）是 Feign 特定需求，不进通用 JavaScanner（YAGNI），
本模块从源文件小正则提取。
"""

import re
from pathlib import Path

FEIGN_CLIENT_RE = re.compile(r'@FeignClient\s*\(([^)]*)\)', re.S)
FEIGN_NAME_RE = re.compile(r'(?:name|value|url)\s*=\s*"([^"]+)"|"([^"]+)"')
MAPPING_ANNOTATIONS = {
    "PostMapping": "POST", "GetMapping": "GET", "PutMapping": "PUT",
    "DeleteMapping": "DELETE", "PatchMapping": "PATCH",
    "RequestMapping": "REQUEST",
}
MAPPING_RE = re.compile(
    r'@(Post|Get|Put|Delete|Patch|Request)Mapping\s*(?:\(([^)]*)\))?')
MAPPING_PATH_RE = re.compile(r'(?:value|path)\s*=\s*"([^"]+)"|"([^"]+)"')
METHOD_DECL_RE = re.compile(
    r'[\w<>\[\],\s]+\s(\w+)\s*\([^)]*\)\s*;?', re.S)


def extract_feign_contracts(project_root: str, info: dict,
                            only_methods: list[str] | None = None) -> dict | None:
    """提取一个 @FeignClient 接口的跨服务契约。

    返回 {service, endpoints: [{http_method, path, java_method}]}；
    非Feign接口或源文件不可读 → None。
    only_methods: v2 方法级联动——只保留这些 Java 方法的端点（None=全部）。
    """
    source_path = info.get("sourcePath") or info.get("filePath", "")
    if not source_path:
        return None
    src = Path(project_root) / source_path
    if not src.exists():
        src = Path(source_path)  # 兼容绝对路径
        if not src.exists():
            return None
    content = src.read_text(encoding="utf-8")

    fc = FEIGN_CLIENT_RE.search(content)
    if not fc:
        return None
    name_m = FEIGN_NAME_RE.search(fc.group(1))
    service = (name_m.group(1) or name_m.group(2)) if name_m else "?"

    endpoints = []
    for m in MAPPING_RE.finditer(content):
        http_method = MAPPING_ANNOTATIONS[f"{m.group(1)}Mapping"]
        path_args = m.group(2) or ""
        pm = MAPPING_PATH_RE.search(path_args)
        path = (pm.group(1) or pm.group(2)) if pm else ""
        # 映射注解之后的第一个方法声明 = 该端点的 Java 方法
        tail = content[m.end():m.end() + 300]
        dm = METHOD_DECL_RE.search(tail)
        java_method = dm.group(1) if dm else "?"
        if only_methods and java_method not in only_methods:
            continue
        endpoints.append({"http_method": http_method, "path": path,
                          "java_method": java_method})
    if only_methods and not endpoints:
        return {"service": service, "endpoints": [], "note":
                f"变更方法 {only_methods} 未命中契约端点（契约级变更可能在类头）"}
    return {"service": service, "endpoints": endpoints}


def build_cross_service_cypher(contracts: list[dict]) -> str | None:
    """契约 path → 下游服务 Route 匹配 Cypher（cross-repo-intelligence 索引）。"""
    paths = sorted({e["path"] for c in contracts for e in c["endpoints"]
                    if e.get("path")})
    if not paths:
        return None
    path_list = ", ".join(f'"{p}"' for p in paths)
    services = sorted({c["service"] for c in contracts})
    return f"""// ── v2 跨服务传播：变更 Feign 契约 → 下游服务暴露路由 ──
// 目标服务（@FeignClient）: {", ".join(services)}
// 前置：目标服务仓库已 index_repository(mode=cross-repo-intelligence)
MATCH (route:Route)
WHERE route.path IN [{path_list}]
OPTIONAL MATCH (svc {{id: route.project}})-[:EXPOSES]->(route)
RETURN route.project            AS downstream_project,
       route.path               AS contract_path,
       route.methods            AS http_methods,
       route.qualified_name     AS handler
ORDER BY downstream_project, contract_path;"""
