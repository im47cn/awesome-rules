"""PO 扫描器 (MyBatis-Plus)。

无 ``.sql`` 文件时，从 MyBatis-Plus PO 类推断数据库结构。

与 :class:`InfrastructureDBExtractor` (JPA ``@Table``/``@Column`` + DO) 互补：
PO 类用 ``@TableName`` 显式声明表名、``@TableField`` 声明列名、``@TableId`` 标记主键。
表名绝不走命名约定 (类名与表名不可推导，如 ``MsgTemplateInfoPO`` → ``msg_tmpl_cfg``)。

本模块从单体脚本 ``doc_gen.py`` 拆分而来，逻辑保持不变。
"""

import os
import re
from pathlib import Path
from typing import Optional

from doctypes import TableDoc, TableColumnDoc, JPA_TYPE_MAP, FileInfo


class POScanner:
    """无 .sql 文件时, 从 MyBatis-Plus PO 类推断数据库结构。

    与 InfrastructureDBExtractor(JPA @Table/@Column + DO) 互补:
    PO 类用 @TableName 显式声明表名、@TableField 声明列名、@TableId 标记主键。
    表名绝不走命名约定(类名与表名不可推导, 如 MsgTemplateInfoPO→msg_tmpl_cfg)。
    """

    # MyBatis-Plus 注解(注意: @TableName 与 JPA @Table 不同)
    # 兼容 @TableName("x") 与 @TableName(value = "x") 两种语法
    TABLE_NAME_RE = re.compile(r'@TableName\s*\(\s*(?:value\s*=\s*)?"([^"]+)"')
    TABLE_FIELD_RE = re.compile(r'@TableField\s*\(\s*(?:value\s*=\s*)?"([^"]+)"')
    TABLE_FIELD_EXIST_FALSE_RE = re.compile(r'@TableField\s*\([^)]*exist\s*=\s*false', re.IGNORECASE)
    TABLE_ID_RE = re.compile(r'@TableId\b', re.IGNORECASE)
    FIELD_RE = re.compile(
        r'(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?'
        r'(\w+(?:<[\w\s,?]+>)?)\s+(\w+)\s*[=;]'
    )

    # 复用共享的 Java→SQL 类型映射（定义见 ..types）
    TYPE_MAP = JPA_TYPE_MAP

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def scan(self, java_files: list[FileInfo]) -> list[TableDoc]:
        """扫描 *PO.java, 从 @TableName/@TableField/@TableId 推断表结构

        与 InfrastructureDBExtractor(JPA @Table/@Column + DO) 互补:
        PO 类用 @TableName 显式声明表名、@TableField 声明列名、@TableId 标记主键。
        表名绝不走命名约定(类名与表名不可推导, 如 MsgTemplateInfoPO→msg_tmpl_cfg)。

        增强：同时扫描 MyBatis XML 映射文件，从 <resultMap> 中提取实际列映射，
        弥补 PO 类中 @TableField 未声明的列（如审计字段、关联字段）。"""
        tables: list[TableDoc] = []
        seen_tables: set[str] = set()

        # 第一遍：从持久化载体类提取表结构
        # 覆盖 PO/BO/DO/Entity 等所有可能承载 @TableName 的后缀：
        # GTSP 项目中领域实体 *BO 直接带 @TableName（无独立 PO 层），
        # 故按后缀预筛后仍以 @TableName 注解为准（无注解则跳过，不回退命名约定）。
        persist_suffixes = ("PO", "BO", "DO", "Entity")
        for fi in java_files:
            if not fi.get("className", "").endswith(persist_suffixes):
                continue
            content = self._read_file(fi.get("filePath", ""))
            if not content:
                continue
            m = self.TABLE_NAME_RE.search(content)
            if not m:
                continue  # 无 @TableName 则跳过(不回退命名约定)
            table_name = m.group(1)
            if table_name not in seen_tables:
                seen_tables.add(table_name)
                tables.append(TableDoc(
                    name=table_name,
                    columns=self._extract_columns(content),
                ))

        # 第二遍：从 MyBatis XML 映射文件补充列（仅补充 PO 未覆盖的列）
        xml_tables = self._scan_mapper_xml_for_po()
        for table_name, xml_columns in xml_tables.items():
            # 找到已有的表
            existing = next((t for t in tables if t.name == table_name), None)
            if existing:
                # 补充 PO 未覆盖的列（如审计字段）
                existing_col_names = {c.name for c in existing.columns}
                for col_name, col_type in xml_columns:
                    if col_name not in existing_col_names:
                        existing.columns.append(TableColumnDoc(
                            name=col_name,
                            type=col_type,
                        ))
            else:
                # 纯 XML 声明的表（无对应 PO 类）
                tables.append(TableDoc(
                    name=table_name,
                    columns=[TableColumnDoc(name=c, type=t) for c, t in xml_columns],
                ))

        return tables

    def _scan_mapper_xml_for_po(self) -> dict[str, list[tuple[str, str]]]:
        """扫描 MyBatis XML 映射文件，从 <resultMap> 中提取列映射（补充 PO 推断）。

        仅处理与 PO 类关联的 Mapper XML（通过 <mapper namespace> 推断）。
        提取 <resultMap> 中的 <id> 和 <result> 标签，补充 PO 未覆盖的列。
        """
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

            # 提取 <resultMap> 中的列映射。
            # 注意：resultMap id 在 *开标签* 内，须用完整标签 group(0) 提取，
            # group(1) 仅是标签内部内容（不含 <resultMap id="...">），在其中搜索开标签恒为空。
            for rm in re.finditer(
                r'<resultMap[^>]*>(.*?)</resultMap>',
                content, re.DOTALL,
            ):
                full_tag = rm.group(0)            # 含 <resultMap id="..."> 开标签
                map_body = rm.group(1)
                rm_id_match = re.search(r'\bid\s*=\s*"(\w+)"', full_tag)
                if not rm_id_match:
                    continue
                # 从 resultMap id 推断表名（通常与 PO 类名或表名相关）
                table_name = self._rm_id_to_table(rm_id_match.group(1))
                if not table_name:
                    continue
                tables.setdefault(table_name, [])
                # 提取 <id>/<result> 标签的 column 属性，补充 PO 未声明的列
                for col in re.finditer(
                    r'<(?:id|result)\s+[^>]*column\s*=\s*"(\w+)"',
                    map_body,
                ):
                    col_name = col.group(1)
                    if not any(c[0] == col_name for c in tables[table_name]):
                        tables[table_name].append((col_name, "varchar(255)"))

        return tables

    @staticmethod
    def _rm_id_to_table(rm_id: str) -> Optional[str]:
        """从 resultMap id 推断表名。

        常见模式：
        - BaseResultMap → 取 Mapper namespace 中的表名
        - XxxDO_resultMap → 取 XxxDO → 表名
        - 直接表名 → 直接返回
        """
        # 尝试从 resultMap id 提取表名
        for suffix in ("_resultMap", "_BaseResultMap", "_Map"):
            if rm_id.endswith(suffix):
                rm_id = rm_id[: -len(suffix)]
                break
        # 尝试 CamelCase → snake_case
        table = re.sub(r'([A-Z])', r'_\1', rm_id).lower().lstrip("_")
        if not table:
            return None
        return f"t_{table}" if not table.startswith("t_") else table

    def _read_file(self, rel_path: str) -> str:
        full = self.root_path / rel_path
        try:
            return full.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _extract_columns(self, content: str) -> list[TableColumnDoc]:
        """提取持久化字段 → 列(@TableField 优先, 否则驼峰转下划线)。

        注解与字段注释可在字段声明上一行或同一行, 用 pending 缓冲。
        字段注释(javadoc ``/** */`` 或行注释 ``//``)写入 ``comment``，
        其中常含枚举取值说明(如 ``状态[0-待签,1-已签]``)。
        """
        columns: list[TableColumnDoc] = []
        pending_col: Optional[str] = None
        pending_id = False
        pending_skip = False
        pending_comment = ""
        in_javadoc = False
        jd_lines: list[str] = []

        for line in content.split("\n"):
            stripped = line.strip()

            # ── javadoc 块注释捕获 ──
            if in_javadoc:
                if "*/" in stripped:
                    in_javadoc = False
                    before = stripped.split("*/", 1)[0]
                    text = before.strip().lstrip("*").strip()
                    if text and not text.startswith("@"):
                        jd_lines.append(text)
                    if jd_lines:
                        pending_comment = " ".join(jd_lines)
                        jd_lines = []
                else:
                    text = stripped.lstrip("*").strip()
                    if text and not text.startswith("@"):
                        jd_lines.append(text)
            elif stripped.startswith("/**"):
                rest = stripped[3:]
                if "*/" in rest:
                    # 单行 javadoc /** 说明 */
                    text = rest.split("*/", 1)[0].strip().lstrip("*").strip()
                    if text and not text.startswith("@"):
                        pending_comment = text
                else:
                    in_javadoc = True
                    text = rest.strip().lstrip("*").strip()
                    if text and not text.startswith("@"):
                        jd_lines.append(text)
            elif "//" in stripped and not stripped.startswith("@"):
                # 行注释（字段说明，常含枚举取值）
                cmt = stripped.split("//", 1)[1].strip()
                if cmt:
                    pending_comment = cmt

            # ── 结构边界：类/接口/方法声明 → 字段注释上下文失效 ──
            # 避免类级 javadoc 或方法注释污染紧随其后的字段
            if re.match(
                r'(?:public\s+|protected\s+|private\s+|abstract\s+|final\s+|static\s+)*'
                r'(?:class|enum|interface|record)\s+\w', stripped
            ) or re.match(
                r'(?:public|protected|private)\s+\S.*\([^)]*\)\s*(?:\{|throws)', stripped
            ):
                pending_comment = ""
                jd_lines = []
                in_javadoc = False

            # ── 注解 → pending ──
            if self.TABLE_FIELD_EXIST_FALSE_RE.search(line):
                pending_skip = True
            m_field = self.TABLE_FIELD_RE.search(line)
            if m_field:
                pending_col = m_field.group(1)
            if self.TABLE_ID_RE.search(line):
                pending_id = True

            # ── 字段声明 → 消费 pending（含注释）──
            m_decl = self.FIELD_RE.search(line)
            if m_decl:
                java_type, java_field = m_decl.group(1), m_decl.group(2)
                if not pending_skip:
                    name = pending_col or self._camel_to_snake(java_field)
                    columns.append(TableColumnDoc(
                        name=name,
                        type=self.TYPE_MAP.get(java_type, "varchar(255)"),
                        primaryKey=pending_id,
                        comment=pending_comment,
                    ))
                pending_col, pending_id, pending_skip = None, False, False
                pending_comment = ""
        return columns

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        return re.sub(r'([A-Z])', r'_\1', name).lower().lstrip("_")
