---
name: work-report
description: >
  跨仓库工作日报/周报自动生成。扫描多个 git 仓库指定时间范围的提交，按业务成果语义聚合
  （非简单罗列），跨仓库合并同一件事，输出 3 种受众模板（自用流水 / 对 leader / 对外汇报），
  默认生成「对 leader」版。配置读取 ~/.config/ar/workspaces.toml，不存在则默认扫描 $HOME/sources。
  当用户提到：工作日报、周报、工作汇报、工作总结、本周工作、最近两周工作、最近做了什么、
  生成日报、跨仓库日报、standup、团队日报、团队产出、成员工作汇总时激活。
---

# 跨仓库工作日报生成 (work-report)

脚本做确定性抓取，AI 做语义聚合（设计论证、模板 B/C/D 正文、团队模式详解、配置示例见
[README](README.md)）。

## 工作流

### 第 1 步：定位配置

1. `~/.config/ar/workspaces.toml`（若存在）—— 模板见 [`workspaces.example.toml`](workspaces.example.toml)，
   各配置项语义见 README「配置」
2. 不存在则用默认：扫描 `$HOME/sources` 下所有 git 仓库，author 取各仓库 `git config user.email`

> **时间范围优先级**：用户对话显式指定 > toml 的 `since`（天数）> 脚本默认 14 天。
> toml 的 `exclude` 逐个转 `--exclude <glob>` 传脚本。

### 第 2 步：运行抓取脚本

> ⚠️ **直接运行脚本，不要逐个仓库手动 git log。** 脚本统一扫描、统一格式、处理
> author 过滤 + WIP 抓取。

```bash
bash scripts/fetch-commits.sh [--since 7] [--author 'a@corp.com\|b@corp.com'] [repo1 repo2 ...]
# 团队模式（每条 commit 附 author email，AI 按成员分组）：加 --team
```

每个有效仓库输出结构化 commit（`日期 | hash | subject`）+ `# WIP:` 进行中信号行
（未推送 commit / 未合并分支 / 工作区改动）。commit 段 → 聚合为「本期成果」；
`# WIP:` 行 → 聚合为「进行中 / 未完成」。

### 第 3 步：AI 语义聚合

| 规则 | 说明 |
|---|---|
| 按**业务成果**聚类 | 不是按 type / 仓库分组；把「订单导出」相关的 feat+fix+refactor 聚成一条 |
| **scope 二级聚类** | 单仓库提交密集（>10 条）时，先以 commit 的 `scope` 作一级聚类信号，再按业务成果二级合并 |
| **跨仓库合并** | 不同仓库服务于同一业务成果的，合并为一条，标注涉及的仓库 |
| 折叠噪音 | `style` / `chore` / 纯 CI 提交合并为「工程优化 N 项」，不逐条列 |
| 统一输出语言 | 无论 commit 原文语言，日报统一用目标模板语言（默认中文） |
| 保留可追溯 | 每条成果附关键 commit 短 hash |

### 第 4 步：套模板输出

默认「对 leader」版，用户可显式指定其他模板：

```markdown
# 工作汇报（{起止日期}）

## 本期成果
1. **{业务成果标题}** —— {一句话价值}
   - 影响：{业务/技术影响}
   - 涉及：{repo1, repo2} {hash1, hash2}

## 进行中 / 未完成
- {仓库}：{当前分支}，未推送 N 个提交 / 未合并分支 / 工作区 M 文件改动

## 风险与阻塞 / 下周计划
- （提交数据无法反映，占位提示用户补充）
```

模板 B 自用流水（仓库+日期全量时间线）/ 模板 C 对外汇报（纯业务语言）/ 模板 D 团队汇总
（`--team` 按成员分组）正文见 [README](README.md#三种受众模板)。

## 原料质量前提

日报质量上限 = commit 质量；`fix`、`update` 类消息聚不出业务含义。与
[`../../steering/git-conventions.md`](../../steering/git-conventions.md) 的 commitlint 互补。
