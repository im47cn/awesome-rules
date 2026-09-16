import sys
from pathlib import Path

# frontmatter_lib 无包结构（tools/ 平面布局，与 check_* 检查器同级），
# sys.path 注入 tools/ 根——与 check_frontmatter_manifests.py 的导入方式一致
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
