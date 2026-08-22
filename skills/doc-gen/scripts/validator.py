"""DocManifest 分片 JSON Schema 校验器 — 内置子集实现，零第三方依赖。

借鉴 archify 的 schema 即契约模式：schema_version const 锁定 +
additionalProperties:false（未知字段拒绝而非静默忽略）。

支持的关键字子集（与 schemas/*.json 严格对齐，不追求完整 draft 覆盖）：
  type / properties / required / items / enum / const /
  additionalProperties / minProperties / minItems / minLength /
  minimum / pattern / $ref（同文件及同目录跨文件引用）

对外入口:
  validate_shard(schema, data) -> list[str]   # 单分片校验，返回错误列表
  validate_manifest_dir(dir) -> list[str]     # 遍历分片目录逐个校验
"""

import json
import re
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

# 分片文件 → schema 文件映射；不在映射内的分片（api-spec/risks/adrs/
# articles/receipt）各有上游规范或属本期范围外，跳过
SHARD_SCHEMAS = {
    "index.json": "index.schema.json",
    "meta.json": "meta.schema.json",
    "database.json": "database.schema.json",
    "state-machines.json": "state-machines.schema.json",
    "cross-domain.json": "cross-domain.schema.json",
    # diagrams.json 为 Mermaid 自由文本，本期只校验 JSON 可解析，不锁结构
}

# 可选扩展分片：缺失合法（跳过），存在则按契约强校验（AH-MANIFEST §2）
OPTIONAL_SHARD_SCHEMAS = {
    "business-context.json": "business-context.schema.json",
    "risks.json": "risks.schema.json",
    "adrs.json": "adrs.schema.json",
    "articles.json": "articles.schema.json",
}

_schema_cache: dict = {}


def _load_schema(name: str) -> dict:
    if name not in _schema_cache:
        _schema_cache[name] = json.loads(
            (SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return _schema_cache[name]


def _resolve_ref(ref: str, base_file: str) -> tuple[dict, str]:
    """解析 $ref：同文件 #/$defs/x 或跨文件 other.schema.json#/$defs/x

    返回 (解析后的子 schema, 该子 schema 所在文件名)。
    """
    if not ref.startswith("#"):
        file_part, _, frag = ref.partition("#")
        file_name = file_part if file_part else base_file
        schema = _load_schema(file_name)
        node = schema
    else:
        file_name = base_file
        schema = _load_schema(base_file)
        node = schema
        frag = ref[1:]
    for seg in frag.strip("/").split("/") if frag else []:
        node = node[seg]
    return node, file_name


def _type_ok(expected, value) -> bool:
    """类型检查，支持联合类型如 ["string", "null"]"""
    for t in (expected if isinstance(expected, list) else [expected]):
        if t == "null":
            if value is None:
                return True
        elif t == "string" and isinstance(value, str):
            return True
        elif t == "boolean" and isinstance(value, bool):
            return True
        elif t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        elif t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        elif t == "array" and isinstance(value, list):
            return True
        elif t == "object" and isinstance(value, dict):
            return True
    return False


def _validate(schema: dict, data, path: str, base_file: str, errors: list):
    """递归校验。errors 原地追加 '路径: 消息' 字符串。"""
    if "$ref" in schema:
        resolved, ref_file = _resolve_ref(schema["$ref"], base_file)
        # 递归保护：仅剥离 $ref 后继续，不做循环检测（schema 集合无环）
        _validate(resolved, data, path, ref_file, errors)
        return

    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: 必须为常量 {schema['const']!r}，实际 {data!r}")
        return

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: 值 {data!r} 不在枚举 {schema['enum']} 内")
        return

    if "type" in schema and not _type_ok(schema["type"], data):
        errors.append(f"{path}: 类型应为 {schema['type']}，实际 "
                      f"{type(data).__name__} ({data!r})")
        return

    if isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"{path}: 长度 {len(data)} < minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], data):
            errors.append(f"{path}: {data!r} 不匹配 pattern {schema['pattern']}")

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: {data} < minimum {schema['minimum']}")

    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(f"{path}: 元素数 {len(data)} < minItems {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(data):
                _validate(schema["items"], item, f"{path}[{i}]", base_file, errors)

    if isinstance(data, dict):
        if "minProperties" in schema and len(data) < schema["minProperties"]:
            errors.append(f"{path}: 属性数 {len(data)} < minProperties "
                          f"{schema['minProperties']}")
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}: 缺少必填字段 '{key}'")
        if schema.get("additionalProperties") is False:
            for key in data:
                if key not in props:
                    errors.append(f"{path}: 未知字段 '{key}'"
                                  f"（additionalProperties: false）")
        for key, sub in props.items():
            if key in data:
                _validate(sub, data[key], f"{path}/{key}", base_file, errors)


def validate_shard(schema: dict, data, base_file: str = "") -> list[str]:
    """校验单个分片数据，返回错误列表（空 = 通过）"""
    errors: list[str] = []
    _validate(schema, data, "", base_file or "inline", errors)
    return errors


def validate_manifest_dir(manifest_dir: Path) -> list[str]:
    """校验 doc-manifest/ 分片目录，返回错误列表（空 = 通过）"""
    manifest_dir = Path(manifest_dir)
    errors: list[str] = []

    for shard_name, schema_name in SHARD_SCHEMAS.items():
        shard_path = manifest_dir / shard_name
        if not shard_path.exists():
            errors.append(f"{shard_name}: 分片文件缺失")
            continue
        try:
            data = json.loads(shard_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{shard_name}: JSON 解析失败: {e}")
            continue
        schema = _load_schema(schema_name)
        shard_errors = validate_shard(schema, data, schema_name)
        errors.extend(f"{shard_name}{msg}" for msg in shard_errors)

    # 可选扩展分片：存在才校验，缺失不报错
    for shard_name, schema_name in OPTIONAL_SHARD_SCHEMAS.items():
        shard_path = manifest_dir / shard_name
        if not shard_path.exists():
            continue
        try:
            data = json.loads(shard_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{shard_name}: JSON 解析失败: {e}")
            continue
        schema = _load_schema(schema_name)
        opt_errors = validate_shard(schema, data, schema_name)
        errors.extend(f"{shard_name}{msg}" for msg in opt_errors)

    # 域分片：index.json 引用的每个 domains/*.json 用 domain.schema.json
    domains_dir = manifest_dir / "domains"
    if domains_dir.is_dir():
        domain_schema = _load_schema("domain.schema.json")
        for domain_file in sorted(domains_dir.glob("*.json")):
            try:
                data = json.loads(domain_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"domains/{domain_file.name}: JSON 解析失败: {e}")
                continue
            shard_errors = validate_shard(domain_schema, data, "domain.schema.json")
            errors.extend(f"domains/{domain_file.name}{msg}" for msg in shard_errors)

    return errors
