"""OpenAPI 3.0 规范生成器。

从 Controllers 的端点数据生成 OpenAPI 3.0 规范。
"""

import re
from pathlib import Path

from doctypes import DocManifest


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

        return spec

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
