#!/usr/bin/env python3
"""
DDD 技术文档自动生成工具 (doc-gen) — CLI 入口

用法:
  python3 doc_gen.py scan /path/to/project               # 扫描项目
  python3 doc_gen.py scan /path/to/project --build       # 生成 manifest + 构建站点
  python3 doc_gen.py scan /path/to/project --manifest-only
  python3 doc_gen.py scan --from-manifest manifest.json --build
  python3 doc_gen.py scan /path/to/project --init
  python3 doc_gen.py aggregate projects.json --output site/
"""

import argparse
import json
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

from generator.manifest import ManifestGenerator
from generator.openapi import OpenAPIGenerator
from generator.risks import RiskScanner
from generator.adr import AdrScanner
from generator.article import ArticleScanner

from builder.writer import ManifestWriter
from builder.astro import build_astro
from builder.aggregate import aggregate_projects


# ── CLI 入口 ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="架构鹰眼 — DDD 技术文档自动生成工具",
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

    # aggregate — 多项目聚合
    agg_parser = sub.add_parser("aggregate", help="聚合多个项目到架构鹰眼站点",
        epilog="示例: doc_gen.py aggregate hawkeye-projects.json --output site/")
    agg_parser.add_argument("projects_json", help="项目列表 JSON 文件路径")
    agg_parser.add_argument("--output", "-o", default="./hawkeye-site", help="站点输出目录")
    agg_parser.add_argument("--build", action="store_true", help="聚合后立即构建站点")
    agg_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # 兼容旧版无子命令调用
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("scan", "aggregate"):
        sys.argv.insert(1, "scan")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "aggregate":
        aggregate_projects(args.projects_json, args.output, args.build, args.verbose)
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

    print(f"🔍 架构鹰眼 扫描: {project_root}")
    print()

    # Phase 1: Maven 模块扫描
    print("📦 扫描 Maven 模块结构...")
    maven = MavenScanner(str(project_root))
    maven_info = maven.scan()
    if "error" in maven_info:
        print(f"  ⚠ {maven_info['error']}")
    else:
        print(f"  ✓ groupId={maven_info.get('groupId')}, 模块数={len(maven_info.get('modules', {}))}")

    # Phase 2: Java 源码扫描
    print("☕ 扫描 Java 源码...")
    java = JavaScanner(str(project_root))
    java_files = java.scan_java_files()
    print(f"  ✓ 找到 {len(java_files)} 个 Java 类")
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

    # Phase 3.5: 状态机扫描
    print("🔀 扫描状态机...")
    state_machines = StateMachineScanner(str(project_root)).scan(java_files)
    print(f"  ✓ 识别 {len(state_machines)} 个状态机")

    # Phase 4: 生成 manifest
    print()
    print("📋 生成 DocManifest（分片）...")
    gen = ManifestGenerator(str(project_root), config)
    manifest = gen.generate(java_files, maven_info, tables,
                            state_machines=state_machines, db_inferred=db_inferred)

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
    elif has_controllers:
        manifest.openapiSpecs["default"] = oapi_spec
        print(f"  ⚠ 检测到 Controller 但未能提取端点，生成空 API 规范")
    else:
        print("  ℹ 未检测到 Controller")

    # Phase 4.6: 写入 manifest（此时 openapiSpecs 已填充）
    print()
    print("📋 写入 DocManifest（分片）...")
    writer = ManifestWriter(output_dir)
    writer.write(manifest)

    if manifest.openapiSpecs:
        (output_dir / "doc-manifest" / "api-spec.json").write_text(
            json.dumps(oapi_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    shard_count = sum(1 for _ in (output_dir / "doc-manifest").rglob("*.json"))
    print(f"  ✓ 分片已写入: {output_dir / 'doc-manifest/'} ({shard_count} 个文件)")

    # Phase 4.7: 架构风险扫描
    print()
    print("⚠️  扫描架构风险...")
    risk_scanner = RiskScanner(str(project_root))
    risks = risk_scanner.scan()
    if "error" in risks:
        print(f"  ⚠ {risks['error']}")
    else:
        (output_dir / "doc-manifest" / "risks.json").write_text(
            json.dumps(risks, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {risks.get('totalIssues', 0)} 个风险 "
              f"(高危: {risks.get('criticalCount', 0)}, "
              f"警告: {risks.get('warningCount', 0)})")

    # Phase 4.8: ADR 扫描
    print("📋 扫描架构决策记录（ADR）...")
    adr_scanner = AdrScanner(str(project_root))
    adrs = adr_scanner.scan()
    (output_dir / "doc-manifest" / "adrs.json").write_text(
        json.dumps(adrs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {adrs.get('total', 0)} 个 ADR")

    # Phase 4.9: 手写深度文档扫描
    print("📝 扫描手写深度文档...")
    articles = ArticleScanner(str(project_root)).scan()
    (output_dir / "doc-manifest" / "articles.json").write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    cats = articles.get("categories", {})
    cat_summary = ", ".join(f"{k}:{v}" for k, v in cats.items())
    print(f"  ✓ {articles.get('total', 0)} 篇深度文档 ({cat_summary})")

    manifest_dir = output_dir / "doc-manifest"

    if args.build:
        print()
        print("🏗️  构建 Astro 静态站点...")
        build_astro(output_dir, manifest_dir)
    elif args.manifest_only:
        print(f"\n✅ 完成！Manifest 分片 → {manifest_dir}")
    else:
        print(f"\n✅ 完成！Manifest 分片 → {manifest_dir}")
        print("💡 使用 --build 生成静态站点")


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
        writer.write(manifest)
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

    build_astro(out, manifest_dir)


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
