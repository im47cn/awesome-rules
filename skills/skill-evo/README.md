# skill-evo

会话经验自动总结与规范/技能进化 — 参考 Hermes self-evolution 的闭环：会话结束后自动提炼「用户纠正 / 失败模式 / 成功模式」，生成对 `skills/*/SKILL.md` 与 `steering/*.md` 的进化提案，人工审核后应用。

> **状态**：✅ v2 已实现（CC SessionEnd hook + omp 原生 hook 双端自动触发；GEPA 进化引擎待标注积累）。测试 51 项（LLM 调用全 mock）。

## 架构

```
Claude Code                                    omp（oh-my-pi）
SessionEnd hook（hooks.json）                  session_shutdown hook（hooks/omp/skill-evo.ts）
  nohup 秒退，不阻塞会话                        Bun.spawn detached
        └──────────────┬──────────────────────────────┘
                       ▼
              scripts/evo.py run
                ├─ 会话定位：hook stdin / --cwd（首行 cwd 匹配 + 内容哈希增量去重）
                ├─ 脱敏切片（密钥/长 token/ANSI）+ 目标资产锚点索引
                ├─ headless claude -p 提炼 lessons（防递归三层）
                └─ 提案落盘 ~/.config/ar/skill-evo/proposals/pending/
                       ▼
         人工审核：evo.py list / apply / reject
           ├─ apply：锚点级追加写入（两阶段校验，失配不盲写）
           └─ rejected + reason → GEPA 负样本
                       ▼
         GEPA 进化引擎（evo.py evolve，手动低频）
           applied/rejected 提案 = 真实标注 → 进化自身总结 SYSTEM_PROMPT
```

核心护栏（对齐 Hermes「一切进化走人工评审」）：**提取全自动，应用必须人工**；只追加不改写（steering【强制】条款结构上不可被削弱）；永不自动 `git commit`。

## 快速使用

零配置即用（默认只总结 `~/sources` 下的会话）。CC 侧随插件安装自动生效；omp 侧需装一次 hook：

```bash
cp hooks/omp/skill-evo.ts ~/.omp/agent/hooks/pre/
```

审核流程（在任意 AI 会话中说「查看 skill-evo 提案」即可触发技能引导）：

```bash
python3 skills/skill-evo/scripts/evo.py list            # 列 pending 提案（含护栏警告）
python3 skills/skill-evo/scripts/evo.py apply <id> --dry-run   # 预演
python3 skills/skill-evo/scripts/evo.py apply <id>      # 应用（锚点失配整体失败）
python3 skills/skill-evo/scripts/evo.py reject <id> --reason "证据不足"   # 驳回 → GEPA 负样本
```

GEPA 进化（冷启动保护：标注 ≥10 cases 且 ≥8 sessions 才可运行）：

```bash
python3 skills/skill-evo/scripts/evo.py evolve --dry-run  # 查看标注积累进度
python3 skills/skill-evo/scripts/evo.py evolve            # 进化总结 prompt（预算默认 16 rollouts）
```

## 提案格式

置信度三级（High = 明确纠正 / Medium = 可行模式 / Low = 待观察），每条 lesson 必须含可追溯 evidence（审核第一步即核对原文，防幻觉）。护栏命中需 `--force`：

- new_text 含【强制】标记（强制级别是人工评审决策）
- 置信度 Low
- `prompt_evolution` 型提案不走 apply，人工编辑 `evo_prompt.py` 的 `SYSTEM_PROMPT` 采纳

## 配置

`~/.config/ar/skill-evo/config.toml`（可选），模板见 [`config.example.toml`](config.example.toml)。常用项：`scope_dirs`（会话范围）、`min_messages`（跳过短会话）、`gepa_budget`。总开关：环境变量 `AR_SKILL_EVO_ENABLED=0`。

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 技术设计（含 GEPA 算法保真点与竞态修复记录）：[`../../docs/design/skill-evo-design.md`](../../docs/design/skill-evo-design.md)
- CC hook：[`../../hooks/on-session-end.sh`](../../hooks/on-session-end.sh)
- omp hook 模板：[`../../hooks/omp/skill-evo.ts`](../../hooks/omp/skill-evo.ts)
