# 任务契约：steering frontmatter 覆盖率报告生成器

## 目标与反目标
**目标**：交付报告生成脚本 + pytest 测试 + 运行产物报告，供仓库维护者总览 steering/ 全部 .md 的 frontmatter 覆盖情况。
**反目标**（看似成功但不算成功的交付）：
- 表格行数对不上实际文件数（漏扫子目录或漏排序去重，报告"看起来完整"）
- 非确定性输出（依赖 os.listdir 顺序），重复运行 diff 不一致
- 测试断言只查"文件生成了"而不查行内容，缺 title 行的 ❌ 没人验

## 双层验收
**机械验收（由执行方自验，并在交付说明中附命令与结果原文）**：
1. `python3 -m pytest tests/test_gen_frontmatter_report.py -q` 全绿（tests/ 目录不存在，可新建）
2. CLI：`python3 tools/gen_frontmatter_report.py [扫描根目录]`（缺省 steering/），生成 docs/reports/frontmatter-coverage.md（目录可新建），markdown 表格：列 = 文件路径、title、scenario、合规与否（缺字段标 ❌）
3. 确定性：文件按路径排序，连续运行两次，两次产物 diff 为空（交付说明附 diff 命令与结果）
4. 负控制（tmp_path 独立构造）：合规、缺 title、无 frontmatter 三种样例，断言报告含 3 行数据且缺 title 行有 ❌
5. 对仓库真实 steering/ 运行一次，报告覆盖全部 16 个文件
**人工验收（主会话终裁）**：负控制是否真为独立样例；排序与转义处理

## 证据与前置 falsifier（下列事实一旦出现：立即停止执行并上报，禁止即兴绕过）
- steering/ 不存在或 .md 数量 ≠ 16 → 任务前提失效
- docs/reports/ 已存在同名报告且非本任务产物 → 停止上报，勿覆盖
- 环境无 pytest → 上报环境问题，勿自行改用其他测试框架

## 状态（写协议：本节由执行方独占写入，每完成一个里程碑追加一行，含卡点）
- 起点：全新任务；基线 main commit 9a76f27，工作区干净
- 当前卡点：无

## 约束（enforcement 分级）
- 【gate 强制】pytest 全绿；双次运行 diff 为空
- 【文件所有权】仅可写 tools/gen_frontmatter_report.py、tests/test_gen_frontmatter_report.py、docs/reports/frontmatter-coverage.md；其余路径一律只读（含 steering/）
- 【仅文字，预算 1 条】不引入第三方运行时依赖（Python 标准库 + pytest 以内）

## 升级条款
执行中任何观察与本契约冲突：停止并上报冲突事实，等待重新协商任务包；禁止以仓库既有实现顺延契约。
