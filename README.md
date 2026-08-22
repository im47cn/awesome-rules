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
│   └── gtsp/                          # GTSP 工程规范（Java/Spring Cloud，按维度拆分，含 DDD 架构）
├── skills/                            # AI Agent 技能
│   ├── ddl-guard/                     # DDL 设计与审查
│   ├── api-guard/                     # API 设计与审查
│   ├── arch-guard/                    # DDD 架构分层审查
│   ├── doc-gen/                       # DDD 技术文档自动生成（单项目）
│   ├── impact-guard/                  # 变更影响分析（blast radius）
│   ├── work-report/                   # 跨仓库工作日报/周报
│   ├── alibabacloud-devops/           # 云效 DevOps 工具集
│   ├── tokensave-mcp/                 # tokensave 图谱专项能力（mcporter 代理）
│   └── skill-evo/                     # 会话经验自动总结与规范进化（Hermes 式自进化闭环）
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

## 规范文件（steering/）

规范分两组，体系独立：

### 通用设计规范（`steering/*.md`，设计阶段）

| 规范 | 说明 |
| --- | --- |
| [Open API 设计规范](steering/openapi-standards.md) | RESTful API 约定：URL 结构、HTTP 方法、响应格式、错误码、分页 |
| [数据库设计规范](steering/database-design-specification.md) | MySQL DDL/DML 设计标准：表、字段、索引、注释、SQL 语句，按【强制】【推荐】分级 |
| [Git 提交规范](steering/git-conventions.md) | 分支命名、Commit 格式、MR 约定 |
| [测试规范](steering/testing-standards.md) | 测试编写与审查标准 |
| [审查报告输出规范](steering/review-report-standards.md) | 审查结论输出结构（guard 技能人工判断部分、CR 评审意见） |
| [跨仓契约兼容性规范](steering/cross-repo-contract-standards.md) | 变更被其他仓库依赖的 API 模块/契约门禁（japicmp、下游编译触发） |

### GTSP 工程规范（`steering/gtsp/`，编码阶段）

Java/Spring Cloud 微服务（`gtsp-*`/`fss-*`）编码规范，按维度拆分为 10 个文件（项目结构、分层架构、命名、Feign、MyBatis、日志、异常、配置、注释、CR 清单）。总入口：[steering/gtsp/README.md](steering/gtsp/README.md)。

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
| [Factory Harness 设计](docs/design/factory-harness-design.md) | L4 自举工厂：第一性原理推导、方案 B（omp headless）、治理锁与 mutation 门（S0 已落地） |
| [Gauntlet 门禁入口 SPEC](docs/design/spec-2026-08-21-gauntlet-entry.md) | 单一门禁入口 tools/gauntlet.sh：层编排 fail-closed + 检查器负控制 + 手动变异冒烟 |
| [Gauntlet 门禁入口 EVIDENCE](docs/design/evidence-2026-08-21-gauntlet-entry.md) | 15 层全绿（927 tests / 4/4 变异击杀）证据报告，含三次门拦真问题与 errexit 缺陷修复记录 |

## 安装

本仓库已适配多种 AI 编程工具的插件格式，支持一行命令安装。详见 [插件安装指南](docs/ai-coding-tools-setup.md)。

## 贡献

欢迎贡献规范文件、AI 技能和反例用例。详见 [贡献指南](CONTRIBUTING.md)。

> 各 AI 工具的插件安装入口清单（`.claude-plugin` 等 + `hooks/hooks.json`）受
> blob 锁定保护（zero-regression 模式）：有意变更后运行
> `python3 scripts/plugin_lock.py --update` 并随变更一起提交；校验命令
> `python3 scripts/plugin_lock.py`（非零退出 = 漂移或新增未锁定入口）。
