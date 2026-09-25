# 2026-09-24 规范/技能文档全量审查（herdr 8 路并行）

- 方式：herdr 8 pane × omp headless，全只读；基线 dfe1732（中期漂移至 3536e53，各报告披露，结论不受影响）
- 发现：104 条 = 🔴7 / 🟠50 / 🔵47，明细见同目录 ar-review-{1,2a,2b,3,4,5,6,7}.md
- 主题聚合：①【强制】机械检查性缺口 ~15 条 ②易腐数字 ③重复条款漂移 ④跨文档矛盾 ⑤死引用 ⑥frontmatter 质量（inclusion 死字段 ×6 等）

## 🔴 裁决与执行（S1–S7，2026-09-24 仓主终裁）

| # | 发现 | 裁决 | 执行 |
|---|---|---|---|
| S1 | `.factory/decisions.md` 死路径+扩散 | 彻底清理 | task-package-standards:54 + docs/design 2 文件 6 处改指 docs/adr/；历史档案（adr/README 迁移自述、audit-c/d、P3 任务包）保留原文 |
| S2 | git-sealing 门禁已落地但文档零引用 | 定仓级约定 | CLAUDE.md 新增「门禁留名约定」；testing-standards 密封性节补机器执行层行 |
| S3 | 一致性守护双副本漂移 | 顺手加 | 合并 L29-30；文件头加单一权威源纪律声明 |
| S4 | 禁止事项列表格式损坏 | 只修格式 | 2 处非列表项行首修复（`❌ ❌ -`/`❌ -` → `- ❌`）；**否决项：不加 linter（一次性事故，不值得常驻门禁）** |
| S5 | api-guard description 与正文矛盾 | 收窄 | 删 openapi 人工核对分支，路由指针改指 steering/openapi-standards.md；删除 openapi-manual-rules.md（系 steering 逐字投影，零信息损失）；manifest 重生成。注意：audit-d D-11 的「openapi 兜底记账」诉求由 steering 正文承接 |
| S6 | sourcery 清零判定漏 --config | 直接修 | 两处补 `--config .sourcery.yaml`（与 gate 口径一致） |
| S7 | 「165+ 工具」易腐计数 | 连门禁一起接 | 4 处文本改实时口径；check_doc_freshness 新增 R12（工具计数禁令）+ NC23/NC23b 负控制；R12 首跑净检出 tokensave-mcp 3 处存量（~100 个工具）一并收敛。**15k/1.2k/20k token 等带日期实测成本保留** |

## 否决沉淀

- S4 linter：否决理由=一次性编辑事故，常驻门禁性价比为负；复发 2 次以上再立项
- S1 md_link_check「旧路径零残留」规则：未采纳（本次人工清理+审查报告留档）；若再发迁移类死引用事故，按 CLAUDE.md「优先接线」补规则

## 待裁决积压（本轮未处理）

- 🟠50 / 🔵47 条按主题打包待裁：inclusion 死字段 ×6 文件（删除 vs 实装语义）、机械检查性标注句式统一、跨文档矛盾（gtsp F1-F7、del_flag 口径）、DRY 收敛（含 CLAUDE.md:31 herdr 模板补 `< /dev/null`）、plugin.json 计数漂移（README:49 已登记待人工 PR）

## 第二批裁决（2026-09-25，🟠 四主题簇，仓主全部批准）

| 簇 | 裁决 | 执行 |
|---|---|---|
| C1 inclusion 死字段 | 批量删除 | 6 文件删除（review-report 为 manual 取值）；CONTRIBUTING.md 改「已废除，禁止新增」 |
| C2 机械检查性 | 全量补标注 | testing F9 四处 + git-conventions F2/F3 文档侧标注 + CRAP≥30 改「落点=消费仓」标注 + gtsp F5/F6 + openapi OA-3 三处（:46 枚举传值/:71 HTTP 200/:160 只增不删）+ task-package F4 六节 enforcement 后缀 + review-report F9 三处 + frontend F11 头部执行承接声明 + code-review/sourcery/skill-evo F-05 脚注（复审🟠-1 补齐）；gtsp F7 其余 7 项接线列 backlog |
| C3 跨文档矛盾 | 六条直接执行 + del_flag 选 A | gtsp F1/F2（:173 与 :64 树同步补 enum，:64 系超出报告范围的主动一致性补齐）/F4/F5/F6、FZ-1、review-report F8；del_flag 口径 A=业务表必含+日志流水豁免，steering 三处收敛 |
| C4 DRY | 必修+顺带 | CLAUDE.md:31 herdr 模板补 `< /dev/null`；:30 压缩为 §3 指针；testing F4/F5/F6 改节名指针；review-report F7 基线声明与核实细则拆分、术语统一「现状类」；R7 F4 mcporter 单源化降级 backlog（daemon 形态未实测） |

### del_flag A 脚本接线

- `ddl_check.py` 新增 `check_del_flag_required`（规则名「逻辑删除字段缺失」，MANDATORY，独立于既有「必含字段缺失」以零波及存量测试；等价别名 delete_flag/is_deleted/is_del/deleted 计入存在性）
- 单测 4 例（业务表缺/含/等价别名/日志表豁免），181 passed（覆盖率 96.15%）
- badcase 075-atomic-del-flag-required（红控制实跑：唯一检出=逻辑删除字段缺失）
- ddl-manual-rules.md 第 7 条同步「均已脚本化」

### 仍未处理（backlog）

- gtsp F7 剩余 7 项 gauntlet 接线（命中率证据不足，盲接线违反负控制纪律）
- R7 F4 mcporter 三件套单源化（需先实测 daemon --stdio 形态）
- DB-1 机械部分：ddl_check.py 增同名 CREATE TABLE 检测 + 负控制
- frontend F11 可机械项的目标仓 CI 片段落地（本批只落头部执行承接声明）
- review-report F9 的 eval 负控制用例（「报告缺证据边界段」）
- 🔵 47 条风格类建议（默认放弃，仓转对外发布物时升格）

### 第二批复审闭环（2026-09-25）

独立复审（/tmp/ar-fix2-review-out.md 已归档）：🔴0 / 🟠2 / 🔵2，四条全部当场修复——
🟠-1 C2 全量口径补齐（openapi 其余两处 + task-package/review-report/frontend/F-05 标注）；🟠-2 CLAUDE.md:30 指针空洞（task-package §3 富化「边界外残留主会话收口」+「已写盘交集判定」两段语义后指针成立）；🔵 testing 退出码语义括注、ddl-manual-rules 行尾换行。
