import os
import sys
from pathlib import Path

# 注入 scripts/ 到 sys.path（各套件独立 rootdir 约定，见 scripts/run_tests.sh）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 测试密封性（steering/testing-standards.md §测试密封性）：import 期剥离
# hook 注入的 GIT_*（lefthook pre-push 链），显式环境变量优先于 cwd 发现，
# 会把 cwd=tmp_path 的 git init/add/commit 劫持到真仓（2026-08-22 事故：
# 389 文件被删）。import 期剥离最早且确定，先于任何测试执行（ADR-010
# 机械化：tools/check_git_sealing.py R1）。
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
    os.environ.pop(_k, None)
