import sys
from pathlib import Path

# 注入 scripts/ 到 sys.path（各套件独立 rootdir 约定，见 scripts/run_tests.sh）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
