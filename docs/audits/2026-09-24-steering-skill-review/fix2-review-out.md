# awesome-rules 第二批修复（C1–C4）独立复审报告

- **对象**：worktree `review-red`（分支 `docs/review-104-fixes`）第二批修复 diff（`/tmp/ar-fix2-diff.txt`，2168 行，含批 1 S1–S7 同基线变更）
- **裁决权威源**：`docs/audits/2026-09-24-steering-skill-review/SUMMARY.md` 第二批裁决节（C1–C4）+ backlog 节
- **方法**：diff 全量通读；仓文件断言全部实读终态核实（22+ 处）；运行验证 6 组；对照批 1 变更抽查误伤
- **日期**：2026-09-25
- **结论**：**无 🔴。两 🟠 均为「记录与执行不一致 / 指针语义丢失」类，修复路径为补齐或明示降范围，非回滚。**

---

## 一、发现清单

### 🔴 必改（0 条）

无。

### 🟠 建议改（2 条）

**🟠-1 C2「全量补标注」执行为子集；OA-3 部分执行且 SUMMARY 执行列未记载 openapi 项**

- 裁决词为「全量补标注」（主题①【强制】机械检查性缺口 ~15 条），但：
  1. **OA-3 三处只执行一处**：ar-review-1 OA-3（🟠）指 openapi-standards :47/:72/:161（现 :46/:71/:160）三处可机械检查条款既未接线也未标注。本批仅 :46 枚举传值加了「仅靠人记：当前无静态门禁；可接线方向为 api-guard 扫描 Schema `enum` 定义 + 负控制」；:71 统一 HTTP 200 与 :160 只增不删两处至今无任何机械检查现状标注（已实读两处原文确认）。
  2. **SUMMARY 执行列与 diff 不一致**：C2 执行列（testing F9 四处 + git-conventions F2/F3 + CRAP≥30 + gtsp F5/F6；F7 其余 7 项 backlog）完全未提 openapi——:46 的标注落地了但记录缺位。
  3. **同主题其余 🟠 项既未执行也未登记**：task-package F4（6 处强制零标注）、review-report F9（3 处）、frontend F11（11 处强制悬空）、code-review/sourcery/skill-evo F-05（6 处）、DB-1 机械部分——SUMMARY backlog 节仅登记 gtsp F7 接线、mcporter 单源化、🔵47 三项，上述各项无去处。按仓纪纪律（审查发现的可操作问题须显式遗留），「全量」与实际子集的差集应补标或明示顺延批次。
- **修复路径**：补齐同主题标注（机械动作，句式已有成熟样例）；或在 SUMMARY 执行列补记 openapi:46 并将剩余项显式登记 backlog。

**🟠-2 C4 CLAUDE.md:30 压缩丢失两处语义，指针目标不承载所指内容**

- 被 compress 的原 :30 含三段语义：(a) 文件所有权隔离（目标文件集无交集）；(b) 子任务检出的**边界外残留由主会话统一收口而非各自扩权**；(c) 拉取远程更新优先选未写盘窗口，**若已写盘须先比对未提交修改与 incoming 改动的文件交集再决定拉取方式**。
- 新 :30：「并行子任务按文件所有权隔离，拉取窗口与已写盘交集判定见 steering/task-package-standards.md §3（单一权威源）」。
- 但 task-package §3:87 实文只有「同仓并行任务按文件所有权隔离（各任务书清单无交集）；需要拉取远程更新时优先选尚未写盘的任务窗口」——
  1. **「已写盘交集判定」在 §3 不存在**：task-package 全文 grep「交集」零命中。指针声称的内容目标节并不承载（指向空洞指针）。
  2. **「边界外残留主会话收口」语义全仓丢失**：§1.3:35 是任务侧「停止写盘、上报、等待重新协商」，L1:70 是 watcher「只记录不拦截」，均非「主会话收口残留、子任务不各自扩权」。
- **修复路径**：DRY 收敛应是「先富化权威源、再压缩引用」——把 (b)(c) 两段补进 §3，指针即成立；或指针收回改内联。

### 🔵 可选（2 条）

**🔵-1 testing F7 的 L274（退出码语义【强制】）括注未加**
F7 建议含 L287 与 L274 两处行尾追加引用；实际只落了 SIGPIPE 行的「机器执行层」命名行（testing:290，指向 check_pipe_early_exit.py + gauntlet 层 lint-pipe-early-exit + NC7，已核实三要素全部实存）。:274-275 退出码语义【强制】管道截断条款仍无机器执行层标注（已实读确认）。核心命名已达成，属补注完整性。

**🔵-2 ddl-manual-rules.md 仍无行尾换行**
本次编辑（第 7 条改「均已脚本化」）沿袭了既有的无行尾换行状态。琐屑，顺手修。

---

## 二、正面核实清单（实读/实跑证实）

### C1 inclusion 死字段清理 — ✅ 全量完成
- 6 文件（cross-repo / git-conventions / openapi / review-report / task-package / testing）frontmatter inclusion 行全部删除；
- 全仓 grep `inclusion`：仅剩 CONTRIBUTING.md:146「已废除（2026-09-24 清理）…禁止新增；存量文件已全部移除」、LICENSE 英文无关词、docs/audits 历史档案——**零残留**；
- CONTRIBUTING 措辞与裁决（「已废除，禁止新增」）一致。

### C2 已执行项 — ✅ 标注语义与门禁事实逐一相符
- **testing F9 四处标注**在位（fixture null / 假绿原则行 / L237 红端验证（含「喂坏输入断言 rc≠0 属可机械执行」的分层）/ Tripwire）；
- **git-conventions F2 标注**属实：commitmsg-check.sh:10 `grep -qE '^(Merge |Revert |Auto-Merged )' && exit 0` 确为 `Merge ` 前缀整体豁免；
- **git-conventions F3 标注**属实：gauntlet.sh:332 `must_not_match "$SECRET_PATTERN" scripts tools hooks skills arch-hawkeye .factory .github` 与标注所列七项目录逐字一致；
- **CRAP≥30「落点=消费仓」标注**属实：grep tools/ 零 CRAP 实现，「本规范仓库与分发链均不承载该门禁实现」声明与事实一致；
- **gtsp F5**（08:16 补【强制】+ 09 清单插项，插位正确）、**F6**（09:26 收敛为 02-naming §2 指针——02-naming §2 权威动词表实存，insert/delete/update/queryPage/queryDetail/queryById/queryList/count/batch 全套在位）；
- **gtsp F7 其余 7 项**已登记 backlog（SUMMARY backlog 节）。

### C3 跨文档矛盾消除 — ✅ 七项全部落地
- **F1**：gtsp README:19 规范表值「类后缀/方法/注入/常量类」与 02-naming.md:3 scenario **逐字一致**；
- **F2**：01-project-structure :64 与 :173 两棵包结构树均已补 `enum`（:64 系主动一致性补齐，SUMMARY 已披露）；
- **F4**：07-config Supabase 专有表述已替换为 Spring 生态通用词；
- **F5/F6**：同 C2；
- **FZ-1**：api-contract-freeze 信封键 data→model 并指向 openapi §4——openapi §4「统一响应体」实存且信封键确为 `model`（:56/:81/:93 三例）；
- **review-report F8**：四级色板句「impact-guard 的 🔴直接/🟠间接为影响方式分级」与 impact-guard SKILL.md:100-101（🔴 直接/🟠 间接抵达）语义一致，引用不悬空。

### C3 del_flag 口径 A + 机械化 — ✅ 质量良好
- steering 三处收敛：:43 豁免行含 del_flag、:70【强制】业务表必含、:133 自检清单，与实现口径一致；
- `check_del_flag_required` 与既有「必含字段缺失」豁免共用 `_is_log_table`（表名含 `_log/_flow/_journal` 子串，:119-125）——豁免口径单一来源，无第二实现；
- 别名集 `{"del_flag","delete_flag","is_deleted","is_del","deleted"}` 与 SUMMARY 声明逐字一致；既有命名规则 `check_del_flag` 的别名集本批未动（纯增量，无夹带行为变更）；单测 docstring 明示「命名统一由 del_flag 命名规则另行约束」，语义诚实；
- 单测 4 例构造有效：helper `_ddl_with_field` 基表 `t_demo`（非日志形态）、五必含字段齐全、注释合规——负控制单变量成立；
- ddl-manual-rules 第 7 条同步「均已脚本化」。

### C4 DRY 收敛（除 🟠-2 外）— ✅ 其余项全部有效
- CLAUDE.md:31 herdr 模板补 `< /dev/null`，与 task-package §3:86 权威模板一致；
- testing F4 指针目标「变异测试纪律」节实存（:211）；F6 指针目标「负控制【强制】」实存；
- testing F5 指针文案内嵌计数「四条细则」**与实数相符**（:237/:239/:240/:241 恰四条 bullet，无易腐错误）；
- review-report F7：:29 收敛为基线声明 + 指向 :34「现状类指控」条（git show/git log 核实细则与配置缺失、DDL 重复建表示例俱在）；全文「事实类」**零残留**。

### 批 1（S1–S7）误伤抽查 — ✅ 未见损伤
CLAUDE.md:19 门禁留名约定、S3 单一权威源声明、S5 api-guard 收窄、S6/S7 计数修正等批 1 变更在 diff 中原样存续，批 2 编辑未触及。

### 门禁与回归 — ✅ 全绿
| 验证 | 命令 | 结果 |
|---|---|---|
| badcase 075 红控制 | `python3 skills/ddl-guard/scripts/ddl_check.py …/075-atomic-del-flag-required/input/example.sql` | 唯一检出「逻辑删除字段缺失」，rc=1，与 expected.md 一致 |
| ddl-guard 全量单测 | `python3 -m pytest skills/ddl-guard/scripts/tests/ -q -p no:cacheprovider` | **181 passed，覆盖率 96.15%**——与 SUMMARY 声明逐字相符 |
| badcase 存量回归 | `python3 scripts/badcase_runner.py --skill ddl-guard` | **72/72 通过**——新规则零波及存量 |
| frontmatter 门禁 | `python3 tools/check_frontmatter_manifests.py .` | OK（steering 19 + skills 13） |
| 文档保鲜门禁 | `python3 tools/check_doc_freshness.py .` | 0 项漂移 / 0 INFO / 0 豁免 |
| 只读纪律 | `git status --porcelain` | 41 行变更全为被审 diff 自身（A/M/D），复审零污染 |

---

## 三、统计

| 级别 | 数量 | 条目 |
|---|---|---|
| 🔴 必改 | 0 | — |
| 🟠 建议改 | 2 | C2 全量口径 vs 执行子集 + OA-3 部分执行/记录缺位；C4 CLAUDE.md:30 压缩丢两处语义（指针空洞） |
| 🔵 可选 | 2 | testing F7 L274 括注未补；ddl-manual-rules.md 行尾换行 |
| **合计** | **4** | |

复审覆盖：C1–C4 四簇全部裁决项逐条对照 + 批 1 抽查 + 6 组运行验证。两条 🟠 均不阻塞合并，但按仓纪「审查发现的可操作问题须显式遗留」应在交付说明中列明。
