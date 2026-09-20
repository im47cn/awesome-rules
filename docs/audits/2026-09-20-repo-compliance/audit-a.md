# 维度 A：规范自洽性审查（audit-a）

基线：`/tmp/ar-audit` @ `135b82913f7bc8936327df16fa1b1ec7398bb640`（= origin/main），工作树 clean，全程只读（未修改仓内任何文件、无任何 git 写操作）。

级别定义：🔴 行为矛盾/规范失效｜🟠 条款冲突/强制文本重复/核心引用断链｜🟡 计数漂移/清单缺项/弱指针/过时陈述。
结论：🔴 0 条；🟠 8 条（R01–R08）；🟡 10 条（R09–R18）；待验证 3 条。

## 发现

### R01 | steering/review-report-standards.md:18-25≡43-50、30/31/33≡56/58/59 | 🟠

**问题描述**：「核心原则」节系统性重复——9 个条款各有两份逐字拷贝，另有同一要求（更新报告须复核旧指控）的三种同义措辞并存。任何单侧修订即产生同文件内条款分歧。该文件自身 :136 明令「报告更新后残留……演进叙事……全文以最终态自洽」，本缺陷正是其自设纪律所禁止的编辑残留。scout 初判 🔴，终裁降 🟠：当前两份文本语义仍一致，属漂移风险而非已成立的行为矛盾。

**证据摘录**：
- :18「- 机器生成的回执/报告正文不得内嵌状态机权威标记（如 `[factory:rejected]`）：机器状态由标签承载……」（:43 同文）
- :28「- 迭代更新既有审查报告时，旧结论必须逐项按当前实际状态复核：用 git show/log 验证……」；:30「- 更新既有审查报告时，须逐项复核旧指控并更新状态（已修复 / 仍在 / 误报更正）……」；:33「- 更新既有审查报告时，须逐项复核旧指控的现状并亲自核实原始证据……」——三款同旨异文
- :136「❌ - 报告更新后残留已被推翻的旧结论或「v1/v2 演进」叙事……全文以最终态自洽」

**复现命令**：
```bash
cd /tmp/ar-audit
diff <(sed -n '18,25p' steering/review-report-standards.md) <(sed -n '43,50p' steering/review-report-standards.md)   # 输出为空（8 行含空行整段一致）
diff <(sed -n '30p;31p;33p' steering/review-report-standards.md) <(sed -n '56p;58p;59p' steering/review-report-standards.md)   # 输出为空
grep -n '更新既有审查报告时\|迭代更新既有审查报告时' steering/review-report-standards.md   # 28/30/33/56/59 五处
```

**建议**：43-50 与 18-25 二留一；28/30/33 三变体合并为单条含「git show/log 核验 + 状态更新 + 误报显式更正」完整语义的条款；按其 :136 自律清除编辑残留。可加 CI「条款去重」检查（非空行归一化后找重复行）防复发。

### R02 | CLAUDE.md:36==39、38==41 | 🟠

**问题描述**：「使用原则」两对条款整段逐字重复，与 R01 同族（规范文本双事实源，单侧修订即自相矛盾）。

**证据摘录**：
- :36==:39「- 标注强制的条款应同步评估可机械检查性：能查出的配 gauntlet 静态门 + 负控制（证明检查器会失败），门禁查不出违规的强制条款只靠人记，效力弱。」
- :38==:41「- 工厂链运行期间（`.factory/fix-issue.sh` 进程存活时）不得修改 `.factory/` 下任何文件：bash 按字节偏移增量解析脚本……（2026-08 issue #2 实证……）」

**复现命令**：
```bash
cd /tmp/ar-audit
diff <(sed -n '36p' CLAUDE.md) <(sed -n '39p' CLAUDE.md)   # 无输出
diff <(sed -n '38p' CLAUDE.md) <(sed -n '41p' CLAUDE.md)   # 无输出
```

**建议**：各保留一份。注意 :36 元规则同时被 audit-d 报告（D-02）引用，去重后行号移位需同步。

### R03 | steering/openapi-standards.md:154==155 | 🟠

**问题描述**：幂等键条款整行逐字重复。

**证据摘录**：:154==:155「- 幂等键口径因事件/接口而异时，应支持按事件配置幂等键表达式，并定义默认兜底键（未配置或表达式解析失败时按默认键计算）；双轨并行或灰度切换期间，新旧链路须产出一致的幂等键。」

**复现命令**：
```bash
cd /tmp/ar-audit && diff <(sed -n '154p' steering/openapi-standards.md) <(sed -n '155p' steering/openapi-standards.md)   # 无输出
```

**建议**：删除一行。

### R04 | steering/gtsp/01-project-structure.md:16==17 | 🟠

**问题描述**：「从零推导架构 + ADR 两类理由」条款整行逐字重复；该条与 task-package-standards §1.6 架构形状级条款同旨（见 R06），双事实源会放大两规范间的措辞漂移。

**证据摘录**：:16==:17「- 设计新系统的技术方案时，应以目标需求为第一性输入从零推导架构；对存量系统的代码梳理仅作为现状证据与迁移约束输入，不得以「演进统一、不另起炉灶」为由让新架构沿用存量实现的形态与缺陷。ADR 决策记录中须区分「目标驱动的选择」与「兼容存量的妥协」两类理由。」

**复现命令**：
```bash
cd /tmp/ar-audit && diff <(sed -n '16p' steering/gtsp/01-project-structure.md) <(sed -n '17p' steering/gtsp/01-project-structure.md)   # 无输出
```

**建议**：删除一行；去重时与 §1.6 对应条款核对表述一致性。

### R05 | steering/git-conventions.md:96==103、97==105、99==106 | 🟠

**问题描述**：「## 提交要求」节两块成段重复：三条纪律各有两份逐字拷贝（96-99 块与 103-106 块）。

**证据摘录**：
- :96==:103「- 合并/rebase 冲突经工具自动解后，提交前必须核验冲突文件完整性：同一锚点两侧各自新增的测试类/函数应保两侧（union）……」
- :97==:105「- 重写/清洗提交历史前必须验证两个不变量：被剔除段的净效果为零（`git diff 段首 段尾` 为空）……」
- :99==:106「- main 与工作分支（如 factory/base）并存时，推送前先比对两分支指向是否同步……」

**复现命令**：
```bash
cd /tmp/ar-audit && diff <(sed -n '96p;97p;99p' steering/git-conventions.md) <(sed -n '103p;105p;106p' steering/git-conventions.md)   # 无输出
```

**建议**：删除 103-106 重复块（:102「暂存区核对」条款仅存一份，保留）；与本报告 R15（同文件两处过时注释）合并为一次清理提交。

### R06 | steering/task-package-standards.md:36 vs :54 vs templates/task-brief.md.template:18 | 🟠

**问题描述**：「禁止顺延」同术语三种 scope 并存：§1.3:36 位于「升级触发器」节触发后动作，无任何层级限定；§1.6:54 声称「1.3 节"禁止顺延"仅指本层」——该限定是只存在于 §1.6 一侧的回溯性再解释，§1.3 原文不含此语义；模板 :18 又是第三口径（spec 条款保真语境）。三处绑定不同对象，调和依赖读者恰好读到 §1.6 的再解释。

**证据摘录**：
- :36「- 触发后动作：停止写盘、上报事实、等待重新协商；禁止即兴绕过，也禁止以仓库既有实现顺延任务书。」
- :54 末句「……1.3 节"禁止顺延"仅指本层。」（「本层」=架构形状级）
- 模板 :18「1. 【禁止顺延】禁止以既有架构/所有权/历史原因为由顺延或降级 spec 条款；发现 spec 与现状冲突，必须上报（hub send 主 agent），不得自行包装成"设计取舍"。违反即失败。」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -n '顺延' steering/task-package-standards.md templates/task-brief.md.template
```

**建议**：§1.3 就地补层级限定（如「禁止以仓库既有架构形状顺延任务书（层级判定见 §1.6）」），把再解释变成前向声明；模板口径独立成立，建议换措辞（如「禁止降级 spec 条款」）避免同名三义。

### R07 | steering/gtsp/08-comments-deprecated.md:12,20 vs steering/gtsp/09-cr-checklist.md:68,69 | 🟠

**问题描述**：同一要求在维度文件为无条件「必须」、在 CR 合并门禁清单降为【推荐】，且字段注释条款范围不一致（09 丢失 Entity）。gtsp/README:12 声明 01-08 不逐条分级、09 为门禁清单，但 08 以自然语言「必须」给出与 09【推荐】不同的约束力读数——按 frontmatter scenario 只加载 08 的执行方会当作强制条款对待，两文约束力读数冲突。

**证据摘录**：
- 08:12「所有 Java 类必须含 Javadoc，包含 `@author` 和 `@date`（格式 `yyyy-MM-dd`）。」 vs 09:68「- [ ]【推荐】类注释含 `@author` 和 `@date`（格式 yyyy-MM-dd）」
- 08:20「- PO/Entity/DTO 所有字段必须有 Javadoc」 vs 09:69「- [ ]【推荐】PO/DTO 字段有 Javadoc 注释，枚举字段说明码值映射」

**复现命令**：
```bash
cd /tmp/ar-audit && sed -n '12p;20p' steering/gtsp/08-comments-deprecated.md && sed -n '68,69p' steering/gtsp/09-cr-checklist.md
```

**建议**：统一约束力口径——08 改「应含（CR 门禁为【推荐】，未遵守须说明理由）」或 09 升【强制】，二选一；09:69 补回 Entity 或 08:20 去掉 Entity，对齐范围。

### R08 | tools/git/commit-template.txt:21 vs steering/git-conventions.md:110 vs tools/git/commitlint.config.cjs:25 | 🟠

**问题描述**：commit 主题行长度三方分叉：规范与 commitlint（含根配置）均为 100（2026-09-16 按 6 仓拦截率校准），分发模板仍写 50。模板经 install.sh 装入 `~/.gitmessage` 成为全局机器级提示——51–100 字符的主题通过门禁却违背模板提示，事前提示与事后拦截两个事实源分叉。

**证据摘录**：
- template:21「# subject 是 commit 目的的简短描述，不超过50个字符。」
- conventions:110「- 使用中文，主题行 ≤100 字符（header ≤150；body 单行 ≤300；阈值按 6 仓提交历史实测拦截率 ≤5% 校准，2026-09-16）」
- cjs:25 `'subject-max-length': [2, 'always', 100],`
- install.sh:119「# commit 模板 → 用户主目录 ~/.gitmessage（全局，所有仓库/IDEA 一次识别）」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -n '不超过50个字符' tools/git/commit-template.txt && sed -n '110p' steering/git-conventions.md && grep -n 'subject-max-length' tools/git/commitlint.config.cjs && grep -n 'gitmessage' tools/git/install.sh | head -3
```

**建议**：模板改「不超过100个字符」，与 R18（同文件计数错误）同一次修复。此条与 audit-b/audit-c 视野交叉，归属由协调方裁定（见上报事项）。

### R09 | README.md:62 vs steering/database-design-specification.md:8 | 🟡

**问题描述**：README 描述数据库规范「按【强制】【推荐】分级」（两级），该规范自述三级（含【参考】，全文 2 处实际使用）。同为 README:68 的前端规范两级描述经核实属实（12 强制/10 推荐/0 参考），故本条为孤立事实错误。

**证据摘录**：
- README:62「| [数据库设计规范](steering/database-design-specification.md) | MySQL DDL/DML 设计标准：表、字段、索引、注释、SQL 语句，按【强制】【推荐】分级 |」
- db:8「规则按约束力分为【强制】（必须遵守）、【推荐】（尽可能遵守）与【参考】（提示性说明，如 `''` 与 `NULL` 的语义差异）。」

**复现命令**：
```bash
cd /tmp/ar-audit && sed -n '62p' README.md && sed -n '8p' steering/database-design-specification.md && grep -c '【参考】' steering/database-design-specification.md   # → 2
```

**建议**：README:62 补「【参考】」或改写为「按约束力三级分级」。

### R10 | README.md:73 | 🟡

**问题描述**：「按维度拆分为 10 个文件」计数错误：gtsp 维度文件实为 9——括号内 10 个维度名中「项目结构、分层架构」同属 01-project-structure.md 一个文件；目录内第 10 个文件是总入口 README（gtsp/README 索引表 9 行）。与 CLAUDE.md:32「文档不写易腐数字……改写为可执行命令让事实自证」元规则精神相悖。

**证据摘录**：README:73「Java/Spring Cloud 微服务（`gtsp-*`/`fss-*`）编码规范，按维度拆分为 10 个文件（项目结构、分层架构、命名、Feign、MyBatis、日志、异常、配置、注释、CR 清单）。总入口：[steering/gtsp/README.md](steering/gtsp/README.md)。」

**复现命令**：
```bash
cd /tmp/ar-audit && sed -n '73p' README.md && ls steering/gtsp/*.md | wc -l   # → 10（含 README，维度文件 9）
grep -c '0[0-9]-' steering/gtsp/README.md   # → 9（索引表行数）
```

**建议**：改「拆分为 9 个维度文件（结构/分层同卷）」或删计数只留维度列举。

### R11 | CLAUDE.md:13-19 | 🟡

**问题描述**：「审查技能（触发式）」清单缺 `/contract-guard`：README:90、hooks/load-steering.sh:89 以及 review-report-standards.md:9（适用范围段）均含该技能，CLAUDE.md 是唯一漏项的清单（仅列 ddl/api/arch/impact 四 guard + doc-gen）。

**证据摘录**：CLAUDE.md:13-19 清单止于「- `/impact-guard` — …」「- `doc-gen` — …」；README:90「| [contract-guard](skills/contract-guard/SKILL.md) | 跨仓契约兼容性设计与审查（japicmp + 下游编译门禁，配 steering 跨仓契约规范） |」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -c 'contract-guard' CLAUDE.md hooks/load-steering.sh   # → CLAUDE.md 0；load-steering.sh 1
grep -n 'contract-guard' README.md steering/review-report-standards.md
```

**建议**：清单补「- `/contract-guard` — 跨仓契约兼容性设计与审查」一行。

### R12 | steering/api-contract-freeze-standards.md:41 | 🟡

**问题描述**：冻结示例的信封 `{ code, message, data }` 在仓内无任何规范锚点：openapi 统一响应体为 code/message/timestamp/traceId/model（失败加 details）；gtsp 内部为 ResultMode/ResponseMessage（06:14、09:76-77）；frontend-standards 未定义信封（grep 0 命中）。示例亦未声明适用响应面——按本规范 §1「响应信封」逐字段冻结要求照抄该示例，会产出与全仓两套响应规范均不符的冻结契约。是否刻意描述 open-platform-admin 后端真实信封（仓外事实，只读无法核证）留人工裁定，故列 🟡 而非升级。

**证据摘录**：
- :41「✅   响应信封 { code, message, data }」
- openapi:103-110 字段表「| code |…| message |…| details |…| timestamp |…| traceId |…| model | 业务数据（失败时无此字段） |」

**复现命令**：
```bash
cd /tmp/ar-audit && sed -n '39,42p' steering/api-contract-freeze-standards.md && sed -n '103,110p' steering/openapi-standards.md && grep -n '信封' steering/frontend-standards.md   # → 0
```

**建议**：示例旁注明「信封以该端点后端实际契约为准，此处仅占位示意」，或改用与某套仓内信封一致的字段结构。

### R13 | README.md:7-51（项目结构树） | 🟡

**问题描述**：结构树与实际仓库严重不符：顶层目录 tools/（40 文件）、templates/（5）、.factory/（70）、.github/（7）全缺；scripts/ 27 个文件仅列 2 个；根文件 16 个仅列 CONTRIBUTING.md 与 README.md（缺 AGENTS.md、CHANGELOG.md、LICENSE、MISSION.md、WATCHDOG.md、commitlint.config.js、lefthook.yml、package.json 等）。README:143 自身提及 `.factory/` 交付约定，树却不展示该目录。

**证据摘录**：树内 scripts/ 节仅两行「│   ├── badcase_runner.py              # Badcase 回归测试」「│   └── plugin_lock.py                 # 插件安装入口 blob 锁定（zero-regression 门禁）」；README:143「- 新增工具链/脚本资产（如 `.factory/`）时，必须同步交付配套 README……」

**复现命令**：
```bash
cd /tmp/ar-audit && git ls-files | cut -d/ -f1 | sort | uniq -c | sort -rn | head -12   # tools=40、.factory=70、templates=5、.github=7
git ls-files scripts/ | wc -l   # → 27
git ls-files | grep -v /        # 根文件 16 个，树仅含 2 个
```

**建议**：树补 tools/、templates/、.factory/（或加「仅列规范消费面目录」省略注记）；scripts/ 收敛为目录级不逐文件，规避再次漂移。

### R14 | tools/git/commitlint.config.cjs:20 | 🟡

**问题描述**：注释自述「本件不参与比对」，但 doc-freshness R9 门禁实际对本件执行两项校验（分发件 scope-enum ⊆ 根枚举的 fail-closed 子集校验 + 枚举声明前须标注「下游」）。陈述与门禁实现不符，读者会误以为本件可自由增删枚举。

**证据摘录**：
- cjs:20「//    R9 门禁守护上游三方一致，本件不参与比对）」
- check_doc_freshness.py:517「c. 分发 .cjs 枚举 ⊆ 根枚举 + 声明前注释标注「下游」（防误当权威）」

**复现命令**：
```bash
cd /tmp/ar-audit && sed -n '20p' tools/git/commitlint.config.cjs && grep -n '下游' tools/check_doc_freshness.py | head -4
```

**建议**：注释改为「本件为下游子集：R9 校验其枚举 ⊆ 根枚举且带「下游」标注」。

### R15 | steering/git-conventions.md:121、195 | 🟡

**问题描述**：两处 HTML 编辑期注释「待 apply」所列条款均已落地，成为过时陈述：:121 所列「暂存核验/分支同步/推送复核」分别已存于 :102/:99/:96-99 一带；:195 所列「stacked PR/强推收敛」已存于 :197-199 与 :181。

**证据摘录**：
- :121「<!-- 待 apply 的「暂存核验/分支同步/推送复核」类条款视语义落本节或「同步纪律」 -->」
- :195「<!-- 待 apply 的「stacked PR/自动合并边界/强推收敛」类条款落本节 -->」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -n '待 apply' steering/git-conventions.md && sed -n '102p;181p;197,199p' steering/git-conventions.md
```

**建议**：删除两注释；与 R05 重复块同一次清理提交处理。

### R16 | steering/database-design-specification.md:131 vs :43 | 🟡

**问题描述**：提交前自检清单「含 5 个必含字段」未吸收 :43 日志/流水表豁免（可免 creator_id/last_updater_id/last_update_time，仅保留 id+create_time）。逐条打勾执行清单会把合规日志表误判为不合规（清单缺项级：机器规则侧 ddl-guard 用例 071-clean-log-table 按豁免判合规，规范正文自洽，仅清单摘要滞后）。

**证据摘录**：
- :131「**表**：表注释 ≤ 64 / 表名合规 ≤ 30 / 含 5 个必含字段。」
- :43「> **日志/流水表豁免**：仅追加不更新的日志/流水类表（表名含 `_log` / `_flow` / `_journal`）可豁免 `creator_id` / `last_updater_id` / `last_update_time`，但必须保留 `id` 与 `create_time`。」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -n '含 5 个必含字段' steering/database-design-specification.md && sed -n '43p' steering/database-design-specification.md
```

**建议**：清单项改「含 5 个必含字段（日志/流水表按豁免保留 id+create_time）」。

### R17 | steering/gtsp/02-naming.md:17 | 🟡

**问题描述**：Assembler 行「见 01 §7」指针落空：01 §7「分层职责与依赖方向」职责表无 Assembler 条目（仅 Controller/AppService/DomainService/Repository 接口/RepositoryImpl/Mapper 六行）；Assembler 实际定义在 01:49（§4 模块表）与 01:193（§17 返回规约）。对照同文件 :25 Converter「见 01 §7」成立（§7 表 RepositoryImpl 行含「PO↔Entity 转换」），证明该指针本可指对。

**证据摘录**：02:17「| 装配器 | `Assembler` | app.application.assembler | `OrderCreateAssembler`（Entity↔DTO 转换，见 [01](01-project-structure.md) §7） |」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -n 'Assembler' steering/gtsp/01-project-structure.md steering/gtsp/02-naming.md   # 01 仅 49、193 两处
sed -n '97,111p' steering/gtsp/01-project-structure.md   # §7 表无 Assembler 行
```

**建议**：指针改「见 01 §4」，或 01 §7 职责表补 Assembler 行。

### R18 | tools/git/commit-template.txt:7 | 🟡

**问题描述**：计数漂移：自称「只允许使用下面7个标识」实列 9 项（feat/fix/docs/style/refactor/perf/test/chore/revert），与规范 type 表及 commitlint type-enum 的 9 项一致——仅计数词错（若为旧版 7 类残留，属历史遗留陈述）。

**证据摘录**：:7「# type 用于说明 commit 的类别，只允许使用下面7个标识。」

**复现命令**：
```bash
cd /tmp/ar-audit && grep -n '只允许使用下面7个标识' tools/git/commit-template.txt && sed -n '9,17p' tools/git/commit-template.txt | grep -c '^[a-z]*:'   # → 9
```

**建议**：改「9 个标识」；与 R08 同文件同次修。

## 待验证

**T1 | gtsp/09-cr-checklist.md:26 vs gtsp/02-naming.md:48-56**：09 为【强制】合并门禁，其应用层动词摘要「create/remove/modify/get/page」未含 02 §2 动词表的 list（列表查询）/count（统计）（02:53-54）；按 02 命名的 listXxx/countXxx 方法需借「业务语义或」开口才能过 09 审查。是否刻意摘要（09 面向 CR 快查）需人工裁定；若非刻意则属 R07 族（门禁摘要与规范表漂移）。复现：`sed -n '26p' steering/gtsp/09-cr-checklist.md; sed -n '48,56p' steering/gtsp/02-naming.md`

**T2 | database-design-specification.md:61 vs :97**：治理主体异名——「经技术委员会评审」（61）vs「经技术管理委员会评审」（97），仓内证据无法判定是同一机构命名漂移还是两个机构（skills/ddl-guard 侧两种称呼亦各有沿用）。需人工裁决后统一或显式区分。复现：`grep -n '技术委员会\|技术管理委员会' steering/database-design-specification.md`

**T3 | README.md:118**：「依据 steering/gtsp/01」为文件名简写（实际 01-project-structure.md），目录内无歧义、目标实存，判定良性不入发现；如追求引用精确可写全名。复现：`sed -n '118p' README.md; test -e steering/gtsp/01-project-structure.md && echo EXISTS`

## 上报事项

1. **跨会话交叉（请协调方去重/互证）**：
   - audit-c（观察 47171）：「【强制】标记泄漏到 canonical docs 之外（checker 输出串/测试）」——影响各维度强制条款计数口径；若本报告 R06/R07 的分级冲突裁定被采纳，两侧强制标记数将随之变动。
   - audit-d（47179/47186）：115 强制条款门禁映射 29✅/12🟡/74❌；其 D-02 引用 CLAUDE.md:36 元规则，与本报告 R02 的重复块同一行——修复 R02 后行号移位，audit-d 报告需同步。
   - audit-b（47182）：bash 3.2 全角字符紧邻 `$var` 缺陷 5 处真实命中（coverage.sh×3 等）——coverage.sh 正是 testing-standards:60 豁免链的机器执行面；本维度已确认规范↔脚本语义逐点一致（见覆盖声明检查点④），若 audit-b 所报缺陷影响脚本实际行为，需回归该一致性结论。
   - 本报告 R08/R14/R18（commit-template.txt、commitlint.cjs 注释）可能同时落入 audit-b（分发物健壮性）/audit-c（文档-事实）视野；观察 47188 已报「subject 长度与 type 计数跨文件不一致」。建议归属本维度（规范载体文本自洽），其余清单剔除以免双计。
2. **外部观察更正**：有观点称「skills/contract-guard/templates/ 不存在」——实测存在（japicmp-pom-snippet.xml、yunxiao-pipeline-contract.yaml），cross-repo-contract-standards.md:41/54 引用可解析（检查点③已验证）。供协调方向提出方更正。
3. skills/alibabacloud-devops→.factory/forge 陈旧引用（audit-c 47166）属 skills/ 目录，非本维度主体文件范围，仅转报不展开。
4. 本审计全程只读：未修改 /tmp/ar-audit 内任何文件、无任何 git 写操作；工作树在启动、收尾两轮 `git status --short` 核对均为空。

## 覆盖声明

**审查对象 21 个主体文件（全量列举，非抽样）+ 8 个对照锚文件**：

- 主体：`CLAUDE.md`；`README.md`；steering 顶层 9（api-contract-freeze-standards、cross-repo-contract-standards、database-design-specification、frontend-standards、git-conventions、openapi-standards、review-report-standards、task-package-standards、testing-standards）；steering/gtsp/ 10（README、01-project-structure、02-naming、03-api-feign、04-database-mybatis、05-logging、06-exception、07-config、08-comments-deprecated、09-cr-checklist）。
- 对照锚（条款比对用，非审查对象）：tools/git/lefthook/coverage.sh、tools/git/commitlint.config.cjs、commitlint.config.js、tools/git/commit-template.txt、tools/check_doc_freshness.py、templates/task-brief.md.template、hooks/load-steering.sh、tools/git/install.sh。

**逐检查点全量命令与结果**（均在基线 135b829 干净树上由主会话亲跑）：

1. 基线对账：`git rev-parse HEAD` → `135b82913f7bc8936327df16fa1b1ec7398bb640`；`git status --short` → 空（启动/收尾两轮）。
2. 检查点① frontmatter 全量：`for f in steering/*.md steering/gtsp/*.md; do fm=$(awk '/^---$/{n++;next} n==1' "$f"); echo "$fm" | grep -q '^title:' && echo "$fm" | grep -q '^scenario:' || echo "MISS:$f"; done` → 0 MISS；`ls steering/*.md steering/gtsp/*.md | wc -l` → 19（顶层 9 + gtsp 10），19/19 全含 title+scenario。
3. 检查点② CLAUDE.md 索引对账：CLAUDE.md:8 概念清单 ↔ `ls steering/*.md`（9↔9，无未索引文件）；CLAUDE.md:11 声明完整索引由 hook 动态生成，无逐文件表需对账。
4. 检查点③ 引用完整性全量：21 主体文件循环提取仓内路径引用 → 77 唯一路径逐一 `test -e` → 仅 2 MISS 且均良性（README:121 `docs/design/architecture/` 属 .gitignore:32 声明性不入库——`ls docs/design/architecture/` 不存在 + `grep -n 'design/architecture' .gitignore` 命中 :32；README:118 `steering/gtsp/01` 简写可解析，见 T3）；`grep -rn '\.md#' <21 文件>` → 0 条锚点形式引用；散文节引用 5 条逐一对照目标 `^## ` 标题实存（gtsp/01:53→09§2、02:17→01§7※弱指针升 R17、02:25→01§7、09:41→03§2、gtsp/README:9→01§3）；api-contract-freeze:31「见前端规范 §1」→ frontend-standards.md:11「## 1. Mock 与本地联调」实存；README:125 research 声明属实：`grep -L 're-check-trigger' docs/research/*.md` → 0（7/7 含）。
5. 检查点④ 指定冲突比对：
   - testing-standards:60 豁免第 4 条 ↔ coverage.sh:207-227 逐点人工比对（预算文件 `.lefthook/coverage-budget.env`、台账 `.lefthook/coverage-exemptions.md`、LEDGER_TOTAL 正则 @:215、min 逐维 @:223-224、预算>0 无台账 fail-closed @:213-219、仅 full 模式）——**一致，无冲突**（「与逐项合计一致」未机器校验，属已知留白非矛盾）；
   - gtsp/06 ↔ gtsp/09 异常体系六锚点比对（响应信封 06:12↔09:45、BaseException/ErrorType 06:18-20↔09:60-62、ExceptionEnum 三字段 06:31↔09:61、命名 06:33↔09:61、未知异常 06:38↔09:62、依赖表 09:76-77↔06:12/20）——**一致**；
   - task-package §1.3:36 ↔ §1.6:54 ↔ template:18 三读比对 → R06。
6. 检查点⑤ 过时陈述：README:7-51 结构树 ↔ `git ls-files | cut -d/ -f1 | sort | uniq -c`（tools=40、.factory=70、templates=5、.github=7 缺；`git ls-files scripts/ | wc -l`=27 vs 树列 2；`git ls-files | grep -v /`=16 根文件 vs 树列 2）→ R13；git-conventions 待 apply 注释 → R15；cjs 自述注释 ↔ check_doc_freshness.py R9 实现 → R14；README 分级描述 ↔ 各规范自述（62↔db:8 不符 → R09；68↔frontend 属实：12×【强制】/10×【推荐】/0×【参考】）。
7. 分级口径核对：`for f in steering/gtsp/*.md; do echo "$f $(grep -c '【强制】\|【推荐】' "$f")"; done` → 01-08 与 gtsp/README 全 0（gtsp/README:12「01-08 不逐条分级」声明属实），09 为唯一非零（38）。
8. 重复块程序化确认：R01–R05 全部以 `diff <(sed …) <(sed …)` 输出为空验证（命令见各条目）。
9. 子代理使用与复核纪律：3 个只读 scout 分工覆盖 21 主体文件首遍精读（ScoutA：openapi/cross-repo/review-report/api-contract-freeze；ScoutB：database/frontend/git-conventions + 分发物链 commitlint 两件/template/README/install.sh/lefthook.yml；ScoutC：gtsp 01-05/07-08/README），主会话另行亲读/亲验全部 21 文件的关键行段；scout 全部候选发现逐条经主会话独立 grep/diff 复核后方入本清单（每条「复现命令」均主会话亲跑、输出与描述一致）；未采信任何未复核断言——ScoutB 两条 SUSPICION 分别降入 T2（治理主体异名）与并入 R18（计数成因）；ScoutA 初判 🔴 的 R01 经复核降 🟠（理由见该条）。ScoutB 对 git-conventions↔commitlint.cjs、frontend↔README:68、frontend 内部无重复三项 CLEAN 结论亦经主会话抽验采纳。
10. 范围外未审（非本维度）：AGENTS.md、skills/、docs/design/、docs/research/、arch-hawkeye/、.factory/ 的内容审查——仅作引用解析与交叉引用对象使用。
