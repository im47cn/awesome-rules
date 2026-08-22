"""pytest 共享配置：scripts/ 入 sys.path + fixture 项目路径"""

import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

# 测试密封性：pytest 可能运行在 hook 注入的 GIT_DIR/GIT_WORK_TREE 环境下
# （lefthook pre-push 链），显式环境变量优先于 cwd 发现，会把测试里
# cwd=tmp_path 的 git init/add/commit 劫持到真仓（2026-08-22 事故：
# 389 文件被删）。import 期剥离最早且确定，先于任何测试执行。
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
    os.environ.pop(_k, None)


@pytest.fixture
def ddd_sample() -> Path:
    return SCRIPTS_DIR.parent / "fixtures" / "ddd-sample"


@pytest.fixture
def scanned(ddd_sample):
    """已扫描的 ImpactScanner + 边界配置（.impact-guard.json 由 --init 生成后提交）"""
    from impact_scanner import ImpactScanner
    config = {"project_package_prefix": "com.acme",
              "ignore": ["**/test/**", "**/dto/**", "**/query/**"]}
    scanner = ImpactScanner(str(ddd_sample), config)
    scanner.scan()
    return scanner
