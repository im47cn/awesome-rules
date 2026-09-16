# 任务契约：steering frontmatter 覆盖率报告生成器（v2 校准版）

## 目标与反目标
**目标**：交付报告生成脚本 + pytest 测试 + 运行产物报告，供仓库维护者总览 steering/ 全部 .md 的 frontmatter 覆盖情况。
**反目标**（看似成功但不算成功的交付）：
- 表格行数对不上实际文件数（漏扫子目录或漏排序去重，报告"看起来完整"）
- 非确定性输出（依赖 os.listdir 顺序），重复运行 diff 不一致
- 测试断言只查"文件生成了"而不查行内容，缺 title 行的 ❌ 没人验

## 双层验收
**机械验收（由执行方自验，并在交付说明中附最后一次写盘之后真实运行的命令与输出原文）**：
1. `python3 -m pytest tests/test_gen_frontmatter_report.py -q` 全绿（tests/ 目录不存在，可新建）
2. CLI：`python3 tools/gen_frontmatter_report.py [扫描根目录]`（缺省 steering/），生成 docs/reports/frontmatter-coverage.md（目录可新建），markdown 表格：列 = 文件路径、title、scenario、合规与否（缺字段标 ❌）
3. 确定性：文件按路径排序，连续运行两次，两次产物 diff 为空（交付说明附 diff 命令与结果）
4. 负控制（tmp_path 独立构造）：合规、缺 title、无 frontmatter 三种样例，断言报告含 3 行数据且缺 title 行有 ❌
5. 对仓库真实 steering/ 运行一次，报告覆盖全部 16 个文件
**人工验收（主会话终裁）**：负控制是否真为独立样例；排序与转义处理

## 升级触发器（点名受保护面；出现下列事实才中止并上报，其他一切不构成中止）
1. **受保护面被侵犯**：本契约所有权文件 `tools/gen_frontmatter_report.py`、`tests/test_gen_frontmatter_report.py`、`docs/reports/frontmatter-coverage.md` 被本执行方之外的进程创建、修改或删除（含起点时刻已存在同名文件的情形）
2. **关键前提失效**：steering/ 不存在或其 .md 数量 ≠ 16；环境无 pytest

**明示豁免（预期环境事件，不触发中止，仅在交付说明中披露）**：同仓其余任何路径（含 tools/、tests/、docs/ 下与本契约所有权清单不同名的文件）出现并行任务产物或外部变更。本任务在共享工作区与其他任务包并行执行，这是设计而非异常。

## 状态（写协议：本节由执行方独占写入，每完成一个里程碑追加一行，含卡点）
- 起点：全新任务；基线 main commit 9a76f27；本契约所有权三文件在起点均不存在于工作区
- 当前卡点：无

## 约束（enforcement 分级）
- 【gate 强制】pytest 全绿；双次运行 diff 为空
- 【文件所有权】仅可写 tools/gen_frontmatter_report.py、tests/test_gen_frontmatter_report.py、docs/reports/frontmatter-coverage.md；其余路径一律只读
- 【仅文字，预算 1 条】不引入第三方运行时依赖（Python 标准库 + pytest 以内）

## 升级条款
触发器 1 或 2 命中：停止写盘并上报事实，等待重新协商；豁免事件继续执行。禁止以仓库既有实现顺延契约。
