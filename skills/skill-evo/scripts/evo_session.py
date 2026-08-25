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

import hashlib
import json
import os
import time
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager
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


def sniff_agent(path: Path) -> str:
    """格式嗅探：omp 首部有 {"type":"session",...}，CC 首部无此类型。默认 cc。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    if obj.get("type") == "session":
                        return "omp"
                    if obj.get("type") in ("user", "assistant", "summary"):
                        return "cc"
    except OSError:
        pass
    return "cc"


def find_latest_omp_sessions(cfg: dict, cwd: str, limit: int = 1) -> List[Path]:
    """按 cwd 定位最近的 omp 会话文件（首行 cwd 匹配 + mtime 降序）。

    omp hook 侧拿不到 session 文件路径（ctx 只有 cwd），退路由 Python 精确定位：
    同 cwd 并发会话属罕见，且 state 去重使误选无害（只是延迟处理）。
    """
    if not cwd:
        return []
    root = Path(os.path.expanduser(str(cfg["omp_sessions_dir"])))
    if not root.is_dir():
        return []
    target = os.path.normpath(os.path.expanduser(cwd))
    hits = []
    for f in root.glob("*/*.jsonl"):
        m = _OMP_FILE_RE.match(f.name)
        if not m:
            continue
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(obj, dict) and obj.get("type") == "session":
                        if os.path.normpath(os.path.expanduser(
                                str(obj.get("cwd", "")))) == target:
                            hits.append(f)
                        break   # session 首部之后不再读
        except OSError:
            continue
    hits.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return hits[:limit]


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


LOCK_STALE_SECONDS = 3600  # 总结含 LLM 慢调用（claude_timeout 默认 180s），宽限 1h


@contextmanager
def session_lock(paths: dict, key: str,
                 stale_seconds: int = LOCK_STALE_SECONDS) -> Iterator[bool]:
    """单会话跨进程互斥锁：原子 O_EXCL 创建；撞锁 yield False（让位跳过）。

    背景（2026-08-21 实测竞态）：多个 hook 并发 run 时各自的 state 快照均未含
    对方即将写入的提案，session_proposal_exists 的 TOCTOU 窗口 + 秒级 LLM 延迟
    使同一会话被并发总结 6 次、产出 6 份重复提案。锁把「查重 → 总结 → 记账」
    串行化：持锁者独占处理，撞锁者跳过（下次扫描时单提案守卫/state 兜底）。
    过期死锁（持锁进程崩溃）按 mtime 超时窃取一次。
    """
    lock_dir: Path = paths["locks"]
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir / (key.replace("/", "_") + ".lock")
    acquired = False
    for _ in range(2):  # 第二轮：清理过期死锁后重试一次
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # 锁恰被持锁者释放：立即重试
            if age < stale_seconds:
                break            # 活锁：让位
            try:                 # 过期死锁：窃取后重试
                lock.unlink()
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()} ts={time.time():.0f}\n")
        acquired = True
        break
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.unlink()
            except OSError:
                pass


def content_digest(path: Path) -> str:
    """会话文件内容哈希（记账用）。mtime 不可靠：SessionEnd flush 也会碰它，
    曾导致同一会话 45 秒内被整会话重总结、产出重复提案。"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def is_processed(state: dict, sess: Session) -> bool:
    """增量去重（内容哈希版）：内容未变即视为已处理（touch/flush 不触发重处理）。

    兼容旧 mtime 记账（float）：值非 str 视为未处理，自然重算为哈希。
    """
    done = state.get("processed", {})
    recorded = done.get(sess.key)
    return isinstance(recorded, str) and recorded == content_digest(sess.path)
