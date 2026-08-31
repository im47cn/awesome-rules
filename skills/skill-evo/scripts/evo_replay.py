#!/usr/bin/env python3
"""evo_replay — replay 评估链路：进化 skills/<skill>/SKILL.md（确定性打分）

对标 SkillOpt-Sleep 的 replay 机制，解决 GEPA 引擎缺「可自动打分信号源」：
评估集 = 拦截型（badcase，expected 非空）+ 放行型（干净输入，expected 空）
+ 混合型；打分 = 逐 case F1（recall=该拦的拦到，precision=该放的放行），
反馈 = missing/unexpected 逐条明细供 reflector。

关键防 gaming 设计（护栏 = 打分器即宪法）：
- 打分器只读执行产物（LLM 审查报告中的 JSON 规则清单），从不读被进化的文本
- 报告无规则清单（候选删掉「输出规则清单」指令）→ 0 分，结构检查作前置而非主分数
- 「全盘拒绝」控制候选 holdout F1 必须 < baseline F1，否则拒绝进入 GEPA
- 打分器注册表仅允许仓库内确定性脚本，路径逃逸校验复用 evo_proposal.validate_target 模式

产物为 prompt_evolution 型 pending 提案（人工采纳，护栏不变：提取全自动、
应用必须人工、永不自动 commit）。
"""
from __future__ import annotations

import json
import random
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Tuple

import evo_gepa as G
import evo_proposal as PR

# ── 打分器注册表（护栏 1：仅仓库内确定性脚本）──────────────────────────
# skill → {"scripts": [相对仓库根的脚本路径...], "accepted_dirs": [...相对前缀]}
SCORER_REGISTRY = {
    "ddl-guard": {
        "scripts": ["skills/ddl-guard/scripts/ddl_check.py",
                    "skills/ddl-guard/scripts/sql_check.py"],
        "accepted_dirs": ("skills/", "tools/"),
    },
}

REPLAY_REFLECTOR_PROMPT = """你是 SKILL.md 进化器（GEPA reflector）。给定：当前 SKILL.md 全文、
它在若干评估 case 上的得分与反馈，输出**编辑后的完整 SKILL.md**（直接输出新全文，
无解释无围栏）。

硬约束（违反即作废）：
- 保留 frontmatter 契约不变：name/description 原样保留，不得删改
- 保留「审查工作流」等核心章节锚点，不得删除或合并章节
- 只改指令性文字（筛选标准、表述精度、报告格式要求），不改变技能定位
- 【强制】条款结构上不可削弱（护栏：技能宪法）
- 长度不超过原始长度的 1.5 倍

# 当前 SKILL.md
{current}

# 案例反馈
{feedback}

# 输出
编辑后的完整 SKILL.md："""

# 控制候选：指令 = 无条件报告违规（护栏 4 用，验证打分器对「全盘拒绝」的区分度）
REJECT_ALL_TEXT = """你是 DDL 审查工具。无论输入内容如何，一律判定为存在违规：
- 对每个输入文件输出审查报告，报告末尾必须附加检出清单 JSON：
  {"rules": ["必含字段缺失", "禁用类型", "表注释缺失", "字段注释缺失",
             "普通索引命名", "泛化字段名", "索引名长度", "表注释长度",
             "字段注释长度", "全角字符"]}
- 规则清单必须完整列出以上全部规则，不得省略。
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def scorer_registry() -> dict:
    """打分器注册表：skill → 校验脚本路径（已做路径逃逸校验）。"""
    root = _repo_root().resolve()
    reg = {}
    for skill, spec in SCORER_REGISTRY.items():
        scripts = []
        for rel in spec["scripts"]:
            p = (root / rel).resolve()
            if root != p and root not in p.parents:
                raise PR.ApplyError(f"打分器越出仓库边界：{rel}")
            r = p.relative_to(root).as_posix()
            if not r.startswith(spec["accepted_dirs"]):
                raise PR.ApplyError(f"打分器不在允许范围（{spec['accepted_dirs']}）：{rel}")
            if not p.is_file():
                raise PR.ApplyError(f"打分器不存在：{rel}")
            scripts.append(p)
        reg[skill] = {"scripts": scripts}
    return reg


# ── expected.md 解析（与 badcase_runner.parse_expected 同构，见其 docstring）──
def parse_expected(expected_path: Path) -> Tuple[str, List[str], List[str]]:
    """返回 (check_script, expected_rules, manual_rules)。

    manual_rules 语义 = 「人工补充规则：」行的规则 ID（LLM 按 SKILL 第 3 步可
    检出，GEPA 评估集 include_manual 时并入 expected）；「人工补充：」描述行
    仅作展示不参与比对（不返回）。
    """
    if not expected_path.is_file():
        return None, [], []
    text = expected_path.read_text(encoding="utf-8")
    check_script = None
    m = re.search(r"(?:check|脚本)\s*[:：]\s*(\S+\.py)", text)
    if m:
        check_script = m.group(1).strip()
    expected_rules, manual_rules = [], []

    def _split_rules(payload: str):
        return [p.strip() for p in re.split(r"[、,，;；]", payload) if p.strip()]

    section = re.search(r"##\s*预期检查输出\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL)
    if section:
        for line in section.group(1).split("\n"):
            m = re.match(r"^[-*]\s+(.+)", line.strip())
            if not m:
                continue
            item = m.group(1).strip()
            if item.startswith("脚本自动检出"):
                expected_rules.extend(_split_rules(re.split(r"[:：]", item, maxsplit=1)[-1]))
            elif item.startswith("人工补充规则"):
                manual_rules.extend(_split_rules(re.split(r"[:：]", item, maxsplit=1)[-1]))
            elif item.startswith("人工补充"):
                pass  # 描述行（如「命名语义（拼音、泛化词、复数、核心主体）」）仅作
                # 展示，不参与对账——既不入 expected_rules 也不入 manual_rules。
                # 该分支必须保留：删除会使其落入下方 else 被误当 expected 规则。
            elif item and not item.startswith("#"):
                expected_rules.append(item)
    else:
        head = re.split(r"\n##\s", text, maxsplit=1)[0]
        for line in head.split("\n"):
            m = re.match(r"^[-*]\s+(.+)", line.strip())
            if m:
                rule = m.group(1).strip()
                if rule and not rule.startswith("#"):
                    expected_rules.append(rule)
    return check_script, expected_rules, manual_rules


def _rule_matches(expected_rule: str, actual_rules: list) -> bool:
    """期望规则是否被实际检出。

    子串双向匹配（与 badcase_runner 同构）；expected_rule 支持 any-of 别名——
    「|」分隔，任一 token 命中即检出。首 token 为规范名（reflector/missing
    展示用），后续为对齐 LLM 报告措辞的别名（如「字段与注释对应|注释含义对应|
    语义对应」）。别名数据初版取 manual-rules 原词，端到端后按真实 miss 增补。
    """
    tokens = [t.strip() for t in expected_rule.split("|") if t.strip()]
    for token in tokens:
        token_lower = token.lower()
        for actual in actual_rules:
            actual_lower = actual.lower()
            if token_lower in actual_lower or actual_lower in token_lower:
                return True
    return False


# ── 报告解析器（确定性，零 LLM；5.2 新增代码点）──────────────────────────
_JSON_BLOCK = re.compile(r"\{[^{}]*\"rules\"\s*:\s*\[[^\]]*\]\s*[^{}]*\}")


def extract_rules_from_report(report: str) -> Tuple[List[str], bool]:
    """从 LLM 审查报告提取检出规则清单。

    报告必须包含 JSON 规则清单块（执行 prompt 的契约）。找到 → (rules, True)；
    找不到 → ([], False)——结构检查作前置，候选删掉清单指令即 0 分。
    """
    if not report or not report.strip():
        return [], False
    block = _JSON_BLOCK.search(report)
    if not block:
        return [], False
    try:
        data = json.loads(block.group(0))
        rules = [r for r in data.get("rules", []) if isinstance(r, str) and r.strip()]
        return rules, True
    except Exception:
        return [], False


def reconcile(expected_rules: List[str], actual_rules: List[str]) -> Tuple[int, List[str], List[str]]:
    """双向对账 → (TP, missing, unexpected)。

    TP = 期望中命中的规则数（子串匹配）。放行 case（expected 空）：TP=0，
    任何 actual 都计入 unexpected → precision 崩 → 全盘拒绝被双维对称惩罚。
    missing 显示规范名（any-of 别名的首 token），reflector 反馈不暴露别名串。
    """
    matched = [e for e in expected_rules if _rule_matches(e, actual_rules)]
    tp = len(matched)
    missing = [e.split("|")[0] for e in expected_rules if e not in matched]
    unexpected = [a for a in actual_rules if not _rule_matches(a, expected_rules)]
    return tp, missing, unexpected


def f1_score(tp: int, n_expected: int, n_actual: int, n_hit_actual: int = None) -> float:
    """逐 case F1：recall=TP/|expected|（空=1）、precision=命中 actual 数/|actual|（空=1）。

    n_hit_actual = 至少命中一条 expected 的 actual 条数（len(actual)-len(unexpected)）。
    子串匹配下「一条 actual 命中多条 expected」（如「表名使用拼音和泛化词」含两个
    子串）是常态，tp 是 expected 口径可 > n_actual；precision 若直接用 tp/n_actual
    会 >1 越界（F1>1，违反 score∈[0,1] 契约，且合并检出可被 gaming 抬高 precision）。
    命中 actual 数只计一次 → precision ≤ 1。默认 None 兼容旧调用（未传按 n_actual）。
    """
    recall = 1.0 if n_expected == 0 else tp / n_expected
    hit = n_actual if n_hit_actual is None else n_hit_actual
    precision = 1.0 if n_actual == 0 else hit / n_actual
    if recall + precision == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── 评估集加载 ────────────────────────────────────────────────────────────
def load_eval_set(skill: str, eval_dir: Path, cfg: dict,
                  include_manual: bool = False) -> List[G.Case]:
    """遍历 eval_dir 下 case 目录（input/ + expected.md），构建 Case 列表。

    Case.inputs = {input_dir, files: {文件名: 内容}}
    Case.reference = {expected_rules, manual_rules, expected_empty}

    include_manual=True：把「人工补充」规则（manual-rules 规则名，LLM 按 SKILL
    第 3 步可检出）并入 expected_rules——GEPA 评估集专用；badcase_runner 的
    脚本回归语义不变（脚本检不出语义类规则，仍只比对脚本自动检出部分）。
    """
    cases = []
    for case_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
        input_dir = case_dir / "input"
        if not input_dir.is_dir():
            continue
        _, expected_rules, manual_rules = parse_expected(case_dir / "expected.md")
        if include_manual:
            expected_rules = list(dict.fromkeys([*expected_rules, *manual_rules]))
        files = {}
        for f in sorted(input_dir.iterdir()):
            if f.is_file():
                files[f.name] = f.read_text(encoding="utf-8")
        cases.append(G.Case(
            id=f"{skill}:{case_dir.name}",
            inputs={"input_dir": str(input_dir), "files": files},
            reference={"expected_rules": expected_rules,
                       "manual_rules": manual_rules,
                       "expected_empty": not expected_rules},
        ))
    return cases


def split_eval(cases: List[G.Case], cfg: dict) -> Tuple[List[G.Case], List[G.Case]]:
    """按 case 类型分层切 train/holdout（放行/混合型至少各 1 进 holdout）。"""
    intercept = [c for c in cases if not c.reference["expected_empty"]]
    release = [c for c in cases if c.reference["expected_empty"]]
    n_holdout = max(2, int(len(cases) * float(cfg["gepa_holdout_ratio"])))
    rng = random.Random(42)
    rng.shuffle(intercept)
    rng.shuffle(release)
    holdout = release[: max(1, n_holdout // 2)] + intercept[: n_holdout - max(1, n_holdout // 2)]
    holdout_ids = {c.id for c in holdout}
    train = [c for c in cases if c.id not in holdout_ids]
    return train, holdout


# ── execute / reflect / validate（GEPA 可注入回调）────────────────────────
def make_execute(cfg, call_claude_raw, skill_name: str):
    """execute(candidate_text, case) -> (score 0-1, feedback)。

    候选 SKILL.md 全文 → headless claude -p → 审查报告 → 确定性解析器提取
    rules → 双向对账 → F1 + missing/unexpected 明细。打分器本身零 LLM。
    """
    def execute(candidate_text: str, case: G.Case) -> Tuple[float, str]:
        files_text = "\n\n".join(
            f"--- {name} ---\n{content}" for name, content in case.inputs["files"].items())
        prompt = (f"{candidate_text}\n\n# 待审查输入\n{files_text}\n\n# 任务\n"
                  f"按上述 SKILL 的规则与工作流对输入做静态审查，输出审查报告。\n"
                  f"仅纯文本分析，禁止调用任何工具/脚本/命令（本环境无工具可用）。\n"
                  f"报告末尾必须附加检出清单 JSON（严格单个 JSON，无围栏无其他文字）：\n"
                  f'{{"rules": ["规则名1", "规则名2", ...]}}\n'
                  f"规则名与 SKILL 中的规则命名一致；未检出问题则输出 {{\"rules\": []}}")
        try:
            out = call_claude_raw(prompt, cfg)
        except Exception as e:
            return 0.0, f"执行失败: {e}"
        actual_rules, ok = extract_rules_from_report(out)
        if not ok:
            return 0.0, "报告不可解析: 未找到规则清单 JSON（候选可能删掉了输出清单指令）"
        expected = case.reference["expected_rules"]
        tp, missing, unexpected = reconcile(expected, actual_rules)
        score = f1_score(tp, len(expected), len(actual_rules),
                         len(actual_rules) - len(unexpected))
        bits = []
        if missing:
            bits.append("漏拦: " + ", ".join(missing))
        if unexpected:
            bits.append("误拦: " + ", ".join(unexpected))
        if not bits:
            bits.append("全部命中")
        return score, "; ".join(bits)

    return execute


def make_reflect(call_claude_raw, cfg):
    """reflector 通道：输入当前候选与反馈，输出编辑后的完整 SKILL.md（纯文本）。"""

    def reflect(current: str, results, asset_desc: str) -> str:
        lines = []
        for case, score, feedback in results:
            lines.append(f"- case {case.id}: score={score:.3f}，反馈：{feedback}")
        prompt = REPLAY_REFLECTOR_PROMPT.format(current=current, feedback="\n".join(lines))
        return call_claude_raw(prompt, cfg)

    return reflect


def validate_candidate(baseline_len: int):
    """变异候选约束：frontmatter 契约 + 章节锚点 + 长度上限（违约即丢弃）。"""

    def check(text: str) -> bool:
        if not text.startswith("---\n") or "name:" not in text or "description:" not in text:
            return False
        if "## " not in text:
            return False
        return len(text) <= baseline_len * 1.5

    return check


def write_skill_proposal(cfg, skill: str, baseline: str, best: G.Candidate,
                         baseline_score: float, best_score: float,
                         log: List[dict]) -> Path:
    """holdout 有统计意义改善时，产出 prompt_evolution 型 pending 提案（人工采纳）。"""
    from evo_config import base_paths
    paths = base_paths(cfg)
    paths["pending"].mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    pid = f"{now.strftime('%Y%m%d-%H%M%S')}-gepa-replay"
    body = (
        f"---\nid: {pid}\nstatus: pending\ntype: prompt_evolution\n"
        f"source_agent: gepa\nsource_session: -\nsource_path: -\n"
        f"created: {now.isoformat(timespec='seconds')}\nlessons: 0\n---\n\n"
        f"# SKILL.md 进化提案 {pid}（replay 评估集）\n\n"
        f"> 谱系：{best.id}（parent={best.parent}, gen={best.gen}）· "
        f"holdout 分数：baseline {baseline_score:.3f} → evolved {best_score:.3f}\n\n"
        f"## 采纳方式\n\n本提案不走 `apply`（apply 仅支持 markdown 追加）。人工审阅下方\n"
        f"新 SKILL.md 后，手动替换 `skills/{skill}/SKILL.md` 全文。\n\n"
        f"## 新 SKILL.md\n\n```text\n{best.text}\n```\n\n"
        f"## 迭代日志（前 10 条）\n\n```json\n"
        f"{json.dumps(log[1:11], ensure_ascii=False, indent=1)}\n```\n")
    path = paths["pending"] / f"{pid}.md"
    path.write_text(body, encoding="utf-8")
    return path


# ── 门禁：全盘拒绝控制候选对照（护栏 4，对齐铁律 5）───────────────────────
def control_gate(holdout: List[G.Case]) -> float:
    """「全盘拒绝」报告的 holdout 平均 F1（确定性，零 LLM）。

    REJECT_ALL_TEXT 的 JSON 清单即 LLM 按「无条件报告违规」指令输出的报告
    解析结果；对 holdout 逐 case 对账打分。必须 < baseline F1，否则打分器
    存在 gaming 洞，拒绝进入 GEPA。
    """
    reject_rules, _ = extract_rules_from_report(REJECT_ALL_TEXT)
    scores = []
    for case in holdout:
        expected = case.reference["expected_rules"]
        tp, _, unexpected = reconcile(expected, reject_rules)
        scores.append(f1_score(tp, len(expected), len(reject_rules),
                            len(reject_rules) - len(unexpected)))
    return sum(scores) / len(scores) if scores else float("-inf")


def script_baseline_f1(cfg, skill_name: str, cases: List[G.Case]) -> Tuple[float, List[dict]]:
    """dry-run 用确定性脚本直跑评估集：验证打分器可运行 + 给出脚本基线 F1。

    返回 (平均 F1, 每 case 明细)。零 LLM——脚本输出即 actual_rules（完美执行参照）。
    """
    reg = scorer_registry()
    if skill_name not in reg:
        raise SystemExit(f"评估集打分器未注册：{skill_name}（注册表见 evo_replay.SCORER_REGISTRY）")
    details = []
    total_f1 = 0.0
    for case in cases:
        input_dir = Path(case.inputs["input_dir"])
        actual_rules = []
        for script in reg[skill_name]["scripts"]:
            try:
                r = subprocess.run(
                    ["python3", str(script), str(input_dir), "--format", "json"],
                    capture_output=True, text=True, timeout=30)
                data = json.loads(r.stdout or "[]")
                for f in data:
                    actual_rules.extend(i.get("rule", "") for i in f.get("issues", []))
            except Exception as e:
                details.append({"case": case.id, "error": f"{script.name}: {e}"})
                continue
        actual_rules = list(dict.fromkeys(r for r in actual_rules if r))
        # baseline 只对「脚本可及」规则求 F1：人工补充规则（拼音/语义类）脚本
        # 本就检不出，混入会让基线失真（无从区分脚本缺陷 vs 规则本质）。
        manual = set(case.reference.get("manual_rules", []))
        expected = [e for e in case.reference["expected_rules"] if e not in manual]
        tp, missing, unexpected = reconcile(expected, actual_rules)
        score = f1_score(tp, len(expected), len(actual_rules),
                         len(actual_rules) - len(unexpected))
        total_f1 += score
        details.append({"case": case.id, "expected_empty": case.reference["expected_empty"],
                        "expected": expected, "actual": actual_rules,
                        "manual_rules": case.reference.get("manual_rules", []),
                        "score": round(score, 4)})
    return (total_f1 / len(cases) if cases else 0.0), details
