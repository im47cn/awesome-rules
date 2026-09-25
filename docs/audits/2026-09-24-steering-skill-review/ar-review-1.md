# awesome-rules steering 文档审查报告（ar-review-1）

- 基线对账：`git status` → HEAD = `dfe1732`（Merge PR #238），工作树 clean，与任务基线一致，无漂移无需披露。
- 审查对象（全文精读，行号来自实读）：
  1. `steering/api-contract-freeze-standards.md`（89 行）
  2. `steering/cross-repo-contract-standards.md`（137 行）
  3. `steering/openapi-standards.md`（169 行）
  4. `steering/database-design-specification.md`（160 行）
- 交叉核实过的引用（全部有效，不构成发现）：`openapi-standards.md:114` → `steering/gtsp/06-exception.md` 存在且错误码格式 `{系统标识}_{模块}_{序号}`（06:33）与正文表述吻合；`cross-repo-contract-standards.md:41/54` → `skills/contract-guard/templates/japicmp-pom-snippet.xml` 存在；`:126` → `skills/contract-guard/scripts/check-contract.sh` 存在且可执行（`-rwxr-xr-x`）；`api-contract-freeze-standards.md:31` 所指前端规范 §1（frontend-standards.md:11「Mock 与本地联调」）存在。
- 审查依据优先级：任务标准 A/B/C → 仓根 CLAUDE.md:37（"标注强制的条款应同步评估可机械检查性"——与标准 B 同构的仓内总则）→ 仓内既有写法。凡与标准冲突处按标准原样报告。

---

## 一、发现明细

### openapi-standards.md

**OA-1 | steering/openapi-standards.md:4 | B | 🟠**
- 问题：`inclusion: always` 为遗留字段，无任何功能消费方——SessionStart hook 仅解析 `title`/`scenario`（hooks/load-steering.sh:37-44 全文无 inclusion 分支）；CONTRIBUTING.md:146 明示"inclusion: always——部分历史文件保留的既有字段，新增文件无需写"。且本文是场景触发型文档（scenario 限定"设计/审查对外 Open API"），语义上也非 always-load。
- 建议：改前 `inclusion: always` → 改后删除该行（frontmatter 只留 title/scenario，与 api-contract-freeze/database 两个较新文件一致）。
- 依据：标准 B（inclusion 字段取值合理）；CONTRIBUTING.md:146；hooks/load-steering.sh:37-44。

**OA-2 | steering/openapi-standards.md:2 与 :7 | B | 🟠**
- 问题：frontmatter title `Open API 设计规范` 与正文 H1 `Open API 设计与安全规范` 不一致。hook 索引注入的是 title（load-steering.sh:38），读者打开文件看到 H1——同一文档在两处叫两个名字，且"安全"这个实质维度（§6 占全文约 1/5）只存在于 H1 一侧，按 title 检索"安全/脱敏"会漏。
- 建议：改前 `title: Open API 设计规范` → 改后 `title: Open API 设计与安全规范`（改 title 而非 H1，保留正文信息量）。仓内 9 个 steering 文件 7 个 title=H1，统一后消除仅有的两处分裂之一（另一处见 DB-7）。
- 依据：标准 B（hook 扫描依赖 frontmatter）+ C（术语一致）；实测普查：仅本文件与 database-design-specification.md 不一致。

**OA-3 | steering/openapi-standards.md:47、:72、:161 | B | 🟠**
- 问题：三处【强制】条款均可机械检查但既未接线也未标注现状：(1) :47 枚举传值——扫描 DTO/Schema 注解中 `enum` 定义与裸 `String`/`Integer` 状态字段即可静态查；(2) :72 统一 HTTP 200——扫描 Controller/响应封装即可；(3) :161 只增不删——对 OpenAPI spec 做版本间 diff（springdoc 产物入 CI）即可。现状是脚本仅自动覆盖路径 kebab-case/动词集/path 变量/时间注解 shape 四项（skills/api-guard/openapi-manual-rules.md:5-6 自述），其余全部落在人工清单。
- 建议：(a) 接线：`api_check.py` 增枚举传值规则 + badcase 负控制（对齐 CLAUDE.md:37"能查出的配静态门 + 负控制"）；HTTP 200 与 spec-diff 属目标工程 CI，可在本文各条款尾标注接入方式。(b) 至少标注现状，照抄仓内成熟样式（ddl-manual-rules.md:34"ddl_check.py 已全文拦截…语句本身无需再人工逐条扫描"）：:47 条尾加"（机械化：api-guard 扫描 @Schema(enum)，待接入；现仅靠人记）"。
- 依据：标准 B（强制条款逐条评估可机械检查性）；CLAUDE.md:37；openapi-manual-rules.md:5-6。

**OA-4 | steering/openapi-standards.md:125-126 | B | 🔵**
- 问题：blockquote 第二段"通过全局 `@ExceptionHandler` 统一兜底"与 gtsp/06-exception.md:36-38（`@RestControllerAdvice` 全局处理器、未知异常兜底）在两份 steering 里重复维护异常兜底机制；两文档已互链（openapi:114 ↔ 06:14/34），边界本已划清（对外信封 vs 内部 ResultMode），兜底机制句属可收敛重复。
- 建议：改前 `> 错误码集中注册，通过全局 @ExceptionHandler 统一兜底，禁止逐方法手写 try-catch；参数校验信息须给出明确的参数名和规则要求。` → 改后 `> 错误码集中注册、统一兜底，禁止逐方法手写 try-catch（内部服务全局处理器机制见 gtsp/06-exception.md §4）；参数校验信息须给出明确的参数名和规则要求。`
- 依据：标准 B（与其他 steering 无重复条款，重复者收敛到单一权威源）。

**OA-5 | steering/openapi-standards.md:3 | B | 🔵**
- 问题：scenario 仅"设计/审查对外 Open API"，缺触发词。scenario 是 hook 注入索引中 AI 判断是否加载的唯一场景线索（load-steering.sh:60）；对照仓内较新文件（frontend-standards.md:3、api-contract-freeze-standards.md:3 均列触发词清单），本文用户以"响应体/错误码/幂等/脱敏"等具体词提问时命中度低。
- 建议：改前 `scenario: 设计/审查对外 Open API` → 改后 `scenario: 设计/评审对外 Open API（开放平台接口）：URI 四段式、统一响应体、错误码、幂等键、日志脱敏、OpenAPI 3 文档注解相关任务必读`。
- 依据：标准 B（frontmatter 完整性、hook 依赖）；frontend-standards.md:3 范式。

### cross-repo-contract-standards.md

**CR-1 | steering/cross-repo-contract-standards.md:4 | B | 🟠**
- 问题：同 OA-1——`inclusion: always` 无功能消费方（hook 不读）、CONTRIBUTING.md:146 定性遗留字段；且本文 :3 scenario 明确是条件触发（"变更会被其他仓库依赖的 API 模块…配置跨仓 CI 门禁"），与 always 语义自相矛盾。
- 建议：改前 `inclusion: always` → 改后删除该行。
- 依据：标准 B；CONTRIBUTING.md:146；load-steering.sh:37-44。

**CR-2 | steering/cross-repo-contract-standards.md:54 | B | 🟠**
- 问题：正文写"重建脚本见 `skills/contract-guard/templates/japicmp-pom-snippet.xml`"——重建脚本实际是 XML 模板内的**注释块**（模板 :73-88），不是可执行脚本文件；接入方必须人工从注释里复制粘贴组装，且 SKILL.md 的 files 清单（contract-guard/SKILL.md:9-13）未登记任何重建脚本，渐进式加载链路里它不可见。
- 建议：抽出为 `skills/contract-guard/scripts/rebuild-baseline.sh`（含 `chmod +x`，内容即模板 :73-88 注释块），随后三处同步：本行改为"重建脚本见 `skills/contract-guard/scripts/rebuild-baseline.sh`"；模板 :73 注释块改为指向该脚本；SKILL.md files 清单登记。已核实 scripts/ 现有 check-contract.sh 具备可执行位，目录范式成立。
- 依据：标准 B（引用的脚本路径逐一核实存在，脚本须有可执行权限）+ A 精神（技能资产可执行化）。

**CR-3 | steering/cross-repo-contract-standards.md:36、:38、:68 | C | 🔵**
- 问题：标题"门禁机制（B：japicmp + C：下游编译触发）"的 B/C 字母沿用一套已不完整的三方案编号——A 方案只剩 :134 划线条目"~~云效私服保留历史 SNAPSHOT~~——已由 sha 重建方案消灭"，新读者在本文件内找不到 A 的定义，编号成为无锚孤儿。
- 建议：两个标题去掉字母（"门禁机制：japicmp + 下游编译触发" / "japicmp 门禁（上游仓）" / "下游编译触发（跨仓）"），或在 :36 下补一句"A（私服 SNAPSHOT 保留）已废弃，见文末外部依赖假设"。
- 依据：标准 C（术语一致、可读性）。

**CR-4 | steering/cross-repo-contract-standards.md:114-117 | B | 🔵**
- 问题：门禁自检【强制】第 1 条"对比对象断言"（检查 `target/japicmp/*.diff` 首行 A≠B）目前是纯文字流程，每次门禁运行都要人工看一眼——而它恰是防"静默恒绿"的最后一道闸，恰属最该脚本化的条款。第 2/3 条（一次性接入验收、环境变更重验）为流程性动作，无法机检。
- 建议：第 1 条沉淀为 `contract-guard` scripts 下的小脚本（读 diff 文件首行正则断言 A≠B，失败 exit 1）并在 `templates/yunxiao-pipeline-contract.yaml` 的契约 job 内调用；第 2/3 条条尾标注"（一次性/流程性，仅靠人记）"。
- 依据：标准 B（能机械查的给出接入方式，查不出的显式标注）；CLAUDE.md:34（发现一致性问题优先接线而非靠人记）。

**CR-5 | steering/cross-repo-contract-standards.md:128-137 | C | 🔵**
- 问题：「外部依赖假设」节结构错层：三条无编号 bullet（:130-132）之后接残留的编号列表 1-3（:134-137，第 1 条已划线），读起来像两份不同时期的清单拼接，编号起点悬空。
- 建议：统一为 bullet 列表，:134 划线条目改为 bullet 并保留删除线（`- ~~云效私服保留历史 SNAPSHOT~~——已由 sha 重建方案消灭…`）。
- 依据：标准 C（风格一致）。

### api-contract-freeze-standards.md

**FZ-1 | steering/api-contract-freeze-standards.md:41-42 | B | 🟠**
- 问题：响应信封占位示例用 `{ code, message, data }`，业务数据键名 `data` 与本仓两个权威信封都不一致：对外统一响应体业务数据键为 `model`（openapi-standards.md:57、:82、:110 字段表）；内部 `ResultMode` 业务数据键同为 `model`（gtsp/06-exception.md:14）。虽然 :41 括注了"以目标端点后端实际契约为准，此处仅占位示意"，但示例本身在教读者一个仓内不存在的键名——占位示意也不应与统一术语打架。
- 建议：改前 `✅   响应信封 { code, message, data }（信封字段以目标端点后端实际契约为准，此处仅占位示意）` + `✅   data { subscriptionId, callbackUrl, status }` → 改后 `✅   响应信封 { code, message, model }（信封字段以目标端点后端实际契约为准，占位键名对齐仓内统一响应体，见 openapi-standards.md §4）` + `✅   model { subscriptionId, callbackUrl, status }`。
- 依据：标准 B（示例代码须符合本仓自身规范）+ C（术语一致）。

**FZ-2 | steering/api-contract-freeze-standards.md:31 | B | 🔵**
- 问题："（见前端规范 §1）"为纯文本引用，无相对链接；md_link_check 门禁（scripts/md_link_check.py，pre-push 执行）只守护真链接，章节号重排后此引用会静默失效。
- 建议：改前 `mock 越同构（见前端规范 §1）` → 改后 `mock 越同构（见 [前端规范 §1](frontend-standards.md)）`。目标节"## 1. Mock 与本地联调"（frontend-standards.md:11）已核实存在。
- 依据：标准 B（内部相对链接有效且可被门禁守护）。

（本文件无其他发现：强制条款 :13/:48/:74 的机械检查性已由 :65-70 自评——"前两条依赖人记忆 checklist，守卫把『照抄不漂移』变成机器判定"列为【推荐】并给出 contract:check 静态 diff 方案，符合标准 B 的"查不出的显式标注"要求，如实声明优于空贴标签。）

### database-design-specification.md

**DB-1 | steering/database-design-specification.md:13 | B | 🟠**
- 问题：表名重复条款无分级标注（违反 :8 自立的"条款分【强制】/【推荐】/【参考】"体例）；且句尾"审查/CI 宜加「表名不得重复」检查"的现状态未交代——实测 `ddl_check.py` **没有**重复表名规则（全脚本 grep"重复/duplicate"仅命中 :950 的"id重复索引"），即该建议至今未落地，"宜加"读起来像已有人管。
- 建议：改前 `- 向共享初始化 DDL 追加表前，先全文检索确认同名 CREATE TABLE 不存在：…审查/CI 宜加「表名不得重复」检查。` → 改后 `- 【强制】向共享初始化 DDL 追加表前，先全文检索确认同名 CREATE TABLE 不存在：…（后果=合并后新环境初始化中断，强制级）（机械化：ddl_check.py 增同名 CREATE TABLE 检测 + badcase 负控制，当前未实现，仅靠人记）`。
- 依据：标准 B（强制条款可机械检查性评估、给出接入方式）；本文件 :8 体例自洽。

**DB-2 | steering/database-design-specification.md:60 | B | 🔵**
- 问题：同一条【强制】内两种子句机械化状态不同却无区分："禁止 `CHANGE COLUMN`"已被脚本拦截（ddl_check.py:610-617，规则名"禁止 CHANGE COLUMN"，MANDATORY 级）；"新加字段一律追加在表末尾"无任何机械检查（脚本无 ADD COLUMN 位置规则，SKILL.md files 清单 :7-174 亦无对应 badcase）。
- 建议：条尾标注现状与拆分：`（"禁止 CHANGE COLUMN"已由 ddl-guard 脚本拦截；"末尾追加"当前仅靠人记——可扩展 ddl_check 解析 ALTER 语句列位置）`。
- 依据：标准 B；ddl_check.py:610-617 实测。

**DB-3 | steering/database-design-specification.md:103 | B | 🔵**
- 问题：【强制】SQL 压测（生产数据量 2–3 倍、<1s / <10 万条 <500ms）无法静态机检（需压测环境与数据构造），正文未标注；ddl-guard 层已把它归入"需运行时验证"人工清单（sql-manual-rules.md:24 含完整操作步骤），但 steering 读者无从知道该落差。
- 建议：条尾追加 `（运行时验证，无法静态机检，仅靠人记；操作指引见 ddl-guard sql-manual-rules.md「需运行时验证」）`。
- 依据：标准 B（查不出的显式标注"仅靠人记"）；sql-manual-rules.md:24。

**DB-4 | steering/database-design-specification.md:70-74、:43、:133 | B | 🟠**
- 问题：del_flag 强制性口径三处互相打架：(1) 新表必含字段表 :33-39 **不含** del_flag；(2) "逻辑删除字段 统一使用"（:70）无【强制】标注、未说明是否所有新表必含；(3) :43 日志/流水豁免清单只豁免 creator_id/last_updater_id/last_update_time，对 del_flag 是否豁免只字未提；(4) 自检清单 :133 却把"`del_flag` 统一"当必查项。脚本行为同样停在中间态：ddl_check.py:866-875 只查"存在则必须叫 del_flag 且注释合规"，不查存在性。审查者按哪一处置信，结果不同。
- 建议（收敛到单一口径）：:70 改前 `统一使用：` → 改后 `【强制】所有业务表必含逻辑删除字段，统一使用：`；:43 豁免行改前 `可豁免 creator_id / last_updater_id / last_update_time，但必须保留 id 与 create_time` → 改后 `可豁免 creator_id / last_updater_id / last_update_time / del_flag（只追加不删除，无逻辑删除语义），但必须保留 id 与 create_time`；随后 :133 自检清单口径自然落地。若定"必含"，同步给 ddl_check.py 必含字段检查补 del_flag（业务表）与豁免（日志表）分支，或标注"存在性人工核对"。
- 依据：标准 B（条款间无矛盾）+ C；ddl_check.py:866-875、badcase 026/029/030/071 实测行为。

**DB-5 | steering/database-design-specification.md:95 | B | 🔵**
- 问题：未分级条款携带"必须"级语义（"两层判定阈值必须同口径"、触发器是"强制安全边界"）——:8 体例承诺条款分级，此条游离在外；而 ddl-manual-rules.md:38 已把它当强制例外流程在执行（"脚本对触发器一律报【强制】…人工判定后放行，并核对两层判定阈值同口径"）。
- 建议：改前 `- 历史事实类数据的删除保护…` → 改后 `- 【强制】历史事实类数据的删除保护…（:96 触发器禁令的例外条款）`。同文件 :82/:91 为说明性许可句，可不标。
- 依据：标准 B；本文件 :8 体例；ddl-manual-rules.md:38。

**DB-6 | steering/database-design-specification.md:131 | C | 🔵**
- 问题：自检清单用行号自引用"（日志/流水表按 :43 豁免保留 id+create_time）"——任何上方插行都会让 43 漂移到错误条款，且行号引用不受 md_link_check 守护。
- 建议：改前 `（日志/流水表按 :43 豁免保留 id+create_time）` → 改后 `（日志/流水表按「三、表」的日志/流水表豁免条：保留 id+create_time）`。
- 依据：标准 C；标准 B（链接有效性——行号引用无门禁可依）。

**DB-7 | steering/database-design-specification.md:2 与 :6 | B | 🔵**
- 问题：同 OA-2——frontmatter title `数据库设计规范` 与 H1 `数据库设计开发规范（MySQL）` 不一致；hook 索引名丢掉"MySQL"限定词，用户问"MySQL 规范"时按索引名匹配弱一拍。
- 建议：改前 `title: 数据库设计规范` → 改后 `title: 数据库设计开发规范（MySQL）`（H1 保持不变）。
- 依据：标准 B + C；同 OA-2 普查证据。

---

## 二、【强制】条款可机械检查性总评（标准 B 逐条）

| 文件 | 强制条款 | 机械化现状 | 结论/动作 |
| --- | --- | --- | --- |
| api-contract-freeze :13/:48/:74 | 五项冻结/四步 checklist/先冻结再实现 | 无静态守卫；:65-70 已自评并给出 contract:check 静态 diff 方案（【推荐】） | 仅靠人记（文档已如实标注，合规） |
| cross-repo :109-121 | 门禁自检 3 条 | 第 1 条可脚本化未脚本（→CR-4）；第 2/3 条一次性/流程性 | 1 接线、2/3 标注仅靠人记 |
| cross-repo :25/:34 | description 认定/新模块必含"契约" | check-contract.sh 承载 description 解析（SKILL.md:33） | 已机械化（目标仓 CI 侧由 japicmp 门禁闭环） |
| cross-repo :92/:95 | 不得以未报错认定兼容/豁免季度复盘 | 评审判断 + 日历动作 | 仅靠人记（可接受） |
| openapi :47/:72/:154-157/:161 | 枚举传值/HTTP 200/幂等键声明/只增不删 | 脚本仅覆盖 4 项路径类规则（openapi-manual-rules.md:5-6） | →OA-3：枚举传值接 api_check + 负控制；其余标注现状或接目标仓 CI |
| openapi 其余 | URI/参数/响应体/错误码/脱敏 | 人工清单兜底（openapi-manual-rules.md 全表） | 派生模式在轨，当前与正文零漂移（抽查逐字比对一致） |
| database DDL 静态类 | 命名/注释/类型/必含字段/索引/禁用语句等 | ddl_check.py 机械化（badcase 010-074 + ddl-manual-rules.md:34 标注） | 已机械化，覆盖面良好 |
| database :21/:87/:103/:123 | InnoDB+utf8mb4/EXPLAIN/压测/应用内禁 DDL | :21 环境基线（DDL 文本被 :17 要求剥离子句，静态无从查）；:87/:103 运行时（sql-manual-rules「需运行时验证」）；:123 sql_check 扫 mapper XML 部分覆盖 | :103 →DB-3 标注；其余属合理的运行时/环境验证层 |

---

## 三、统计

| 维度 | 计数 |
| --- | --- |
| 发现总数 | 19 |
| 按严重度 | 🔴 必改 **0**；🟠 建议 **8**（OA-1/2/3、CR-1/2、FZ-1、DB-1/4）；🔵 可选 **11**（OA-4/5、CR-3/4/5、FZ-2、DB-2/3/5/6/7） |
| 按类别 | A **0**（审查对象均为 steering，无 SKILL.md；CR-2 涉及技能资产但按 B 的引用核实条款归 B）；B **16**；C **3** |
| 按文件 | openapi 5；cross-repo 5；api-contract-freeze 2；database 7 |
| 核实通过、未计发现 | 4 文件全部内部/跨文件引用有效；CLAUDE.md:8 规范清单与 steering 现状零漂移；freeze 与 cross-repo 边界清晰无重复（前者管前端实现时序、后者管 Maven 产物兼容，contract-guard SKILL.md:55-56 明示边界）；openapi 字段 camelCase 与 database 字段 snake_case 属 API/DB 分层惯例，非矛盾；openapi"只增不删"与 cross-repo"豁免制破坏性变更"针对不同契约对象（对外 HTTP vs 内部 jar），口径差异合理 |

## 四、审查中上报事项

1. **范围外引用问题 2 类（建议移交对应审查/归属人）**：交叉核实时发现——(a) **真失效**：`task-package-standards.md:54` 引用 `.factory/decisions.md`，该文件已被 commit 684cdc4 刻意删除（"索引迁 docs/adr/README.md"），ADR 现居 `docs/adr/`，引用成为陈旧漂移。(b) **环境相对引用未注明**：`git-conventions.md:158/160` 引用 `.lefthook/pre-push-delete-guard.sh` 与 `install.sh`——实测 `.lefthook/` 在 .gitignore:10-12 中声明为 install.sh 分发的**运行时副本**（入库源为 `tools/git/lefthook/`，`tools/git/install.sh` 存在），故引用描述的是分发后环境而非仓内断链，但文档未在行内注明这一相对性，照字面在仓内检索会扑空（文档清晰度候选）。两处均不在本次 4 个审查对象内，未计入发现统计。
2. **manual-rules 逐条锚定缺失（skills 侧，范围外）**：`openapi-manual-rules.md`/`ddl-manual-rules.md` 与 steering 正文近乎逐字派生（今日抽查零漂移），但 CONTRIBUTING.md:212 要求"标注与规范文件的对应关系"，两文件仅有文件级全局链接、无条款级锚定，未来正文改动无门禁拦漂移（doc-freshness 只管计数字类陈述）。建议补条款级对应或加漂移检查。
3. **无 🔴 发现**：4 个文件内所有相对链接与引用路径逐一核实有效；未发现与 CLAUDE.md 或彼此矛盾的实质条款。严重度最高的问题（🟠）集中在"遗留字段未清、示例术语漂移、强制条款机械化现状不透明、del_flag 口径分裂"。
4. 本次审查全程只读：未对仓内任何文件执行写操作，无 git 写操作；唯一写权限 `/tmp/ar-review-1.md` 已按约定使用。
