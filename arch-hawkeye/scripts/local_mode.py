"""本地双模式（AH-B01/B02/B03）— 员工本地一条命令的全链路治理视图。

B01 本地运行：给定仓库路径 → 逐个 scan → 聚合 → （含基线项目）治理视图，
零服务依赖、零凭证；dirty 工作区恰是本地模式的分析对象（aggregate
local_mode 跳过 §6.3 联邦卫生——那是对中心索引的约束）。

B02 token 成本：全链路纯脚本（scan/aggregate/trend/gate），零 LLM 调用；
鹰眼接入 LLM 时必须保持"仅集中模式且规则无法判定"的约束（README 承诺）。

B03 本地结论上报：本地产出（trend.json / cross-project.json / governance.json）
标准落盘在 <output>/doc-manifest/，上报 = 推送到归档分支（CI 样例
ci/governance-pipeline.example.yml 的 archive job 同构步骤；本地不做任何
自动 push——对外推送必须由人执行）。
"""

import json
import subprocess
import sys
from pathlib import Path

HAWKEYE_DIR = Path(__file__).resolve().parent
DOC_GEN = (HAWKEYE_DIR.parent.parent / "skills" / "doc-gen" / "scripts" / "doc_gen.py")


def _scan(repo: Path, out_dir: Path) -> bool:
    """scan 单仓库（复用 doc-gen CLI；receipt 是唯一验收依据）"""
    result = subprocess.run(
        [sys.executable, str(DOC_GEN), "scan", str(repo),
         "--manifest-only", "--output", str(out_dir)],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        print(f"  ❌ scan 失败 {repo.name}: {result.stderr[-300:]}", file=sys.stderr)
        return False
    receipt = out_dir / "doc-manifest" / "receipt.json"
    if receipt.exists():
        try:
            ok = json.loads(receipt.read_text(encoding="utf-8")).get("ok")
            if not ok:
                print(f"  ⚠ {repo.name}: receipt.ok=false（阶段降级，详见 receipt.json）")
        except (json.JSONDecodeError, OSError):
            pass
    return True


def run_local(repos: list, output: str, baseline: str | None = None,
              build: bool = False) -> bool:
    """本地全链路：scan 全部 → 聚合（local_mode）→ 含基线项目执行 trend。

    返回 False 表示任一 scan 失败或无有效项目。
    """
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"🏠 本地模式（B01）：{len(repos)} 个仓库 → {out}")
    projects = []
    for repo_path in repos:
        repo = Path(repo_path).expanduser().resolve()
        if not repo.is_dir():
            print(f"  ❌ 目录不存在: {repo}", file=sys.stderr)
            return False
        pid = repo.name
        proj_out = out / "scans" / pid
        if not _scan(repo, proj_out):
            return False
        projects.append({"id": pid, "name": pid,
                         "manifest": str(proj_out / "doc-manifest")})
        print(f"  ✓ {pid} 扫描完成")

    if not projects:
        return False

    pj = out / "local-projects.json"
    pj.write_text(json.dumps({"title": "本地治理视图", "projects": projects},
                             ensure_ascii=False), encoding="utf-8")

    # 聚合（local_mode：dirty 工作区是分析对象而非拒收项）
    from aggregate import aggregate_projects
    print()
    aggregate_projects(str(pj), str(out / "site"), build=build, verbose=False,
                       local_mode=True)

    # 含基线项目执行趋势（本地治理结论，B03 落盘于各项目 manifest 目录）
    if baseline:
        from governance import load_baseline, load_risks, diff_risks, sync_ledger
        print()
        for proj in projects:
            md = Path(proj["manifest"])
            try:
                bl = load_baseline(md, baseline)
            except FileNotFoundError:
                print(f"  ℹ {proj['id']}: 无基线 '{baseline}'，跳过 trend")
                continue
            diff = diff_risks(bl, load_risks(md))
            closed = sync_ledger(md, load_risks(md))
            trend_file = md / f"trend-{baseline}.json"
            trend_file.write_text(json.dumps(
                {**diff, "ledgerClosed": closed["closedCount"]},
                ensure_ascii=False, indent=2), encoding="utf-8")
            st = diff["stats"]
            print(f"  📈 {proj['id']} vs {baseline}: "
                  f"新增 {st['added']} / 消除 {st['removed']} / 净 {st['net']:+d}"
                  + (f"（关债 {closed['closedCount']}）" if closed["closedCount"] else ""))

    print()
    print(f"✅ 本地治理视图 → {out / 'site' / 'doc-manifest'}")
    print("   • cross-project.json 跨项目链路 / governance.json 治理分片")
    if not build:
        print(f"   • 站点构建: cd {out / 'site'} && npm run build")
    print("   • 本地结论上报（B03）: 推送各 scans/<pid>/doc-manifest 到归档分支，"
          "见 ci/governance-pipeline.example.yml（本地不自动 push）")
    return True
