"""BoundaryScanner — --init：扫描注解/SDK 调用，生成 5 通道边界配置

边界模式（默认，对齐 DESIGN §2.4 矩阵）：
  入站入口（→ 回归范围）: http_entry / mq_entry / job_entry
  出站/落点（变更点=此 → 🔴 直接）: http_exit / db_sink / cache_sink / mq_exit
"""

from __future__ import annotations  # 兼容 Python 3.9：延迟求值 PEP 604 联合类型注解
import json
import re
from pathlib import Path

# 模式 → 匹配目标（annotation=类注解命中；call=源码含 SDK 调用特征）
DEFAULT_BOUNDARY_PATTERNS = {
    "http_entry": {"kind": "annotation", "patterns": ["RestController", "Controller"]},
    "mq_entry":   {"kind": "annotation", "patterns": ["RocketMQMessageListener", "KafkaListener"]},
    "job_entry":  {"kind": "annotation", "patterns": ["XxlJob"]},
    "http_exit":  {"kind": "annotation", "patterns": ["FeignClient"]},
    "mq_exit":    {"kind": "call", "patterns": ["rocketMQTemplate", "kafkaTemplate"]},
    "db_sink":    {"kind": "annotation", "patterns": ["Mapper"]},
    "cache_sink": {"kind": "call", "patterns": ["RedisUtil", "@CachePut", "@CacheEvict"]},
}

CHANNEL_TITLES = {
    "http_entry": "HTTP 入口", "mq_entry": "MQ 入口", "job_entry": "定时入口",
    "http_exit": "HTTP 出站（Feign）", "mq_exit": "MQ 出站",
    "db_sink": "DB 落点（Mapper）", "cache_sink": "缓存落点",
}


def scan_boundary_hits(infos: dict, patterns: dict | None = None) -> dict[str, list[str]]:
    """按模式扫描 {qn: FileInfo}，返回 {通道: [命中类 qn...]}。"""
    pats = patterns or DEFAULT_BOUNDARY_PATTERNS
    hits: dict[str, list[str]] = {}
    for channel, rule in pats.items():
        found = []
        for qn, info in infos.items():
            annos = info.get("annotations", [])
            if rule["kind"] == "annotation":
                if any(any(p in a for a in annos) for p in rule["patterns"]):
                    found.append(qn)
            else:  # call: 匹配 import（SDK 引用即视为出站调用面）
                imports = " ".join(info.get("imports", []))
                if any(p.split(".")[0] in imports for p in rule["patterns"]):
                    found.append(qn)
        if found:
            hits[channel] = sorted(found)
    return hits


def init_config(project_root: str, infos: dict,
                config_path: str | None = None) -> dict:
    """--init：生成 .impact-guard.json（含边界模式 + 实际命中清单）。"""
    root = Path(project_root)
    prefix = _infer_prefix(root, infos)
    hits = scan_boundary_hits(infos)
    config = {
        "project_package_prefix": prefix,
        "boundaries": {k: v["patterns"] for k, v in DEFAULT_BOUNDARY_PATTERNS.items()},
        "boundary_hits": hits,
        "highways": ["**Util", "**Assembler"],
        "ignore": ["**/test/**", "**/dto/**", "**/query/**"],
    }
    out = Path(config_path) if config_path else root / ".impact-guard.json"
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def _infer_prefix(root: Path, infos: dict) -> str:
    """从已有类的包名推断项目包前缀（最深公共包段）。"""
    packages = [info.get("package", "") for info in infos.values()]
    packages = [p for p in packages if p]
    if not packages:
        return ""
    segments = [p.split(".") for p in packages]
    common = []
    for i in range(min(len(s) for s in segments)):
        seg = {s[i] for s in segments}
        if len(seg) == 1:
            common.append(seg.pop())
        else:
            break
    # 保留到倒数第二段（最后一段通常是类所在的子包/层）
    return ".".join(common[:-1]) if len(common) > 2 else ".".join(common)
