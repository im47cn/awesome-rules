# awesome-rules 审查报告（ar-review-3）：steering/testing-standards.md

## 基线对账

- `git rev-parse HEAD` = `dfe173295422ddfa02ee81dddc903e081a251b43`，与任务基线 dfe1732 一致；`git status` 工作树 clean。**无漂移、无需披露。**
- 审查对象：`steering/testing-standards.md`（299 行，全文精读）。仓内一切路径只读，未做任何 git 写操作与文件修改；唯一写权限 `/tmp/ar-review-3.md`。

## 范围与标准适用说明

- 标准 A（SKILL.md 专项）不直接适用（目标为 steering 文档）；其精神项已按 B/C 落实：引用路径逐一 `test -e` 核实（见「引用路径核实清单」）；文内 ΣCRAP/方法数等均为**带日期的事故实证记录**而非待维护计数，不计为"易腐计数"发现。
- 标准 B 的「可机械检查性」评估锚定仓内权威原则 `CLAUDE.md:37`：*"标注强制的条款应同步评估可机械检查性：能查出的配 gauntlet 静态门 + 负控制（证明检查器会失败），门禁查不出违规的强制条款只靠人记，效力弱。"*——文末附 12 处【强制】条款机械化状态总表。
- 标准与仓现状冲突项：严重度图例（详见上报事项 #1）。

---

## 发现

### F1
**testing-standards.md:243-247 | B | 🔴必改**

**问题**：「测试密封性（git 环境隔离）【强制】」节未引用已存在的机械化门禁。仓内 `tools/check_git_sealing.py` 已落地（gauntlet 层 `git-sealing`，`tools/gauntlet.sh:430`），其 docstring 自称 *"steering/testing-standards.md §测试密封性是规范事实源；本门把其中靠人记住的三件事机械化（负控制 NC14，tools/test_gauntlet_checks.sh）"*，拦截 R1（conftest 缺 import 期 GIT_* 剥离）/R2（shell 测试未 unset GIT_*）/R3（`GIT_FIXTURE_CASES` 登记表不完备）。但文档该节只引范式测试文件（L246-247），无"机器执行层"行——与两个姊妹节形成不对称：L257（killpg）与 L266（tempdir）均带 `机器执行层：tools/check_xxx.py（gauntlet 层 lint-xxx）…负控制 NCxx` 句式。读者（含 AI）按本文档会误判该强制条款"仅靠人记"。

**修改建议**：在 L247 后追加一条（句式对齐 L257/L266）：

```
- 机器执行层：tools/check_git_sealing.py（gauntlet 层 git-sealing）静态拦截 R1（套件
  conftest 缺 import 期 GIT_* 剥离块）/R2（tracked shell 测试调 git 未顶层 unset
  GIT_*）/R3（scripts/tests/test_hermetic_git.py 的 GIT_FIXTURE_CASES 未覆盖 R1 检出
  套件）；负控制 NC14 见 tools/test_gauntlet_checks.sh
```

**依据**：任务标准 B2（强制条款给出 gauntlet/CI 接入方式）；CLAUDE.md:37。

---

### F2
**testing-standards.md:29-30 | B/C | 🔴必改**

**问题**：「测试范围」开头两条为**同一规则的两份活维护副本**——均为"多处配置写一致性守护测试"，三组例子完全相同（分片 yml / datetime 界限 / DDL 预建表）。已现措辞漂移：L29"任一漂移即 **CI 失败**"+独有的"只护对齐不护过期"警示；L30"任一方漂移即**测试失败**"+独有参考类名 `AccessLogShardingConsistencyTest`。两份副本必然继续分叉。

**修改建议**：合并为一条（吸收双方独有信息）：

改前（L29-L30 两条，原文）：
```
- 多份工件必须同步的配置（如分片 yml 区间端点、datetime 界限、DDL 预建表集合）应纳入测试范围：编写一致性守护测试解析各端并断言对齐，任一漂移即 CI 失败，把人工多处同步的漂移风险固化为防回归护栏；注意此类守护只护「对齐」不护「过期」，时间上界仍需另行提前扩界。
- 配置一致性守护测试：当同一约束散落在多处配置（如分片区间 yml、datetime 上下界限、DDL 预建表清单）时，应编写守护测试解析各方配置并断言一致，任一方漂移即测试失败，把配置漂移类风险固化为防回归护栏（参考 AccessLogShardingConsistencyTest 三方对齐模式）。
```
改后（一条）：
```
- 多份工件必须同步的配置（分片 yml 区间端点、datetime 上下界限、DDL 预建表清单）应纳入测试范围：编写一致性守护测试解析各方配置并断言对齐（参考 AccessLogShardingConsistencyTest 三方对齐模式），任一方漂移即测试失败，把人工多处同步的漂移风险固化为防回归护栏；注意此类守护只护「对齐」不护「过期」，时间上界仍需另行提前扩界。
```

**依据**：任务标准 B3（重复条款收敛到单一权威源）、C1（DRY）。

---

### F3
**testing-standards.md:285-288 | C | 🔴必改**

**问题**：「禁止事项」节列表格式损坏，四种并存形态：
- L285 `- 禁止用「现状钉住」…`（无 ❌ 的普通 bullet）
- L287 `❌ ❌ - 禁止在启用 set -o pipefail…`（**双 ❌ 编辑事故**；且以 ❌ 开头、`-` 不在行首，markdown 渲染为**段落**而非列表项）
- L288 `❌ - 断言 checkout 目录名…`（同样非列表项）
- L290-299 `- ❌ …`（标准形态）

两条最有分量的规则（SIGPIPE 管道规则、checkout 目录名规则）因此脱出列表结构，注入 AI 上下文时按列表解析会丢失层级。

**修改建议**：统一为 `- ❌ …` 形态：

改前：
```
❌ ❌ - 禁止在启用 `set -o pipefail` 的脚本中把 `grep -m<N>`、`head`、`true` 等提前关读端的命令放在管道非末位——…
❌ - 断言 checkout 目录名等环境特定值（如 `root.name == "awesome-rules"`）：…
```
改后（正文不变，仅改行首；L287 顺带补机器执行层引用，见 F7）：
```
- ❌ 在启用 `set -o pipefail` 的脚本中把 `grep -m<N>`、`head`、`true` 等提前关读端的命令放在管道非末位——…（正文不变）；机器执行层：tools/check_pipe_early_exit.py（gauntlet 层 lint-pipe-early-exit），负控制 NC7 见 tools/test_gauntlet_checks.sh
- ❌ 断言 checkout 目录名等环境特定值（如 `root.name == "awesome-rules"`）：…（正文不变）
```

**依据**：任务标准 C3（标点/格式一致性）；A 精神项（引用资产逐一核实）。

---

### F4
**testing-standards.md:214 与 282 | B/C | 🟠建议**

**问题**：完全重复句两处维护：L214 *"不为「全灭」数字编写断言非行为的测试"*（变异测试纪律节）vs L282 *"禁止为"全灭"数字编写断言非行为的测试"*（等价项处理【推荐】节）。同一句还是引号风格分裂样本（「全灭」 vs "全灭"，见 F10）。

**修改建议**：L282 删后半句、改指针（权威源保留在 L214 所在节）：

改前：`- 被判定等价的项（等价变异、行为不可区分的重构）须附论证与差分测试证据后豁免；禁止为"全灭"数字编写断言非行为的测试`
改后：`- 被判定等价的项（等价变异、行为不可区分的重构）须附论证与差分测试证据后豁免（「全灭」数字红线见「变异测试纪律」节，单一权威源，不在此复述）`

**依据**：任务标准 B3、C1。

---

### F5
**testing-standards.md:239 与 298 | B/C | 🟠建议**

**问题**：负控制原则两处维护：L239 *"检查器上线前必须喂**已知坏输入**并断言其退出码非零；仅验证"好输入能通过"不构成证明"* vs L298 *"❌ 检查器只验证"能通过"，不验证"会失败"（缺负控制）"*。L298 是 L239 的弱化复述，属重复条款。

**修改建议**：删除 L298（L236-241 节已含更细的强制条款），或改为纯索引条目：`- ❌ 负控制缺位（权威条款与四条细则见「负控制【强制】」节）`。

**依据**：任务标准 B3、C1。

---

### F6
**testing-standards.md:237 与 285 | B/C | 🟠建议**

**问题**：红测验收要求两处表述：L237（负控制【强制】首条：先在未修复基线跑红、再修复后跑绿的**验证程序**）vs L285 尾部 *"缺陷修复必须交付断言期望行为的红测（修复前红、修复后转绿）"*（**要求本身**）。互补但重叠，且 L285 另有"分层标注"细则、L237 无——分叉已现。

**修改建议**：L285 保留其独有内容（现状钉住的零判别力判定、分层标注），程序性细节指向权威节：

改前（L285 尾部）：`…缺陷修复必须交付断言期望行为的红测（修复前红、修复后转绿）；钉住当前正确行为的回归保护用例允许保留…`
改后：`…缺陷修复必须交付断言期望行为的红测，先红后绿的验证程序见「负控制【强制】」；钉住当前正确行为的回归保护用例允许保留…`

**依据**：任务标准 B3、C1。

---

### F7
**testing-standards.md:287（关联 273-278）| B | 🟠建议**

**问题**：管道提前关读端/SIGPIPE 规则（L287，自称"本仓三犯"）与「退出码语义【强制】」的管道截断条款（L274）均未引用已存在的机械层：`tools/check_pipe_early_exit.py` + gauntlet 层 `lint-pipe-early-exit`（`tools/gauntlet.sh:392`）+ 负控制 NC7 系列（`tools/test_gauntlet_checks.sh:167-206`）。规则已机械化而文档不告知，读者会手工执行已由门禁覆盖的检查。

**修改建议**：L287 行尾追加引用（文本见 F3 改后）；L274 行尾追加：`（管道提前关读端形态已机械化：gauntlet 层 lint-pipe-early-exit，负控制 NC7）`。

**依据**：任务标准 B2；CLAUDE.md:37。

---

### F8
**testing-standards.md:112-114 | B | 🟠建议**

**问题**：「质量门禁【强制】」要求落地 **CRAP ≥ 30 方法计数 = 0** 第二道门禁，但 `grep -rli crap tools/` 为空——**全仓（含分发链 tools/git/）零实现**。该门禁完全可机械查（JaCoCo XML 方法级 COMPLEXITY/INSTRUCTION，口径已在 L74/L104 写死），且分发脚本 `tools/git/lefthook/coverage.sh` full 模式已在解析 JaCoCo XML（行/分支计数、台账扣除），是最小增量落地点。当前状态下【强制】实为"无载体的期望"。

**修改建议**（二选一）：
- (a) **落地实现**：在 `tools/git/lefthook/coverage.sh` full 模式解析 JaCoCo XML 处扩展方法级聚合——`comp = ΣCOMPLEXITY(missed+covered)`、`cov = INSTRUCTION`（LINE 兜底）代入 L74 公式，CRAP ≥ 30 计数 > 0 即 fail；配负控制登记入 `tools/test_gauntlet_checks.sh` NC 序列（夹具：CC5/cov0% 方法断言 rc≠0；CC5/cov100% 方法断言 rc=0）。
- (b) **显式改标注**：L114 括注改为 *"本规范仓库与分发链均不承载该门禁实现；落点=消费仓 pre-push/CI 自建（口径见「度量纪律」）"*，避免强制条款被读作已有门禁。

**依据**：任务标准 B2（能机械查的给出接入 gauntlet/CI 的具体方式）。

---

### F9
**testing-standards.md:140 / 184 / 236 / 268 | B | 🟠建议**

**问题**：四处【强制】条款**无法静态机械检查**，但未显式标注"仅靠人记"，与 CLAUDE.md:37"门禁查不出违规的强制条款只靠人记，效力弱"的仓内原则不符——不标注会高估强制效力：
- L140 接口层 fixture 禁 null 填充（注解敏感字段识别无静态检查）
- L184 工具链假绿形态（诊断启发式，逐条判别信号实为人工检查清单）
- L236 负控制（红测"先红"端验证靠人工执行；"喂坏输入断言 rc≠0"可在验收时机械执行）
- L268 Tripwire（前提后验的存在性无法静态证明）

**修改建议**：行尾显式标注，例：
- L140 → `…纯单元测试直接 new 序列化对象的可豁免（仅靠人记：注解敏感字段无静态门禁，CR 把关）`
- L186 原则行 → `…每条附判别信号与验收口径（仅靠人记：判别信号即人工检查清单）`
- L237 → `…不能作为修复拦截力证据（红端验证仅靠人记；喂坏输入断言 rc≠0 属可机械执行的验收步骤）`
- L270 → `…不会以红色形式暴露（仅靠人记）`

**依据**：任务标准 B2（查不出的显式标注"仅靠人记"）；CLAUDE.md:37。

---

### F10
**testing-standards.md:39,51,165,239,240,241,254,270,276,282,298 | C | 🟠建议**

**问题**：引号风格文内混用：中文散文直引号 "…" 11 行 vs 「」30 处。同词对照最直观：L282 `"全灭"` vs L214 `「全灭」`。仓无声明规范（CONTRIBUTING.md/README.md 无引号条目），但单一文件内部应一致；本文多数派为「」。

**修改建议**：散文层直引号统一改「」（排除 code span 与英文报错原话：L191 `"No code coverage driver available"` 保留、L201/232/265/288 为代码不算）。逐行清单即上述 11 行。例：
- L39 改前 `排除是"让度量对准真实风险"` → 改后 `排除是「让度量对准真实风险」`
- L270 改前 `永远是"虚假通过"` → 改后 `永远是「虚假通过」`

**依据**：任务标准 C3（中英文/标点风格一致）。

---

### F11
**testing-standards.md:70 | C | 🔵可选**

**问题**：CRAP 缩写展开与所引 FAQ 不符。所引 wayback 快照页自问自答：*"didn't CRAP used to stand for Change Risk Analysis and Prediction? — Yes it did, and **yes we did [change it]**"*，官方后更名 **Change Risk Anti-Patterns**；本文却以旧展开释义并引用该页为源。（外链本日实测可达；公式 `comp²×(1−cov)³+comp` 与阈值 30 与 L74/L76 一致。）

**修改建议**：改前 `CRAP（Change Risk Analysis and Prediction，[crap4j FAQ](…)）` → 改后 `CRAP（[crap4j FAQ](…)；官方后将缩写更名释义为 Change Risk Anti-Patterns，本文沿用经典口径）`。

**依据**：任务标准 C（术语一致性/事实准确）。

---

### F12
**testing-standards.md:31 | C | 🔵可选**

**问题**：第三负测场景"全部一致但未过门禁"语义不明——"未过门禁"何指（守卫测试未纳入 CI？还是笔误？）。若意在正控对照应为"全部一致且门禁绿"。

**修改建议**：需作者澄清原意后改写。若为正控：改前 `负测试三场景（新值只落一侧/单侧丢值/全部一致但未过门禁）应全部命中预期签名` → 改后 `负测试三场景（新值只落一侧/单侧丢值/全部一致且门禁绿的正控）应全部命中预期签名`；若另有所指，补一句定义。

**依据**：任务标准 C（术语一致、表述无歧义）。

---

### F13
**testing-standards.md:181（对照 21-23）| B | 🔵可选**

**问题**：L181 在已声明"覆盖率门禁与「覆盖率阈值」同口径"之后仍复述全部阈值数值（全量 ≥98%、增量 java ≥98%/非 Java ≥90%、非 Java 核心 ≥98%），与 L21-23 构成双份维护（当前一致，漂移风险）。分发脚本 `tools/git/lefthook/coverage.sh` 头注已反向锚定（*"红线…与 steering/testing-standards.md「覆盖率阈值」同口径"*，L5-7），单向引用链已成立，文档侧可收口。

**修改建议**：改后：`- 覆盖率门禁与「覆盖率阈值」同口径（数值以该节为单一权威源，此处不复述）：本地 pre-push/full 与 CI 统一经 tools/git/lefthook/coverage.sh 落地；非 Java 核心业务 ≥ 红线由 CR 把关`

**依据**：任务标准 B3（收敛到单一权威源）、C1。

---

### F14
**testing-standards.md:4 | B | 🔵可选**

**问题**：`inclusion: always` 为遗留字段：CONTRIBUTING.md:146 *"部分历史文件保留的既有字段，新增文件无需写"*；`hooks/load-steering.sh` 不消费该字段（新文件如 frontend-standards.md 均已省略）。无害，与"历史文件保留"政策相符。

**修改建议**：无需动作（信息性记录）；若仓面统一清理遗留字段，随政策批量处理，不单独改本文件。

**依据**：任务标准 B1（inclusion 取值合理性——评估结论：字段已无功能语义，取值 moot）。

---

### F15
**testing-standards.md:3 | B | 🔵可选**

**问题**：`scenario: 编写/审查测试代码` 过简（6 字）。scenario 是 SessionStart hook 路由的**唯一** frontmatter 信号（title 之外），本文件覆盖面（Java JaCoCo/CRAP、Mockito、pytest、vitest/Playwright、变异测试、门禁脚本反作弊、gauntlet 层）远超 6 字能触发的范围；仓内 house style（frontend-standards、api-contract-freeze-standards）均为含触发词的长场景+「必读」。

**修改建议**：改后：`scenario: 编写或审查测试代码、搭建/评审覆盖率与 CRAP 与变异测试门禁、开发自建检查脚本与负控制时必读；涉及 JaCoCo/diff-cover、Mockito、pytest、vitest/Playwright、gauntlet lint-* 层`

**依据**：任务标准 B1（frontmatter 完整性与 hook 扫描依赖）；A 精神项（description/scenario 含明确触发词）。

---

### F16
**testing-standards.md:60 | C | 🔵可选**

**问题**：「决策顺序」第 4 条为约 230 字单 bullet，混合四层语义（台账格式/预算 env/生效规则 fail-closed/CR 背书），且 `.lefthook/coverage-exemptions.md`、`.lefthook/coverage-budget.env` 为**消费仓运行时路径**（本仓不存在；由 `tools/git/lefthook/coverage.sh:205-228` 从 `$d/.lefthook/` 读取实现）却未行内注明环境相对性——审阅者易误判为失效引用。

**修改建议**：拆子条目并注明路径语义：

```
4. 结构性不可达分支（逐行推理有调用链证据，如前置校验保证非空、Servlet 规范恒非
   null、枚举穷举）？→ 豁免预算台账（`.lefthook/*` 为消费仓运行时路径，本仓分发
   实现见 tools/git/lefthook/coverage.sh）：
   - 台账：.lefthook/coverage-exemptions.md 逐项记录「类:行 + 不可达理由 +
     falsifier（何种新调用方/输入会推翻）」
   - 预算：.lefthook/coverage-budget.env 声明预算数（棘轮上限非目标）
   - 生效规则：coverage.sh full 模式生效预算 = min(预算, 台账 LEDGER_TOTAL 申报
     行，与逐项合计一致)；预算 > 0 而无台账/申报行直接拒绝（fail-closed）
   - 每项须 CR 背书
```

**依据**：任务标准 C2（KISS）、B4（引用目标可核实——注明环境相对性即消除歧义）。

---

## 【强制】条款机械化状态总表（12 处，B2 核心交付）

| 行号 | 条款 | 机械化状态 |
| --- | --- | --- |
| L21 | JaCoCo 全量 ≥98% 覆盖率 | ✅ 已落地：`tools/git/lefthook/coverage.sh` full 模式（头注反向锚定本节），L60 已引用 |
| L87 | 四形态决策规则 | ⚙️ 半：读数依赖 CRAP 计算（实现缺失见 L114 行）；处置动作靠人 |
| L101 | 度量纪律 | ⚙️ 半：JaCoCo XML 口径可机械解析；skip 清单门禁/失败测试定性靠人 |
| L112-116 | 质量门禁（CRAP 计数=0） | ❌ 全仓零实现 → **F8** |
| L140 | 接口层 fixture 禁 null | 🙅 仅靠人记，未标注 → **F9** |
| L184 | 工具链假绿形态 | 🙅 仅靠人记，未标注 → **F9** |
| L236-241 | 负控制 | 🙅 红端验证靠人，未标注 → **F9**（坏输入断 rc≠0 可验收机械化） |
| L243-247 | 测试密封性 | ✅ 已落地（check_git_sealing.py/git-sealing/NC14）**未引用** → **F1** |
| L249-257 | 进程组信号 | ✅ 已落地已引用（lint-killpg-strict/NC8）——本文标杆写法 |
| L259-266 | tempdir 隔离 | ✅ 已落地已引用（lint-tempdir-isolation/NC17）——本文标杆写法 |
| L268-271 | Tripwire | 🙅 仅靠人记，未标注 → **F9** |
| L273-278 | 退出码语义 | ⚙️ 半：管道截断形态已落地（lint-pipe-early-exit/NC7）未引用 → **F7**；rc 分类语义靠人 |

## 引用路径核实清单（B4，逐一 `test -e` /符号 grep/外链 read）

| 引用（行号） | 目标 | 结果 |
| --- | --- | --- |
| L60 | `scripts/tests/test_hermetic_git.py`（另见 L246） | ✅ 存在 |
| L60 | `.lefthook/coverage-exemptions.md` / `.lefthook/coverage-budget.env` | ◐ 消费仓运行时路径，非本仓链接（coverage.sh:205-228 实现，见 F16） |
| L195 | `ADR-016` | ✅ `docs/adr/ADR-016-parallel-test-gate.md` 存在 |
| L247 | `scripts/run_tests.sh` | ✅ 存在 |
| L256 | `.factory/tests/test_mutations_run.py::_assert_group_dead` | ✅ 文件与符号均在（符号在 :99） |
| L257 | `tools/check_killpg_strict.py`、`tools/test_gauntlet_checks.sh`（NC8） | ✅ 存在；NC8/NC8b/NC8c 在册 |
| L264 | `.factory/tests/conftest.py::private_tmp` | ✅ 文件与符号均在（符号在 :22） |
| L266 | `tools/check_tempdir_usage.py`、NC17/NC17b/NC17c | ✅ 存在；NC17 系列（含 17b/17c…17g）在册 |
| L70 | 外链 crap4j FAQ wayback 快照 | ✅ 本日实测可达，公式/阈值与正文一致（缩写差异见 F11） |

**失效引用：0 处。**

## 统计

| 严重度 | 数量 | 编号 |
| --- | --- | --- |
| 🔴 必改 | 3 | F1, F2, F3 |
| 🟠 建议 | 7 | F4, F5, F6, F7, F8, F9, F10 |
| 🔵 可选 | 6 | F11, F12, F13, F14, F15, F16 |
| 合计 | 16 | — |

## 审查中上报事项

1. **严重度图例偏差**：任务口径 🔴必改/🟠建议/🔵可选；仓权威图例为 `steering/review-report-standards.md:84` 的 🔴阻断/🟠需处理/🟡建议/🟢通过（🔵 不在仓图例中）。本报告按任务口径执行并在此披露。
2. **`.lefthook/*` 路径歧义已消解**：`.lefthook/coverage-exemptions.md`、`.lefthook/coverage-budget.env` 本仓不存在，但非失效引用——`tools/git/lefthook/coverage.sh` 从消费仓 `$d/.lefthook/` 读取并实现台账/预算/fail-closed 语义（L205-228 核实）；改进建议归入 F16。
3. **外链核实**：L70 wayback 快照本日（2026-09-24）实测可达；正文 CRAP 公式、阈值 30、全部实证数字复算自洽（5²+5=30、12²×0.125+12=30、0.51³≈0.13、CC18/cov89.2%→CRAP 18.4）；缩写更名差异见 F11。
4. **边界确认（无发现）**：仓根 CLAUDE.md 无测试规则重复（仅 L37 可机械检查性原则，方向一致）；`steering/gtsp/09-cr-checklist.md` 零测试/覆盖率条款；13 个 skills/*/SKILL.md 无测试术语交叠；`steering/frontend-standards.md` 的 mock 条款属开发态 mock 服务（VITE_MOCK 门控），与本文件测试态 Mock 边界（Mockito/vitest）权责清晰——仅 frontend:38「mock 数据与真实后端契约同构」与本文 L125「Mock 响应形状对齐消费端」理念相邻，建议未来互加一行交叉引用（未列为发现）。
5. **并行会话**：同一基线 dfe1732 上另有会话只读审查其他 steering 文档（产出 /tmp/ar-review-1.md、/tmp/ar-review-2.md），与本报告范围（仅 testing-standards.md）无交集、无文件冲突。
6. **正面确认**：frontmatter title「测试规范」与 H1 一致（无姊妹文档的 title≠H1 问题）；全部 12 处【强制】中 3 处已"落地+引用"（L21/L257/L266）构成文内标杆句式，F1/F7 即按其补齐。
