# sourcery-autofix — Sourcery AI 审查自动修复技能

> SKILL.md 是给 agent 的操作指引（触发后载入）；本 README 给人看：设计背景、实测证据、分发关系。

## 为什么有这个技能

wop-java-sdk 实践（`sourcery-review-gate.yml`）确立了「`sourcery review --check` 合并门禁 + 评论清零」契约：PR 存在未解决 issue 即禁止合并。该契约的痛点是**拦截发生在远端**——红叉后人工/AI 逐条修，往返成本高。本技能把修复前移到提交前：agent 主动跑 `review --fix` + 修复纪律，gate 只做兜底。

## 红线（修复纪律，先于命令）

1. fix 后必须全量测试（"safe refactor"只是假设，测试是唯一裁判）；
2. fix 的 diff 必须人过目（simplify 类重构会折掉防御性显式代码）；
3. 剩余 issue 必须闭环（修复或评审后进保留清单），禁 `--disable` 压制。

## 实测证据（2026-08，sourcery 1.45.0）

| 实验 | 结果 |
|---|---|
| Python `if/return` 三行 | `--fix` 折成三元表达式（`assign-if-exp`+`reintroduce-else` 均自动修复）——同时证明过目红线的必要性 |
| Python 未用变量（无登录态） | 未检出——free CLI 规则集受限 |
| Java 未用变量 + 多余 else（无登录态） | `No issues detected`——**非 Python 的 fix 能力不可依赖** |

结论：`--fix` 的修复面 = 检出面 ∩ 可自动修复项，且检出面随登录态/订阅扩大。技能对非 Python 剩余项直接走人工闭环，不反复重试。

## 与 lefthook 硬闸的关系

| 层 | 载体 | 约束力 |
|---|---|---|
| 修复纪律（本技能） | `skills/sourcery-autofix/SKILL.md` | 软约束：agent 遵循度依赖模型 |
| pre-push 硬闸 | `tools/git/lefthook/sourcery-gate.sh`（经 install.sh 分发到业务项目 `.lefthook/`） | 硬约束：push 时 `review --check` 非零即拦 |

opt-in 语义：硬闸仅当仓库根存在 `.sourcery.yaml` 时启用——未 opt-in 的项目
（即使装了 sourcery CLI）不会被默认规则集突袭拦截；配置文件同时是评审保留
清单的载体，声明即表示团队接受 sourcery 审查契约。

## 已知边界

- sourcery 检出与修复能力依赖登录态/订阅，无 token 时规则集显著收窄；
- `.sourcery.yaml` 保留清单是评审产物，本技能不自动增删清单条目（人工评审后改）。
