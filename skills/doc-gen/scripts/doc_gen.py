#!/usr/bin/env python3
"""
DDD 技术文档自动生成工具 (doc-gen) — CLI 入口

用法:
  python3 doc_gen.py scan /path/to/project               # 扫描项目
  python3 doc_gen.py scan /path/to/project --build       # 生成 manifest + 构建站点
  python3 doc_gen.py scan /path/to/project --manifest-only
  python3 doc_gen.py scan --from-manifest manifest.json --build
  python3 doc_gen.py scan /path/to/project --init

多项目聚合已迁移至架构鹰眼: arch-hawkeye/scripts/hawkeye.py aggregate
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from doctypes import (
    DocManifest, DomainDoc, LayerDoc, ComponentDoc, FieldDoc, EndpointDoc,
    AggregateDoc, DiagramSet, CrossDomainDep,
)

from scanner.maven import MavenScanner
from scanner.java import JavaScanner
from scanner.ddl import DDLScanner
from scanner.infra_db import InfrastructureDBExtractor
from scanner.po_scanner import POScanner
from scanner.state_machine import StateMachineScanner
from scanner.business_context import BusinessContextScanner

from generator.manifest import ManifestGenerator
from generator.openapi import OpenAPIGenerator
from generator.risks import RiskScanner
from generator.adr import AdrScanner
from generator.article import ArticleScanner

from builder.writer import ManifestWriter, collect_evidence
from builder.astro import build_astro
from validator import validate_manifest_dir


# ── Receipt 契约 ────────────────────────────────────────────────────────────────


def build_receipt(checks: dict) -> dict:
    """组装验收 receipt。ok 当且仅当无 fail（warn 是事实降级，不阻断）。"""
    ok = all(c.get("status") != "fail" for c in checks.values())
    return {"schema_version": 1, "ok": ok, "checks": checks}


def write_receipt(manifest_dir, receipt: dict) -> None:
    """写入 doc-manifest/receipt.json（诚实契约的唯一机器可读载体）"""
    manifest_dir = Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


def _finish(receipt: dict, manifest_dir, summary: str) -> None:
    """统一收尾：写 receipt，按 ok 决定退出码与结束语。"""
    write_receipt(manifest_dir, receipt)
    if receipt["ok"]:
        print(f"\n✅ {summary}")
    else:
        failed = [k for k, c in receipt["checks"].items()
                  if c.get("status") == "fail"]
        print(f"\n❌ 阶段失败: {', '.join(failed)}（详见 receipt.json）",
              file=sys.stderr)
        sys.exit(1)


# ── CLI 入口 ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="doc-gen — DDD 技术文档自动生成工具（单项目）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # scan — 单项目扫描
    scan_parser = sub.add_parser("scan", help="扫描单个 Java 项目",
        epilog="示例: doc_gen.py scan /path/to/project --build --output site/")
    scan_parser.add_argument("project", help="Java 项目根目录路径")
    scan_parser.add_argument("--build", action="store_true", help="生成完整静态站点")
    scan_parser.add_argument("--manifest-only", action="store_true", help="仅生成 manifest")
    scan_parser.add_argument("--output", "-o", default=".", help="输出目录（默认当前目录）")
    scan_parser.add_argument("--config", "-c", help="项目配置文件 .doc-gen.json")
    scan_parser.add_argument("--init", action="store_true", help="初始化项目配置文件")
    scan_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    scan_parser.add_argument("--from-manifest", help="从已有 manifest 构建站点")

    # diff — 架构演进对比（delta）
    diff_parser = sub.add_parser("diff", help="对比两份 DocManifest 快照的架构演进",
        epilog="示例: doc_gen.py diff archive/a1b2c3d/doc-manifest ./doc-manifest"
               " --output delta.json --markdown delta.md")
    diff_parser.add_argument("base_manifest", help="基准快照目录（doc-manifest/）")
    diff_parser.add_argument("head_manifest", help="对比快照目录（doc-manifest/）")
    diff_parser.add_argument("--output", "-o", default="delta.json", help="JSON receipt 输出路径")
    diff_parser.add_argument("--markdown", "-m", help="Markdown 摘要输出路径（可选）")

    # 兼容旧版无子命令调用
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("scan", "diff"):
        sys.argv.insert(1, "scan")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "diff":
        _diff_manifests(args)
        return

    if args.command == "scan":
        _scan_project(args)
        return


# ── 扫描流程 ──────────────────────────────────────────────────────────────────


def _scan_project(args):
    """单项目扫描（scan 子命令 / 旧版兼容）"""
    # --init 模式
    if args.init:
        if not args.project:
            print("❌ --init 需要指定项目路径", file=sys.stderr)
            sys.exit(2)
        _init_config(args.project)
        return

    # --from-manifest 模式
    if args.from_manifest:
        _build_from_manifest(args.from_manifest, args.output)
        return

    if not args.project:
        print("❌ 请指定项目路径", file=sys.stderr)
        sys.exit(2)

    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        print(f"❌ 目录不存在: {args.project}", file=sys.stderr)
        sys.exit(2)

    config = _load_config(project_root)

    print(f"🔍 doc-gen 扫描: {project_root}")
    print()

    checks: dict = {}

    # Phase 1: Maven 模块扫描
    print("📦 扫描 Maven 模块结构...")
    maven = MavenScanner(str(project_root))
    maven_info = maven.scan()
    if "error" in maven_info:
        print(f"  ⚠ {maven_info['error']}")
        checks["maven"] = {"status": "warn", "error": maven_info["error"]}
    else:
        print(f"  ✓ groupId={maven_info.get('groupId')}, 模块数={len(maven_info.get('modules', {}))}")
        checks["maven"] = {"status": "ok", "modules": len(maven_info.get("modules", {}))}

    # Phase 2: Java 源码扫描
    print("☕ 扫描 Java 源码...")
    java = JavaScanner(str(project_root))
    java_files = java.scan_java_files()
    print(f"  ✓ 找到 {len(java_files)} 个 Java 类")
    checks["java"] = {"status": "ok", "classes": len(java_files)}
    if java_files:
        print()
        print("  ⚠ 注意：Java 源码扫描基于正则表达式，以下情况可能导致信息不完整：")
        print("    • 泛型嵌套超过 2 层（如 Map<String, List<Map<Integer, String>>>）")
        print("    • 字符串字面量中包含 class/@ 关键字")
        print("    • Lambda 表达式、匿名内部类")
        print("    • 多注解合并（@A @B class Foo）")
        print("    • 注释内的假匹配")
        print("  建议对关键类手动核对生成的文档。")
        print()

    # Phase 3: 数据库扫描
    print("🗄️  扫描数据库结构...")
    ddl_tables = DDLScanner(str(project_root)).scan()
    infra_tables = []
    db_inferred = False
    if not ddl_tables:
        print("  ⚠ 未找到 .sql 文件，从代码推断...")
        po_tables = POScanner(str(project_root)).scan(java_files)
        if po_tables:
            tables = po_tables
            db_inferred = True
            print(f"  ✓ 从 PO 注解推断出 {len(tables)} 张表 (MyBatis-Plus)")
        else:
            infra_extractor = InfrastructureDBExtractor(str(project_root))
            infra_tables = infra_extractor.extract(java_files)
            tables = infra_tables
            db_inferred = bool(tables)
            if tables:
                print(f"  ✓ 从代码推断出 {len(tables)} 张表")
    else:
        tables = ddl_tables
        if infra_tables:
            tables.extend(infra_tables)
    print(f"  ✓ 共 {len(tables)} 张数据库表")
    checks["database"] = {"status": "ok", "tables": len(tables),
                          "inferred": db_inferred}

    # Phase 3.5: 状态机扫描
    print("🔀 扫描状态机...")
    state_machines = StateMachineScanner(str(project_root)).scan(java_files)
    print(f"  ✓ 识别 {len(state_machines)} 个状态机")
    checks["stateMachines"] = {"status": "ok", "count": len(state_machines)}

    # Phase 3.6: 业务上下文扫描（可选扩展分片：business-context.md 人工叙事
    #            + @PreAuthorize 角色/状态机流程弱信号；全空不产出分片）
    print("🏢 扫描业务上下文...")
    biz_ctx = BusinessContextScanner(str(project_root), config).scan(java_files, state_machines)
    if biz_ctx is not None:
        biz_total = sum(len(x) for x in (biz_ctx.customers, biz_ctx.roles,
                                         biz_ctx.scenarios, biz_ctx.flows))
        checks["businessContext"] = {"status": "ok", "total": biz_total}
        print(f"  ✓ 业务上下文 {biz_total} 条（客户/角色/场景/流程）")
    else:
        checks["businessContext"] = {"status": "skipped"}
        print("  ℹ 无 business-context.md 且无弱信号，跳过")

    # Phase 4: 生成 manifest
    print()
    print("📋 生成 DocManifest（分片）...")
    gen = ManifestGenerator(str(project_root), config)
    manifest = gen.generate(java_files, maven_info, tables,
                            state_machines=state_machines, db_inferred=db_inferred)
    manifest.businessContext = biz_ctx

    domains_count = len(manifest.domains)
    components_count = sum(
        len(layer_data.components)
        for domain in manifest.domains
        for layer_data in domain.layers.values()
        if layer_data
    )
    print(f"  ✓ {domains_count} 个业务域, {components_count} 个组件")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 4.5: OpenAPI 生成（在 ManifestWriter.write() 之前）
    print("🔌 生成 OpenAPI 3.0 规范...")
    oapi_gen = OpenAPIGenerator(str(project_root))
    oapi_spec = oapi_gen.generate(manifest)
    path_count = len(oapi_spec.get("paths", {}))
    has_controllers = any(
        c.type == "controller"
        for domain in manifest.domains
        for c in domain.layers.get("adapter", LayerDoc()).components
    )
    if path_count > 0:
        manifest.openapiSpecs["default"] = oapi_spec
        print(f"  ✓ {path_count} 个 API 路径")
        checks["openapi"] = {"status": "ok", "paths": path_count}
    elif has_controllers:
        manifest.openapiSpecs["default"] = oapi_spec
        print(f"  ⚠ 检测到 Controller 但未能提取端点，生成空 API 规范")
        checks["openapi"] = {"status": "warn", "paths": 0}
    else:
        print("  ℹ 未检测到 Controller")
        checks["openapi"] = {"status": "skipped"}

    # Phase 4.6: 写入 manifest（此时 openapiSpecs 已填充；附 evidence）
    print()
    print("📋 写入 DocManifest（分片）...")
    evidence = collect_evidence(project_root, config)
    if evidence.get("dirty"):
        print("  ⚠ 工作区有未提交变更（evidence.dirty=true），"
              "revision 与扫描内容可能不一致")
    if evidence.get("revision"):
        print(f"  ✓ evidence 钉定 revision {evidence['revision'][:12]}")
    else:
        print("  ⚠ 无 git 仓库或获取 SHA 失败，evidence.revision=null")
    writer = ManifestWriter(output_dir, evidence=evidence)
    try:
        writer.write(manifest)
        checks["manifest"] = {"status": "ok"}
    except RuntimeError as e:
        print(f"  ❌ {e}", file=sys.stderr)
        checks["manifest"] = {"status": "fail"}

    if manifest.openapiSpecs:
        (output_dir / "doc-manifest" / "api-spec.json").write_text(
            json.dumps(oapi_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    shard_count = sum(1 for _ in (output_dir / "doc-manifest").rglob("*.json"))
    print(f"  ✓ 分片已写入: {output_dir / 'doc-manifest/'} ({shard_count} 个文件)")
    checks["manifest"]["shards"] = shard_count

    # Phase 4.7: 架构风险扫描
    print()
    print("⚠️  扫描架构风险...")
    risk_scanner = RiskScanner(str(project_root))
    risks = risk_scanner.scan()
    if "error" in risks:
        print(f"  ⚠ {risks['error']}")
        checks["risks"] = {"status": "warn", "error": risks["error"]}
    else:
        (output_dir / "doc-manifest" / "risks.json").write_text(
            json.dumps(risks, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {risks.get('totalIssues', 0)} 个风险 "
              f"(高危: {risks.get('criticalCount', 0)}, "
              f"警告: {risks.get('warningCount', 0)})")
        checks["risks"] = {"status": "ok",
                           "critical": risks.get("criticalCount", 0),
                           "warning": risks.get("warningCount", 0)}

    # Phase 4.8: ADR 扫描
    print("📋 扫描架构决策记录（ADR）...")
    adr_scanner = AdrScanner(str(project_root))
    adrs = adr_scanner.scan()
    (output_dir / "doc-manifest" / "adrs.json").write_text(
        json.dumps(adrs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {adrs.get('total', 0)} 个 ADR")
    checks["adrs"] = {"status": "ok", "total": adrs.get("total", 0)}

    # Phase 4.9: 手写深度文档扫描
    print("📝 扫描手写深度文档...")
    articles = ArticleScanner(str(project_root)).scan()
    (output_dir / "doc-manifest" / "articles.json").write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    cats = articles.get("categories", {})
    cat_summary = ", ".join(f"{k}:{v}" for k, v in cats.items())
    print(f"  ✓ {articles.get('total', 0)} 篇深度文档 ({cat_summary})")
    checks["articles"] = {"status": "ok", "total": articles.get("total", 0)}

    manifest_dir = output_dir / "doc-manifest"

    if args.build:
        print()
        print("🏗️  构建 Astro 静态站点...")
        checks["build"] = {"status": "ok"} if build_astro(output_dir, manifest_dir) \
            else {"status": "fail"}
    else:
        checks["build"] = {"status": "skipped"}

    receipt = build_receipt(checks)
    _finish(receipt, manifest_dir,
            f"完成！Manifest 分片 → {manifest_dir}"
            + ("" if args.build else "（使用 --build 生成静态站点）"))


# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def _init_config(project_root: str):
    """初始化项目配置文件 .doc-gen.json"""
    root = Path(project_root)
    config_path = root / ".doc-gen.json"

    if config_path.exists():
        print(f"⚠ 配置文件已存在: {config_path}")
        return

    group_id = ""
    root_pom = root / "pom.xml"
    if root_pom.exists():
        maven = MavenScanner(str(root))
        maven_info = maven.scan()
        group_id = maven_info.get("groupId", "")

    config = {
        "project_name": root.name,
        "project_description": "",
        "project_group_id": group_id,
        "project_repo": "",
        "domain_names": {},
    }

    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ 配置文件已创建: {config_path}")


def _load_config(project_root: Path) -> dict:
    """加载项目配置文件"""
    config_path = project_root / ".doc-gen.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _check_manifest_contract(manifest_dir: Path) -> dict:
    """消费端 schema 门禁。

    - index.json 含 schema_version:1 → 严格校验全部分片，失败 exit 1
    - 无 schema_version（旧版）→ warn 跳过（additive 兼容，不把旧文件变硬失败）
    返回 receipt 的 manifest check。
    """
    index_path = manifest_dir / "index.json"
    if not index_path.exists():
        print(f"❌ 缺少 index.json: {manifest_dir}", file=sys.stderr)
        sys.exit(2)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1:
        print("  ⚠ 旧版 manifest（无 schema_version），跳过 schema 校验")
        return {"status": "warn", "reason": "legacy manifest"}
    errors = validate_manifest_dir(manifest_dir)
    if errors:
        print(f"❌ manifest 分片未通过 schema 契约:", file=sys.stderr)
        for e in errors[:20]:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ manifest 通过 schema 契约校验（schema_version=1）")
    return {"status": "ok", "schemaVersion": 1}


def _stale_commits(manifest_dir: Path) -> int | None:
    """文档新鲜度：meta.json 钉定的 revision 落后当前 HEAD 多少 commit。

    无 git / 无 revision / 向上未找到 .git 时返回 None（无法判定）。
    """
    meta_path = manifest_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        evidence = json.loads(meta_path.read_text(encoding="utf-8")).get("evidence", {})
        revision = evidence.get("revision")
        if not revision:
            return None
        root = manifest_dir
        while root != root.parent and not (root / ".git").exists():
            root = root.parent
        if not (root / ".git").exists():
            return None
        out = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", f"{revision}..HEAD"],
            capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        return int(out)
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _build_from_manifest(manifest_path: str, output_dir: str):
    """从已有 manifest 构建站点（支持单文件或分片目录）"""
    manifest_src = Path(manifest_path)
    if not manifest_src.exists():
        print(f"❌ Manifest 不存在: {manifest_path}", file=sys.stderr)
        sys.exit(2)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if manifest_src.is_dir() and (manifest_src / "index.json").exists():
        manifest_dir = manifest_src
    elif manifest_src.is_file() and manifest_src.suffix == ".json":
        print("  ℹ 检测到旧版单文件 manifest，转换为分片...")
        manifest_data = json.loads(manifest_src.read_text(encoding="utf-8"))
        manifest = _dict_to_manifest(manifest_data)
        writer = ManifestWriter(out)
        try:
            writer.write(manifest)
        except RuntimeError as e:
            print(f"❌ 旧版 manifest 转换后未通过 schema 契约: {e}",
                  file=sys.stderr)
            sys.exit(1)
        manifest_dir = out / "doc-manifest"
        # 修复：旧版 manifest 中的 openapiSpecs 丢失 → 写入 api-spec.json
        if manifest_data.get("openapiSpecs"):
            api_spec_file = manifest_dir / "api-spec.json"
            api_spec_file.write_text(
                json.dumps(manifest_data["openapiSpecs"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  ✓ 已写入 api-spec.json（来自旧版 openapiSpecs）")
    else:
        print(f"❌ 无效的 manifest: {manifest_path}", file=sys.stderr)
        sys.exit(2)

    manifest_check = _check_manifest_contract(manifest_dir)
    stale = _stale_commits(manifest_dir)
    if stale is not None and stale > 0:
        print(f"  ⚠ 文档已落后当前 HEAD {stale} 个提交（evidence 钉定的版本可能过期）")
        manifest_check["staleCommits"] = stale

    ok = build_astro(out, manifest_dir)
    receipt = build_receipt({
        "manifest": manifest_check,
        "build": {"status": "ok"} if ok else {"status": "fail"},
    })
    _finish(receipt, manifest_dir, f"站点构建完成 → {out / 'dist'}")


def _diff_manifests(args):
    """架构演进对比：两份快照 → delta receipt（JSON + 可选 Markdown）。

    退出码语义（诚实契约）：0 = 对比成功完成（不代表无变化）；
    2 = 输入无效（缺 index.json / schema_version 不相等）。
    """
    from delta import diff_snapshots, load_snapshot, render_markdown

    try:
        base = load_snapshot(args.base_manifest)
        head = load_snapshot(args.head_manifest)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)

    if base["schema_version"] != head["schema_version"]:
        print(f"❌ schema_version 不相等: base={base['schema_version']!r} "
              f"head={head['schema_version']!r}，拒绝对比（契约门禁）",
              file=sys.stderr)
        sys.exit(2)
    if base["schema_version"] != 1:
        print(f"❌ 旧版 manifest（schema_version={base['schema_version']!r}），"
              f"无法对比", file=sys.stderr)
        sys.exit(2)

    receipt = diff_snapshots(base, head)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    s = receipt["summary"]
    total = sum(sum(v.values()) for v in s.values())
    print(f"🔀 架构演进 delta:")
    print(f"  基准 {_short_sha(receipt['base']['revision'])} → "
          f"当前 {_short_sha(receipt['head']['revision'])}")
    for dim, counts in s.items():
        parts = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        print(f"  {dim}: {parts or '无变化'}")
    print(f"  ✓ receipt → {output}（共 {total} 处变化）")

    if args.markdown:
        Path(args.markdown).write_text(render_markdown(receipt), encoding="utf-8")
        print(f"  ✓ markdown → {args.markdown}")


def _short_sha(revision) -> str:
    return revision[:12] if revision else "?"


def _dict_to_manifest(data: dict) -> DocManifest:
    """将 dict 转回 DocManifest 对象（旧版兼容）"""
    manifest = DocManifest()
    manifest.meta = data.get("meta", {})
    manifest.openapiSpecs = data.get("openapiSpecs", {})
    manifest.database = data.get("database", {"tables": []})

    for dd in data.get("domains", []):
        domain = DomainDoc(
            name=dd.get("name", ""),
            displayName=dd.get("displayName", ""),
            description=dd.get("description", ""),
            modulePrefix=dd.get("modulePrefix", ""),
        )
        for layer_name, ld in dd.get("layers", {}).items():
            layer = LayerDoc(
                javaPackage=ld.get("javaPackage", ""),
                mavenModule=ld.get("mavenModule", ""),
            )
            for cd in ld.get("components", []):
                comp = ComponentDoc(
                    type=cd.get("type", ""),
                    className=cd.get("className", ""),
                    qualifiedName=cd.get("qualifiedName", ""),
                    sourcePath=cd.get("sourcePath", ""),
                    description=cd.get("description", ""),
                    methods=cd.get("methods", []),
                    deprecated=cd.get("deprecated", False),
                )
                for fd in cd.get("fields", []):
                    comp.fields.append(FieldDoc(
                        name=fd.get("name", ""),
                        type=fd.get("type", ""),
                        kind=fd.get("kind", ""),
                        comment=fd.get("comment", ""),
                        deprecated=fd.get("deprecated", False),
                    ))
                for ep in cd.get("endpoints", []):
                    comp.endpoints.append(EndpointDoc(
                        method=ep.get("method", ""),
                        path=ep.get("path", ""),
                        summary=ep.get("summary", ""),
                        requestBody=ep.get("requestBody", ""),
                        responseBody=ep.get("responseBody", ""),
                        deprecated=ep.get("deprecated", False),
                    ))
                layer.components.append(comp)

            for ad in ld.get("aggregates", []):
                agg = AggregateDoc(name=ad.get("name", ""))
                if ad.get("rootEntity"):
                    agg.rootEntity = ComponentDoc(**ad["rootEntity"])
                layer.aggregates.append(agg)

            domain.layers[layer_name] = layer

        manifest.domains.append(domain)

    dia_data = data.get("diagrams", {})
    manifest.diagrams = DiagramSet(
        architectureOverview=dia_data.get("architectureOverview", ""),
        layeredDependency=dia_data.get("layeredDependency", ""),
        domainAggregates=dia_data.get("domainAggregates", {}),
        erDiagram=dia_data.get("erDiagram", ""),
    )

    for cd_data in data.get("crossDomainDependencies", []):
        manifest.crossDomainDependencies.append(CrossDomainDep(
            fromDomain=cd_data.get("fromDomain", ""),
            toDomain=cd_data.get("toDomain", ""),
            type=cd_data.get("type", ""),
            description=cd_data.get("description", ""),
        ))

    return manifest


def _update_index_has_openapi(index_path: Path):
    """更新 index.json 中的 hasOpenApi 标志（向后兼容）"""
    if not index_path.exists():
        return
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    idx["hasOpenApi"] = True
    index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
