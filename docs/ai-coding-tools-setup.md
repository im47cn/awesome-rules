# 安装本项目 Skills

本仓库适配多种 AI 编程工具的插件格式，用户添加市场后即可一键安装。

仓库内插件清单一览：

| 目录 | 工具 | 说明 |
|---|---|---|
| `.claude-plugin/` | Claude Code | plugin.json + marketplace.json |
| `.codex-plugin/` + `.agents/plugins/` | Codex CLI | plugin.json + marketplace.json |
| `.cursor-plugin/` | Cursor | plugin.json + marketplace.json |
| `.kimi-plugin/` | Kimi (Moonshot) | plugin.json + marketplace.json |
| `.grok-plugin/` | Grok (xAI) | plugin.json + marketplace.json |
| `.opencode/opencode.json` | OpenCode | 指令文件引用 |
| `.pi/extensions/` | Pi (Google) | TS 扩展注册 skills 路径 |
| `skills/` | Crush | 自动发现，无需清单 |

---

## Claude Code

```bash
claude plugin marketplace add git@github.com:im47cn/awesome-rules.git
claude plugin install awesome-rules@awesome-rules
```

验证：`/status` 查看已加载插件。触发：对话中提到"审查 DDL""建表"等关键词，或 `@awesome-rules:ddl-guard`。

> **易错点**：安装命令格式是 `插件名@市场名`，两者都是 `awesome-rules`。

## Codex CLI

```bash
codex plugin marketplace add git@github.com:im47cn/awesome-rules.git
codex plugin install awesome-rules@awesome-rules
```

或交互界面：`codex /plugins` → 浏览市场 → 安装。

> **易错点**：Codex 的插件清单在 `.codex-plugin/`，市场清单在 `.agents/plugins/`，两者目录不同。

## Cursor

```bash
cursor plugin marketplace add git@github.com:im47cn/awesome-rules.git
```

或在 **Customize → Rules → Add Rule → Remote Rule** 中粘贴仓库 URL。

> **易错点**：Cursor 的 `.cursor/rules/` 中只识别 `.mdc` 文件；插件内的 `.cursor-plugin/` 格式不受此限制。

## Kimi

```bash
kimi plugin marketplace add git@github.com:im47cn/awesome-rules.git
```

## Grok

```bash
grok plugin marketplace add git@github.com:im47cn/awesome-rules.git
```

## OpenCode

OpenCode 自动读取 `.opencode/opencode.json` 中声明的指令文件和 `AGENTS.md`。将仓库 clone 到任意位置后，在该目录运行 `opencode` 即可。

> **易错点**：OpenCode 的插件系统是 JS/TS 文件（`.opencode/plugins/`），不是 JSON 清单。本仓库通过 `opencode.json` 的 `instructions` 字段引用 SKILL.md 实现等效效果。

## Pi

Pi 通过 `.pi/extensions/` 下的 TS 扩展注册 skills 路径。无需手动安装，检出仓库后 Pi 自动发现。

---

## 前置依赖

检查脚本依赖 Python 3（标准库，无第三方依赖）：

```bash
python3 /path/to/awesome-rules/skills/ddl-guard/scripts/ddl_check.py --help
```
