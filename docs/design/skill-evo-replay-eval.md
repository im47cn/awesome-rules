# skill-evo replay-eval 设计文档

> **状态**：已实现（2026-09-01 落地主体；2026-09-03 收尾核对）· 基于 GEPA 引擎（`scripts/evo_gepa.py`）零改动复用
> **落地范围**：`evo_replay.py` + 单测 46 项（`tests/test_replay.py`，LLM 全 mock）+
> `evo.py` CLI 接线（`evolve --skill/--eval/--dry-run/--budget/--seed`）+ 评估集语料
> `eval/007-clean`（放行型）/`eval/008-real`（混合型，含 1 条人工补充规则）+
> 门禁 `control_gate`（全盘拒绝控制候选）+ `split_eval` 分层切分 + badcase 语料
> 扩充至 71 例（设计时 6 例）——replay 评估集共 73 cases
> **剩余项**：无（2026-09-03 收尾：badcase_runner strict 空放行型修正已落地 §3.2、
> CI `replay-dry-run` 哨兵已接线 §5.3、带 LLM `--budget 16` 端到端已跑通 §7.4、
> §7.6/§7.7 缺口测试已补；引擎阈值未产出提案的分歧见 §7.4 注）
> **范围**：高频重复任务 → 确定性打分评估集 → GEPA 进化信号源（对标 SkillOpt-Sleep 的 replay 机制）
> **参考**：[GEPA arXiv 2507.19457](https://arxiv.org/abs/2507.19457)、
> [Microsoft/SkillOpt](https://github.com/microsoft/SkillOpt)（sleep 阶段 replay 打分）、
> 仓库现有 `scripts/badcase_runner.py`（缺陷注入对账设施）· **日期**：2026-09-01

---

## 1. 背景与动机

skill-evo 已内置 GEPA 同族进化引擎（`evo_gepa.py`，stdlib 复刻 arXiv 2507.19457），
首个应用 `evo_evolve.py` 进化自身 SYSTEM_PROMPT，其信号源是 applied/rejected 提案
（人工审核结果即标签）。但该信号**依赖提案积累**，且 judge 是 LLM（成本 + 噪声）。

微软 SkillOpt 的对照结论（已交付，勿重复）指出唯一实质差距：**缺可自动打分的信号源**。
SkillOpt-Sleep 用 replay 机制——把历史 benchmark 输入重放给候选 skill，用确定性
benchmark 打分。本设计的对应物更优：仓库**已有**缺陷注入对账设施
（`scripts/badcase_runner.py`：input/ + expected.md 双通道比对，missing/unexpected
逐项梯度），且 ddl-guard 已有 6 个真实坏例语料 + 真实 DDL 样例。链路把它接到
GEPA 引擎上，让进化候选有客观、零 LLM、可复现的分数。

核心决策（已与用户确认）：
1. **进化目标**：`skills/<name>/SKILL.md` 的指令性正文（validate 约束保留 frontmatter 契约）
2. **主信号 = 缺陷注入对账**：评估集以「注入已知缺陷的 case」为主——预埋问题 →
   expected = 必须检出的缺陷清单 → score = 检出率 + 放行率（precision+recall），
   逐项天然有梯度；结构检查（五段式/verified/file:line）只作次级项（产物可解析前置），
   不作主分数（防 GEPA 变异 gaming 格式，Goodhart）
3. **打分器即宪法**：打分器比被进化的 SKILL.md 更不可变，改动只走人工；
   **绝不让 GEPA 进化打分器本身**（闭环会塌成自我粉饰）；打分器注册表仅允许
   仓库内确定性脚本（路径逃逸校验复用 `evo_proposal.validate_target` 模式）
5. **评估集选型判据 = 进化梯度，非脚本覆盖**：case 的 expected 必须区分「脚本转述型」
   （001-004：规则全在脚本里，LLM 只需复述脚本输出 → dry-run 基线 F1=1.0 饱和，
   无进化梯度，仅回归价值）与「人工判断型」（005/006：拼音/语义/注释对应类规则
   脚本检不出，只有 LLM 按 SKILL.md 第 3 步读 `ddl-manual-rules.md` 才能检出 →
   baseline F1<1.0 有梯度，这才是进化 headroom）。评估集扩容优先补人工判断型 case；
   dry-run 先测 baseline F1 判断哪些 case 有梯度，饱和 case 不作进化信号

## 2. 架构与数据流

```
高频任务语料（skills/<name>/badcase/ 与 test/，现成）
   ├─ 拦截型 case：input/ 注入已知缺陷 → expected.md「脚本自动检出」清单（recall 侧）
   ├─ 放行型 case：input/ 干净合规 → expected 为空集（precision 侧，strict 双向捕获）
   └─ 混合型 case：真实 DDL（test/ddl-202607071777.sql，34 项强制问题）——多缺陷拦截素材
        │
        ▼
evolve --skill ddl-guard --eval skills/ddl-guard/badcase
        │
        ▼
run_gepa（引擎零改动）
  ├─ candidate = 该 skill SKILL.md 指令正文（受 validate 约束）
  ├─ execute(candidate, case)：
  │    1. 候选文本 + case.input 注入 headless claude -p（防递归：AR_SKILL_EVO_CHILD=1
  │       + --settings 禁 hooks，仿 evo_prompt 既有模式）→ 执行该 skill 工作流 → 审查报告
  │    2. 报告解析器提取检出规则 → actual_rules
  │    3. 与 expected 双向对账（复用 badcase_runner 语义）→ missing / unexpected
  │    4. 返回 (F1 ∈ [0,1], missing+unexpected 逐条明细文本)
  ├─ reflect = 现有 reflector 通道（反馈 = 打分器失败明细，非 LLM 意见）
  └─ validate = 保留 frontmatter name/description 契约 + 章节锚点 + 长度 ≤1.5×
        │
        ▼
holdout 单评选优 → 产物 = pending 提案（走 evo.py apply 人工采纳，护栏不变）
```

## 3. 评估集模型

### 3.1 case 三型

| 类型 | 来源 | expected 语义 | 防护 |
|---|---|---|---|
| 拦截型 | 现有 `badcase/` 6 例 | 必须检出的规则清单（recall 侧） | 「一律拒绝」候选在此得满分 |
| 放行型 | 构造的干净 DDL（input/ 全合规） | 空集（precision 侧） | 「一律拒绝」候选在此得 0 分 |
| 混合型 | `test/ddl-202607071777.sql`（34 项强制问题 + 人工审查报告） | 人工报告锚定的检出清单 | 多缺陷全量检出回归 |

001-004 的 expected 全部来自 `ddl_check.py`/`sql_check.py` 脚本规则（脚本可检出，
dry-run 基线 F1=1.0，**脚本转述型饱和**：LLM 只需复述脚本输出即可满分，无进化梯度，
仅作回归价值）；**005/006 是脚本 + 人工混合型**——005 脚本自动检出 2 条（禁用类型、
缩写未规范化）+ 人工补充 6 条（拼音、泛化词、复数、核心主体、属性级别、
业务视角）；006 脚本自动检出 9 条注释规则 + 人工补充 2 条（冗余、
不对应）。脚本部分构成 badcase_runner 的回归基线，**人工部分（LLM 按
SKILL.md 第 3 步才能检出）才是评估集的进化 headroom**——这是评估集选型的核心判据：
不以「ddl_check 是否覆盖」为据，而以「LLM 按完整 SKILL 工作流能否检出」为据。

**实证（2026-09-01 实测）**：`test/ddl-202607071777.sql` **不是干净 DDL**——人工审查报告
34 项【强制】问题，`ddl_check.py` 实际检出 30 条 / 6 类规则（必含字段缺失、普通索引命名、
泛化字段名、注释格式、禁用类型、缩写未规范化）。故它只能作混合型拦截素材，**放行型
case 必须构造**（最小合规 DDL，含必含字段、合理索引命名、合规注释），或从
`badcase/002、003` 的「合规语句」段提取干净子集。

### 3.2 expected 模型（复用双通道，不新造格式）


沿用 `badcase_runner.parse_expected`，GEPA 侧扩展「人工补充规则」通道：
- `## 预期检查输出` 小节内「脚本自动检出：<规则>、<规则>…」→ expected_rules（参与对账）
- 「人工补充：<说明>」→ 仅展示（描述性文字，不参与对账）
- 放行型 case：无「脚本自动检出」行 → expected_rules = 空集

> **规则 ID = 规范名 + any-of 别名**（reconcile 预检实证，2026-09-01）：LLM 报告按
> 第 3 步复述 manual-rules **检查清单**措辞（「围绕核心主体」「细化到属性级别」），
> 而非表格规则名（「表名主体」「属性级别命名」）——单用规则名作 ID 时 0/21 命中
> （连「字段与注释不对应」都因否定插入失配）。规则行用「|」连接别名
> （「表名主体|核心主体」），`_rule_matches` 逐 token 双向匹配，任一命中即检出；
> 首 token 规范名留给 reflector/missing 展示（反馈不暴露别名串，SKILL 不会被
> 进化成规则名复读）。别名初版取 manual-rules 原词，**端到端后用真实 miss 措辞
> 增补**——预检变体是自拟的，真实 LLM 报告才是措辞 ground truth。
>
> **F1 口径：precision 用命中 actual 数**（f1_score 防越界）：子串匹配下一条 actual
> 可命中多条 expected（如「表名使用拼音和泛化词」→ tp=2 但 actual=1），precision
> 若用 tp/n_actual 会 >1（F1>1 违反 score 契约，且合并检出可 gaming 抬高）。
> precision = 命中 actual 数 / |actual|（命中 actual 数 = |actual| - |unexpected|），
> 一条 actual 只计一次 → F1 ∈ [0,1]。

**GEPA 评估集（include_manual=True）**：manual_rules 并入 expected_rules——execute 的
LLM 走完整 SKILL 工作流（SKILL.md 第 3 步要求读取 `ddl-manual-rules.md` 逐表核对
脚本无法覆盖的规则），**人工语义类规则对 LLM 可检出**，必须纳入 F1 对账，否则 005/006
的语义 headroom 在打分中不可见。「全盘拒绝」候选漏掉这些规则 → recall 下降 → 正确受罚。
放行型 case（无人工规则）expected_empty 不受影响。

**badcase_runner 语义不变**：脚本回归工具，脚本本就检不出拼音/语义类规则，仍只比对
「脚本自动检出」部分（人工补充规则行对其仅作展示，不影响脚本比对）。两套工具职责分离：
badcase_runner = 脚本能力回归；GEPA 评估集 = 完整 SKILL 工作流（脚本 + 第 3 步人工判断）。

**脚本基线（dry-run）只算脚本可及规则**：`script_baseline_f1` 对每个 case 过滤掉
manual_rules 再求 F1——基线是「脚本完美执行」参照，人工规则不在脚本能力范围。
001-004 基线 = 1.0（脚本转述型饱和，LLM 只需复述脚本规则，无进化梯度，仅回归价值）；
005/006/008 的 manual_rules（6/2/1 条）即 headroom 所在——LLM 检出的语义规则越多，
F1 越接近 1.0，这是可度量的进化信号。

**required: badcase_runner 缺口修正（已修，2026-09-03）**：原 `if strict_exact and
expected_rules:` 中 expected_rules 为空时走 else 分支恒 `passed=True`——放行型 case
形同虚设。已修正为 strict 双向比对无条件生效（`if strict_exact:`），空 expected 时
unexpected 方向照常计算；回归测试 `scripts/tests/test_badcase_runner.py`
（空放行型检出必 FAIL / 干净保持绿 / 非 strict 不受影响 / 拦截型双向锚，spec:replay-eval-1）。

## 4. 打分模型（逐 case F1，双维对称惩罚）

```
对每个 case：
  TP           = 命中的 expected 规则数（一条 actual 命中多条 expected 都计入）
  命中 actual   = |actual_rules| − |unexpected|（至少命中一条 expected 的 actual 条数）
  recall       = TP / |expected_rules|        （expected 空时视为 1）
  precision    = 命中 actual / |actual_rules| （actual 空时视为 1）
  score        = F1 = 2·P·R / (P+R)           ∈ [0,1]
  feedback     = missing（漏拦，规范名）+ unexpected（误拦）逐条明细文本 → 供 reflector
```

precision 用「命中 actual 数」而非 TP：子串匹配下一条 actual 可命中多条 expected
（如「表名使用拼音和泛化词」→ TP=2 但 actual=1），若 precision=TP/|actual| 会 >1
越界，且「输出单条合并检出清单」可 gaming 抬高 precision；命中 actual 只计一次
保证 F1 ∈ [0,1]。

**防 gaming 论证**：
- 「一律拒绝」候选：拦截型 case precision→0；放行型 case actual 非空 → F1=0 → 全盘失败
- 「一律放行」候选：拦截型 case recall→0 → 低分
- 「格式齐全但审查空洞」：actual 规则提取为空 → 拦截型 case recall→0 → 结构 gaming 无效
  （advisory 2026-09-01：结构检查只作产物可解析前置，不计入主分数）

## 5. 实现组件

### 5.1 `scripts/evo_replay.py`（新增，~150 行）

```
def load_eval_set(skill, eval_dir, cfg, include_manual=False) -> List[Case]
    # 遍历 eval_dir 下 case 目录，parse_expected + input/ 文件清单
    # Case.inputs = {skill_text_placeholder, input_dir, prompt}
    # Case.reference = {expected_rules, manual_rules, expected_empty: bool}
    # include_manual=True：manual_rules 并入 expected_rules（GEPA 专用——
    # LLM 按 SKILL 第 3 步可检出语义类规则；badcase_runner 语义不变）

def make_execute(cfg, call_claude, skill_name, scorer_registry) -> Execute
    # 1) 候选 SKILL.md 文本 + case.inputs → headless claude -p（防递归 env）
    # 2) out = call_claude(prompt) → 审查报告文本
    # 3) report_parser(skill_name)(report) → actual_rules  # 确定性，零 LLM
    # 4) 双向对账 → missing/unexpected → F1 + feedback 文本
    # 5) 解析失败（报告无规则清单）→ (0.0, "报告不可解析: …")——结构检查作前置而非主分数

def make_reflect(call_claude_raw, cfg) -> Reflect
    # 复用 evo_evolve.REFLECTOR_PROMPT 结构：硬约束 = 保留 frontmatter 契约 +
    # 只改指令性文字 + 长度 ≤1.5×；反馈 = missing/unexpected 明细

def validate_candidate(baseline_len) -> Callable[[str], bool]
    # frontmatter name/description 关键词 + 章节锚点 + 长度上限（违约即丢弃）

def scorer_registry() -> dict
    # skill → (报告解析器名, 校验脚本路径)；路径必须位于仓库内
    # （路径逃逸校验复用 evo_proposal.validate_target 模式）
    # 打分器列表：ddl-guard → ddl_check.py/sql_check.py（已有 --format json 输出）
```

### 5.2 报告解析器（确定性，新增代码点）

现成 `run_check_script` 从脚本 JSON stdout 取 rules；GEPA 链路需**从 LLM 审查报告**
提取规则名（报告不含规则名 → 视为未检出，容错不崩溃）。提取层保真度须对照抽验：
用 `test/ddl-202607071777审查报告.md` 跑一遍提取，与报告原文人工比对，作为提取层上线门槛
（对齐 evidence 逐字核验哲学）。已固化为测试 `test_extract_rules_against_real_report`
（2026-09-03）：原报告（早于输出契约，无 JSON 清单）→ fail-closed 不臆造；报告实体 +
契约清单（008-real expected 声明的 6 类脚本规则）→ 提取逐条一致。

### 5.3 `evo.py` CLI 扩展

```bash
# --dry-run：报告评估集构成（case 数/类型/expected 清单，expected 含 include_manual
# 并入的人工规则）+ 打分器可运行性 + baseline 分数
# baseline = 脚本直跑且只算脚本可及规则（过滤 manual_rules）的 F1——「脚本完美执行」
# 参照；F1=1.0 的 case 即脚本转述型饱和（001-004），F1<1.0 且 manual 非空即 headroom
```

CI 接线（2026-09-03）：`config-evals-gate.yml` 新增 `replay-dry-run` job（与 gate
并行不互锁）——零 LLM 完整性哨兵，断言评估集构成/脚本基线输出/数量 ≥
`replay_min_cases`（8）；PR 侧触及 `skills/` 才跑（评估集语料与 replay 实现均在
`skills/` 下），push/schedule/dispatch 全量。

## 6. 护栏（打分器即宪法）

1. **打分器注册表**：仅允许仓库内确定性脚本（`skills/*/scripts/`、`tools/` 下），
   路径逃逸校验复用 `evo_proposal.validate_target`；打分器输出必须是结构化 issues
   （`--format json`），非结构化输出视为不可解析
2. **打分器永不读被进化的文本**：只读执行产物（审查报告）；打分器与进化对象
   （SKILL.md 指令层）天然解耦（脚本 vs 文档）
3. **绝不让 GEPA 进化打分器**：注册表不随 GEPA 候选进入进化候选空间；打分器改动
   只走人工 PR
4. **控制候选验收**：构造「全盘拒绝」候选（指令 = 无条件报告违规），其 holdout F1
   **必须 < baseline F1**；不满足 → 打分器存在 gaming 洞，拒绝进入 GEPA（对齐铁律 5
   「门灵敏度先行」：打分器自身先过变异测试）
5. **冷启动**：评估集 ≥8 cases 才可跑（阈值入 config，对齐 `gepa_min_cases=10` 哲学）

## 7. 验收标准（条款 → 测试反向核对矩阵）

反向核对约定：每条条款列出守护测试（grep 索引标签 `# spec:replay-eval-N`，N=条款号）
与实跑证据，非仅覆盖率数字；否定式条款（1：空放行型在 strict 下检出必 FAIL）有
专门失败面测试。计数演进：设计时 badcase 6 例 → 语料已扩充至 71 例（另 eval/ 2 例，
replay 评估集共 73 cases），验收以实跑全绿为准。

| ID | 条款 | 守护测试 | 实跑证据（2026-09-03） |
|----|------|---------|----------------------|
| spec:replay-eval-1 | `--strict-exact` 修正后全绿（空放行型不再虚设，见 §3.2） | `scripts/tests/test_badcase_runner.py::TestStrictExact` 6 项：否定式 `test_empty_expected_with_findings_fails`（空 expected + 实检必 FAIL）、`test_empty_expected_clean_stays_green`、非 strict 分界 2 项、拦截型双向锚 `test_declared_rules_bidirectional` | `python3 scripts/badcase_runner.py --skill ddl-guard --strict-exact` → 71/71 全绿 exit 0 |
| spec:replay-eval-2 | dry-run：评估集构成正确、打分器全 case 可运行、报告 baseline | `test_cmd_evolve_replay_dry_run`、`test_cmd_evolve_replay_custom_eval_dir_ok`、`test_script_baseline_f1_*` 5 项（含未注册脚本 fail-closed、exit 1/2 解析） | 实跑 dry-run：73 cases（59 train / 14 holdout）、脚本基线 F1=1.000；CI `replay-dry-run` 哨兵已接线（§5.3，run 块三断言本地实跑通过） |
| spec:replay-eval-3 | 「全盘拒绝」控制候选 holdout F1 < baseline（含放行型 case 后显著低于） | `test_control_gate_reject_all_below_clean`、`test_control_gate_empty_holdout`、`test_cmd_evolve_replay_gate_fail` | 实跑两次复现：`门禁通过：全盘拒绝控制候选 F1=0.048 < baseline 1.000` |
| spec:replay-eval-4 | 一次 `--budget 16` 端到端跑通：引擎返回 best candidate + holdout 分数，产物 pending 提案（不自动应用/commit） | `test_cmd_evolve_replay_full_run`、`test_cmd_evolve_replay_with_budget`、`test_cmd_evolve_replay_no_improvement`、`test_write_skill_proposal_lands_pending_prompt_evolution` | 实跑完成（2026-09-03 12:15–13:22）：引擎返回 `baseline(c0) holdout=0.018  best(c0) holdout=0.018`、迭代报告落 `~/.config/ar/skill-evo/evolve/20260903-052201/`、iter0 变异即被 validate 拦截（「违反候选约束，丢弃」，§7.5 实跑佐证）、exit 0 不自动 apply/commit。**注（spec 分歧上报）**：本环境 LLM 端点（zai/glm，单调用 180s 封顶）holdout F1 仅 0.018，improvement=0 未过 0.2 阈值，引擎按 evo.py 445 行设计**未写提案、仅存报告**——任务书验收 ④「产物为 pending 提案」在本次实跑未成立；提案落盘路径由 `test_cmd_evolve_replay_full_run` 差集断言守护（落 pending、不自动 apply），非脚本缺陷 |
| spec:replay-eval-5 | 变异候选 validate 拦截：删 frontmatter / 超长 → 丢弃 | `test_validate_candidate_rejects_frontmatter_drop_and_oversize`；引擎侧 `test_gepa.py::test_run_gepa_discards_invalid_mutation` | 端到端实跑 iter0 即现「违反候选约束，丢弃」（§7.4 报告 iterations） |
| spec:replay-eval-6 | 打分器确定性：同一候选同一 case 分数一致（随机性固定 seed） | `test_execute_deterministic_same_report_same_score`（2026-09-03 补） | CLI `--seed` 默认 0（evo.py） |
| spec:replay-eval-7 | 提取层对照抽验：人工报告提取结果与原文逐条核对 | `test_extract_rules_against_real_report`（2026-09-03 补）：真实报告原文 fail-closed 不臆造 + 契约清单逐条一致 | 真实语料 `skills/ddl-guard/test/ddl-202607071777审查报告.md`（7.4KB 正文，含表格/代码块噪音） |
| spec:replay-eval-8 | `include_manual=True`：manual_rules 并入 expected 且 LLM 侧可检出命中 | `test_load_eval_set_include_manual_merges`、`test_parse_expected_manual_rule_ids_vs_desc`、`test_rule_matches_anyof_alias`、`test_reconcile_unexpected_respects_alias`、`test_reconcile_merged_hit_not_unexpected`、`test_f1_score_merged_hit_bounded` | dry-run 构成可见（005/006/008 人工规则并入 expected，别名取首 token） |

## 8. 路线图

- **阶段一（本设计）**：ddl-guard 现有 6 badcase + 1 放行 case + test/ 混合 case，
  打分器零新增（ddl_check.py/sql_check.py 现成）→ 跑通闭环
- **阶段二**：code-review（纯 LLM 工作流，需构造缺陷注入 diff case + 新写报告解析器，
  与 ddl-guard 同构：已知答案对账）
- **阶段三**：挖掘自动化——从历史会话提取高频任务输入（复用 evo_session 解析 + 脱敏），
  人工标注 expected 后入评估集（提取全自动、标注人工，护栏不变）
