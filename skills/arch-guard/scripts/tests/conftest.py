"""pytest 共享配置 — 环境密封（测试自带 sys.path 注入，见 test_arch_check.py 头部）。"""

import os

# 测试密封性：pytest 可能运行在 hook 注入的 GIT_DIR/GIT_WORK_TREE 环境下
# （lefthook pre-push 链），显式环境变量优先于 cwd 发现，会把测试里
# cwd=tmp_path 的 git init/add/commit 劫持到真仓（2026-08-22 事故：
# 389 文件被删）。import 期剥离最早且确定，先于任何测试执行。
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
    os.environ.pop(_k, None)
