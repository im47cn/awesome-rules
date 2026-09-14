---
last-checked: 2026-09-13
re-check-trigger: 发表独立 benchmark 论文/报告，或 MCP 集成方式发生大改，或 star 突破 15k
depth: README/CLI 级（未做代码级验证）
---

# Graft（trailhq/Graft）

## 一句话定位

面向 coding agent 的文件型知识图谱上下文层：给 Claude Code/Cursor/Codex/Gemini 等注入代码库级理解，宣称更快更省。

## 事实快照（2026-09-13）

- MIT；2026-07-03 建仓；7,354 stars / 671 forks；当日仍活跃（138 open issues）
- TypeScript；tree-sitter 解析 + MCP server 分发；主页 graft.nanonets.ai（nanonets 出品）
- README 含 CLI 用法与 benchmark 结果（具体数字未复核，采用时需独立验证）

## 可借鉴点

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | 文件型知识图谱（图谱即文件，可 git diff/审计/评审） | 与本仓 cbm（codebase-memory，DB 图谱）形成两种持久化范式对照：文件型换来可审计与可版本化，代价是查询能力 | ⚠️ README 级 | 未裁决（评估 cbm 是否补文件导出面） |
| 2 | 以 MCP server 统一对接多家 agent CLI（Claude Code/Cursor/Codex/Gemini） | 本仓回退链 cbm → tokensave → LSP → grep 的分发层设计参考：同一图谱服务多前端 | ⚠️ README 级 | 未裁决 |

## 不适配点 / 否决

- 无显式否决项；benchmark 主张均出自官方 README，未采纳为事实。

## 资源链接

- 仓库：<https://github.com/trailhq/Graft>
- 调研产出：2026-09-13 会话（README + CLI 用法 + benchmark 浏览）
