# Awesome Rules

研发规范与 AI Agent 技能库，用于统一团队的设计标准并自动化审查流程。

## 项目结构

```
awesome-rules/
├── steering/                          # 规范文件（团队标准，唯一真相源）
│   ├── openapi-standards.md               # Open API 设计规范（RESTful）
│   ├── database-design-specification.md # 数据库设计规范（MySQL）
│   ├── git-conventions.md             # Git 提交规范
│   ├── testing-standards.md           # 测试规范
│   ├── review-report-standards.md     # 审查报告输出规范
│   ├── task-package-standards.md      # 任务包与派发守护规范
│   ├── cross-repo-contract-standards.md # 跨仓契约兼容性规范
│   ├── frontend-standards.md          # 前端工程技术规范（Vue3 管理端）
│   ├── api-contract-freeze-standards.md # API 契约冻结规范（先冻结再实现）
│   └── gtsp/                          # GTSP 工程规范（Java/Spring Cloud，按维度拆分，含 DDD 架构）
├── skills/                            # AI Agent 技能
│   ├── _shared/                       # guard 技能共享库（Severity/文件发现/报告骨架）
│   ├── ddl-guard/                     # DDL 设计与审查
│   ├── api-guard/                     # API 设计与审查
│   ├── arch-guard/                    # DDD 架构分层审查
│   ├── contract-guard/                # 跨仓契约兼容性设计与审查（japicmp + 下游编译门禁）
│   ├── doc-gen/                       # DDD 技术文档自动生成（单项目）
│   ├── impact-guard/                  # 变更影响分析（blast radius）
│   ├── work-report/                   # 跨仓库工作日报/周报
│   ├── alibabacloud-devops/           # 云效 DevOps 工具集
│   ├── tokensave-mcp/                 # tokensave 图谱专项能力（mcporter 代理）
│   ├── skill-evo/                     # 会话经验自动总结与规范进化（Hermes 式自进化闭环）
│   ├── code-review/                   # 两轴代码审查（规范轴+规格轴并行子代理，聚合抽验）
│   └── sourcery-autofix/              # Sourcery AI 审查自动修复（fix→测试→过目→闭环）
├── arch-hawkeye/                      # 架构鹰眼：全局架构观测与治理（消费 doc-gen manifest）
├── hooks/                             # Claude Code hooks（SessionStart 规范索引 + SessionEnd 会话总结）
├── scripts/                           # 工具脚本
│   ├── badcase_runner.py              # Badcase 回归测试
│   └── plugin_lock.py                 # 插件安装入口 blob 锁定（zero-regression 门禁）
├── docs/                              # 文档
│   ├── ai-coding-tools-setup.md       # 插件安装指南
│   └── design/                        # 技能设计文档（doc-gen 可信化 / impact-guard）
├── CONTRIBUTING.md                    # 贡献指南
├── .claude-plugin/                    # Claude Code 插件清单
├── .codex-plugin/                     # Codex CLI 插件清单
├── .cursor-plugin/                    # Cursor 插件清单
├── .kimi-plugin/                      # Kimi 插件清单
├── .grok-plugin/                      # Grok 插件清单
├── .opencode/                         # OpenCode 配置
├── .pi/extensions/                    # Pi 扩展
└── README.md
```

> 注：仅列规范消费面与主要入口，门禁/模板/工厂链等顶层目录（`tools/`、`templates/`、`.factory/`、`.github/`）不逐项展开；完整目录与文件清单以 `git ls-files` 为准。

## 规范文件（steering/）

规范分两组，体系独立：

### 通用设计规范（`steering/*.md`，设计阶段）

| 规范 | 说明 |
| --- | --- |
| [Open API 设计规范](steering/openapi-standards.md) | RESTful API 约定：URL 结构、HTTP 方法、响应格式、错误码、分页 |
| [数据库设计规范](steering/database-design-specification.md) | MySQL DDL/DML 设计标准：表、字段、索引、注释、SQL 语句，按强制级/推荐级/参考级三级分级 |
| [Git 提交规范](steering/git-conventions.md) | 分支命名、Commit 格式、MR 约定 |
| [测试规范](steering/testing-standards.md) | 测试编写与审查标准 |
| [审查报告输出规范](steering/review-report-standards.md) | 审查结论输出结构（guard 技能人工判断部分、CR 评审意见） |
| [跨仓契约兼容性规范](steering/cross-repo-contract-standards.md) | 变更被其他仓库依赖的 API 模块/契约门禁（japicmp、下游编译触发） |
| [任务包与派发守护规范](steering/task-package-standards.md) | AI Agent 任务包五要素骨架与派发治理：L1 记录型 watcher / L2 事后异构审查分级守护 |
| [前端工程技术规范（Vue3 管理端）](steering/frontend-standards.md) | Vue3 管理端工程标准：mock 联调门控、菜单下发路由、axios 工厂复用、可交互数据展示、变更验证，按强制级/推荐级分级 |
| [API 契约冻结规范](steering/api-contract-freeze-standards.md) | 新端点实现前契约逐字段冻结：method/path/请求参数名/响应信封/字段名未冻结禁止实现（mock 也不许先写），先冻结再实现 |

### GTSP 工程规范（`steering/gtsp/`，编码阶段）

Java/Spring Cloud 微服务（`gtsp-*`/`fss-*`）编码规范，按维度拆分，维度文件清单见 `ls steering/gtsp/0*.md`。总入口：[steering/gtsp/README.md](steering/gtsp/README.md)。

规范文件由人工维护，是所有审查和设计的唯一依据。

## 技能（skills/）

| 技能 | 说明 |
| --- | --- |
| [ddl-guard](skills/ddl-guard/README.md) | MySQL DDL 设计与规范审查 |
| [api-guard](skills/api-guard/README.md) | 业务接口规范审查 |
| [arch-guard](skills/arch-guard/README.md) | DDD 架构分层规范审查 |
| [doc-gen](skills/doc-gen/README.md) | DDD 技术文档自动生成（交互式静态站点） |
| [impact-guard](skills/impact-guard/README.md) | 变更影响分析（blast radius），按直接/间接 + GTSP 5 通道分级 |
| [work-report](skills/work-report/README.md) | 跨仓库工作日报/周报自动生成（3 种受众模板） |
| [alibabacloud-devops](skills/alibabacloud-devops/SKILL.md) | 阿里云云效 DevOps 工具集（Codeup/流水线/工作项，mcporter 代理） |
| [tokensave-mcp](skills/tokensave-mcp/SKILL.md) | tokensave 代码图谱专项能力（测试覆盖/dead code/rename 安全网，mcporter 代理；常规发现走 codebase-memory-mcp） |
| [skill-evo](skills/skill-evo/README.md) | 会话经验自动总结与规范进化：CC/omp 会话结束自动提炼经验生成提案，人工审核应用；GEPA 引擎进化自身（Hermes 式自进化闭环） |
| [contract-guard](skills/contract-guard/SKILL.md) | 跨仓契约兼容性设计与审查（japicmp + 下游编译门禁，配 steering 跨仓契约规范） |
| [code-review](skills/code-review/README.md) | 两轴代码审查（规范轴+规格轴并行子代理+聚合抽验，GitHub/云效适配） |
| [sourcery-autofix](skills/sourcery-autofix/SKILL.md) | Sourcery AI 审查自动修复：fix→全量测试→diff 人过目→剩余项闭环（配 lefthook pre-push opt-in 硬闸） |

**独立工程**（非技能，随仓库发布）：

| 工程 | 说明 |
|------|------|
| [arch-hawkeye](arch-hawkeye/README.md) | 架构鹰眼：全局架构观测与治理 — 联邦聚合 + 跨项目链路（HTTP/MQ/DB/缓存/定时 5 通道，confirmed/inferred 双置信度）+ 变更影响分析 + 治理闭环（基线/趋势/blame 归属/债务/超期告警/增量零容忍门禁）+ 本地双模式（`hawkeye local` 零依赖） |

各技能的详细文档、用法和检查规则见各自目录下的 README。

## 设计文档（docs/design/）

| 文档 | 说明 |
| --- | --- |
| [doc-gen 可信化改造](docs/design/doc-gen-contract-design.md) | Manifest Schema 契约 + 诚实退出码/receipt + revision-pinned evidence（已落地） |
| [impact-guard 技术设计](docs/design/impact-guard-design.md) | 变更影响分析（blast radius）完整论证与 grill 决策（评审稿） |
| [arch-guard 演进设计](docs/design/arch-guard-evolution-design.md) | ArchUnit 试点演进（Tier 1 巡检 + Tier 2 字节码双跑互补） |
| [guard 收据规范](docs/design/guard-receipt-spec.md) | 审查报告 receipt（收据）通用规范 |
| [skill-evo 技术设计](docs/design/skill-evo-design.md) | Hermes 式会话经验进化闭环 + GEPA 引擎（含竞态修复记录，已实现） |
| [skill-evo replay-eval 设计](docs/design/skill-evo-replay-eval.md) | 高频重复任务确定性打分评估集 → GEPA 进化信号源（对标 SkillOpt-Sleep replay，设计中） |
| [skills 清单门禁设计](docs/design/skill-manifest-gate.md) | frontmatter 单一事实源 + M1/M2 清单门禁（断链单向 + 路径围栏，含 grilling 六项裁决，已落地） |
| [Factory Harness 设计](docs/design/factory-harness-design.md) | L4 自举工厂：第一性原理推导、方案 B（omp headless）、治理锁与 mutation 门（S0 已落地） |
| [Gauntlet 门禁入口 SPEC](docs/design/spec-2026-08-21-gauntlet-entry.md) | 单一门禁入口 tools/gauntlet.sh：层编排 fail-closed + 检查器负控制 + 手动变异冒烟 |
| [Gauntlet 门禁入口 EVIDENCE](docs/design/evidence-2026-08-21-gauntlet-entry.md) | 15 层全绿（927 tests / 4/4 变异击杀）证据报告，含三次门拦真问题与 errexit 缺陷修复记录 |
| [P3 分发层数据验证与套件设计](docs/design/distribution-verification-and-suite-design.md) | 10 下游仓实测(冻结 sha 证据索引):DIST-1..10 条款、mkdir 跨平台锁、CI gate 注入方案 |
| 项目架构图 | 仓库整体架构交互图：治理闭环 / 规范供给 / 分发与自进化（archify 生成 awesome-rules-architecture.html，规格 JSON 同目录） |
| GTSP 分层架构图 | gtsp-* 完整档六模块分层与跨域解耦交互图（依据 steering/gtsp/01，生成 gtsp-layered-architecture.html） |
| 工厂链执行时序图 | .factory 工厂链 issue→triage→holdout→PR 全流程时序（依据 fix-issue.sh 实现真相，生成 factory-chain-sequence.html） |

> 注：以上三图为 archify 生成的本地产物，位于 docs/design/architecture/（已列 .gitignore 不入库），本地重新生成即可查看。

## 研究跟踪（docs/research/）

外部项目的调研档案与借鉴登记：可借鉴点带验证状态与落地状态，事件驱动跟进（frontmatter 含 `re-check-trigger`，不设时间门禁）。新增调研按同目录模板建档并登记本表。

| 项目 | 定位与借鉴要点 |
| --- | --- |
| [wemux](docs/research/wemux.md) | worker 优先执行的 Agent 协作平台：隔离 worktree 生命周期 / 配对安装 / 遥测白名单 / 许可切割（全部未裁决） |
| [Rome](docs/research/rome.md) | 递归智能体 Agent OS：单一 strict schema 多关卡复用 / 路径逃逸防护 / 负控范式（代码级验证，清单门禁 ADR 候选） |
| [Graft](docs/research/graft.md) | 文件型知识图谱上下文层：图谱即文件可审计，与 cbm 的 DB 图谱范式对照（未裁决） |
| [hermes-agent-self-evolution](docs/research/hermes-agent-self-evolution.md) | session 挖掘 + 人工审核护栏 → 已落地 skill-evo |
| [GEPA](docs/research/gepa.md) | Genetic-Pareto 反思进化引擎 → 已落地 skills/skill-evo/scripts/evo_gepa.py；v2/ICLR 2026 Oral 增量待裁决 |
| [SkillOpt](docs/research/skillopt.md) | Sleep replay 确定性打分 + 反 Goodhart 门控 → 已落地 replay-eval |
| [任务包模板对照实验](docs/research/taskpkg-ab-experiment.md) | FIVE vs CONTRACT 四轮预注册实验：触发器特异性消误报（R2），但纸面触发器对静默侵犯无执行力（R3，有条款臂漏报）→ 守护机械化，L1/L2/L3 分层防御（已落地规范包） |
| [Comet](docs/research/comet.md) | Agent Skill Harness 双工作流运行时：pass@k/pass^k 评估分离 / 发布门禁绑定草稿 hash / 三层状态可恢复 → 借鉴点 #1-5、#7 已落地（task-flow / evo_replay 三件套 / release_guard 证据门 / platform-matrix），#6 部分已有（单源多清单替代双目录复制） |

## 安装

本仓库已适配多种 AI 编程工具的插件格式，支持一行命令安装。详见 [插件安装指南](docs/ai-coding-tools-setup.md)。

## 贡献

- 新增工具链/脚本资产（如 `.factory/`）时，必须同步交付配套 README：涵盖快速使用、链/组件结构、已知边界与移植说明；不得只交付代码，等用户索要时再补文档。
- 技能 description 触发词须带领域语境限定（如「画审查流程图/风险标注时序图」而非裸「画流程图/时序图」），避免无相关意图的请求误激活技能；新增或修改 description 后对照官方 Skill authoring best practices 自检触发面是否过宽（triggers too often → make it more specific）

- **插件 manifest 约定**：`.claude-plugin/plugin.json` 不要显式声明 `"hooks": "./hooks/hooks.json"`——新版 Claude Code 自动加载标准路径的 hooks 文件，显式声明会触发 Duplicate hooks file 使整插件加载失败（且失败是静默的，可用 `claude plugin list` 或 `evo.py patrol` 检出）。
- **SKILL.md 编写约定**：按 Anthropic 官方最佳实践，SKILL.md 只放触发后 AI 需要的操作指引（命令序列、判定语义、验收红线、易踩坑）；架构图、设计背景等给人看的内容放同目录 README；采用渐进式加载（description 常驻 → SKILL.md 触发载入 → 细节按需读引用文件），正文控制在 ~70 行。

欢迎贡献规范文件、AI 技能和反例用例。详见 [贡献指南](CONTRIBUTING.md)。

> 各 AI 工具的插件安装入口清单（`.claude-plugin` 等 + `hooks/hooks.json`）受
> blob 锁定保护（zero-regression 模式）：有意变更后运行
> `python3 scripts/plugin_lock.py --update` 并随变更一起提交；校验命令
> `python3 scripts/plugin_lock.py`（非零退出 = 漂移或新增未锁定入口）。

> **门禁定位（spec-check）**：spec-check 为 spec 工作流文档的条款↔测试核对设施（opt-in：仅含 `spec:<ID>` 标签的文件触发），非全仓强制门——执行体 `tools/git/lefthook/spec-check.sh`；口径与 [CONTRIBUTING.md](CONTRIBUTING.md) 钩子说明一致。
