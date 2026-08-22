"""pytest 共享配置：scripts/ 入 sys.path + fixture 项目路径"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest


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
