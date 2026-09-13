---
last-checked: 2026-09-13
re-check-trigger: 仓库恢复活跃（2026-06-17 后出现新 commit/release），或 hermes-agent 本体护栏机制更新
depth: 仓库级（skill-evo 设计基线 + 2026-09-13 上游快照）
---

# hermes-agent-self-evolution（NousResearch）

## 一句话定位

Hermes Agent 的进化式自我改进组件：用 DSPy + GEPA 优化 skills、prompts 与代码，session 挖掘 + PR 人工审核护栏。

## 事实快照（2026-09-13）

- Python；2026-03-09 建仓；5,321 stars / 630 forks
- **最近推送 2026-06-17，已近 3 个月无活动（趋冷）**；skill-evo 设计文档基线（2026-08-18）晚于其最后推送，既有结论仍新鲜

## 可借鉴点

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | session 挖掘 → 经验提取 → 资产进化，**应用提案必须人工审核（绝不直改）** | skill-evo 的护栏范式来源 | ✅ 设计文档对照（skill-evo-design.md §1-2） | 已落地：skill-evo（见 [skill-evo 技术设计](../design/skill-evo-design.md)，已实现） |
| 2 | 任务后自主创建/改进 skill（hermes-agent 本体行为） | skill-evo 的自动触发设计来源 | ✅ 同上 | 已落地：同上（v2 omp 原生触发） |

## 不适配点 / 否决

- 无新增否决；上游趋冷本身是跟进降权理由，不构成对已落地机制的影响。

## 资源链接

- 仓库：<https://github.com/NousResearch/hermes-agent-self-evolution>
- 本仓落地：docs/design/skill-evo-design.md
