---
name: task-flow
description: >
  业务项目内「五阶段任务工作流运行时」（Comet 式可恢复状态机，本仓哲学适配）。以三层
  状态文件——人读 `taskflow.yaml` / 机器读 `run-state.json` / 追加审计
  `state-events.jsonl`——接管单个编码任务从需求到归档的全过程，阶段推进由门禁产物
  驱动（fail-closed：产物缺失/校验失败/绑定规范缺失即拒绝推进且不改变状态），
  `resume` 做三层一致性探针并给修复指引，`audit` 全量重放审计链校验转移合法性。
  形态为 SKILL.md 协议 + 纯标准库 Python CLI（零第三方依赖、零 postinstall、零网络
  行为）；运行在用户业务项目内，状态落该项目 `.taskflow/`。
  当用户提到：task-flow、taskflow.py、五阶段任务流、任务流状态机、阶段门禁推进、
  推进被拒/fail-closed、恢复任务流、resume 三层不一致、审计状态转移、.taskflow/
  目录时激活。
files:
  - README.md
  - scripts/taskflow.py
  - tests/conftest.py
  - tests/pytest.ini
  - tests/test_taskflow.py
---

# 任务工作流运行时（task-flow）

## 定位

把「一个编码任务的推进过程」变成**可恢复、可审计、有门禁**的状态机：

- **状态可恢复**：会话中断、换 agent、隔天回来，`resume` 一次判定能否继续
- **推进有门禁**：每个阶段的退出产物必须真实存在并通过校验，否则拒绝推进且状态不变
- **过程可审计**：每次阶段变更、落盘的门禁判定（`verify` 判定与通过推进）与恢复动作追加一行事件，`audit` 可全量重放

本技能在本仓的落地原则（对齐 `docs/research/comet.md` 借鉴点 #5，并遵循本仓
「内容库而非运行时安装器」的形态约束）：

- 只吸收**状态分层 + 门禁 + 恢复**机制；不做意图分类路由（六值路由与本仓二值
  哲学冲突，调研已否决），不做任务调度、不自动改代码、不自动提交
- 纯标准库实现，零第三方依赖、零 postinstall、零网络行为
- 状态文件只落**用户业务项目**的 `.taskflow/`；本仓自身不产生运行时状态

## 何时使用

- 用户项目里有一个明确的编码任务，且需要跨会话/跨 agent 交接的阶段状态
- 需要 fail-closed 的阶段性门禁（产物 + 绑定规范双条件校验）作为推进依据
- 上一位执行者中断，需要判定「现在这个任务流处于什么阶段、能否继续」

## 何时不用

- 单次问答、一次性脚本改动（无状态需求）
- 本仓自身的维护任务（本仓不写运行时状态）
- 期望自动完成任务拆分、自动写代码、自动 commit 的场景（本技能只做状态 + 门禁）

## 三层状态（契约）

| 层 | 文件（用户项目 `.taskflow/`） | 内容 | 写者 |
| --- | --- | --- | --- |
| 人读层 | `taskflow.yaml` | 任务元数据（id/标题/创建时间/当前阶段）、阶段产物声明 `artifacts:`、追加绑定规范 `specs:` | `init` 生成；`advance` 同步 `stage:` 行；其余行可人工编辑 |
| 机器层 | `run-state.json` | 单写者状态：当前阶段、进入时间、每阶段门禁记录（结果 + 逐项明细 + 时间戳） | 仅 CLI 写入（手工编辑 = 漂移源） |
| 审计层 | `state-events.jsonl` | 追加写事件 `{ts, event, from, to, detail}`；`event ∈ init/advance/gate/resume` | 仅 CLI 追加 |

一致性铁律（`resume` 逐条校验）：`yaml.stage == run-state.stage` 且
`jsonl 最后一条转移事件（init/advance）的 to == 当前阶段`，外加任务身份
（`yaml.task.id == run-state.task_id`）不漂移。任一条不成立即 `resume` 非零退出，
并给出「以审计层为事实源」的修复指引。

## 五阶段与门禁

| 阶段 | 默认退出产物（`init` 写入 `artifacts:`） | 绑定规范（内置，不可由 yaml 移除） |
| --- | --- | --- |
| requirements | `docs/taskflow/requirements.md` | — |
| design | `docs/taskflow/design.md` | `steering/database-design-specification.md`、`steering/api-contract-freeze-standards.md` |
| implement | `docs/taskflow/implementation.md` | — |
| verify | `docs/taskflow/verification.md` | `steering/testing-standards.md` |
| archive | —（终态：状态目录只读） | — |

产物校验方式（`artifacts:` 条目第三列类型）：

- `doc`：相对项目根解析 → 存在 + 非空
- `script`：在项目根以当前 Python 解释器执行 → `exit 0`（超时 300s；失败时取
  stderr/stdout 摘要 160 字入门禁明细）

绑定规范解析顺序：先本仓根，其次用户项目根；两处皆无 → 门禁判定「规范缺失」→
拒绝推进。追加绑定：在 `taskflow.yaml` 的 `specs:` 里写 `- 阶段 | 相对路径`。

## 命令

| 子命令 | 作用 | 退出码 |
| --- | --- | --- |
| `init [--title T] [--id ID]` | 生成三层状态（`.taskflow/` 已存在则拒绝，防覆盖） | 0 / 2 |
| `status [--format json]` | 只读快照：阶段、三层对账、当前阶段产物与上次判定、绑定规范解析情况、下一步 | 0 / 1 / 2 |
| `verify [--format json]` | 只求值门禁并记录判定，**不推进** | 0（通过）/ 1（未通过）/ 2 |
| `advance` | 求值门禁 → 通过则写机器层、同步 `stage:` 行并追加事件；不通过则**零写入**（三层文件均不变） | 0 / 1 / 2 |
| `resume [--format json]` | 三层一致性探针：一致输出可继续指令（非终态追加 `resume` 事件）；不一致非零退出 + 修复指引 | 0 / 1 / 2 |
| `audit [--format json]` | 全量重放 `state-events.jsonl`：非法转移、事件字段损坏逐行报告 | 0 / 1 / 2 |

全局选项置于子命令之后：`--project DIR`（默认当前目录）、`--repo-root DIR`
（默认脚本所在仓，用于解析内置绑定规范）。

退出码语义：`0` 成功/门禁通过/三层一致；`1` 门禁未通过/三层不一致；`2` 运行错误
（用法非法、状态文件缺失或损坏、配置非法）。未知子命令与损坏状态一律 fail-closed
非零退出，错误信息为中文。

## resume 行为（跨会话恢复）

1. 三层一致 + 非终态 → 打印「当前阶段 + 下一步指令」，追加 `resume` 事件（`gate`
   与 `resume` 事件不改阶段，仅留痕）
2. 三层一致 + `archive` → 提示终态只读，**不追加任何事件**（保持只读语义）
3. 三层不一致 → 非零退出，列出各层当前值与问题，并给出修复指引（先 `audit` 确认
   审计层合法；以审计层末事件为事实源校正 yaml/run-state 的 `stage`；审计层本身
   违规时人工确认后修复 jsonl 末行或整体重建——重建会丢审计链，须在任务说明中记录）
4. 不一致期间 `verify` / `advance` 一律被拒（fail-closed），直到 `resume` 复核通过

## fail-closed 纪律

| 情形 | 行为 |
| --- | --- |
| 官方门禁未通过（产物缺失/为空、脚本非零、规范缺失） | `advance` exit 1 且**零写入**（阶段不变、不追加事件）；需要给失败判定留痕时改用 `verify`（记录判定 + `gate` 事件，不推进） |
| 阶段未声明任何产物 | exit 2（拒绝空门禁，防「无检查推进」） |
| 三层不一致 | `resume` exit 1；`verify`/`advance` exit 2（先修后动） |
| 状态文件缺失/非法 JSON/事件行损坏/yaml 子集外语法 | exit 2，中文错误指明文件与行号 |
| `archive` 之后 | 一切推进/门禁写入被拒（状态目录只读） |
| 未知子命令 | exit 2 + 用法 |

## 不做的事

- 不自动修复状态：探针只报告与指引，不替用户改文件（避免掩盖漂移根因）
- 不自动 commit / 不碰用户代码：门禁只读产物、只写 `.taskflow/`
- 不联网、不装依赖、不写本仓状态
