# Awesome Rules

研发规范与 AI Agent 技能库，用于统一团队的设计标准并自动化审查流程。

## 项目结构

```
awesome-rules/
├── steering/                          # 规范文件（团队标准，唯一真相源）
│   ├── database-design-specification.md   # 数据库设计开发规范（MySQL）
│   └── api-standards.md                  # API 设计规范（RESTful）
├── skills/                            # AI Agent 技能
│   ├── ddl-guard/                     # DDL 设计与审查
│   └── api-guard/                     # API 设计与审查
├── docs/                              # 文档
│   └── ai-coding-tools-setup.md       # 插件安装指南
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

| 规范 | 说明 |
| --- | --- |
| [数据库设计开发规范](steering/database-design-specification.md) | MySQL DDL/DML 设计标准，覆盖表、字段、索引、注释、SQL 语句等，规则按【强制】【推荐】分级 |
| [API 设计规范](steering/api-standards.md) | RESTful API 约定，包括 URL 结构、HTTP 方法、响应格式、错误码、分页 |

规范文件由人工维护，是所有审查和设计的唯一依据。

## 技能（skills/）

| 技能 | 说明 |
| --- | --- |
| [ddl-guard](skills/ddl-guard/README.md) | MySQL DDL 设计与规范审查 |
| [api-guard](skills/api-guard/README.md) | Open API 设计与规范审查 |

各技能的详细文档、用法和检查规则见各自目录下的 README。

## 安装

本仓库已适配多种 AI 编程工具的插件格式，支持一行命令安装。详见 [插件安装指南](docs/ai-coding-tools-setup.md)。

## 贡献

欢迎贡献规范文件、AI 技能和反例用例。详见 [贡献指南](CONTRIBUTING.md)。
