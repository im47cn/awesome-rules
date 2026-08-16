"""跨项目真实链路构建器 — HTTP/Feign 调用签名对齐（AH-C01/C04）。

证据来源（均为 doc-gen manifest 已有字段，无需读源码）：
  provider：各项目 adapter 层 controller.endpoints（路由声明）
  consumer：各项目 client 层 feignInterface.endpoints（调用声明，
            含 @FeignClient(path) 类级前缀拼接，doc-gen Phase2-A 产出）

匹配与置信度：
  HTTP confirmed — method + 归一化路径完全一致（路径变量段 {var} 统一为 {}），
              双侧证据齐全（consumer qn/调用签名 + provider controller/路由）
  HTTP inferred — 路由未命中，但 @FeignClient name 近似某项目 id → 项目级推断边
              （低置信度，AH-C04：不进入阻断级结论）
  MQ   confirmed — producer.channel == consumer.channel 精确匹配（topic 全局
              命名空间）；依赖方向与 HTTP 统一：订阅者(consumer)依赖发布者
              (producer)，evidence.provider=发布组件
  项目内调用（from == to）不算跨项目边，计入 internalCalls。
"""

import json
import re
from pathlib import Path


def normalize_path(path: str) -> str:
    """路由归一化：路径变量段统一为 {}、折叠重复斜杠、统一首 / 尾去 /"""
    p = re.sub(r"\{[^}]*\}", "{}", path or "")
    p = re.sub(r"/+", "/", p)
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def _load_domains(manifest_dir: Path) -> list[dict]:
    """读取 manifest 的 domains/*.json 分片（损坏文件跳过不阻断）"""
    d = Path(manifest_dir) / "domains"
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def build_provider_index(projects: list) -> dict:
    """构建 provider 路由索引。projects: [(project_id, manifest_dir)]

    → {(METHOD, norm_path): [provider...]}，同名路由多项目并存时一对多全记。
    """
    index: dict = {}
    for pid, mdir in projects:
        for domain in _load_domains(mdir):
            adapter = (domain.get("layers") or {}).get("adapter") or {}
            for comp in adapter.get("components", []):
                if comp.get("type") != "controller":
                    continue
                for ep in comp.get("endpoints", []):
                    key = (ep.get("method", "").upper(), normalize_path(ep.get("path", "")))
                    index.setdefault(key, []).append({
                        "project": pid,
                        "qualifiedName": comp.get("qualifiedName") or comp.get("className", ""),
                        "sourcePath": comp.get("sourcePath", ""),
                        "route": f'{ep.get("method", "")} {ep.get("path", "")}',
                    })
    return index


def _feign_name(annotations: list) -> str:
    """从类注解原文提取 @FeignClient(name="...")（GTSP 四属性之一）"""
    for a in annotations or []:
        m = re.search(r'@FeignClient\b[^(]*\([^)]*?\bname\s*=\s*"([^"]+)"', a)
        if m:
            return m.group(1)
    return ""


def _infer_target(feign_name: str, project_ids: list, from_pid: str) -> str:
    """@FeignClient name 与项目 id 近似匹配（如 demo-service → demo）"""
    if not feign_name:
        return ""
    for pid in project_ids:
        if pid == from_pid:
            continue
        if feign_name == pid or feign_name.startswith(pid + "-") or pid in feign_name:
            return pid
    return ""


def build_cross_project_edges(projects: list) -> dict:
    """构建跨项目边。projects: [(project_id, manifest_dir)]

    返回 {"edges": [...], "stats": {...}}；edges 每条含 confidence 与双侧证据。
    """
    provider_index = build_provider_index(projects)
    project_ids = [pid for pid, _ in projects]

    edges: list = []
    seen, inferred_seen = set(), set()
    internal_calls = 0
    unmatched = 0

    for pid, mdir in projects:
        for domain in _load_domains(mdir):
            client = (domain.get("layers") or {}).get("client") or {}
            for comp in client.get("components", []):
                if comp.get("type") != "feignInterface":
                    continue
                feign_name = _feign_name(comp.get("annotations"))
                consumer = {
                    "qualifiedName": comp.get("qualifiedName") or comp.get("className", ""),
                    "sourcePath": comp.get("sourcePath", ""),
                }
                for ep in comp.get("endpoints", []):
                    method = ep.get("method", "").upper()
                    path = ep.get("path", "")
                    norm = normalize_path(path)

                    # 项目内同名路由 = 项目内调用，不算跨项目边
                    all_providers = provider_index.get((method, norm), [])
                    cross_providers = [p for p in all_providers if p["project"] != pid]
                    if len(all_providers) > len(cross_providers):
                        internal_calls += 1

                    if cross_providers:
                        for prov in cross_providers:
                            ekey = (pid, prov["project"], method, norm)
                            if ekey in seen:
                                continue
                            seen.add(ekey)
                            edges.append({
                                "from": pid,
                                "to": prov["project"],
                                "type": "http",
                                "confidence": "confirmed",
                                "evidence": {
                                    "consumer": {**consumer,
                                                 "call": f"{method} {path}"},
                                    "provider": prov,
                                },
                            })
                        continue

                    # AH-C04：路由未命中 → 服务名近似推断（低置信度）
                    target = _infer_target(feign_name, project_ids, pid)
                    if target:
                        ikey = (pid, target, feign_name)
                        if ikey not in inferred_seen:
                            inferred_seen.add(ikey)
                            edges.append({
                                "from": pid,
                                "to": target,
                                "type": "http",
                                "confidence": "inferred",
                                "evidence": {
                                    "consumer": {**consumer,
                                                 "call": f"{method} {path}"},
                                    "provider": {"service": feign_name, "route": None},
                                },
                            })
                    else:
                        unmatched += 1

    # ── MQ 边：producer.channel × consumer.channel 精确匹配（全局命名空间）──
    mq_consumers: dict = {}   # channel -> [(pid, comp)]
    for pid, mdir in projects:
        for domain in _load_domains(mdir):
            for lname, layer in (domain.get("layers") or {}).items():
                for comp in layer.get("components", []):
                    for ch in comp.get("mqChannels", []):
                        if ch.get("role") == "consumer":
                            mq_consumers.setdefault(ch.get("channel", ""), []).append(
                                (pid, comp, ch))

    mq_edges = 0
    mq_seen = set()
    for pid, mdir in projects:
        for domain in _load_domains(mdir):
            for lname, layer in (domain.get("layers") or {}).items():
                for comp in layer.get("components", []):
                    for ch in comp.get("mqChannels", []):
                        if ch.get("role") != "producer":
                            continue
                        channel = ch.get("channel", "")
                        for cpid, ccomp, cch in mq_consumers.get(channel, []):
                            if cpid == pid:
                                internal_calls += 1
                                continue
                            ekey = (cpid, pid, "mq", channel)
                            if ekey in mq_seen:
                                continue
                            mq_seen.add(ekey)
                            mq_edges += 1
                            # 依赖方向与 HTTP 统一：订阅者(consumer)依赖发布者(provider)
                            edges.append({
                                "from": cpid,
                                "to": pid,
                                "type": "mq",
                                "confidence": "confirmed",
                                "evidence": {
                                    "consumer": {
                                        "qualifiedName": ccomp.get("qualifiedName")
                                                         or ccomp.get("className", ""),
                                        "sourcePath": ccomp.get("sourcePath", ""),
                                        "call": f"subscribe {channel} ({cch.get('via', '')})",
                                    },
                                    "provider": {
                                        "project": pid,
                                        "qualifiedName": comp.get("qualifiedName")
                                                         or comp.get("className", ""),
                                        "sourcePath": comp.get("sourcePath", ""),
                                        "route": f"publish {channel} ({ch.get('via', '')})",
                                    },
                                },
                            })

    edges.sort(key=lambda e: (e["confidence"] != "confirmed", e["from"], e["to"]))
    confirmed = sum(1 for e in edges if e["confidence"] == "confirmed")
    return {
        "schema_version": 1,
        "edges": edges,
        "stats": {
            "confirmed": confirmed,
            "inferred": len(edges) - confirmed,
            "httpEdges": confirmed - mq_edges,
            "mqEdges": mq_edges,
            "internalCalls": internal_calls,
            "unmatchedConsumers": unmatched,
        },
    }
