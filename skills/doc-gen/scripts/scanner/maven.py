"""Maven 多模块项目结构扫描器。"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


class MavenScanner:
    """Maven 多模块项目结构扫描"""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.modules: dict[str, dict] = {}  # artifactId -> {groupId, path, dependencies, parent}

    def scan(self) -> dict:
        """扫描根 pom.xml 和子模块"""
        root_pom = self.root_path / "pom.xml"
        if not root_pom.exists():
            return {"error": "根 pom.xml 未找到，仅按包路径扫描"}

        root = self._parse_pom(root_pom)
        if not root:
            return {"error": "无法解析根 pom.xml"}

        # 扫描子模块
        for module_dir in root.get("modules", []):
            module_pom = self.root_path / module_dir / "pom.xml"
            if module_pom.exists():
                self._scan_module(module_pom, root)

        return {
            "groupId": root.get("groupId", ""),
            "artifactId": root.get("artifactId", ""),
            "modules": self.modules,
        }

    def _parse_pom(self, pom_path: Path) -> Optional[dict]:
        """解析单个 pom.xml"""
        try:
            # 去掉命名空间以简化解析
            xml_str = pom_path.read_text(encoding="utf-8")
            xml_str = re.sub(r'xmlns="[^"]*"', '', xml_str)
            xml_str = re.sub(r'xsi:schemaLocation="[^"]*"', '', xml_str)
            root = ET.fromstring(xml_str)

            ns = ""
            group_id = ""
            artifact_id = ""
            modules = []
            dependencies = []

            for child in root:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "groupId":
                    group_id = (child.text or "").strip()
                elif tag == "artifactId":
                    artifact_id = (child.text or "").strip()
                elif tag == "modules":
                    for mod in child:
                        if mod.text:
                            modules.append(mod.text.strip())
                elif tag == "dependencyManagement":
                    # 跳过 - 不需要深度解析
                    pass
                elif tag == "dependencies":
                    for dep in child:
                        dep_info = self._parse_dependency(dep)
                        if dep_info:
                            dependencies.append(dep_info)
                elif tag == "parent":
                    parent_info = self._parse_parent(child)
                    if parent_info and not group_id:
                        group_id = parent_info.get("groupId", "")

            return {
                "groupId": group_id,
                "artifactId": artifact_id,
                "modules": modules,
                "dependencies": dependencies,
            }
        except ET.ParseError as e:
            print(f"  ⚠ 解析 {pom_path} 失败: {e}", file=sys.stderr)
            return None

    def _parse_parent(self, element: ET.Element) -> dict:
        result = {}
        for child in element:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag in ("groupId", "artifactId", "version"):
                result[tag] = (child.text or "").strip()
        return result

    def _parse_dependency(self, element: ET.Element) -> Optional[dict]:
        result = {}
        for child in element:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag in ("groupId", "artifactId", "version", "scope"):
                result[tag] = (child.text or "").strip()
        return result if "artifactId" in result else None

    def _scan_module(self, pom_path: Path, parent_info: dict):
        """递归扫描模块 pom.xml"""
        parsed = self._parse_pom(pom_path)
        if not parsed:
            return

        artifact_id = parsed.get("artifactId", "")
        module_dir = str(pom_path.parent.relative_to(self.root_path))

        self.modules[artifact_id] = {
            "groupId": parsed.get("groupId") or parent_info.get("groupId", ""),
            "artifactId": artifact_id,
            "path": module_dir,
            "dependencies": parsed.get("dependencies", []),
        }

        # 递归处理子模块
        for sub_module in parsed.get("modules", []):
            sub_pom = pom_path.parent / sub_module / "pom.xml"
            if sub_pom.exists():
                self._scan_module(sub_pom, parent_info)
