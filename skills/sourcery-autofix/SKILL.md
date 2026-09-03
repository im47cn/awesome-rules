---
name: sourcery-autofix
description: >
  Sourcery AI 审查 issue 自动修复循环。当用户提到以下任意意图时激活：
  sourcery 修复、sourcery issue 清零、审查意见自动修复、AI 审查自动修复、
  sourcery review --fix、sourcery gate 红叉、合并门禁拦截修复、review --check
  失败响应。提供：变更文件的修复循环（fix → 全量测试 → diff 人过目 →
  剩余项闭环）与 CI gate 失败的标准响应动作。
---

# Sourcery AI 审查自动修复

## 红线（先于一切工作）

1. **fix 后必须测试**：`--fix` 产生任何 diff → 立即跑该项目**全量**测试，
   不许只信 sourcery 的"safe refactor"声明；
2. **diff 必须人过目**：`--fix` 的典型动作是折三元 / 删 else / 内联赋值类
   simplify——对防御性显式代码是品味破坏，agent 不得 fix 后直接 commit，
   必须展示 diff 等人确认；
3. **剩余项必须闭环而非绕过**：fix 后仍存活的 issue 逐条二选一——修复，
   或经评审进 `.sourcery.yaml` 保留清单；禁 `--disable` 临时压制。

## 工作流

### 场景 1：提交前主动修复循环

1. **圈定范围**：合并 `git diff --name-only <base>...HEAD`（已提交）、
   `git diff --cached --name-only`（暂存）、`git diff --name-only`（工作区）
  三源去重，过滤 `.py|.ts|.js`（CLI 实测支持面——php 等 CLI 静默不扫，
  喂入 fix 循环会以 check exit 0 虚假闭环，见 sourcery-gate.sh 头注释）
  且排除已删除文件；
   全仓扫描禁止（翻历史 issue 噪音）；
2. **同配置**：仓库有 `.sourcery.yaml` 必须 `--config .sourcery.yaml`——
   本地、CI gate、sourcery-ai[bot] 三方同引擎同配置，否则本地修的 gate 不认；
3. 执行 `sourcery review --fix --config .sourcery.yaml <files>`；
4. fix 产生了 diff → **探测测试命令**（pom.xml→`mvn verify`；
   pyproject/pytest 配置→`pytest`；package.json `scripts.test`→`npm test`；
   均无→明确告知未探测到）；成功探测到命令后立即跑全量测试，不等待用户确认；
5. `git diff` 展示 fix 全部改动，等人确认（红线 2）；
6. 复跑 `sourcery review --check <files>`：exit 0 = 清零；否则列出剩余
   issue 进闭环（红线 3）。

### 场景 2：gate 红叉响应

检测到 `sourcery-review-gate` workflow 失败、或 CI 日志/PR 评论含
sourcery issue → 按场景 1 完整循环修复，以 `sourcery review --check`
exit 0 收尾后重新 push。

## 边界

- `--fix` 能力 **Python 最全**；无登录态 CLI 对 Java 连未用变量都检不出
  （实测 2026-08）——非 Python 的剩余项大概率走人工修复，不要反复重试 fix；
- review 输出概览区分「could be fixed by Sourcery」与「need to be fixed
  manually」，后者直接进闭环条款；
- 硬闸为 **opt-in 门禁**：仅当仓库根存在 `.sourcery.yaml` 才启用（主动声明，
  同 wop-java-sdk gate 模式）；未 opt-in / 未装 CLI / 无支持语言文件均跳过
  （支持面=CLI 实测 py/ts/js，见 sourcery-gate.sh 头注释）；
