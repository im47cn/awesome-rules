# code-review — 两轴代码审查

对 diff 做两轴并行子代理审查：**Standards**（规范轴：仓库书面标准 + 坏味道
基线）与 **Spec**（规格轴：MR 标题/工单/PRD 对照），聚合时抽验事实断言，
按 [审查报告输出规范](../../steering/review-report-standards.md) 五段式输出。

## 上游参考源（定期对齐）

本技能 fork 自 [mattpocock/skills](https://github.com/mattpocock/skills) 的
`code-review`（MIT，两轴+并行子代理设计的原始出处），演进已分叉：本版叠加了
可证伪性条款、结构化输出契约、交付恢复、聚合抽验环、云效适配与五段式报告
对齐，与上游不保持文件级同步。

定期（季度或上游大版本）参考以下两个上游的演进，评估值得吸收的设计：

| 上游 | 地址 | 关注点 |
|---|---|---|
| mattpocock/skills | https://github.com/mattpocock/skills | 两轴流程本源；规格源识别、smell 基线的演进 |
| claude-plugins-official code-review | https://github.com/anthropics/claude-code 下 `plugins/code-review` | 官方多代理置信度 PR 审查；置信度过滤误报的机制设计 |

对齐时保持本仓库约束：单一数据源（本目录），不回拷文件覆盖；吸收的设计
先落 badcase 验证再合入。

## 快速使用

对话中说「审查 PR #167」「review since origin/develop」「帮我审一下这个分支」
即可触发。支持 GitHub（`pr://N`、`gh`）与云效 Codeup（走
[alibabacloud-devops](../alibabacloud-devops/SKILL.md)，mcporter 动态查询）。

## 与上游版本的差异

本技能源自社区两轴审查技能（Matt Pocock 风格），经 2026-08-24 云效 MR #167
（woa 仓库，超时配置重构 + 策略工厂修复混装）实测后深度重构，六项改进：

| # | 改进 | 防的问题（实测教训） |
|---|---|---|
| A | 子代理可证伪性条款：否定性断言必须全仓 grep 附证据 | 子代理只看 diff 就断言「station.timeout 是死配置」，实际 4 个类仍在消费 |
| B | 结构化 outputSchema（findings[] + severity/confidence/verified） | 两子代理一散文一 JSON，聚合需人工对齐 |
| C | 输出契约：禁止占位符/空增量 yield | 子代理最终交付退化为字面量 `"..."`，报告只存于 transcript |
| D | 交付恢复：先 `history://` 考古再重派 | 子代理断连 exit 1 后盲目重派成本 3 分钟+，考古秒级恢复 |
| E | 聚合抽验环：可 grep 断言逐条核证，未通过附修正标注 | 错误发现照登会诱导删除仍被消费的配置键，致三环境超时静默回退 |
| F | 托管平台适配：remote 识别 → GitHub/云效分支处理 | `pr://` 对 Codeup 无效；skill 原假设 GitHub 工作流 |

另有输出对齐：聚合报告遵守 steering 审查报告五段式（结论先行 + 证据边界强制段）。

### G — 可视化输出（2026-08-24 gtsp-wop-service 审查沉淀；08-26 转默认）

聚合报告默认附 mermaid 时序图并标记技术风险点（无调用交互的 diff
声明免图，不硬造）：
参与者按架构分层，风险 `Note over` 钉在确切触发消息上（全局编号与正文
共用），已验证防线（行锁/CAS/事务）用 ✅ 同标。实测教训两条入档：
① 图比文字更易被当成事实——落图前必须过聚合抽验环（初判「8 域未发事件」
被全量 grep 推翻为 4 域有事件，误报若落图会随图扩散）；② sequenceDiagram
的 `Note` 文本含半角分号会截断解析，交付前 `mmdc` 逐块渲染验证。
画法与语法坑详见 [visual-output.md](visual-output.md)。

## 检查覆盖

- Standards 轴：仓库书面标准（AGENTS.md / CONTRIBUTING / .editorconfig /
  steering）+ Fowler 坏味道基线 12 条（判断性，仓库标准覆盖基线）
- Spec 轴：规格断言逐条核对、scope creep、实现疑点（单位/语义静默变化/默认值漂移）
- 聚合：分轴呈现不合并排序、跨轴不选唯一赢家、事实断言抽验
- 可视化输出（默认）：跨层链路 mermaid 时序图、风险 Note 定位、
  证据链核查环、增量图维护（见 [visual-output.md](visual-output.md)）


## 相关文件

- [SKILL.md](SKILL.md) — 技能定义（AI 入口）
- [steering/review-report-standards.md](../../steering/review-report-standards.md) — 输出结构规范（五段式/证据边界）
- [skills/alibabacloud-devops](../alibabacloud-devops/SKILL.md) — 云效 MR 查询依赖
- [visual-output.md](visual-output.md) — 可视化审查输出（时序图画法/风险标注/语法坑）
