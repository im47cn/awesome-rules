# 维度 D · 门禁覆盖度（gate-coverage）

- 审计对象：`/tmp/ar-audit`（awesome-rules worktree），基线 `HEAD = 135b829`（= `origin/main`，含 PR #203 两层重用 + PR #206 覆盖率预算），工作树干净（`git status --short` 空）。
- 审计问题：每一条【强制】条款与现存机械门禁（脚本 / lefthook 钩子 / CI 工作流 / gauntlet 层）之间的映射是否完整；反向：是否存在"有门禁、无条款"或"有条款、门禁缺位"的漂移。
- 方法：程序化枚举全部【强制】标记行 → 逐条分类 已接线 / 部分接线 / 未接线（附门禁 file:line 证据）→ 反向清点门禁清单找文档漂移 → 按风险排序未接线项。

---

## 0. 本仓现存机械门禁全景（证据锚点）

| 门禁 | 载体 | 触发 | 证据 |
|---|---|---|---|
| commitlint | `tools/git/lefthook/commitmsg-check.sh` | commit-msg | lefthook.yml:11–14 |
| coverage-light | pre-commit 钩子 | commit | lefthook.yml:19–20 |
| spec-check（spec↔test 反向矩阵） | `tools/git/lefthook/spec-check.sh` → `tools/spec_check.py` | commit（仅 spec 工作流文档） | lefthook.yml:22–23 |
| pre-push-delete-guard（fail-open 边界守卫） | `tools/git/lefthook/pre-push-delete-guard.sh` | push | lefthook.yml:41 起；语义记载 steering/git-conventions.md:165 |
| tests（8 套 pytest + badcase + lease-sql 并行；串行尾部 plugin_lock/doc_freshness/shellcheck） | `scripts/run_tests.sh` | push | lefthook.yml:41–44；run_tests.sh:108–131 |
| coverage-full / sourcery-gate(固定 1.45.0) / mutation-gate / coderabbit-gate | lefthook + 工作流 | push / PR | lefthook.yml:45–62；.github/workflows/sourcery-review-gate.yml |
| gauntlet 全量门 | `tools/gauntlet.sh` | PR / push main / 每周 | .github/workflows/config-evals-gate.yml；自测层 gauntlet.sh:192–196，plugin-versions:220，doc-freshness:222，frontmatter:225，md-link:226，diff-cover:231–232，must-not-secrets:234–239，syntax/lint:241–247，factory 层（syntax-factory-sh:261 … git-sealing:310） |
| badcase 回归 + 空语料防假绿 + replay-dry-run | `scripts/badcase_runner.py --strict-exact` | 同上 | config-evals-gate.yml:89–94, 100–136 |
| 文档模板可构建 | doc-gen-build.yml（cola-sample fixture） | PR | .github/workflows/doc-gen-build.yml |
| 检查器负控制（证明检查器会失败） | `tools/test_gauntlet_checks.sh`（NC*）等 5 个自测 | gauntlet 首层 | gauntlet.sh:192–196 |
| guard 技能脚本（分发资产，非本仓 CI） | ddl_check.py（19 检查函数）/ sql_check.py（16 规则 + 4 PO 检查）/ api_check.py（5 检查函数）/ arch_check.py | 下游调用 | skills/ddl-guard/scripts/ddl_check.py:453–955 等，见矩阵 |

---

## 1. 条款→门禁分类矩阵（M001–M121 + 扩展集）

枚举命令（见 §覆盖声明）产出 121 个标记行；其中 **6 行为非条款**：M007/M019/M036/M075 为各规范序言（"条款分【强制】/【推荐】…"式元描述），M106/M107 为 README 表格描述性提及。实际条款行 **115**（多数为条款组标题，组内含多条子款）。

状态图例：✅ 已接线（仓内存在门禁伪影）｜🟡 部分接线｜❌ 未接线（下游/人工设计如此，或漂移——逐条注明）。

### steering/task-package-standards.md（M001–M006）
| 条款 | 状态 | 门禁证据 |
|---|---|---|
| M001 目标+反目标 / M002 双层验收 | 🟡 | L1 watcher 落地：`tools/dispatch_watch.sh`（存在）+ gauntlet 自测 gauntlet.sh:196 + 负控制 NC19e（tools/test_dispatch_watch.sh:68–91）；L2 模板 templates/reviewer-battery.md.template；L3 复跑人工 |
| M003 升级触发器 / M004 enforcement 分级 / M005 复用两层判定 | ❌ | 流程条款，无伪影（M005 即 PR #203 引入的两层判定本身，无脚本） |
| M006 三层守护 | 🟡 | 同 M001–M002 组合 |

### steering/frontend-standards.md（M007 序言；M008–M018）
M008–M018（mock 开关/.env.local/契约同构/宽容解析/路由下发/axios 工厂/合并落新对象/点击复制/真实锚点/门控 lint/本地冒烟）全部 ❌ **未接线——下游 Vue3 工程条款，本仓无前端工程与脚本**。文件内仅 2 处散文提及"脚本"，无门禁伪影。

### steering/api-contract-freeze-standards.md（M019 序言；M020–M022）
M020（未冻结字段禁实现）/M021（四步）/M022（先冻结再实现）❌ 未接线——下游协作时序条款，无伪影。相关资产仅 skills/contract-guard（check-contract.sh 仅提示不阻断，见 M071）。

### steering/testing-standards.md（M023–M034）
| 条款 | 状态 | 门禁证据 |
|---|---|---|
| M023 覆盖率（L21） | ✅ | coverage-light（lefthook.yml:19–20）+ coverage-full（:45–48）+ gauntlet diff-cover:231–232（90% vs origin/main）；规范 L114 明示 Java/JaCoCo 面向下游、本仓非 Java |
| M024 四形态决策 / M025 度量纪律 / M026 质量门禁（CRAP 等） | ❌ | 下游测试治理条款，无伪影 |
| M027 null-fixture 禁令（L140） | ❌ | 人工审查纪律，无伪影 |
| M028 工具链假绿形态（L184） | ❌ | 人工；仓内近亲防线是 config-evals-gate.yml:89–94 空语料防假绿（仅护评测语料自身） |
| M029 负控制（L220） | ✅ | `tools/test_gauntlet_checks.sh`（NC* 系列）+ gauntlet checker-self-test:193——规范条款直接命名自身门禁 |
| M030 测试密封性（L227） | ✅ | `tools/check_git_sealing.py` + gauntlet git-sealing:310 + ADR-010（.factory/decisions.md:293 制度化） |
| M031 killpg 平台语义（L233） | ✅ | `tools/check_killpg_strict.py` + gauntlet lint-killpg-strict:277 |
| M032 tempdir 隔离（L243） | ✅ | `tools/check_tempdir_usage.py` + gauntlet lint-tempdir-isolation:284 |
| M033 tripwire（L252） | ❌ | 人工纪律 |
| M034 退出码语义（L257） | 🟡 | `tools/check_pipe_early_exit.py`（gauntlet lint-pipe-early-exit:272）仅覆盖管道截断子集 |

### steering/openapi-standards.md（M035）
M035 枚举传值（:47）❌ 未接线。**api-guard SKILL.md:8 明确将 Open API 规范排除在脚本范围外**，且 openapi 规范没有对应 *-manual-rules.md 记账谁人工兜底——见发现 D-11。

### steering/gtsp/09-cr-checklist.md（M036 序言；M037–M070，34 条）
| 条款 | 状态 | 门禁证据 |
|---|---|---|
| M037 完整档 COLA 6 模块 / M038 轻量档 / M040 依赖方向 | ✅（分发资产） | skills/arch-guard/scripts/arch_check.py（pom/模块结构/依赖方向检查，随 SKILL 分发，非本仓 CI） |
| M041 Controller 不直调 Mapper | 🟡 | arch-guard 仅导入层检查（SKILL.md 一级检查），非调用链 |
| M052 action 动词统一 | ✅（分发资产） | api_check.py `check_action_verb`:207 |
| M059 PO 无日期注解 / DTO @JsonFormat | 🟡 | api_check.py `check_time_annotation`:368 拦 shape=NUMBER；pattern 缺失人工（api-manual-rules.md:18 自认） |
| 其余 ~28 条（M039, M042–M051, M053–M058, M060–M070：Feign 四属性、@Valid、@PostMapping/@RequestMapping、ResultMode、PO Serializable/@TableField、Mapper XML namespace/del_flag、@Resource/@Autowired、@Slf4j/System.out、traceId、异常体系、context-path、父 POM、@Deprecated…） | ❌ | 下游 CR 人工清单条款，本仓无伪影。其中 M046/M055/M062/M061 为纯文本模式可低成本接线（见 §3） |

### steering/cross-repo-contract-standards.md（M071）
M071 门禁自检（:109）🟡：下游实现资产 skills/contract-guard/templates/yunxiao-pipeline-contract.yaml:46–50（对比对象 A≠B，awk 自比自即 fail）；本仓 check-contract.sh 仅提示不阻断（SKILL.md 自述）。

### steering/review-report-standards.md（M072–M074）
三方对账 / 五段式 / 证据边界 ❌ 未接线——报告格式条款，天然人工。

### steering/database-design-specification.md（M075 序言；M076–M104，29 条）
| 条款 | 状态 | 门禁证据（skills/ddl-guard/scripts/） |
|---|---|---|
| M076 .sql 扩展名 | ✅ | ddl_check.py:1072 `f.endswith(".sql")` |
| M077 只保留关键语句与必要注释 | 🟡 | 注释侧 check_comment_style:513；"内容精简"人工 |
| M078 去除 CHARACTER SET 等子句 | ✅ | check_forbidden_clauses:453 |
| M079 InnoDB/utf8mb4/排序规则 | （待验证） | 未见解显式 ENGINE/charset 校验函数；或经 M078 去子句间接保证——见 §待验证 |
| M080 禁分区表 | ✅ | check_partition:539 |
| M081 表注释 ≤64 | ✅ | check_table_comment:614 |
| M082 表名格式 | ✅ | check_table_name:566 |
| M083 表名英文禁拼音 | ❌ 人工 | ddl-manual-rules.md:5–14（明示脚本不可查） |
| M084 字段名格式 | ✅ | check_field_name:671 |
| M085/M086/M087 字段语义命名/属性级别/泛化词·方人 | ❌ 人工 | ddl-manual-rules.md:9–12 |
| M088 禁用类型（LOB/TEXT/JSON/enum/set…） | ✅ | check_field_type:765 |
| M089 禁存图片/二进制静态资源 | ❌ 人工 | 语义判断（类型禁用仅覆盖载体类型） |
| M090 新字段追加末尾 / 修改字段约束 | 🟡 | 修改字段 check_change_column:553；"追加在末尾"需 diff 上下文，人工 |
| M091 字段数 ≤40 | ✅ | check_field_count:661 |
| M092/M093 字段注释存在性/格式 | ✅ | check_field_comment:727 + check_comment_style:513 |
| M094/M096 索引命名 uk_/ix_、唯一索引不重复建联合 | ✅ | check_index_naming:831 / check_unique_hint:865 / check_index_on_id:881 / check_index_count:903 |
| M095 索引有效性 EXPLAIN | ❌ 人工 | ddl-manual-rules.md:42–46（明示需运行时验证） |
| M097 禁外键/触发器/存储过程 | 🟡 | 外键 check_foreign_key:928 ✅；**触发器/存储过程被明示放弃检出**（ddl-manual-rules.md:34 "脚本只解析 CREATE TABLE…不会被检出"）——发现 D-02 |
| M098 SQL 压测 | ❌ 人工 | sql-manual-rules.md:20–25 |
| M099 禁 SELECT * | ✅ | sql_check.py check_select_star:210 |
| M100 count(*)/count(1) | ✅ | check_count_field:221 |
| M101 多表关联字段带前缀 | ✅ | check_table_alias_prefix:259（前缀存在性；指向正确表人工，sql-manual-rules.md:10） |
| M102 必带 WHERE / 禁 1=1 | ✅ | check_where_required:231 + check_invalid_where:247 |
| M103 INSERT 列字段列表 | ✅ | check_insert_columns:420 |
| M104 应用内禁 DDL | ✅ | check_ddl_in_app:429 |

### CLAUDE.md / README.md（M105–M107）
- M105（:45 "标注【强制】的条款不可违反"）：🟡 元条款，由整套门禁系统承载；规范索引由 hooks/load-steering.sh 自动生成。
- M106/M107：README:62/68 表格描述性提及，非条款（见 D-12）。

### skills/（M108–M121）
| 条款 | 状态 | 门禁证据 |
|---|---|---|
| M108 skills/README.md:7 不得静态复制可动态获取的内容 | 🟡 | doc-freshness 仅覆盖 2 起既往事件（check_doc_freshness.py 头部 R5），非通用条款执行 |
| M109/M110 skill-evo：new_text 含【强制】→护栏；既有【强制】不可削弱 | ✅ | evo_proposal.py:23 `_MANDATORY_MARK`、:91–92 命中告警；测试 skills/skill-evo/scripts/tests/test_proposal.py:384,388 |
| M111–M114 api-manual-rules（响应体/参数/业务/安全） | ❌ 人工（记账显式） | 文件标题即"API 脚本无法检查的规则"；M112 时间格式部分脚本化（shape=NUMBER，api_check.py:368；pattern 人工，:18 自认） |
| M115/M116 ddl-manual（命名语义/注释质量） | ❌ 人工（记账显式） | 即 M083/M085–M087 的人工面 |
| M117 禁用语句（触发器/存储过程/视图） | ❌ 人工（记账显式） | ddl-manual-rules.md:32–40；与 D-02 相关 |
| M118 需运行时验证（EXPLAIN） | ❌ 人工（记账显式） | 即 M095 |
| M119–M121 sql-manual（NULL 语义/压测/PO 类） | ❌ 人工（记账显式）；PO 已脚本化子集 ✅ check_po_table_name:672 / check_po_field_names:703 / check_po_required_fields:744 | sql-manual-rules.md:29 自述脚本覆盖面 |

### 扩展集（规范三件套之外的【强制】）
- E-01/E-02 templates/reviewer-battery.md.template:4–5（组合规则≥3 维且含 RANGE/SECURITY；盲测纪律）：❌ 派发纪律条款，天然人工。
- E-03 skills/contract-guard/templates/yunxiao-pipeline-contract.yaml:46 门禁自检【强制】：M071 的下游流水线实现（分发资产）。
- 非条款提及：AGENTS.md:24 与 hooks/load-steering.sh:88（总则句**双份硬编码**，见 D-09）、CONTRIBUTING.md:109（分级规则说明）、docs/design/skill-evo-design.md:48/51、docs/design/skill-evo-replay-eval.md:95、scripts/ablate/results/*.log（实验数据）。

**汇总**：115 条款行中 ✅ 29（7 条由本仓 CI 门禁直接承载：testing 5 + skill-evo 2；22 条为 guard 分发资产）、🟡 12（含 M105 元条款）、❌ 74（绝大多数为下游/人工**设计如此**且多数经 *-manual-rules.md 显式记账；仓内自身可接线而未接线的集中在 D-02/D-10/D-11）。

---

## 2. 发现

| 编号 | 位置 | 级别 | 问题 | 证据摘录 | 复现命令 | 建议 |
|---|---|---|---|---|---|---|
| D-01 | lefthook.yml:19–23 vs CONTRIBUTING.md:32–35 | 🟠 | pre-commit 两道门禁（coverage-light、spec-check）在任何钩子文档中缺位：CONTRIBUTING 只记载 commit-msg 与 pre-push；git-conventions.md 通篇无 "pre-commit"；两门的唯一记载是 lefthook.yml 注释 | CONTRIBUTING：`- **commit-msg**：commitlint 校验…` `- **pre-push**：全量测试…`（无 pre-commit 条目） | `rg -n 'pre-commit' CONTRIBUTING.md steering/git-conventions.md`（0 命中）对照 `sed -n '19,23p' lefthook.yml` | CONTRIBUTING 钩子清单补 pre-commit 两条目，或在 git-conventions 增加 pre-push 之外的钩子段 |
| D-02 | skills/ddl-guard/ddl-manual-rules.md:34,38–39 | 🟠 | 【强制】禁用语句（CREATE TRIGGER / CREATE PROCEDURE）被 ddl_check.py 明示放弃检出——一行大小写不敏感 grep 即可拦截的强制条款，在千余行解析器（ddl_check.py ≥1072 行）已存在的前提下留给人工，违反 CLAUDE.md:36 自身元规则（"能查出的配 gauntlet 静态门"） | `脚本只解析 CREATE TABLE，以下语句类型不会被检出` | `rg -ni 'create\s+(trigger\|procedure)' skills/ddl-guard/scripts/ddl_check.py`（0 命中）；`sed -n '34,39p' skills/ddl-guard/ddl-manual-rules.md` | ddl_check.py 增加全文级 `CREATE TRIGGER/PROCEDURE` 扫描（不需解析 AST），并按 M029 惯例在 test_*.py 加负控制 |
| D-03 | CLAUDE.md:36≡39 | 🟡 | 条款逐字重复两遍（"标注强制的条款应同步评估可机械检查性…"） | 两行内容完全一致 | `rg -n '标注强制的条款应同步评估可机械检查性' CLAUDE.md` → 36,39 | 删除其一 |
| D-04 | CLAUDE.md:38≡41 | 🟡 | 条款逐字重复两遍（"工厂链运行期间…不得修改 .factory/…"） | 两行内容完全一致 | `rg -n '工厂链运行期间' CLAUDE.md` → 38,41 | 删除其一 |
| D-05 | steering/openapi-standards.md:154≡155 | 🟡 | 幂等键口径行逐字重复 | `幂等键口径因事件/接口而异时…` ×2 | `sed -n '153,156p' steering/openapi-standards.md` | 删除其一 |
| D-06 | tools/gauntlet.sh:234–239（must-not-secrets） | 🟡 | 反向漂移：门禁存在、规范沉默——全 steering/CLAUDE/README 无任何条款要求"仓内禁提交凭据"，SECRET_PATTERN 仅活在 must_not_match.sh 注释里 | `SECRET_PATTERN='((api[_-]?key\|s[e]cret\|…)` | `rg -n '密钥\|SECRET\|secret' steering/*.md CLAUDE.md README.md`（仅脱敏/枚举表/泛化词示例，无凭据禁令条款） | 在 git-conventions 或 testing-standards 增补一条【强制】凭据禁令条款并标注已接线门禁 |
| D-07 | tools/check_doc_freshness.py（规则 R8） | 🟡 | doc-freshness 的同步防线对的是分发副本（tools/git/README.md ↔ tools/git/lefthook.yml），根 lefthook.yml ↔ CONTRIBUTING 钩子清单（D-01 的漂移面）无任何同步检查 | R8 头部注释（check_doc_freshness.py:1–66） | `sed -n '1,66p' tools/check_doc_freshness.py \| rg -n 'R8\|lefthook'` | 增加 R10：CONTRIBUTING 钩子段须包含 lefthook.yml 中启用的全部钩子名 |
| D-08 | tools/git/lefthook/spec-check.sh:5–10 + 全仓 spec: 标签 | 🟡 | spec-check 前置门近休眠：门禁为 opt-in（仅当暂存文件名含 "spec" 且内容含 spec:<ID> 才核对），而全仓 .md 只有 1 个文件使用 spec: 标签——115 条【强制】条款零条享受条款↔测试反向核对矩阵，追溯设施闲置 | 判定语义：`文件名含 spec 子串且内容含…spec:<ID> 字面量` | `rg -l 'spec:[A-Za-z0-9][A-Za-z0-9_-]*-[0-9]+' -g '*.md'` → 仅 docs/design/skill-evo-replay-eval.md | 要么为核心规范（testing-standards 等）启用 spec: 条款标签接入该矩阵，要么在 README 明示该门为下游/专用工作流设施 |
| D-09 | hooks/load-steering.sh:88 vs AGENTS.md:24 | 🟡 | 总则句（"标注【强制】的条款不可违反…"）在钩子生成的 Python 字符串里硬编码第二份副本，与 AGENTS.md 原文双轨，改动任一侧即漂移 | 两处文本一致 | `rg -n '标注【强制】的条款不可违反' AGENTS.md hooks/load-steering.sh` | load-steering 生成逻辑改为引用/抽取 AGENTS.md 原句，或加 doc-freshness 规则锁定两份一致 |
| D-10 | steering/gtsp/09-cr-checklist.md:16–70 | 🟠 | 全仓最大强制条款群（35 个标记行 = 34 条款 + 1 行序言）无任何逐条机械可检查性标注：CLAUDE.md:36 元规则要求"标注强制的条款应同步评估可机械检查性"，但 09-cr-checklist 无 脚本名/人工/下游 三态标注；其中 M046（@Resource 非 @Autowired）、M055（@PostMapping 非 @RequestMapping(method=)）、M062（@Slf4j 非 System.out）、M061（查询带 del_flag=0）均为纯文本模式，arch/api/sql guard 已有同类先例可低成本接线 | 清单全部为 `- [ ]【强制】…` 复选框，无任何门禁引用 | `rg -c '【强制】' steering/gtsp/09-cr-checklist.md` → 35；`rg -n 'check\|脚本\|gate' steering/gtsp/09-cr-checklist.md`（0 命中） | 按 api/ddl 的 manual-rules 模式为 09-cr-checklist 逐条标注三态；先接 4 条纯文本模式项 |
| D-11 | steering/openapi-standards.md:47 + skills/api-guard/SKILL.md:8 | 🟠 | openapi 规范全文唯一【强制】条款（枚举传值）处于"规范强制、门禁无人认领"状态：api-guard 明确排除 Open API 规范范围，且无 openapi-manual-rules.md 记账人工兜底——与 ddl/sql/api 三处 manual-rules 显式记账惯例不一致 | SKILL.md:8 排除声明 | `rg -c '【强制】' steering/openapi-standards.md` → 1；`rg -n 'Open API\|openapi' skills/api-guard/SKILL.md` | 二选一：api_check.py 增加枚举字段示例值校验（OpenAPI 文档可解析），或建 openapi-manual-rules.md 显式记账为人工 |
| D-12 | README.md:62,68 | 🟡 | README 表格行的描述文本携带【强制】字样（非条款），使全仓【强制】扫描产生噪声命中，枚举对账需人工剔除（本次 121 行中剔 6 行） | `\| [数据库设计规范](steering/…) \| MySQL DDL/DML 设计标准…【强制】…` | `rg -n '【强制】' README.md` | 表格描述改用"强制级条款"等措辞，避开标记字面量 |

---

## 3. 未接线条款风险排序与最小接线建议

按"本仓自身适用 + 接线成本"排序：

1. **D-02**（M097 触发器/存储过程）：guard 已在分发、一条 grep + 负控制即可闭环——成本最低、收益直接。
2. **D-11**（M035 枚举传值）：规范属于本仓资产且仅此一条强制条款，最小动作是补 manual-rules 记账（零代码）。
3. **D-10 四条纯文本模式**（M046/M055/M062/M061）：arch/api guard 增加正则检查 + 负控制，复用现有分发管道。
4. **D-01/D-07**（pre-commit 门禁文档缺位 + 无同步防线）：补 CONTRIBUTING 段落 + doc-freshness R10。
5. **M108 通用化**：doc-freshness R5 从"2 起既往事件"泛化为"静态复制检测"通用规则（如比对 skills/README 与生成源的重叠度）。
6. **D-08**（spec-check 闲置）：为 testing-standards 的已接线条款（M029–M032）补 spec: 标签示范，激活条款↔测试矩阵。
7. M027（null-fixture）/M033（tripwire）/M028（假绿形态）：测试纪律条款，可用负控制样例文件部分机械化，优先级最低。
8. 其余 ❌ 项（frontend M008–M018、契约冻结 M020–M022、GTSP 其余、审查报告 M072–M074、manual-rules 各节）：下游/人工**设计如此**且多数显式记账——不构成缺陷，维持现状。

---

## 待验证

（无 grep 证据支撑、不计为正式发现的项目）

1. **M079（InnoDB/utf8mb4/排序规则）**：ddl_check.py 未见显式 ENGINE/charset 校验函数（`rg -n 'InnoDB\|utf8mb4\|ENGINE' skills/ddl-guard/scripts/ddl_check.py` 需人工确认）；若确无，则该【强制】依赖 M078 去子句后的库级默认值，属隐式未接线。
2. **三个 CI 工作流的规范面记载**：sourcery-review-gate / config-evals-gate / doc-gen-build 是否有条款级记载（README:112 链接的 docs/design/skill-manifest-gate.md 未逐字核对是否覆盖全部三层 CI）。
3. **owner_check.py / release_guard.py**：存在于 scripts/ 但不进任何门禁（release_guard 仅 `npm run release` 手动触发）；是否有文档记载其定位未核对。
4. **门禁参数的规范出处**：sourcery 版本固定 1.45.0、diff-cover 90% 阈值、coverage 预算（PR #206）等数值的条款级出处未逐字核对（git-conventions.md:165 仅记载触发边界）。

---

## 上报事项

1. **元规则执行落差**：CLAUDE.md:36 要求每条强制条款同步评估机械可检查性，但该评估结果未落盘为任何标注（除 testing-standards M029–M032 与 guard 的 manual-rules 外）。建议在规范总则要求"条款标注三态：已接线(脚本名)/人工记账/下游"。
2. **【强制】标记扩散**：标记已扩散至 templates/、docs/design/、hooks/、AGENTS.md、CONTRIBUTING.md、ablate 实验日志（数据非规范）及 skills/ 内 13 处 .py 实现串（检查器报告格式串/提示词/测试 fixture，见覆盖声明）。建议总则定义合法载体清单，否则任何全仓强制条款审计都要做人工剔噪（本次剔 6+8 行；.py 实现串另由枚举范围豁免）。
3. **规范 vs 实现冲突（按原样报告）**：database-design-specification M097 宣称禁外键/触发器/存储过程三件事同一强度，实现只拦外键（check_foreign_key:928）；manual-rules 的记账文件把"脚本只解析 CREATE TABLE"作为既成事实陈述，而非与规范对齐的声明。

---

## 覆盖声明

**枚举范围**（证明穷尽，非抽样）：

```
rg -n '【强制】' steering/ CLAUDE.md README.md skills/README.md skills/*/SKILL.md \
  skills/api-guard/api-manual-rules.md skills/ddl-guard/ddl-manual-rules.md \
  skills/ddl-guard/sql-manual-rules.md --no-heading \
  | awk '{printf "M%03d %s\n", NR, $0}'
# → 121 行（M001–M121），基线 135b829，本文 §1 矩阵逐行分类
```

**负面空间验证**（枚举边界之外无遗漏）：

```
rg -l '【强制】' --no-ignore -g '!steering/**' -g '!CLAUDE.md' -g '!README.md' \
  -g '!skills/**' -g '!.git/**'
# → AGENTS.md, CONTRIBUTING.md, docs/design/skill-evo-design.md,
#   docs/design/skill-evo-replay-eval.md, hooks/load-steering.sh,
#   scripts/ablate/results/*（数据）, templates/reviewer-battery.md.template
#   → 已全部纳入 §1 扩展集/非条款提及
```

12 个 skills/*/SKILL.md 中仅 skill-evo 含【强制】（M109/M110）；其余 11 个经同一 rg 命令验证为 0 命中。

**skills/ 内非 .md 载体**（枚举范围外，非条款）：`rg -n '【强制】' skills -g '!*.md'` → 13 处 .py 命中：evo_proposal.py:23 `_MANDATORY_MARK = "【强制】"` 定义及 :7/:706 文档串；ddl_check.py:1014、sql_check.py:828、api_check.py:432 报告格式串；evo_prompt.py:150、evo_replay.py:49、evo_evolve.py:53 提示词串；test_proposal.py:384,388、test_prompt.py:61、test_api_check.py:429 测试 fixture/断言——均为标记字符串的实现用法，非条款；另 yunxiao-pipeline-contract.yaml:46 已记为扩展集 E-03。

**门禁清单来源**（§0 全景的证据命令）：`sed -n '1,70p' lefthook.yml`；`sed -n '190,310p' tools/gauntlet.sh`；`sed -n '1,140p' scripts/run_tests.sh`；三个 .github/workflows/*.yml 全文；`rg -n 'def check_' skills/ddl-guard/scripts/{ddl_check,sql_check}.py skills/api-guard/scripts/api_check.py`；`ls skills/arch-guard/scripts/`。

**分类口径**：✅ 要求仓内存在门禁伪影（脚本/工作流/钩子/gauntlet 层）并给出 file:line；guard 技能脚本视为"分发资产"单列（它们不在本仓 CI 中运行，下游才生效）；面向下游、本仓无伪影的条款记 ❌ 并注明"设计如此"，不判豁免。

**基线一致性**：审计期间 `git -C /tmp/ar-audit status --short` 恒为空；唯一写入文件为本报告。
