# skill-evo

会话经验自动总结与规范/技能进化 — 参考 Hermes self-evolution 的闭环：会话结束后自动提炼「用户纠正 / 失败模式 / 成功模式」，生成对 `skills/*/SKILL.md` 与 `steering/*.md` 的进化提案，人工审核后应用。

> **状态**：✅ v2 已实现（CC SessionEnd hook + omp 原生 hook 双端自动触发；GEPA 进化引擎待标注积累）。测试：`pytest skills/skill-evo/scripts/tests -q`（LLM 调用全 mock）。

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
                ├─ 搭车插件哑故障巡检（evo_patrol，节流 + 台账 patrol.json）
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

- omp 自动发现用户级 hook；`session_shutdown` fire-and-forget 调用
  `evo.py run --agent omp --cwd <cwd>`；脚本路径可用 `AR_SKILL_EVO_SCRIPT` 覆盖
- 与 CC 搭车扫描并存无害（state.json 增量去重收敛）；防递归链：
  omp → evo.py（`AR_SKILL_EVO_CHILD=1`）→ claude -p（继承标记）→ CC hook 见标记即退
- 验证：安装后结束一个 omp 会话，`~/.config/ar/skill-evo/logs/evo.log` 应有记录

审核流程（在任意 AI 会话中说「查看 skill-evo 提案」即可触发技能引导）：

```bash
python3 skills/skill-evo/scripts/evo.py list            # 列 pending 提案（含护栏警告）
python3 skills/skill-evo/scripts/evo.py apply <id> --dry-run   # 预演
python3 skills/skill-evo/scripts/evo.py apply <id>      # 应用（锚点失配整体失败）
python3 skills/skill-evo/scripts/evo.py reject <id> --reason "证据不足"   # 驳回 → GEPA 负样本
python3 skills/skill-evo/scripts/evo.py patrol [--force]          # 插件哑故障巡检复查
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

## 插件哑故障巡检（evo_patrol）

CC 插件 `failed to load` 不弹通知，hook 静默失效无感知（曾发生：awesome-rules
插件因 manifest 重复 hooks 声明静默失效多日）。`evo.py run` 搭车巡检
`claude plugin list`（`patrol_interval_hours` 节流，默认 6h）：

- 加载失败落盘 `~/.config/ar/skill-evo/patrol.json` 台账（含 first_seen），
  新故障/错误变化记 `logs/evo.log` 告警，恢复记恢复日志
- `evo.py list` 置顶展示未决故障；`evo.py patrol [--force]` 手动复查（有故障 exit 1）
- 巡检自身永不抛栈（哑故障检测器不能自己成为哑故障）

## 设计边界（v2）

- 排查「会话被跳过/被重复处理」时先查 state.json 的内容哈希记账（omp 退出 flush 会碰 mtime，mtime 不可作为处理依据）
- 进化目标：`skills/**/*.md`、`steering/**/*.md`、根 `README.md`（索引表，表格感知追加）、
  根 `CLAUDE.md`（AI 操作指引）；只做**追加**，不做改写/删除，不做「新增 skill」级提案
- README 索引另有确定性兜底：`scripts/md_link_check.py`（链接有效性 + README 索引
  零漂移统一门禁，已接入 `run_tests.sh`），磁盘新增技能/规范/设计文档而 README
  未登记即红
- 处理过的会话不再重提（state.json 内容哈希去重 + 单会话单提案守卫）
- omp 触发优先用原生 hook（未安装时 CC 搭车扫描兜底）；`evo.py scan-omp` 可手动查看
- GEPA 进化对象 v2 仅 `SYSTEM_PROMPT`；guard skill 触发词进化待数据积累后立项

## 配置

`~/.config/ar/skill-evo/config.toml`（可选），模板见 [`config.example.toml`](config.example.toml)。常用项：`scope_dirs`（会话范围）、`min_messages`（跳过短会话）、`gepa_budget`、
`patrol_interval_hours`（插件巡检节流间隔）。总开关：环境变量 `AR_SKILL_EVO_ENABLED=0`。

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)（AI 审核操作指引）
- 核心脚本：[`scripts/evo.py`](scripts/evo.py)（CLI）、[`scripts/evo_patrol.py`](scripts/evo_patrol.py)（插件巡检）等
- 技术设计（含 GEPA 算法保真点与竞态修复记录）：[`../../docs/design/skill-evo-design.md`](../../docs/design/skill-evo-design.md)
- CC hook：[`../../hooks/on-session-end.sh`](../../hooks/on-session-end.sh)
- omp hook 模板：[`../../hooks/omp/skill-evo.ts`](../../hooks/omp/skill-evo.ts)
