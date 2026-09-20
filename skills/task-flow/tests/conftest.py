"""task-flow 测试前置：注入 scripts/ 到 sys.path + 环境密封。

rootdir 约定与 skills/skill-evo/scripts/tests 同构：pytest.ini 在 tests/ 内，
scripts/ 不构成包，须显式注入路径才能 `import taskflow`。

@date 2026-09-20
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# 测试密封性（steering/testing-standards.md §测试密封性）：剥离 hook 链注入的
# GIT_* 环境变量。本套件不执行 git 命令，但门禁脚本类产物在用户项目根下跑子
# 进程，密封可防环境变量把子进程的路径发现劫持到真仓（2026-08-22 事故防线）。
for _k in (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
):
    os.environ.pop(_k, None)
