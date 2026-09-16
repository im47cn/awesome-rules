# 任务包：steering frontmatter 字段校验脚本

## 目标
交付一个 Python 校验脚本及其 pytest 单元测试，供本仓库 CI 门禁调用，校验 steering/ 目录下所有规范文档的 frontmatter 完整性。使用者是仓库维护者与 CI 流水线。

## 证据
- 仓库 CLAUDE.md 要求：规范文件须带 frontmatter（title + scenario 两个非空字段）
- steering/ 含通用规范（steering/*.md）与 GTSP 规范（steering/gtsp/*.md），共 16 个 .md
- 现有同类工具可参考风格：tools/check_doc_freshness.py

## 约束
- 不得修改 steering/ 下任何现有文件
- 不得修改 tools/ 下已有脚本，只能新增
- 仅使用 Python 标准库；测试框架用 pytest（仓库根 tests/ 目录不存在，可新建）

## 状态
- 全新任务，无前置工作
- 基线：main 分支 commit 9a76f27，工作区干净

## 验收
1. `python3 -m pytest tests/test_check_frontmatter_fields.py -q` 全绿
2. CLI：`python3 tools/check_frontmatter_fields.py [路径...]`（缺省为 steering/）。每个违规文件输出一行 `路径: 缺失字段`；全部合规 exit 0；存在违规 exit 1
3. 测试须含负控制（用 tmp_path 独立构造，不依赖仓库真实文件）：缺 title、缺 scenario、空 frontmatter、无 frontmatter 四种情况均断言 exit 1；正控制：合规样例 exit 0
4. 对仓库真实 steering/ 目录运行一次，在交付说明中报告 exit code 与违规清单

执行前，请先检查本任务包的三类噪声：缺失（关键信息是否缺失）、冲突（各节是否互相矛盾）、过期（引用的事实是否仍然成立），然后再开始实现。
