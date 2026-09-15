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
  - parse_frontmatter：门禁用的结构子集解析器（纯 stdlib）：标量 /
    行内列表 / 块列表 / 折叠块（> 与 |）。子集外语法 raise（fail-closed）
    而非静默猜测——这是 schema 校验的结构解析，不是无 schema 正则
    （Rome 教训的正解）。零第三方依赖：CI runner 与 hook 环境均无须装包
    （2026-09-15 实证：PR CI 无 PyYAML，import 即炸）

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
    """门禁用结构子集解析器（纯 stdlib，fail-closed）。

    支持语法：`key: value` 标量 / `key: [a, b]` 行内列表 / `key:` +
    `  - item` 块列表 / `key: >|>-|-` 折叠块（收集为多行字符串）。
    子集外语法（嵌套结构、未知缩进、顶层裸文本）raise ValueError——
    门禁要求可解析性显式成立，不静默猜测（YAML 重复键同样显式拒绝：
    safe_load 语义是静默取后值，拼写漂移会静默生效）。
    """
    fm = split_frontmatter(content)
    if fm is None:
        return {}
    result: dict = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", ln)
        if not m:
            raise ValueError(
                f"frontmatter 子集外语法（第 {i + 1} 行）: {ln!r}——"
                f"仅支持 key: value / 行内列表 / 块列表 / 折叠块"
            )
        key, val = m.group(1), m.group(2).strip()
        if key in result:
            raise ValueError(f"frontmatter 重复键 {key!r}（静默取后值属拼写漂移，门禁显式拒绝）")
        if val == "":
            # 块列表：紧随的 `  - item` 行
            items = []
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                items.append(lines[i][4:].strip())
                i += 1
            result[key] = items
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = [s.strip() for s in inner.split(",")] if inner else []
        elif val in (">", "|", ">-", "|-"):
            # 折叠/字面块：收集缩进续行（含块内空行）为多行字符串
            i += 1
            buf = []
            while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                if lines[i].strip() == "" and i + 1 < len(lines) and not lines[i + 1].startswith("  "):
                    break  # 空行 + 后续非缩进 = 块结束
                buf.append(lines[i].strip())
                i += 1
            result[key] = "\n".join(buf)
            continue  # i 已推进到块后首行，不得再走循环尾统一 +1
        else:
            result[key] = val.strip("'\"")
        i += 1
    return result


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
