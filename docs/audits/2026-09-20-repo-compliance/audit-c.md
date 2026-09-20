# 维度 C：文档-事实一致性审查（awesome-rules）

- 审查对象：/tmp/ar-audit 工作树，基线 commit `135b82913f7bc8936327df16fa1b1ec7398bb640`（= origin/main，含 PR #203/#206）
- 规范源（判定依据，非审查对象）：CLAUDE.md:32-33（易腐数字条款 + 优先接线原则）、steering/*.md、README.md 自身条款
- 性质：只读合规审查。全程未修改仓内任何文件；收尾 `git status --short` = 0 行。
- 审查范围：76 个活文档（枚举命令见「覆盖声明」）。CLAUDE.md 为规范源不列为审查对象；skills/README.md 不匹配范围 glob（见「上报事项」6）。

## 发现

### C-1 🟠 README.md:73 — 维度文件计数与磁盘事实不符（10 ≠ 9）

- **文件：行**：README.md:73
- **级别**：🟠 主要
- **问题**：根 README（最高曝光活文档）声称 gtsp 规范"按维度拆分为 10 个文件"，括号枚举 10 个维度名；实测 steering/gtsp/ 仅 9 个编号维度文件（01-09）。枚举中"项目结构、分层架构"实为同一文件 `01-project-structure.md`（gtsp README 索引行"01 | 架构与分层"自证）。三种读法中两种自然读法（8 维度文件 / 9 编号文件）均与"10"矛盾；仅"9 编号文件 + README 索引"读法可凑成 10，但索引不是维度文件且"按维度拆分为"的语义不涵盖它。git log 显示该计数自创建（80395a9）后从未校正；check_doc_freshness.py（R1-R9）对此无守护面。
- **证据摘录**：`按维度拆分为 10 个文件（项目结构、分层架构、命名、Feign、MyBatis、日志、异常、配置、注释、CR 清清单）` ←→ `ls steering/gtsp/` = 01-project-structure.md … 09-cr-checklist.md + README.md（共 10 个 .md，其中维度文件 9 个）
- **复现命令**：`sed -n '73p' README.md; ls steering/gtsp/; ls steering/gtsp/*.md | grep -v README | wc -l`（= 9）
- **建议**：二选一：(a) 改计数为 9 并合并枚举首两项为"架构与分层"；(b) 按 CLAUDE.md:32 改写为自证命令式表述（如"维度文件清单见 `ls steering/gtsp/0*.md`"）。若保留数字，建议在 check_doc_freshness.py R7（枚举守护）中扩展覆盖根 README 的 gtsp 段。

### C-2 🟠 skills/alibabacloud-devops/SKILL.md:90 — 活文档以现在时引用已退役组件 `.factory/forge`

- **文件：行**：skills/alibabacloud-devops/SKILL.md:90
- **级别**：🟠 主要
- **问题**：SKILL.md（运行时操作文档）将"脚本化集成（`.factory/forge` 形态）"列为当前可选形态。事实：forge 已随 ADR-007→ADR-008 演进退役——ADR-007 标头明注【已被 ADR-008 取代】（decisions.md:68），`.factory/` 现为 hosting.py 抽象层，无 forge、forge.json、test_forge.py（`ls .factory/ | grep -c forge` = 0），fix-issue.sh:29 注释"forge.json 中间级随 forge 退役"自证退役。读者/Agent 按 SKILL.md 指引查找 `.factory/forge` 必然落空；其后链接的 ADR-007（REST 实测知识）仍存在且有效，但"形态"框架已陈旧。
- **证据摘录**：SKILL.md:90 `2. **脚本化集成**（\`.factory/forge\` 形态）：需要稳定 argv 界面时。完整实测` ←→ decisions.md:68 `## ADR-007 · 2026-08-25 · forge 平台适配层（GitHub 单平台 → gh 兼容多平台）【已被 ADR-008 取代】`
- **复现命令**：`sed -n '90p' skills/alibabacloud-devops/SKILL.md; ls .factory/ | grep forge; grep -n '已被 ADR-008 取代' .factory/decisions.md`
- **建议**：改述为历史形态并指向现行抽象："脚本化集成（历史上 `.factory/forge` 形态，已由 ADR-008 hosting 抽象层取代，实测知识见 ADR-007）"。同类退役组件引用可考虑加入 doc-freshness R5 式断言守护。

### C-3 🟡 skills/arch-guard/README.md:120 — 守卫外易腐计数"5 组场景"

- **文件：行**：skills/arch-guard/README.md:120
- **级别**：🟡 次要
- **问题**：`badcase/`（5 组场景）为随目录增删变动的活计数。当前恰好正确（badcase/ 下 001-005 共 5 目录），但 check_doc_freshness.py 计数守护面（R4）只覆盖"测试数"三类正则，badcase 组数不在任何门禁内——新增第 6 组场景时此数字将静默漂移且 CI 不拦截。属 CLAUDE.md:32"存量陈述由门禁守护"承诺的守卫空白（CLAUDE.md:33 优先接线场景）。
- **证据摘录**：`- 审查样例：[\`badcase/\`](badcase/)（5 组场景）` ←→ `ls skills/arch-guard/badcase/` = 001-domain-imports-infrastructure … 005-static-import-noise-suppression
- **复现命令**：`sed -n '120p' skills/arch-guard/README.md; ls skills/arch-guard/badcase/ | wc -l`
- **建议**：改写为命令式（`ls badcase/`）或在 R4 增加badcase 组数断言（模式与测试数守护同构）。

### C-4 🟡 skills/code-review/README.md:60 — 跨文档重复且守卫外的"Fowler 基线 12 条"

- **文件：行**：skills/code-review/README.md:60（计数）↔ skills/code-review/SKILL.md:125-160（清单实体）
- **级别**：🟡 次要
- **问题**：README 计数"Fowler 坏味道基线 12 条"与 SKILL.md 清单为两处独立维护的事实源（计数在 README、条目在 SKILL），当前一致（SKILL.md:125-160 恰 12 条 `^\s*-\s+\*\*`），但增删条目时 README 计数无人守护（R1-R9 无此断言）。与 C-3 同类：守卫外活计数 + 双源重复。
- **证据摘录**：README:60 `+ Fowler 坏味道基线 12 条（判断性，仓库标准覆盖基线）` ←→ `sed -n '125,160p' skills/code-review/SKILL.md | grep -cE '^\s*-\s+\*\*'` = 12
- **复现命令**：`sed -n '60p' skills/code-review/README.md; sed -n '125,160p' skills/code-review/SKILL.md | grep -cE '^\s*-\s+\*\*'`
- **建议**：README 改为指向性表述（"条目清单见 SKILL.md 基线节"）消除双源，或 R 系新增跨文档计数断言。

## 待验证

无未决项。审查中产生的唯一候选疑点已定案：docs/design/skill-manifest-gate.md:25 "gauntlet 31 层中无等价层"——该文档为 2026-09-14 dated 设计记录（最后提交 2026-09-15 5382930），其状态头自述"已落地（gauntlet `frontmatter-manifests` 层）"，且 `tools/gauntlet.sh:225` 实存该层；写时 31 层 + 本设计新增 1 层 = 当前 `grep -c '^\s*run_layer ' tools/gauntlet.sh` = 32，内部自洽 → 点时历史记录，合规，不计发现。

**判合规的代表性核验样本**（防止重复劳动，均程序化核对过）：README:112"六项裁决"= skill-manifest-gate.md 恰 6 个 `### ADR-`；README:115"15 层/927 tests"= 对 dated 证据文档 evidence-2026-08-21 内容的引用（当前 9 套件 collect 合计 1578 用例，增长属正常演进，不构成该引用失实）；README:117-120 三张架构图 = README:122 明示"archify 生成的本产能物，位于 docs/design/architecture/（已列 .gitignore 不入库）"且 .gitignore 实含该目录，文档自洽；README:116 DIST-1..10 = 设计文档静态枚举；skill-evo README 各计数（39 份/118 条/30 条/7 条）均带日期实证；doc-gen"7 层"、work-report"3 种"= 句内枚举自锚；grilling 六项/~70 行、templates 阈值类（≥10 cases、1-3 条判据）= 指导边界非事实断言；taskpkg-exp 全部 prompts 内路径 = 冻结实验克隆交付物。

## 上报事项

1. **core.quotePath 陷阱**：`git status` 默认对非 ASCII 路径加引号包裹，曾致 `^docs/` 锚点误判大量"未跟踪文件"。本审计所有枚举一律使用 `git -c core.quotePath=off ls-files`。后续审计者请沿用。
2. **并行会话**：同工作树存在并行维度 D 审计（门禁覆盖度，产出 /tmp/audit-d.md）。两维度全程只读、互不干涉；claude-mem 上下文回放多次注入两会话观察流，均按 system 授权内容处理、未据此改变本维度结论。
3. **/tmp 草稿披露**：纪律原文"唯一允许写盘 /tmp/audit-c.md"，实际审查过程中在仓外 /tmp 使用过中间草稿：scope-files.txt（76 文件范围清单）、a.txt、b.txt、disk-scope.txt、git-scope.txt（枚举对账用）。仓内零写入。
4. **pytest 只读实证方式**：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest <dir> --collect-only -q -p no:cacheprovider`——两标志分别防 __pycache__ 与 .pytest_cache 写盘（两者均在 .gitignore 内，git status 不能作为无写入的证据，故以机制而非状态证明）。本机 pytest 8.x 可用；pytest-cov/yq 缺失但无文档声称依赖其存在于本机，不影响结论。
5. **范围外礼貌备注**（属维度 D 或仓主）：CLAUDE.md 存在两处逐字重复条款块（"标注强制的条款应同步评估可机械检查性"与"工厂链运行期间"各自出现两次，约 36-41 行区）；skills/README.md 不匹配本维度范围 glob（`skills/*/README.md` 只匹配一级子目录），若各维度范围定义希望覆盖它需明示。
6. **命令路径解析口径**：skills/*/README·SKILL 中 `python3 scripts/xxx.py` 以技能目录为执行基准（SKILL.md frontmatter 与正文均声明"以本文件所在路径为基准"），从文档自身目录解析会误报断链；distribution 设计文档 §4.1 明示"常用复核命令(在各下游仓执行)"，其 `.factory/locks/*` 路径仅存在于下游仓。机械路径存在性检查必须结合声明的执行基准裁决。

## 覆盖声明

**范围**（全量枚举，非抽样）：

```
git -c core.quotePath=off ls-files | grep -E '^README\.md$|^skills/[^/]+/(SKILL|README)\.md$|^docs/.*\.md$|^templates/[^/]+$' | wc -l
→ 76
```

**检查点 ①（易腐数字）**：对 76 文件跑三类计数正则——阿拉伯 `[0-9][0-9,，]*\s*[个条处项类种次行套组篇份步层门张块名点支]`、中文数字 `[{一二三四五六七八九十百}]{1,4}\s*[同前缀量词]`、英文 `\b\d+\s*(tests?|components?|rules?|cases?|层|…)\b` ——合计 427 命中，逐条裁决。分类口径：dated 记录（docs/design、docs/research、P2-P4 task-brief、evidence、冻结 prompts、文中带日期实证）与句内枚举自锚计数 = 合规；活文档守卫外活计数 = 发现（C-1/C-3/C-4；C-2 属检查点④产物）。产出正式发现 4 条，无误杀。

**检查点 ②（命令声称）**：程序化提取围栏命令 86 条 + 行内命令 138 条，路径 token 验证 125 个：48 个初判缺失经逐条裁决全部为结构性假阳性——`path/to/*` 占位符（skills README 示例）、git 引用（`origin/master...HEAD`、`refs/remotes`）、明示下游仓命令（distribution §4.1）、冻结实验 prompts 的克隆内交付物（taskpkg-exp）、`src/main/java` 目标仓参数。根 scripts/ 引用资产（run_tests.sh、md_link_check.py、pre-push-tests.sh、tests/）与四份 pytest.ini 均存在。核心 pytest 声称以 `--collect-only` 无害实证：gauntlet 9 套件（tools/gauntlet.sh:201-227）全部可收集——scripts 64、.factory/tests 443、api-guard 88、ddl-guard 169、arch-guard 144、impact-guard 69、skill-evo 213、doc-gen 316、arch-hawkeye 72，合计 1578；README 三条声称命令（arch-guard:118、impact-guard:5、skill-evo:5 的 `pytest skills/<x>/scripts/tests -q`）路径全部命中上述套件。命令类零违例。

**检查点 ③（相对链接）**：程序化解析 76 文件全部 Markdown 相对链接 151 条，目标文件存在性 100%（含从文件所在目录解析的相对基准）；跨文件锚点引用 3 条（`#锚` 形态）目标标题全部存在。零断链。

**检查点 ④（SKILL.md 路径引用）**：两轮扫描——前缀法 + 反引号全量 45 个路径 token 逐条裁决——44 个命中或定性假阳性（glob 通配、占位符、运行时产物如 doc-manifest/receipt.json、散文简称后接全路径、steering/ 下实体如 openapi-standards.md）；唯一真阳性即 C-2（`.factory/forge` 陈旧引用）。

**基线与只读复核**：审查首尾两次 `git status --short` 均 0 行；HEAD 全程 `135b82913f7bc8936327df16fa1b1ec7398bb640` 未动。
