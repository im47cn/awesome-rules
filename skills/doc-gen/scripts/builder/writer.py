"""ManifestWriter — 将 DocManifest 拆分为分片文件写入，支持域级并发生成。

从 doc_gen.py 提取，逻辑保持不变。
"""

from __future__ import annotations  # 兼容 Python 3.9：延迟求值 PEP 604 联合类型注解

import json
import subprocess
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from validator import validate_manifest_dir

from doctypes import (
    AggregateDoc,
    ComponentDoc,
    CrossDomainDep,
    DiagramSet,
    DocManifest,
    DomainDoc,
    EndpointDoc,
    FieldDoc,
    LayerDoc,
    TableDoc,
    TableColumnDoc,
    TableIndexDoc,
)


def collect_evidence(project_root: Path, config: dict) -> dict:
    """采集 revision-pinned evidence（借鉴 archify 的钉版本语义）。

    - revision: 生成时刻的 HEAD SHA（40 位），无 git 时为 None（降级不阻断）
    - dirty: 工作区是否有未提交变更（脏工作区的 SHA 对不上扫描内容，必须如实标注）
    - repo_url: 来自项目配置 project_repo，未配置为 None
    """
    revision = None
    dirty = False
    try:
        revision = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(project_root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        dirty = bool(status)
    except (subprocess.SubprocessError, OSError):
        pass  # 无 git / 浅克隆 / 非 git 目录：降级为 revision=None

    return {
        "repo_url": config.get("project_repo") or None,
        "revision": revision if re_sha(revision) else None,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dirty": dirty,
    }


def re_sha(value) -> bool:
    """校验 40 位十六进制 SHA"""
    if not isinstance(value, str) or len(value) != 40:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in value)


def _custom_serializer(obj):
    """JSON 序列化辅助函数，处理 dataclass 类型"""
    if isinstance(obj, (DocManifest, ComponentDoc, FieldDoc, AggregateDoc,
                        LayerDoc, DomainDoc, DiagramSet, CrossDomainDep,
                        TableDoc, TableColumnDoc, TableIndexDoc, EndpointDoc)):
        return {k: v for k, v in obj.__dict__.items() if v is not None}
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class ManifestWriter:
    """将 DocManifest 拆分为分片文件写入，支持域级并发生成

    输出结构:
      doc-manifest/
      ├── index.json           # 域列表 + 统计
      ├── meta.json            # 项目元信息
      ├── diagrams.json        # Mermaid 图
      ├── database.json        # 表结构
      ├── cross-domain.json    # 跨域依赖
      └── domains/
          └── {domain}.json    # 每域一个文件
    """

    INDEX_KEYS = {"schemaVersion", "generatedAt", "generator", "project",
                   "domainCount", "componentCount", "tableCount",
                   "hasOpenApi", "hasDeepAnalysis", "hasCrossDomain",
                   "domains"}

    def __init__(self, output_dir: Path, max_workers: int = 4,
                 evidence: dict | None = None):
        self.output_dir = output_dir
        self.manifest_dir = output_dir / "doc-manifest"
        self.max_workers = max_workers
        self.evidence = evidence

    def write(self, manifest: DocManifest):
        """写入分片文件"""
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        (self.manifest_dir / "domains").mkdir(exist_ok=True)

        meta = manifest.meta
        domains = manifest.domains

        # 1. meta.json（含 revision-pinned evidence）
        meta_payload = {"project": meta.get("project", {})}
        if self.evidence:
            meta_payload["evidence"] = self.evidence
        (self.manifest_dir / "meta.json").write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 2. diagrams.json
        (self.manifest_dir / "diagrams.json").write_text(
            json.dumps(self._serialize(manifest.diagrams),
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 3. database.json
        (self.manifest_dir / "database.json").write_text(
            json.dumps(manifest.database, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 3.1 state-machines.json（结构化：状态/转换/质量审查；图文本见 diagrams.json）
        (self.manifest_dir / "state-machines.json").write_text(
            json.dumps([self._serialize(sm) for sm in manifest.stateMachines],
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 3.2 business-context.json（可选扩展分片：业务维度，None 则不写出）
        if manifest.businessContext is not None:
            (self.manifest_dir / "business-context.json").write_text(
                json.dumps(self._serialize_business_context(manifest.businessContext),
                           ensure_ascii=False, indent=2),
                encoding="utf-8")

        # 4. cross-domain.json
        cross = []
        for cd in manifest.crossDomainDependencies:
            cross.append({
                "fromDomain": cd.fromDomain,
                "toDomain": cd.toDomain,
                "type": cd.type,
                "description": cd.description,
                "evidence": cd.evidence,
            })
        (self.manifest_dir / "cross-domain.json").write_text(
            json.dumps(cross, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 5. 并发写各域文件（I/O 密集，多线程有效；失败即记录，写入后统一裁决）
        domain_entries = []
        failed_domains: list[str] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._write_domain_file, d): d
                for d in domains
            }
            for fut in as_completed(futures):
                d = futures[fut]
                try:
                    entry = fut.result()
                    domain_entries.append(entry)
                except Exception as e:
                    print(f"  ⚠ 写入域 {d.name} 失败: {e}", file=sys.stderr)
                    failed_domains.append(d.name)

        # 6. index.json（schema_version: 1 为契约版本，与 generator 的
        #    schemaVersion 字符串字段语义不同：前者锁定分片结构，后者记录格式历史）
        index = {
            "schema_version": 1,
            "schemaVersion": meta.get("schemaVersion", "1.0"),
            "generatedAt": meta.get("generatedAt", ""),
            "generator": meta.get("generator", "doc-gen v0.1.0"),
            "project": meta.get("project", {}),
            "domainCount": len(domains),
            "componentCount": sum(e["componentCount"] for e in domain_entries),
            "tableCount": len(manifest.database.get("tables", [])),
            "hasOpenApi": len(manifest.openapiSpecs) > 0,
            "hasDeepAnalysis": "deepAnalysis" in meta,
            "hasCrossDomain": len(cross) > 0,
            "domains": domain_entries,
        }
        (self.manifest_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 7. 生成端自检（archify "validate after every edit" 的等价物）：
        #    写出的分片必须通过 schema 契约，否则视为生成器 bug，不静默出劣质产物
        errors = []
        if failed_domains:
            errors.append(f"以下域分片写入失败: {', '.join(sorted(failed_domains))}")
        errors.extend(validate_manifest_dir(self.manifest_dir))
        if errors:
            raise RuntimeError(
                "DocManifest 分片 schema 自检失败（生成器 bug，请检查 "
                "doctypes.py 与 schemas/ 是否同步）:\n  " + "\n  ".join(errors[:20]))

    def _write_domain_file(self, domain: DomainDoc) -> dict:
        """写入单个域文件，返回 index 条目"""
        domain_data = {
            "name": domain.name,
            "displayName": domain.displayName,
            "description": domain.description,
            "modulePrefix": domain.modulePrefix,
            "layers": {},
        }

        total_comps = 0
        for layer_name, layer_doc in domain.layers.items():
            comps = layer_doc.components
            if not comps and not layer_doc.aggregates:
                continue

            layer_data = {
                "javaPackage": layer_doc.javaPackage,
                "mavenModule": layer_doc.mavenModule,
                "components": [self._serialize_component(c) for c in comps],
            }

            if layer_doc.aggregates:
                layer_data["aggregates"] = []
                for agg in layer_doc.aggregates:
                    agg_data = {"name": agg.name, "kind": agg.kind}
                    if agg.rootEntity:
                        agg_data["rootEntity"] = self._serialize_component(agg.rootEntity)
                    if agg.entities:
                        agg_data["entities"] = [
                            self._serialize_component(e) for e in agg.entities
                        ]
                    if agg.valueObjects:
                        agg_data["valueObjects"] = [
                            self._serialize_component(v) for v in agg.valueObjects
                        ]
                    if agg.domainServices:
                        agg_data["domainServices"] = [
                            self._serialize_component(s) for s in agg.domainServices
                        ]
                    if agg.domainEvents:
                        agg_data["domainEvents"] = [
                            self._serialize_component(e) for e in agg.domainEvents
                        ]
                    layer_data["aggregates"].append(agg_data)

            domain_data["layers"][layer_name] = layer_data
            total_comps += len(comps)

        file_path = self.manifest_dir / "domains" / f"{domain.name}.json"
        file_path.write_text(
            json.dumps(domain_data, ensure_ascii=False, indent=2),
            encoding="utf-8")

        return {
            "name": domain.name,
            "displayName": domain.displayName,
            "description": domain.description,
            "componentCount": total_comps,
            "layers": list(domain_data["layers"].keys()),
            "file": f"domains/{domain.name}.json",
        }

    @staticmethod
    def _serialize_business_context(ctx) -> dict[str, Any]:
        """业务上下文分片序列化（契约：business-context.schema.json）"""
        def _item(i) -> dict[str, Any]:
            d = {"name": i.name, "source": i.source}
            if i.description:
                d["description"] = i.description
            if getattr(i, "domain", ""):
                d["domain"] = i.domain
            if i.anchors:
                d["anchors"] = i.anchors
            return d

        def _step(s) -> dict[str, Any]:
            d = {"name": s.name}
            if s.description:
                d["description"] = s.description
            if s.anchors:
                d["anchors"] = s.anchors
            return d

        def _flow(f) -> dict[str, Any]:
            d = {"name": f.name, "source": f.source}
            if f.description:
                d["description"] = f.description
            if f.anchors:
                d["anchors"] = f.anchors
            if f.steps:
                d["steps"] = [_step(s) for s in f.steps]
            return d

        return {
            "schema_version": 1,
            "customers": [_item(i) for i in ctx.customers],
            "roles": [_item(i) for i in ctx.roles],
            "scenarios": [_item(i) for i in ctx.scenarios],
            "flows": [_flow(f) for f in ctx.flows],
        }

    @staticmethod
    def _serialize_component(c: ComponentDoc) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": c.type,
            "className": c.className,
            "qualifiedName": c.qualifiedName,
            "sourcePath": c.sourcePath,
            "description": c.description,
        }
        if getattr(c, "sourceLine", 0):
            d["sourceLine"] = c.sourceLine
        if c.deprecated:
            d["deprecated"] = True
        if c.annotations:
            d["annotations"] = c.annotations
        if c.methods:
            d["methods"] = c.methods
        if c.fields:
            d["fields"] = [
                {"name": f.name, "type": f.type, "kind": f.kind, "comment": f.comment,
                 "deprecated": f.deprecated}
                for f in c.fields
            ]
        if c.endpoints:
            d["endpoints"] = [
                {"method": e.method, "path": e.path, "summary": e.summary,
                 "requestBody": e.requestBody, "responseBody": e.responseBody,
                 "deprecated": e.deprecated}
                for e in c.endpoints
            ]
        if c.interfaces:
            d["interfaces"] = c.interfaces
        if c.deps:
            d["deps"] = c.deps
        if c.feignClient is not None:
            d["feignClient"] = {
                "name": c.feignClient.name, "path": c.feignClient.path,
                "contextId": c.feignClient.contextId, "url": c.feignClient.url,
            }
        if c.mqChannels:
            d["mqChannels"] = [
                {"role": m.role, "channel": m.channel,
                 "framework": m.framework, "via": m.via}
                for m in c.mqChannels
            ]
        if c.cacheKeys:
            d["cacheKeys"] = [
                {"key": k.key, "via": k.via} for k in c.cacheKeys
            ]
        if c.schedules:
            d["schedules"] = [
                {"handler": j.handler, "cron": j.cron, "via": j.via}
                for j in c.schedules
            ]
        return d

    @staticmethod
    def _serialize(obj) -> Any:
        """递归序列化 dataclass → dict"""
        if hasattr(obj, "__dataclass_fields__"):
            return {k: ManifestWriter._serialize(v) for k, v in asdict(obj).items()
                    if v is not None}
        if isinstance(obj, list):
            return [ManifestWriter._serialize(i) for i in obj]
        if isinstance(obj, dict):
            return {k: ManifestWriter._serialize(v) for k, v in obj.items()
                    if v is not None}
        return obj
