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

omp 原生 hook（可选安装，session_shutdown 即时触发，见下节）
  → scripts/evo.py run --agent omp --cwd <cwd>（搭车扫描保留作兜底）

GEPA 进化引擎（手动低频，见「进化自身」一节）
```

## omp 原生触发（可选安装）

omp 会话结束即时总结，不依赖 CC 会话搭车（避免「只用 omp 时经验滞后积累」）：

```bash
cp hooks/omp/skill-evo.ts ~/.omp/agent/hooks/pre/
```

- omp 自动发现用户级 hook；会话结束（`session_shutdown`）fire-and-forget 调用
  `evo.py run --agent omp --cwd <cwd>`（会话文件由 Python 按 cwd+mtime 定位）
- 脚本路径默认 `~/sources/awesome-rules/...`，可用环境变量 `AR_SKILL_EVO_SCRIPT` 覆盖
- 与 CC 搭车扫描并存无害（state.json 增量去重收敛）；防递归链：
  omp → evo.py（`AR_SKILL_EVO_CHILD=1`）→ claude -p（继承标记）→ CC hook 见标记即退
- 验证：安装后结束一个 omp 会话，`~/.config/ar/skill-evo/logs/evo.log` 应有记录

## 工作流（人工审核入口）
- 审核「模式归纳」类提案时警惕单例过拟合：从单一来源归纳的结构可能不完整或误判必选项（实测案例：初版模板在 5 条样本下即被修正，14 条样本后才区分出必选段与可选段）。优先采纳有跨会话/多样本复现证据的条目；仅凭单例归纳的模式即使采纳也应保持低置信度。

### 第 1 步：列出待审提案

```bash
python3 scripts/evo.py list
```

输出每个提案的 id、lessons（lesson_id + 证据核验标记 + 置信度 + 类型 + 目标文件）与护栏警告。
证据核验标记：`✓` = evidence 逐字命中来源会话原文；`✗` = 未命中（可疑编造，apply 会拦截）；
`?` = 来源会话缺失无法核验。

### 第 2 步：逐条审核

对每个 lesson 核对三点（AI 协助时必须打开提案原文展示）：

1. **证据可追溯**：evidence 是否真出现在来源会话中——`list`/`apply` 已自动做空白与引号字形不敏感的
   逐字核验（脚本代人工抽查），`✗` 时仍应人工打开来源会话确认
2. **目标合理**：target_file 与 heading 锚点是否是该经验的正确落点
3. **变更得当**：new_text 是否与目标文件既有风格一致、无重复条款

护栏规则（apply 会自动检查，命中则需 `--force`）：
- new_text 含**【强制】**标记 → 强制级别是人工评审决策，自动化只能提【推荐】级内容
- 置信度 Low → 建议先人工核实
- **evidence 未命中来源会话**（✗）→ 可疑编造，需人工核实
- **重复沉淀**：lesson_id（按 target|type|new_text 内容哈希确定性派生）已存在于 applied
  归档，或 new_text 已逐字存在于目标文件 → 疑似同一教训重复提案
- **steering 既有【强制】条款不可被削弱**——v1 仅支持追加（append_under/append_end），
  改写删除类变更一律驳回并等待人工直接编辑规范文件

硬错（`--force` 不可越过）：`supersedes` 引用不在 applied 归档中的 lesson_id 或指向自身。
修正既有 lesson 的方式不是改写，而是新 lesson 填写 `supersedes: L-XXXXXXXX` 指向旧
lesson_id（人工审核时在提案 JSON 块中填写），保留完整的演进链。

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

> ⚠️ **prompt_evolution 型提案不走 apply**（apply 仅支持 markdown 追加语义）。人工审阅
> 提案中新 SYSTEM_PROMPT 后，手动编辑 `scripts/evo_prompt.py` 的 `SYSTEM_PROMPT` 常量采纳。

## 进化自身（GEPA，手动低频）

skill-evo 用 GEPA（Genetic-Pareto prompt evolution）进化自己的总结 SYSTEM_PROMPT——
标注数据就是人工审核结果（applied 提案 = 正样本，rejected + reject_reason = 负样本），
冷启动天然成立、随使用持续积累：

```bash
python3 scripts/evo.py evolve --dry-run   # 查看标注数据积累进度（不足会提示，属预期）
python3 scripts/evo.py evolve             # 正式进化（预算默认 16 rollouts ≈ 32-50 次 claude -p）
```

- **成本提示**：budget 默认 16（config `gepa_budget`），每 rollout 含提炼+judge 两次
  headless 调用；仅在用户明确要求时运行
- 产出：`~/.config/ar/skill-evo/evolve/<ts>/`（迭代日志 + 候选 prompt）；
  holdout 改善 > 0.2 才生成 prompt_evolution 型 pending 提案（人工采纳方式见提案正文）
- 防过拟合：train/holdout 按会话分层切（holdout ≥4），holdout 每候选只评一次

## 配置

`~/.config/ar/skill-evo/config.toml`（可选，零配置即可用），模板见
[`config.example.toml`](config.example.toml)。常用项：`enabled`（总开关，或环境变量
`AR_SKILL_EVO_ENABLED=0`）、`scope_dirs`（只总结哪些目录下的会话）、`omp_max_per_run`、
`min_messages`。

## 设计边界（v2）

- 进化目标：`skills/**/*.md`、`steering/**/*.md`、根 `README.md`（索引表，表格感知追加）、
  根 `CLAUDE.md`（AI 操作指引）；只做**追加**，不做改写/删除，不做「新增 skill」级提案
- README 索引另有确定性兜底：`scripts/md_link_check.py`（链接有效性 + README 索引
  零漂移统一门禁，已接入 `run_tests.sh`），磁盘新增技能/规范/设计文档而 README
  未登记即红
- 处理过的会话不再重提（state.json 内容哈希去重 + 单会话单提案守卫）
- omp 触发优先用原生 hook（未安装时 CC 搭车扫描兜底）；`evo.py scan-omp` 可手动查看
- GEPA 进化对象 v2 仅 `SYSTEM_PROMPT`；guard skill 触发词进化待数据积累后立项

## 相关文件

- 核心脚本：[`scripts/evo.py`](scripts/evo.py)（CLI）、[`scripts/evo_session.py`](scripts/evo_session.py)、
  [`scripts/evo_prompt.py`](scripts/evo_prompt.py)、[`scripts/evo_proposal.py`](scripts/evo_proposal.py)、
  [`scripts/evo_config.py`](scripts/evo_config.py)、[`scripts/evo_gepa.py`](scripts/evo_gepa.py)、
  [`scripts/evo_evolve.py`](scripts/evo_evolve.py)
- hook 入口：[`../../hooks/on-session-end.sh`](../../hooks/on-session-end.sh)（CC）、
  [`../../hooks/omp/skill-evo.ts`](../../hooks/omp/skill-evo.ts)（omp，需安装）
- 设计文档：[`../../docs/design/skill-evo-design.md`](../../docs/design/skill-evo-design.md)
