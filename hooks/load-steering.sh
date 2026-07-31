#!/bin/bash
# SessionStart hook — 注入 steering 规范索引，不直接注入全文以避免 token 浪费
# AI 会在需要时主动 Read 对应规范文件

cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "## Awesome Rules 规范索引\n\n以下团队规范文件已就绪，在相关任务中必须主动 Read 并遵守：\n\n| 规范 | 路径 | 适用场景 |\n|---|---|---|\n| 测试规范 | steering/testing-standards.md | 编写/审查测试 |\n| API 设计规范 | steering/api-standards.md | 设计/审查 API |\n| 数据库规范 | steering/database-design-specification.md | 设计表结构/SQL |\n| Git 提交规范 | steering/git-conventions.md | 提交/分支/PR |\n| DDD 架构规范 | steering/ddd-architecture.md | 架构设计/分包/领域建模 |\n\n**使用规则**：\n- 遇到上述场景时，先 `Read` 对应规范文件，再开始工作\n- 规范中【强制】标记的条款不可违反\n- 规范中【推荐】标记的条款尽可能遵守\n- 审查类任务可使用 `/ddl-guard`、`/api-guard`、`/arch-guard` 自动检查"
  }
}
EOF
