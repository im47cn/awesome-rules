"""pytest 共享配置 — 注入鹰眼 scripts 目录（aggregate.py 自行注入 doc-gen 侧路径）。"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
