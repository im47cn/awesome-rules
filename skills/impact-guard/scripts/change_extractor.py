"""ChangeExtractor — git diff / --changed 归一为 List[ChangePoint]"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from _compat import LayerIdentifier

import json


@dataclass
class ChangePoint:
    qualified_name: str      # com.example.order.app.OrderCreateExecutor
    file_path: str
    layer: str               # start/adapter/client/application/domain/infrastructure
    component_type: str      # controller/executor/entity/...（LayerIdentifier 第二返回值）
    change_type: str = "modified"   # modified / added / deleted


def _git_lines(project_root: Path, *args: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True, text=True, timeout=30, check=True).stdout
        return [l.strip() for l in out.splitlines() if l.strip()]
    except (subprocess.SubprocessError, OSError):
        return []


def load_config(project_root: Path, config_path: str | None = None) -> dict:
    """加载 .impact-guard.json（自动查找项目根）。"""
    if config_path:
        p = Path(config_path)
    else:
        p = Path(project_root) / ".impact-guard.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


class ChangeExtractor:
    """两种输入归一为变更点列表（v1 粒度：类级）。"""

    def __init__(self, project_root: str, config: dict):
        self.root = Path(project_root)
        self.config = config
        self._identifier = LayerIdentifier()

    def extract_from_diff(self, ref: str = "origin/master...HEAD",
                          infos: dict | None = None) -> list[ChangePoint]:
        """git diff → 变更 Java 文件 → 类级变更点。

        infos: ImpactScanner.scan() 的 {qualified_name: file_info}（可选，避免重复扫描）。
        """
        name_status = _git_lines(self.root, "diff", "--name-status", ref)
        return self._from_name_status(name_status, infos)

    def extract_explicit(self, changed: list[str],
                         infos: dict | None = None) -> list[ChangePoint]:
        """--changed 显式起点（qualified_name 或文件路径，可多次）。"""
        points = []
        for item in changed:
            info = (infos or {}).get(item)
            if info is None:
                # 尝试按文件路径后缀匹配
                info = next((f for f in (infos or {}).values()
                             if f.get("filePath", "").endswith(item) or item.endswith(
                                 f.get("filePath", ""))), None)
            if info is None:
                # 无 infos（未扫描）时按源码路径规则推导 qn
                info = self._derive_info(item)
            if info is not None:
                points.append(self._to_point(info, "modified"))
        return points

    def _from_name_status(self, lines: list[str], infos: dict | None) -> list[ChangePoint]:
        points = []
        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status, path = parts
            if not path.endswith(".java"):
                continue
            ctype = {"A": "added", "D": "deleted"}.get(status[0], "modified")
            info = (infos or {}).get(path) or next(
                (f for f in (infos or {}).values()
                 if f.get("filePath", "").endswith(path)), None)
            if info is None:
                info = self._derive_info(path)
            if info is not None:
                points.append(self._to_point(info, ctype))
        return points

    def _to_point(self, info: dict, change_type: str) -> ChangePoint:
        result = self._identifier.classify(info)
        layer, comp_type = result if result else ("", "")
        return ChangePoint(
            qualified_name=info.get("qualifiedName", ""),
            file_path=info.get("filePath", ""),
            layer=layer,
            component_type=comp_type,
            change_type=change_type,
        )

    def _derive_info(self, path: str) -> dict | None:
        """无扫描结果时，从源码路径推导 package/qualifiedName/className。"""
        p = Path(path)
        if not p.suffix == ".java":
            return None
        src = self.root / path
        text = src.read_text(encoding="utf-8") if src.exists() else ""
        package = ""
        for line in text.splitlines():
            if line.strip().startswith("package "):
                package = line.strip().rstrip(";").removeprefix("package ").strip()
                break
        class_name = p.stem
        qn = f"{package}.{class_name}" if package else class_name
        if not src.exists():
            return None  # 删除的文件读不到内容；package 未知则只能给文件级
        return {"filePath": path, "package": package, "qualifiedName": qn,
                "className": class_name, "annotations": [], "imports": [],
                "methods": [], "fields": [], "enumValues": [], "nestedEnums": [],
                "classType": "", "deprecated": False}
