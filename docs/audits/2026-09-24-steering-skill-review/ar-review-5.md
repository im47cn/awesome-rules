# awesome-rules 技能文档审查报告（ar-review-5）

- **审查对象**：`skills/{api-guard,arch-guard,contract-guard,ddl-guard,impact-guard}/SKILL.md`（逐文件全文精读）
- **基线对账**：`git status` 实测 HEAD = `dfe173295422ddfa02ee81dddc903e081a251b43`（= 基线 dfe1732），工作树 clean，无漂移需披露。
- **审查方式**：只读。引用路径/权限/脚本参数均经实测（`os.path` 逐一存在性核验、`os.access` 权限核验、脚本 argparse 源码 grep、关键字符串全 scripts/ 目录 grep）。
- **严重度**：按任务给定三级 🔴必改 / 🟠建议 / 🔵可选（未沿用仓内 impact-guard 四级色标）。

---

## 发现

### F1 | skills/api-guard/SKILL.md:8（对照 :54、files :19）| A | 🔴必改

**问题**：frontmatter description 写"仅检查业务接口通用规范（……），不检查对外 Open API 四段式规范"，但正文第 2 步（:54）明确指示"审查对外 Open API 时，另读 `openapi-manual-rules.md`，逐条核对脚本外条款"，且 files 清单（:19）就打包了该文件。description 是技能激活路由的依据，这句"不检查"会让路由方在收到"审查对外 Open API"请求时拒绝激活本技能——而工作流实际支持该场景。属于同文件内 description 与正文的能力声明矛盾（仓根 CLAUDE.md:16 的"业务接口自动审查"一行也沿用了这一窄化口径）。

**修改建议**（改前 → 改后）：
- 改前（:8）：`仅检查业务接口通用规范（路径命名、动作收敛、禁止 path 传标识、时间注解、映射注解、Mapper XML 软删过滤），不检查对外 Open API 四段式规范。`
- 改后：`脚本自动检查仅覆盖业务接口通用规范（路径命名、动作收敛、禁止 path 传标识、时间注解、映射注解、Mapper XML 软删过滤）；对外 Open API 四段式规范不在脚本自动检查范围，由人工按 openapi-manual-rules.md 清单核对（见正文第 2 步）。`

**依据**：A（description 含明确触发词、准确表达"何时用"；不得声明排除已支持场景）；B（同文件内条款矛盾）。

### F2 | skills/ddl-guard/SKILL.md:189、:192（对照 :200）| A | 🟠建议

**问题**：命令模板 `python3 scripts/ddl_check.py [--format json]`（:189）与 `python3 scripts/sql_check.py [--format json]`（:192）均未写位置参数。实测脚本支持：`ddl_check.py:1125` 与 `sql_check.py:877` 均有 `parser.add_argument("path", nargs="?", default=".", …)`。兄弟技能都写明了目标参数（api-guard:42 `<目标文件或目录>` + :45 默认值说明；arch-guard:72 `<项目根目录>`；impact-guard:74-83 示例带 `.`）。ddl-guard 正文 :200 只说"脚本自动扫描全部文件"，未说明扫描基准是哪个目录——脚本以 cwd 为默认，而技能定位脚本又要求"以本文件所在路径为基准"（:185），两处基准混用，照文档执行很可能扫错目录。

**修改建议**：
- 改前（:189）：`python3 scripts/ddl_check.py [--format json]`
- 改后：`python3 scripts/ddl_check.py <目标文件或目录> [--format json]`
- :192 同改：`python3 scripts/sql_check.py <目标文件或目录> [--format json]`
- 并在 :195 退出码说明附近补一行：`<目标文件或目录>`：待审查路径；不传则默认扫描当前目录（与 api-guard:45 句式一致）。

**依据**：A（SKILL.md 须是可照做的操作指引，参数面与脚本实际 CLI 一致）；C（与兄弟技能写法一致）。

### F3 | skills/arch-guard/SKILL.md:90 | A | 🟠建议

**问题**："覆盖 6 个依赖方向"是易腐计数字：脚本演进出第 7 个方向时此句即成陈旧陈述，且该数字无法从文档自证。仓根 CLAUDE.md:33 明令"文档不写易腐数字：测试数量、组件数量等随代码变动的计数值不进 README/SKILL.md，改写为可执行命令让事实自证"。

**修改建议**（改前 → 改后）：
- 改前：`结果每行一条违规（caller → callee 精确链路），覆盖 6 个依赖方向。`
- 改后：`结果每行一条违规（caller → callee 精确链路）；覆盖的依赖方向清单以本次 \`--mode graph\` 实时输出为准，不在此静态转写。`

**依据**：A（不写易腐计数字）；仓根 CLAUDE.md:33（易腐数字禁令）。

### F4 | skills/impact-guard/SKILL.md:60 | A | 🟠建议

**问题**：架构表 Tier 1 行写"仅项目未 index 时降级，头部告警 `[Tier 1 only]`"。实测 impact-guard 全部 scripts/ 目录 grep 字面串 `Tier 1 only` 0 命中——该告警字符串不存在。实际降级标注机制是：`renderer.py:80` 写入 receipt `"degraded": ["tier1_class_level"]`，`renderer.py:92-93` 据此在文本报告渲染 `分析精度: Tier 1 类级（import 反向索引）`。按文档去找 `[Tier 1 only]` 标记的验证者会误判"未降级"。

**修改建议**（改前 → 改后）：
- 改前：`仅项目未 index 时降级，头部告警 \`[Tier 1 only]\``
- 改后：`仅项目未 index 时降级；报告标注 \`分析精度: Tier 1 类级（import 反向索引）\`，receipt 中 \`boundary.degraded\` 含 \`tier1_class_level\``

**依据**：A（SKILL.md 引用的脚本行为须与代码一致）；证据 renderer.py:80,92-93。

### F5 | skills/ddl-guard/SKILL.md:3-6 | A | 🔵可选

**问题**：description 是 4 个兄弟技能中唯一没有"当用户提到……时激活"主动句式的：现写法"数据库设计规范与检查，包括审查DDL、建表语句、……"把触发词埋在名词枚举里，"何时用"不显式。兄弟技能统一句式见 api-guard:4-6、arch-guard:6-7、contract-guard:4-5、impact-guard:5-7。

**修改建议**（改前 → 改后）：
- 改前（:4-5）：`数据库设计规范与检查，包括审查DDL、建表语句、表结构设计、字段设计、索引设计、MySQL建表、审查Mapper SQL、PO类规范、数据库规范检查、SQL审核、数据库设计审查。`
- 改后：`数据库设计与审查。当用户提到以下任意意图时激活：审查DDL、建表语句、表结构设计、字段设计、索引设计、MySQL建表、审查Mapper SQL、PO类规范、数据库规范检查、SQL审核、数据库设计审查。`

**依据**：A（description 以主动语态写"何时用"）；C（技能家族句式一致）。

### F6 | skills/contract-guard/SKILL.md:51（连带 :8）| C | 🔵可选

**问题**：:51 "输出报告按 `steering/review-report-standards.md` 五段式"是裸代码文本路径，基准目录不明也不可点击；兄弟技能一律用相对链接（api-guard:59、ddl-guard:219 均为 `[`../../steering/review-report-standards.md`](../../../steering/review-report-standards.md)`）。:8 description 里 `steering/cross-repo-contract-standards.md` 同为仓根基准路径，与正文 :39 的 `../../` 链接并存两套口径。

**修改建议**（改前 → 改后）：
- 改前（:51）：`输出报告按 \`steering/review-report-standards.md\` 五段式。`
- 改后：`输出报告按 [\`../../steering/review-report-standards.md\`](../../../steering/review-report-standards.md) 五段式。`

**依据**：B（内部相对链接有效且风格统一）；C。

### F7 | skills/impact-guard/SKILL.md:39 | C | 🔵可选

**问题**：H1 为 `# 变更影响分析 (impact-guard)`，半角括号混排英文技能名，是 5 个技能中唯一带英文后缀的 H1（api-guard:26 `# 业务接口规范设计与审查`、arch-guard:53、contract-guard:16、ddl-guard:177 均纯中文）。frontmatter name 已承载英文标识，H1 重复且风格不一致。

**修改建议**（改前 → 改后）：`# 变更影响分析 (impact-guard)` → `# 变更影响分析`。

**依据**：C（中英文/标点风格一致；术语不重复承载）。

### F8 | 跨技能：5 个入口脚本可执行权限 | A | 🔵可选

**问题**：按审查标准"脚本须有可执行权限"实测：`check-contract.sh` 755 ✓；但 5 个 Python 入口脚本全部 644 无 +x（api_check.py / arch_check.py / ddl_check.py / sql_check.py / impact_check.py），且首行均已带 `#!/usr/bin/env python3`（head -1 实测）。SKILL.md 均以 `python3 scripts/…` 解释器调用，无功能影响，故降为可选；另 ddl-guard 内部权限倒挂：非正文引用的 `gen_cases.py`、`test_gen_cases.py` 反而 755。

**修改建议**（具体动作）：
```
chmod +x skills/api-guard/scripts/api_check.py skills/arch-guard/scripts/arch_check.py \
  skills/ddl-guard/scripts/ddl_check.py skills/ddl-guard/scripts/sql_check.py \
  skills/impact-guard/scripts/impact_check.py
```
或维持解释器调用约定不动，但应统一 ddl-guard 内 gen_cases 系与入口脚本的权限口径。

**依据**：A（脚本须有可执行权限；脚本引用逐一核实）。

### F9 | skills/ddl-guard/SKILL.md:171-172（files 清单；连带 api-guard files:23）| C | 🔵可选

**问题**：清单列入 `test/ddl-202607071777.sql` 与 `test/ddl-202607071777审查报告.md`。实测后者是真实一次性审查产出（文件自记"审查日期：2026-07-29、【强制】问题：34 项"，题注指向"202607071777郑磊.sql"）：(a) 文件名时间戳 `1777` 非合法时分，且与自记审查日期 2026-07-29 互相矛盾；(b) 审查报告是输出物不是输入 fixture；(c) SKILL.md 正文对 `test/` 零引用（api-guard:23 `test/test_controller.java` 同为"清单含、正文零引用"）。清单本身由 `tools/backfill_skill_manifests.py`（ADR-5）按 git 跟踪文件全量回填，根因在文件落位而非清单维护。

**修改建议**（具体动作）：若为真实样本，移入 `eval/`（如 `eval/009-real-world-gdc/`，与既有 007/008 编号衔接）并去掉非法时间戳命名，报告作 expected 参照；若为遗留物，删除后复跑 `tools/backfill_skill_manifests.py` 收敛清单。api-guard 的 `test/test_controller.java` 建议同批处置（正文引用或移入 badcase/）。

**依据**：C（DRY/清单卫生）；A（渐进式加载：正文未用的物料不应默认随包声明）。

---

## 统计

| 维度 | 计数 |
|---|---|
| 总发现 | **9** |
| 按严重度 | 🔴必改 **1**（F1）；🟠建议 **3**（F2、F3、F4）；🔵可选 **5**（F5、F6、F7、F8、F9） |
| 按类别 | A **6**（F1-F5、F8）；B **0**；C **3**（F6、F7、F9） |
| 按文件 | api-guard 1；arch-guard 1；contract-guard 1；ddl-guard 3；impact-guard 2；跨技能 1 |

**合规确认（实测通过、无发现）**：
- 渐进式加载：5/5 达标——SKILL.md 均只留流程/门禁/决策点，背景与明细外置（arch-guard→README、impact-guard→DESIGN.md/README、api/ddl→manual-rules）。
- 路径核验：files 清单 254 条目 + 正文全部相对链接 + 跨目录引用（steering 5 篇、docs/design 2 篇、doc-gen 复用脚本 2 个）**0 断链**；arch-guard README 被引章节名「脚本检查覆盖」「需人工补充的规则」实测存在；impact-guard DESIGN.md §2.4 实测存在且标题与正文声明一致。
- 脚本参数：SKILL.md 所写 CLI 旗标（--format/--strict/--init/--refreeze/--baseline/--frozen/--mode graph/--diff/--changed/--skip-reindex/--base 等）逐一与 argparse 源码对上，除 F2 的缺失参数与 F4 的告警字符串外无漂移。
- 交叉一致性：退出码三元组（0/1/2）在 api-guard:47、arch-guard:76、ddl-guard:195 三处重复且语义与 `docs/design/guard-receipt-spec.md:44,56` 对齐；Tier 1/Tier 2、收据（receipt）、五段式术语跨技能一致；`steering/review-report-standards.md` 五段式【强制】含证据边界段（:75-117），各技能引用属实。

---

## 审查中上报事项

1. **基线对账**：HEAD = dfe1732 与任务基线一致，工作树 clean（`git status` 实测），无需漂移披露。
2. **`files:` 字段非手工清单**：实测由 `tools/backfill_skill_manifests.py`（ADR-5）按"该目录全部 git 跟踪文件"程序化回填，门禁只查断链不查多声明。故未按"易腐清单"立案，F9 定性为文件落位问题。
3. **退出码三元组跨技能重复的裁定**：标准 B 要求重复条款收敛单一权威源；本组重复实为技能独立加载所需的合理投影，且权威语义已存于 guard-receipt-spec.md——建议保持现状，不做收敛改动（若强收敛会让技能脱离自包含加载）。
4. **Open API 规则"双源"核实为非重复**：`skills/api-guard/openapi-manual-rules.md` 开篇即回指 `steering/openapi-standards.md` 为设计权威，自身只承载脚本外人工核对清单——单一权威源 + 投影结构成立，与 F1 的 description 矛盾是两回事。
5. **本地运行时产物**：4 个技能的 `scripts/.pytest_cache/` 为 gitignored 本地产物（`git check-ignore` 实测），不入清单、不影响工作树 clean 判定，仅记录。
6. **标准与现状冲突项**：无。本批对象未出现"审查标准与仓内既有写法冲突需原样上报"的情形（F1 为文件内部矛盾，非标准冲突）。
7. **证据边界**：
   - 已验证：5 个 SKILL.md 全文精读；全部引用路径存在性与权限；脚本 argparse/关键字符串静态核对；被引 steering 文档的存在性与被引章节锚点。
   - 未覆盖：脚本功能性运行验证（未执行任何脚本，仅静态读源）；F3 中"6 个依赖方向"的当前实际数值未与 `--mode graph` 输出核对（不影响立案——CLAUDE.md:33 禁令与数值当前真伪无关）；steering 文档正文的逐条精读属并行任务（ar-review-1），本报告仅核实被 SKILL.md 引用的事实。
   - 置信度：全部基于静态阅读与目录实测，行号引自本次实际读取的文件快照。
