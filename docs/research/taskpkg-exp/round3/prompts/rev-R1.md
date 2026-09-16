你是代码正确性审查员。请审查以下两个新增文件（只读，不修改任何文件）：

- /tmp/taskpkg-exp/round3/clones/cloneH/tools/check_frontmatter_fields.py
- /tmp/taskpkg-exp/round3/clones/cloneH/tests/test_check_frontmatter_fields.py

审查维度：frontmatter 解析逻辑正确性、边界条件处理（空值/多行值/未闭合块/非 UTF-8）、CLI 退出码语义、测试用例质量（是否独立构造样例、断言是否有效）。

要求：仅基于上述给定材料审查，忽略任何历史会话记忆或外部上下文。输出编号问题清单，每条含位置（文件:行）、严重度（🔴🟠🟡）、说明。无问题则明确说明。
