# 仓库合规审查报告 · 2026-09-20（herdr 四维并行）

基线：`origin/main @ 135b829`（已含 PR #203 复用两层判定、PR #206 覆盖率预算棘轮），审查工作树
`/tmp/ar-audit` 全程只读，收尾 `git status --short` 为空。主会话对四份维度报告
（归档于本目录 `audit-{a,b,c,d}.md`）做了阻断级全验、关键引用抽验与跨源去重。

维度分工（按缺陷类型切分）：A 规范自洽性 ｜ B 脚本与工具健壮性 ｜ C 文档-事实一致性 ｜ D 门禁覆盖度。
原始计数：A 18 条 + B 7 条 + C 4 条 + D 12 条 = 41 条；跨源去重合并 5 条（A-R02≡D-03/D-04、
A-R03≡D-05、A-R10≡C-1、A 上报转报≡C-2、B-2 关联主会话独立发现 F-0）→ **去重后 36 条**：
🔴 1 ｜ 🟠 12 ｜ 🟡 23。

## 1. 结论先行

这是一个「门禁资产丰富但存在两处活性断裂 + 规范文本系统性双事实源」的仓：
- 🔴 **1 条活性阻断**：commitmsg-check.sh 在 stock macOS 下崩溃阻断提交（已端到端实测）；
- 🟠 **最高优先**：昨日 E2E 已验证的 coverage.sh 两项修复**滞留 feature 分支未合入 main**（合并在两次推送之间发生）；
- 🟠 **系统性病灶**：规范文本 5 处整段逐字重复（双事实源），单侧修订即自相矛盾；
- 🟠 **门禁覆盖断层**：3 处「规范强制、门禁无人认领/明示放弃」（触发器/存储过程、openapi 枚举、09-cr-checklist 全清单）；
- 其余 🟡 为守卫外活计数、文档漂移与健壮性加固项。

## 2. 依据（违反的不变量）

- CLAUDE.md:36「标注强制的条款应同步评估可机械检查性：能查出的配 gauntlet 静态门，门禁查不出违规的强制条款只靠人记，效力弱」→ D-02/D-10/D-11 违例
- CLAUDE.md:32「文档不写易腐数字…此类存量陈述由 doc-freshness 门禁守护」→ C-1/C-3/C-4 守卫空白
- install.sh:50-51 自身记录「变量后紧跟全角字符须用 `${}` 界定」→ B-1/B-2/B-3 违例（范式在案而未全量执行）
- CLAUDE.md「commit 即 push（小步快推，禁止攒批）」流程纪律 → F-0 修复滞留即其后果面

## 3. 证据 + 建议（仅列 🔴/🟠，🟡 见维度归档报告）

### F-0 🔴→🟠｜coverage.sh 已验证修复滞留 feature 分支，main 带伤运行
`origin/main` 的 coverage.sh 停在 `86679da`；`8edc293`（全角花括号×4）与 bp 除零修复仅在
`origin/feat/coverage-budget-gate`（PR #206 在两次推送之间被合并截胡）。main 现存
:184/:225/:235/:241 四处 `$var` 紧邻全角字符——macOS bash 3.2 + UTF-8 下预算生效路径与
红线失败路径均会 unbound variable 中止（虚假阻断 push / 诊断不可见）。
**建议**：`git cherry-pick 8edc293 <bp-fix>` 到新分支提 PR 补合（已过 E2E 四场景验证，见
memory project_coverage_sh_e2e_harness）。

### F-1 🔴｜tools/git/lefthook/commitmsg-check.sh:27 — 放行路径在 macOS 默认环境不可达
`（$CL）` 在 bash 3.2 + UTF-8 下报 `unbound variable` rc=1，`exit 0` 放行分支永远执行不到 →
**commit-msg 钩子拦截一切提交**，且发生在「已安装但未定位到可执行文件」这一纯环境问题上，
违反脚本自身 :5 头注原则。主会话已独立复现（机制级 rc=1 实测；agent B 另有端到端 stub 复现）。
**建议**：改 `（${CL}）`（与 install.sh:52 既有范式一致）。

### F-2 🟠｜规范文本 5 处整段逐字重复（双事实源族）
- CLAUDE.md:36≡39、38≡41（≡ D-03/D-04）
- steering/review-report-standards.md:18-25≡43-50、30/31/33≡56/58/59（八行整段两份）
- steering/git-conventions.md:96≡103、97≡105、99≡106（三条纪律各两份）
- steering/openapi-standards.md:154≡155（≡ D-05）
- steering/gtsp/01-project-structure.md:16≡17
全部以 `diff` 输出为空程序化确认 + 主会话亲验。**建议**：各保留一份，一次清理提交；注意
CLAUDE.md 去重后行号移位会波及 D 维矩阵引用。

### F-3 🟠｜README.md:73 gtsp 维度文件计数 10 ≠ 实际 9（≡ C-1/A-R10）
枚举 10 个维度名但 01-09 仅 9 个文件（「项目结构、分层架构」实为同一文件）。自创建起未校正，
doc-freshness 无守护面。**建议**：按 CLAUDE.md:32 改自证命令式（`ls steering/gtsp/0*.md`）。

### F-4 🟠｜skills/alibabacloud-devops/SKILL.md:90 以现在时引用已退役 `.factory/forge`
forge 已随 ADR-007→ADR-008 退役（`ls .factory/ | grep -c forge` = 0），运行时操作文档仍指路。
**建议**：改述历史形态并指向 hosting 抽象层。

### F-5 🟠｜D-02：触发器/存储过程【强制】禁令被 ddl_check.py 明示放弃检出
ddl-manual-rules.md:34「脚本只解析 CREATE TABLE」；一行大小小写不敏感 grep 即可拦截，千余行
解析器已在的前提下留给人工。**建议**：ddl_check.py 增全文级 `CREATE TRIGGER/PROCEDURE` 扫描 +
负控制（M029 惯例）。

### F-6 🟠｜D-11：openapi 规范唯一【强制】条款「规范强制、门禁无人认领」
api-guard SKILL.md:8 明确排除 Open API 范范，且无 openapi-manual-rules.md 记账——与 ddl/sql/api
三处 manual-rules 显式记账惯例不一致。**建议**：补 manual-rules 记账（零代码）或 api_check.py
增枚举校验。

### F-7 🟠｜D-10：09-cr-checklist 35 个强制标记行零机械可检查性标注
其中 M046（@Resource）/M055（@PostMapping）/M062（@Slf4j）/M061（del_flag=0）为纯文本模式，
可低成本接线。**建议**：按 api/ddl manual-rules 模式逐条标三态，先接 4 条纯文本项。

### F-8 🟠｜D-01：pre-commit 两道门禁（coverage-light、spec-check）文档缺位
CONTRIBUTING 只记 commit-msg 与 pre-push；唯一记载是 lefthook.yml 注释。
**建议**：CONTRIBUTING 补条目 + doc-freshness 增 R10 同步防线（D-07）。

### F-9 🟠｜A-R06：「禁止顺延」三处口径需对齐
task-package-standards:36（含所有权顺延） vs :54（仅指架构形状级） vs
templates/task-brief.md.template:18（含架构/所有权/历史原因）。**建议**：以 §1.6 两层判定为准
统一三处措辞边界。

### F-10 🟠｜A-R07：Javadoc 约束力口径矛盾（08【必须】vs 09【推荐】）
08-comments-deprecated:12/20 vs 09-cr-checklist:68/69 对同类要求标注强度相反，Entity 范围不对齐。

### F-11 🟠｜A-R08+R18：commit-template.txt 计数与阈值双错
:7「7 个标识」实为 9；:21「不超过50个字符」vs conventions/commitlint 的 100。同文件同次修。

## 4. 关联

- F-0 与 F-1 同根因（全角邻接，B 维扫描 7 命中全量在案）；修复后建议将「分发脚本 bash 3.2 实测」
  与全角扫描接入 gauntlet（B-6 已指出 tools/git/ 9 个分发脚本不在 syntax/lint 门内——两处断裂
  恰都在该未门控集合内，构成因果链）。
- F-5/F-6/F-7/F-8 同属 CLAUDE.md:36 元规则执行落差（D 上报事项 1）；F-3/F-4 属 doc-freshness
  守卫空白（C-3/C-4 同类）。
- B 上报 R1（testing-standards:261 fail-closed 条款 vs 分发钩子 fail-open 设计的适用边界冲突）
  需人工终裁，影响 F-1 修复时是否同时补 set -e。

## 5. 证据边界

── 证据边界 ──
  已验证: 基线/只读对账（4/4 维度双轮 status 空）；🔴 F-1 机制级亲复现（bash 3.2 rc=1）；
    F-0 cherry-pick 缺失以 branch --contains 亲验；F-2 五处 diff 亲验；F-3/F-4/F-5/F-6
    关键行亲读；B 维全角扫描/shellcheck/python 入口模式全量程序化；D 维 121 强制标记行
    程序化枚举+负面空间验证；C 维 427 计数命中逐条裁决、151 相对链接 100% 验证。
  未覆盖: AGENTS.md/docs/design/docs/research 内容审查（A 维范围外）；hooks/omp/skill-evo.ts
    未深审；四个千行自测脚本仅 bash -n + 抽样；D 维 4 项待验证（M079 ENGINE 校验、CI 工作流
    条款级记载、owner_check/release_guard 定位、门禁参数条款出处）；skills/README.md 不匹配
    C 维范围 glob 未审；受影响人群统计（bash 3.2 存量比例）未做。
  置信度: 🔴/🟠 全部经主会话亲验或双源交叉（V1/V2）；🟡 采信维度报告原文（V2/V3），
    修复前请按各归档报告的复现命令回源核验。B 维声明 claude-mem 注入的并行观察流未采信为证据。

## 附：处置优先级（推荐降序）

1. F-1（1 行修复，活性阻断）+ F-0（cherry-pick 两个已验证 commit）——可同分支一次 PR
2. F-2 重复块清理（5 文件一次提交，注意行号移位联动）
3. F-5/F-6（最小接线/记账，闭环元规则落差）
4. F-3/F-4/F-11（文档事实修正）+ B-6（分发脚本入门禁）
5. F-7/F-8/F-9/F-10（结构化改进，需人工终裁 B 上报 R1 后统一）
