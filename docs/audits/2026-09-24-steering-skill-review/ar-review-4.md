# awesome-rules steering/gtsp 文档审查报告（ar-review-4）

审查日期：2026-09-24｜基线：`git -C /Users/dreambt/sources/awesome-rules status` → `On branch main, nothing to commit, working tree clean`，`HEAD = dfe173295422ddfa02ee81dddc903e081a251b43`，与任务基线 dfe1732 一致，**无漂移、无需披露项**。审查全程只读，唯一写入为本报告。

审查方式：10 个目标文件逐行精读；交叉核实仓根 CLAUDE.md、hooks/load-steering.sh（frontmatter 扫描机制）、steering/openapi-standards.md（对齐声明）、.claude-plugin/plugin.json 与 .codex-plugin/plugin.json（README 引用行号）、skills/arch-guard/scripts/arch_check.py 与 skills/api-guard/scripts/api_check.py（09「已接线」函数存在性）、tools/gauntlet.sh（接线方式）、docs/platform-matrix.md（§4 存在性）。所有行号来自实际读取输出。

---

## 发现清单

**F1** | steering/gtsp/README.md:19 ↔ steering/gtsp/02-naming.md:3 | B | 🟠 | README 维度索引中 02 的适用场景写「类后缀/方法分层/扩展点/常量类」，而 02 frontmatter scenario 实为「类后缀/方法/注入/常量类」，两侧措辞漂移；SessionStart hook（hooks/load-steering.sh:37-45）注入的是 frontmatter scenario，README 表是人类入口，入口与注入源不一致会误导按图索骥。| 改 README.md:19 该单元格：改前 `类后缀/方法分层/扩展点/常量类` → 改后 `类后缀/方法/注入/常量类`（与 02 frontmatter 逐字对齐；如确需保留"扩展点"触发词，则同步把 02:3 scenario 改为 `类后缀/方法分层/注入/扩展点/常量类`，二选一收敛到单一权威源）。| 依据 B（frontmatter title+scenario 完整且为 hook 扫描依赖）、C（术语一致）。

**F2** | steering/gtsp/02-naming.md:35 ↔ steering/gtsp/01-project-structure.md:173 | B | 🟠 | 02:35 规定领域状态枚举位于 `domain（model/enum 或领域服务同包）`，但 01 §15 的权威包结构树中 domain 行为 `model/{entity,valueobject,condition} extensionpoint/ repository/ service/ event/`——连冷门的 `condition` 都列出，却缺 `model/enum`；两份规范对同一包结构各执一词，按 01 生成的工程会违反 02。| 改 01-project-structure.md:173：改前 `domain/        model/{entity,valueobject,condition} extensionpoint/(ExtPt) repository/(接口) service/(DomainService) event/` → 改后 `domain/        model/{entity,valueobject,condition,enum} extensionpoint/(ExtPt) repository/(接口) service/(DomainService) event/`；如「领域服务同包」仍是合法备选，在 02:35 保持现文即可（首选项已入树）。| 依据 B（steering 间无矛盾条款）。

**F3** | steering/gtsp/01-project-structure.md:125 | C | 🟠 | 「仅复杂 MyBatis-Plus 链式仓储才用 `ServiceImpl`（模式 B）」——「模式 B」标签全 gtsp 目录仅此一处出现，「模式 A/B」分类法无定义（grep 实证），读者无从对照。| 删除悬空标签：改前 `仅复杂 MyBatis-Plus 链式仓储才用 \`ServiceImpl\`（模式 B）` → 改后 `仅复杂 MyBatis-Plus 链式仓储才用 \`ServiceImpl\``；如需保留分类法，须先在 §10 定义模式 A（手动 RepositoryImpl）/模式 B（ServiceImpl）两段。| 依据 C（术语一致）、B。

**F4** | steering/gtsp/07-config.md:23 | B | 🟠 | §3 首条混入 Supabase 域术语：`前端 anon key`、`service_role/secret key`、`行级安全（RLS）`——本规范栈为 Java/Spring Cloud + Nacos（§3 其余条款均围绕 Nacos），anon key/RLS 属他栈概念，疑似跨项目拷贝残留；通用原则（凭证按权限分级专用）成立，但示例误导。| 改前 `- 凭证按权限级别专用：面向客户端的公开凭证（如前端 anon key）不得用于服务端/CI 任务，服务端须使用对应的特权凭证（service_role/secret key）；行级安全（RLS）场景下低权限凭证会静默返回空数据集而非报错，此类静默错误比显式失败更难发现` → 改后 `- 凭证按权限级别专用：面向客户端下发的公开凭证不得挪用于服务端/CI 任务，服务端须使用对应的服务账户/特权凭证；权限层级错配可能在数据层表现为静默空结果而非报错，比显式失败更难发现，配置 CR 时须核对凭证层级`。| 依据 B（与仓内体系一致、示例代码/示例须符合本仓自身规范）、C。

**F5** | steering/gtsp/08-comments-deprecated.md:16 + steering/gtsp/09-cr-checklist.md:64-70 | B | 🟠 | 08:16「**Feign 接口方法和 Controller 方法必须注释。**」携带"必须"语义却无【强制】/【推荐】分级标注，且 09 §1「配置与注释」组（68-70 行）无对应清单项——按 README:12「09 为 CR 合并门禁清单」，该"必须"条款实际逃逸门禁，仅靠人记。| 两处动作：① 08:16 改前 `**Feign 接口方法和 Controller 方法必须注释。**` → 改后 `**【强制】Feign 接口方法和 Controller 方法必须注释。**`；② 在 09-cr-checklist.md:69 与 :70 之间插入 `- [ ]【强制】Feign 接口方法与 Controller 方法有 Javadoc 注释（功能 + @param + @return）（人工）`。| 依据 B（【强制】条款须可被门禁覆盖、分级标注一致）、README:12、CLAUDE.md:44。

**F6** | steering/gtsp/09-cr-checklist.md:26 ↔ steering/gtsp/02-naming.md:48-55 | B | 🟠 | 09:26 概括基础设施层动词为 `insert/update/delete/queryPage/queryList/queryDetail`，较 02 §2 权威表缺 `queryById`（02:52 单个查询备选）、`count`（02:54）、`batch`+动词（02:55）；按 09 门禁严格执行会把 02 判合法的 `count`/`batchXxx` Mapper 方法误判违规——门禁摘要与权威源漂移。| 改 09:26：改前 `（人工）` 前的动词列举 `insert/update/delete/queryPage/queryList/queryDetail` → 改后 `insert/update/delete/queryPage/queryList/queryDetail/queryById/count（批量用 batch+动词，全表见 [02](02-naming.md) §2）`；或整句收敛为 `基础设施层动词遵循 [02](02-naming.md) §2 权威表`，消除第二份枚举。| 依据 B（重复条款收敛到单一权威源）。

**F7** | steering/gtsp/09-cr-checklist.md:40、43、45、49、50、60、66、70 | B | 🟠 | 多条【强制】项标注（人工）但实为可机械检查，违背仓内元规则 CLAUDE.md:37「标注强制的条款应同步评估可机械检查性：能查出的配 gauntlet 静态门」。可接线清单（落点沿用 skills/arch-guard|api-guard/scripts + tools/gauntlet.sh:303-309 既有 pytest 层模式，并各配负控制）：① :40 `@FeignClient` 四属性齐全 + 方法路径 `/{version}/{resource}/{action}` → api_check 新增 check_feign_client_attrs（注解参数静态扫描）；② :43 写操作 `@RequestBody` 参数标 `@Valid`/`@Validated` → api_check.check_validation_annotation；③ :45 Controller 方法返回 `ResultMode<T>` 且无 try-catch → api_check/arch_check AST 扫描 adapter.web；④ :49 PO 不实现 Serializable、标 `@TableName`、禁 `@Data` → arch_check.check_po_conventions；⑤ :50 非数据库字段标 `@TableField(exist=false)` → 与④同一 AST 遍历；⑥ :60 禁直接抛 `RuntimeException`/异常须继承 `BaseException` → arch_check.check_exception_throw；⑦ :66 `context-path == spring.application.name` → YAML 解析检查（配置门）；⑧ :70 废弃标记 `@Deprecated` 存在性 → AST 扫描。（:68 为【推荐】不强制接线，如接线可regex `@author`/`@date`。）| 具体动作：逐项在对应 check 脚本实现 + test_*.py 负控制用例 + 09 对应行 `（人工）` 改 `（已接线：<函数名>）`；确不接线的显式保留 `（人工）` 即视为「仅靠人记」的自觉标注。| 依据 B（【强制】条款逐条评估可机械检查性、给出接入 gauntlet/CI 具体方式）、CLAUDE.md:37。

**F8** | steering/gtsp/README.md:37-48 | C | 🔵 | 「编号语义对照」表 9 行内容逐字相同（`无逐编号对应`/`无对应（双侧一致，单源设计）`），信息量为一条事实，展开成 9×4 表违反 DRY，且未来新增维度文件需手工同步第 10 行。| 改前：保留 37-48 整表 → 改后：删除表格，把唯一事实并入 :35 引用块末尾追加一句：`编号 01-09 双侧均无逐编号对应（单源设计，无跨平台编号漂移面）`，全量映射仍指向 [docs/platform-matrix.md](../../../docs/platform-matrix.md)。| 依据 C（DRY/KISS）。

**F9** | steering/gtsp/09-cr-checklist.md:59 | C | 🔵 | 标注词出现第三态 `（下游）`，全清单仅此一次，与既有词表（`（人工）`/`（已接线：…）`）并列却无定义，语义（由下游依赖保证？）不可考。| 改前 `（链路追踪默认配置）（下游）` → 改后 `（链路追踪默认配置）`——该行已注明由 starter 默认配置保证，`（下游）`删除即无信息损失；若想表达"由依赖默认值保证、非本仓检查"，在 09:12 分级说明处统一定义该词表。| 依据 C（术语一致）。

**F10** | steering/gtsp/06-exception.md:33 | C | 🔵 | 「系统标识取服务前缀大写（UA/LS）」——按 01:185 服务统一 `gtsp-` 前缀，其"前缀大写"应为 GTSP，示例 UA/LS 无法由命名规则推导，映射关系（历史遗留标识？）未说明，新服务照抄示例会无所适从。| 在 06:33 补一句映射说明（需规范所有者裁决口径），示例方向：`系统标识取服务前缀大写：存量服务沿用历史标识（UA/LS），gtsp- 新服务取 <规则待定，如固定段 GTSP>`；至少须把「UA/LS 从何而来」写明，消除示例与命名规则的表面矛盾。| 依据 C（术语一致）、B。

**F11** | steering/gtsp/07-config.md:26 ↔ :12 | C | 🔵 | §1 配置文件清单仅列 `bootstrap.yml`、`application.yml`、`application-local.yml`，§3 却引用 `bootstrap-local.yml`（本地密码），清单与正文文件名不一致。| 改 07:12 清单补项：`每个服务包含：bootstrap.yml（…）、application.yml（…）、application-local.yml（本地开发覆盖）、bootstrap-local.yml（本地 Nacos 连接覆盖，不入库）`；或若语义实为同一文件，将 :26 的 `bootstrap-local.yml` 统一为 `application-local.yml`——按 §3 语境（Nacos 账密）建议前者。| 依据 C（一致性）、B。

**F12** | steering/gtsp/09-cr-checklist.md:66 ↔ steering/gtsp/07-config.md:16-19 | B | 🔵 | 07 §2 列 5 项 application.yml 必须项，09:66 门禁仅覆盖其中 2 项（context-path 一致、wlyd.trace.enabled）；`spring.application.name` 显式声明、`server.port`、`allow-bean-definition-overriding: true` 三项未入门禁，且均为 YAML 可机械解析。| 改 09:66：改前 `- [ ]【强制】\`context-path\` 与 \`application.name\` 一致，\`wlyd.trace.enabled: true\`（人工）` → 改后 `- [ ]【强制】application.yml 必须项齐全：\`spring.application.name\` 显式声明、\`context-path\` 与之相等、\`wlyd.trace.enabled: true\`（三项均可 YAML 解析，候选接线）（人工）`；`allow-bean-definition-overriding`/`server.port` 若有意不设门禁，在 07 §2 旁注说明。| 依据 B（门禁覆盖 vs 维度文件必须项）。

**F13** | steering/gtsp/README.md:8、steering/gtsp/01-project-structure.md:142、steering/gtsp/09-cr-checklist.md:16 | C | 🔵 | 同一框架名三种写法：README「COLA DDD 架构」、01:142「Cola Statemachine」、09:16「COLA 6 模块」。| 统一缩写大写：改 01-project-structure.md:142 改前 `Cola Statemachine` → 改后 `COLA Statemachine`。| 依据 C（中英文/标点风格一致）。

---

## 统计

| 严重度 | 数量 | 编号 |
| --- | --- | --- |
| 🔴 必改 | 0 | — |
| 🟠 建议 | 7 | F1、F2、F3、F4、F5、F6、F7 |
| 🔵 可选 | 6 | F8、F9、F10、F11、F12、F13 |

类别分布：A 0 条（审查对象为 steering 文档，A 标准无直接命中；其"不写易腐计数"精神经上报事项 1 关联）；B 7 条（F1、F2、F4、F5、F6、F7、F12）；C 6 条（F3、F8、F9、F10、F11、F13）。

正面核实（无发现项的事实基础）：10 文件全部内部相对链接目标存在（含 `../openapi-standards.md`、`../database-design-specification.md`、`../../docs/platform-matrix.md`、`../../.claude-plugin/plugin.json`、`../../.codex-plugin/plugin.json`，README:35 引用的 plugin.json:10/:8 行号属实）；09 声明的 11 个已接线函数全部实存（arch_check：check_maven_modules/check_dependency_direction/check_naming/check_injection_annotation/check_state_field_leakage/check_state_machine_governance；api_check：check_action_verb/check_mapping_annotation/check_time_annotation/check_del_flag_filter/check_path_variable；check_console_output 在 arch_check），gauntlet 经 pytest 层接线（tools/gauntlet.sh:303-309）；03/04/06 对 openapi-standards 的对齐声明（禁 path 变量 :29、URI 四段式 :19、ISO 8601 时区 :42、错误码下划线风格 :114）逐条核实为真；frontmatter title+scenario 10/10 完整；gtsp 未用 inclusion 字段正确——CONTRIBUTING.md:146 声明 inclusion 为历史遗留字段、新增文件无需写，hooks/load-steering.sh:37-45 亦仅消费 title/scenario（存量 openapi-standards.md:4 的 `inclusion: always` 属文档化遗留而非活机制，本报告不据此对 gtsp 提字段要求）。

## 审查中上报事项

1. **易腐计数漂移（已登记，建议人工 PR 优先处理）**：`.claude-plugin/plugin.json:3` 描述含「11 个审查/工具技能 + 6 项通用设计规范 + GTSP 工程规范」，`.codex-plugin/plugin.json:4` 仅「包含测试、数据库、API、Git 四大规范」——实测 skills/ 下技能目录 13 个（除 _shared）、steering/ 通用规范 9 项，「11 个技能/6 项规范」均为与现状脱节的易腐计数值，违反 CLAUDE.md:33「文档不写易腐数字」总则。README:49 与 docs/platform-matrix.md §4 已登记该描述层漂移「供人工 PR 裁决」，本审查维持只读不动，建议该 PR 一并删除两处 manifest 中的计数表述。
2. **F7 落地体量提示**：8 项可接线清单为一批工程量，建议拆分优先级——②③④（写参数校验、Controller 无 try-catch、PO 约定）命中率最高先做，①⑥⑦⑧ 次之；每项须按 CLAUDE.md:37 配负控制证明检查器会失败，避免只加正例。
3. **F10 需规范所有者定口径**：UA/LS 与 `gtsp-` 前缀的映射关系仓内无据可查，本报告只能给出补说明的建议方向，不能代拟事实。
4. 本审查未修改仓库任何文件、未执行任何 git 写操作；唯一写入为 /tmp/ar-review-4.md。
