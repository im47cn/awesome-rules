# skill-evo 技术设计文档

> **状态**：已实现（v2）· 单测 50 例全绿 · 待真实会话观察期验证
> **范围**：v2 = v1 + omp 原生触发 + GEPA 进化引擎（进化自身 SYSTEM_PROMPT）
> **参考**：[NousResearch/hermes-agent-self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution)（session 挖掘 + PR 人工审核护栏）、hermes-agent 本体（任务后自主创建/改进 skill）、[GEPA arXiv 2507.19457](https://arxiv.org/abs/2507.19457) · **日期**：2026-08-18

---

## 1. 背景与动机

本仓库的 skills 与 steering 是「规范即资产」，但目前资产的唯一进化路径是人工发现遗漏再手改。
会话中大量真实信号——用户纠正 AI 的做法、反复失败后找到的正确路径、被明确认可的模式——
随会话结束而流失。Hermes 的 self-evolution 证明了「session 挖掘 → 经验提取 → 资产进化
（人工审核）」闭环可行，本设计将其移植到 Claude Code 与 omp（oh-my-pi）双端。

核心决策（已与用户确认）：
1. **进化目标**：`skills/*/SKILL.md` + `steering/*.md`（含 gtsp/）
2. **仅自动触发**：提取/总结全自动；应用提案必须人工审核（Hermes 护栏：绝不直改）
3. **共享 Python 核心 + 双端适配**：脚本仅标准库（Py3.9 兼容）

## 2. 架构与数据流

```
CC SessionEnd hook ──► hooks/on-session-end.sh（同步秒退：防递归检查 + nohup spawn）
                              │
                              ▼  (后台)
                    scripts/evo.py run
                      ├─ CC: hook stdin JSON → transcript_path
                      ├─ omp 搭车: ~/.omp/agent/sessions/<cwd-slug>/*.jsonl 增量扫描
                      │         （state.json 按 <agent>:<session_id> + mtime 去重）
                      ├─ 过滤门槛: scope_dirs 内 / 用户消息 ≥ min_messages
                      ├─ evo_prompt: 脱敏切片（密钥/长 token/ANSI）+ 目标资产索引
                      ├─ claude -p（headless, --settings 禁 hooks, --max-turns 1）
                      │    → {no_signal, lessons[{type, evidence, target_file,
                      │       confidence, reason, change{action, heading, new_text}}]}
                      └─ 落盘提案 ~/.config/ar/skill-evo/proposals/pending/*.md
人工审核（skill-evo SKILL.md 工作流）
  evo.py list → apply --dry-run → apply [--force] → git diff 自查 → 自行 commit
                                          或 reject --reason
```

## 3. 关键设计

### 3.1 只追加语义（append-only）

v1 的 change 仅支持 `append_under`（插入到既有 `##` 标题下，锚点须唯一）与 `append_end`。
**不做改写/删除**——因此：
- steering 既有【强制】条款在结构上不可能被提案削弱（与「【强制】不可违反」的仓库原则对齐）
- 应用是确定性的：锚点失配/不唯一 → 两阶段校验整体失败，绝不盲写

护栏（命中需 `apply --force`）：new_text 含【强制】标记（强制级别是人工评审决策）；
置信度 Low。

### 3.2 omp 搭车扫描

omp 无生命周期 hooks API（探明其扩展机制为 TypeScript 插件；`~/.omp/agent/hooks/pre/`
存在 TS hook 形态，claude-mem 在用——**v2 可考虑 omp 原生 hook 触发**，v1 不引入第二套实现）。
方案：CC 会话结束触发 `evo.py run` 时顺带增量扫描 omp 会话目录（omp 会话格式
`<timestamp>_<sessionId>.jsonl` 已实测确认：首行 `{"type":"session","id","cwd"}`，
正文 `{"type":"message","message":{"role":"user|assistant|toolResult",...}}`）。
成本由 `omp_max_per_run`（默认 5）限流。

### 3.3 防递归三层

1. hook 脚本检查 `AR_SKILL_EVO_CHILD`（后台进程及其 claude -p 子进程继承该标记）
2. `claude -p` 传 `--settings '{"hooks":{}}'` 禁用 hooks，并 `env -u CLAUDECODE`
3. 增量 state 幂等：即使二次触发也是 no-op

### 3.4 失败语义

后台一切异常只写 `logs/evo.log` 后静默；**处理过即记账**（含失败与 no_signal），
防失败会话无限重试——代价是丢弃的会话不补提，可接受（下次会话的经验通常等价）。

## 4. 文件清单

| 路径 | 职责 |
|---|---|
| `hooks/on-session-end.sh` + `hooks/hooks.json` | SessionEnd 入口（秒退 spawn） |
| `skills/skill-evo/SKILL.md` | 人工审核工作流（AI 辅助审核时必读） |
| `scripts/evo.py` | CLI：run / scan-omp / list / apply / reject |
| `scripts/evo_session.py` | CC/omp 双解析器、增量去重、omp 发现 |
| `scripts/evo_prompt.py` | 脱敏、切片、目标资产索引（重用 load-steering 的 frontmatter 解析范式）、prompt |
| `scripts/evo_proposal.py` | 提案读写（markdown + 机读 JSON 块）、路径逃逸校验、两阶段应用、状态流转 |
| `scripts/evo_config.py` | `~/.config/ar/skill-evo/config.toml`（极简 KV 解析，零配置可用） |
| `scripts/tests/` | 36 例单测（claude 子进程全 mock，不打真模型） |

## 5. 安全边界

- 后台进程对仓库**只读**；写仓库仅发生在人工驱动的 `apply`
- `validate_target`：目标必须解析到仓库内 `skills/`、`steering/` 的 `.md`（防逃逸）
- transcript 送 LLM 前脱敏（密钥/长 token/ANSI）；提案 evidence 要求逐字可追溯，审核第一步即核对
- 永不自动 `git commit`（应用后提示用户 `git diff` 自查）
- 总开关：`AR_SKILL_EVO_ENABLED=0` 或配置 `enabled = false`

## 6. v2 增强（2026-08-18 已实现）

### 6.1 omp 原生触发

- 机制确证：omp 自动发现用户级 `~/.omp/agent/hooks/pre/*.ts`（Bun 原生加载，
  default export `f(pi: HookAPI)`），`session_shutdown` 事件即会话结束时机；
  handler 有 30s 上限 → detached fire-and-forget（样例：claude-mem.ts）
- 仓库提供模板 `hooks/omp/skill-evo.ts`，一条 `cp` 安装；TS 侧只传 `ctx.cwd`
  （ctx 上确证可用的只有 cwd），会话文件由 Python `find_latest_omp_sessions`
  （首行 cwd 匹配 + mtime 降序）定位——不依赖未确证的 `ctx.sessionManager`
- CC 搭车扫描保留作兜底（hook 未安装时），state 去重收敛重复
- 防递归链三段：omp → evo.py（`AR_SKILL_EVO_CHILD=1`）→ claude -p（继承标记 +
  禁 hooks）→ CC SessionEnd hook 见标记即退

### 6.2 GEPA 进化引擎（`evo_gepa.py`，stdlib 复刻 arXiv 2507.19457）

- 引擎与资产解耦：`run_gepa(baseline, train, holdout, execute, reflect, budget,
  validate)` —— execute/reflect 均为回调，引擎不含任何 LLM/ML 依赖
- 算法保真点：逐实例最优并集 Pareto 前沿（并列保留、被支配剔除）+ 按 f[Φ] 加权
  采样；minibatch 反思变异（reflector 看分数+judge 反馈）；minibatch 局部接受
  （均分改善才进池）；接受则补评 train 缺口；rollout 预算硬上限；holdout
  每候选只评一次后选优（防择优污染）
- **首个应用 = 进化自身 SYSTEM_PROMPT**（`evo_evolve.py`）：标注 = applied/rejected
  提案（人工审核即真实标签，reject_reason 是负反馈）；judge 四维
  precision/recall/negative_avoidance/format_compliance 加权打分；train/holdout
  按会话分层切（holdout ≥4）；变异约束（JSON 契约关键词 + 长度 ≤ baseline×1.5）
  违约即丢弃
- 进化产物 = prompt_evolution 型 pending 提案（新旧 prompt + 分数 + 谱系），
  **人工采纳**（手动编辑 SYSTEM_PROMPT 常量），不走 apply（apply 仅支持
  markdown 追加）；holdout 改善 ≤ 0.2 仅存报告不出提案
- 冷启动保护：标注 < `gepa_min_cases`（10）拒绝运行，`evolve --dry-run` 可查进度

### 6.3 竞态修复（2026-08-18 实测发现）

omp 原生 hook 首日即暴露 mtime 记账缺陷：SessionEnd flush 碰 mtime 导致同一会话
45 秒内被整会话重总结、产出两份重叠提案。修复（单测 51 例）：
- **state 记账改为内容哈希**（`content_digest`）：touch/flush 不再触发重处理；
  内容真实增长才重处理；旧 mtime 记账（float）自然迁移
- **单会话单提案守卫**（`session_proposal_exists`）：pending/applied/rejected 任一
  状态已有该会话提案即跳过总结——内容增长的兜底防线，代价是尾部新增经验丢失
  （与「处理过即不再重提」取舍一致）

### 6.4 v3 候选（YAGNI，暂不做）

- 跨会话 lesson 去重（同 target + 相似 text 合并）
- replace 语义（改写既有条款，需更强护栏：diff 审阅界面 + steering 强制条款削弱检测）
- 「新增 skill」级提案
- guard skill 触发词（SKILL.md description）的 GEPA 进化——引擎已就绪，
  缺评估集（合成任务 + judge 噪声大，待提案数据积累后立项）

## 7. 验证记录

- 单测：50 例全绿（`python3 -m pytest skills/skill-evo/scripts/tests`，claude 调用全 mock）
- `evo.py scan-omp`：对本机真实 `~/.omp/agent/sessions/` 的发现与 scope 过滤正常
- `evo.py run --transcript <真实 CC 会话> --dry-run`：prompt 生成含目标索引与脱敏视图
- omp hook 模板已安装至 `~/.omp/agent/hooks/pre/`，待自然会话结束验证 evo.log
- `evolve --dry-run`：标注不足时正确拒绝（冷启动预期）
- 真实闭环（SessionEnd 自动成案 → 人工 apply → 数据积累 → evolve）待观察期验证
