"""pytest 共享配置。

将 scripts/ 注入 sys.path，使各测试模块可直接 import scanner/generator/builder，
无需每个文件重复 sys.path.insert（DRY）。
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
