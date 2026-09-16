# 未跟踪文件归属盘点（2026-09-14 执行，供 09-15 晨间验收）

任务来源：open-platform-02 任务书 #2（只读盘点 + 本报告，禁止 commit/push/删除）。
盘点时点：2026-09-14 15:39 UTC（北京 23:39）。HEAD = `02d155e`，与 origin/main 一致。

## 1. 工作区全量状态

`git status --porcelain`：**无任何已修改/已暂存文件**，仅 5 个未跟踪对象。

## 2. 未跟踪文件归属分析

### 2.1 已知归属（awesome-rules-bd 产出，三件成套互证）

| 文件 | 内容摘要 | 归属 | 置信度 |
|---|---|---|---|
| `steering/task-package-standards.md` | 任务包与派发守护规范：五要素骨架、L1/L2 守护分级 | awesome-rules-bd（回报确认） | 高（已知） |
| `tools/dispatch_watch.sh` | L1 记录型派发 watcher，stdout JSONL 事件流，文件头注明"设计依据: steering/task-package-standards.md §2 L1" | awesome-rules-bd（已知+交叉引用自证） | 高 |
| `templates/reviewer-battery.md.template` | L2 事后异构审查提示词模板，注明"配套规范: steering/task-package-standards.md §2 L2" | awesome-rules-bd（已知+交叉引用自证） | 高 |

三件构成"规范 + L1 工具 + L2 模板"完整闭环，处置应整体裁决，不宜拆散。

### 2.2 其余未跟踪对象（本会话推断）

| 对象 | 内容摘要 | 归属推断 | 置信度 |
|---|---|---|---|
| `.factory/metrics/daily-regression.jsonl` | 15 条 JSONL，每日 03:01（+0800）一条，2026-08-29 起至 09-14，layers 全 pass | **定时回归流水线**（launchd/cron 调用已跟踪的 `.factory/regression/daily-regression.sh`）的运行时产出，非任何 AI 会话产出 | 高（时间戳精确到每日 03:01 的机器规律性） |
| `.pi/remote-pi/`（config.json） | `{"agent_name":"awesome-rules","auto_start_relay":true}`，2026-09-02 14:41 创建 | **用户本机 remote-pi relay 基建配置**（与 `~/.claude/sessions` 跨会话消息拓扑配套），非会话产出 | 高（创建时间在会话空档、内容为纯基础设施配置） |

注：`.pi/extensions/awesome-rules.ts` 已被跟踪，不在盘点范围。

## 3. 已修改文件

**无。** 超长会话 a1a63db1 的收尾改动（NC20a–f 负控制 + `md_link_check.py` frontmatter 非空校验）及其他会话在途变更均已随 PR #182–#184 合入并推送，工作树对 HEAD 干净。

## 4. 归属建议表

| 对象 | 推断归属（置信度） | 处置建议 |
|---|---|---|
| `steering/task-package-standards.md` | awesome-rules-bd（高） | **建议纳入提交**：带 title+scenario frontmatter，符合 SessionStart hook 动态扫描惯例 |
| `tools/dispatch_watch.sh` | awesome-rules-bd（高） | **建议纳入提交**：与规范成套 |
| `templates/reviewer-battery.md.template` | awesome-rules-bd（高） | **建议纳入提交**：与规范成套 |
| `.factory/metrics/daily-regression.jsonl` | 定时流水线（高） | **待用户裁决**：运行时指标产物，按本仓"gitignore 是运行时产物排除唯一真相源"哲学应 gitignore；若需留指标历史则改走提交策略，二选一 |
| `.pi/remote-pi/` | 用户本机基建（高） | **待用户裁决**：机器本地 relay 配置（含 agent 名）通常不入库，建议 gitignore；若有意随仓分发则提交 |

## 5. 上报与边界

- 任务书指定文件名 `2026-09-15` 为验收日期（北京时区次晨），执行日实为 09-14，已在标题注明，非笔误不擅改。
- 本报告为纯事实盘点，全部结论可由文中命令复现（`git status --porcelain`、`head`/`tail`、`ls -l` 时间戳）；未派发独立审查子代理（报告无代码逻辑，事实链即审查链），如需对抗性复核可由验收方指定。
