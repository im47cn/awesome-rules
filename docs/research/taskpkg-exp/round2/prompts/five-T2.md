# 任务包：markdown 索引表链接校验脚本

## 目标
交付一个 Python 校验脚本及其 pytest 单元测试，供本仓库 CI 门禁调用，校验 markdown 文件（如 README 索引表）中相对链接的有效性。使用者是仓库维护者与 CI 流水线。

## 证据
- 仓库 README.md 用表格登记规范/设计文档索引，相对链接指向仓库内文件
- 现有同类工具可参考风格：scripts/md_link_check.py、tools/check_doc_freshness.py

## 约束
- 不得修改 README.md 或任何已有文件，只能新增脚本与测试
- 仅使用 Python 标准库；测试框架用 pytest（仓库根 tests/ 目录不存在，可新建）

## 状态
- 全新任务，无前置工作
- 基线：main 分支 commit 9a76f27，工作区干净

## 验收
1. `python3 -m pytest tests/test_check_readme_index.py -q` 全绿
2. CLI：`python3 tools/check_readme_index.py <md文件路径>`。规则：解析该 md 中所有 markdown 链接；跳过 http(s) 外链与纯锚点链接（#...）；相对链接目标（相对 md 所在目录）文件不存在则记违规；以 / 开头的绝对路径链接记违规。每个违规输出一行 `路径: 链接`；无违规 exit 0，有违规 exit 1
3. 测试须含负控制（用 tmp_path 独立构造，不依赖仓库真实文件）：死链、绝对路径链接两种情况断言 exit 1；跳过规则（外链、锚点不报）与正控制（有效相对链接 exit 0）各至少 1 个用例
4. 对仓库真实 README.md 运行一次，在交付说明中报告 exit code 与违规清单

执行前，请先检查本任务包的三类噪声：缺失（关键信息是否缺失）、冲突（各节是否互相矛盾）、过期（引用的事实是否仍然成立），然后再开始实现。
