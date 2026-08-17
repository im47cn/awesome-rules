"""业务上下文扫描器 — 人工 business-context.md 为主 + 代码弱信号锚定为辅。

输入约定（AH-MANIFEST.md §5.1 受约束 markdown 子集）：
  ## 客户 / ## 角色 / ## 业务场景   条目：- **名称**：描述（场景支持 ``(域名)`` 前缀）
  ## 业务流程                      流程：### 名称，步骤：1. 步骤名 → 锚点

弱信号（source=code）：
  角色   — @PreAuthorize hasRole/hasAnyRole/hasAuthority 文本匹配，锚定所在类 qn
  流程   — StateMachineDoc 转换序列 → 状态流转流程

合并策略：md 条目优先；同名角色被代码证据补锚点时升 source=hybrid。
"""

from __future__ import annotations  # 兼容 Python 3.9：延迟求值 PEP 604 联合类型注解

import re
from pathlib import Path

from doctypes import (
    BusinessContextDoc,
    BusinessFlowDoc,
    BusinessFlowStepDoc,
    BusinessItemDoc,
)

# md 二级标题 → 分片字段
_MD_SECTIONS = {"客户": "customers", "角色": "roles", "业务场景": "scenarios"}

_ITEM_RE = re.compile(r"^-\s+\*\*(.+?)\*\*\s*[：:]\s*(.*)$")
# 场景条目名称里的 (domain) / （domain）归属标注
_DOMAIN_RE = re.compile(r"[（(]\s*([A-Za-z0-9_-]+)\s*[）)]")
_FLOW_HEAD_RE = re.compile(r"^###\s+(.+)$")
_STEP_RE = re.compile(r"^\d+[.、]\s*(.+)$")

# @PreAuthorize 角色提取（单引号/双引号、单角色/任一角色/权限）
_ROLE_RES = [
    re.compile(r"hasRole\(\s*'([^']+)'\s*\)"),
    re.compile(r'hasRole\(\s*"([^"]+)"\s*\)'),
    re.compile(r"hasAnyRole\(\s*'([^']+)'"),
    re.compile(r'hasAnyRole\(\s*"([^"]+)"'),
    re.compile(r"hasAuthority\(\s*'([^']+)'\s*\)"),
    re.compile(r'hasAuthority\(\s*"([^"]+)"\s*\)'),
]


class BusinessContextScanner:
    """业务上下文扫描：md 解析 + 弱信号提取 + 合并"""

    def __init__(self, root_path: str, config: dict | None = None):
        self.root = Path(root_path).resolve()
        self.config = config or {}

    # ── 对外入口 ──────────────────────────────────────────────────────────────

    def find_context_md(self) -> Path | None:
        """按优先级查找 business-context.md：配置指定 → 根目录 → docs/"""
        candidates: list[Path] = []
        cfg_file = self.config.get("business_context_file")
        if cfg_file:
            candidates.append(self.root / cfg_file)
        candidates.append(self.root / "business-context.md")
        candidates.append(self.root / "docs" / "business-context.md")
        for c in candidates:
            if c.is_file():
                return c
        return None

    def scan(self, java_files: list, state_machines: list) -> BusinessContextDoc | None:
        """扫描并合并，产出业务维度扩展分片；全空（无 md 且无弱信号）返回 None"""
        md = self._read_md()
        code_roles = self._scan_roles(java_files)
        code_flows = self._flows_from_state_machines(state_machines)

        ctx = BusinessContextDoc()
        ctx.customers = md.get("customers", [])
        ctx.scenarios = md.get("scenarios", [])
        ctx.roles = self._merge_roles(md.get("roles", []), code_roles)
        ctx.flows = self._merge_flows(md.get("flows", []), code_flows)

        total = (len(ctx.customers) + len(ctx.roles)
                 + len(ctx.scenarios) + len(ctx.flows))
        return ctx if total > 0 else None

    # ── md 解析 ───────────────────────────────────────────────────────────────

    def _read_md(self) -> dict:
        md_path = self.find_context_md()
        if md_path is None:
            return {}
        try:
            return self.parse_md(md_path.read_text(encoding="utf-8"))
        except OSError:
            return {}

    @staticmethod
    def parse_md(text: str) -> dict:
        """解析受约束 markdown 子集，忽略不认识的节与行"""
        result: dict = {"customers": [], "roles": [], "scenarios": [], "flows": []}
        section = None          # 当前二级标题对应的字段
        current_flow = None     # 当前流程（### 层级）

        for raw in text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue

            # 二级标题：切换节（业务流程单独处理）
            if line.startswith("## "):
                head = line[3:].strip()
                if head == "业务流程":
                    section, current_flow = "flows", None
                elif head in _MD_SECTIONS:
                    section, current_flow = _MD_SECTIONS[head], None
                else:
                    section, current_flow = None, None
                continue

            if section == "flows":
                # ### 流程名（可选「：描述」）
                m = _FLOW_HEAD_RE.match(line)
                if m:
                    name, _, desc = m.group(1).partition("：")
                    if not desc:
                        name, _, desc = m.group(1).partition(": ")
                    current_flow = BusinessFlowDoc(
                        name=name.strip(), description=desc.strip())
                    result["flows"].append(current_flow)
                    continue
                # 有序步骤：1. 步骤名 → 锚点1, 锚点2
                m = _STEP_RE.match(line)
                if m and current_flow is not None:
                    step_text = m.group(1).strip()
                    step_name, _, anchor_text = step_text.partition("→")
                    anchors = [a.strip() for a in anchor_text.split(",") if a.strip()] \
                        if anchor_text.strip() else []
                    desc = ""
                    if "：" in step_name or ": " in step_name:
                        sep = "：" if "：" in step_name else ": "
                        step_name, _, desc = step_name.partition(sep)
                    current_flow.steps.append(BusinessFlowStepDoc(
                        name=step_name.strip(), description=desc.strip(),
                        anchors=anchors))
                continue

            if section is None:
                continue
            # 条目：- **名称**：描述
            m = _ITEM_RE.match(line)
            if not m:
                continue
            name, desc = m.group(1).strip(), m.group(2).strip()
            item = {"name": name, "description": desc, "source": "manual"}
            if section == "scenarios":
                # 场景名支持 (domain) 标注：- **下单**：(order) 描述
                dm = _DOMAIN_RE.match(desc)
                if dm:
                    item["domain"] = dm.group(1)
                    item["description"] = desc[dm.end():].lstrip(" 　")
            result[section].append(BusinessItemDoc(**item))

        return result

    # ── 弱信号提取 ────────────────────────────────────────────────────────────

    def _scan_roles(self, java_files: list) -> list[BusinessItemDoc]:
        """从 @PreAuthorize 注解提取角色（source=code，锚定所在类）"""
        roles: dict[str, list[str]] = {}
        for jf in java_files:
            file_path = jf.get("filePath", "")
            qn = jf.get("qualifiedName", "")
            if not file_path or not qn:
                continue
            # JavaScanner 的 filePath 为项目相对路径 → 拼接项目根
            src = Path(file_path)
            if not src.is_absolute():
                src = self.root / file_path
            try:
                text = src.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for rx in _ROLE_RES:
                for m in rx.finditer(text):
                    role = m.group(1).strip()
                    if role:
                        roles.setdefault(role, [])
                        if qn not in roles[role]:
                            roles[role].append(qn)
        return [BusinessItemDoc(name=r, source="code", anchors=qns)
                for r, qns in sorted(roles.items())]

    def _flows_from_state_machines(self, state_machines: list) -> list[BusinessFlowDoc]:
        """状态机 → 状态流转流程（source=code）"""
        flows = []
        for sm in state_machines:
            steps = [BusinessFlowStepDoc(
                name=f"{t.source} → {t.target}" + (f"（{t.event}）" if t.event else ""))
                for t in (sm.transitions or [])]
            if not steps:
                continue
            anchors = [a for a in (sm.sourceClass, sm.managedEnum) if a]
            flows.append(BusinessFlowDoc(
                name=f"{sm.name} 状态流转",
                description=f"由{sm.sourceClass or sm.name}的状态机驱动",
                steps=steps, source="code", anchors=anchors))
        return flows

    # ── 合并 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_roles(md_roles: list, code_roles: list) -> list:
        """md 优先；同名角色被代码证据补锚点 → hybrid；纯代码角色追加在后"""
        merged = list(md_roles)
        md_names = {r.name for r in md_roles}
        for cr in code_roles:
            hit = next((r for r in merged if r.name == cr.name), None)
            if hit is not None:
                new_anchors = list(hit.anchors) + [a for a in cr.anchors
                                                   if a not in hit.anchors]
                hit.anchors = new_anchors
                if hit.source == "manual":
                    hit.source = "hybrid"
            else:
                merged.append(cr)
        return merged

    @staticmethod
    def _merge_flows(md_flows: list, code_flows: list) -> list:
        """md 优先；同名状态机流程已被人工覆盖时跳过代码版"""
        merged = list(md_flows)
        md_names = {f.name for f in md_flows}
        merged.extend(f for f in code_flows if f.name not in md_names)
        return merged
