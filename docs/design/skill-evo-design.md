# skill-evo 技术设计文档

> **状态**：已实现（v1）· 单测 36 例全绿 · 待真实会话观察期验证
> **范围**：v1 完整版（CC SessionEnd hook 自动总结 + omp 搭车增量扫描 + 置信度分级提案 + 人工审核应用）
> **参考**：[NousResearch/hermes-agent-self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution)（session 挖掘 + PR 人工审核护栏）、hermes-agent 本体（任务后自主创建/改进 skill） · **日期**：2026-08-18

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

## 6. v2 候选（YAGNI，v1 不做）

- omp 原生 TS hook 触发（替代搭车扫描）
- 跨会话 lesson 去重（同 target + 相似 text 合并）
- replace 语义（改写既有条款，需更强护栏：diff 审阅界面 + steering 强制条款削弱检测）
- 「新增 skill」级提案
- 参考 hermes-agent-self-evolution 的 GEPA：对 SKILL.md 的 description（触发词）做
  eval 驱动的自动调优（需要坏例数据集，待积累）

## 7. 验证记录

- 单测：36 例全绿（`python3 -m pytest skills/skill-evo/scripts/tests`，claude 调用全 mock）
- `evo.py scan-omp`：对本机真实 `~/.omp/agent/sessions/` 的发现与 scope 过滤正常
- `evo.py run --transcript <真实 CC 会话> --dry-run`：prompt 生成含目标索引与脱敏视图
- 真实闭环（SessionEnd 自动成案 → 人工 apply）待观察期验证，见 SKILL.md 工作流
