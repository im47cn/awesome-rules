#!/usr/bin/env python3
"""evo_session — 会话发现与解析（Claude Code / omp 双适配器）

transcript 格式（均 JSONL，逐行 JSON，损坏行容错跳过）：
- Claude Code: ~/.claude/projects/<cwd-slug>/<sessionId>.jsonl
  行形如 {"type":"user"|"assistant", "message":{"role","content":[...]}, "cwd":...}
  content 块: {"type":"text","text"} / {"type":"tool_result","content",...,"is_error"}
- omp: ~/.omp/agent/sessions/<cwd-slug>/<timestamp>_<sessionId>.jsonl
  首部 {"type":"session","id","cwd"}，正文 {"type":"message","message":{"role","content":[...]}}
  role: user/assistant/toolResult；块: text/thinking/toolCall
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, List, Optional


@dataclass
class Msg:
    role: str            # user / assistant / tool
    text: str
    tool_name: Optional[str] = None
    is_error: bool = False


@dataclass
class Session:
    agent: str           # "cc" | "omp"
    session_id: str
    cwd: Optional[str]
    path: Path
    mtime: float
    messages: List[Msg] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.agent}:{self.session_id}"

    def user_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")


def _load_jsonl(path: Path) -> Iterator[dict]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def _block_text(content) -> str:
    """content 可能是 str 或 块列表；提取 text 块文本。"""
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(str(b.get("text", "")))
    return "\n".join(p for p in parts if p)


# ── Claude Code ──────────────────────────────────────────────────────────────

_META_PREFIX = ("<command-", "<local-command", "<system-", "Caveat:")


def parse_cc_session(path: Path) -> Session:
    sess = Session(agent="cc", session_id=path.stem, cwd=None,
                   path=path, mtime=path.stat().st_mtime if path.exists() else 0.0)
    for obj in _load_jsonl(path):
        if not sess.cwd and obj.get("cwd"):
            sess.cwd = obj["cwd"]
        if not sess.session_id or sess.session_id == path.stem:
            sid = obj.get("sessionId")
            if sid:
                sess.session_id = sid
        if obj.get("isMeta"):
            continue
        mtype = obj.get("type")
        msg = obj.get("message") or {}
        if mtype not in ("user", "assistant") or not isinstance(msg, dict):
            continue
        role = msg.get("role") or mtype
        content = msg.get("content")
        if role == "user":
            text = _block_text(content)
            # 跳过工具结果（user 消息内嵌 tool_result 块）之外的噪音标签消息
            if text and not text.lstrip().startswith(_META_PREFIX):
                sess.messages.append(Msg(role="user", text=text))
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    sess.messages.append(Msg(
                        role="tool", text=_block_text(b.get("content")),
                        is_error=bool(b.get("is_error"))))
        elif role == "assistant":
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text"):
                    sess.messages.append(Msg(role="assistant", text=str(b["text"])))
                elif b.get("type") == "tool_use":
                    # 记录工具名，供后续 tool 结果归属（简化为独立消息）
                    sess.messages.append(Msg(role="assistant", text="",
                                             tool_name=str(b.get("name", ""))))
    return sess


# ── omp ──────────────────────────────────────────────────────────────────────

_OMP_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-\d+Z_([0-9a-zA-Z-]+)\.jsonl$")


def parse_omp_session(path: Path) -> Session:
    sess = Session(agent="omp", session_id=path.stem, cwd=None,
                   path=path, mtime=path.stat().st_mtime if path.exists() else 0.0)
    for obj in _load_jsonl(path):
        if obj.get("type") == "session":
            sess.session_id = str(obj.get("id") or path.stem)
            sess.cwd = obj.get("cwd")
            continue
        if obj.get("type") != "message":
            continue
        msg = obj.get("message") or {}
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        content = msg.get("content")
        if role == "toolResult":
            sess.messages.append(Msg(
                role="tool", text=_block_text(content),
                is_error=bool(msg.get("isError"))))
        elif role == "assistant":
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                    sess.messages.append(Msg(role="assistant", text=str(b["text"])))
        elif role == "user":
            text = _block_text(content)
            if text:
                sess.messages.append(Msg(role="user", text=text))
    return sess


def parse_session(agent: str, path: Path) -> Session:
    return parse_cc_session(path) if agent == "cc" else parse_omp_session(path)


# ── 发现与增量 ───────────────────────────────────────────────────────────────

def discover_omp_roots(cfg: dict) -> List[Path]:
    """omp 会话根目录候选（config 覆盖 > 默认 ~/.omp/agent/sessions）。"""
    root = Path(os.path.expanduser(str(cfg["omp_sessions_dir"])))
    return [root] if root.is_dir() else []


def iter_omp_sessions(cfg: dict) -> Iterator[Path]:
    """枚举 lookback 天数内的 omp 会话文件（按 cwd-slug 子目录组织）。"""
    root = Path(os.path.expanduser(str(cfg["omp_sessions_dir"])))
    if not root.is_dir():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(cfg["omp_lookback_days"]))
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        for f in sorted(sub.glob("*.jsonl")):
            m = _OMP_FILE_RE.match(f.name)
            if not m:
                continue
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%dT%H-%M-%S").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                continue
            if ts >= cutoff:
                yield f


def load_state(state_path: Path) -> dict:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(state_path)  # 原子替换


def is_processed(state: dict, sess: Session) -> bool:
    """增量去重：处理过即不再重处理（接受 SessionEnd 尾部少量丢尾，防重复提案）。"""
    done = state.get("processed", {})
    return done.get(sess.key) is not None and done[sess.key] >= sess.mtime
