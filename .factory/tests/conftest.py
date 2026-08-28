import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 测试密封性（steering/testing-standards.md）：import 期剥离 hook 注入的
# GIT_*（lefthook pre-push 链），显式环境变量优先于 cwd 发现，会把测试里
# cwd=tmp_path / git -C <tmp夹具仓> 的 git init/add/commit 劫持到真仓
# （2026-08-22 事故：389 文件被删；2026-08-27 PR #71：夹具提交落真仓
# HEAD）。import 期剥离最早且确定，先于任何测试执行；子进程继承剥离后的
# 环境（含 spawn 的 .factory 脚本子链）。与各 skills 套件 conftest 同一
# 范式（ADR-010 机械化：tools/check_git_sealing.py R1）。
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
    os.environ.pop(_k, None)
