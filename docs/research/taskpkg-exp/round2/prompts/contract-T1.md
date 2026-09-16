# 任务契约：steering frontmatter 字段校验脚本（v2 校准版）

## 目标与反目标
**目标**：交付校验脚本 + pytest 测试，供本仓库 CI 门禁调用，校验 steering/ 全部 .md（含 gtsp/ 子目录）frontmatter 含非空 title 与 scenario。使用者是仓库维护者与 CI 流水线。
**反目标**（看似成功但不算成功的交付）：
- 只校验字段存在、不校验非空（`title:` 后空白照样放行）
- 用脆弱正则解析 frontmatter，遇多行值或含冒号值误判
- 测试依赖仓库真实文件而非独立构造样例，文件一变测试就飘

## 双层验收
**机械验收（由执行方自验，并在交付说明中附最后一次写盘之后真实运行的命令与输出原文）**：
1. `python3 -m pytest tests/test_check_frontmatter_fields.py -q` 全绿（tests/ 目录不存在，可新建）
2. CLI：`python3 tools/check_frontmatter_fields.py [路径...]`（缺省 steering/）。每个违规文件输出一行 `路径: 缺失字段`；全部合规 exit 0；存在违规 exit 1
3. 负控制（tmp_path 独立构造）：缺 title、缺 scenario、空 frontmatter、无 frontmatter 四种情况均 exit 1；正控制：合规样例 exit 0
4. 对仓库真实 steering/ 运行一次，报告 exit code 与违规清单（此项仅上报，不计成败）
**人工验收（主会话终裁）**：负控制是否真为独立样例；frontmatter 边界处理是否合理

## 升级触发器（点名受保护面；出现下列事实才中止并上报，其他一切不构成中止）
1. **受保护面被侵犯**：本契约所有权文件 `tools/check_frontmatter_fields.py`、`tests/test_check_frontmatter_fields.py` 被本执行方之外的进程创建、修改或删除
2. **关键前提失效**：steering/ 不存在或其 .md 数量 ≠ 16；环境无 pytest

**明示豁免（预期环境事件，不触发中止，仅在工作区披露中记录）**：同仓其余任何路径（含 tools/、tests/、docs/ 下与本契约所有权清单不同名的文件）出现并行任务产物或外部变更。本任务在共享工作区与其他任务包并行执行，这是设计而非异常。

## 状态（写协议：本节由执行方独占写入，每完成一个里程碑追加一行，含卡点）
- 起点：全新任务；基线 main commit 9a76f27；本契约所有权两文件在起点均不存在于工作区
- 当前卡点：无

## 约束（enforcement 分级）
- 【gate 强制】pytest 全绿；CLI exit code 语义正确
- 【文件所有权】仅可写 tools/check_frontmatter_fields.py 与 tests/test_check_frontmatter_fields.py；其余路径一律只读
- 【仅文字，预算 1 条】不引入第三方运行时依赖（Python 标准库 + pytest 以内）

## 升级条款
触发器 1 或 2 命中：停止写盘并上报事实，等待重新协商；豁免事件继续执行。禁止以仓库既有实现顺延契约。
