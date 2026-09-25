# awesome-rules 技能文档审查报告（ar-review-7）

- 审查对象（逐文件全文精读，一律只读）：`skills/alibabacloud-devops/SKILL.md`、`skills/doc-gen/SKILL.md`、`skills/tokensave-mcp/SKILL.md`、`skills/work-report/SKILL.md`
- 基线对账：HEAD = dfe1732（`git status` 工作树 clean，`git rev-parse HEAD` = dfe173295422ddfa02ee81dddc903e081a251b43），与任务基线一致，无漂移，无需披露事项
- 审查标准：A（Claude Code 技能编写最佳实践）/ B（steering 最佳实践——本次对象均为技能文件，B 不直接适用，仅在涉及 steering 交界引用处核实目标存在性）/ C（DRY/KISS/术语一致）
- 仓内权威依据（引用时给出行号，均经实际读取）：`CLAUDE.md`（仓根总则）、`skills/README.md`（技能编写约束）、`tools/check_doc_freshness.py`（doc-freshness 门禁规则面）、`tools/frontmatter_lib.py` + `tools/check_frontmatter_manifests.py`（M2 门禁）、`tools/backfill_skill_manifests.py`（ADR-5 files 清单约定）

---

## 发现

### F1 | skills/alibabacloud-devops/SKILL.md:3（description）、:10（另协调 README.md:3、:7）| A | 🔴必改

**问题**：上游工具计数「165+ 工具」属易腐数字，出现在常驻注入面 description（:3）与正文红线（:10），并同数字四处维护（SKILL.md:3、:10；README.md:3、:7）。与文件自身 :42-43「工具清单随上游版本变化，**始终以 `mcporter list` 实时结果为准**，不依赖静态清单」直接自相矛盾——正文另有 :58「典型工作流（模式参考，工具名以实时查询为准）」、:76「工具（以 `mcporter list` 实时为准）」两处同类声明，全文件共三处「以实时为准」的自我原则，静态计数与之全面冲突。工具数随上游 server 版本漂移，静态计数必然过时。

**修改建议**：
- :3 改前 `阿里云云效 DevOps 平台工具集（165+ 工具）。` → 改后 `阿里云云效 DevOps 平台工具集（上百工具，数量以 mcporter list 实时结果为准）。`
- :10 改前 `**红线：刻意不注册为 MCP server**（165+ 工具 schema 常驻约 15k token/轮）。` → 改后 `**红线：刻意不注册为 MCP server**（全量工具 schema 常驻成本高，量级测算见 [README](README.md)）。`
- 协调：README.md:3、:7 的「165+ 工具」同步改「上百工具」；成本量级（约 15k token/轮）属带上下文的历史实测，保留在 README 即可。

**依据条款**：skills/README.md:7-22【强制】「不得静态复制可动态获取的内容」（:11 明列「外部 MCP server 的工具清单」；:20 明确记载本技能「曾静态罗列 165 个 MCP 工具 → 改为 mcporter list 动态查询」的整改教训，此计数系该反模式残留）；CLAUDE.md:33「文档不写易腐数字……改写为可执行命令让事实自证」；本文件 :42-43、:58、:76 三处自我声明。

---

### F2 | skills/tokensave-mcp/SKILL.md:10 | A | 🟠建议

**问题**：「连接时全量注入 ~100 个工具名约 1.2k token，关闭 tool search 时 schema 约 20k token/轮」——三组计数/成本数字与 README.md:5-12 实测表格双份维护（「~100 个工具」仍是随上游漂移的计数断言）。SKILL.md 应只留红线结论 + 指针。

**修改建议**：:10 改前 `**红线：刻意不注册为 MCP server**（连接时全量注入 ~100 个工具名约 1.2k token，关闭 tool search 时 schema 约 20k token/轮）。` → 改后 `**红线：刻意不注册为 MCP server**（两种模式常驻注入成本实测与性价比裁决见 [README](README.md)）。`（README 的实测表是设计论证的合理归宿，不删。）

**依据条款**：标准 A 渐进式加载；CLAUDE.md:33；skills/README.md:15「SKILL.md 只保留工作流与决策树」。

---

### F3 | skills/work-report/SKILL.md:6（description；协调 :76 与 README.md:10、:58）| A/C | 🟠建议

**问题**：description 称「输出 3 种受众模板（自用流水 / 对 leader / 对外汇报）」，实际为 4 种：README.md:10 标题「三种受众模板」下的表格有 4 行（自用流水/对 leader/对外汇报/团队汇总），SKILL.md:75-76 列模板 B/C/D + 内联默认「对 leader」= 4。description 枚举漏掉团队汇总，而其自身触发词清单（:8「团队日报、团队产出、成员工作汇总」）恰恰指向它；README.md:58 还引用了全仓从未定义的「模板 A」。同一「三种」在两文件指代不同的集合，计数已实际漂移。

**修改建议**：
- SKILL.md:6 改前 `输出 3 种受众模板（自用流水 / 对 leader / 对外汇报），` → 改后 `按受众输出模板（自用流水 / 对 leader / 对外汇报 / 团队汇总），`（去计数，防再漂移）
- 配套：README.md:10 `## 三种受众模板` → `## 受众模板`；SKILL.md:76 锚点同步为 `README.md#受众模板`
- README.md:58 `用模板 A` → `用「对 leader」模板`（或在两文件显式定义默认模板即模板 A，二选一后全仓统一）

**依据条款**：标准 A 不写易腐计数字；标准 C 术语一致；CLAUDE.md:33。

---

### F4 | skills/alibabacloud-devops/SKILL.md:25-38 ↔ skills/tokensave-mcp/SKILL.md:31-43 | A | 🟠建议

**问题**：通用 mcporter「工具调用三件套」（`list --stdio "$SRV" --schema | grep` → `call key=value` → daemon 模式）作为同一操作规则在两个技能各维护一份，且已实际漂移：tokensave:28 有「mcporter 未全局安装时用 npx：npx -y mcporter@latest」兜底，alibabacloud 无此说明；daemon 用法两处形态不同（alibabacloud:36-37 `mcporter config add yunxiao && mcporter daemon start` 后具名调用 `mcporter list yunxiao`，tokensave:42 `mcporter daemon start --stdio "$SRV"`）。通用 CLI 用法的修改需要双处同步，符合「重复维护同一规则」的反模式。

**修改建议**：单源化通用层——参数双语法（key=value / key:"..."，经本机 `mcporter call --help` 证实均合法）、daemon 用法、npx 兜底收敛到一处（建议扩充 alibabacloud-devops/README.md 的 mcporter 节，tokensave/README.md:16 已有「与 alibabacloud-devops 同一模式」指针，落点现成；或放 skills/_shared/）；两份 SKILL.md 各保留 server 特有部分（$SRV 定义、env 约定、业务域关键词）+ 一行指针。落地前先实测两种 daemon 形态的正确性（见上报事项 3）。

**依据条款**：标准 A「技能间边界清晰，不与其他技能重复维护同一规则」；skills/README.md:22「单一数据源只允许存在于脚本/上游」。

---

### F5 | skills/alibabacloud-devops/SKILL.md:110 | A/C | 🟠建议

**问题**：「（实测 2026-09-16：gtsp-wop-callback → 7264847）」把实例态映射（具体仓库短名 → 数字 ID）写进文档，与本文件 :92-93 自己声明的原则「实例态数据（fieldId 等）随 space 模板变化，正确位置是代码运行时发现，不是文档」直接矛盾；该映射随仓库增删即腐烂，且日期戳暴露其时效性。

**修改建议**：删除整个括注「（实测 2026-09-16：gtsp-wop-callback → 7264847）」——前文「短名或不带 org 的群组路径一律 404——正确入口是先 `list_repositories organizationId=<orgId> search=<关键词>` 拿数字 ID」已完整承载可复用结论，括注只余个例噪音。

**依据条款**：标准 A（SKILL.md 只放稳定操作指引）；文件内部一致性（:92-93 自我原则）。

---

### F6 | skills/alibabacloud-devops/SKILL.md:114（对照 :97）| C | 🟠建议

**问题**：swagger.json 排错指引近逐字重复两次：:97「**MCP server 仓 `docs/*.swagger.json`**（GitHub 链接）——字段必填性/类型/枚举一查便知，比帮助文档表格结构化」（「排错信源优先级」第 1 条）与 :114（「注意」末条）「OpenAPI 精确 schema 见 …… 仓 `docs/*.swagger.json`（比帮助文档表格更结构化，字段必填性/类型/枚举一查便知）」。同一事实双处维护，改一处漏一处。

**修改建议**：:114 改前 `官方文档：https://help.aliyun.com/zh/yunxiao/ ；OpenAPI 精确 schema 见 [alibabacloud-devops-mcp-server](https://github.com/aliyun/alibabacloud-devops-mcp-server) 仓 \`docs/*.swagger.json\`（比帮助文档表格更结构化，字段必填性/类型/枚举一查便知）。` → 改后 `官方文档：https://help.aliyun.com/zh/yunxiao/ ；schema 查证信源优先级见上文「排错信源优先级」节。`

**依据条款**：标准 C DRY。

---

### F7 | skills/doc-gen/SKILL.md:182 | A | 🟠建议

**问题**：「npm 构建失败从静默跳过改为 `exit 1`（breaking）：依赖旧行为的脚本需显式降级」是变更史叙述而非现状契约：现行为已由 :179 完整定义（「1 = 阶段失败（manifest 校验失败 / npm 缺失或 install/build 失败）」），本行与 :179 重复；且「需显式降级」无任何操作落点（如何降级无处可查），是悬空指引。

**修改建议**：删除 :182。若需保留 breaking 迁移指引，移至 README.md「文档」节（:121 起）并写明具体降级做法或链接 CHANGELOG 对应条目。

**依据条款**：标准 A 渐进式加载（历史/背景叙述归 README）；标准 C DRY。

---

### F8 | skills/work-report/SKILL.md:37-38 | A | 🟠建议

**问题**：用法行把 `--team` 表述为可独立使用（:38「团队模式（每条 commit 附 author email，AI 按成员分组）：加 --team」），但脚本硬校验 `--team` 必须配合 `--author`，单用直接 `exit 2`（scripts/fetch-commits.sh:48-50：「✘ --team 模式需配合 --author 指定团队成员（否则会扫描目录下所有人 commit，爆炸）」）。AI 按 SKILL.md 直跑 `bash scripts/fetch-commits.sh --team` 必然失败。

**修改建议**：:38 改前 `# 团队模式（每条 commit 附 author email，AI 按成员分组）：加 --team` → 改后 `# 团队模式（每条 commit 附 author email，AI 按成员分组）：加 --team，须配合 --author 指定团队成员（脚本硬校验，缺省 exit 2）`

**依据条款**：标准 A（SKILL.md 是 AI 操作指引，须与脚本真实 CLI 契约一致——本次逐一核实证实的旗标面：--since/--author/--exclude/--team 均真实存在，唯 --team 搭配约束未写）。

---

### F9 | skills/alibabacloud-devops/SKILL.md:90 | A | 🔵可选

**问题**：「已由 ADR-008 hosting 抽象层取代」只提名字未给链接（ADR-007 在 :92 有链接；docs/adr/ADR-008-hosting-abstraction.md 实际存在，已核实）。

**修改建议**：:90 改前 `已由 ADR-008 hosting 抽象层取代` → 改后 `已由 [ADR-008](../../../docs/adr/ADR-008-hosting-abstraction.md) hosting 抽象层取代`

**依据条款**：标准 A 引用路径逐一核实（目标存在，补链接即闭环）。

---

### F10 | skills/tokensave-mcp/SKILL.md:21 | C | 🔵可选

**问题**：「若与专项能力无关则回退 cbm」——「cbm」缩写在本文首次出现且未定义（:3、:15、:17 均用全称 codebase-memory-mcp；仓内 research/graft.md:23 另有「cbm（codebase-memory）」的近似用法，亦非正式定义）。

**修改建议**（二选一）：:17 行「**默认发现层 = codebase-memory-mcp**」补「（下文简称 cbm）」；或 :21 直接用全称「回退 codebase-memory-mcp」。

**依据条款**：标准 C 术语一致。

---

### F11 | skills/doc-gen/SKILL.md:177 | C | 🔵可选

**问题**：「## 退出码与验收契约（强制）」用全角括号（强制）；仓根条款标注约定为【强制】/【推荐】（CLAUDE.md:44「标注【强制】的条款不可违反……【推荐】尽可能遵守」），技能域规则文件的主流标题形态亦为【强制】（api-guard/api-manual-rules.md:5、ddl-guard/ddl-manual-rules.md:5、skills/README.md:7 等）。注：code-review/SKILL.md:61-105 亦存在同类（强制）偏差，可一并收敛。

**修改建议**：:177 改前 `## 退出码与验收契约（强制）` → 改后 `## 退出码与验收契约【强制】`

**依据条款**：标准 C 标注/术语风格一致；CLAUDE.md:44。

---

## 统计

| 严重度 | 数量 | 编号 |
|---|---|---|
| 🔴 必改 | 1 | F1 |
| 🟠 建议 | 7 | F2、F3、F4、F5、F6、F7、F8 |
| 🔵 可选 | 3 | F9、F10、F11 |
| 合计 | 11 | 类别分布：A 8 条（F1-F5、F7-F9）、C 3 条（F6、F10、F11）、B 0 条（审查对象为技能文件，B 不直接适用）。【勘误 2026-09-25：原「A 9/C 4 + F3/F5 双标 A/C」与逐条类别标不符，经 CodeRabbit 复审指出后逐条重核更正】 |

按文件：alibabacloud-devops 5 条（F1、F4、F5、F6、F9）；doc-gen 2 条（F7、F11）；tokensave-mcp 3 条（F2、F4、F10）；work-report 3 条（F3、F8 及 F3 配套）。

## 审查中上报事项

1. **基线对账**：HEAD = dfe1732，工作树 clean，与任务基线一致，无漂移。
2. **路径/权限/契约核实全景（全部通过）**：doc-gen frontmatter `files:` 111/111 存在（逐条 `test -e` 核实；该清单系 ADR-5「全量 git 跟踪文件」既定约定，由 tools/backfill_skill_manifests.py 生成、M2 门禁断链单向检查守护，不判为渐进式加载违规）；docs/adr/ADR-007-forge-adapter.md、ADR-008-hosting-abstraction.md、steering/git-conventions.md、arch-hawkeye/、workspaces.example.toml 均存在；work-report/scripts/fetch-commits.sh 有执行位（-rwxr-xr-x）；doc-gen scripts/doc_gen.py 的 argparse 面（--init/--build/--manifest-only/--from-manifest/--output/diff base head --output/--markdown）与 SKILL.md:133-176 快速使用/diff 命令逐一吻合；doc-gen README `#项目配置`、work-report README `#三种受众模板` 锚点当前有效（F3 落地时须同步改锚点）。
3. **mcporter 本机实证与副作用披露**：本机装有 /opt/homebrew/bin/mcporter。`mcporter call --help` 证实 key=value 与 key:value 双参数语法均合法——alibabacloud:31-32「注释写 key:"..." 而示例写 key2="value 2"」不构成错误，未列为发现；`mcporter daemon --help` 顶层旗标仅见 --foreground/--json，未见 --stdio，tokensave:42 `daemon start --stdio "$SRV"` 形态正确性未定，F4 收敛前建议实测。**副作用**：执行 `mcporter daemon start --help` 意图查帮助，该子命令不识别 --help 直接启动了单用户 daemon（输出 "Single-user daemon started."）；已随即执行 `mcporter daemon stop` 复原并经 `daemon status` 确认 "Daemon is not running"。仓内文件零改动。
4. **work-report/README.md:1-4 带 steering 风格 frontmatter**（title + scenario），为四技能 README 中唯一；SessionStart hook 只扫 steering/ 目录，该 frontmatter 无任何消费者，疑似从 steering 迁移或复制模板时的遗留，建议仓主裁决删除或注明用途。
5. **判断性弃报（避免噪音）**：alibabacloud:99「13 种键名形态」、README:8「约 15k token/轮」、tokensave README:21「264 vs 10 次调用」属带日期/场景的历史实测记录（不随上游版本漂移），不按易腐计数报；CLAUDE.md:20 与 doc-gen SKILL.md:125 的 arch-hawkeye 边界为指针级重复，风险低未列发现；doc-gen `files:` 含 23 个测试文件与 package-lock.json 系 ADR-5 全量清单约定（见第 2 条），不判违规。
6. **门禁缺口提示（供仓主裁量）**：tools/check_doc_freshness.py R4 仅覆盖「测试 N 项」类数字陈述（:18-20），「165+ 工具 / ~100 个工具」类工具计数不在门禁面内。若采纳 F1/F2，按 CLAUDE.md:34「优先接线而非只修文档」原则，可给 doc-freshness 增一条 R 规则：skills/*/{SKILL,README}.md 禁止「`\d+\+?\s*(个)?工具`」精确计数形态（负控制：现行「165+ 工具」应命中）。
