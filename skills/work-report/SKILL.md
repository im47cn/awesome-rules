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

把散落在多个仓库的 commit，压缩成有业务语义的工作汇报。

## 为什么是 skill 而非脚本

纯脚本只能罗列 commit；「47 条 commit → 5 条业务成果」是语义压缩，是 AI 的活。
本 skill 分两层：**脚本**做确定性抓取，**AI** 做语义聚合。

## 工作流

### 第 1 步：定位配置

按优先级读取仓库清单与 author：

1. `~/.config/ar/workspaces.toml`（若存在）—— 参考模板 [`workspaces.example.toml`](workspaces.example.toml)
2. 不存在则用默认：扫描 `$HOME/sources` 下所有 git 仓库，author 取各仓库 `git config user.email`

> **时间范围优先级**：用户当前对话显式指定（「本周」「最近一个月」）> toml 的 `since`（天数）> 脚本默认 14 天。AI 将天数转为 `--since <N>` 传给脚本。
> 读取 toml 的 `exclude` 列表后，逐个作为 `--exclude <glob>` 传给脚本，排除个人项目 / 第三方 clone / 已归档仓库。

### 第 2 步：运行抓取脚本

脚本位于本 SKILL.md 同级的 `scripts/` 子目录。请按本文件实际路径定位脚本：

```bash
# 默认：2 周 + $HOME/sources + 各仓库 git author
bash scripts/fetch-commits.sh

# 精细控制（读 toml 后传入）
bash scripts/fetch-commits.sh --since 7 \
  --author 'a@corp.com\|b@corp.com' \
  /path/to/repo1 /path/to/repo2
```

每个有效仓库输出一段结构化 commit（`日期 | hash | subject`），并附一行 `# WIP:` 进行中信号：

```
## 仓库: /path/to/repo
2026-08-09 | 057e9b2 | feat: ...
# WIP: 分支=feature/x | 未推送=2 | 未合并分支=fix/a | 工作区=3文件
  - 修登录超时
  - 补单元测试
```

- commit 段 → 聚合为「本期成果」
- `# WIP:` 行 → 聚合为「进行中 / 未完成」（未推送 commit / 未合并分支 / 工作区改动作为近似信号）

> ⚠️ **直接运行脚本，不要逐个仓库手动 git log。** 脚本统一扫描、统一格式、处理 author 过滤 + WIP 抓取。

### 第 3 步：AI 语义聚合

对脚本输出的 commit，按以下规则聚合：

| 规则 | 说明 |
|---|---|
| 按**业务成果**聚类 | 不是按 type / 仓库分组；把「订单导出」相关的 feat+fix+refactor 聚成一条 |
| **scope 二级聚类** | 单仓库提交密集（>10 条）时，先以 commit 的 `scope` 作一级聚类信号，再按业务成果二级合并。scope 规范越好，聚类越准 |
| **跨仓库合并** | 不同仓库服务于同一业务成果的，合并为一条，标注涉及的仓库 |
| 折叠噪音 | `style` / `chore` / 纯 CI 提交合并为「工程优化 N 项」，不逐条列 |
| 统一输出语言 | 无论 commit 原文语言，日报统一用目标模板语言（默认中文）输出 |
| 保留可追溯 | 每条成果附关键 commit 短 hash，便于追溯 |

### 第 4 步：套模板输出

默认输出「对 leader」版。用户可显式指定其他模板。

#### 模板 A：对 leader（默认）

```markdown
# 工作汇报（{起止日期}）

## 本期成果
1. **{业务成果标题}** —— {一句话价值}
   - 影响：{业务/技术影响}
   - 涉及：{repo1, repo2} {hash1, hash2}
2. ...

## 进行中 / 未完成
- {仓库}：{当前分支}，未推送 N 个提交 / 未合并分支 / 工作区 M 文件改动
  - 最近未推送：{subject1}、{subject2}
- （结合用户口述补充）

## 风险与阻塞
- （提交数据无法反映，依赖用户补充）

## 下周计划
- （占位，提示用户补充）
```

#### 模板 B：自用流水

```markdown
# 工作日志（{起止日期}）

## {仓库1}
- {date} {hash} {subject}
- ...

## {仓库2}
- ...
```

按仓库 + 日期时间线，全量保留，技术细节完整。

#### 模板 C：对外汇报

```markdown
# 阶段进展（{起止日期}）

- {业务里程碑 1}：{对用户/客户的价值}
- {业务里程碑 2}：...
```

纯业务语言，屏蔽 hash / type / 仓库等技术细节。

## 团队模式（TL 视角）

TL 抓团队成员近 N 天的工作，两种输出：

| 诉求 | 做法 |
|---|---|
| **团队整体产出**（向上汇报） | `authors` 配团队成员 email，用模板 A——多人 commit 按业务成果聚类 |
| **每人产出**（按成员分组） | 加 `--team`，用模板 D——按 author 分组 |

### 抓取（--team）

```bash
# 读 toml 的 members 配置后传入团队成员
bash scripts/fetch-commits.sh --team --since 14 \
  --author 'alice@corp.com\|bob@corp.com\|carol@corp.com'
```

`--team` 让每条 commit 附 author email（`email | date | hash | subject`），AI 据此按成员分组。`--author` 传团队成员（正则 `\|` 连接），不传则抓所有人。

### 模板 D：团队汇总（按成员分组）

```markdown
# 团队工作汇总（{起止日期}）

## {成员A 姓名}
### 本期成果
- {业务成果}（{repo} {hash}）
### 进行中
- {WIP 信号摘要}

## {成员B 姓名}
### 本期成果
- ...

## 团队整体观察
- **产出聚焦**：{谁聚焦什么域}
- **进行中分布**：{谁在做什么}

> ⚠️ 仅反映编码产出，不含 code review / 方案设计 / 线上排查 / 跨团队沟通
```

### 成员映射（[[members]]）

git author 可能不规范或多 email。配 `[[members]]` 做 email→姓名映射，输出用真名：

```toml
[[members]]
email = "alice@corp.com"
name = "张三"
```

未映射的成员用 email 原样显示。

> **方法论提醒**：git commit 只反映编码，严重低估 review / 设计 / 排查 / 沟通等非编码贡献。团队汇总适合「产出盘点」，不适合个人绩效量化（Goodhart：一旦用于考核，commit 会变碎变多，指标失效）。

## 配置文件

`~/.config/ar/workspaces.toml`（可选，零配置即可用）：

```toml
# 多身份（公司账号 + 个人邮箱，解决 squash 后 author 变 bot 的问题）
authors = ["you@corp.com", "you@personal.com"]

# 扫描目录（默认 ~/sources）
scan_dirs = ["~/sources"]

# 扫描时间范围（默认 14；单位天）
since = 14

# 排除目录/项目（glob，匹配仓库名或路径片段）—— 排除个人项目 / 第三方 clone
exclude = ["target"]

# 团队成员映射（TL 团队模式用，email → 姓名；未配则用 email 原样显示）
[[members]]
email = "alice@corp.com"
name = "张三"

# 显式声明仓库 + 业务域（可选，提升聚类质量）
[[repos]]
path = "~/sources/order-service"
domain = "订单域"
```

> `authors` 与 `[[repos]]` 任选其一或组合；都不写则用默认扫描 + 各仓库 git author。

## 原料质量前提

日报质量上限 = commit 质量。`fix`、`update` 这类无意义消息聚不出业务含义。
本 skill 与 [`tools/git`](../../tools/git/README.md) 的 commitlint 互补——后者保证原料合格，本 skill 消费原料。

## 相关文件

- 抓取脚本：[`scripts/fetch-commits.sh`](scripts/fetch-commits.sh)
- 配置模板：[`workspaces.example.toml`](workspaces.example.toml)
- 提交规范（原料来源）：[`../../steering/git-conventions.md`](../../steering/git-conventions.md)
