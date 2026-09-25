#!/usr/bin/env python3
"""badcase 物料（expected.md / prompts.md）解析——单一真相源。

原 scripts/badcase_runner.py 与 skills/skill-evo/scripts/evo_replay.py 各持一份
同构解析并已漂移（别名口径、「人工补充」语义），2026-09-25 收编于此：
两调用方以参数选择语义（strip_aliases / manual 取舍），格式演进只改一处。
"""

from __future__ import annotations

import re
from pathlib import Path


def parse_expected(expected_path: Path, strip_aliases: bool = False):
    """解析 expected.md，返回 (check_script, expected_rules, manual_rule_ids, manual_notes)。

    - check_script：「check: xxx.py」声明的检查脚本
    - expected_rules：「预期检查输出」小节中「脚本自动检出」的规则与裸 bullet
    - manual_rule_ids：「人工补充规则：」行的规则 ID（evo_replay include_manual
      时并入 expected 比对；badcase_runner 仅记录展示）
    - manual_notes：「人工补充：」描述行（仅展示，不参与任何比对）
    - strip_aliases=True 时「脚本自动检出」的别名串（「规范名|别名1|别名2」）
      只取首 token 规范名——badcase_runner 纯脚本回归语义；False 保留全 token
      ——evo_replay GEPA 评估集 any-of 别名匹配语义
    - 无「预期检查输出」小节（旧式）：第一个 ## 标题前的顶层 bullet 全入
      expected_rules（违规语句/改进建议等小节里的 bullet 是给人工看的叙述）
    """
    if not expected_path.is_file():
        return None, [], [], []

    text = expected_path.read_text(encoding="utf-8")

    check_script = None
    m = re.search(r"(?:check|脚本)\s*[:：]\s*(\S+\.py)", text)
    if m:
        check_script = m[1].strip()

    expected_rules, manual_rule_ids, manual_notes = [], [], []

    def _split_rules(payload: str):
        tokens = [p.strip() for p in re.split(r"[、,，;；]", payload) if p.strip()]
        return [t.split("|")[0] for t in tokens] if strip_aliases else tokens

    section = re.search(r"##\s*预期检查输出\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL)
    if section:
        # 新式：只认「预期检查输出」小节的 bullet
        for line in section[1].split("\n"):
            m = re.match(r"^[-*]\s+(.+)", line.strip())
            if not m:
                continue
            item = m[1].strip()
            if item.startswith("脚本自动检出"):
                expected_rules.extend(_split_rules(
                    re.split(r"[:：]", item, 1)[-1]))
            elif item.startswith("人工补充规则"):
                manual_rule_ids.extend(_split_rules(
                    re.split(r"[:：]", item, 1)[-1]))
            elif item.startswith("人工补充"):
                manual_notes.append(re.split(r"[:：]", item, 1)[-1].strip())
            elif item and not item.startswith("#"):
                expected_rules.append(item)
    else:
        # 旧式：第一个 ## 标题前的顶层 bullet
        head = re.split(r"\n##\s", text, 1)[0]
        for line in head.split("\n"):
            m = re.match(r"^[-*]\s+(.+)", line.strip())
            if m:
                rule = m[1].strip()
                if rule and not rule.startswith("#"):
                    expected_rules.append(rule)

    return check_script, expected_rules, manual_rule_ids, manual_notes


def parse_prompts(prompts_path: Path):
    """解析 prompts.md，返回 (prompts, known_issues)。

    两种格式（@date 2026-09-20 双 Agent 扩展）：
    - 旧式纯 bullet：每行 `- 内容` 即一条 prompt（一个回合），行为与历史
      版本逐字一致（零回归锚）
    - `---` 围栏块：每个围栏块一条 prompt；块内有 bullet → 逐 bullet 一条
      （bullet 恒等于回合）；无 bullet → 剥 `#` 标题行后整块压缩空白为一条
    已知问题 section 先剥离再解析。prompts.md 无 YAML frontmatter，
    ^---$ 行不与其分隔符冲突。
    """
    if not prompts_path.is_file():
        return [], []

    text = prompts_path.read_text(encoding="utf-8")

    # 提取"已知问题"section
    known_section = ""
    if km := re.search(
        r"##\s*已知问题\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL
    ):
        known_section = km[1].strip()
        # 从 text 中移除已知问题部分，避免解析到 prompts
        text = text[: km.start()] + text[km.end():]

    blocks = re.split(r"(?m)^---\s*$", text)
    prompts = []
    if len(blocks) > 1:
        # 围栏模式：逐块 → prompt
        for block in blocks:
            bullets = [m[1].strip() for line in block.split("\n")
                       if (m := re.match(r"^[-*]\s+(.+)", line.strip()))]
            if bullets:
                prompts.extend(b for b in bullets if b)
            else:
                body = "\n".join(l for l in block.split("\n")
                                 if not l.strip().startswith("#"))
                if compact := " ".join(body.split()):
                    prompts.append(compact)
    else:
        # 无围栏 → 既有纯 bullet 行为（零回归）
        for line in text.split("\n"):
            line = line.strip()
            if m := re.match(r"^[-*]\s+(.+)", line):
                if prompt := m[1].strip():
                    prompts.append(prompt)

    known_issues = []
    for line in known_section.split("\n"):
        line = line.strip()
        if m := re.match(r"^[-*]\s+(.+)", line):
            known_issues.append(m[1].strip())

    return prompts, known_issues
