"""跨技能复用桥 — 导入 doc-gen 的 JavaScanner / LayerIdentifier

复用来源（DESIGN.md §6）：doc-gen 的 scanner/java.py 与 generator/layers.py。
（评审稿写"arch-guard"，实际物理位置在 doc-gen——JavaScanner/LayerIdentifier
从未存在于 arch-guard 的单文件 arch_check.py 中。）
"""

import sys
from pathlib import Path

DOC_GEN_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "doc-gen" / "scripts"

if str(DOC_GEN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DOC_GEN_SCRIPTS))

from scanner.java import JavaScanner          # noqa: E402,F401
from generator.layers import LayerIdentifier  # noqa: E402,F401
