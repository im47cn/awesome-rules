# 平台目录映射矩阵

> @date 2026-09-20｜发布面（MISSION 周界）平台分发入口的统一映射与漂移核对基线。
> 安装操作指引（人读）见 [docs/ai-coding-tools-setup.md](ai-coding-tools-setup.md)，本矩阵不复制其全文，只做映射与核对。

数据契约（三源交叉，冲突以源 2 实地为准，差异记入 §4 漂移上报）：

- **源 1**（人读口径）：[docs/ai-coding-tools-setup.md](ai-coding-tools-setup.md) 插件一览表（L7-16）与分平台安装节
- **源 2**（实地核对）：各发布面目录 manifest / extension 文件逐字段读取
- **源 3**（登记面）：[tools/check_plugin_versions.py](../tools/check_plugin_versions.py) L38-53 版本清单 allowlist + 排除集

## 1. 矩阵主表

| 平台 | 安装入口（命令） | 项目 scope 路径 | 全局 scope 路径 | 规则/技能注入方式 | 数据来源 |
|---|---|---|---|---|---|
| Claude Code | `claude plugin marketplace add git@github.com:im47cn/awesome-rules.git` + `claude plugin install awesome-rules@awesome-rules` | `.claude-plugin/plugin.json` + `marketplace.json`（市场注册 source 指向仓库根 `./`） | 无仓侧声明† | plugin.json `skills` 字段引共享 `./skills/`（L10）；描述层声明 SessionStart 自动注入规范索引（L3，机制在 [hooks/hooks.json](../hooks/hooks.json)）；矩阵排除共享 hook 配置 | 源1:23-24｜源2:.claude-plugin/plugin.json:3,10、marketplace.json:7-13｜源3:39,51 |
| Codex CLI | `codex plugin marketplace add git@github.com:im47cn/awesome-rules.git` + `codex plugin install awesome-rules@awesome-rules` | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json`（本地路径注册 `./`，installation=AVAILABLE） | 无仓侧声明† | plugin.json `skills` 字段引共享 `./skills/`（L8）；清单与市场分置两目录（源1:40 易错点） | 源1:33-38｜源2:.codex-plugin/plugin.json:8、.agents/plugins/marketplace.json:8-17｜源3:40,50 |
| Cursor | `cursor plugin marketplace add git@github.com:im47cn/awesome-rules.git`（或 Customize → Rules → Add Rule → Remote Rule 粘贴仓库 URL） | `.cursor-plugin/plugin.json` + `marketplace.json`（source `.`） | 无仓侧声明† | 无 `skills` 字段——规则经插件包内文件生效；`.cursor/rules/` 只识别 `.mdc` 的限制不适用于插件格式（源1:50） | 源1:44-50｜源2:.cursor-plugin/plugin.json:1-18、marketplace.json:12-15｜源3:41-42 |
| Kimi (Moonshot) | `kimi plugin marketplace add git@github.com:im47cn/awesome-rules.git` | `.kimi-plugin/plugin.json` + `marketplace.json`（唯一以远端 git URL 为 source 的注册） | 无仓侧声明† | plugin.json `skills` 字段引共享 `./skills/`（L8）+ `interface` 展示元数据（L9-15，capabilities=Read） | 源1:54-56｜源2:.kimi-plugin/plugin.json:8-15、marketplace.json:2-9｜源3:43,49 |
| Grok (xAI) | `grok plugin marketplace add git@github.com:im47cn/awesome-rules.git` | `.grok-plugin/plugin.json` + `marketplace.json`（source `.`） | 无仓侧声明† | 无 `skills` 字段（与 Cursor plugin.json 同构：displayName/keywords 元数据，L1-18） | 源1:60-62｜源2:.grok-plugin/plugin.json:1-18、marketplace.json:7-13｜源3:44,52 |
| OpenCode | 无命令——clone 后在该目录运行 `opencode` 自动读取 | `.opencode/opencode.json` | 无仓侧声明† | `instructions` 字段静态枚举 22 文件：12× `skills/*/SKILL.md`（L4-15）+ 9× `steering/*.md`（L16-24）+ `steering/gtsp/README.md` 总入口（L25） | 源1:64-68｜源2:.opencode/opencode.json:3-26｜源3:不在登记面（无 plugin/marketplace manifest） |
| Pi (Google) | 无命令——检出仓库后 Pi 自动发现 | `.pi/extensions/awesome-rules.ts` | 无仓侧声明† | TS 扩展 `resources_discover` 事件注册 `skillsDir`（=包根 `skills/`，L6-11） | 源1:70-72｜源2:.pi/extensions/awesome-rules.ts:6-11｜源3:不在登记面 |
| Crush | 无命令、无清单 | `skills/`（自动发现面） | 无仓侧声明† | 平台自动发现 `skills/`，无需 manifest（源1:16）；`.crush/` 目录为空占位（见 §2） | 源1:16｜源2:skills/ 目录实存｜源3:不在登记面 |

† 全局 scope 统一口径：源 2 全部 12 个文件（11 个 manifest/extension + `.opencode/opencode.json`）逐字段核对，无用户目录或绝对安装路径声明；全局安装是目标平台 marketplace 机制侧行为，不由本仓文件写入。唯一作为安装 source 的绝对地址为 `.kimi-plugin/marketplace.json:7` 的 git 源 URL（homepage/websiteURL/$schema 等绝对 URL 属元数据，非安装目标）。

‡ Pi 例外语义：`.pi/` 整目录在 `.gitignore:41`（2026-09-15 裁决：remote-pi relay 本机基建，运行时生成不入库），但 `extensions/awesome-rules.ts` 系先于该裁决入库的已跟踪文件（`git ls-files -- .pi` 实证唯一在库）——克隆/worktree 正常复现，Pi 自动发现不受影响；该 ignore 仅拦截新增 `.pi/` 文件。

枚举一致性核对（源 2 vs 磁盘）：opencode 枚举的 steering 根 9 个 `.md` 与 `steering/*.md` glob 结果一一对应（无漏登/多登），gtsp 子目录经 README 总入口不逐文件展开；`skills/*/SKILL.md` glob = 12 目录全有 SKILL.md，与枚举 12 项一致。

## 2. 空目录备注

`.crush/`、`.vscode/` 为 **gitignored 目录**（`.gitignore:8`——crush 会话运行时产物；`.gitignore:19`——编辑器个人设置）：设计意图即不入库，任何新鲜克隆/worktree 天然不存在；主检出的空目录（2026-09-01 创建）仅为本机运行残留，非分发面占位。

- 消费侧实际触达面 = §1 的 8 个内容入口；Crush 平台经 `skills/` 自动发现（源1:16），与 `.crush/` 目录存在与否无关
- `.vscode/` 语义为个人编辑器设置（gitignore 出处即设计意图），非仓内配置预留位（见 §4 漂移上报 #1）

## 3. Comet 37 平台对照

Comet（npm CLI `@rpamis/comet`）宣称 `comet init` 支持 37 个编码平台，映射矩阵维度为平台 × 项目/全局 scope × 路径差异（含 Antigravity 双版本路径）——详见 [docs/research/comet.md](research/comet.md) 借鉴点 #7（本节不复制其内容）。与本仓差距：

| 维度 | Comet | 本仓 |
|---|---|---|
| 覆盖规模 | 37 平台 | 8 个内容入口 + 2 个空占位 |
| 写入机制 | npm 全局 CLI 安装器主动写入平台目录 | 清单 checked-in，各平台 marketplace/自动发现被动消费 |
| scope 粒度 | 平台 × 项目/全局 × 路径三轴差异 | 仓侧仅项目 scope（发布面 checked-in）；全局路径为平台侧行为，无仓侧声明 |

适用定位：本矩阵即 P3 分发层验证的平台覆盖基线（借鉴点 #7 的仓内落点）。

## 4. 漂移上报（供人工裁决；发布面/治理层本任务只读）

| # | 现象 | 期望对齐语义 | 建议处置 |
|---|---|---|---|
| 1 | MISSION 周界列 10 目录，实况 8 个内容入口 + 2 个 gitignored 目录（`.crush/`=`.gitignore:8` 运行时产物、`.vscode/`=`.gitignore:19` 个人设置——克隆天然不存在，主检出空目录系本机残留） | 周界清单只列实际分发面（或显式注明 gitignored 残留不属分发面） | 人工 PR：MISSION 清单收敛为 8 内容入口，或加注 `.crush/`/`.vscode/` 为 gitignored 本机残留（治理文件，本任务只读） |
| 2 | plugin.json 描述层口径漂移：claude（L3）"11 个审查/工具技能 + 6 项通用设计规范 + GTSP 工程规范"，codex（L4）"测试、数据库、API、Git 四大规范"（无技能计数、无 GTSP）；磁盘实况 = 12 技能目录（`skills/*/SKILL.md`）+ 9 通用规范（`steering/*.md`）+ `steering/gtsp/` | 同一 `skills/` 单源负载 → 双平台描述与磁盘实况一致（若刻意用子集口径须界定） | 人工 PR 对齐描述（claude 11→12、6→9；codex 补 GTSP 或统一话术） |
| 3 | 注入能力声明不对称：claude 描述声明 "SessionStart 自动注入规范索引"（plugin.json:3，机制实存于 `hooks/`），codex 侧无对应声明 | 注入能力宣传与各平台实际注入行为一致 | 人工裁决：codex 是否补等价声明，或描述层统一注明差异 |
