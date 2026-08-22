"""Infrastructure 代码数据库结构提取器。

无 ``.sql`` 文件时，从 Infrastructure 层 Java 代码推断数据库结构：

- DO 类 (``@Table`` + ``@Column`` 注解) → 表 / 列
- Mapper 接口 (方法名解析) → 索引 / 查询
- MyBatis XML (``<resultMap>``、``<insert>``) → 列映射

本模块从单体脚本 ``doc_gen.py`` 拆分而来，逻辑保持不变。
"""

import os
import re
from pathlib import Path
from typing import Optional

from doctypes import TableDoc, TableColumnDoc, TableIndexDoc, JPA_TYPE_MAP, FileInfo


class InfrastructureDBExtractor:
    """无 .sql 文件时，从 Infrastructure 代码提取数据库结构：

    - DO 类 (@Table + @Column 注解) → 表/列
    - Mapper 接口 (方法名解析) → 索引/查询
    - MyBatis XML (<resultMap>, <insert>) → 列映射
    """

    TABLE_ANNO_RE = re.compile(
        r'@Table\s*\(\s*(?:name|value)\s*=\s*"(\w+)"',
        re.IGNORECASE,
    )
    COLUMN_ANNO_RE = re.compile(
        r'@Column\s*\(\s*(?:name\s*=\s*)?"(\w+)"',
        re.IGNORECASE,
    )
    ID_ANNO_RE = re.compile(r'@Id\b', re.IGNORECASE)
    GENERATED_VALUE_RE = re.compile(r'@GeneratedValue', re.IGNORECASE)

    # JPA 类型 → SQL 类型粗略映射（定义见 ..types，复用共享常量）
    JPA_TYPE_MAP = JPA_TYPE_MAP

    # 类名 → 表名（常见映射：XxxDO → t_xxx）
    @staticmethod
    def class_to_table(name: str) -> str:
        """OrderDO → t_order, OrderMainDO → t_order_main"""
        base = name
        for suffix in ("DO", "Po", "PO", "Entity", "Model"):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        # CamelCase → snake_case
        table = re.sub(r'([A-Z])', r'_\1', base).lower().lstrip("_")
        return f"t_{table}"

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def extract(self, java_files: list[FileInfo]) -> list[TableDoc]:
        """从 Infrastructure 代码推断表结构"""
        tables: dict[str, TableDoc] = {}

        for fi in java_files:
            fpath = fi.get("filePath", "")
            pkg = fi.get("package", "")

            # 只处理 infrastructure 层
            if "/infrastructure/" not in fpath.lower() and "/infra/" not in fpath.lower():
                continue

            # DO 类：@Table 映射表
            if fi.get("className", "").endswith("DO"):
                table = self._extract_from_do(fi)
                if table and table.name not in tables:
                    tables[table.name] = table

            # Mapper 接口：从方法名推断
            if fi.get("className", "").endswith("Mapper"):
                mapper_table = self._infer_table_from_mapper(fi)
                if mapper_table:
                    existing = tables.get(mapper_table.name)
                    if existing:
                        self._merge_mapper_info(existing, fi)

        # 扫描 MyBatis XML 映射文件
        xml_tables = self._scan_mapper_xml()
        for name, columns in xml_tables.items():
            if name in tables:
                for col_name, col_type in columns:
                    if not any(c.name == col_name for c in tables[name].columns):
                        tables[name].columns.append(TableColumnDoc(
                            name=col_name, type=col_type,
                        ))
            else:
                tables[name] = TableDoc(
                    name=name,
                    columns=[TableColumnDoc(name=c, type=t) for c, t in columns],
                )

        return list(tables.values())

    def _extract_from_do(self, file_info: FileInfo) -> Optional[TableDoc]:
        """从 DO 类的 @Table/@Column 注解提取表结构"""
        fpath = file_info.get("filePath", "")
        java_file = self.root_path / fpath
        if not java_file.exists():
            return None

        try:
            raw = java_file.read_text(encoding="utf-8")
        except Exception:
            return None

        # 表名
        table_match = self.TABLE_ANNO_RE.search(raw)
        table_name = table_match.group(1) if table_match else self.class_to_table(file_info.get("className", ""))

        columns = []
        seen_fields = set()

        # 提取类体
        class_body_match = re.search(r'class\s+\w+\s*\{([\s\S]*)\}', raw)
        if class_body_match:
            body = class_body_match.group(1)
        else:
            body = raw

        # 逐字段解析：向后找最近的 ; 或 { 作为字段块起点
        field_re = re.compile(
            r'(?:public|protected|private)\s+'
            r'(?:static\s+)?(?:final\s+)?'
            r'([\w.]+(?:<[^>]+>)?)\s+'                     # 类型（含 java.math.BigDecimal）
            r'(\w+)\s*[=;]',                                # 字段名
        )

        for m in field_re.finditer(body):
            java_type = m.group(1).split(".")[-1]  # java.math.BigDecimal → BigDecimal
            field_name = m.group(2)

            # 跳过重复/静态/序列化字段
            if field_name in seen_fields:
                continue
            if field_name in ("serialVersionUID",):
                continue
            seen_fields.add(field_name)

            # 精确回溯：从当前字段向前找到上一个 ; 或 { 作为注解搜索范围
            boundary = body.rfind(";", 0, m.start())
            if boundary < 0:
                boundary = body.find("{") if "{" in body[:m.start()] else 0
            else:
                boundary += 1  # 跳过 ;
            field_context = body[boundary:m.end()]

            col_name = field_name
            col_match = self.COLUMN_ANNO_RE.search(field_context)
            if col_match:
                col_name = col_match.group(1)

            sql_type = self.JPA_TYPE_MAP.get(java_type, "varchar(255)")

            is_pk = bool(self.ID_ANNO_RE.search(field_context))
            is_auto = bool(self.GENERATED_VALUE_RE.search(field_context))

            columns.append(TableColumnDoc(
                name=col_name,
                type=sql_type,
                primaryKey=is_pk,
                comment=self._extract_field_comment(field_context) or field_name,
                defaultValue="" if not is_auto else "auto_increment",
            ))

        if not columns:
            return None

        # 区分「显式 @Table 声明」与「命名约定推断」，便于前端展示不同警示级别
        table_comment = f"从 {file_info.get('className', '')} 推断"
        if table_match:
            table_comment = f"MyBatis @Table 声明: {table_match.group(1)}"
        return TableDoc(
            name=table_name,
            comment=table_comment,
            columns=columns,
        )

    def _extract_field_comment(self, context: str) -> str:
        """从字段前缀区域提取紧邻的注释（javadoc 或行注释），含枚举取值说明。"""
        # 最后一个 javadoc 块
        jdls = re.findall(r'/\*\*(.*?)\*/', context, re.DOTALL)
        if jdls:
            lines = []
            for ln in jdls[-1].split("\n"):
                ln = ln.strip().lstrip("*").strip()
                if ln and not ln.startswith("@"):
                    lines.append(ln)
            return " ".join(lines)
        # 行注释（取最后一个）
        line_cmts = re.findall(r'//\s*(.+)$', context, re.MULTILINE)
        if line_cmts:
            return line_cmts[-1].strip()
        return ""

    def _infer_table_from_mapper(self, file_info: FileInfo) -> Optional[TableDoc]:
        """从 Mapper 接口名推断对应的表"""
        mapper_name = file_info.get("className", "")
        if not mapper_name.endswith("Mapper"):
            return None
        table_name = self.class_to_table(mapper_name.replace("Mapper", ""))
        return TableDoc(
            name=table_name,
            comment=f"从 {mapper_name} 推断",
            columns=[],
        )

    def _merge_mapper_info(self, table: TableDoc, mapper_info: FileInfo):
        """合并 Mapper 方法信息到表"""
        # 从方法名提取索引提示（selectByXxx → idx_xxx）
        for method in mapper_info.get("methods", []):
            name = method.get("name", "")
            # selectByOrderNo → order_no 可能是索引
            field_match = re.search(r'(?:selectBy|deleteBy|updateBy)(\w+)', name)
            if field_match:
                camel = field_match.group(1)
                snake = re.sub(r'([A-Z])', r'_\1', camel).lower().lstrip("_")
                # 检查是否已有此索引
                existing_idx = any(
                    snake in idx.columns for idx in table.indexes
                )
                if not existing_idx:
                    table.indexes.append(TableIndexDoc(
                        name=f"idx_{snake}",
                        columns=[snake],
                    ))

    def _scan_mapper_xml(self) -> dict[str, list[tuple[str, str]]]:
        """扫描 MyBatis XML 映射文件提取列映射"""
        tables: dict[str, list[tuple[str, str]]] = {}
        xml_files = list(self.root_path.rglob("*.xml"))

        for xml_file in xml_files:
            if "target" in str(xml_file).split(os.sep):
                continue
            try:
                content = xml_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # 检测是否是 MyBatis mapper XML
            if "<mapper " not in content[:200]:
                continue

            # 提取 <insert>/<update> 中的字段引用 → 推断表名和列
            for stmt in re.finditer(
                r'<(?:insert|update|delete|select)[^>]*id\s*=\s*"(\w+)"[^>]*>\s*([\s\S]*?)</(?:insert|update|delete|select)>',
                content, re.DOTALL,
            ):
                stmt_id = stmt.group(1)
                stmt_body = stmt.group(2)

                # 推断表名（INSERT INTO xxx / UPDATE xxx）
                table_match = re.search(
                    r'(?:INTO|FROM|UPDATE)\s+`?(\w+)`?',
                    stmt_body, re.IGNORECASE,
                )
                if not table_match:
                    continue
                table_name = table_match.group(1)

                if table_name not in tables:
                    tables[table_name] = []

                # 提取 #{field} 或 #{dto.field} 中的字段名
                for field_ref in re.finditer(r'#\{(\w+)(?:\.(\w+))?[\s,}]*', stmt_body):
                    col = field_ref.group(2) or field_ref.group(1)
                    if col not in ("dto", "param1", "param2", "arg0", "arg1",
                                   "criteria", "example", "offset", "limit",
                                   "pageSize", "pageNum", "record", "wrapper",
                                   "ew", "collection", "item", "index"):
                        tables[table_name].append((col, "varchar(255)"))

        return tables
