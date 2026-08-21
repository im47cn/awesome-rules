#!/usr/bin/env python3
"""evo_patrol — 插件哑故障巡检

背景：CC 插件 `failed to load` 不弹通知（哑故障），steering 注入等 hook
静默失效无感知。本模块在 skill-evo 的 SessionEnd 搭车扫描中顺带巡检
`claude plugin list`，把加载失败落盘为可查询的告警台账。

数据：{base_dir}/patrol.json — {updated, failures:[{id,version,scope,error,first_seen}]}
语义：新故障 / 错误文本变化 → 日志告警；恢复 → 日志恢复；节流防每次会话都跑。
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PATROL_TIMEOUT = 60  # claude plugin list 秒级返回，60s 兜底
PATROL_FILE = "patrol.json"

# 块头：`  ❯ name@marketplace`
_HEAD = re.compile(r"❯\s+(\S+)")


def run_plugin_list(claude_bin: str, timeout: int = PATROL_TIMEOUT) -> str:
    """执行 claude plugin list，任何失败返回空串（巡检自身绝不抛栈）。"""
    try:
        r = subprocess.run(
            [claude_bin, "plugin", "list"], capture_output=True, text=True,
            timeout=timeout)
        return r.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def parse_failures(text: str) -> list[dict]:
    """从 plugin list 输出提取 failed to load 的插件（含多行 Error）。"""
    failures: list[dict] = []
    cur_id = cur_ver = cur_scope = cur_status = ""
    err_lines: list[str] = []

    def flush() -> None:
        if cur_id and "failed" in cur_status:
            failures.append({
                "id": cur_id, "version": cur_ver, "scope": cur_scope,
                "error": " ".join(x.strip() for x in err_lines if x.strip()),
            })

    for line in text.splitlines():
        m = _HEAD.search(line)
        if m:
            flush()
            cur_id, cur_ver, cur_scope, cur_status = m.group(1), "", "", ""
            err_lines = []
        elif line.strip().startswith("Version:"):
            cur_ver = line.split(":", 1)[1].strip()
        elif line.strip().startswith("Scope:"):
            cur_scope = line.split(":", 1)[1].strip()
        elif line.strip().startswith("Status:"):
            cur_status = line.split(":", 1)[1].strip()
        elif line.strip().startswith("Error:"):
            err_lines.append(line.split(":", 1)[1])
        elif cur_id and cur_status and line.startswith("    ") and err_lines:
            err_lines.append(line)  # Error 的续行（缩进 4 格且已有 Error 前缀）
    flush()
    return failures


def _load_known(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def patrol(cfg: dict, force: bool = False, log=None) -> dict | None:
    """巡检一次（节流）。返回 patrol.json 内容；节流未执行返回 None。

    log: 回调（evo._log），缺省丢弃 — 巡检永不影响调用方。
    """
    def _say(msg: str) -> None:
        if log:
            try:
                log(msg)
            except Exception:
                pass

    base = Path(cfg["base_dir"]).expanduser()
    path = base / PATROL_FILE
    now = datetime.now(timezone.utc)
    known = _load_known(path)
    interval_h = float(cfg.get("patrol_interval_hours", 6))
    if not force:
        last = known.get("checked_at", "")
        if last:
            try:
                elapsed = (now - datetime.fromisoformat(last)).total_seconds()
                if elapsed < interval_h * 3600:
                    return None  # 节流窗口内，跳过
            except ValueError:
                pass  # 坏时间戳 → 视为过期，照常巡检

    raw = run_plugin_list(str(cfg.get("claude_bin", "claude")))
    if not raw.strip():
        _say("patrol 跳过：claude plugin list 无输出")
        return None
    failures = parse_failures(raw)

    # 台账去重：id+error 为身份，first_seen 沿用；变化即告警
    prev = {f["id"]: f for f in known.get("failures", [])}
    stamp = now.isoformat(timespec="seconds")
    out = []
    for f in failures:
        old = prev.get(f["id"])
        fresh = old is None or old.get("error") != f["error"]
        f["first_seen"] = stamp if fresh else old.get("first_seen", stamp)
        if fresh:
            _say(f"patrol 告警: {f['id']} {f['error'][:80]}")
        out.append(f)
    for pid, old in prev.items():
        if pid not in {f["id"] for f in failures}:
            _say(f"patrol 恢复: {pid}（此前 {old.get('error', '?')[:60]}）")

    report = {"updated": stamp, "checked_at": stamp, "failures": out}
    try:
        base.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except OSError:
        pass  # 落盘失败不致命：下次会话重试
    return report


def load_alerts(cfg: dict) -> list[dict]:
    """读取当前未决故障（供 list 展示；文件缺失/损坏返回空）。"""
    return _load_known(Path(cfg["base_dir"]).expanduser() / PATROL_FILE).get(
        "failures", [])
