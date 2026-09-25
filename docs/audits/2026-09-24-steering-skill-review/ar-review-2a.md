# awesome-rules 审查报告 #2 — steering/git-conventions.md

- 审查对象：`/Users/dreambt/sources/awesome-rules/steering/git-conventions.md`（199 行，全文精读；分段读取 1-39 / 39-73 / 73-153 / 151-199 / 174-199，107-140 另行重读复核——全部引用行号均有本会话真实读取输出支撑）
- 基线对账披露：任务基线 dfe1732；实测 HEAD=3536e53（其上 2 个 docs 提交：f7ecb07 ADR-017 双层反馈范式、3536e53 CLAUDE.md 审查子代理挂起降级条款），工作树 clean。两提交均不触及本文件及本文件引用的全部路径（git diff dfe1732..HEAD 仅 CLAUDE.md、docs/adr/*），审查结论不受漂移影响。
- 标准适用声明：A 类针对 SKILL.md，本对象为 steering 文件，A 不直接适用（其中"引用路径逐一核实存在"一条按 B-4 对本文件执行完毕）；B、C 全量适用。
- 交叉核实手段：根 CLAUDE.md、commitlint.config.js、tools/git/lefthook/commitmsg-check.sh、tools/gauntlet.sh、tools/check_doc_freshness.py（R9）、.factory/feedback.py、.factory/README.md、.gitignore、CONTRIBUTING.md、hooks/load-steering.sh、steering/ 全部 frontmatter、skills/ 全量 grep。

---

## 发现

**F1** | steering/git-conventions.md:4 | B | 🟠 建议改
`inclusion: always` 是无消费方的死字段：hooks/load-steering.sh 全文 grep "inclusion" 零命中（hook 只扫 title/scenario 生成索引）；CONTRIBUTING.md:146 自认「部分历史文件保留的既有字段，新增文件无需写」。且 6 个 steering 文件取值互不一致（本文件及 4 个为 always，review-report-standards.md:4 为 manual），进一步印证字段无运行时语义——"manual/always" 的区别不产生任何行为差异。
修改建议：改前 `inclusion: always` → 改后 删除该行。若仓方决定保留历史字段，则须先在 load-steering.sh 实装语义，二选一，维持现状最差（读者误以为字段在起作用）。
依据：B-1（frontmatter 完整 + inclusion 取值合理）。注：CONTRIBUTING 既已定性 legacy，本条属"标准与仓内既有写法冲突，按审查标准原样报告"。

**F2** | steering/git-conventions.md:10 | B | 🟠 建议改
「Commit 格式（强制）」节首条要求手工合并提交不得沿用 `Merge branch 'xxx' of ...` 平台默认主题，但本地门禁恰好整体豁免被禁形态：tools/git/lefthook/commitmsg-check.sh:10 `sed -n '1p' "$MSG_FILE" | grep -qE '^(Merge |Revert |Auto-Merged )' && exit 0`——任何 `Merge ` 开头的主题（含平台默认形态）直接放行、不进 commitlint。平台侧 web-merge 本就不经本地钩子，因此本地豁免拦掉的正是该条款唯一可机械检查的对象：条款实际零机械执行，与 CLAUDE.md:37「标注强制的条款应同步评估可机械检查性……门禁查不出违规的强制条款只靠人记，效力弱」直接冲突。
存量佐证（本仓实测，2026-09-24）：`git log --merges` 计 211 个合并提交，205 个为 `Merge ` 前缀默认主题——其中 192 个 `Merge pull request`（平台侧产生，本就不经本地钩子）、1 个 `Merge branch`（本地默认形态，属 :10 禁用范围且被钩子豁免放行）；另 5 个为规范式主题，未命中豁免前缀、正常通过 commitlint——反证钩子对非默认前缀的合并主题确有校验，缺口收敛于 `^Merge ` 豁免本身。
修改建议（二选一）：
(a) 门禁侧：commitmsg-check.sh:10 收窄豁免范围（保留 `Auto-Merged `，`^Merge ` 不再整体放行，交由 commitlint 按 :10 规则校验），并在 tools/test_gauntlet_checks.sh 增负控制用例：`Merge branch 'x' of ...` 主题必须被拦；
(b) 文档侧：:10 句尾追加「（本地 commit-msg 钩子对 `Merge ` 前缀整体豁免，本条当前仅靠人记）」。
依据：B-2（【强制】条款机械可查性评估）+ CLAUDE.md:37。

**F3** | steering/git-conventions.md:119 | B | 🟠 建议改
【强制】条款范围「仓内禁提交凭据」与所声明门禁的覆盖面不符：tools/gauntlet.sh:332 实测扫描目标为 `scripts tools hooks skills arch-hawkeye .factory .github`——不含 steering/、docs/、仓根 md；.github/ 下 grep gitleaks/trufflehog/secret 零命中，无第二道全仓密钥扫描。即本文件所在的 steering/ 目录不在任何密钥门禁覆盖内，「仓内」实为「7 个目录内」。
修改建议（择一，推荐前者）：
(a) 门禁侧：tools/gauntlet.sh:332 改前 `must_not_match "$SECRET_PATTERN" scripts tools hooks skills arch-hawkeye .factory .github` → 改后 同句尾追加 ` steering docs`，并在 steering/ 植入假凭据补一条负控制；
(b) 文档侧：:119 改前「……已接线门禁：`tools/gauntlet.sh` `must-not-secrets` 层（……）」→ 改后 句尾追加「（门禁覆盖 scripts/tools/hooks/skills/arch-hawkeye/.factory/.github；steering/、docs/ 与仓根文件暂仅靠人记）」。
依据：B-2 + CLAUDE.md:37。核实备注：层名 `must-not-secrets`（gauntlet.sh:334）、`tools/must_not_match.sh`、SECRET_PATTERN 均实存，条款对门禁的引用本身准确。

**F4** | steering/git-conventions.md:160 | B | 🟠 建议改
引用的脚本路径在本仓恒不存在：`.lefthook/pre-push-delete-guard.sh`——.gitignore:12 忽略 `.lefthook/`，:10-11 注释明示「install.sh 拷贝 tools/git/lefthook/ 到业务项目；本仓库直接引用源目录，不产生此运行时目录」；仓内权威源 `tools/git/lefthook/pre-push-delete-guard.sh` 实存（已核实）。本文件经 SessionStart 注入本仓会话（scenario「提交代码/创建分支/PR」），agent 按文中路径找守卫必然落空。同段 :155/:158 的 `.lefthook/*` 是「本地实验」语境（下游业务项目视角）尚可辨析，:160 是唯一以确定性口吻描述单个守卫脚本行为的引用，误导最强。
修改建议：改前「判定由 `.lefthook/pre-push-delete-guard.sh` 读 pre-push stdin 的 ref 更新行完成」→ 改后「判定由 `tools/git/lefthook/pre-push-delete-guard.sh`（install.sh 分发后位于下游 `.lefthook/`）读 pre-push stdin 的 ref 更新行完成」。
依据：B-4（引用路径逐一核实存在）。

**F5** | steering/git-conventions.md:41 | C | 🔵 可选
「自动包含，无需手工登记」与紧邻 :44「新增技能时追加到根 `commitlint.config.js` 的 `scope-enum`」表述打架：枚举是手工静态清单（commitlint.config.js:21-25 硬编码 14 个技能名），「自动」的只是 R9 门禁的事后校验（tools/check_doc_freshness.py:547-560：技能目录名 ⊆ 根枚举、规范表↔枚举双向对齐、分发件 ⊆ 根枚举）。读者按 :41 字面可理解为「新增技能零动作」。
修改建议：改前「`skills/`（指针行——各技能 scope 由根配置的 scope 枚举自动包含，无需手工登记）」→ 改后「`skills/`（指针行——本表不逐技能登记，权威枚举见根 `commitlint.config.js`；新增技能须按下行规则追加枚举，表↔枚举一致性由 doc-freshness R9 门禁守护）」。
依据：C-1（DRY/术语准确）+ B-3。

**F6** | steering/git-conventions.md:110 | C | 🔵 可选
破坏性变更规则双处维护：:46-53「§破坏性变更（强制标记）」是权威表述（两种写法 + 推荐并用 + 机理），:110 在「基础要求」清单里重复其结论一行；将来写法演进（如语义化版本工具变更识别规则）需同步两处。
修改建议：改前 `- 破坏性变更必须标记（\`!\` 或 \`BREAKING CHANGE:\`）` → 改后 删除该行，或改为 `- 破坏性变更必须标记（见 §破坏性变更（强制标记））`。
依据：C-DRY + B-3（重复条款收敛到单一权威源）。

**F7** | steering/git-conventions.md:48 | B | 🔵 可选
「破坏性变更（强制标记）」节未按 CLAUDE.md:37 标注可机械检查性边界：某提交「是否属破坏性变更」是语义判断，任何门禁都查不出漏标（commitlint 只校验已出现标记的格式——commitlint.config.js:43-44 注释确认两种写法被识别并触发 major bump）；`!` 触发版本自动化依赖人先标对。
修改建议：改前「含破坏性变更的提交**必须**显式标记，这是触发 major 版本号的唯一信号：」→ 改后 句尾追加「（是否破坏无法机械判定，漏标仅靠人记；标记一旦出现，格式与版本效应由 commitlint/semantic-release 自动处理）」。
依据：B-2。

**F8** | steering/git-conventions.md:109、:185 | C | 🔵 可选
引号风格不一致：全文引用语统一用直角引号「」（:133「符号已定义 / already defined」、:141「领先 3 个提交待推送」、:147「远端更完整」、:149「不可判定」、:157「实验中」、:158「上游同步」等），唯两处例外用弯引号""：:109 `（如 "fix"、"update"）`、:185 `"疑似垃圾文件"` 与 `"0B 空文件"`。
修改建议：:109 改前 `（如 "fix"、"update"）` → 改后 `（如「fix」「update」）`；:185 改前 `"疑似垃圾文件"`/`"0B 空文件"` → 改后 `「疑似垃圾文件」`/`「0B 空文件」`。
依据：C-2（中英文/标点风格一致）。

**F9** | steering/git-conventions.md:112、:194 | C | 🔵 可选
历史重写规则散布三处、两个同前缀小节零互引：「提交要求 > 历史重写与敏感信息」（:112-121）、重写两不变量（:97，挂在§提交要求下）、「Pull Request > 历史重写与外部贡献」（:194-199），另 :147-151 分叉处置三件套亦属重写等价性主题。从 :198（force-push 前禁用 ruleset）入手的读者不易发现 :118 的 bundle 全量备份要求——两者是同一操作的前置与执行。
修改建议（择一）：① 低成本：:194 节首补一行交叉引用「通用备份/复扫/不变量要求见『提交要求 > 历史重写与敏感信息』」；② 高成本：将 :97、:112-121、:194-199 合并为独立 `## 历史重写` 章。
依据：C-3（结构一致/可检索性）。

**F10** | steering/git-conventions.md:2（连动 :7、:3） | C | 🔵 可选
标题窄于内容：title/H1「Git 提交规范」，但分支命名（:123）、同步纪律（:132）、受保护 main 写者治理（:145）、门禁双向流（:153）、Pull Request（:162）等非"提交格式"主题约占全文 2/3；scenario（:3）已如实写「提交代码/创建分支/PR」，frontmatter 反而比标题诚实。
修改建议：改前 `title: Git 提交规范` / `# Git 提交规范` → 改后 `title: Git 工作流规范` / `# Git 工作流规范`；连动更新 CLAUDE.md:8 索引句「Git 提交」→「Git 工作流」（load-steering 索引由 frontmatter 自动生成，无需改 hook）。
依据：C-3（术语与内容一致）。改名会改变会话注入索引的显示名，收益与扰动均小，故列可选。

---

## 统计

| 严重度 | 数量 | 编号 |
| --- | --- | --- |
| 🔴 必改 | 0 | — |
| 🟠 建议改 | 4 | F1（inclusion 死字段）、F2（合并提交强制条款被钩子豁免）、F3（密钥门禁覆盖面 < 条款范围）、F4（.lefthook 路径本仓不存在） |
| 🔵 可选 | 6 | F5、F6、F7、F8、F9、F10 |
| 合计 | 10 | 类别分布：B×5（F1-F4、F7）、C×5（F5、F6、F8、F9、F10）、A×0（不适用于 steering 文件） |

## 审查中上报事项

1. **基线漂移**：HEAD=3536e53 ≠ 基线 dfe1732（2 个 docs 提交：f7ecb07、3536e53），工作树 clean；漂移文件集与本文件及其引用路径零交集，结论不受影响（已在报告头披露）。
2. **门禁侧修复超出本次只读边界**：F2/F3 的根治动作在 tools/git/lefthook/commitmsg-check.sh 与 tools/gauntlet.sh（本仓代码，非本审查对象）；文档侧标注可先行落地，门禁侧改动建议另立任务并按仓规附负控制测试。
3. **inclusion 死字段系 6 文件共性问题**：cross-repo-contract-standards.md:4、openapi-standards.md:4、review-report-standards.md:4、task-package-standards.md:4、testing-standards.md:4 同样携带；F1 仅就本文件提出，批量清理需仓方统一决策（删除 vs 在 load-steering.sh 实装语义）。
4. **正面核实清单（无误项，供后续审查免重复核验）**：
   a. :106 三阈值 100/150/300 与 commitlint.config.js:29-32 逐值一致（subject/header/body 均 error 级）；
   b. scope 表业务域 4 值 + 工程 8 值与 scope-enum 逐值一致，R9 双向锚定（check_doc_freshness.py:547-631）当前成立；
   c. :119 引用的 `must-not-secrets` 层、`tools/must_not_match.sh`、SECRET_PATTERN 机制均实存（gauntlet.sh:331-334）；
   d. :149 对 `_patch_id` 的断言与 .factory/feedback.py:328-337 实现吻合（docstring：「空 diff（纯 merge/空提交）返回 None」）；
   e. :158 引用的 `.factory/sync-from-upstream.sh` 实存、`.factory/README.md:341`「上游同步」节实存；
   f. :44 分发件 `tools/git/commitlint.config.cjs` 实存且 R9c 锚定其 ⊆ 根枚举；
   g. 跨文档无重复/矛盾：根 CLAUDE.md 无 commit 格式条款；skills/ 中仅 work-report/SKILL.md:81 以指针互补引用本文件；分支/PR/原子提交主题在 steering/ 与 CLAUDE.md 中无第二处维护；
   h. 文内示例（:68-92、:10）全部符合本仓 commitlint 口径（type 合法、中文主题、长度达标）。
