"""DDL SQL 文件扫描器。"""

import re
from pathlib import Path

from doctypes import SKIP_DIRS, TableDoc, TableColumnDoc, TableIndexDoc


class DDLScanner:
    """DDL SQL 文件扫描"""

    CREATE_TABLE_RE = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
        r'`?(\w+)`?\s*\(([\s\S]*?)\)\s*'
        r'(?:ENGINE|COMMENT|;|\n\n)',
        re.IGNORECASE,
    )
    COLUMN_RE = re.compile(
        r'`(\w+)`\s+(\w+(?:\([^)]+\))?)\s*'
        r'(?:NOT\s+NULL\s*)?'
        r'(?:DEFAULT\s+([^\s,]+)\s*)?'
        r'(?:AUTO_INCREMENT\s*)?'
        r'(?:COMMENT\s+[\'"]([^\'"]*)[\'"]\s*)?',
        re.IGNORECASE,
    )
    PK_RE = re.compile(r'PRIMARY\s+KEY\s*\(`?(\w+)`?\)', re.IGNORECASE)
    INDEX_RE = re.compile(
        r'(?:UNIQUE\s+)?(?:KEY|INDEX)\s+`?(\w+)`?\s*\(([^)]+)\)',
        re.IGNORECASE,
    )
    TABLE_COMMENT_RE = re.compile(
        r"COMMENT\s*=\s*'([^']*)'",
        re.IGNORECASE,
    )

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def scan(self) -> list[TableDoc]:
        """扫描所有 SQL 文件，提取表结构"""
        tables = []
        sql_files = list(self.root_path.rglob("*.sql"))

        for sql_file in sql_files:
            if not self._should_scan(sql_file):
                continue
            try:
                content = sql_file.read_text(encoding="utf-8")
                tables.extend(self._extract_tables(content))
            except Exception:
                pass

        return tables

    def _should_scan(self, file_path: Path) -> bool:
        return not any(skip in file_path.parts for skip in SKIP_DIRS)

    def _extract_tables(self, content: str) -> list[TableDoc]:
        tables = []
        for table_match in self.CREATE_TABLE_RE.finditer(content):
            table_name = table_match.group(1)
            body = table_match.group(2)

            columns = []
            for col_match in self.COLUMN_RE.finditer(body):
                col = TableColumnDoc(
                    name=col_match.group(1),
                    type=col_match.group(2),
                    nullable="NOT NULL" not in (col_match.group(0) or ""),
                    defaultValue=col_match.group(3) or "",
                    comment=col_match.group(4) or "",
                )
                columns.append(col)

            # 提取主键
            pk_match = self.PK_RE.search(body)
            if pk_match:
                pk_col = pk_match.group(1)
                for col in columns:
                    if col.name == pk_col:
                        col.primaryKey = True

            # 提取索引
            indexes = []
            for idx_match in self.INDEX_RE.finditer(body):
                is_unique = "UNIQUE" in (idx_match.group(0) or "").upper()
                idx = TableIndexDoc(
                    name=idx_match.group(1),
                    columns=[c.strip().strip("`") for c in idx_match.group(2).split(",")],
                    unique=is_unique,
                )
                indexes.append(idx)

            # 表注释
            comment_match = self.TABLE_COMMENT_RE.search(content[table_match.end():table_match.end()+200])
            table_comment = comment_match.group(1) if comment_match else ""

            tables.append(TableDoc(
                name=table_name,
                comment=table_comment,
                columns=columns,
                indexes=indexes,
            ))

        return tables
