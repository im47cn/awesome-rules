# tokensave-mcp — mcporter 代理模式设计论证

## 为什么不常驻注册

tokensave MCP server 暴露 ~100 个工具。实测两种常驻成本：

| 场景 | 注入成本 |
|---|---|
| 开启 tool search（schema 按需） | 连接时全量注入 ~100 个工具名，约 1.2k token |
| 关闭 tool search（schema 前置） | 约 20k token/轮 |

而 30 天实测调用约 10 次，按「性价比排序」（调用数 ÷ 注入万 token）远低于保留阈值。

## 为什么用 mcporter

与 [alibabacloud-devops](../alibabacloud-devops/README.md) 同一模式：`mcporter list` 按需查工具、
`mcporter call` 按需调用，零常驻注入。冷启动开销用 daemon 模式规避。

## 与 codebase-memory-mcp 的分工

两者均为代码图谱，全局裁决（2026-08-20，30 天实测 264 vs 10 次调用）：

1. cbm 为默认发现层（符号/调用链/源码/架构）
2. tokensave 仅限独有专项能力：测试覆盖、rename/replace_symbol、dead code、复杂度、依赖矩阵、blame
3. 回退链：cbm → tokensave → grep/glob

本技能只承接第 2 类；第 1 类请直接用 cbm MCP 工具。

## 恢复常驻注册（如需）

```bash
claude mcp add tokensave -s user -- /Users/dreambt/.local/bin/tokensave serve
```
