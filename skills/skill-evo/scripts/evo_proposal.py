#!/usr/bin/env python3
"""evo_proposal — 进化提案的读写与应用

提案 = markdown（frontmatter 元信息 + 人类可读正文 + 机读 JSON 块）。
round-trip 只依赖 JSON 块，正文渲染仅供人工审核阅读。
应用为「只追加」语义：append_under（插入到既有 ## 标题下）/ append_end，
不做改写删除 —— 天然不会削弱 steering 的【强制】条款。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
_MANDATORY_MARK = "【强制】"


@dataclass
class Change:
    action: str                    # append_under | append_end
    heading: str = ""
    new_text: str = ""


@dataclass
class Lesson:
    type: str                      # correction | failure | success
    evidence: str
    target_file: str
    confidence: str                # High | Medium | Low
    reason: str = ""
    change: Optional[Change] = None
    lesson_id: str = ""            # L-XXXXXXXX，write/load 时自动派生
    supersedes: str = ""           # 被修正的旧 lesson_id（人工审核时填写）


def derive_lesson_id(ls: Lesson) -> str:
    """确定性 lesson ID：L- + sha256(target|type|new_text)[:8]。

    内容相同 → ID 相同（幂等，供重复沉淀检测）；内容变化 → ID 变化
    （自然演化为新 lesson，修正走 supersedes 链而非改写）。
    """
    new_text = ls.change.new_text if ls.change else ""
    digest = hashlib.sha256(f"{ls.target_file}|{ls.type}|{new_text}".encode("utf-8"))
    return f"L-{digest.hexdigest()[:8].upper()}"


@dataclass
class Proposal:
    id: str
    source_agent: str
    source_session: str
    source_path: str
    created: str
    status: str = "pending"
    lessons: List[Lesson] = field(default_factory=list)

    def warnings(self) -> List[str]:
        """应用前的护栏检查（不阻断，apply 时要求确认/--force）。"""
        out = []
        for i, ls in enumerate(self.lessons, 1):
            nt = ls.change.new_text if ls.change else ""
            if _MANDATORY_MARK in nt:
                out.append(f"lesson {i}: new_text 含 {_MANDATORY_MARK}，"
                           "强制级别应由人工评审设定（apply 需 --force）")
            if ls.confidence == "Low":
                out.append(f"lesson {i}: 置信度 Low，建议人工核实后再应用")
        return out


# ── 序列化 ──────────────────────────────────────────────────────────────────

def _render_lesson(i: int, ls: Lesson) -> str:
    ch = ls.change
    where = (f"追加至 `{ls.target_file}` 的 `{ch.heading}` 下" if ch and ch.action == "append_under"
             else f"追加至 `{ls.target_file}` 末尾" if ch else "（无变更描述）")
    body = ""
    if ch and ch.new_text:
        body = "\n\n   ```markdown\n   " + ch.new_text.replace("\n", "\n   ") + "\n   ```"
    sup = f"\n- **修正（supersedes）**：{ls.supersedes}" if ls.supersedes else ""
    return (f"### {i}. `{ls.lesson_id}` [{ls.confidence}] {ls.type} → {ls.target_file}\n"
            f"- **证据**：{ls.evidence}\n"
            f"- **理由**：{ls.reason}{sup}\n"
            f"- **变更**：{where}{body}")


def write_proposal(p: Proposal, pending_dir: Path) -> Path:
    pending_dir.mkdir(parents=True, exist_ok=True)
    path = pending_dir / f"{p.id}.md"
    fm = (f"---\nid: {p.id}\nstatus: {p.status}\nsource_agent: {p.source_agent}\n"
          f"source_session: {p.source_session}\nsource_path: {p.source_path}\n"
          f"created: {p.created}\nlessons: {len(p.lessons)}\n---\n")
    for ls in p.lessons:
        ls.lesson_id = ls.lesson_id or derive_lesson_id(ls)
    rendered = "\n".join(_render_lesson(i, ls) for i, ls in enumerate(p.lessons, 1))
    payload = {"lessons": [{
        "type": ls.type, "evidence": ls.evidence, "target_file": ls.target_file,
        "confidence": ls.confidence, "reason": ls.reason,
        "lesson_id": ls.lesson_id, "supersedes": ls.supersedes,
        "change": {"action": ls.change.action, "heading": ls.change.heading,
                   "new_text": ls.change.new_text} if ls.change else None,
    } for ls in p.lessons]}
    machine = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=1) + "\n```"
    path.write_text(
        f"{fm}\n# 进化提案 {p.id}\n\n> 来源：{p.source_agent} 会话 `{p.source_session}`"
        f"（{p.source_path}）\n\n{rendered}\n\n## 机读数据（apply 依据，勿手改）\n\n{machine}\n",
        encoding="utf-8")
    return path


def load_proposal(path: Path) -> Proposal:
    content = path.read_text(encoding="utf-8")
    fm = {}
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            for line in content[3:end].strip().splitlines():
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip()
    lessons: List[Lesson] = []
    payload = None
    for m in _JSON_BLOCK_RE.finditer(content):
        try:
            candidate_payload = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(candidate_payload, dict):   # 跳过非 lessons 载荷（如迭代日志 list）
            payload = candidate_payload
            break
    if payload:
        try:
            for ls in payload.get("lessons", []):
                ch_raw = ls.get("change") or {}
                ch = Change(action=str(ch_raw.get("action", "append_end")),
                            heading=str(ch_raw.get("heading", "")),
                            new_text=str(ch_raw.get("new_text", ""))) if ch_raw else None
                lessons.append(Lesson(
                    type=str(ls.get("type", "")), evidence=str(ls.get("evidence", "")),
                    target_file=str(ls.get("target_file", "")),
                    confidence=str(ls.get("confidence", "")),
                    reason=str(ls.get("reason", "")), change=ch,
                    lesson_id=str(ls.get("lesson_id", "")),
                    supersedes=str(ls.get("supersedes", ""))))
        except json.JSONDecodeError:
            pass
    for ls in lessons:
        ls.lesson_id = ls.lesson_id or derive_lesson_id(ls)   # 旧提案兼容：按内容补派生
    return Proposal(
        id=fm.get("id", path.stem), source_agent=fm.get("source_agent", "?"),
        source_session=fm.get("source_session", "?"), source_path=fm.get("source_path", "?"),
        created=fm.get("created", "?"), status=fm.get("status", "pending"), lessons=lessons)


def list_proposals(status_dir: Path) -> List[Proposal]:
    if not status_dir.is_dir():
        return []
    return [load_proposal(p) for p in sorted(status_dir.glob("*.md"))]


def _read_fm(path: Path) -> dict:
    """轻量 frontmatter 读取（只扫文件头，不解析正文）。"""
    fm: dict = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            if f.readline().startswith("---"):
                for line in f:
                    if line.startswith("---"):
                        break
                    key, _, val = line.partition(":")
                    fm[key.strip()] = val.strip()
    except OSError:
        pass
    return fm


def session_proposal_exists(paths: dict, source_agent: str, source_session: str) -> bool:
    """单会话单提案守卫：该会话在 pending/applied/rejected 任一状态已有提案。

    防两类重复：a) 内容哈希竞态之外的兜底（如手动跑两次）；
    b) 会话尾部增长触发重总结导致整包重复提案。代价是丢失尾部新增经验，
    与「处理过即不再重提」的既定取舍一致。
    """
    for key in ("pending", "applied", "rejected"):
        d: Path = paths[key]
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            fm = _read_fm(f)
            if (fm.get("source_agent") == source_agent
                    and fm.get("source_session") == source_session
                    and fm.get("type") != "prompt_evolution"):
                return True
    return False


def applied_lesson_ids(applied_dir: Path) -> dict:
    """已应用归档索引：lesson_id → 来源提案 stem。

    供两类检查：重复沉淀检测（同 ID 再次出现）与 supersedes 引用校验。
    """
    out: dict = {}
    if not applied_dir.is_dir():
        return out
    for f in sorted(applied_dir.glob("*.md")):
        for ls in load_proposal(f).lessons:
            out.setdefault(ls.lesson_id or derive_lesson_id(ls), f.stem)
    return out


_QUOTE_NORM = str.maketrans({"“": '"', "”": '"', "‘": "'",
                             "’": "'", "「": '"', "」": '"'})


def _norm_quote(text: str) -> str:
    """空白剔除 + 引号字形归一（弯引号/直角引号 → 直引号）。

    总结器会把会话原文的弯引号写成直引号（实测 2026-08-19 提案 lesson 2），
    字形差异不应导致真实引用被判 miss。
    """
    return "".join(text.split()).translate(_QUOTE_NORM)


def verify_evidence(p: Proposal, corpus: str) -> List[Tuple[int, str]]:
    """逐 lesson 核验 evidence 是否逐字命中来源会话原文（空白不敏感）。

    返回 (lesson 序号, 状态)：hit=命中 / miss=未命中（可疑编造）/
    no_corpus=语料缺失无法核验。把人工抽查 evidence 真实性变成脚本核验。
    """
    norm_corpus = _norm_quote(corpus)
    results: List[Tuple[int, str]] = []
    for i, ls in enumerate(p.lessons, 1):
        if not norm_corpus:
            results.append((i, "no_corpus"))
            continue
        quote = _norm_quote(ls.evidence)
        results.append((i, "hit" if quote and quote in norm_corpus else "miss"))
    return results


# ── 应用 ────────────────────────────────────────────────────────────────────

class ApplyError(Exception):
    pass


def validate_target(target_file: str, repo_root: Path) -> Path:
    """目标必须解析到仓库内的允许资产（防路径逃逸）。

    允许：skills/**.md、steering/**.md、根 README.md（索引表格）、根 CLAUDE.md（AI 操作指引）。
    """
    root = repo_root.resolve()
    p = (root / target_file).resolve()
    if root != p and root not in p.parents:
        raise ApplyError(f"目标越出仓库边界：{target_file}")
    rel = p.relative_to(root).as_posix()
    ok = ((rel.startswith("skills/") or rel.startswith("steering/"))
          and rel.endswith(".md")) or rel in ("README.md", "CLAUDE.md")
    if not ok:
        raise ApplyError(f"目标不在允许范围（skills/、steering/ 的 .md 或根 README/CLAUDE.md）：{target_file}")
    if not p.is_file():
        raise ApplyError(f"目标文件不存在：{target_file}")
    return p


def _apply_change(content: str, ch: Change, target_file: str) -> str:
    if ch.action == "append_end":
        sep = "" if content.endswith("\n") else "\n"
        return content + f"{sep}{ch.new_text}\n"
    if ch.action == "append_under":
        if not ch.heading:
            raise ApplyError(f"{target_file}: append_under 缺少 heading")
        lines = content.splitlines(keepends=True)
        hits = [i for i, ln in enumerate(lines)
                if ln.strip() == ch.heading.strip() and ln.lstrip().startswith("#")]
        if not hits:
            raise ApplyError(f"{target_file}: 找不到标题锚点 `{ch.heading}`")
        if len(hits) > 1:
            raise ApplyError(f"{target_file}: 标题锚点 `{ch.heading}` 出现 {len(hits)} 次，不唯一")
        i = hits[0]
        # 表格感知：标题下紧跟表格（| 行）时，插到表格末行之后（插到表头前会破坏表格）
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].lstrip().startswith("|"):
            while j + 1 < len(lines) and lines[j + 1].lstrip().startswith("|"):
                j += 1
            lines.insert(j + 1, ch.new_text.rstrip("\n") + "\n")
            return "".join(lines)
        insert = ("\n" if i + 1 < len(lines) and lines[i + 1].strip() else "") + ch.new_text + "\n"
        lines.insert(i + 1, insert)
        return "".join(lines)
    raise ApplyError(f"{target_file}: 未知 action `{ch.action}`")


def apply_proposal(p: Proposal, repo_root: Path, *, dry_run: bool = False,
                   force: bool = False, applied_dir: Optional[Path] = None,
                   extra_warnings: Optional[List[str]] = None) -> List[str]:
    """两阶段应用：先在内存中对所有 lesson 校验并计算新内容，全部通过才落盘。

    返回各文件变更说明；dry_run 只输出不写。锚点失配/不唯一即整体失败，不盲写。
    护栏警告（【强制】标记/Low 置信度/重复沉淀/evidence 未核验）需 --force 越过；
    supersedes 引用无效为硬错（输入非法，force 不可越过）。
    """
    if not p.lessons:
        raise ApplyError("提案无 lesson")
    # 阶段 1：内存计算（同一文件多个 lesson 顺序叠加）+ 重复沉淀检测
    new_contents: dict = {}
    report: List[str] = []
    guard = list(extra_warnings or [])
    known = applied_lesson_ids(applied_dir) if applied_dir else {}
    for i, ls in enumerate(p.lessons, 1):
        if not ls.change or not ls.change.new_text:
            raise ApplyError(f"lesson {i}: 无变更内容")
        lid = ls.lesson_id or derive_lesson_id(ls)
        if ls.supersedes == lid:
            raise ApplyError(f"lesson {i}: supersedes 不能指向自身（{lid}）")
        if ls.supersedes and ls.supersedes not in known:
            raise ApplyError(f"lesson {i}: supersedes 引用的 {ls.supersedes} "
                             "不在已应用归档中（请核对 lesson_id）")
        if lid in known:
            guard.append(f"lesson {i}: 与已应用提案 {known[lid]} 的 {lid} 内容相同"
                         "（疑似重复沉淀，--force 可越过）")
        path = validate_target(ls.target_file, repo_root)
        content = new_contents.get(path.as_posix()) or path.read_text(encoding="utf-8")
        if ls.change.new_text.strip() in content:
            guard.append(f"lesson {i}: new_text 已逐字存在于 {ls.target_file}"
                         "（疑似重复追加，--force 可越过）")
        new_contents[path.as_posix()] = _apply_change(content, ls.change, ls.target_file)
        where = (f"`{ls.change.heading}` 下" if ls.change.action == "append_under" else "末尾")
        report.append(f"lesson {i} → {ls.target_file}（{where}）追加 {len(ls.change.new_text)} chars")
    # 阶段 2：护栏汇总（默认阻断；--force 越过后落盘）
    guard = p.warnings() + guard
    if guard and not force:
        raise ApplyError("存在护栏警告，需人工确认后 --force 应用：\n- " + "\n- ".join(guard))
    if not dry_run:
        for posix_path, content in new_contents.items():
            Path(posix_path).write_text(content, encoding="utf-8")
    return report


def move_proposal(proposal_path: Path, dest_dir: Path, extra_fm: dict) -> Path:
    """状态流转：pending → applied/rejected（frontmatter 追加记录后移动）。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = proposal_path.read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    extra = "".join(f"{k}: {v}\n" for k, v in extra_fm.items())
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[:end + 1] + extra + content[end + 1:]
    else:
        content = f"---\n{extra}---\n" + content
    dest = dest_dir / proposal_path.name
    final = dest if not dest.exists() else dest.with_name(
        f"{dest.stem}-{stamp.replace(':', '').replace('+', '-')}{dest.suffix}")
    final.write_text(content, encoding="utf-8")
    if proposal_path.is_dir():  # 防御：提案应为文件
        shutil.rmtree(proposal_path, ignore_errors=True)
    else:
        proposal_path.unlink(missing_ok=True)
    return final
