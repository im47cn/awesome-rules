"""JS 页面生成冒烟测试 — 守护 Python 扫描器与 .mjs 页面生成器的接线完整。

背景：8970fe7 提交时 JS 侧被还原遗漏，Python 测试全绿掩盖了 /business/
页面不渲染的半成品。本测试用 node 真实执行 generate-pages.mjs，把前端
接线纳入测试保护伞（utils.mjs 的 DOCGEN_* 环境变量支持临时目录运行）。
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "template"
GEN_SCRIPT = TEMPLATE_DIR / "scripts" / "generate-pages.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node 不可用，跳过 JS 冒烟")


def _write_min_manifest(manifest_dir: Path):
    """最小可聚合 doc-manifest：index.json + business-context.json"""
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "index.json").write_text(json.dumps({
        "schema_version": 1,
        "project": {"name": "smoke", "description": "JS 冒烟"},
        "domainCount": 1, "componentCount": 1, "tableCount": 0,
        "domains": [{"name": "demo", "componentCount": 1,
                     "layers": ["domain"], "file": "domains/demo.json"}],
    }), encoding="utf-8")
    (manifest_dir / "domains").mkdir()
    (manifest_dir / "domains" / "demo.json").write_text(
        json.dumps({"name": "demo", "layers": {}}), encoding="utf-8")
    (manifest_dir / "business-context.json").write_text(json.dumps({
        "schema_version": 1,
        "customers": [{"name": "商户", "description": "冒烟", "source": "manual"}],
        "roles": [], "scenarios": [], "flows": [],
    }, ensure_ascii=False), encoding="utf-8")


def test_generate_pages_business_smoke(tmp_path):
    """真实执行 node generate-pages.mjs，断言 business.mdx 生成且含业务全景内容。"""
    manifest_dir = tmp_path / "doc-manifest"
    docs_dir = tmp_path / "docs"
    _write_min_manifest(manifest_dir)

    result = subprocess.run(
        ["node", str(GEN_SCRIPT)],
        capture_output=True, text=True, timeout=60,
        cwd=TEMPLATE_DIR,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
             "DOCGEN_MANIFEST_DIR": str(manifest_dir),
             "DOCGEN_DOCS_DIR": str(docs_dir)},
    )
    assert result.returncode == 0, f"generate-pages 失败:\n{result.stderr}"

    business = docs_dir / "business.mdx"
    assert business.exists(), "business.mdx 未生成 —— 前端接线缺失（对比 8970fe7 教训）"
    content = business.read_text(encoding="utf-8")
    assert "业务全景" in content
    assert "商户" in content


def test_generate_pages_omits_business_without_shard(tmp_path):
    """无 business-context.json 分片时不生成 business.mdx（可选分片语义）。"""
    manifest_dir = tmp_path / "doc-manifest"
    docs_dir = tmp_path / "docs"
    _write_min_manifest(manifest_dir)
    (manifest_dir / "business-context.json").unlink()

    result = subprocess.run(
        ["node", str(GEN_SCRIPT)],
        capture_output=True, text=True, timeout=60,
        cwd=TEMPLATE_DIR,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
             "DOCGEN_MANIFEST_DIR": str(manifest_dir),
             "DOCGEN_DOCS_DIR": str(docs_dir)},
    )
    assert result.returncode == 0, result.stderr
    assert not (docs_dir / "business.mdx").exists()
