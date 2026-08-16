"""Manifest 生成器。

将 Java 扫描结果、Maven 模块信息、数据库表结构组装为 DocManifest，
包含分层识别、域分组、聚合构建、ER 关系推断、Mermaid 图表生成与跨域依赖分析。
"""

import json
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from doctypes import (
    DocManifest, DomainDoc, LayerDoc, ComponentDoc, FieldDoc, EndpointDoc,
    AggregateDoc, DiagramSet, CrossDomainDep, TableDoc, TableColumnDoc, TableIndexDoc,
    FileInfo,
    SUFFIX_TYPE_MAP_ORDERED, LAYER_PATTERNS, CONTROLLER_ANNOTATIONS, HTTP_MAPPING_ANNOTATIONS,
)
from .layers import LayerIdentifier

# 文档展示用的层顺序(含 client/start, 存在组件的层才画)
DOC_LAYER_ORDER = ["adapter", "client", "application", "domain", "infrastructure", "start"]
# 全景图依赖边(两端均存在组件才画, 避免引用未定义节点)
DOC_LAYER_EDGES = [("adapter", "application"), ("application", "domain"),
                   ("application", "client"), ("infrastructure", "domain")]
# 合法层依赖目标(与 arch-guard Tier2 矩阵口径一致)。tgt 不在此集合的跨层边 = 违规。
LEGAL_LAYER_TARGETS = {
    "adapter": {"client", "application"},
    "application": {"domain", "infrastructure", "client"},
    "domain": set(),          # 领域层不依赖其他层
    "infrastructure": {"domain"},
    "client": set(), "start": set(),
}


class ManifestGenerator:
    """将扫描结果组装为 DocManifest"""

    def __init__(self, root_path: str, project_config: Optional[dict] = None):
        self.root_path = Path(root_path).resolve()
        self.config = project_config or {}

    def generate(self,
                 java_files: list[FileInfo],
                 maven_info: dict,
                 tables: list[TableDoc],
                 state_machines: Optional[list] = None,
                 db_inferred: bool = False) -> DocManifest:
        """生成完整 DocManifest"""
        manifest = DocManifest()

        # Meta 信息
        group_id = maven_info.get("groupId", "")
        artifact_id = maven_info.get("artifactId", self.root_path.name)

        # 评估 Java 正则扫描的局限性影响（基于扫描结果的启发式判断）。
        # 如果项目包含大量泛型嵌套、Lambda、文本块等，扫描可能不完整。
        # 通过组件/文件数量比例启发式判断：组件数 < 文件数的 30% 可能表示
        # 大量类因正则限制被跳过。
        java_scanner = __import__("scanner.java", fromlist=["JavaScanner"]).JavaScanner
        all_java = java_scanner(str(self.root_path)).scan_java_files()
        total_java = len(list(self.root_path.rglob("*.java")))
        scanned_ratio = len(all_java) / max(total_java, 1)
        has_limitations = scanned_ratio < 0.3  # 扫描覆盖率低于 30% 时标记

        manifest.meta = {
            "schemaVersion": "1.0",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "generator": "doc-gen v0.1.0",
            "project": {
                "name": self.config.get("project_name") or artifact_id or self.root_path.name,
                "groupId": group_id,
                "description": self.config.get("project_description", ""),
                "repo": self.config.get("project_repo", ""),
            },
            # 扫描局限性标志（供文档生成器使用）
            "scanLimitations": {
                "hasIssues": has_limitations,
                "scannedRatio": round(scanned_ratio, 3),
                "totalJavaFiles": total_java,
                "scannedJavaFiles": len(all_java),
                "knownLimitations": [
                    "泛型嵌套 > 2 层（如 Map<String, List<Map<Integer, String>>>）",
                    "Lambda 表达式、匿名内部类",
                    "字符串字面量内出现 class/@ 关键字",
                    "多注解合并（如 @A @B class Foo）",
                    "文本块（text block）含换行和缩进",
                ],
            },
        }

        # 分层识别 + 按域名分组
        domain_groups: dict[str, dict[str, list]] = defaultdict(
            lambda: defaultdict(list)
        )

        layers = LayerIdentifier()
        modules = maven_info.get("modules", {})
        # 项目内 qn 集合：deps 依赖边过滤（只保留项目内 import，供 /impact/ 前端 BFS）
        internal_qns = {f.get("qualifiedName") for f in java_files
                        if f.get("qualifiedName")}

        for file_info in java_files:
            result = layers.classify(file_info)
            if not result:
                continue
            layer, comp_type = result

            # 确定域
            domain_name = self._find_domain(file_info, modules)

            comp = self._build_component(file_info, comp_type, layer, internal_qns)
            domain_groups[domain_name][layer].append(comp)

        # 组装 DomainDoc
        for domain_name, layer_data in domain_groups.items():
            domain_doc = DomainDoc(
                name=domain_name,
                displayName=self._domain_display_name(domain_name),
                modulePrefix=domain_name,
            )

            for layer_name, components in layer_data.items():
                layer_doc = LayerDoc(
                    javaPackage=self._guess_package(components, domain_name, layer_name),
                    components=components,
                )

                # Domain 层特殊处理：构建聚合
                if layer_name == "domain":
                    layer_doc.aggregates = self._build_aggregates(components, domain_name)

                domain_doc.layers[layer_name] = layer_doc

            manifest.domains.append(domain_doc)

        # 数据库(先组装: 含表 + 推断关系, erDiagram 依赖)
        relationships, unmatched_fks = self._infer_er_relationships(tables)
        manifest.database = {
            "tables": [asdict(t) for t in tables],
            "relationships": relationships,
            "unmatched_fks": unmatched_fks,
            "inferred": db_inferred,
            "source": "MyBatis-Plus @TableName/@TableField (PO 推断)" if db_inferred else "DDL (.sql)",
        }

        # 状态机（_generate_diagrams 生成 stateDiagram 时读取）
        manifest.stateMachines = state_machines or []

        # 生成 Mermaid 图(erDiagram 用 manifest.database, stateDiagram 用 manifest.stateMachines)
        layer_edges = self._compute_layer_edges(java_files)
        manifest.diagrams = self._generate_diagrams(manifest, layer_edges)

        # 跨域依赖
        manifest.crossDomainDependencies = self._find_cross_domain_deps(
            java_files, modules
        )

        return manifest

    def _find_domain(self, file_info: FileInfo, modules: dict) -> str:
        """从文件路径确定所属业务域（COLA / GTSP 通用）

        1. DDD 多模块: artifactId 形如 {domain}-{layer} → 剥离层后缀得域
        2. 按层分包: com.{company}.{domain}.{layer}.{...} → 域 = 层段的前一段
        无层段时回退到标准 DDD 第 3 段包名(com.{company}.{domain})。
        """
        file_path = file_info.get("filePath", "")

        # Maven 多模块：从 artifactId 推断
        for artifact_id, mod_info in modules.items():
            mod_path = mod_info.get("path", "")
            if mod_path and file_path.startswith(mod_path):
                return LayerIdentifier().identify_domain_from_module(artifact_id, modules) or "unknown"

        qualified = file_info.get("qualifiedName", "")
        parts = qualified.split(".")

        # 层段集合(与 layers.PKG_LAYER 对齐, 容纳 COLA/GTSP 命名差异)
        LAYER_NAMES = {"start", "adapter", "client", "application", "app",
                       "interfaces", "domain", "infrastructure", "infra"}

        # 定位 layer 段索引
        layer_idx = next(
            (i for i, p in enumerate(parts) if p in LAYER_NAMES), None
        )

        # 无层段 → 回退标准 DDD 第 3 段包名(com.{company}.{domain})
        if layer_idx is None:
            return parts[2] if len(parts) >= 3 else "unknown"

        # ★ 优先用 domain_names 白名单匹配「层段之后」的子段
        #   适配 com.{company}.{project}.{layer}.{...}.{domain}（业务域在层后）这类结构，
        #   domain_names 即用户在 .doc-gen.json 显式声明的业务域清单。
        whitelist = self.config.get("domain_names", {})
        if whitelist and layer_idx is not None:
            for p in parts[layer_idx + 1:]:
                if p in whitelist:
                    return p

        # 兜底启发式：域 = 层段的前一段(com.company.{order}.adapter.web → order)
        # 覆盖 COLA(com.alibaba.cola.{demo}.app) 与 GTSP(com.acme.{order}.adapter)
        if layer_idx >= 1 and parts[layer_idx - 1] not in {"com", "org", "cn", "net"}:
            return parts[layer_idx - 1]

        # 深层结构兜底: com.{company}.{domain}.{layer} 的 domain 在 parts[2]
        if len(parts) >= 3:
            return parts[2]
        return "shared-kernel" if parts[layer_idx] == "domain" else "common"

    def _build_component(self, file_info: FileInfo, comp_type: str, layer: str,
                         internal_qns: set | None = None) -> ComponentDoc:
        """构建组件文档"""
        qn = file_info.get("qualifiedName", "")
        deps = []
        if internal_qns and qn:
            deps = sorted({imp.strip().rstrip(";") for imp in file_info.get("imports", [])}
                          & internal_qns)
        comp = ComponentDoc(
            type=comp_type,
            className=file_info.get("className", ""),
            qualifiedName=qn,
            sourcePath=file_info.get("filePath", ""),
            sourceLine=file_info.get("classLine", 0),
            annotations=file_info.get("annotations", []),
            methods=[m["name"] for m in file_info.get("methods", [])],
            fields=[
                FieldDoc(name=f["name"], type=f["type"], deprecated=f.get("deprecated", False))
                for f in file_info.get("fields", [])
            ],
            classType=file_info.get("classType", ""),
            enumValues=file_info.get("enumValues", []),
            deprecated=file_info.get("deprecated", False),
            deps=deps,
        )

        # 提取 HTTP 端点（仅 Controller）
        if comp_type == "controller" and "annotations" in file_info:
            comp.endpoints = self._extract_endpoints(file_info)

        return comp

    def _extract_endpoints(self, file_info: FileInfo) -> list[EndpointDoc]:
        """从 Controller 文件中提取 REST 端点 — 解析方法级 HTTP 注解"""
        source_path = file_info.get("filePath", "")
        java_file = self.root_path / source_path
        if not java_file.exists():
            return []

        try:
            raw = java_file.read_text(encoding="utf-8")
        except Exception:
            return []

        # 1. 提取类级 @RequestMapping 前缀（兼容 value/path 关键字和裸字符串）
        class_prefix = ""
        class_header = raw.split("class ")[0] if "class " in raw else ""
        class_req_map = re.search(
            r'@RequestMapping\s*\(\s*(?:(?:value|path)\s*=\s*)?"([^"]*)"',
            class_header,
        )
        if class_req_map:
            class_prefix = class_req_map.group(1)

        # 2. 提取类体（从 "class Xxx {" 到最后的 "}"）
        class_body_start = raw.find("{", raw.find("class "))
        if class_body_start < 0:
            return []
        class_body = raw[class_body_start:]

        # 3. 搜索方法级 HTTP 注解（不使用 DOTALL，注解 → 方法签名 ≤500 字符）
        endpoints = []
        # HTTP 注解（parens 可选，兼容 @PostMapping 和 @GetMapping("/path")）
        http_anno_re = re.compile(
            r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)'
            r'(?:\(\s*((?:(?:value|path|method)\s*=\s*[^,)]+,?\s*)*'   # 命名参数
            r'(?:"[^"]*"\s*,?\s*)*'                                       # 裸字符串值
            r')\))?',
        )
        # 方法签名（跟在注解后 ≤500 字符内）
        method_sig_re = re.compile(
            r'(?:public|protected|private|\s)*'
            r'(?:static\s+)?'
            r'(?:<[^>]+>\s+)?'
            r'(\w+(?:<[^>]+>)?)\s+'             # 返回类型
            r'(\w+)\s*\(([^)]*)\)',              # 方法名 + 参数
        )

        # 在类体中逐段搜索：找 HTTP 注解 → 向后 500 字符内找方法签名
        for anno_m in http_anno_re.finditer(class_body):
            annotation = anno_m.group(1)
            anno_params_raw = anno_m.group(2) or ""

            # 向后 500 字符内找方法签名
            after_anno = class_body[anno_m.end():anno_m.end() + 500]
            sig_m = method_sig_re.search(after_anno)
            if not sig_m:
                continue

            return_type = sig_m.group(1)
            method_name = sig_m.group(2)
            method_params = sig_m.group(3)

            # 跳过构造函数（方法名与类名相同）
            if method_name == file_info.get("className", ""):
                continue

            http_method = HTTP_MAPPING_ANNOTATIONS.get(annotation, "GET")

            # 提取 path
            path = ""
            # 裸字符串路径: @GetMapping("/xxx") → anno_params = '"/xxx"'
            bare_path = re.search(r'"([^"]*)"', anno_params_raw)
            if bare_path:
                path = bare_path.group(1)

            # @RequestMapping 可能有 method 属性
            if annotation == "RequestMapping":
                method_match = re.search(
                    r'method\s*=\s*(?:RequestMethod\.)?(\w+)',
                    anno_params_raw,
                    re.IGNORECASE,
                )
                if method_match:
                    http_method = method_match.group(1).upper()

            full_path = (class_prefix.rstrip("/") + "/" + path.lstrip("/")).rstrip("/")
            if not full_path:
                full_path = "/" + path.lstrip("/") if path else "/"

            # 提取请求体参数（@RequestBody）
            request_body = ""
            body_match = re.search(
                r'@RequestBody\s+(?:@Valid(?:ated)?\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)',
                method_params,
            )
            if body_match:
                request_body = body_match.group(1)

            # 提取 @ApiOperation / @Operation 的 summary
            summary = ""
            summary_match = re.search(
                r'(?:@ApiOperation|@Operation)\s*\([^)]*(?:summary|value)\s*=\s*"([^"]*)"',
                after_anno[:300],
            )
            if summary_match:
                summary = summary_match.group(1)

            if not summary:
                summary = self._method_name_to_summary(method_name)

            # 检测方法级 @Deprecated（注解可在 HTTP 注解前或后，只要落在「本方法注解段」内）
            # 以方法签名为锚点回看到上一个成员边界(;}/{)，截取本方法注解段
            sig_abs = anno_m.end() + sig_m.start()
            pre_region = class_body[max(0, sig_abs - 300):sig_abs]
            last_sep = max(pre_region.rfind(';'), pre_region.rfind('}'), pre_region.rfind('{'))
            anno_region = pre_region[last_sep + 1:] if last_sep >= 0 else pre_region
            method_deprecated = bool(re.search(r'@(?:Deprecated|deprecated)(?:\([^)]*\))?', anno_region))

            endpoints.append(EndpointDoc(
                method=http_method,
                path=full_path,
                summary=summary[:80] if summary else "",
                requestBody=request_body,
                responseBody=return_type,
                deprecated=method_deprecated,
            ))

        # 如果方法级注解未命中，回退到类级检测
        if not endpoints:
            for ann in file_info.get("annotations", []):
                if ann in CONTROLLER_ANNOTATIONS:
                    endpoints.append(EndpointDoc(
                        method="*",
                        path=class_prefix or "/*",
                        summary=f"{ann} 端点（详见源代码）",
                    ))
                    break

        return endpoints

    @staticmethod
    def _method_name_to_summary(name: str) -> str:
        """驼峰方法名 → 中文摘要"""
        action_map = {
            "create": "创建", "add": "新增", "insert": "新增",
            "remove": "删除", "delete": "删除",
            "modify": "修改", "update": "更新", "edit": "编辑",
            "get": "查询", "query": "查询", "find": "查找",
            "page": "分页查询", "list": "列表查询",
            "count": "统计", "check": "校验", "validate": "校验",
            "save": "保存", "cancel": "取消", "submit": "提交",
            "export": "导出", "import": "导入", "sync": "同步",
        }
        for camel_prefix, zh in sorted(action_map.items(), key=lambda kv: len(kv[0]), reverse=True):
            if name.startswith(camel_prefix):
                rest = name[len(camel_prefix):]
                # rest 为空或首字母大写 → 直接返回中文摘要
                if not rest or rest[0].isupper():
                    return zh
                return zh + rest
        return name

    def _guess_package(self, components: list, domain: str, layer: str) -> str:
        """从组件推断 Java 包路径"""
        if components:
            qn = components[0].qualifiedName
            parts = qn.rsplit(".", 1)
            return parts[0] if len(parts) > 1 else ""
        return f"com.example.{domain}.{layer}"

    def _domain_display_name(self, domain: str) -> str:
        """域英文名 → 中文显示名"""
        name_map = self.config.get("domain_names", {})
        return name_map.get(domain, domain)

    def _build_aggregates(self, components: list, domain_name: str = "") -> list[AggregateDoc]:
        """从领域层组件构建聚合文档

        聚合根启发式识别：被其他实体作为字段引用的实体视为「内部实体」，
        归入引用它的聚合根，不再单独成聚合。无法判定（循环引用/无字段引用）
        时退化为「每实体一聚合」，保证安全降级。

        无实体兜底：领域层仅含领域服务/网关/值对象（行为域/能力域）时，不产出
        伪聚合根，而是以域名命名并标记 kind="behavior"，供前端渲染「行为域」标识。
        """
        entities = [c for c in components if c.type == "entity"]
        vos = [c for c in components if c.type == "valueObject"]
        services = [c for c in components if c.type == "domainService"]
        repos = [c for c in components if c.type == "repositoryInterface"]
        events = [c for c in components if c.type == "domainEvent"]
        repo_if = repos[0] if repos else None

        entity_names = {e.className for e in entities}
        vo_names = {v.className for v in vos}
        # 聚合名(去 Entity 等后缀)用于同前缀内部实体启发式
        agg_name_of = {e.className: self._strip_aggregate_name(e.className) for e in entities}

        def referenced_types(owner, candidates: set) -> list:
            """提取 owner 字段类型中引用的候选类名（兼容 List<X>/Set<X>/Map<K,X> 泛型）"""
            owned: list = []
            for f in (getattr(owner, "fields", None) or []):
                for name in re.findall(r"[A-Z]\w*", getattr(f, "type", "") or ""):
                    if name in candidates and name != owner.className and name not in owned:
                        owned.append(name)
            return owned

        def internal_by_prefix(owner_name: str) -> list:
            """同前缀启发式：聚合名以 owner 聚合名为前缀且更长的实体 → owner 的内部实体。

            适配「实体间通过外键 ID 关联、不对象持有」的 DDD 实践——此时字段引用
            启发式失效，改由命名前缀识别从属关系(如 MsgSendTaskDetail→MsgSendTask、
            LegacyMsgPushConfigParam→LegacyMsgPushConfig)。仅当 owner 是明确主干
            (存在以其聚合名开头的更长实体)时命中，避免过度聚合。
            """
            owner_agg = agg_name_of.get(owner_name, "")
            if not owner_agg:
                return []
            owned: list = []
            for e in entities:
                if e.className == owner_name:
                    continue
                ea = agg_name_of.get(e.className, "")
                if ea.startswith(owner_agg) and len(ea) > len(owner_agg):
                    owned.append(e.className)
            return owned

        # 被引用(字段持有 或 同前缀从属)为内部实体 → 非聚合根
        internal_names: set = set()
        for e in entities:
            internal_names.update(referenced_types(e, entity_names))
            internal_names.update(internal_by_prefix(e.className))

        roots = [e for e in entities if e.className not in internal_names] or entities
        # 聚合根启发式：有对应 Repository 的实体才是聚合根。
        # 无 Repository 的 BO 多为命令/查询/值对象/数据载体（如 ContractCreateBO、
        # SealQueryBO、PlatformCmCityBO），不应独立成聚合。Repository 名去
        # "Repository" 后缀 == Entity 名去 "BO/Entity/E" 后缀 视为对应；
        # 无任一匹配时退化为原 roots（保留安全降级）。
        repo_cores = {re.sub(r"Repository$", "", r.className) for r in repos}
        def _entity_core(name: str) -> str:
            return re.sub(r"(BO|Entity|E)$", "", name)
        repo_backed = [e for e in roots if _entity_core(e.className) in repo_cores]
        if repo_backed:
            roots = repo_backed

        aggregates = []
        for root in roots:
            owned_names = referenced_types(root, entity_names) + internal_by_prefix(root.className)
            owned = [e for e in entities if e.className in owned_names]
            owned_vo_names = referenced_types(root, vo_names)
            aggregates.append(AggregateDoc(
                name=self._strip_aggregate_name(root.className),
                rootEntity=root,
                entities=owned,
                valueObjects=[v for v in vos if v.className in owned_vo_names],
                domainServices=services,
                repositoryInterface=repo_if,
                domainEvents=events,
            ))

        if not aggregates and components:
            # 行为域/能力域：领域层无聚合根实体，仅有服务/网关/值对象。
            # 以域名命名、标记 kind="behavior"，避免误导性的 "Unknown" 伪聚合。
            aggregates.append(AggregateDoc(
                name=domain_name or "shared",
                kind="behavior",
                domainServices=services,
                repositoryInterface=repo_if,
                domainEvents=events,
            ))

        return aggregates

    @staticmethod
    def _strip_aggregate_name(class_name: str) -> str:
        """实体类名 → 聚合名：去掉 Entity/DO/PO 等后缀（修复 OrderEntity→Orderntity 乱码）"""
        name = re.sub(r"(Entity|DO|PO|AggregateRoot|DomainEntity)$", "", class_name)
        return name or class_name

    def _infer_er_relationships(self, tables: list) -> tuple[list, list]:
        """从 *_id/*_no 外键列名推断表关系(启发式, 无 DDL 时需人工核对)。

        返回 (relationships, unmatched_fks):
        - relationships: 强匹配的关系边 [{from, to, fk, cardinality}]
        - unmatched_fks: 未匹配到表的外键候选 [{table, column, prefix}]
        """
        def core_name(tn: str) -> str:
            for p in ("msg_", "t_", "app_"):
                if tn.startswith(p):
                    return tn[len(p):]
            return tn

        cores = {t.name: core_name(t.name) for t in tables}
        # 同义词组: 列前缀核心词 ↔ 表核心词(命名缩写差异)
        SYN_GROUPS = [{"tmpl", "template"}, {"send_task", "task"}]

        def same_syn(a: str, b: str) -> bool:
            return any(a in g and b in g for g in SYN_GROUPS)

        def match(fk_prefix: str, table_core: str) -> bool:
            if not fk_prefix or not table_core:
                return False
            if fk_prefix == table_core:
                return True
            if fk_prefix in table_core or table_core in fk_prefix:
                return True
            fa = fk_prefix.split("_")[-1]
            tb = table_core.split("_")[0]
            return same_syn(fk_prefix, table_core) or same_syn(fa, tb)

        relationships: list[dict] = []
        unmatched: list[dict] = []
        seen: set = set()

        for t in tables:
            for col in getattr(t, "columns", []):
                cn = col.name
                if getattr(col, "primaryKey", False):
                    continue
                if not (cn.endswith("_id") or cn.endswith("_no")):
                    continue
                fk_prefix = cn[:-3]  # 去 _id / _no(均3字符)
                # 收集所有候选, 选核心词最短的(主表通常命名最短, 避免 change_rec 等明细表抢占)
                candidates = [
                    (other_name, other_core)
                    for other_name, other_core in cores.items()
                    if other_name != t.name and match(fk_prefix, other_core)
                ]
                best = min(candidates, key=lambda x: len(x[1]))[0] if candidates else None
                if best:
                    key = (t.name, best, cn)
                    if key not in seen:
                        seen.add(key)
                        relationships.append({
                            "from": t.name, "to": best,
                            "fk": cn, "cardinality": "||--o{",
                        })
                else:
                    unmatched.append({"table": t.name, "column": cn, "prefix": fk_prefix})

        return relationships, unmatched

    def _generate_diagrams(self, manifest: DocManifest, layer_edges: dict = None) -> DiagramSet:
        """生成全套 Mermaid 图表"""
        ds = DiagramSet()

        # 1. 全景架构图
        lines = ["graph TD"]
        lines.append("  subgraph PROJECT[\"🏗️ 项目全景架构\"]")
        for domain in manifest.domains:
            domain_name = domain.displayName or domain.name
            domain_id = domain.name.replace("-", "_")
            lines.append(f"    subgraph {domain_id}[\"{domain_name}\"]")

            for layer_name in DOC_LAYER_ORDER:
                layer_data = domain.layers.get(layer_name)
                if layer_data and layer_data.components:
                    layer_id = f"{domain_id}_{layer_name}"
                    # 取前 3 个组件展示
                    comp_names = [c.className for c in layer_data.components[:3]]
                    label = f"{layer_name.title()}<br/>" + "<br/>".join(comp_names)
                    lines.append(f"      {layer_id}[\"{label}\"]")

            # 域内依赖方向(仅生成两端节点均存在的边, 避免引用未定义节点导致渲染失败)
            # infrastructure --> domain 表示基础设施依赖领域(依赖倒置), 箭头须用合法的 -->
            present = {ln for ln in DOC_LAYER_ORDER
                       if (ld := domain.layers.get(ln)) and ld.components}
            for src, dst in DOC_LAYER_EDGES:
                if src in present and dst in present:
                    lines.append(f"      {domain_id}_{src} --> {domain_id}_{dst}")
            lines.append("    end")

        lines.append("  end")

        # 点击事件
        for domain in manifest.domains:
            domain_name = domain.name
            domain_id = domain_name.replace("-", "_")
            for layer_name in DOC_LAYER_ORDER:
                ld = domain.layers.get(layer_name)
                if not (ld and ld.components):
                    continue
                layer_id = f"{domain_id}_{layer_name}"
                url = f"/domains/{domain_name}/{layer_name}/"
                lines.append(f"  click {layer_id} \"{url}\" \"查看{layer_name}层详情\"")

        ds.architectureOverview = "\n".join(lines)

        # 2. 分层依赖图
        dep_lines = ["flowchart LR"]
        dep_lines.append("  A[🖥️ Adapter<br/>接口层] --> B[⚙️ Application<br/>应用层]")
        dep_lines.append("  B --> C[🧠 Domain<br/>领域层]")
        dep_lines.append("  D[🏗️ Infrastructure<br/>基础设施层] --> C")
        dep_lines.append("  B --> D")
        dep_lines.append("  A -.-> E[📦 Client<br/>契约层]")
        dep_lines.append("  click A \"/architecture#adapter\"")
        dep_lines.append("  click B \"/architecture#application\"")
        dep_lines.append("  click C \"/architecture#domain\"")
        dep_lines.append("  click D \"/architecture#infrastructure\"")
        ds.layeredDependency = "\n".join(dep_lines)

        # 3. 聚合类图
        ds.domainAggregates = {}
        for domain in manifest.domains:
            layer_data = domain.layers.get("domain")
            if layer_data and layer_data.aggregates:
                agg_lines = ["classDiagram"]
                for agg in layer_data.aggregates:
                    # 行为域无聚合根, 无聚合结构可画(前端用 kind="behavior" 展示)
                    if not agg.rootEntity:
                        continue
                    entity_name = agg.rootEntity.className
                    agg_lines.append(f"  class {entity_name} {{")
                    for f in (agg.rootEntity.fields or []):
                        agg_lines.append(f"    +{f.type} {f.name}")
                    agg_lines.append("  }")
                    # 内部实体(同前缀/字段引用归并): 根 contains 内部实体
                    for ie in agg.entities:
                        agg_lines.append(f"  class {ie.className} {{")
                        agg_lines.append("    <<Entity>>")
                        agg_lines.append("  }")
                        agg_lines.append(f"  {entity_name} --> {ie.className} : contains")
                    # 值对象关系
                    for vo in agg.valueObjects:
                        agg_lines.append(f"  class {vo.className} {{")
                        agg_lines.append("    <<ValueObject>>")
                        agg_lines.append("  }")
                        agg_lines.append(f"  {entity_name} --> {vo.className}")
                # 仅当画出实际内容时才存储(全行为域域不产生空 classDiagram)
                if len(agg_lines) > 1:
                    ds.domainAggregates[domain.name] = "\n".join(agg_lines)

        # 4. 数据库 ER 图（精简版：仅表名 + 关系线，不画字段）
        # 字段会使 ER 图随表/列数线性膨胀，几十张表时极不直观。
        # 精简后只保留表名方框与外键关系线，字段详情见页面下方"表结构"区（每表可折叠）。
        if manifest.database.get("tables"):
            er_lines = ["erDiagram"]
            if manifest.database.get("inferred"):
                er_lines.append("%% 基于 PO @TableName/@TableField 注解推断, 无 DDL 支撑, 关系为启发式匹配")
            # 仅声明表存在（空字段块 → Mermaid 画一个空表名方框）
            for table in manifest.database["tables"]:
                tbl = table if isinstance(table, dict) else asdict(table)
                er_lines.append(f"  {tbl['name']} {{ }}")
            # 关系边(从外键推断)：父表(被引用,一)在前、子表(含外键,多)在后
            for rel in manifest.database.get("relationships", []):
                er_lines.append(f"  {rel['to']} {rel.get('cardinality', '||--o{')} {rel['from']} : \"{rel['fk']}\"")
            ds.erDiagram = "\n".join(er_lines)

        # 5. 状态转换图（每个状态机一张 stateDiagram-v2）
        if manifest.stateMachines:
            for sm in manifest.stateMachines:
                ds.stateMachines[sm.name] = self._render_state_diagram(sm)

        # 6. 层间真实依赖图(基于 IMPORTS, 违规跨层边标红)
        ds.layerDependencyReal = self._generate_layer_dependency_real(layer_edges or {})

        return ds

    def _compute_layer_edges(self, java_files: list) -> dict:
        """从 Java import 计算层间真实依赖矩阵 {(src_layer, tgt_layer): count}。

        复用 LayerIdentifier.classify 定层(与 _find_cross_domain_from_imports 同模式),
        对每条 import 构造伪 file_info 判目标层。同层跳过, classify 返回 None 的第三方库天然过滤。
        """
        layer_edges = defaultdict(int)
        layers = LayerIdentifier()
        for fi in java_files:
            src = layers.classify(fi)
            if not src:
                continue
            src_layer = src[0]
            for imp in fi.get("imports", []):
                tgt = layers.classify({"qualifiedName": imp, "filePath": ""})
                if not tgt:
                    continue
                tgt_layer = tgt[0]
                if src_layer != tgt_layer:
                    layer_edges[(src_layer, tgt_layer)] += 1
        return dict(layer_edges)

    def _generate_layer_dependency_real(self, layer_edges: dict) -> str:
        """生成层间真实依赖 Mermaid 图。合法边 -->, 违规边 ==> 并 linkStyle 染红。"""
        LAYER_TITLE = {
            "adapter": "Adapter 接口层", "client": "Client 契约层",
            "application": "Application 应用层", "domain": "Domain 领域层",
            "infrastructure": "Infrastructure 基础设施层", "start": "Start 启动层",
        }
        involved = set()
        for src, tgt in layer_edges:
            involved.add(src)
            involved.add(tgt)
        if not involved:
            return ""
        order = [l for l in ["adapter", "client", "application", "domain", "infrastructure", "start"]
                 if l in involved]
        lines = ["graph LR"]
        for l in order:
            lines.append(f'  {l}["{LAYER_TITLE.get(l, l)}"]')
        illegal_idx = []
        edge_idx = 0
        for (src, tgt), cnt in sorted(layer_edges.items(), key=lambda x: -x[1]):
            illegal = tgt not in LEGAL_LAYER_TARGETS.get(src, set())
            arrow = "==>" if illegal else "-->"
            tag = " 违规" if illegal else ""
            lines.append(f"  {src} {arrow}|{cnt}{tag}| {tgt}")
            if illegal:
                illegal_idx.append(edge_idx)
            edge_idx += 1
        if illegal_idx:
            lines.append(f"  linkStyle {','.join(str(i) for i in illegal_idx)} stroke:#dc2626,stroke-width:2.5px")
        return "\n".join(lines)

    def _render_state_diagram(self, sm) -> str:
        """渲染单个状态机为 Mermaid stateDiagram-v2 文本。

        - ``[*] --> initialState``  初始转换
        - ``endState --> [*]``      终止转换
        - ``source --> target : event``  业务转换
        """
        # raw enum → flowchart TD：转换箭头 + 孤立状态均带框。stateDiagram-v2 对
        # 无边的 ``state`` 声明渲染为空白，而 raw 的转换常分散在方法中、伴随孤立
        # 终态（如 finish() 参数化终态提取不到），统一用 flowchart 保证所有状态可见。
        # spring/cola → stateDiagram-v2：保留 ``[*]`` 初始/终态语义。
        if sm.framework in ("spring", "cola"):
            return self._render_state_diagram_v2(sm)

        lines = ["flowchart TD"]
        involved = set(sm.endStates or [])
        if sm.initialState:
            involved.add(sm.initialState)
        for t in sm.transitions:
            src = t.source or "?"
            dst = t.target or "?"
            involved.add(src)
            involved.add(dst)
            label = f"|{t.event}|" if t.event else ""
            lines.append(f"  {src} -->{label} {dst}")
        for st in sm.states or []:
            if st and st not in involved:
                lines.append(f'  {st}("{st}")')
        return "\n".join(lines) if len(lines) > 1 else "flowchart TD"

    def _render_state_diagram_v2(self, sm) -> str:
        """spring/cola 状态机：stateDiagram-v2（[*] 初始/终态 + 转换箭头）。"""
        lines = ["stateDiagram-v2"]
        if sm.initialState:
            lines.append(f"  [*] --> {sm.initialState}")
        for end in sm.endStates:
            lines.append(f"  {end} --> [*]")
        seen = set()
        for t in sm.transitions:
            key = (t.source, t.target, t.event)
            if key in seen:
                continue
            seen.add(key)
            label = f" : {t.event}" if t.event else ""
            lines.append(f"  {t.source or '?'} --> {t.target or '?'}{label}")
        involved = {sm.initialState} | set(sm.endStates or [])
        for t in sm.transitions:
            involved.add(t.source)
            involved.add(t.target)
        for st in sm.states or []:
            if st and st not in involved:
                lines.append(f"  state {st}")
        return "\n".join(lines)

    def _find_cross_domain_deps(self, java_files: list, modules: dict) -> list[CrossDomainDep]:
        """识别跨域依赖（双轨：Maven 多模块 + Java import 分析）"""
        deps = []
        seen_keys = set()

        # ── 路径 1：Maven 多模块依赖 ──
        if modules:
            module_to_domain = {}
            for artifact_id, mod_info in modules.items():
                domain = LayerIdentifier().identify_domain_from_module(artifact_id, modules)
                module_to_domain[artifact_id] = domain

            for artifact_id, mod_info in modules.items():
                current_domain = module_to_domain.get(artifact_id, "")
                for dep in mod_info.get("dependencies", []):
                    dep_artifact = dep.get("artifactId", "")
                    dep_domain = module_to_domain.get(dep_artifact, "")
                    if dep_domain and dep_domain != current_domain and dep_artifact.endswith("-client"):
                        key = f"{current_domain}→{dep_domain}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            deps.append(CrossDomainDep(
                                fromDomain=current_domain,
                                toDomain=dep_domain,
                                type="client-api",
                                description=f"{current_domain} 域通过 {dep_artifact} 调用 {dep_domain} 域",
                                evidence=f"Maven 依赖: {artifact_id} → {dep_artifact}",
                            ))

        # ── 路径 2：Java import 分析（适用单模块/无 Maven 项目）──
        if not deps or len(modules) <= 1:
            import_deps = self._find_cross_domain_from_imports(java_files, modules)
            for dep in import_deps:
                key = f"{dep.fromDomain}→{dep.toDomain}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    deps.append(dep)

        return deps

    def _find_cross_domain_from_imports(self, java_files: list, modules: dict) -> list[CrossDomainDep]:
        """从 Java import 语句推断跨域依赖（单模块/无 Maven 项目主路径）。

        复用 _find_domain 做域识别（与主流程统一），替代原 parts[2] 硬编码——
        后者对单 base-package 项目(com.acme.messagecenter.*)恒判同一域,
        导致跨域依赖恒为空。新增 domain-coupling 类型如实标记领域层直接耦合。
        """
        # ── Pass 1: 用 _find_domain 建立 known_domains 集合 ──
        known_domains: set = set()
        for fi in java_files:
            if not fi.get("qualifiedName"):
                continue
            domain = self._find_domain(fi, modules)
            if domain and domain != "unknown":
                known_domains.add(domain)

        if len(known_domains) <= 1:
            return []

        # ── Pass 2: 查找跨域 import ──
        cross_domain_edges: dict = defaultdict(set)

        for fi in java_files:
            if not fi.get("qualifiedName"):
                continue
            current_domain = self._find_domain(fi, modules)
            if current_domain == "unknown" or current_domain not in known_domains:
                continue

            for imp in fi.get("imports", []):
                # 用 import 串构造伪 file_info, 复用 _find_domain 判域
                imp_domain = self._find_domain(
                    {"qualifiedName": imp, "filePath": ""}, modules
                )

                # 同域或未知域(含第三方库)跳过
                if imp_domain == current_domain or imp_domain not in known_domains:
                    continue

                # 分类跨域通信类型
                imp_parts = imp.split(".")
                imp_class = imp_parts[-1] if imp_parts else ""
                is_client_call = (
                    imp_class.endswith("ServiceI")
                    or imp_class.endswith("CO")
                    or imp_class.endswith("Cmd")
                    or imp_class.endswith("Query")
                    or ".client." in imp
                    or ".api." in imp
                )
                is_event_ref = (
                    imp_class.endswith("Event")
                    and ".domain." in imp
                    and ".event." in imp
                )

                if is_client_call:
                    cross_domain_edges[(current_domain, imp_domain)].add("client-api")
                elif is_event_ref:
                    cross_domain_edges[(current_domain, imp_domain)].add("domain-event")
                else:
                    # 直接 import 他域实体/仓库/枚举等 = 领域层耦合(应通过 Client API/事件解耦)
                    cross_domain_edges[(current_domain, imp_domain)].add("domain-coupling")

        type_desc = {
            "client-api": "同步 Client API 调用",
            "domain-event": "异步领域事件订阅",
            "domain-coupling": "直接领域层耦合（建议通过 Client API 或领域事件解耦）",
        }
        deps = []
        for (from_d, to_d), types in cross_domain_edges.items():
            for typ in types:
                deps.append(CrossDomainDep(
                    fromDomain=from_d,
                    toDomain=to_d,
                    type=typ,
                    description=f"{from_d} 域通过 Java import 与 {to_d} 域耦合（{type_desc.get(typ, typ)}）",
                    evidence=f"import 分析: {from_d} → {to_d}",
                ))

        return deps

    def to_json(self, manifest: DocManifest, pretty: bool = True) -> str:
        """序列化为 JSON"""

        def _custom_serializer(obj):
            if isinstance(obj, (DocManifest, ComponentDoc, FieldDoc, AggregateDoc,
                               LayerDoc, DomainDoc, DiagramSet, CrossDomainDep,
                               TableDoc, TableColumnDoc, TableIndexDoc, EndpointDoc)):
                return {k: v for k, v in obj.__dict__.items() if v is not None}
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        indent = 2 if pretty else None
        return json.dumps(asdict(manifest), default=_custom_serializer,
                         ensure_ascii=False, indent=indent)
