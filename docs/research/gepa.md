---
last-checked: 2026-09-13
re-check-trigger: arXiv 出 v3，或 gepa-ai/gepa 引擎大版本重构，或 ICLR 2026 正式版发布
depth: 论文级（摘要 + 版本沿革）
---

# GEPA（arXiv 2507.19457）

## 一句话定位

Genetic-Pareto 提示优化器：从轨迹反思中诊断问题迭代改进提示，并从 Pareto 前沿融合互补经验；实验上平均超 GRPO 约 6%、超 MIPROv2 超 10%。

## 事实快照（2026-09-13）

- **v1：2025-07-25；v2（最新）：2026-02-14**；被 **ICLR 2026 接收（Oral）**
- 作者 17 人（Khattab/Stoica/Zaharia 等）；官方代码 <https://github.com/gepa-ai/gepa>

## 可借鉴点

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | 反思式进化：run_gepa(baseline, train, holdout, execute, reflect, budget) 引擎与资产解耦、冷启动保护（<10 案例拒绝运行）、变异候选 validate 拦截 | skill-evo 的进化引擎哲学来源 | ✅ 引擎已复刻并测试 | 已落地：`skills/skill-evo/scripts/evo_gepa.py`（stdlib 复刻 arXiv 2507.19457），见 [skill-evo 技术设计](../design/skill-evo-design.md) §6.2 |
| 2 | v2（2026-02-14）与 ICLR 2026 Oral 版的内容增量 | `evo_gepa.py` 复刻基线是 v1 还是 v2 未核实；若为 v1，是否吸收 v2 增量待裁决 | ⚠️ 仅确认版本存在 | 未裁决（需 diff v1/v2 后再评估） |

## 不适配点 / 否决

- 论文任务域（数学/代码 benchmark）与本仓场景不同，数字结论不直接引用；仅吸收引擎结构。

## 资源链接

- 论文：<https://arxiv.org/abs/2507.19457>；代码：<https://github.com/gepa-ai/gepa>
- 本仓落地：skills/skill-evo/scripts/evo_gepa.py；docs/design/skill-evo-design.md
