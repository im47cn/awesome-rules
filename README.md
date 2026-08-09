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
│   └── gtsp/                          # GTSP 工程规范（Java/Spring Cloud，按维度拆分，含 DDD 架构）
├── skills/                            # AI Agent 技能
│   ├── ddl-guard/                     # DDL 设计与审查
│   ├── api-guard/                     # API 设计与审查
│   ├── arch-guard/                    # DDD 架构分层审查
│   └── doc-gen/                       # DDD 技术文档自动生成
├── scripts/                           # 工具脚本
│   └── badcase_runner.py              # Badcase 回归测试
├── docs/                              # 文档
│   └── ai-coding-tools-setup.md       # 插件安装指南
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

### GTSP 工程规范（`steering/gtsp/`，编码阶段）

Java/Spring Cloud 微服务（`gtsp-*`/`fss-*`）编码规范，按维度拆分为 10 个文件（项目结构、分层架构、命名、Feign、MyBatis、日志、异常、配置、注释、CR 清单）。总入口：[steering/gtsp/README.md](steering/gtsp/README.md)。

规范文件由人工维护，是所有审查和设计的唯一依据。

## 技能（skills/）

| 技能 | 说明 |
| --- | --- |
| [ddl-guard](skills/ddl-guard/README.md) | MySQL DDL 设计与规范审查 |
| [api-guard](skills/api-guard/README.md) | Open API 设计与规范审查 |
| [arch-guard](skills/arch-guard/README.md) | DDD 架构分层规范审查 |
| [doc-gen](skills/doc-gen/README.md) | DDD 技术文档自动生成（交互式静态站点） |

各技能的详细文档、用法和检查规则见各自目录下的 README。

## 安装

本仓库已适配多种 AI 编程工具的插件格式，支持一行命令安装。详见 [插件安装指南](docs/ai-coding-tools-setup.md)。

## 贡献

欢迎贡献规范文件、AI 技能和反例用例。详见 [贡献指南](CONTRIBUTING.md)。
