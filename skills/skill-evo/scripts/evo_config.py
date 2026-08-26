#!/usr/bin/env python3
"""evo_config — skill-evo 配置读取

配置文件 ~/.config/ar/skill-evo/config.toml（可选，零配置即可用）。
Python 3.9 无 tomllib，且本技能只需扁平 KV + 字符串列表，内置极简解析器
（不支持嵌套表/多行值，够用即可，见 KISS）。
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULTS = {
    # 总开关（hook 侧另有 AR_SKILL_EVO_ENABLED 环境变量开关）
    "enabled": True,
    # 会话消息数低于该值视为无总结价值，跳过
    "min_messages": 6,
    # 送入 LLM 的 transcript 视图字符上限
    "max_transcript_chars": 60000,
    # omp 会话根目录（其下按 cwd-slug 分子目录）
    "omp_sessions_dir": "~/.omp/agent/sessions",
    # omp 搭车扫描回看天数（按文件名时间戳过滤）
    "omp_lookback_days": 7,
    # 单次 run 最多处理的 omp 会话数（控制后台 LLM 调用成本）
    "omp_max_per_run": 5,
    # headless 总结用的 CLI
    "claude_bin": "claude",
    # 单次 LLM 调用超时（秒），超时丢弃本次（幂等，下次会话再来）
    "claude_timeout": 180,
    # 只处理 cwd 位于这些目录下的会话（路径逃逸护栏）
    "scope_dirs": ["~/sources"],
    # 运行数据根目录（proposals/ state.json logs/ 均在其下）
    "base_dir": "~/.config/ar/skill-evo",
    # ── GEPA 进化（evo.py evolve）──
    # rollout 预算 = evolve 一次的 execute 调用上限（每次 execute 含提炼+judge 两次 claude -p）
    "gepa_budget": 16,
    "gepa_batch_size": 4,
    "gepa_holdout_ratio": 0.2,
    # 标注样本（applied/rejected 提案）低于此数拒绝进化（冷启动保护）
    "gepa_min_cases": 10,
    # ── 插件哑故障巡检（evo_patrol）──
    # 两次巡检最小间隔（小时）；run 搭车执行，patrol 子命令 --force 可越过
    "patrol_interval_hours": 6,
    # ── apply 幂等检查（evo.py apply）──
    # new_text 与目标文件既有段落 difflib 相似度 ≥ 该阈值即拦截（0-1，越高越保守）
    "idempotent_threshold": 0.8,
    # judge 四维权重：precision / recall / negative_avoidance / format_compliance
    "judge_weights": [0.35, 0.35, 0.2, 0.1],
}

# 不允许被配置覆盖的键（防误配把数据目录指到仓库内）
_IMMUTABLE = ()


def _parse_scalar(raw: str):
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        return [_parse_scalar(x) for x in s[1:-1].split(",") if x.strip()]
    if s in ("true", "false"):
        return s == "true"
    for cast in (int, float):
        try:
            return cast(s)
        except ValueError:
            pass
    return s


def load_config(path: str | None = None) -> dict:
    """读取配置：默认值 < config.toml（浅覆盖）。"""
    cfg = dict(DEFAULTS)
    p = Path(path).expanduser() if path else Path(cfg["base_dir"]).expanduser() / "config.toml"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return cfg
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("[") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in cfg and key not in _IMMUTABLE:
            cfg[key] = _parse_scalar(value)
    return cfg


def repo_root() -> Path:
    """awesome-rules 仓库根（进化目标资产所在地）：scripts/ 向上 4 级。"""
    return Path(__file__).resolve().parents[3]


def base_paths(cfg: dict) -> dict:
    """派生路径：base_dir 下的 proposals/state/logs。"""
    base = Path(cfg["base_dir"]).expanduser()
    return {
        "base": base,
        "proposals": base / "proposals",
        "pending": base / "proposals" / "pending",
        "applied": base / "proposals" / "applied",
        "rejected": base / "proposals" / "rejected",
        "state": base / "state.json",
        "logs": base / "logs",
        "locks": base / "locks",
    }


def in_scope(cwd: str | None, cfg: dict) -> bool:
    """会话 cwd 必须位于 scope_dirs 之一之下。"""
    if not cwd:
        return False
    try:
        cwd_p = Path(os.path.normpath(os.path.expanduser(cwd))).resolve()
    except OSError:
        return False
    for d in cfg["scope_dirs"]:
        root = Path(os.path.expanduser(str(d))).resolve()
        if cwd_p == root or root in cwd_p.parents:
            return True
    return False
