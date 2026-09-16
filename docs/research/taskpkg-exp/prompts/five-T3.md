# 任务包：steering frontmatter 覆盖率报告生成器

## 目标
交付一个 Python 报告生成脚本、其 pytest 单元测试、以及运行产物报告文件，供仓库维护者总览 steering/ 规范文档的 frontmatter 覆盖情况。

## 证据
- 仓库 CLAUDE.md 要求：规范文件须带 frontmatter（title + scenario 两个非空字段）
- steering/ 含通用规范（steering/*.md）与 GTSP 规范（steering/gtsp/*.md），共 16 个 .md
- 报告产物理应入库（docs/reports/ 目录当前不存在，可新建）

## 约束
- 不得修改 steering/ 下任何现有文件
- 不得修改 tools/ 下已有脚本，只能新增
- 仅使用 Python 标准库；测试框架用 pytest（仓库根 tests/ 目录不存在，可新建）

## 状态
- 全新任务，无前置工作
- 基线：main 分支 commit 9a76f27，工作区干净

## 验收
1. `python3 -m pytest tests/test_gen_frontmatter_report.py -q` 全绿
2. CLI：`python3 tools/gen_frontmatter_report.py [扫描根目录]`（缺省 steering/），生成 docs/reports/frontmatter-coverage.md，内容为 markdown 表格：列 = 文件路径、title、scenario、合规与否（缺字段标 ❌）
3. 输出确定性：文件按路径排序，重复运行两次产物 byte-identical
4. 测试须含负控制（用 tmp_path 独立构造，不依赖仓库真实文件）：合规、缺 title、无 frontmatter 三种样例，断言生成报告含 3 行数据且缺 title 行有 ❌ 标记
5. 对仓库真实 steering/ 运行一次，报告覆盖全部 16 个文件

执行前，请先检查本任务包的三类噪声：缺失（关键信息是否缺失）、冲突（各节是否互相矛盾）、过期（引用的事实是否仍然成立），然后再开始实现。
