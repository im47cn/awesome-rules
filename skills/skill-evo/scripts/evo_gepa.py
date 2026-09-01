#!/usr/bin/env python3
"""evo_gepa — GEPA 式进化引擎（stdlib 复刻，arXiv 2507.19457）

GEPA = Genetic-Pareto prompt evolution：候选池 + 逐实例最优并集的 Pareto 前沿采样
+ minibatch 执行反思变异 + rollout 预算。executor/reflector 均为可注入回调
（skill-evo 的实现走 headless claude -p），引擎本身不依赖任何 LLM/ML 库。

首个应用：进化 evo_prompt.SYSTEM_PROMPT（lessons 提炼质量），标注来自
applied/rejected 提案（人工审核结果 = 真实标签，reject_reason 是负反馈）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class Case:
    id: str                 # 通常为 <agent>:<session_id>
    inputs: dict            # 应用自定输入（如 transcript_view / target_index）
    reference: dict         # 标注（applied/rejected lessons 与理由）


@dataclass
class Candidate:
    id: str                 # c0, c1, ...
    text: str               # 资产文本（如 SYSTEM_PROMPT 候选）
    parent: Optional[str]   # 谱系
    gen: int


@dataclass
class ScoreMatrix:
    """scores[cid][case_id] -> float（0-1）；缺失 = 未评。"""
    scores: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def set(self, cid: str, case_id: str, score: float) -> None:
        self.scores.setdefault(cid, {})[case_id] = score

    def get(self, cid: str, case_id: str) -> Optional[float]:
        return self.scores.get(cid, {}).get(case_id)

    def cases_of(self, cid: str) -> Dict[str, float]:
        return dict(self.scores.get(cid, {}))

    def mean(self, cid: str) -> float:
        vals = list(self.scores.get(cid, {}).values())
        return sum(vals) / len(vals) if vals else float("-inf")


# ── Pareto（GEPA Algorithm 2：逐实例最优并集 + 支配剔除 + 加权采样）────────

def pareto_front(matrix: ScoreMatrix) -> Dict[str, int]:
    """返回 {cid: 前沿出现次数 f[Φ]}。

    逐 case 取最优（并列都计），得并集前沿；再剔除被支配候选
    （在两者均已评的 case 上处处 ≤ 且存在 <）。
    """
    winners: Dict[str, int] = {}
    case_ids = {c for m in matrix.scores.values() for c in m}
    for case_id in case_ids:
        best = max((matrix.scores[c][case_id] for c in matrix.scores
                    if case_id in matrix.scores[c]), default=None)
        if best is None or best == float("-inf"):
            continue
        for cid, m in matrix.scores.items():
            if case_id in m and m[case_id] == best:
                winners[cid] = winners.get(cid, 0) + 1
    # 支配剔除
    dominated = set()
    for a in winners:
        for b in winners:
            if a == b or b in dominated:
                continue
            sa, sb = matrix.cases_of(a), matrix.cases_of(b)
            common = set(sa) & set(sb)
            if not common:
                continue
            if all(sb[c] >= sa[c] for c in common) and any(sb[c] > sa[c] for c in common):
                dominated.add(a)
                break
    return {cid: n for cid, n in winners.items() if cid not in dominated}


def sample_candidate(front_freq: Dict[str, int], rng: random.Random) -> Optional[str]:
    """按 f[Φ] 加权随机采样前沿候选。"""
    if not front_freq:
        return None
    cids = list(front_freq)
    weights = [front_freq[c] for c in cids]
    return rng.choices(cids, weights=weights, k=1)[0]


# ── 主循环 ─────────────────────────────────────────────────────────────────

# execute: (candidate_text, case) -> (score 0-1, feedback 文本)；feedback 供 reflector
Execute = Callable[[str, Case], Tuple[float, str]]
# reflect: (当前候选, [(case, score, feedback)], 约束说明) -> 变异候选文本
Reflect = Callable[[str, List[Tuple[Case, float, str]], str], str]


def run_gepa(baseline: str, train: List[Case], holdout: List[Case],
             execute: Execute, reflect: Reflect, budget: int,
             batch_size: int = 4, rng_seed: int = 0,
             validate: Optional[Callable[[str], bool]] = None,
             asset_desc: str = "") -> Tuple[Candidate, ScoreMatrix, List[dict]]:
    """GEPA 主循环，rollout 预算 = execute 调用总次数。

    返回 (最优候选, 分数矩阵, 迭代日志)。语义：
    1. baseline 在 train 子集上评分（预算 1/4 上限，防大数据集吃光预算）
    2. 循环：Pareto 采样候选 → minibatch 执行（留 trace/反馈）→ reflect 变异
       → minibatch 上局部接受（均分改善才进池）→ 接受则补评 train 缺口
    3. 预算耗尽后，各候选在 holdout 上各评一次，holdout 均分选优（防择优污染）
    """
    rng = random.Random(rng_seed)
    pool: Dict[str, Candidate] = {"c0": Candidate("c0", baseline, None, 0)}
    matrix = ScoreMatrix()
    log: List[dict] = []
    used = 0

    def _exec(text: str, cid: str, case: Case) -> Tuple[float, str]:
        nonlocal used
        score, feedback = execute(text, case)
        used += 1
        matrix.set(cid, case.id, score)
        return score, feedback

    # 1) baseline 评分（控制规模：min(train, max(batch, budget//4))）
    baseline_cases = rng.sample(train, min(len(train), max(batch_size, budget // 4)))
    for case in baseline_cases:
        if used >= budget:
            break
        _exec(baseline, "c0", case)

    # 2) 进化循环
    while used < budget:
        cid = sample_candidate(pareto_front(matrix), rng)
        if cid is None:
            cid = "c0"
        parent = pool[cid]
        batch = rng.sample(train, min(batch_size, len(train)))
        results: List[Tuple[Case, float, str]] = []
        for case in batch:
            if used >= budget:
                break
            results.append((case, *_exec(parent.text, cid, case)))
        if not results:
            break
        try:
            mutated = reflect(parent.text, results, asset_desc)
        except Exception as e:                       # reflector 失败：丢弃本轮变异
            log.append({"iter": len(log), "parent": cid, "reflected": False,
                        "error": f"{type(e).__name__}: {e}"})
            continue
        if validate and not validate(mutated):
            log.append({"iter": len(log), "parent": cid, "reflected": True,
                        "accepted": False, "reason": "违反候选约束，丢弃"})
            continue
        # minibatch 局部接受（同一批上新旧均分比较）
        new_scores: Dict[str, float] = {}
        new_cid = f"c{len(pool)}"
        for case, _, _ in results:
            if used >= budget:
                break
            s, _ = _exec(mutated, new_cid, case)
            new_scores[case.id] = s
        old_mean = _mean([matrix.get(cid, c.id) or 0.0 for c, _, _ in results])
        new_mean = _mean(list(new_scores.values())) if new_scores else float("-inf")
        entry = {"iter": len(log), "parent": cid, "candidate": new_cid,
                 "old_mean": round(old_mean, 4), "new_mean": round(new_mean, 4)}
        if new_mean > old_mean:
            pool[new_cid] = Candidate(new_cid, mutated, cid, parent.gen + 1)
            entry["accepted"] = True
            # 接受则补评 train 上未评的 case（D_pareto 全量填充，预算内）
            for case in train:
                if used >= budget:
                    break
                if matrix.get(new_cid, case.id) is None:
                    _exec(mutated, new_cid, case)
        else:
            entry["accepted"] = False
            entry["reason"] = "minibatch 均分未改善"
        log.append(entry)

    # 3) holdout 选优（验收信号，独立于 rollout 预算：每候选每 case 只评一次）
    #    c0（baseline）必评作改善锚；其余按 train 均分降序评（预算外不截断）
    holdout_matrix = ScoreMatrix()
    ranked = sorted(pool, key=lambda c: matrix.mean(c), reverse=True)
    ranked = ["c0"] + [c for c in ranked if c != "c0"]
    for cid in ranked:
        for case in holdout:
            score, _ = execute(pool[cid].text, case)
            holdout_matrix.set(cid, case.id, score)
    best = max(pool, key=lambda c: (holdout_matrix.mean(c) if holdout_matrix.cases_of(c)
                                    else float("-inf")))
    return pool[best], matrix, [{"holdout": {c: round(holdout_matrix.mean(c), 4)
                                             for c in holdout_matrix.scores}},
                                *log]


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else float("-inf")
