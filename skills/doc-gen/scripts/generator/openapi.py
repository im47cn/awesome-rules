"""OpenAPI 3.0 规范生成器。

从 Controllers 的端点数据生成 OpenAPI 3.0 规范。
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

from doctypes import DocManifest

# 单 tag 下 operation 数超过该值 → 按 URI 前缀细分层级（Scalar 侧边栏单组可导航上限）
MAX_OPS_PER_TAG = 20


class OpenAPIGenerator:
    """从 Controllers 的端点数据生成 OpenAPI 3.0 规范"""

    JAVA_TO_OAS_TYPE = {
        "String": "string", "Integer": "integer", "int": "integer",
        "Long": "integer", "long": "integer", "Double": "number",
        "Float": "number", "BigDecimal": "number",
        "Boolean": "boolean", "boolean": "boolean",
        "LocalDateTime": "string", "Date": "string",
        "void": "object", "Object": "object",
        "List": "array", "Map": "object",
    }

    def __init__(self, root_path: str, project_name: str = ""):
        self.root_path = Path(root_path).resolve()
        self.project_name = project_name

    def generate(self, manifest: DocManifest) -> dict:
        """从 manifest domains 中提取所有 controller 端点生成 OpenAPI 3.0 spec"""
        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": f"{manifest.meta.get('project', {}).get('name', self.project_name) or 'ARCH-HAWKEYE'} API",
                "description": manifest.meta.get("project", {}).get("description", "DDD 架构鹰眼自动生成"),
                "version": "1.0.0",
            },
            "servers": [{"url": "/api"}],
            "paths": {},
            "tags": [],
            "components": {"schemas": {}},
        }

        seen_tags = set()
        schema_refs = set()

        # 构建 component 索引（className → ComponentDoc），供 schema 填充字段/枚举值
        self.comp_index = {}
        for _domain in manifest.domains:
            for _layer in (_domain.layers or {}).values():
                if not _layer:
                    continue
                for _comp in (_layer.components or []):
                    if _comp.className:
                        self.comp_index[_comp.className] = _comp

        for domain in manifest.domains:
            adapter = domain.layers.get("adapter")
            if not adapter or not adapter.components:
                continue

            for comp in adapter.components:
                if comp.type != "controller" or not comp.endpoints:
                    continue

                # 推断 tag
                tag = domain.displayName or domain.name
                if tag not in seen_tags:
                    seen_tags.add(tag)
                    spec["tags"].append({"name": tag, "description": domain.description or ""})

                for ep in comp.endpoints:
                    if ep.method == "*":
                        continue

                    path = ep.path or "/"
                    # 去除首尾多余斜杠
                    path = "/" + path.strip("/")
                    method = ep.method.lower()

                    if path not in spec["paths"]:
                        spec["paths"][path] = {}

                    op = {
                        "tags": [tag],
                        "summary": ep.summary or f"{comp.className} endpoint",
                        "operationId": f"{comp.className}_{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}",
                        "responses": {
                            "200": {"description": "成功"}
                        },
                    }

                    # @Deprecated → OpenAPI deprecated（Scalar 原生渲染删除线）
                    if getattr(ep, "deprecated", False):
                        op["deprecated"] = True

                    # requestBody
                    if ep.requestBody and ep.requestBody not in ("void", "Object"):
                        schema_ref = self._java_to_oas_schema(ep.requestBody, spec["components"]["schemas"], schema_refs)
                        if schema_ref:
                            op["requestBody"] = {
                                "required": True,
                                "content": {"application/json": {"schema": schema_ref}},
                            }

                    # response body
                    if ep.responseBody and ep.responseBody not in ("void", "Object", "*"):
                        schema_ref = self._java_to_oas_schema(ep.responseBody, spec["components"]["schemas"], schema_refs)
                        if schema_ref:
                            op["responses"]["200"]["content"] = {
                                "application/json": {"schema": schema_ref}
                            }

                    # 路径参数
                    path_params = re.findall(r'\{(\w+)\}', path)
                    if path_params:
                        op["parameters"] = []
                        for param in path_params:
                            op["parameters"].append({
                                "name": param,
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            })

                    spec["paths"][path][method] = op

        if not spec["paths"]:
            return {"openapi": "3.0.3", "info": spec["info"], "paths": {}, "components": {}}

        self._regroup_oversized_tags(spec)

        return spec

    def _regroup_oversized_tags(self, spec: dict) -> None:
        """单 tag 接口过多（域划分粒度过粗）或无域信息时，按 URI 前缀细分层级。

        Scalar 侧边栏按 tag 单层分组，一个 tag 下平铺上百个接口无法导航。
        细分后 tag 名保留域上下文（如 "basecont · signFlow"），组内仍超阈值
        且路径有更深段时继续下钻（如 "msg · statistics/task-send"）。
        """
        items = []          # [(path, method, op)]
        tag_of = {}         # id(op) -> 当前 tag（空串 = 无域信息）
        for path, ops in spec["paths"].items():
            for method, op in ops.items():
                if not isinstance(op, dict):
                    continue
                items.append((path, method, op))
                tags = op.get("tags") or []
                tag_of[id(op)] = tags[0] if tags else ""

        counts = Counter(tag_of.values())
        tag_desc = {t.get("name", ""): t.get("description", "") for t in spec["tags"]}

        new_tags = []       # 顶层 tags 数组（有序，保持原 tag 相对顺序）
        # OpenAPI 3.0 要求 tags 数组内 name 唯一：细分名（"域 · 前缀"）可能撞上
        # 既有同名 tag（用户自定义或上轮细分产物），冲突时加序号后缀消歧
        used_names = set(counts.keys())   # 原样保留的小 tag 占据名字空间

        def _unique_name(name: str) -> str:
            if name not in used_names:
                used_names.add(name)
                return name
            n = 2
            while f"{name} · {n}" in used_names:
                n += 1
            uniq = f"{name} · {n}"
            used_names.add(uniq)
            return uniq

        for tag, total in counts.items():
            entries = [(p, m, o) for p, m, o in items if tag_of[id(o)] == tag]
            if tag and total <= MAX_OPS_PER_TAG:
                new_tags.append({"name": tag, "description": tag_desc.get(tag, "")})
                continue
            # 无域信息 → 纯前缀；有域但组过大 → "域 · 前缀"
            for label, sub in self._group_by_path_prefix(entries, depth=0):
                name = _unique_name(f"{tag} · {label}" if tag else label)
                for _p, _m, op in sub:
                    op["tags"] = [name]
                hint = "（按 URI 前缀自动细分）"
                new_tags.append({
                    "name": name,
                    "description": f"{tag_desc.get(tag, '')} {hint}".strip() if tag else hint.strip(),
                })
        spec["tags"] = new_tags

    def _group_by_path_prefix(self, entries: list, depth: int) -> list:
        """按路径第 depth 段分组；组内仍超阈值且下钻有价值时递归细分。

        entries: [(path, method, op)]；返回 [(组名, entries)]。
        根路径或变量段（{id}）不是稳定分组键，归入「其余」组不再下钻。
        下钻价值：下一层段取值有重复（资源名，如 task-send）才有分类意义；
        下钻后大半接口落入单接口组（实例 ID 层，如 /root/5）则停钻——
        单接口组无导航价值且组名冗长。
        """
        if len(entries) <= MAX_OPS_PER_TAG:
            return [("", entries)]

        buckets = defaultdict(list)
        for path, method, op in entries:
            segs = path.strip("/").split("/")
            seg = segs[depth] if len(segs) > depth else ""
            if "{" in seg:
                seg = ""
            buckets[seg].append((path, method, op))

        result = []
        for seg, sub in sorted(buckets.items()):
            label = seg or "其余"
            deeper = seg and len(sub) > MAX_OPS_PER_TAG \
                and self._drill_worthwhile(sub, depth)
            if deeper:
                for sub_label, sub_entries in self._group_by_path_prefix(sub, depth + 1):
                    result.append((f"{label}/{sub_label}" if sub_label else label, sub_entries))
            else:
                result.append((label, sub))
        return result

    @staticmethod
    def _drill_worthwhile(entries: list, depth: int) -> bool:
        """预演按 depth+1 层分桶：单接口组占比过半则下钻无价值，停钻。

        判据同时覆盖两种坏场景——下一层取值几乎全唯一（实例 ID），
        或少数重复值混大量唯一方法名（下钻后多数接口落单）。
        """
        buckets = defaultdict(int)
        for path, _m, _o in entries:
            segs = path.strip("/").split("/")
            seg = segs[depth + 1] if len(segs) > depth + 1 else ""
            buckets[seg or "其余"] += 1
        singles = sum(n for n in buckets.values() if n == 1)
        return singles < len(entries) / 2

    def _java_to_oas_schema(self, java_type: str, schemas: dict, schema_refs: set) -> dict:
        """将 Java 类型名映射为 OpenAPI schema/$ref"""
        base = java_type.split("<")[0].strip()

        # 基本类型
        oas_type = self.JAVA_TO_OAS_TYPE.get(base)
        if oas_type and oas_type != "object":
            return {"type": oas_type}

        # 泛型 List<T>
        generic_match = re.match(r'(List|Set|Collection)<(\w+)>', java_type)
        if generic_match:
            inner = generic_match.group(2)
            return {
                "type": "array",
                "items": self._java_to_oas_schema(inner, schemas, schema_refs),
            }

        # 泛型类型参数（单字母 T/E/K/V/R 等）→ inline object，不建立独立 schema
        if len(base) == 1 and base.isupper():
            return {"type": "object"}

        # 类 → $ref (去后缀 CO/DO/DTO/Cmd/Query)
        clean = base
        for suffix in ("CO", "DO", "DTO", "Cmd", "Query", "Req", "Resp"):
            if clean.endswith(suffix):
                clean = clean[:-len(suffix)]
                break

        if clean not in schema_refs:
            schema_refs.add(clean)
            comp = self.comp_index.get(base) or self.comp_index.get(clean)
            if comp and getattr(comp, "classType", "") == "enum":
                # 枚举 → string + 可选值
                schemas[clean] = {
                    "type": "string",
                    "enum": list(getattr(comp, "enumValues", []) or []),
                    "description": f"枚举类型 {base}",
                }
            elif comp and comp.fields:
                # 对象 → 填充真实字段
                schemas[clean] = {
                    "type": "object",
                    "properties": self._fields_to_properties(comp.fields, schemas, schema_refs),
                    "description": f"Auto-generated schema for {base}",
                }
            else:
                # 外部依赖类型（src 无定义，无法提取字段）
                schemas[clean] = {
                    "type": "object",
                    "description": f"{base}（外部依赖类型，结构未解析）",
                }

        return {"$ref": f"#/components/schemas/{clean}"}

    def _fields_to_properties(self, fields, schemas, schema_refs):
        """将 FieldDoc 列表转为 OpenAPI properties（递归处理字段类型，嵌套对象自动建 schema）"""
        props = {}
        for f in (fields or []):
            name = getattr(f, "name", None) or (f.get("name") if isinstance(f, dict) else None)
            ftype = getattr(f, "type", None) or (f.get("type") if isinstance(f, dict) else None)
            if not name or not ftype:
                continue
            prop = self._java_to_oas_schema(ftype, schemas, schema_refs)
            comment = getattr(f, "comment", None) or (f.get("comment") if isinstance(f, dict) else None)
            if comment:
                prop["description"] = comment
            props[name] = prop
        return props
