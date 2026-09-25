# awesome-rules steering 文档审查报告（ar-review-2b）

审查对象：`steering/task-package-standards.md`、`steering/review-report-standards.md`、`steering/frontend-standards.md`
审查日期：2026-09-24 ｜ 方式：逐文件全文只读精读，行号均来自本次实际读取

## 基线对账（按任务要求披露）

- `git status`：工作树 clean，分支 `docs/adr-017-dual-feedback-paradigm`。
- **HEAD = 3536e53 ≠ 基线 dfe1732**，漂移 2 个 docs 提交：f7ecb07（docs/adr/ADR-017 + docs/adr/README.md）、3536e53（CLAUDE.md +3/-1 审查子代理挂起降级条款）。
- 漂移文件不含三个审查对象；但 CLAUDE.md 是重复性比对基准之一，其 :51-54 条款系基线后新增——本文比对按 HEAD 版执行。若需严格 dfe1732 视角复核，F2/F3 中 CLAUDE.md 侧行号需对旧版重核。

## 标准适用性声明

三对象均为 steering 文档而非 SKILL.md，标准 A 仅两条可平移适用：①引用路径逐一核实存在（已执行，结果见"正面核实"）；②不写易腐计数字（三文件中的数字均为冻结判例数据，不违）。其余 A 条款不适用。B、C 按序适用。

---

## 发现

**F1 | task-package-standards.md:54 | B | 🔴必改**
问题：强制条款指向死路径——"须先在 `.factory/decisions.md` 新增 ADR"。实测该文件不存在；ADR 台账已于 2026-09-20 整体迁入 `docs/adr/`（docs/adr/README.md:3 自述"原 `.factory/decisions.md`，2026-09-20 拆分迁入"）。Agent 按此条款执行会在废弃位置新开平行台账，裂解 ADR 单一索引，恰违反本仓 CLAUDE.md:41"单一权威目录"纪律。
修改建议：改前 "须先在 `.factory/decisions.md` 新增 ADR" → 改后 "须先在 `docs/adr/` 新增 ADR（按 `docs/adr/README.md` 索引格式登记）"。
依据：B-内部相对链接有效；C-DRY（单一权威源）。

**F2 | task-package-standards.md:88 | B | 🟠建议**
问题：与 CLAUDE.md:30 双处维护同一规则（并行任务文件所有权隔离 + 拉取远程选窗口）且已经漂移——CLAUDE 版多出"若已写盘须先比对未提交修改与 incoming 改动的文件交集再决定拉取方式"分支，steering 版无。双源不等价即重复维护的实证。
修改建议：收敛单一权威源到本文件 §3，CLAUDE.md:30 压缩为一句并引用："并行子任务按文件所有权隔离；拉取窗口与已写盘交集判定见 steering/task-package-standards.md §3"。（修改位置在 CLAUDE.md，本报告只建议。）
依据：B-与 CLAUDE.md 无重复条款。

**F3 | task-package-standards.md:87 | B | 🟠建议**
问题：omp 后台派发命令在两处各持一份模板且守卫不等价：本条含 `< /dev/null` stdin 防卡死守卫（实证卡 1400s），CLAUDE.md:31 的 herdr 派发模板 `omp -p --no-session --max-time 30m "$(cat /tmp/prompt-x.md)" > /tmp/x.out 2>&1` 无此守卫。同一坑只在一处设防。
修改建议：CLAUDE.md:31 命令补 `< /dev/null`，或整句改为引用本条 §3。
依据：B-与 CLAUDE.md 无重复/矛盾；C-DRY。

**F4 | task-package-standards.md:15,20,26,42,50,59 | B | 🟠建议**
问题：全文 6 处【强制】（§1.1/§1.2/§1.3/§1.5/§1.6/§2）零机械检查性标注，违反本仓 CLAUDE.md:37 自设标准（"标注强制的条款应同步评估可机械检查性"）。逐条判定：
| 条款 | 可机械检查 | 接线方式 |
|---|---|---|
| §1.1 反目标在场 / §1.2 双层验收在场 / §1.3 点名受保护面 | ✅ | gauntlet 加任务书形状检查（docs/*-task-brief.md 须含"反目标""机械验收""所有权清单"节块） |
| §1.5 约束分级标注 | 🔶 仅人记 | 无 |
| §1.6 两层判定执行质量 | 🔶 仅人记 | 归 L2 审查维度 |
| §2 L1 watcher | ✅ 已有实物 | tools/dispatch_watch.sh（存在且可执行，实测） |
| §2 L2 reviewer 电池 | ✅ 已有实物 | templates/reviewer-battery.md.template（存在，实测） |
| §2 L3 独立复跑 | 🔶 仅人记 | 主会话工序 |
修改建议：在 §1/§2 各节标题后补 enforcement 后缀，如 "### 1.3 升级触发器【强制｜gate:任务书形状；触发后纪律仅靠人记】"；实物已存在的在条款内点名工具路径（当前 §2 表格已点名，可保）。
依据：B-【强制】条款逐条评估可机械检查性。

**F5 | task-package-standards.md:11-13 | B | 🟠建议**
问题：§1 定义"五要素骨架 + 三处契约式移植"为强制形态，但 `templates/` 全部 5 个模板（task-brief/spec/plan/intent/reviewer-battery）均为设计链形态，任务包无权威模板，只剩手写实例。实证漂移已发生：docs/P4-rome-借鉴B档-task-brief.md 以"# 非目标"（范围排除）顶替 §1.1 强制要素"反目标"（plausible-but-wrong 交付形态）——语义不同、要素实质缺位，且无任何门禁能发现。
修改建议：新增 `templates/task-package.md.template`，骨架六槽位对应 §1.1–§1.6（目标+反目标 / 双层验收 / 升级触发器点名受保护面 / 状态写协议 / 约束 enforcement 分级 / 存量工具盘点清单），与 :9 "两者不混用"相呼应。
依据：B-机械检查性（形状检查需模板锚点）；C-DRY。

**F6 | review-report-standards.md:55 | B | 🟠建议**
问题：正文残留过程占位注释 `<!-- 待 apply 的「证据核实/基线声明/复核表态」类条款落此节 -->`。所列三类条款均已落地正文（复核表态 :29、基线声明 :30、证据核实 :37），占位注释误导读者以为仍有条款未合入；本文件自身 :121 禁止报告残留中间演进叙事，同一纪律应适用于规范文档。
修改建议：删除 :55 整行。
依据：B-与仓自身规范一致；C。

**F7 | review-report-standards.md:30,35 | B | 🟠建议**
问题：同文件内重复条款且术语漂移——:30 与 :35 都规定"指控先对照远端/基线核实再定级"，同引"配置缺失、DDL 重复建表"示例，但 :30 称"**事实类**指控"、:35 称"**现状类**指控"，同一概念两个名字。
修改建议：:30 收敛为只管声明基线（"工作区存在未提交变更时，报告必须先声明基线（HEAD commit + 工作区是否干净）"），删除其后半句核实细则；核实细则统一保留在 :35，术语统一为"现状类指控"。
依据：B-无重复条款；C-术语一致。

**F8 | review-report-standards.md:84 | B | 🟠建议**
问题："分级对齐 guard 家族：🔴 阻断 / 🟠 需处理 / 🟡 建议 / 🟢 通过"名不副实——impact-guard 实际四级为 🔴直接（--strict 阻断）/🟠间接抵达（告警）/🟡Warning/🟢Info（skills/impact-guard/SKILL.md:100-103），是"影响方式"轴；本表是"处置"轴。审阅者按本条读 impact-guard 输出会把 🟠间接抵达 误读为"需处理"。
修改建议：改前 "分级对齐 guard 家族：🔴 阻断 / 🟠 需处理 / 🟡 建议 / 🟢 通过" → 改后 "四级色板沿用 guard 家族（🔴/🟠/🟡/🟢），处置语义为：🔴 阻断 / 🟠 需处理 / 🟡 建议 / 🟢 通过；impact-guard 的直接/间接为影响方式分级，与本表处置轴分开使用"。
依据：B-与各 SKILL.md 无矛盾；C-术语一致。

**F9 | review-report-standards.md:72,75,104 | B | 🟠建议**
问题：3 处【强制】（销项三方对账 :72、五段式 :75、证据边界 :104）既无 gauntlet 接线（tools/gauntlet.sh grep "五段式|证据边界|销项" 零命中）也无"仅靠人记"标注。实际接线现状：人读路径已有 4 个 guard 技能 SKILL.md 回链本规范（api/code-review/contract/ddl-guard，ddl-guard:218-220 为例）；机器路径 .factory/factory_lib.py:622 已实现五段式拒绝回执——即"未接线"的说法不成立，缺的是条款上的标注与 eval 负控制。
修改建议：条款后补标注：:72 "销项三方对账【强制｜仅靠人记：跨仓对账表无法本仓门禁】"；:75/:104 "【强制｜gate 技能步骤 + eval 负控制】"，并在 guard 技能 eval 补"报告缺证据边界段"负控制用例（新增工作项，见上报 E-2 同类）。
依据：B-机械检查性评估。

**F10 | frontend-standards.md:181-185 | C | 🟠建议**
问题：lint/类型门控的示例命令存在假绿路径——`npx vue-tsc --build --force 2>&1 | grep -E "改动文件路径"`：vue-tsc 自身崩溃（exit 2）或命令拼错（127）时输出不含改动文件路径 → grep 空 → 按 :184 注释"输出为空 ⇒ 改动文件零类型错误"误判通过。与本仓 review-report-standards.md:44 自订纪律（零命中驱动的否定性结论须先防假象）同构。
修改建议：改前
```bash
✅ npx vue-tsc --build --force 2>&1 | grep -E "改动文件路径"
   // 输出为空 ⇒ 改动文件零类型错误；非空需对照 main 基线差集判定——
```
改后
```bash
✅ out=$(npx vue-tsc --build --force 2>&1); rc=$?
   # 先确认 rc 非 2/127（vue-tsc 自身未崩、命令存在），再过滤：
   echo "$out" | grep -E "改动文件路径"
   # 输出为空且 rc 健在 ⇒ 改动文件零类型错误；非空对照 main 基线差集判定——
```
依据：B-示例代码须符合本仓自身规范；C。

**F11 | frontend-standards.md:13,30,38,49,72,101,119,139,154,176,190 | B | 🟠建议**
问题：全文 11 处【强制】全部面向外部 Vue3 目标仓（open-platform-admin 等），本仓 gauntlet 结构上无法触达，文档亦未按 CLAUDE.md:37 标注承接方（目标仓 CI vs 仅靠人记），强制效力完全悬空。
修改建议：文档头部加"执行承接"声明，并给可机械项目标仓 CI 片段，例如：
```bash
# :13 mock 门控（目标仓 CI）——硬编码恒开应零命中：
! grep -rn 'enableDev:[[:space:]]*true' build/
# :30 个人覆盖分层（目标仓 CI）——共享 .env 不得置真：
! git grep -in 'VITE_MOCK.*true' -- .env
```
其余（同构 mock :38、宽容解析 :49、路由下发 :72、axios 工厂 :101、merge 落新对象 :119、点击复制 :139、真实锚点 :154、本地冒烟 :190）标注"仅靠目标仓 CR 评审承接"。
依据：B-机械检查性；B-与 CLAUDE.md:37 一致。

**F12 | task-package-standards.md:4 + review-report-standards.md:4 + frontend-standards.md:1-4 | B | 🔵可选**
问题：`inclusion` 字段三态并存——task-package `always`、review-report `manual`、frontend 缺失。全仓核实：SessionStart hook（hooks/load-steering.sh:37-45）只消费 title/scenario，`inclusion` 零代码消费者；CONTRIBUTING.md:146 自认"部分历史文件保留的既有字段，新增文件无需写"。若未来实装，`always` 将使 7.7KB 全文常驻注入，与 scenario 触发式加载设计矛盾。
修改建议：删除 task-package:4 与 review-report:4 两行死字段，统一为 frontend 的无字段形态（仓级共 6 文件携带，另 4 个不在本任务范围，见上报 E-5）。
依据：B-frontmatter inclusion 取值合理。

**F13 | review-report-standards.md:52,59,60,64 + task-package-standards.md:57,100 | C | 🔵可选**
问题：文件内引号体系混用——review-report 以「」为主（24 处）但 :52/:59/:60/:64 用 ASCII 直引号（如 :52 按文档字面"修正"代码）；task-package 反向：ASCII 直引号为主（:18/:24/:34/:40/:52/:54/:71/:78/:87）但 :57/:100 用「」；frontend 纯 ASCII。仓内无引号单一标准。
修改建议：各文件归自身多数派——review-report 四行改「」：`按文档字面"修正"代码` → `按文档字面「修正」代码`；task-package :57/:100 改 `"禁止顺延既有架构"`。仓级统一（「」 vs ASCII）需维护者决策，见上报 E-6。
依据：C-中英文/标点风格一致。

**F14 | review-report-standards.md:27,37,38 | C | 🔵可选**
问题：列表行缺句号收尾（awk 实测 :27/:37/:38），同节其余列表行均有——同文件标点不一致。
修改建议：三行末补"。"，或全文统一"列表行一律句号收尾"。
依据：C-标点风格一致。

**F15 | review-report-standards.md:121-122 vs 124-127 | C | 🔵可选**
问题：禁止事项节标记顺序混用——:121/:122 为 `❌ - 内容`，:124-:127 为 `- ❌ 内容`。
修改建议：统一为 `- ❌ 内容`（:121/:122 去掉行首 ❌、在 - 后加 ❌）。
依据：C-风格一致。

**F16 | review-report-standards.md:44 | C | 🔵可选**
问题："必须以 Read/Glob 直读原文复核"——Read/Glob 为 Claude Code 专属工具名，本仓多平台分发（.opencode/.cursor/.kimi/.grok/.codex 插件目录并存），术语不可移植。
修改建议：改前 "必须以 Read/Glob 直读原文复核" → 改后 "必须以文件直读工具（Read/Glob 或宿主等价能力）原文复核"。
依据：C-术语一致/可移植。

**F17 | review-report-standards.md:9 | C | 🔵可选**
问题："适用于**本仓库**所有审查类输出"指代含混——所列 guard 家族审查的是外部目标仓（DDL/业务接口/分层），CR 评语也发生在目标仓，读者易误解为仅约束对 awesome-rules 自身的审查。
修改建议：改前 "适用于本仓库所有审查类输出" → 改后 "适用于经本规范体系（guard 技能人工判断部分、CR 评审、设计评审）产出的所有审查类输出"。
依据：C-措辞清晰。

**F18 | review-report-standards.md:9-10 | B | 🔵可选**
问题：本条声明适用于 /impact-guard 的人工判断部分，但 skills/impact-guard/ 全目录 grep 零回链本规范（其余 4 个 guard 技能 SKILL.md 均回链，ddl-guard:218-220 为标准写法）——适用声明与技能实际接线不一致。
修改建议：在 skills/impact-guard/SKILL.md 输出步骤补一行，镜像 ddl-guard 写法："按 [`../../steering/review-report-standards.md`](../../../steering/review-report-standards.md) 五段式输出（含证据边界段）"。（修改位置在技能文件，本报告只建议。）
依据：B-与各 SKILL.md 无矛盾/边界清晰。

---

## 统计

| 严重度 | 数量 | 编号 |
|---|---|---|
| 🔴 必改 | 1 | F1 |
| 🟠 建议 | 10 | F2–F11 |
| 🔵 可选 | 7 | F12–F18 |
| 合计 | 18 | |

按类别：A 0（不适用，见声明）｜B 12｜C 6。

## 正面核实（已验证无问题项）

1. 三文件 frontmatter title/scenario 完整且为单行标量（load-steering.sh M1 门禁约束成立）；scenario 均含明确触发词（如 frontend :3 列举五类必读场景）。
2. 引用路径全部存在：templates/task-brief.md.template、templates/reviewer-battery.md.template、tools/dispatch_watch.sh（含可执行位）、docs/design/guard-receipt-spec.md（review-report:12 相对链接可解析）。
3. review-report:88 示例引用 `database-design-specification §六、索引`——该节实存（steering/database-design-specification.md:84 `## 六、索引`）。
4. 文内节引用有效：task-package:36/:83 → §1.6 存在；frontend:91 → §1 存在。
5. task-flow 技能与任务包边界零重叠（grep 任务包/反目标/升级触发 = 0）。
6. 历史计数字（:24 13 failed、:57/:100 7 类/11 位置、frontend:46 8 条 mock 菜单）均为冻结判例数据而非易腐计数，不违"计数让事实自证"条款。
7. review-report 的五段式权威单一源成立：4 个 guard 技能引用而不复述。

## 审查中上报事项

- **E-1 基线漂移**：HEAD=3536e53 ≠ dfe1732（f7ecb07 docs/adr/ADR-017；3536e53 CLAUDE.md +3/-1）。工作树 clean；漂移文件不含三对象，但 CLAUDE.md 比对基准含基线后新增条款（:51-54），本文按 HEAD 执行。
- **E-2 本报告归档冲突**：任务指定落 /tmp/ar-review-2b.md，与被审文件自身条款冲突（review-report:16/22 要求报告与中间产物落目标仓 docs/ 持久归档、不滞留易失目录）。已按任务指令执行，建议主会话事后归档至 docs/audits/。
- **E-3 死引用扩散（F1 同源，超出三对象）**：docs/design/distribution-verification-and-suite-design.md:7/:128 仍显式指向 `.factory/decisions.md`；factory-harness-design.md:118/:367/:379 泛指 decisions.md；audit-d.md:54 为带行号的历史引用（保留原状可接受）。建议随 F1 一并批量修正。
- **E-4 陈旧审查结论**：docs/audits/2026-09-20-repo-compliance/audit-d.md:76 称"三方对账/五段式/证据边界 ❌ 未接线——报告格式条款，天然人工"，而 .factory/factory_lib.py:622 已实现五段式拒绝回执。按 review-report:29 自身要求（旧指控须复核更新状态）应回源更正。
- **E-5 inclusion 死字段为 6 文件共性**：另 4 个（git-conventions/cross-repo-contract-standards/openapi-standards/testing-standards 均在 :4）不在本任务范围，批量清理需维护者决策（删除 vs 在 load-steering.sh 实装语义）。
- **E-6 引号体系仓级分裂**：「」与 ASCII 直引号跨 steering 文件并存，本报告仅修文件内混用；仓级统一需另行决策并写入 CONTRIBUTING。
- **E-7 F9/F11 涉及新门禁工作项**（任务书形状检查、guard eval 负控制、目标仓 CI 片段），属新增工程量，需单独排期而非文档顺手改。
