---
name: skill-evo
description: >
  会话经验自动总结与规范/技能进化（Hermes 式自进化闭环）。Claude Code 会话结束后由
  SessionEnd hook 异步总结会话，提炼用户纠正/失败模式/成功模式，生成对 skills/*/SKILL.md
  与 steering/*.md 的进化提案（置信度分级、pending 人工审核、只追加不改写、永不自动应用）；
  同时搭车增量扫描 omp（oh-my-pi）会话。数据在 ~/.config/ar/skill-evo/。
  当用户提到：skill-evo、进化提案、审核提案、查看提案、应用提案、驳回提案、会话总结、
  经验沉淀、规范进化、为什么 AI 又犯同样错误时激活。
---

# 会话经验进化 (skill-evo)

把每次会话中「用户纠正 AI / 反复失败后找到正确做法 / 被认可的模式」自动沉淀为
本仓库规范与技能的进化提案。**提取全自动，应用必须人工审核**——这是 Hermes
self-evolution 的核心护栏（一切进化走人工评审，绝不直改）。

## 架构（AI 无需执行，仅理解定位）

```
CC SessionEnd hook（秒退，nohup 后台）
  → scripts/evo.py run
      ├─ 总结当前 CC 会话（headless claude -p，禁 hooks 防递归）
      ├─ 搭车增量扫描 omp 会话（~/.omp/agent/sessions/，state.json 去重）
      └─ 提案落盘 ~/.config/ar/skill-evo/proposals/pending/*.md
人工审核（本 skill 的核心工作流 ↓）
```

## 工作流（人工审核入口）

### 第 1 步：列出待审提案

```bash
python3 scripts/evo.py list
```

输出每个提案的 id、lessons（置信度 + 类型 + 目标文件）与护栏警告。

### 第 2 步：逐条审核

对每个 lesson 核对三点（AI 协助时必须打开提案原文展示）：

1. **证据可追溯**：evidence 是否真出现在来源会话中（防幻觉）
2. **目标合理**：target_file 与 heading 锚点是否是该经验的正确落点
3. **变更得当**：new_text 是否与目标文件既有风格一致、无重复条款

护栏规则（apply 会自动检查，命中则需 `--force`）：
- new_text 含**【强制】**标记 → 强制级别是人工评审决策，自动化只能提【推荐】级内容
- 置信度 Low → 建议先人工核实
- **steering 既有【强制】条款不可被削弱**——v1 仅支持追加（append_under/append_end），
  改写删除类变更一律驳回并等待人工直接编辑规范文件

### 第 3 步：应用或驳回

```bash
# 预演（不落盘，展示将追加的内容与位置）
python3 scripts/evo.py apply <id> --dry-run

# 确认后应用（直接写入目标文件；护栏警告命中时加 --force）
python3 scripts/evo.py apply <id> [--force]

# 驳回
python3 scripts/evo.py reject <id> --reason "证据不足"
```

应用后：
- 变更已写入工作区，**提示用户 `git diff` 检查，满意后自行提交**（本技能永不自动 commit）
- 锚点失配/不唯一时 apply 整体失败不盲写——此时应人工打开目标文件与提案，改由人工编辑

## 配置

`~/.config/ar/skill-evo/config.toml`（可选，零配置即可用），模板见
[`config.example.toml`](config.example.toml)。常用项：`enabled`（总开关，或环境变量
`AR_SKILL_EVO_ENABLED=0`）、`scope_dirs`（只总结哪些目录下的会话）、`omp_max_per_run`、
`min_messages`。

## 设计边界（v1）

- 只做存量文件的**追加**，不做改写/删除，不做「新增 skill」级提案
- 处理过的会话不再重提（state.json 按 id+mtime 去重；SessionEnd 尾部少量丢尾可接受）
- omp 无生命周期 hooks，依赖 CC 会话结束时搭车扫描；omp 会话也可能由
  `evo.py scan-omp` 手动补偿（仅列出，处理仍走 `run`）

## 相关文件

- 核心脚本：[`scripts/evo.py`](scripts/evo.py)（CLI）、[`scripts/evo_session.py`](scripts/evo_session.py)、
  [`scripts/evo_prompt.py`](scripts/evo_prompt.py)、[`scripts/evo_proposal.py`](scripts/evo_proposal.py)、
  [`scripts/evo_config.py`](scripts/evo_config.py)
- hook 入口：[`../../hooks/on-session-end.sh`](../../hooks/on-session-end.sh)
- 设计文档：[`../../docs/design/skill-evo-design.md`](../../docs/design/skill-evo-design.md)
