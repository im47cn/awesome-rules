---
name: tokensave-mcp
description: tokensave 代码图谱专项能力（mcporter 代理模式）。当用户提到以下任意意图时激活：测试覆盖、覆盖率缺口、测试映射、死代码、无用函数、复杂度、god class、依赖矩阵、耦合分析、blame、重命名重构、rename 预览、影响面、session recall。仅覆盖 tokensave 独有专项能力；常规符号查找/调用链/架构概览走 codebase-memory-mcp（默认发现层），本技能不承接。通过 mcporter CLI 按需调用，不在 Claude Code 中常驻注册。
---

# tokensave 代码图谱（mcporter 代理模式）

**红线：刻意不注册为 MCP server**（连接时全量注入 ~100 个工具名约 1.2k token，关闭 tool search 时 schema 约 20k token/轮）。
所有调用走 mcporter CLI 按需查询与执行，设计论证见 [README](README.md)。

## 职责边界（先读这个）

tokensave 与 codebase-memory-mcp 职能重叠，按全局裁决分工：

- **默认发现层 = codebase-memory-mcp**：符号查找、调用链、源码读取、架构概览 → 不要用本技能
- **本技能仅承接 tokensave 专项能力**：测试覆盖（覆盖缺口/测试映射/测试风险）、
  dead code、复杂度与 god class、依赖矩阵（DSM/耦合）、blame、rename/replace_symbol 重构安全网、session recall

不确定某个能力归属时：先 `mcporter list` 查工具名，若与专项能力无关则回退 cbm。

## 前置：命令约定

```bash
# 下文以 $SRV 代指 server 启动命令（二进制位于 ~/.local/bin/tokensave）：
SRV='tokensave serve'
# mcporter 未全局安装时用 npx：npx -y mcporter@latest
```

## 工具调用三件套

```bash
# 1. 查工具（先查后用，不要猜工具名；按专项能力关键词过滤）
mcporter list --stdio "$SRV" --schema | grep -iE "coverage|test_map|test_risk"
mcporter list --stdio "$SRV" --schema | grep -iE "dead|complexity|god_class|dsm|blame|rename"

# 2. 调工具（参数 key=value，含空格值用 key:"..."；工具返回含 tokensave_metrics: 行时向用户报告节省）
mcporter call --stdio "$SRV" tokensave_test_coverage path=src/main/java

# 3. 可选：daemon 模式（避免每次冷启动索引）
mcporter daemon start --stdio "$SRV"
```

## 典型工作流

### 测试覆盖缺口分析

```bash
mcporter list --stdio "$SRV" --schema | grep -i "test"      # 先查覆盖类工具全集
mcporter call --stdio "$SRV" <coverage 工具> path=<目标路径>  # 拿到未覆盖符号清单
mcporter call --stdio "$SRV" <test_map 工具> ...             # 映射测试与被测代码
```

### 重构安全网（rename / dead code）

```bash
mcporter call --stdio "$SRV" <rename_preview 工具> qualified_name=<符号> new_name=<新名>
mcporter call --stdio "$SRV" <dead_code 工具> path=<路径>     # 确认无引用后再删
```

## 相关文件

- 设计论证（为何代理模式、常驻成本测算）：[README](README.md)
