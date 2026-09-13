---
last-checked: 2026-09-13
re-check-trigger: 新 release / aka.ms/skillopt 发布 sleep 机制论文或方法更新
depth: 仓库级（skill-evo replay-eval 基线 + 2026-09-13 上游快照）
---

# SkillOpt（Microsoft）

## 一句话定位

text-space optimizer：为冻结 LLM agent 训练可复用的自然语言 skill，轨迹驱动编辑 + 验证门控更新，产出可部署的 best_skill.md 工件。

## 事实快照（2026-09-13）

- MIT；2026-05-08 建仓；16,976 stars / 1,590 forks；**仍活跃演化**（最近推送 2026-09-05，40 open issues）
- Python；topics: agent-skills、self-evolving-agents；主页 aka.ms/skillopt

## 可借鉴点

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | Sleep 阶段 replay：历史输入重放给候选 skill，确定性打分（零 LLM、可复现），分数做进化信号 | replay-eval 的机制来源 | ✅ 设计文档对照（skill-evo-replay-eval.md） | 已落地：replay-eval（2026-09-01 实现），见 [skill-evo replay-eval 设计](../design/skill-evo-replay-eval.md) |
| 2 | 验证门控更新（validation-gated updates）+ 防 gaming：打分器绝不进候选空间、打分器改动必须低于 baseline F1 | gauntlet/进化闭环的反 Goodhart 条款范本 | ✅ 同上（铁律 3-5 已吸收） | 已落地：同上 |

## 不适配点 / 否决

- 上游 SkillOpt 的对照结论已在 replay-eval 设计中裁决（"唯一实质差距：缺可自动打分的信号源"，已交付，勿重复）；本次快照未发现推翻该结论的新证据。

## 资源链接

- 仓库：<https://github.com/microsoft/SkillOpt>；主页：<https://aka.ms/skillopt>
- 本仓落地：docs/design/skill-evo-replay-eval.md
