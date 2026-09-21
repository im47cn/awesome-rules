# task-flow —— 业务项目内的五阶段任务工作流运行时

> 技能入口见 [`SKILL.md`](SKILL.md)。本文件面向「要用它 / 要改它 / 要搬走它」的人。

## 快速使用

在**用户业务项目根**（不是本仓）执行：

```bash
TF=~/.claude/skills/task-flow/scripts/taskflow.py     # 按实际安装位置替换
python3 "$TF" init --title "订单导出接口重构"           # 生成 .taskflow/ 三层状态
python3 "$TF" status                                  # 只读快照：阶段 / 产物 / 绑定规范
python3 "$TF" advance                                 # 门禁不过就 exit 1，状态不变
python3 "$TF" resume                                  # 跨会话恢复：三层一致性探针
python3 "$TF" audit                                   # 全量重放审计链
```

典型循环：`status` 看下一步 → 写本阶段产物 → `advance`（或先 `verify` 预检）→ 下一阶段。
中断后回来：`resume` 判定能否继续；它报不一致时按其「修复指引」处理，修好前
`verify` / `advance` 一律被拒。

生成物（全部在用户项目 `.taskflow/` 内，本仓不产生运行时状态）：

```text
.taskflow/
├── taskflow.yaml          # 人读层：任务元数据 / 产物声明 / 追加绑定规范
├── run-state.json         # 机器层：阶段 + 每阶段门禁记录（CLI 独占写）
└── state-events.jsonl     # 审计层：追加事件 {ts,event,from,to,detail}
```

`taskflow.yaml` 中可直接编辑的部分：

```yaml
artifacts:                       # 每阶段至少一项；不声明即拒绝推进
  - requirements | doc | docs/taskflow/requirements.md
  - requirements | script | tools/check_requirements.py
specs:                           # 追加绑定（内置绑定不可在此移除）
  - implement | steering/git-conventions.md
```

产物类型：`doc` = 存在且非空；`script` = 在项目根执行到 `exit 0`（超时 300s）。
绑定规范解析顺序：先本仓根，其次用户项目根；两处皆无 = 规范缺失 → 拒绝推进。

## 结构

```text
skills/task-flow/
├── SKILL.md               # 协议：何时用、三层契约、阶段门禁表、命令与退出码、resume 行为
├── scripts/taskflow.py    # 单文件 CLI（纯标准库）：init/status/advance/verify/resume/audit
└── tests/                 # pytest 单测（tmp_path 模拟用户项目）
    ├── conftest.py        # sys.path 注入 scripts/ + GIT_* 环境密封
    ├── pytest.ini
    └── test_taskflow.py
```

组件职责：

- `taskflow.py` 是唯一写者：`.taskflow/` 下所有写入都经过它（JSON 状态用「临时文件 +
  `os.replace`」原子替换；审计事件追加写且只追加）
- 阶段状态机线性无跳阶段：`requirements → design → implement → verify → archive`；
  `archive` 后状态目录只读
- 门禁判定 = 产物（doc/script 校验）+ 绑定规范（存在性）双条件；`advance` 未通过时
  exit 1 且**零写入**（阶段不变、不追加事件）——需要给失败判定留痕时改用 `verify`
  （记录判定 + `gate` 事件，但不推进）
- 事件类型 `init/advance/gate/resume`：只有 `init`/`advance` 改阶段，`gate`/`resume`
  只留痕——`audit` 重放即以此判定转移合法性

自检（在**本仓根**）：

```bash
python3 -m pytest skills/task-flow/tests/ -q     # 单测
python3 tools/check_frontmatter_manifests.py     # M1/M2 frontmatter 门禁（含本技能 SKILL.md）
```

`tools/frontmatter_lib.py` 是模块函数式校验器（无 `__main__` 入口），门禁侧消费者是
`tools/check_frontmatter_manifests.py`。需要对单个技能目录做编程式校验时：

```bash
python3 - <<'PY'
import sys, pathlib
sys.path.insert(0, "tools")
import frontmatter_lib as fl
p = pathlib.Path("skills/task-flow/SKILL.md")
fm = fl.parse_frontmatter(p.read_text(encoding="utf-8"))
print(fl.validate_skill(fm, str(p), p.parent) or "OK")   # 空列表 = 通过（name + files 断链单向）
PY
```

## 已知边界

- **不做执行**：本技能只维护「状态 + 门禁」，不会拆任务、写代码、跑测试、commit；
  产物由使用者（人或 agent）产出，`script` 类产物只被**读取退出码**
- **门禁是自证式的**：`doc` 只校验存在且非空，**不校验内容质量**；`script` 只校验
  `exit 0`——门禁强度取决于你声明的产物脚本有多严
- **单任务单目录**：状态目录固定 `.taskflow/`，一个用户项目同时只跑一个任务流
  （多任务需求不在本技能范围）
- **不自动修复状态**：`resume` 只报告与给指引，不改任何层（避免掩盖漂移根因）；
  审计层本身损坏时需人工确认后修复或整体重建，重建会丢审计链
- **绑定规范靠仓库在场**：内置绑定指向本仓 `steering/`，用户项目里跑时需能解析到
  本仓根（默认取脚本所在仓；可用 `--repo-root` 显式指定，或用 `specs:` 追加项目内规范）
- **yaml 只支持两级子集**（顶层 `key: value` / `key:` + 2 空格块列表或子映射 /
  行内列表）：子集外语法一律拒绝而非静默猜测；复杂 YAML 请精简结构
- **无并发保护**：同一项目并行跑两个 CLI 实例可能互相覆盖机器层——串行使用；
  `advance` 通过后按「机器层 → 人读层 → 审计层」三步写入（各自原子、整体非事务），
  中途失败会留下三层漂移——CLI 会提示 `taskflow.py resume` 复核并按修复指引校正
- 退出码三值：`0` 成功 / `1` 门禁未通过或三层不一致 / `2` 运行错误（用法、损坏状态、
  非法配置）；未知子命令与损坏状态一律 fail-closed 非零退出
- **advance 拒绝 = 零写入（集成裁决）**：门禁失败时不动三层任何一层、不追加事件；
  「失败的判定也留痕」由 `verify` 承担（记录判定与 gate 事件但不推进状态）。
  任务书「任何门禁判定都追加事件」与「拒绝时不改变状态」存在歧义，集成期主会话
  显式采纳零写入语义（实现 taskflow.py:858-866、文档、测试三方一致），特此记录

## 移植说明

- **零依赖**：只用 Python 标准库（`argparse/json/os/re/subprocess/sys/uuid/datetime/pathlib`），
  Python ≥ 3.9；无 `postinstall`、无网络请求、无本仓专有 import——**整个 `skills/task-flow/`
  目录可整体拷贝**到任意位置使用
- **要改绑定规范**：只需编辑 `scripts/taskflow.py` 的 `STAGE_SPECS`（内置绑定）与
  `DEFAULT_ARTIFACTS`（init 默认产物声明）；两者都是模块级常量，改完跑测试即可
- **要改阶段数**：`STAGES` 元组 + `_next_stage`/`_replay` 均以该序为准（线性、末位为终态）；
  `STAGE_SPECS`/`DEFAULT_ARTIFACTS` 按新阶段名调整；测试中的 `DEFAULT_ARTIFACTS` 需同步
- **搬去别仓时**：`tools/check_frontmatter_manifests.py` 属本仓门禁，可不带；带走的
  最小集是 `SKILL.md + scripts/taskflow.py + tests/`
- 状态目录名固定 `.taskflow/`（`STATE_DIR` 常量），与技能的 `--project` 默认值（当前
  工作目录）共同构成「在用户项目内运行」的边界：**在本仓根误跑 `init` 会污染本仓**，
  故本仓的使用约定是显式 `--project <用户项目>`
