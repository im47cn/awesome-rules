# Skills — AI Agent 技能库

本目录收录可复用的 AI Agent 技能。每个技能是一个子目录，核心为 `SKILL.md`（YAML frontmatter `name` + `description` + 正文工作流），可附 `scripts/` 自动化脚本与 `*-manual-rules.md` 人工判断规则。

## 技能编写约束

### 【强制】不得静态复制可动态获取的内容

SKILL.md 不得把「可被脚本/工具实时获取的内容」硬编码为静态副本，包括但不限于：

- 外部 MCP server 的工具清单（工具名 / 参数 schema）
- 知识图谱查询语句、API schema、生成产物
- 脚本的检查项清单、帮助文本（应由脚本 `--help` 或子命令输出）

这类内容必须「**先查后用**」——由脚本 / `mcporter list` / `--mode graph` 等实时获取，SKILL.md 只保留工作流与决策树。

**为什么**：静态副本必然与上游漂移，且大量 schema 会撑爆上下文。仓库内已有两次教训：

- `arch-guard` 曾手抄 Cypher 查询，`:Function` 标签过时导致 0 结果 → 改为 `python3 scripts/arch_check.py --mode graph` 动态生成
- `alibabacloud-devops` 曾静态罗列 165 个 MCP 工具 → 改为 `mcporter list` 动态查询（同时避免工具 schema 全量进上下文）

单一数据源（single source of truth）只允许存在于脚本 / 上游，文档只负责引用与引导。

### 【推荐】description 必须含业务触发词

`description` 不要只写功能性描述，必须列出用户会实际说出的业务触发词（「云效 / 合并请求 / 流水线」「架构审查 / 分层检查」），否则模型召回率低。参考 `arch-guard`、`ddl-guard` 的写法。
