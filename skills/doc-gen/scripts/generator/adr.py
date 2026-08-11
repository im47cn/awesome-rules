"""ADR（架构决策记录）扫描器。

扫描项目中的架构决策记录（docs/adr/ 目录下的 .md 文件）。
"""

import re
from pathlib import Path
from typing import Optional


class AdrScanner:
    """扫描项目中的架构决策记录（docs/adr/ 目录下的 .md 文件）"""

    ADR_PATTERN = re.compile(
        r'^#\s+(?:ADR\s*[-–—:.]?\s*)?(\d+)[-–—:.]?\s*(.+)',
        re.MULTILINE | re.IGNORECASE,
    )
    STATUS_RE = re.compile(
        r'(?:\*\*)?(?:状态|Status)(?:\*\*)?[：:]\s*(\S+)',
        re.IGNORECASE,
    )
    DATE_RE = re.compile(
        r'(?:\*\*)?(?:日期|Date)(?:\*\*)?[：:]\s*([\d-]+)',
        re.IGNORECASE,
    )

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def scan(self) -> dict:
        """扫描 docs/adr/ 目录，收集 ADR 列表"""
        adrs = []

        # 常见的 ADR 目录位置
        candidates = [
            self.root_path / "docs" / "adr",
            self.root_path / "doc" / "adr",
            self.root_path / "adr",
            self.root_path / ".adr",
        ]

        for adr_dir in candidates:
            if not adr_dir.is_dir():
                continue
            for md_file in sorted(adr_dir.glob("*.md")):
                adr = self._parse_adr(md_file)
                if adr:
                    adrs.append(adr)

        # 也扫描子目录（如 docs/adr/0001-xxx/）
        for adr_dir in candidates:
            if not adr_dir.is_dir():
                continue
            for subdir in sorted(adr_dir.iterdir()):
                if not subdir.is_dir():
                    continue
                readme = subdir / "README.md"
                index = subdir / "index.md"
                for f in (readme, index):
                    if f.exists():
                        adr = self._parse_adr(f)
                        if adr:
                            adr["filename"] = str(f.relative_to(self.root_path))
                            adrs.append(adr)
                        break

        return {
            "total": len(adrs),
            "adrs": [self._adr_to_dict(a) for a in adrs],
        }

    @staticmethod
    def _parse_adr(file_path: Path) -> Optional[dict]:
        """解析单个 ADR 文件"""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        # 标题
        title_match = AdrScanner.ADR_PATTERN.search(content)
        if not title_match:
            # 回退：取第一个 h1
            h1_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
                number = ""
            else:
                return None
        else:
            number = title_match.group(1)
            title = title_match.group(2).strip()

        # 状态
        status = "proposed"
        status_match = AdrScanner.STATUS_RE.search(content[:200])
        if status_match:
            status = status_match.group(1).lower()

        # 日期
        date = ""
        date_match = AdrScanner.DATE_RE.search(content[:200])
        if date_match:
            date = date_match.group(1)

        return {
            "number": number,
            "title": title,
            "status": status,
            "date": date,
            "filename": str(file_path.relative_to(file_path.parent.parent.parent))
                          if "docs/adr" in str(file_path) else str(file_path),
            "sourcePath": str(file_path),
        }

    @staticmethod
    def _adr_to_dict(adr: dict) -> dict:
        return {k: v for k, v in adr.items() if v is not None}
