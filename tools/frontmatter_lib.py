#!/usr/bin/env python3
"""frontmatter_lib — markdown frontmatter 单一事实源（解析 + 两族 schema 校验）

历史病灶：hooks/load-steering.sh 与 tools/check_doc_freshness.py 各持一份
frontmatter 解析逻辑，靠注释声明"口径对齐"（纪律同步）。2026-09 调研
rome-os/rome 实证：校验链最薄弱环节正是"正则解析无 schema"——本模块
消灭第二份实现，两个消费者统一 import 此处。

解析分层（与消费方式匹配，详见 docs/design/skill-manifest-gate.md ADR-2）：
  - simple_fields：纯 stdlib 标量提取，供 SessionStart hook（无第三方依赖、
    单行 `key: value` 子集）。分叉被结构性封死：M1 校验保证 steering
    title/scenario 恰为单行标量，即 simple 路径的假设恒成立
  - parse_frontmatter：完整 YAML 解析（PyYAML），供门禁检查器（须处理
    `description: >` 折叠块与列表）。缺 PyYAML 时 fail-closed

schema 双层严格度（ADR-2）：声明字段严格（类型/必填/路径存在）；未知
字段容忍但惰性——不剥离、不校验、不阻断。人写文档不被封闭 schema 绑架。
"""
from __future__ import annotations

import re
from typing import Optional

__all__ = [
    "split_frontmatter",
    "simple_fields",
    "parse_frontmatter",
    "validate_steering",
    "validate_skill",
]

# 简单路径仅认单行标量；门禁 M1 强制 title/scenario 为单行非空，
# 保证该子集对 steering 族恒充分。
_SCALAR_RE = re.compile(r"(?m)^([A-Za-z0-9_-]+):\s*(.*)$")


def split_frontmatter(content: str) -> Optional[str]:
    """返回 frontmatter 块内容（不含首尾 --- 分隔行）；无 frontmatter 返回 None。

    口径与原 hooks/load-steering.sh 对齐：startswith('---')，
    结束于首个 '\\n---'。结束分隔后允许尾随空白。
    """
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    return content[3:end]


def simple_fields(content: str) -> dict:
    """标量子集提取（无第三方依赖）：`key: value` 单行键值对。

    嵌套结构（列表/折叠块）不在此路径的契约内——需要完整结构时用
    parse_frontmatter。键重复时后值覆盖前值（与门禁 M1 的唯一性校验互补：
    门禁拒绝重复键，运行时简化处理）。
    """
    fm = split_frontmatter(content)
    if fm is None:
        return {}
    fields: dict = {}
    for m in _SCALAR_RE.finditer(fm):
        fields[m.group(1)] = m.group(2).strip()
    return fields


def parse_frontmatter(content: str) -> dict:
    """完整 YAML 解析 frontmatter（依赖 PyYAML，缺失即抛错，不静默降级）。

    YAML 重复键在 safe_load 下静默取后值（最后一行覆盖前面的同名键，
    拼写漂移即静默生效）——门禁语义要求显式拒绝而非静默容忍。
    """
    fm = split_frontmatter(content)
    if fm is None:
        return {}
    seen: dict = {}
    for m in re.finditer(r"(?m)^([A-Za-z0-9_-]+):", fm):
        if m.group(1) in seen:
            raise ValueError(f"frontmatter 重复键 {m.group(1)!r}（safe_load 静默取后值，门禁显式拒绝）")
        seen[m.group(1)] = True
    import yaml

    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError as exc:  # pragma: no cover - 消息内容随 PyYAML 版本
        raise ValueError(f"frontmatter YAML 解析失败: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter 顶层须为映射，实际: {type(data).__name__}")
    return data


# ── M1 steering 族：title/scenario 必填、单行、非空、不可重复 ────────────


def validate_steering(fm: dict, rel: str) -> list:
    """校验 steering 规范 frontmatter，返回错误列表（空 = 通过）。

    单行约束是 simple_fields 路径的结构性前提（见模块 docstring），
    同时禁重复键（YAML 重复键在 safe_load 下静默取后值，门禁须显式拒绝）。
    """
    errors: list = []
    for key in ("title", "scenario"):
        val = fm.get(key)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"M1 {rel}: frontmatter 字段 {key} 缺失或为空")
        elif "\n" in val:
            errors.append(f"M1 {rel}: {key} 必须单行（simple 解析路径前提）")
    return errors


# ── M2 skills 族：name/files 必填 + files 断链单向 ────────────────────────


def validate_skill(fm: dict, rel: str, skill_dir) -> list:
    """校验 SKILL.md frontmatter，返回错误列表（空 = 通过）。

    断链单向（ADR-3）：只验证声明的路径存在，不反向要求磁盘文件被声明。
    路径围栏（ADR-2 借鉴 rome resolvePathWithinBase）：拒绝绝对路径与
    `..` 逃逸——声明的文件必须落在 skill 目录内部。
    files 允许显式空列表（纯文档型 skill），但不允许缺键（ADR-5）。
    """
    from pathlib import Path

    errors: list = []
    name = fm.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"M2 {rel}: frontmatter 字段 name 缺失或为空")
    files = fm.get("files")
    if files is None:
        errors.append(f"M2 {rel}: frontmatter 缺少 files 声明（纯文档型 skill 可显式 files: []）")
        return errors
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        errors.append(f"M2 {rel}: files 必须为字符串列表")
        return errors
    for entry in files:
        p = Path(entry)
        if p.is_absolute():
            errors.append(f"M2 {rel}: files 条目 {entry!r} 为绝对路径，仅允许 skill 目录内相对路径")
            continue
        if ".." in p.parts:
            errors.append(f"M2 {rel}: files 条目 {entry!r} 含 .. 逃逸，必须解析在 skill 目录内")
            continue
        if not (Path(skill_dir) / p).exists():
            errors.append(f"M2 {rel}: files 条目 {entry!r} 指向的文件不存在（断链）")
    return errors
