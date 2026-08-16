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
    changed_methods: list = None    # 变更行命中的方法名（区间近似：方法起始行到下一方法前）

    def __post_init__(self):
        if self.changed_methods is None:
            self.changed_methods = []


def parse_diff_hunks(diff_text: str) -> dict[str, dict]:
    """解析 `git diff -U0` 输出 → {path: {change_type, hunks: [(start,end)...]}}。

    hunks 为 head 侧（新文件）行区间，1-based 闭区间。
    """
    import re as _re
    result: dict[str, dict] = {}
    current_file = None
    change_type = "modified"
    for line in diff_text.splitlines():
        m = _re.match(r'diff --git a/(.+) b/(.+)$', line)
        if m:
            current_file = m.group(2)
            change_type = "modified"
            result.setdefault(current_file, {"change_type": change_type, "hunks": []})
            continue
        if current_file is None:
            continue
        if line.startswith("new file mode"):
            change_type = "added"
        elif line.startswith("deleted file mode"):
            change_type = "deleted"
        elif line.startswith("@@"):
            h = _re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
            if h:
                start = int(h.group(1))
                count = int(h.group(2)) if h.group(2) is not None else 1
                if count > 0:  # count=0（纯删除锚点）不产生 head 侧行
                    result[current_file]["hunks"].append((start, start + count - 1))
        if current_file in result:
            result[current_file]["change_type"] = change_type
    return result


def match_changed_methods(hunks: list, methods: list) -> list[str]:
    """变更行区间 ↔ 方法区间求交。

    方法区间近似：起始行到下一方法起始行-1（最后一个到文件尾）。
    """
    if not hunks or not methods:
        return []
    sorted_methods = sorted(
        [m for m in methods if m.get("line")], key=lambda m: m["line"])
    matched = []
    for i, m in enumerate(sorted_methods):
        start = m["line"]
        end = sorted_methods[i + 1]["line"] - 1 if i + 1 < len(sorted_methods) \
            else float("inf")
        if any(not (h_end < start or h_start > end) for h_start, h_end in hunks):
            matched.append(m["name"])
    return matched


def _git_lines(project_root: Path, *args: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True, text=True, timeout=30, check=True).stdout
        return [l.strip() for l in out.splitlines() if l.strip()]
    except (subprocess.SubprocessError, OSError):
        return []


def _git_text(project_root: Path, *args: str) -> str | None:
    """git 命令完整文本输出（失败返回 None，不与'无差异'的空串混淆）。"""
    try:
        return subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True, text=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return None


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
        """git diff -U0 → 变更 Java 文件 → 类级 + 方法级变更点（v2）。

        infos: ImpactScanner.scan() 的 {qualified_name: file_info}（可选，避免重复扫描）。
        """
        diff_text = _git_text(self.root, "diff", "-U0", ref)
        if diff_text is None:
            return []
        file_diffs = parse_diff_hunks(diff_text)
        points = []
        for path, fd in file_diffs.items():
            if not path.endswith(".java"):
                continue
            info = (infos or {}).get(path) or next(
                (f for f in (infos or {}).values()
                 if f.get("filePath", "").endswith(path)), None)
            if info is None:
                info = self._derive_info(path)
            if info is None:
                continue
            cp = self._to_point(info, fd["change_type"])
            if fd["change_type"] == "modified":
                cp.changed_methods = match_changed_methods(
                    fd["hunks"], info.get("methods", []))
            points.append(cp)
        return points

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
