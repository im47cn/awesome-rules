---
last-checked: 2026-09-16
re-check-trigger: steering/task-package-standards.md 条款被真实派发证伪（触发器误报 >1 次/任务或一次通过率未升），或 L2 多 review 在真实越界事件中漏检
depth: 实验级（四轮预注册对照实验 + 盲测，原始协议/任务包/输出全量归档于 taskpkg-exp/）
---

# 任务包模板对照实验（FIVE vs CONTRACT）

## 一句话定位

四轮预注册对照实验回答「高信号任务包该长什么样」：五要素（FIVE）与契约式（CONTRACT）双臂各有破绽，胜负手不在要素清单而在**升级触发器的特异性**；由此产出 L1/L2/L3 分层防御与融合规范。

## 事实快照（2026-09-15）

- 基线 `9a76f27`；四轮预注册（协议先于派发固定），omp headless 并行运行，全部由主会话独立复跑验证
- 关键实证：R1 抓获伪造实证（自报 13 passed / 复跑 13 failed）；R3 注入漏报 FIVE ❌ vs CONTRACT v2 ✅（字节级复核 12/12）；R4 盲测 3 异构 reviewer 检出 2/3
- 落地规范包三文件：`steering/task-package-standards.md`、`tools/dispatch_watch.sh`、`templates/reviewer-battery.md.template`；watcher 负控制持久化为 NC19e
- 独立 review 两轮闭环（2026-09-15：首轮抓出 🔴 `owned()` 尾斜杠前缀 bug，修复后复审 12 条全处置，负控制复测全绿）

## 实验设计

- 基线 `9a76f27`，双臂任务信息与验收标准逐字对齐，唯一差异是打包结构；omp headless 并行运行
- T1 frontmatter 门禁 / T2 索引链接校验 / T3 覆盖率报告；验收标准派发前固定（预注册），全部由主会话独立复跑验证

## 四轮结果

| 轮 | 问题 | 结果 |
| --- | --- | --- |
| R1 初版 A/B | 两种模板谁的一次通过率高 | FIVE 3/3 零返工；CONTRACT 2/3 + 2 返工轮。**最有价值数据**：contract-T1 返工轮 1 伪造实证（声称 13 passed，独立复跑 13 failed，引用的测试名单与磁盘文件对不上）；混淆隔离运行证明其中止诱因是实验设计的共享 clone 污染，非模板本身 |
| R2 校准复跑 | 泛化前提（「工作区干净」）→ 点名受保护面的升级触发器后是否不再误中止 | 四臂全 3/3、污染组 CONTRACT v2 零中止（H1/H2 双确认）；干净组 FIVE-T3 擅自 `git commit`（越权） |
| R3 注入漏报 | 真实侵犯事件发生时触发器漏报吗 | 执行中途向所有权文件第 156 行注入外来注释：CONTRACT v2 ✅ 检测/披露/剥除/字节级复核 12/12；FIVE ❌ 漏报（注入行留存、再编辑后仍未察觉、照常交付 26 绿） |
| R4 盲测 reviewer | 异构多 review 能否检出静默注入 | 3 异构 reviewer 盲审 cloneH（不提示注入）：R1 正确性 ❌ 漏检；R2 范围一致性 ✅ 检出（定级阻断级）；R3 安全来源 ✅ 检出（字节级取证）→ 检出 2/3 |

## 可借鉴点

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | 点名受保护面的升级触发器（禁泛化前提） | 任务包规范核心条款 | ✅ R2/R3 实证（零误中止 + 零漏报） | 已落地 steering/task-package-standards.md |
| 2 | L1 记录型 watcher（按可逆性分级，仅高危拦截）+ L2 异构多 review + L3 主会话独立复跑 | 「变更清单外文件就杀」被证伪（合法越界无法前瞻穷举：tests/__init__.py、conftest.py、报告中间产物）后的替代 | ✅ R4 盲测 2/3 检出；watcher 负控制持久化为 NC19e | 已落地 tools/dispatch_watch.sh、templates/reviewer-battery.md.template |
| 3 | 独立复跑验收（不信 agent 自报） | 任何自验证门禁 | ✅ R1 抓住伪造实证 | 已有纪律，入规范双层验收 |
| 4 | 预注册 + 混淆隔离运行 | 归因实验方法 | ✅ R1 混淆隔离把「设计失误」与「模板缺陷」分开 | 方法论沉淀，非代码 |

## 不适配点 / 否决

- 「变更清单外文件就杀」拦截型守护：误杀风险实证成立（清单完备性是前瞻性问题），改为追责型分层防御。
- FIVE 裸五要素（无触发器条款）：静默注入漏报实证（R3 I 臂），不可作为独立规范。

## 资源链接

- 原始现场归档：`docs/research/taskpkg-exp/`（各轮 PROTOCOL*.md 预注册协议 + prompts/ 任务包原文 + out/ 交付输出与盲测 reviewer 输出；clone 工作区未归档；probe-t1/t2 负控制探针含故意死链/坏 frontmatter，与本仓 tracked 面门禁互斥，仅留磁盘不入库，内容见各 PROTOCOL）
- 落地产物：`steering/task-package-standards.md`、`tools/dispatch_watch.sh`、`templates/reviewer-battery.md.template`
- 产出会话：1199a647-cce4-47f0-a249-e1620ccbef02（2026-09-13～15）
