#!/usr/bin/env python3
"""evo_evolve — GEPA 首个应用：进化 evo_prompt.SYSTEM_PROMPT

标注数据 = applied/rejected 提案（人工审核结果即真实标签）：
- Case.inputs：溯源 source_path 重解析会话，重建 transcript 视图 + 目标资产索引
- execute：候选 SYSTEM_PROMPT 在 Case 上跑 lessons 提炼 → judge 按
  precision/recall/负样本规避（reject_reason）/格式合规 四维打分
- reflect：reflector 看当前候选 + minibatch 分数与反馈 → 编辑后的完整 SYSTEM_PROMPT

进化产物为 prompt_evolution 型 pending 提案，人工采纳（手动编辑常量），
不走 apply（apply 仅支持 markdown 追加语义）。
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import evo_gepa as G
import evo_prompt as P
import evo_proposal as PR
import evo_session as S

# judge 输出四维（各 0-10）：权重见 config judge_weights
JUDGE_PROMPT = """你是「经验提炼质量」评审。给定：候选 prompt 在一段会话上提炼出的 lessons，
以及人工审核的参考结果。参考中每条 lesson 携带结构化 verdict（最终处置）：
- applied = 原样应用（应提炼出的内容）
- trimmed = 内容被裁剪后应用（产出方向对但含冗余，verdict_codes 给出原因）
- edited = 修正锚点/落点后应用（内容对，元数据有缺陷）
- rejected = 被剔除或整包驳回（不应产出；verdict_codes 给出原因）
另有整包 reject_reason（若有）。

参考还携带两类元数据：
- heading：人工认可的落点锚点。## 与 ### 级均合法（目标清单同时提供两级），
  语义匹配时应优先最具体的子节锚点；候选落点比参考更粗（堆在二级标题）计 precision 扣分，
  落到语义不符的锚点按 off_target 处理。
- evidence_check：来源会话核验状态。hit=逐字命中 / paraphrase=转述拼接（片段命中，
  可接受）/ miss=可疑编造 / no_corpus=无法核验。候选复现 miss 级 evidence 内容时
  precision 必须低分；paraphrase 与 hit 同为有效证据形态，不因非逐字扣分。

negative_avoidance 按 verdict_codes 精确评估：候选复现被标注 dup_superset /
content_overlap / low_value / off_target 等模式的内容则低分；trimmed 的教训
（超量/冗余产出）也计入。

按四维打分（0-10 整数），输出严格单个 JSON（无围栏无其他文字）：
{
  "precision": "产出的 lessons 中命中人工认可内容的比例（trimmed 部分按冗余扣；evidence 复现 miss 级内容计 0）",
  "recall": "人工认可的经验中被提炼出的比例",
  "negative_avoidance": "是否规避了被驳回/被裁剪的错误（按 verdict_codes 逐类核对）",
  "format_compliance": "JSON schema、追加语义（append_under/append_end，锚点 ##/### 逐字取自清单）、无新增【强制】标记",
  "feedback": "一句话最有价值的改进方向"
}"""

REFLECTOR_PROMPT = """你是 prompt 进化器（GEPA reflector）。给定：当前 SYSTEM_PROMPT 全文、
它在若干会话案例上的得分与评审反馈，输出**编辑后的完整 SYSTEM_PROMPT**（直接输出新全文，
无解释无围栏）。

硬约束（违反即作废）：
- 保持输出 JSON 契约不变：顶层 {"no_signal": bool, "lessons": [...]}，
  lesson 字段 type/evidence/target_file/confidence/reason/change{action,heading,new_text} 不增不减
- change.action 只允许 append_under / append_end
- 只改指令性文字（筛选标准、表述精度、防幻觉要求），不改变角色定位
- 长度不超过原始长度的 1.5 倍

# 当前 SYSTEM_PROMPT
{current}

# 案例反馈
{feedback}

# 输出
编辑后的完整 SYSTEM_PROMPT："""


def build_dataset(cfg: dict) -> Tuple[List[G.Case], List[G.Case]]:
    """从 applied/rejected 提案构建 train/holdout（按 source_session 分层切）。"""
    from evo_config import base_paths, repo_root
    paths = base_paths(cfg)
    repo = repo_root()
    cases: List[G.Case] = []
    for status in ("applied", "rejected"):
        d: Path = paths[status]
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            p = PR.load_proposal(f)
            src = Path(p.source_path)
            if not src.is_file():
                continue
            agent = "omp" if p.source_agent == "omp" else "cc"
            sess = S.parse_session(agent, src)
            if not sess.messages:
                continue
            # 与 evo.py _session_corpus 同构的语料：脱敏后逐字/转述核验（✓/⚠/✗/?）
            corpus = "\n".join(P.sanitize(m.text) for m in sess.messages)
            ev_checks = dict(PR.verify_evidence(p, corpus))
            cases.append(G.Case(
                id=sess.key,
                inputs={"transcript_view": P.build_transcript_view(sess, cfg),
                        "target_index": P.build_target_index(repo)},
                reference={"status": status, "lessons": [
                    {"target_file": ls.target_file, "confidence": ls.confidence,
                     "change_new_text": ls.change.new_text if ls.change else "",
                     "heading": ls.change.heading if ls.change else "",
                     "evidence": ls.evidence,
                     "evidence_check": ev_checks.get(i, "no_corpus"),
                     "verdict": ls.verdict,
                     "verdict_codes": ls.verdict_codes} for i, ls in enumerate(p.lessons, 1)],
                    "reject_reason": _reject_reason(f)}))
    # 按 session 分层切（同会话的提案不跨集）
    sessions = sorted({c.id for c in cases})
    rng = random.Random(42)
    rng.shuffle(sessions)
    n_holdout = max(4, int(len(sessions) * float(cfg["gepa_holdout_ratio"])))
    if len(cases) < int(cfg["gepa_min_cases"]) or len(sessions) - n_holdout < 2:
        raise SystemExit(
            f"标注样本不足：{len(cases)} cases / {len(sessions)} sessions"
            f"（需 ≥{cfg['gepa_min_cases']} cases；持续使用后自动积累，可 evolve --dry-run 查看进度）")
    holdout_ids = set(sessions[:n_holdout])
    train = [c for c in cases if c.id not in holdout_ids]
    holdout = [c for c in cases if c.id in holdout_ids]
    return train, holdout


def _reject_reason(path: Path) -> str:
    fm = {}
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            for line in content[3:end].strip().splitlines():
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
    return fm.get("reject_reason", "")


def make_execute(cfg, call_claude):
    """execute(candidate_text, case) -> (score 0-1, feedback)。"""

    def execute(system_prompt: str, case: G.Case) -> Tuple[float, str]:
        prompt = (f"{system_prompt}\n\n# 目标资产清单\n{case.inputs['target_index']}\n\n"
                  f"# 会话记录（已脱敏截断）\n{case.inputs['transcript_view']}\n\n# 任务\n请提炼")
        try:
            out = call_claude(prompt, cfg)
        except Exception as e:
            return 0.0, f"执行失败: {e}"
        lessons = out.get("lessons") or []
        if out.get("no_signal") and not lessons:
            lessons = []
        ref = json.dumps(case.reference, ensure_ascii=False)
        judge_in = (f"{JUDGE_PROMPT}\n\n# 候选产出\n{json.dumps(lessons, ensure_ascii=False)}"
                    f"\n\n# 人工参考\n{ref}")
        try:
            judged = call_claude(judge_in, cfg)
        except Exception as e:
            return 0.0, f"judge 失败: {e}"
        w = cfg["judge_weights"]
        dims = [judged.get("precision", 0) / 10, judged.get("recall", 0) / 10,
                judged.get("negative_avoidance", 0) / 10,
                judged.get("format_compliance", 0) / 10]
        score = sum(d * float(wi) for d, wi in zip(dims, w))
        return score, str(judged.get("feedback", ""))

    return execute


def make_reflect(call_claude_raw, cfg):
    """reflector 通道：输入当前候选与反馈，输出编辑后的完整 SYSTEM_PROMPT（纯文本）。"""

    def reflect(current: str, results, asset_desc: str) -> str:
        lines = []
        for case, score, feedback in results:
            lines.append(f"- case {case.id}: score={score:.3f}，反馈：{feedback}")
        prompt = REFLECTOR_PROMPT.format(current=current, feedback="\n".join(lines))
        return call_claude_raw(prompt, cfg)

    return reflect


def validate_candidate(baseline_len: int):
    """变异候选约束：保留 JSON 契约关键词 + 子节锚点契约 + 长度上限。"""

    def check(text: str) -> bool:
        for kw in ('"no_signal"', '"lessons"', "append_under", "append_end", "evidence", '"knowledge_type"'):
            if kw not in text:
                return False
        # 子节锚点契约是人工基线的一部分（2026-08-24 调整）：reflector 重写掉
        ### 指引会使新提案全部堆回二级标题，属退化候选，直接拒绝
        return False if "###" not in text else len(text) <= baseline_len * 1.5

    return check


def write_evolution_proposal(cfg, baseline: str, best: G.Candidate,
                             baseline_score: float, best_score: float,
                             log: List[dict]) -> Path:
    """holdout 有统计意义改善时，产出 prompt_evolution 型 pending 提案（人工采纳）。"""
    from evo_config import base_paths
    paths = base_paths(cfg)
    paths["pending"].mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    pid = f"{now.strftime('%Y%m%d-%H%M%S')}-gepa-prompt"
    body = (
        f"---\nid: {pid}\nstatus: pending\ntype: prompt_evolution\n"
        f"source_agent: gepa\nsource_session: -\nsource_path: -\n"
        f"created: {now.isoformat(timespec='seconds')}\nlessons: 0\n---\n\n"
        f"# SYSTEM_PROMPT 进化提案 {pid}\n\n"
        f"> 谱系：{best.id}（parent={best.parent}, gen={best.gen}）· "
        f"holdout 分数：baseline {baseline_score:.3f} → evolved {best_score:.3f}\n\n"
        f"## 采纳方式\n\n本提案不走 `apply`（apply 仅支持 markdown 追加）。人工审阅下方新 prompt 后，\n"
        f"手动编辑 `skills/skill-evo/scripts/evo_prompt.py` 的 `SYSTEM_PROMPT` 常量替换之。\n\n"
        f"## 新 SYSTEM_PROMPT\n\n```text\n{best.text}\n```\n\n"
        f"## 迭代日志（前 10 条）\n\n```json\n"
        f"{json.dumps(log[1:11], ensure_ascii=False, indent=1)}\n```\n")
    path = paths["pending"] / f"{pid}.md"
    path.write_text(body, encoding="utf-8")
    return path
