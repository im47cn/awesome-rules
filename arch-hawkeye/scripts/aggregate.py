"""架构鹰眼 — 多项目联邦聚合模块，将多个 doc-manifest/ 合并到架构鹰眼站点。

从 skills/doc-gen/scripts/builder/aggregate.py 迁移（doc-gen 收缩为单项目文档站，
聚合职责归架构鹰眼，见 arch-hawkeye/AH-MANIFEST.md §1 契约定位）。
站点渲染复用 doc-gen 的 Astro 模板渲染器（单一真相源，不复制）。
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 跨项目依赖：doc-gen scripts（builder.astro 站点渲染）
DOC_GEN_SCRIPTS = (Path(__file__).resolve().parent.parent.parent
                   / "skills" / "doc-gen" / "scripts")
if str(DOC_GEN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DOC_GEN_SCRIPTS))

from builder.astro import build_astro  # noqa: E402
from validator import validate_manifest_dir  # noqa: E402 — 契约校验器（AH-MANIFEST 真相源）

from crossproject import build_cross_project_edges  # noqa: E402 — 同目录模块


def aggregate_projects(projects_json: str, output_dir: str, build: bool, verbose: bool,
                       local_mode: bool = False):
    """多项目聚合 — 将多个 doc-manifest/ 合并到架构鹰眼站点

    projects.json 格式:
    {
      "title": "公司架构全景",
      "projects": [
        {"id": "order-system", "name": "订单系统", "manifest": "./order/doc-manifest/", "repo": "..."},
        {"id": "logistics", "name": "物流系统", "manifest": "./logistics/doc-manifest/", "repo": "..."}
      ]
    }
    """
    config_file = Path(projects_json)
    if not config_file.exists():
        print(f"❌ 聚合配置文件不存在: {projects_json}", file=sys.stderr)
        sys.exit(2)

    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(2)

    projects = config.get("projects", [])
    site_title = config.get("title", "架构鹰眼")
    site_desc = config.get("description", "全公司 DDD 架构全景视图")

    if not projects:
        print("❌ 配置中无项目列表 (projects 字段为空)", file=sys.stderr)
        sys.exit(2)

    print(f"🦅 架构鹰眼 聚合 {len(projects)} 个项目")
    print()

    # Phase 1: 验证 & 读取各项目 manifest
    project_data = []
    valid_manifests = []      # [(proj_id, manifest_path)] 跨项目边构建输入
    all_governance = []       # 各项目治理分片（baselines/debts，E03 仪表盘数据源）
    total_domains = 0
    total_components = 0
    total_tables = 0
    all_domains = []
    all_tables = []
    all_relationships = []
    all_domain_aggregates = {}
    all_state_machines = []
    all_state_diagrams = {}
    all_cross_deps = []

    for proj in projects:
        proj_id = proj.get("id", "unknown")
        proj_name = proj.get("name", proj_id)
        manifest_path = Path(proj.get("manifest", f"./{proj_id}/doc-manifest/"))

        if not manifest_path.exists():
            print(f"  ⚠ {proj_name}: manifest 不存在 ({manifest_path})，跳过")
            continue

        index_file = manifest_path / "index.json"
        if not index_file.exists():
            # 尝试旧版单文件
            legacy = manifest_path.parent / "doc-manifest.json"
            if legacy.exists():
                print(f"  ⚠ {proj_name}: 旧版单文件格式，请先重新扫描")
            else:
                print(f"  ⚠ {proj_name}: index.json 不存在，跳过")
            continue

        # 消费者义务 §6.1：校验后再纳管（AH-A05）——失败跳过 + 结构化告警，
        # 不得静默降级纳管
        shard_errors = validate_manifest_dir(manifest_path)
        if shard_errors:
            print(f"  ⚠ {proj_name}: manifest 契约校验失败（{len(shard_errors)} 处），跳过")
            for err in shard_errors[:5]:
                print(f"      - {err}")
            if len(shard_errors) > 5:
                print(f"      - ... 共 {len(shard_errors)} 处")
            continue

        # 消费者义务 §6.3：revision 卫生——脏工作区 / 无 revision 的快照
        # 不进入联邦索引（SHA 与扫描内容对不上，§4 脏工作区标注）
        meta_file = manifest_path / "meta.json"
        evidence = {}
        if meta_file.exists():
            try:
                evidence = json.loads(meta_file.read_text(
                    encoding="utf-8")).get("evidence", {})
            except json.JSONDecodeError:
                evidence = {}
        # local_mode（hawkeye local）：本地分析视角——dirty 工作区恰是本地
        # 模式的分析对象（分析当前未提交改动），仅联邦索引要求干净快照
        if not local_mode and (evidence.get("dirty") or not evidence.get("revision")):
            reason = ("evidence.dirty=true，SHA 与扫描内容不符"
                      if evidence.get("dirty") else "revision 缺失/null")
            print(f"  ⚠ {proj_name}: {reason}，不进入联邦索引（请重新扫描干净工作区）")
            continue
        # local_mode 仅豁免 dirty（本地分析对象）；revision 缺失仍提示——
        # 无指纹的快照纳管后 trend/上报不可追溯
        if local_mode and not evidence.get("revision"):
            print(f"  ℹ {proj_name}: revision 缺失（未纳入 git？）——本地纳管，"
                  f"但快照无指纹、上报不可追溯")

        try:
            idx = json.loads(index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ⚠ {proj_name}: index.json 解析失败，跳过")
            continue

        # 收集域名
        domains = idx.get("domains", [])
        domain_count = len(domains)
        comp_count = sum(d.get("componentCount", 0) for d in domains)

        total_domains += domain_count
        total_components += comp_count

        # 标记所属项目的域
        for d in domains:
            d["_project_id"] = proj_id
            d["_project_name"] = proj_name
        all_domains.extend(domains)

        # 收集表
        db_tables: list = []
        db_file = manifest_path / "database.json"
        if db_file.exists():
            try:
                db = json.loads(db_file.read_text(encoding="utf-8"))
                db_tables = db.get("tables", [])
                for t in db_tables:
                    t["_project_id"] = proj_id
                    t["_project_name"] = proj_name
                total_tables += len(db_tables)
                all_tables.extend(db_tables)
                # 收集表关系（保留项目归属，用于聚合全景 ER 图）
                for rel in db.get("relationships", []):
                    r = dict(rel)
                    r["_project_id"] = proj_id
                    all_relationships.append(r)
            except json.JSONDecodeError:
                pass

        # 收集跨域依赖
        cd_file = manifest_path / "cross-domain.json"
        if cd_file.exists():
            try:
                cd = json.loads(cd_file.read_text(encoding="utf-8"))
                all_cross_deps.extend(cd if isinstance(cd, list) else [])
            except json.JSONDecodeError:
                pass

        # 收集领域聚合类图 + 状态机图（mermaid 数据源）
        diag_file = manifest_path / "diagrams.json"
        if diag_file.exists():
            try:
                diag = json.loads(diag_file.read_text(encoding="utf-8"))
                for dn, diagram in (diag.get("domainAggregates") or {}).items():
                    all_domain_aggregates[dn] = diagram
                for smn, sdiagram in (diag.get("stateMachines") or {}).items():
                    all_state_diagrams[smn] = sdiagram
            except json.JSONDecodeError:
                pass

        # 收集状态机（含隐式状态机）
        sm_file = manifest_path / "state-machines.json"
        if sm_file.exists():
            try:
                sms = json.loads(sm_file.read_text(encoding="utf-8"))
                for sm in (sms if isinstance(sms, list) else []):
                    sm["_project_id"] = proj_id
                    all_state_machines.append(sm)
            except json.JSONDecodeError:
                pass

        # 记录项目摘要
        project_data.append({
            "id": proj_id,
            "name": proj_name,
            "repo": proj.get("repo", ""),
            "description": proj.get("description", ""),
            "domainCount": domain_count,
            "componentCount": comp_count,
            "tableCount": len(db_tables) if db_file.exists() else 0,
            "layers": list(set(l for d in domains for l in (d.get("layers", []) or []))),
            # 域名清单：全景图域→项目匹配依赖此键（find_project_for_domain）
            "domains": [d.get("name", "") for d in domains if d.get("name")],
        })
        # 记录成功读取的 manifest（跨项目边构建输入，AH-C01）
        valid_manifests.append((proj_id, manifest_path))

        # 收集治理分片（baselines/debt-ledger，若项目已建立治理——供
        # 聚合站点的治理仪表盘 E03 汇总，缺省跳过）
        gov_data = {"projectId": proj_id, "projectName": proj_name,
                    "baselines": [], "debts": []}
        for bf in sorted((manifest_path / "baselines").glob("*.json")) \
                if (manifest_path / "baselines").is_dir() else []:
            try:
                gov_data["baselines"].append({
                    "name": bf.stem,
                    **{k: v for k, v in json.loads(
                        bf.read_text(encoding="utf-8")).items()
                        if k != "fingerprints"}})   # 指纹明细留在项目侧
            except (json.JSONDecodeError, OSError):
                pass
        ledger_file = manifest_path / "debt-ledger.json"
        if ledger_file.exists():
            try:
                gov_data["debts"] = json.loads(
                    ledger_file.read_text(encoding="utf-8")).get("debts", [])
            except (json.JSONDecodeError, OSError):
                pass
        if gov_data["baselines"] or gov_data["debts"]:
            all_governance.append(gov_data)

        print(f"  ✓ {proj_name}: {domain_count} 域, {comp_count} 组件")

    print(f"     合计: {len(project_data)} 项目, {total_domains} 域, {total_components} 组件, {total_tables} 表")

    # Phase 2: 生成聚合 manifest
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    agg_dir = out / "doc-manifest"
    agg_dir.mkdir(exist_ok=True)
    (agg_dir / "domains").mkdir(exist_ok=True)
    (agg_dir / "projects").mkdir(exist_ok=True)

    # index.json — 多项目入口
    # 收集 & 合并 OpenAPI specs
    all_paths = {}
    has_any_api = False
    for proj in projects:
        proj_manifest = Path(proj.get("manifest", ""))
        api_spec_file = proj_manifest / "api-spec.json"
        if api_spec_file.exists():
            try:
                sub_spec = json.loads(api_spec_file.read_text(encoding="utf-8"))
                sub_paths = sub_spec.get("paths", {})
                for p, methods in sub_paths.items():
                    if p not in all_paths:
                        all_paths[p] = {}
                    for m, op in methods.items():
                        all_paths[p][m] = op
                has_any_api = True
            except (json.JSONDecodeError, IOError):
                pass

    if has_any_api:
        merged_spec = {
            "openapi": "3.0.3",
            "info": {"title": f"{site_title} API", "description": site_desc, "version": "1.0.0"},
            "servers": [{"url": "/api"}],
            "paths": all_paths,
            "tags": [],
            "components": {"schemas": {}},
        }
        (agg_dir / "api-spec.json").write_text(
            json.dumps(merged_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    index = {
        "schemaVersion": "2.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generator": "arch-hawkeye v2.0",
        "project": {"name": site_title, "description": site_desc},
        "projects": project_data,
        "domainCount": total_domains,
        "componentCount": total_components,
        "tableCount": total_tables,
        "hasOpenApi": has_any_api,
        "hasDeepAnalysis": False,
        "hasCrossDomain": len(all_cross_deps) > 0,
        "domains": all_domains,
    }
    (agg_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # meta.json
    (agg_dir / "meta.json").write_text(
        json.dumps({"project": {"name": site_title, "description": site_desc}},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # 写各域的详细数据（从原始 manifest 复制，标记项目归属）
    for proj in projects:
        proj_manifest = Path(proj.get("manifest", ""))
        if not proj_manifest.exists():
            continue
        domains_dir = proj_manifest / "domains"
        if not domains_dir.is_dir():
            continue
        for df in sorted(domains_dir.glob("*.json")):
            domain_data = json.loads(df.read_text(encoding="utf-8"))
            domain_data["_project_id"] = proj.get("id", "")
            domain_data["_project_name"] = proj.get("name", "")
            # 域文件按 project-id/domain-name.json 存储
            proj_domains_dir = agg_dir / "projects" / proj.get("id", "")
            proj_domains_dir.mkdir(parents=True, exist_ok=True)
            (proj_domains_dir / df.name).write_text(
                json.dumps(domain_data, ensure_ascii=False, indent=2), encoding="utf-8")
            # 也保留顶级 domains/ 目录的副本（兼容懒加载查找）
            (agg_dir / "domains" / df.name).write_text(
                json.dumps(domain_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # database.json — 合并所有表 + 表关系（聚合全景 ER 图数据源）
    (agg_dir / "database.json").write_text(
        json.dumps({"tables": all_tables, "relationships": all_relationships},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # state-machines.json — 合并所有项目的状态机（含隐式状态机）
    (agg_dir / "state-machines.json").write_text(
        json.dumps(all_state_machines, ensure_ascii=False, indent=2), encoding="utf-8")

    # business-context.json — 合并各项目业务全景（人工 md + 代码弱信号，模板按条目 _project_name 区分来源）
    merged_bc = {"customers": [], "roles": [], "scenarios": [], "flows": []}
    for proj in projects:
        bc_file = Path(proj.get("manifest", "")) / "business-context.json"
        if not bc_file.exists():
            continue
        try:
            bc = json.loads(bc_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key in ("customers", "roles", "scenarios", "flows"):
            for item in bc.get(key, []):
                item["_project_id"] = proj.get("id", "")
                item["_project_name"] = proj.get("name", "")
                merged_bc[key].append(item)
    bc_total = sum(len(merged_bc[k]) for k in merged_bc)
    if bc_total:
        (agg_dir / "business-context.json").write_text(
            json.dumps(merged_bc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ 业务全景: {bc_total} 条（客户/角色/场景/流程）")

    # cross-domain.json — 聚合（去重）
    seen_cd = set()
    unique_cd = []
    for cd in all_cross_deps:
        key = f"{cd.get('fromDomain','')}→{cd.get('toDomain','')}"
        if key not in seen_cd:
            seen_cd.add(key)
            unique_cd.append(cd)
    (agg_dir / "cross-domain.json").write_text(
        json.dumps(unique_cd, ensure_ascii=False, indent=2), encoding="utf-8")

    # cross-project.json — 跨项目真实链路（Phase 2，AH-C01/C04）
    # Feign 调用签名 ↔ Controller 路由签名对齐，confirmed/inferred 双置信度
    cross_project = build_cross_project_edges(valid_manifests)
    (agg_dir / "cross-project.json").write_text(
        json.dumps(cross_project, ensure_ascii=False, indent=2),
        encoding="utf-8")
    cp_stats = cross_project["stats"]
    print(f"  ✓ 跨项目链路: confirmed={cp_stats['confirmed']}, "
          f"inferred={cp_stats['inferred']}, "
          f"项目内调用={cp_stats['internalCalls']}, "
          f"未匹配={cp_stats['unmatchedConsumers']}")

    # governance.json — 治理分片汇总（E03 仪表盘数据源，项目未接入治理时为空）
    (agg_dir / "governance.json").write_text(
        json.dumps({"projects": all_governance}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    total_debts = sum(len(g["debts"]) for g in all_governance)
    if all_governance:
        print(f"  ✓ 治理分片: {len(all_governance)} 项目, {total_debts} 条债务")

    # diagrams.json — 公司级全景架构图 + 聚合全景 ER 图
    # 跨项目依赖图优先用真实边（confirmed/inferred 视觉区分），无真实边时回退域名猜测
    diagrams = generate_panorama_diagram(project_data, all_cross_deps)
    diagrams["crossProjectEdges"] = cross_project["edges"]
    diagrams["erDiagram"] = generate_er_diagram(all_tables, all_relationships)
    diagrams["domainAggregates"] = all_domain_aggregates
    diagrams["stateMachines"] = all_state_diagrams
    (agg_dir / "diagrams.json").write_text(
        json.dumps(diagrams, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"  ✓ 聚合 manifest → {agg_dir}")

    # Phase 3: 可选构建（失败传播：非零退出绝不可描述为成功）
    if build:
        print()
        print("🏗️  构建架构鹰眼站点...")
        if not build_astro(out, agg_dir):
            print("❌ 聚合站点构建失败", file=sys.stderr)
            sys.exit(1)
        print(f"\n🦅 架构鹰眼站点构建完成!")
        print(f"  📁 {out / 'dist'}")
    else:
        print(f"\n🦅 架构鹰眼聚合完成!")
        print(f"  📁 {agg_dir}")
        print(f"  💡 使用 --build 构建站点，或直接 cd {output_dir} && npm run build")


def generate_er_diagram(tables: list, relationships: list) -> str:
    """生成聚合全景 ER 图（mermaid erDiagram）。

    实体为各项目表（mermaid 标识符化）；关系边来自各项目 FK 推断。
    方向：父表(被引用, 一)在前、子表(含外键, 多)在后 —— ``to ||--o{ from``。
    多项目同名表自然合并为同一实体。
    """
    import re

    def ent(name: str) -> str:
        e = re.sub(r'\W', '_', str(name))
        return e or "T"

    lines = ["erDiagram"]
    declared = set()
    for t in tables:
        e = ent(t.get("name", ""))
        if e not in declared:
            declared.add(e)
            lines.append(f"  {e} {{ }}")
    for rel in relationships:
        parent = ent(rel.get("to", ""))   # 被引用表(一)
        child = ent(rel.get("from", ""))  # 含外键表(多)
        if parent and child and parent != child:
            card = rel.get("cardinality", "||--o{")
            fk = rel.get("fk", "")
            lines.append(f'  {parent} {card} {child} : "{fk}"')
    return "\n".join(lines)


def generate_panorama_diagram(project_data: list, cross_deps: list) -> dict:
    """生成公司级全景 Mermaid 架构图 + 分层依赖图"""
    diagrams = {}

    # 1. 公司全景项目拓扑图
    lines = ["graph TD"]
    lines.append("  subgraph PANORAMA[\"🏢 公司架构全景\"]")

    for i, proj in enumerate(project_data):
        pid = proj["id"].replace("-", "_")
        pname = proj["name"]
        domain_count = proj.get("domainCount", 0)
        comp_count = proj.get("componentCount", 0)
        label = f"{pname}<br/>{domain_count}域 {comp_count}组件"

        lines.append(f"    {pid}[\"{label}\"]")

        # 项目节点可点击
        lines.append(f"    click {pid} \"/projects/{proj['id']}/\" \"查看{proj['name']}详情\"")

    # 跨项目关系边：独立于项目节点循环（否则随项目数重复 N 倍），去重后追加
    seen_edges = set()
    for cd in cross_deps:
        from_domain = cd.get("fromDomain", cd.get("from_domain", ""))
        to_domain = cd.get("toDomain", cd.get("to_domain", ""))
        # 尝试匹配项目
        from_proj = find_project_for_domain(project_data, from_domain)
        to_proj = find_project_for_domain(project_data, to_domain)
        if from_proj and to_proj and from_proj != to_proj:
            dep_type = cd.get("type", "client-api")
            edge_key = (from_proj, to_proj, dep_type)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            from_id = from_proj.replace("-", "_")
            to_id = to_proj.replace("-", "_")
            style = " -.-> " if dep_type == "domain-event" else " --> "
            lines.append(f"    {from_id}{style}|{dep_type}| {to_id}")

    lines.append("  end")
    diagrams["architectureOverview"] = "\n".join(lines)

    # 2. 分层依赖图（通用 DDD 图）
    diagrams["layeredDependency"] = ("flowchart LR\n"
        "  A[🖥️ Adapter] --> B[⚙️ Application]\n"
        "  B --> C[🧠 Domain]\n"
        "  D[🏗️ Infrastructure] --> C\n"
        "  B --> D\n"
        "  A -.-> E[📦 Client]\n"
        "  click A \"/architecture#adapter\"\n"
        "  click C \"/architecture#domain\"")

    # 3. 项目间依赖矩阵
    if cross_deps:
        dep_lines = ["graph LR"]
        deps_by_pair = defaultdict(int)
        for cd in cross_deps:
            from_p = find_project_for_domain(project_data, cd.get("fromDomain", cd.get("from_domain", "")))
            to_p = find_project_for_domain(project_data, cd.get("toDomain", cd.get("to_domain", "")))
            if from_p and to_p:
                deps_by_pair[(from_p, to_p)] += 1
        for (fp, tp), count in deps_by_pair.items():
            from_id = fp.replace("-", "_").replace(" ", "_")
            to_id = tp.replace("-", "_").replace(" ", "_")
            dep_lines.append(f"  {from_id}[\"{fp}\"] -->|\"{count} 依赖\"| {to_id}[\"{tp}\"]")
        diagrams["crossProjectDependencies"] = "\n".join(dep_lines) if len(dep_lines) > 1 else ""

    return diagrams


def find_project_for_domain(project_data: list, domain_name: str) -> Optional[str]:
    """根据域名查找所属项目名"""
    if not domain_name:
        return None
    for proj in project_data:
        # 域名直接匹配或者前缀匹配
        if domain_name == proj.get("id", "") or domain_name == proj.get("name", ""):
            return proj.get("name", "")
        # 检查域列表（兼容字符串清单与 {'name': ...} 字典两种形态）
        for d in proj.get("domains", []):
            name = d.get("name", "") if isinstance(d, dict) else str(d)
            if name and name == domain_name:
                return proj.get("name", "")
    return None
