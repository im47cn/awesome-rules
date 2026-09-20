---
last-checked: 2026-09-20
re-check-trigger: Comet 发布任意高于 0.4.1 的新版本或 Native/Classic 工作流语义变更；或本仓 replay-eval 落地 pass^k 条款时复评
depth: 文档级（README 全文 + docs llms.txt 索引 + tech-blog + npm registry 元数据；未做代码级验证）
---

# Comet（rpamis/comet）

## 一句话定位

面向 AI 编码 Agent 的任务工作流运行时 + Skill 平台（npm CLI `@rpamis/comet`）：以可恢复状态机接管「需求→设计→实现→验证→归档」，附 Skill 创建/评估/发布工具链；与 Perplexity 同名浏览器无关。

## 事实快照（2026-09-20）

- MIT；2026-05-14 首发 0.1.0（"OpenSpec + Superpowers dual-star workflow"），4 个月迭代至 0.4.1；单人维护者 benym
- 3091 stars / 296 forks / 40 issues；npm 周下载 ~880；中文社区为主（抖音/B站/LINUX DO），中英双语文档各 100 页
- 双工作流：Native（强模型自主，Comet 自有 Runtime）/ Classic（OpenSpec + Superpowers 五阶段治理）；`/comet` 按 `.comet/config.yaml` 确定性转发，不按任务规模猜测
- 纯 Node 运行时（Windows 免 Bash/WSL）；包 27.7MB 且含 postinstall；`comet init` 宣称支持 37 个编码平台
- 自评估实验（16 任务 × pass@3）：Native vs Classic 双通过配对样本省 76.8% token / 57.4% Agent 轮次 / 47.4% 时间——项目自测，无第三方复现，采信打折

## 与本仓的差异

| 维度 | Comet | awesome-rules |
| --- | --- | --- |
| 层 | 任务执行过程运行时：在用户项目内驱动编码任务全生命周期 | 规范内容库 + 审查技能 + 仓库自维护工厂；不驱动业务编码任务 |
| 人在环 | Native 默认 `archive_confirmation: automatic`、Classic `auto_transition: true`，最大化强模型自主 | 人类保留写 issue / 批准合并 / 晋升 release；auto-merge 双锁 + kill-rate ≥80% 前置 |
| 门禁哲学 | guard 脚本 + PreToolUse hook + 共享转移语义表 | gauntlet 15 层 fail-closed + 检查器负控制 + mutation kill-rate + holdout 前置 |
| 评估对象 | 工作流 Skill 的增量价值（CONTROL vs COMET_FULL 对照） | 门灵敏度（mutation 注入）+ badcase 回归 + replay-eval 确定性打分 |
| 状态恢复 | 会话内任务三层状态 + `resume-probe` 跨设备续传 | `.factory` 租约/epoch 仲裁（仓库维护链互斥），无会话级任务续传概念 |
| 分发 | npm 全局 CLI 安装器写入 37 平台目录 | 插件/配置清单 10 入口 + hooks + blob 锁 zero-regression |
| 供应链 | 27.7MB + postinstall + `@vscode/ripgrep` 二进制（面大） | Python/bash 轻内容分发（面小） |

## 可借鉴点

以下机制来自官方文档与公开材料（2026-09-20 文档级精读，未做代码级验证）：

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | pass@k（能力上限，HumanEval 无偏估计）与 pass^k（可靠性下限）分离 | replay-eval 给 GEPA 选择信号补「每次都能做对」维度，区别于「能做对一次」 | ✅ 文档级 | 未裁决 |
| 2 | 双 Agent 自动交互：被测 Agent 跑 Skill，另一 Agent 模拟用户在决策点应答，评测无人值守跑完多轮 | badcase_runner / replay-eval 的多轮交互场景自动化 | ✅ 文档级 | 未裁决 |
| 3 | Skill 调用证据硬门禁：PreToolUse hook + stream-json 解析调用证据，未真正触发 Skill 的运行不计入评测（对照：仅加提示词触发率约 70%） | replay-eval 防「裸模型答对」污染进化信号；与 CONTRIBUTING 触发词领域限定纪律互补 | ✅ 文档级 | 未裁决 |
| 4 | 发布门禁绑定草稿 hash：eval 证据必须对应最新草稿 hash，旧 hash / 失败证据一律阻断 publish | release_guard / plugin_lock 之外增加「技能内容 hash ↔ 评测证据」绑定 | ✅ 文档级 | 未裁决 |
| 5 | 状态三层分层：用户可读 `.comet.yaml` / 机器 `run-state.json` / 追加审计 `state-events.jsonl` | 长任务技能（如 code-review 并行子代理）的中断恢复与审计 | ✅ 文档级 | 未裁决 |
| 6 | 编号规则文件双平台同步：`.claude/rules` 与 `.codex/rules` 同编号同语义，01 工作区安全、02 证据与验证置顶 | 跨平台规则分发的语义对齐约定与优先级排序法 | ✅ 文档级 | 部分已有（gtsp/ 已按 0*.md 编号，多插件清单已有） |
| 7 | 37 平台目录映射矩阵（平台 × 项目/全局 scope × 路径差异，含 Antigravity 双版本路径） | P3 分发层验证的平台覆盖参考 | ✅ 文档级 | 未裁决 |

## 不适配点 / 否决

- 整体引入 = 给团队换工作流操作系统，超出规范库使命（YAGNI）；只吸收评估与门禁机制
- 意图路由六值分类（full/hotfix/tweak/resume/ask_user/out_of_scope）与本仓二值 triage 铁律哲学相反（本仓刻意消除中间态收件箱），否决
- Personal Memory / Project Knowledge 与已落地 skill-evo（Hermes + GEPA）重叠；其自动上下文注入弱于本仓人工审核护栏，仅参考「新经验先试用、攒证据后转正」分级
- **反向借鉴**：27.7MB 包 + postinstall 脚本 + 打包 Dashboard（antd/mermaid）的供应链面——本仓维持内容型轻分发 + blob 锁的佐证

## 资源链接

- 仓库：<https://github.com/rpamis/comet>（镜像 AtomGit rpamis/comet）
- 文档：<https://docs.comet.rpamis.com/en>（索引 <https://docs.comet.rpamis.com/llms.txt>）
- 业界对照：<https://docs.comet.rpamis.com/en/tech-blog/comet-vs-industry>
- 自评估实验：<https://docs.comet.rpamis.com/en/eval/comet-native-vs-040-experiment>
- npm：<https://www.npmjs.com/package/@rpamis/comet>
- 调研产出：2026-09-20 会话（README/docs 全文精读 + registry 元数据）
