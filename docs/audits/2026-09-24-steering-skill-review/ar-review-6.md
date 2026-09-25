# awesome-rules 技能文档审查报告（ar-review-6）

- **基线对账**：`git -C /Users/dreambt/sources/awesome-rules status` → `On branch main` / `nothing to commit, working tree clean`；`HEAD = dfe173295422ddfa02ee81dddc903e081a251b43`（= 基线 dfe1732）。无漂移、无脏树，无需披露例外。
- **审查对象**（全文精读）：`skills/code-review/SKILL.md`、`skills/sourcery-autofix/SKILL.md`、`skills/skill-evo/SKILL.md`、`skills/task-flow/SKILL.md`。
- **取证范围**（只读）：各技能 README.md / config.example.toml / scripts / tests、仓根 CLAUDE.md、skills/README.md、steering/review-report-standards.md、tools/check_frontmatter_manifests.py、tools/git/install.sh、lefthook.yml（仓根 + tools/git 模板）、tools/git/lefthook/sourcery-gate.sh（stat + 行读）。
- **严重度定义**：必改（错误或不可执行，须改）；建议（偏离最佳实践，宜改）；可选（一致性瑕疵）。
- 本仓零修改：无 git 写操作、无仓内文件写入；唯一写入为本报告。全部行号来自本轮实际读取 / grep / stat 输出。

---

## F-01 | skills/sourcery-autofix/SKILL.md:42、48 | A/C | 必改

**问题**：`review --check` 清零判定与 fix 命令的配置口径自相矛盾。文件自定「同配置」条款要求 `--config .sourcery.yaml`（L35-36：``2. **同配置**：仓库有 `.sourcery.yaml` 必须 `--config .sourcery.yaml`——`` / ``  本地、CI gate、sourcery-ai[bot] 三方同引擎同配置，否则本地修的 gate 不认；``），且 L37 的 fix 命令确实带该参数：``3. 执行 `sourcery review --fix --config .sourcery.yaml <files>`；``；但同流程的**清零判定**（L42：``6. 复跑 `sourcery review --check <files>`：exit 0 = 清零；否则列出剩余``）与场景 2 收尾（L48：``sourcery issue -> 按场景 1 完整循环修复，以 `sourcery review --check` ``）均**漏传 `--config`**。合并门禁实测调用为带配置形式：`tools/git/lefthook/sourcery-gate.sh` L54 ``out=$(sourcery review --check --config .sourcery.yaml "${SUPPORTED[@]}" 2>&1)``。后果：本地以默认配置清零、gate 以 `.sourcery.yaml` 判定，`exit 0` 不构成 gate 放行的充分条件——正是 L35-36 明文要防的情形（「本地修的 gate 不认」）。

**修改建议**：
- 改前（L42）：``6. 复跑 `sourcery review --check <files>`：exit 0 = 清零；否则列出剩余``
  改后（L42）：``6. 复跑 `sourcery review --check --config .sourcery.yaml <files>`：exit 0 = 清零；否则列出剩余``
- 改前（L48）：``sourcery issue -> 按场景 1 完整循环修复，以 `sourcery review --check` ``
  改后（L48）：``sourcery issue -> 按场景 1 完整循环修复，以 `sourcery review --check --config .sourcery.yaml` ``

**依据**：标准 A（技能内命令须一致、可执行）；标准 C（一致性）；本文件 L35-37 自定「同配置」规则；gate 脚本 L54 实证。

---

## F-02 | skills/code-review/SKILL.md:31、59、90（同步 code-review/README.md:27、40、42） | A | 建议

**问题**：核心执行路径依赖 omp（oh-my-pi）宿主专属原语且未标注适用范围：L31 ``- 用户给了固定点就用它；没给就问。MR/PR 号先解析：GitHub 用 `pr://N`；``；L59 ``单批 `tasks[]` 同时发出。两个 prompt 都必须包含：``；L90 ``1. **先考古再重派**：读 `history://<agent名>` 提取其最终 yield——子代理通常``（L89-92 的断连恢复流程，为本技能实测亮点）。本技能经 `skills/` 分发面进入非 omp 宿主（仓根 `.claude-plugin/plugin.json` 已实证多宿主分发形态）；`pr://` / `tasks[]` / `history://` 是 omp harness 专属资源，其他宿主不存在，L89-92 恢复流程将整体不可执行。README.md 同源表述：:27（``支持 GitHub（`pr://N`、`gh`）与云效 Codeup（走``）、:40（D 行 ``先 `history://` 考古再重派``）、:42（F 行 `` `pr://` 对 Codeup 无效；skill 原假设 GitHub 工作流``）。

**修改建议**（保留 omp 写法，补宿主分支，均为改前 -> 改后）：
- L31 改前：``- 用户给了固定点就用它；没给就问。MR/PR 号先解析：GitHub 用 `pr://N`；``
  L31 改后：``- 用户给了固定点就用它；没给就问。MR/PR 号先解析：GitHub 用 `pr://N`（omp 宿主快捷资源；其他宿主用 `gh pr view <N>`）；``
- L59 改前：``单批 `tasks[]` 同时发出。两个 prompt 都必须包含：``
  L59 改后：``单批并行发出（omp 宿主单批 `tasks[]`；其他宿主在同一条消息内并行发出多个子代理任务）。两个 prompt 都必须包含：``
- L90 改前：``1. **先考古再重派**：读 `history://<agent名>` 提取其最终 yield——子代理通常``
  L90 改后：``1. **先考古再重派**：读子代理交付记录（omp 宿主 `history://<agent名>`；其他宿主读子代理输出/落盘交接件）提取其最终 yield——子代理通常``
- README.md:27 按 L31 同法加注；README.md:40 D 行末增注「（`history://` 为 omp 宿主能力）」；README.md:42 F 行保持（已说明 `pr://` 局限，仅需与 SKILL.md 口径一致）。

**依据**：标准 A 第 1/6 条（分发面可执行性、技能边界）；仓根多宿主分发实证。

---

## F-03 | code-review:22-25、skill-evo:48、51、task-flow:32-33 | A | 建议

**问题**：渐进式加载违例——背景/案例叙述留在 SKILL.md，而各文件 frontmatter `files:` 已声明按需加载的 README：
- (a) `skills/code-review/SKILL.md:22-25`「## 为什么两轴」整节为设计动机（`一次变更可以过一轴而挂另一轴：完全合规但实现错了东西（Standards 过、Spec 挂）；` / `精确实现工单但破坏项目约定（Spec 过、Standards 挂）。分轴报告防止一轴掩盖另一轴。`），零操作指令；且正文从不引用 README.md（frontmatter 声明了它）。对比 skill-evo L41-42 已有正确指针：`架构、omp hook 安装、GEPA 原理、配置详解、设计边界等背景知识见` / `[README](README.md)（渐进式加载：本文件只保留审核操作所需的指引）。`
- (b) `skills/skill-evo/SKILL.md`：L48 实测案例（`实测案例（2026-08-24 消融实验）：子代理在报告自述「不显著、夹具泄题」的同时直接删除 manual-rules 7 条规范（含两条安全规则），被集成验收 revert——安全类规则的裁剪证据门槛须高于普通条目。`）与 L51 实测案例（`（实测案例：初版模板在 5 条样本下即被修正，14 条样本后才区分出必选段与可选段）`）属「为什么」背景，非审核操作步骤；同类内容在 README 已有专门容器（skill-evo/README.md 的 `## 设计边界（v2）` 节，其 L138 即存同类实战案例）。
- (c) `skills/task-flow/SKILL.md:32-33`：`本技能在本仓的落地原则（对齐 \`docs/research/comet.md\` 借鉴点 #5，并遵循本仓` / `「内容库而非运行时安装器」的形态约束）：`——设计取舍叙述；`docs/research/comet.md` 虽在本仓存在（已 stat 核实），但技能运行语境是「用户业务项目内」（L4），届时该路径不可解析。

**修改建议**：
- (a) L22-25 整节移入 code-review/README.md（建议在 `## 与上游版本的差异`（L30）内新增「为什么两轴」小节）；SKILL.md 原位替换为一行指针：`两轴设计动机见 [README](README.md)。`
- (b) L48、L51 的实测案例移入 skill-evo/README.md 的 `## 设计边界（v2）` 节（或新增「实战记录」小节）；SKILL.md 保留规则句本体（「结论落地须另开提案走人工审核」与「警惕单例过拟合，优先采纳跨会话/多样本复现证据」）。
- (c) L32-33 替换为指针：`本技能的设计取舍与形态约束（含 \`docs/research/comet.md\` 借鉴点 #5 对齐说明）见 [README](README.md)。` 原叙述移入 task-flow/README.md（建议并入 `## 移植说明` 或新增「设计取舍」小节）。

**依据**：标准 A 第 2 条（渐进式加载：SKILL.md 只放 AI 操作指引，背景/原理归 README 或 references 按需读取）。

---

## F-04 | skills/code-review/SKILL.md:103-106 | B | 建议

**问题**：L103 `- 收尾对齐[审查报告输出规范](../../../steering/review-report-standards.md)：` 只对齐了五段式结构，漏掉该规范 L16 的落盘硬要求：`审查报告落盘到目标仓库的 docs/ 目录（或直接推送到 MR 评论），不放 /tmp 等重启即失的临时目录；后续补充证据链、修复方案、测试覆盖等追加在同一份报告上，形成单一审查档案而非散落多份文件。` 本技能无任何落盘指引，聚合报告容易只留在会话里（L106 汇总行、L105 证据边界段都在会话内消费）。code-review/README.md:44（`另有输出对齐：聚合报告遵守 steering 审查报告五段式（结论先行 + 证据边界强制段）。`）同缺落盘口径。

**修改建议**：在 L106 之后追加一条，并同步 README.md:44 句末：
- 追加（SKILL.md）：`- 落盘：报告写入目标仓库 \`docs/\` 或推送 MR 评论，禁 /tmp 等易失目录；后续证据链/修复方案/测试覆盖追加同一份报告（见[审查报告输出规范](../../../steering/review-report-standards.md)）。`
- README.md:44 句末拼入：`按规范落盘目标仓库 docs/ 或 MR 评论，不落临时目录。`

**依据**：标准 B 第 3 条（与其余权威源一致，重复条款收敛到单一权威源）+ steering/review-report-standards.md:16。

---

## F-05 | code-review:61、67、98、105（同类 sourcery-autofix:15-23、skill-evo:38-39） | B | 建议

**问题**：六处【强制】条款未按仓根 CLAUDE.md:37 评估可机械检查性：`标注强制的条款应同步评估可机械检查性：能查出的配 gauntlet 静态门 + 负控制（证明检查器会失败），门禁查不出违规的强制条款只靠人记，效力弱。` CLAUDE.md:34 还要求 `发现「实现与文档不一致」类问题时，优先接线而非只修文档：给守门层（\`tools/check_doc_freshness.py\` 及 gauntlet）追加规则…`；CLAUDE.md:45 声明 `审查类技能会运行自动化脚本，不要跳过脚本检查步骤`。实测现有 gauntlet 门禁（`tools/check_frontmatter_manifests.py` 的 M1 steering / M2 skills 清单校验）不覆盖：code-review L61 `**可证伪性条款（强制）**`、L67 `**输出契约（强制）**`、L98 `- **抽验环（强制）**：聚合方对子代理发现中可 grep 验证的事实断言逐条抽验`、L105 `**证据边界段（强制）**：\`已验证 / 未覆盖 / 置信度\`，抽验结果归入已验证。`；sourcery-autofix 红线（L15-23）与 skill-evo 人工审核护栏（L38-39：`**提取全自动，应用必须人工审核**`）同属流程性约束，均无机械门禁——当前全靠执行方自检。

**修改建议**（两条并取）：(a) 就近标注：对以上六处在所在小节末尾统一补一行「`> 机械检查现状：仓级 gauntlet 未覆盖本条（现仅 frontmatter M1/M2 等），靠执行方自检。`」；(b) 可机械化项接线：L67 输出契约本身是结构化 JSON（`findings[]`，每项含 `title/severity/confidence/file/line/...`）、L105 证据边界段有固定三段名——与 F-04 落盘配套后，可在 gauntlet 增加「聚合报告 JSON schema + 三段存在性」静态检查并配负控制，先例见既有 frontmatter 检查器与 `tools/test_gauntlet_checks.sh`。

**依据**：标准 B 第 2 条 + CLAUDE.md:34/37/45。**对照**：task-flow 的 fail-closed 纪律（SKILL.md:112-121 表；如 L116 `| 官方门禁未通过（产物缺失/为空、脚本非零、规范缺失） | \`advance\` exit 1 且**零写入**…`）已由 `scripts/taskflow.py` 以退出码机械实现，属「已机械」正面样板。

---

## F-06 | skills/skill-evo/SKILL.md:47 | A | 可选

**问题**：L47 句首 ``- pending 大量积压时（如 39 份提案 118 条 lesson）逐条人工审不可扩展：``——「如 39 份提案 118 条 lesson」的静态计数会被读作常态量级，属易腐数字；CLAUDE.md:33 要求 `文档不写易腐数字：测试数量、组件数量等随代码变动的计数值不进 README/SKILL.md，改写为可执行命令（如 \`pytest <测试目录> -q\`）让事实自证`。同句末带的日期快照（`2026-08-24 实战：118 条 → apply 65 / reject 36 / 灰区 17，人终裁 3 项`）为历史实测，保留合理，宜与当前量级表述分离。

**修改建议**：
- 改前（L47 句首）：`- pending 大量积压时（如 39 份提案 118 条 lesson）逐条人工审不可扩展：`
- 改后（L47 句首）：`- pending 大量积压时（当前积压量以 \`python3 scripts/evo.py list\` 实测为准；2026-08-24 快照 39 份提案 / 118 条 lesson）逐条人工审不可扩展：`
（`python3 scripts/evo.py list` 为本文件 L56 已定义命令，证据链自洽。）

**依据**：标准 A 第 5 条 + CLAUDE.md:33。

---

## F-07 | skills/sourcery-autofix/SKILL.md:32、59 | A | 可选

**问题**：两处以裸文件名引用脚本：L32 尾 `  喂入 fix 循环会以 check exit 0 虚假闭环，见 sourcery-gate.sh 头注释）`、L59 尾 `（支持面=CLI 实测 py/ts/js，见 sourcery-gate.sh 头注释）；`。`sourcery-gate.sh` 在本仓位于 `tools/git/lefthook/sourcery-gate.sh`（仓根 lefthook.yml:52 `run: bash tools/git/lefthook/pre-push-delete-guard.sh || bash tools/git/lefthook/sourcery-gate.sh {push_files}`），在业务仓分发为 `.lefthook/sourcery-gate.sh`（tools/git/install.sh:44 `DIST` 映射 `"lefthook/sourcery-gate.sh:.lefthook/sourcery-gate.sh"`；模板 tools/git/lefthook.yml:46 同法调用）——裸名不可路径解析，读者无法定位。

**修改建议**：
- L32 改后：`  喂入 fix 循环会以 check exit 0 虚假闭环，见 sourcery-gate.sh 头注释——该脚本在本仓为 \`tools/git/lefthook/sourcery-gate.sh\`，在业务仓为 \`.lefthook/sourcery-gate.sh\`）`
- L59 改后：`（支持面=CLI 实测 py/ts/js，见 sourcery-gate.sh 头注释——脚本路径见第 1 步）；`

**依据**：标准 A 第 3 条（引用路径逐一核实 + 可定位）。

---

## F-08 | skills/skill-evo/scripts/*.py、skills/task-flow/{scripts,tests} | A | 可选

**问题**：可执行位分布无规律（stat 实测）：skill-evo/scripts 9 个 .py 中 8 个 644、仅 `evo_replay.py` 755（`evo.py`、`evo_config.py`、`evo_evolve.py`、`evo_gepa.py`、`evo_patrol.py`、`evo_prompt.py`、`evo_proposal.py`、`evo_session.py` 均 644）；task-flow 混布（`scripts/taskflow.py` 755、`tests/test_taskflow.py` 755、`tests/conftest.py` 与 `tests/pytest.ini` 644）。两技能文档的调用式样均为 `python3 <path>`（如 skill-evo L56/L66/L106/L109/L112），+x 对调用非必需，属一致性瑕疵。

**修改建议**：先定约定再对齐。仓内先例：`tools/git/lefthook/` 下脚本一律 644 且以 `bash <path>` 调用。据此推荐统一 644（文档命令一律带解释器前缀）：`chmod 644 skills/skill-evo/scripts/evo_replay.py skills/task-flow/tests/test_taskflow.py`；若反向选择「入口脚本可直呼」式样，则对齐为入口 755（`chmod +x skills/skill-evo/scripts/evo.py`）并把约定写入 `skills/README.md`。

**依据**：标准 A 第 3 条（权限核查；核查结论：+x 非功能性必需，属一致性项）。

---

## 统计

- **总数 8**：必改 1（F-01）；建议 4（F-02、F-03、F-04、F-05）；可选 3（F-06、F-07、F-08）。
- 按对象：code-review 4（F-02、F-03a、F-04、F-05）；sourcery-autofix 3（F-01、F-05、F-07）；skill-evo 3（F-03b、F-05、F-06）；task-flow 2（F-03c、F-08）。
- 按类别：A 6（F-01 兼 C、F-02、F-03、F-06、F-07、F-08）；B 2（F-04、F-05）。

## 核查通过项（正面结论，供交叉验证）

1. frontmatter：四文件 `name` / `description` / `files` 齐全；description 均含「当用户提到：… 时激活」（或「以下任意意图时激活」）触发句式。
2. `files:` 清单逐条 stat 核实全部存在（含 skill-evo 的 20 条 scripts/tests 清单）。
3. 正文引用路径核实：code-review -> `../../steering/review-report-standards.md`、`../alibabacloud-devops/SKILL.md`、`visual-output.md`；sourcery-autofix -> `.sourcery.yaml`（仓根存在）；skill-evo -> `README.md`、`config.example.toml`、`scripts/evo_prompt.py`；task-flow -> `steering/database-design-specification.md`、`steering/api-contract-freeze-standards.md`（`--repo-root` 解析，两文件存在）、`docs/research/comet.md`（本仓存在，F-03c 另述其可移植问题）。
4. 文档 <-> 实现一致：task-flow 子命令与退出码表（L86-98）与 SKILL.md fail-closed 表（L112-121）、`scripts/taskflow.py` 行为语义逐条吻合；skill-evo REASON_CODES（L119-122）与 `scripts/evo_proposal.py` 一致；sourcery-autofix 的 CLI 支持面口径（py/ts/js，php 静默不扫）与 gate 脚本头注释一致。
5. 半角分号规则（code-review L122 与 visual-output.md、README.md）为「常量 + 细节单源」分层，不计 DRY 违例。
6. 未发现中英文/标点系统性不一致：四文件破折号一律 `--`、箭头一律 `->`、中文标点全角统一。

## 审查中上报事项

- **E-1**：`skills/README.md`（技能编写规范，非本次审查对象）首段仅登记 frontmatter = `` `name` + `description` + 正文工作流 ``，未登记 `files:` 字段；但 `tools/check_frontmatter_manifests.py` 的 M2 已将其定为必填（docstring：`M2 skills 族（skills/*/SKILL.md）：name 必填；files 必填（断链单向 + 路径围栏，见 frontmatter_lib.validate_skill）`，缺失/断链即拒）。建议在 `skills/README.md`「技能编写约束」补录 `files:` 语义（按需加载清单 + 断链校验），避免新技能作者被 M2 拦截时才知晓。
- **E-2**：F-05 方案 (b) 若采纳，需在 gauntlet 新增「聚合报告 JSON schema + 证据边界段存在性」检查与负控制，属新工作项（超出文档修改范畴），建议由主会话立项排期。

---

（本报告为只读审查产物；仓内文件与 git 状态未做任何修改。全部行号来自本轮实际读取 / grep / stat 输出。）
