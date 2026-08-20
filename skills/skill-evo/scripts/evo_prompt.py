#!/usr/bin/env python3
"""evo_prompt — transcript 过滤切片 + headless 总结 prompt 构造

切片原则：用户消息全保留（经验的唯一来源），assistant 文本截断，
工具结果仅错误类全文 + 正常结果截断；全程脱敏。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from evo_session import Session

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_.-]{200,}")
_SECRET_RES = (
    re.compile(r"\b(sk|rk|ghp|gho|github_pat)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)

_ASSISTANT_MAX = 800       # assistant 单条文本截断
_TOOL_OK_MAX = 200         # 正常工具结果截断
_TOOL_ERR_MAX = 2000       # 错误工具结果上限


def sanitize(text: str) -> str:
    """脱敏 + 去噪：ANSI、密钥、超长 token（base64/hex 类）。"""
    if not text:
        return ""
    text = _ANSI_RE.sub("", text)
    for r in _SECRET_RES:
        text = r.sub("<REDACTED>", text)
    return _LONG_TOKEN_RE.sub("<LONG-TOKEN>", text)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"…(+{len(text) - limit} chars)"


def build_transcript_view(sess: Session, cfg: dict) -> str:
    """会话 → 紧凑文本视图：[role] 内容，总长度受 max_transcript_chars 约束。"""
    lines: List[str] = []
    last_tool = ""
    for m in sess.messages:
        if m.tool_name:  # assistant 的工具调用记号
            last_tool = m.tool_name
            continue
        if m.role == "user":
            lines.append(f"[user] {sanitize(m.text)}")
        elif m.role == "assistant":
            lines.append(f"[assistant] {_clip(sanitize(m.text), _ASSISTANT_MAX)}")
        elif m.role == "tool":
            body = sanitize(m.text)
            limit = _TOOL_ERR_MAX if m.is_error else _TOOL_OK_MAX
            tag = f"[tool:{last_tool or '?'}{' ERROR' if m.is_error else ''}]"
            lines.append(f"{tag} {_clip(body, limit)}")
    view = "\n".join(lines)
    cap = int(cfg["max_transcript_chars"])
    if len(view) > cap:
        view = view[:cap] + f"\n…(截断，共 {len(view)} chars)"
    return view


# ── 目标资产索引（重用 load-steering.sh 的 frontmatter 解析范式）────────────

def _frontmatter_title(content: str, fallback: str) -> str:
    title = None
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            m = re.search(r"^title:\s*(.+)$", content[3:end], re.M)
            if m:
                title = m.group(1).strip()
    if not title:
        m = re.search(r"^#\s+(.+)$", content, re.M)
        title = m.group(1).strip() if m else fallback
    return title


def build_target_index(repo_root: Path) -> str:
    """进化目标清单：根 README/CLAUDE.md + skills 下全部 .md + steering/**.md（标题 + 二级标题锚点）。"""
    rows: List[str] = []
    targets: List[Path] = [p for p in (repo_root / "README.md", repo_root / "CLAUDE.md")
                           if p.is_file()]
    targets += sorted(repo_root.glob("skills/*/*.md"))
    targets += sorted(repo_root.glob("steering/*.md")) + sorted(repo_root.glob("steering/gtsp/*.md"))
    for p in targets:
        rel = p.relative_to(repo_root).as_posix()
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        headings = re.findall(r"^##\s+(.+)$", content, re.M)[:15]
        rows.append(f"- {rel}（{_frontmatter_title(content, rel)}）"
                    + (f"；可用标题锚点: {'、'.join(f'## {h}' for h in headings)}" if headings else ""))
    return "\n".join(rows)


# ── prompt ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是研发规范仓库 awesome-rules 的「经验提炼器」。给定一段终端 AI 编码会话记录，\
提炼对仓库规范/技能文件有持久价值的经验教训。

只提取满足以下条件的内容（宁缺毋滥，无信号则 no_signal=true）：
1. 用户对 AI 行为的纠正（AI 做错了，用户指出正确做法）
2. 失败模式（工具/命令/方案反复失败后找到的正确做法）
3. 被用户明确认可的成功模式
且该经验能落到下方目标资产清单中某个文件的具体条款上；泛泛的闲聊、一次性上下文、
与本仓库规范无关的内容一律忽略。

输出严格为单个 JSON 对象（无 markdown 代码围栏、无其他文字）：
{
  "no_signal": false,
  "lessons": [
    {
      "type": "correction | failure | success",
      "evidence": "会话原文片段（逐字引用，可追溯）",
      "target_file": "目标资产清单中的相对路径",
      "confidence": "High | Medium | Low",
      "reason": "为什么要改这个文件（一句话）",
      "change": {
        "action": "append_under | append_end",
        "heading": "append_under 时必填：目标文件中已存在的 ## 级标题（从清单锚点中选，逐字一致）",
        "new_text": "要插入的 markdown 片段（1-5 行的条款/要点，格式与目标文件风格一致，中文）"
      }
    }
  ]
}

约束：
- v1 只允许追加（append_under / append_end），不得改写或删除既有内容
- new_text 必须自包含成一条规范条款（列表项或短段落），不使用「如上」「同前」等指代
- 目标标题下是表格时（如 README 的技能/规范/文档索引表），new_text 必须是完整表格行（以 | 开头，列数与该表一致）
- 新技能/新规范/新设计文档已在磁盘但未登记 README 索引表的经验，优先以表格行追加到对应 README
- 不新增【强制】标记（强制级别是人工评审决策）
- 每条 evidence 必须能在会话记录中找到出处"""


def build_summary_prompt(sess: Session, cfg: dict, repo_root: Path) -> str:
    return (
        f"# 会话信息\nagent: {sess.agent}\ncwd: {sess.cwd}\n"
        f"# 目标资产清单\n{build_target_index(repo_root)}\n\n"
        f"# 会话记录（已脱敏截断）\n{build_transcript_view(sess, cfg)}\n\n"
        f"# 任务\n{SYSTEM_PROMPT}"
    )
