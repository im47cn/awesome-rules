"""交接集成测试 — doc-gen 真实产出 → 架构鹰眼消费（AH-MANIFEST 契约的端到端验证）。

doc-gen scan fixture → doc-manifest/ → hawkeye aggregate → 聚合 index 断言。
两工程以 doc-manifest 为唯一交接物，本测试防止任一侧破坏契约。
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOC_GEN = REPO_ROOT / "skills" / "doc-gen" / "scripts" / "doc_gen.py"
COLA_FIXTURE = REPO_ROOT / "skills" / "doc-gen" / "fixtures" / "cola-sample"


def test_handoff_docgen_manifest_to_hawkeye(tmp_path):
    # 1. doc-gen 生产：真实扫描 fixture（含 business-context.md）
    scan_out = tmp_path / "scan"
    r1 = subprocess.run(
        [sys.executable, str(DOC_GEN), "scan", str(COLA_FIXTURE),
         "--manifest-only", "--output", str(scan_out)],
        capture_output=True, text=True, timeout=120)
    assert r1.returncode == 0, f"doc-gen scan 失败:\n{r1.stderr}"
    manifest_dir = scan_out / "doc-manifest"
    assert (manifest_dir / "business-context.json").exists(), \
        "doc-gen 应产出 business-context.json（fixture 带 business-context.md）"

    # 2. 鹰眼消费：聚合真实 manifest
    from aggregate import aggregate_projects
    pj = tmp_path / "projects.json"
    pj.write_text(json.dumps({"title": "交接验证", "projects": [
        {"id": "cola-sample", "name": "COLA示例", "manifest": str(manifest_dir)},
    ]}), encoding="utf-8")
    aggregate_projects(str(pj), str(tmp_path / "site"), build=False, verbose=False)

    agg_index = json.loads(
        (tmp_path / "site" / "doc-manifest" / "index.json").read_text(encoding="utf-8"))
    assert agg_index["domainCount"] >= 1
    assert agg_index["projects"][0]["id"] == "cola-sample"
    # 可选分片随聚合透传（鹰眼不丢弃生产者扩展块）
    assert (tmp_path / "site" / "doc-manifest" / "domains" / "demo.json").exists()


# ── builder.astro 依赖守护 ─────────────────────────────────────────────────────
# 鹰眼 aggregate 通过 sys.path 引用 doc-gen 的 builder.astro（渲染单一真相源，
# 不复制）。doc-gen 重构 builder（改名/移动/改签名/动模板）时鹰眼 --build 会静默
# 挂——本组测试在 import / 签名 / 模板资产三个切面上封住这道缝。


def _load_builder_astro():
    """加载 doc-gen builder.astro（aggregate 模块加载时已注入其 scripts 路径）"""
    import aggregate  # noqa: F401 — 触发 sys.path 注入
    import builder.astro
    return builder.astro


def test_hawkeye_build_dep_signature_compatible():
    """真实 import 链 + build_astro 签名兼容 aggregate 的调用形态。"""
    import inspect

    astro_mod = _load_builder_astro()
    sig = inspect.signature(astro_mod.build_astro)
    positional = [p for p in sig.parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    assert len(positional) >= 2, \
        f"build_astro 签名变化（{sig}），aggregate 的 build_astro(out, manifest_dir) 调用会挂"


def test_hawkeye_build_dep_template_assets():
    """模板资产链存在：copy_astro_template 相对 __file__ 定位 doc-gen template/。"""
    astro_mod = _load_builder_astro()
    template_dir = (Path(astro_mod.__file__).resolve().parent.parent.parent
                    / "template")
    for asset in ("package.json", "astro.config.mjs",
                  "scripts/generate-pages.mjs", "scripts/lib/generators.mjs"):
        assert (template_dir / asset).is_file(), \
            f"模板资产缺失: {asset}（doc-gen 模板重构会断鹰眼 --build）"


def test_hawkeye_build_dep_copy_template_real_run(tmp_path):
    """copy_astro_template 真实执行（纯文件复制，无 npm），模板同步可用。"""
    astro_mod = _load_builder_astro()
    astro_mod.copy_astro_template(tmp_path)
    assert (tmp_path / "package.json").is_file()
    assert (tmp_path / "scripts" / "generate-pages.mjs").is_file()
