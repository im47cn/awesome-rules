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
