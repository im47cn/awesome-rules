#!/usr/bin/env python3
"""check_doc_freshness — 实现↔文档一致性门禁（陈述 vs 事实）

代码是事实，文档是陈述；两者的差（数字、清单、指向）此前只能靠人工
审查发现。本门把审查实证逃逸过的漂移（计数/覆盖/枚举）+ 已踩坑断言
机械化，让工厂链 final_gate 自己拦漂移：

  R1 工厂组件覆盖：.factory 顶层 *.sh/*.py 每个文件名须出现在
     .factory/README.md 文本中（子目录内文件豁免——tests/ locks/
     mutations/ db/ prompts/ artifacts/ worktrees/ metrics/ var/
     按目录名整体提及即可，不逐一点名）
  R2 提示词计数：README「N 个…提示词」（含中文数字）的 N 必须等于
     .factory/prompts/*.md 实数；若改为逐一列名（含 prompts 的行内
     反引号 .md 名），则列名集合 == 实际文件名集合。计数口径先命中
     则不再查列名口径
  R3 结构树覆盖：根 README tree 区块的 skills 子目录名 ⊇ skills/
     下所有含 SKILL.md 的目录；_shared 无 SKILL.md → 缺失仅 [INFO]
  R4 技能测试数：skills/*/{README,SKILL}.md 中紧邻「测试」的数字
     陈述（测试 N 项 / N 项测试 / （N 条））== 对应测试文件的
     def test_ 计数。对应关系：陈述行内 markdown 链接指向具体
     test_*.py 则只数该文件，否则聚合该技能全部 test_*.py；
     找不到测试文件 → [INFO] 跳过
  R5 交叉引用防复发（只查两条已踩坑断言，防回归）：
     a. impact-guard SKILL/README 不得再出现「复用 arch-guard」；
        「复用来源」行须指向实际存在的 doc-gen 路径
     b. .factory/README 不得再出现「git checkout -b factory/issue」
        （实际是 worktree add -B）
  R6 平台清单覆盖：.opencode/opencode.json 的 instructions ⊇
     skills/*/SKILL.md 全集 ∪ steering 顶层 *.md 全集。opencode 是
     枚举式注入清单，缺新技能/新规范即漂移；其余平台为 ./skills/
     目录级声明，无枚举漂移面（文件不存在则整条跳过）
  R7 枚举完整性（三处人工维护清单，文件缺失对应子项跳过）：
     a. CONTRIBUTING.md 目录结构树（``` 围栏）中的 steering 文件 ⊇
        steering/ 顶层 *.md
     b. AGENTS.md / CLAUDE.md「通用设计规范」行枚举 ⊇ 各规范主题。
        主题 = frontmatter title 去「规范/标准」尾缀；覆盖判定为
        枚举 token（「——」后的、/，切分）与主题互为包含——容忍
        「API 设计」对「Open API 设计」这类前后缀措辞差；行含
        「等」明示枚举非穷尽，该行不查
     c. hooks/load-steering.sh「审查类任务可使用」清单 ⊇ 全部
        *-guard 技能
  R8 分发闸枚举覆盖：tools/git/README.md 的 pre-push 并发注记行枚举的
     command 名 ⊇ tools/git/lefthook.yml pre-push: commands 键全集
     （行内按分隔符切 token 与命令名取交集，容忍多余措辞；加/删闸
     不更新注记即漂移；yml 或 README 任一缺失则整条跳过）

豁免（误报控制，两条稳定通道）：
  --allow REGEX（可重复）：正则 search 命中证据行（[级别] 文件:行 →
  消息）即跳过该条——R1 这类无源行的发现用它做条目级豁免
  行级：markdown 源行尾追加 <!-- doc-freshness:allow -->

用法:
  python3 tools/check_doc_freshness.py [repo_root] [--allow REGEX]

退出码: 0=一致
        1=有漂移（任一 FAIL）
        2=结构性错误（repo_root 缺 .factory / .factory/README.md /
          README.md / skills 任一项——门自身不可判，fail-closed）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ALLOW_MARK = "<!-- doc-freshness:allow -->"

_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
       "六": 6, "七": 7, "八": 8, "九": 9}

# R2 计数口径：N 个 …提示词（N 支持阿拉伯与中文数字；间隙限 30 字且
# 不跨句/表格列，避免把无关计数误归提示词）
_NUM = r"([0-9]+|[一二三四五六七八九十]{1,3})"
R2_COUNT_RE = re.compile(r"[（(]?\s*" + _NUM + r"\s*[)）]?\s*个[^。\n|]{0,30}?提示词")

# R4 陈述口径：三个形态都要求「项/条」做单位（覆盖率 95% 这类百分数
# 天然不匹配）；模式 2 仅在行含「测试」时启用（见 rule_r4）
R4_TESTED_RE = re.compile(r"测试\s*[（(]?\s*(\d+)\s*[)）]?\s*[项条个]")
R4_PAREN_RE = re.compile(r"[（(]\s*(\d+)\s*[项条]\s*[)）]")
R4_REVERSED_RE = re.compile(r"(\d+)\s*[项条]\s*测试")

R5_REUSE_RE = re.compile(r"复用\s*arch-guard")
R5_CHECKOUT_RE = re.compile(r"git\s+checkout\s+-b\s+factory/issue")

# R8 陈述侧口径：注记行按分隔符切 token，与 pre-push command 名取交集
R8_SPLIT_RE = re.compile(r"[\s/、，,`*（）()：:。；;]+")

DEF_TEST_RE = re.compile(r"(?m)^\s*(?:async\s+)?def\s+test_")


def _cn_to_int(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        left, _, right = s.partition("十")
        if (left and left not in _CN) or (right and right not in _CN):
            return None
        return (_CN.get(left, 1) if left else 1) * 10 + (_CN.get(right, 0) if right else 0)
    return _CN.get(s) if len(s) == 1 else None


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _fence_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """提取 ``` 围栏区块 → [(起始行号, 区块行, ...)]（未闭合尾块算到文末）。

    R3/R7a 共用：起始行号为围栏内第一行的行号。
    """
    segs: list[tuple[int, list[str]]] = []
    inside, start = False, 0
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            if inside:
                segs.append((start, lines[start - 1:i - 1]))
            else:
                start = i + 1
            inside = not inside
    if inside:
        segs.append((start, lines[start - 1:]))
    return segs


class Gate:
    def __init__(self) -> None:
        self.findings: list[tuple[str, str, str]] = []  # (level, where, msg)

    def fail(self, where: str, msg: str) -> None:
        self.findings.append(("FAIL", where, msg))

    def info(self, where: str, msg: str) -> None:
        self.findings.append(("INFO", where, msg))


def rule_r1(root: Path, g: Gate) -> None:
    """R1 工厂组件覆盖：.factory 顶层 *.sh/*.py 逐名点到。"""
    fac = root / ".factory"
    lines = _lines(fac / "README.md")
    text = "\n".join(lines)
    anchor = next((i for i, ln in enumerate(lines, 1)
                   if ln.startswith("##") and "组件" in ln), 1)
    for f in sorted(fac.iterdir()):
        if not f.is_file() or f.suffix not in {".sh", ".py"}:
            continue
        if f.name not in text:
            g.fail(f".factory/README.md:{anchor}",
                   f"R1 顶层组件未提及 {f.name}（.factory 顶层 *.sh/*.py 须在 README 出现）")


def rule_r2(root: Path, g: Gate) -> None:
    """R2 提示词计数：计数口径先命中，否则列名口径。"""
    readme = root / ".factory" / "README.md"
    prompts = root / ".factory" / "prompts"
    lines = _lines(readme)
    actual = sorted(p.name for p in prompts.glob("*.md")) if prompts.is_dir() else []

    claims: list[tuple[int, int]] = []
    for i, ln in enumerate(lines, 1):
        for m in R2_COUNT_RE.finditer(ln):
            n = _cn_to_int(m.group(1))
            if n is not None:
                claims.append((i, n))
    if claims:
        for i, n in claims:
            if n != len(actual):
                g.fail(f".factory/README.md:{i}",
                       f"R2 提示词计数 陈述 {n} vs 实际 {len(actual)}")
        return

    # 列名口径：含 prompts 的行内反引号 .md 名（glob/路径形不算名）
    listed: dict[str, int] = {}
    for i, ln in enumerate(lines, 1):
        if "prompts" not in ln:
            continue
        for tok in re.findall(r"`([^`\n]+\.md)`", ln):
            if "*" not in tok and "/" not in tok:
                listed.setdefault(tok, i)
    if listed:
        for name, i in sorted(listed.items()):
            if name not in actual:
                g.fail(f".factory/README.md:{i}",
                       f"R2 列出不存在的提示词 {name}")
        for name in actual:
            if name not in listed:
                g.fail(".factory/README.md:1",
                       f"R2 逐一列名口径缺 {name}（列名集合须等于实际集合）")


def rule_r3(root: Path, g: Gate) -> None:
    """R3 根 README 结构树 ⊇ 含 SKILL.md 的技能目录。"""
    skills = root / "skills"
    actual = {d.name for d in skills.iterdir()
              if d.is_dir() and (d / "SKILL.md").is_file()}

    segs = _fence_blocks(_lines(root / "README.md"))

    tree_line: int | None = None
    tree_names: list[str] = []
    for seg_start, seg in segs:
        for j, ln in enumerate(seg):
            if re.match(r"\s*[├└]──\s*skills/?(\s|#|$)", ln):
                tree_line = seg_start + j
                for cont in seg[j + 1:]:
                    if not cont.startswith("│"):
                        break
                    if (
                        name := re.sub(r"^[│├└─\s]+", "", cont.split("#")[0])
                        .strip()
                        .rstrip("/")
                    ):
                        tree_names.append(name)
                break
        if tree_line is not None:
            break

    if tree_line is None:
        if actual:
            g.fail("README.md:1",
                   f"R3 结构树未找到 skills 区块（{len(actual)} 个含 SKILL.md 的技能未被覆盖）")
        return
    for name in tree_names:
        if not (skills / name).is_dir():
            g.fail(f"README.md:{tree_line}",
                   f"R3 结构树列出不存在的技能目录 {name}")
    for name in sorted(actual - set(tree_names)):
        g.fail(f"README.md:{tree_line}",
               f"R3 结构树缺少技能目录 {name}")
    shared = skills / "_shared"
    if shared.is_dir() and not (shared / "SKILL.md").is_file() \
            and "_shared" not in tree_names:
        g.info(f"README.md:{tree_line}",
               "R3 建议在结构树列出 _shared（无 SKILL.md，不强制）")


def _count_def_test(path: Path) -> int:
    return len(DEF_TEST_RE.findall(path.read_text(encoding="utf-8")))


def rule_r4(root: Path, g: Gate) -> None:
    """R4 技能测试数对账：行内点名测试文件则只数该文件，否则聚合。"""
    skills = root / "skills"
    mds = sorted(skills.glob("*/README.md")) + sorted(skills.glob("*/SKILL.md"))
    for md in mds:
        rel = md.relative_to(root).as_posix()
        lines = _lines(md)
        claims: list[tuple[int, int]] = []
        for i, ln in enumerate(lines, 1):
            if "测试" not in ln:
                continue
            for pat in (R4_TESTED_RE, R4_PAREN_RE, R4_REVERSED_RE):
                claims += [(i, int(m.group(1))) for m in pat.finditer(ln)]
        if not claims:
            continue

        # 对应关系：陈述行 markdown 链接指向的 test_*.py 优先（arch-guard
        # 「（53 条）」点名单文件的口径）；点不名则聚合技能全部 test_*.py
        named: list[Path] = []
        for i, _ in claims:
            for target in re.findall(r"\]\(([^)\s]+\.py)\)", lines[i - 1]):
                p = (md.parent / target).resolve()
                if p.is_file() and p.name.startswith("test_"):
                    named.append(p)
        scope = sorted(set(named)) if named else sorted(md.parent.rglob("test_*.py"))
        if not scope:
            for i, n in claims:
                g.info(f"{rel}:{i}",
                       f"R4 陈述 测试 {n} 但技能目录内未找到 test_*.py（跳过）")
            continue
        count = sum(_count_def_test(p) for p in scope)
        scope_desc = ", ".join(p.name for p in scope)
        for i, n in sorted(set(claims)):
            if n != count:
                g.fail(f"{rel}:{i}",
                       f"R4 测试数 陈述 {n} vs 实际 {count}（{scope_desc}）")


def rule_r5(root: Path, g: Gate) -> None:
    """R5 交叉引用防复发：两条已踩坑断言。"""
    for rel in ("skills/impact-guard/SKILL.md", "skills/impact-guard/README.md"):
        p = root / rel
        if not p.is_file():
            continue
        for i, ln in enumerate(_lines(p), 1):
            if R5_REUSE_RE.search(ln):
                g.fail(f"{rel}:{i}",
                       "R5 禁用表述「复用 arch-guard」（实际依赖经 doc-gen，防复发）")
            if "复用来源" in ln:
                m = re.search(r"\]\(([^)\s]+)\)", ln)
                target = m[1] if m else None
                if target is None:
                    bk = re.search(r"`([^`\s]+)`", ln)
                    if bk and ("/" in bk[1] or bk[1].endswith(".py")):
                        target = bk[1]
                if target is None:
                    g.info(f"{rel}:{i}",
                           "R5 复用来源行未解析出路径（口径变更请同步本门规则）")
                elif not (p.parent / target).resolve().exists():
                    g.fail(f"{rel}:{i}",
                           f"R5 复用来源指向不存在路径 {target}")
                elif "doc-gen" not in target:
                    g.fail(f"{rel}:{i}",
                           f"R5 复用来源须指向 doc-gen 路径（实际 {target}）")

    for i, ln in enumerate(_lines(root / ".factory" / "README.md"), 1):
        if R5_CHECKOUT_RE.search(ln):
            g.fail(f".factory/README.md:{i}",
                   "R5 禁用表述「git checkout -b factory/issue」（实际为 worktree add -B）")


def rule_r6(root: Path, g: Gate) -> None:
    """R6 平台清单覆盖：opencode instructions ⊇ 技能 ∪ steering 顶层。"""
    oc = root / ".opencode" / "opencode.json"
    if not oc.is_file():
        return  # 未装 opencode 适配即无枚举面（其余平台为目录级声明）
    skills = root / "skills"
    required = {f"skills/{d.name}/SKILL.md" for d in skills.iterdir()
                if d.is_dir() and (d / "SKILL.md").is_file()}
    required |= {f"steering/{p.name}" for p in (root / "steering").glob("*.md")}
    text = oc.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        g.fail(".opencode/opencode.json:1", f"R6 opencode.json 解析失败（{e}）")
        return
    entries = data.get("instructions") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        g.fail(".opencode/opencode.json:1", "R6 opencode.json 缺 instructions 数组")
        return
    key = re.search(r'(?m)^\s*"instructions"', text)
    line = text[:key.start()].count("\n") + 1 if key else 1
    for rel in sorted(required - {e for e in entries if isinstance(e, str)}):
        g.fail(f".opencode/opencode.json:{line}",
               f"R6 instructions 缺 {rel}（须 ⊇ skills/*/SKILL.md ∪ steering 顶层 *.md）")


def _steering_topic(path: Path) -> str | None:
    """steering 规范 frontmatter title → 主题词（去「规范/标准」尾缀）。

    frontmatter 解析口径与 hooks/load-steering.sh 对齐（startswith('---')）。
    无 title 返回 None（调用方跳过该文件）。
    """
    content = path.read_text(encoding="utf-8")
    title = None
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            if m := re.search(r"(?m)^title:\s*(.+)$", content[3:end]):
                title = m[1].strip()
    return re.sub(r"(规范|标准)$", "", title) if title else None


def rule_r7(root: Path, g: Gate) -> None:
    """R7 枚举完整性：三处人工维护清单各自 ⊇ 实际集合。"""
    steering = sorted((root / "steering").glob("*.md"))
    top = [p.name for p in steering]

    # a. CONTRIBUTING.md 目录结构树（``` 围栏）中的 steering 文件
    contributing = root / "CONTRIBUTING.md"
    if contributing.is_file():
        tree: tuple[int, list[str]] | None = None
        for seg_start, seg in _fence_blocks(_lines(contributing)):
            for j, ln in enumerate(seg):
                stem = re.sub(r"^[│├└─\s]+", "", ln.split("#")[0]).strip().rstrip("/")
                if stem == "steering":
                    tree = (seg_start + j, seg)
                    break
            if tree:
                break
        if tree is None:
            if top:
                g.fail("CONTRIBUTING.md:1",
                       f"R7a 结构树未找到 steering 区块（{len(top)} 个顶层规范未被覆盖）")
        else:
            body = "\n".join(tree[1])
            for name in top:
                if name not in body:
                    g.fail(f"CONTRIBUTING.md:{tree[0]}",
                           f"R7a 目录树缺 steering 顶层文件 {name}")

    # b. AGENTS.md / CLAUDE.md「通用设计规范」行枚举 ⊇ 各规范主题
    for rel in ("AGENTS.md", "CLAUDE.md"):
        p = root / rel
        if not p.is_file():
            continue
        hit = False
        for i, ln in enumerate(_lines(p), 1):
            if "通用设计规范" not in ln:
                continue
            hit = True
            if "等" in ln:
                # 「等」明示枚举非穷尽，硬对齐必误报 → 该行不查
                continue
            # 覆盖口径：枚举 token（「——」后按 、/，切分）与主题互为包含，
            # 容忍「API 设计」对「Open API 设计」的前后缀措辞差
            tokens = [t.strip(" `*（）()。：:")
                      for t in re.split("[、，]", re.split("——", ln)[-1])]
            for sp in steering:
                topic = _steering_topic(sp)
                if not topic:
                    continue
                if not any(len(t) >= 2 and (t in topic or topic in t)
                           for t in tokens):
                    g.fail(f"{rel}:{i}",
                           f"R7b 枚举未提及主题「{topic}」（对应 steering/{sp.name}）")
        if not hit and steering:
            g.fail(f"{rel}:1", "R7b 未找到「通用设计规范」行")

    # c. hooks/load-steering.sh「审查类任务可使用」清单 ⊇ 全部 *-guard 技能
    hook = root / "hooks" / "load-steering.sh"
    if hook.is_file():
        guards = sorted(d.name for d in (root / "skills").iterdir()
                        if d.is_dir() and d.name.endswith("-guard")
                        and (d / "SKILL.md").is_file())
        hit = False
        for i, ln in enumerate(_lines(hook), 1):
            if "审查类任务可使用" not in ln:
                continue
            hit = True
            listed = set(re.findall(r"/([A-Za-z0-9-]+-guard)\b", ln))
            for name in guards:
                if name not in listed:
                    g.fail(f"hooks/load-steering.sh:{i}",
                           f"R7c 审查技能清单缺 /{name}（须含全部 *-guard 技能）")
        if not hit and guards:
            g.fail("hooks/load-steering.sh:1", "R7c 未找到「审查类任务可使用」清单行")


def rule_r8(root: Path, g: Gate) -> None:
    """R8 分发闸枚举覆盖：README 并发注记 ⊇ lefthook pre-push commands。"""
    yml = root / "tools" / "git" / "lefthook.yml"
    readme = root / "tools" / "git" / "README.md"
    if not yml.is_file() or not readme.is_file():
        return  # 无分发面即无枚举漂移面
    # 事实侧：pre-push 段内 4 空格缩进键（commands: 2 缩进、run: 6 缩进均不匹配）
    commands: list[str] = []
    in_pre_push = False
    for ln in _lines(yml):
        if ln.lstrip().startswith("#"):
            continue
        if re.match(r"^\S", ln):
            if in_pre_push:
                break  # 下一个顶层段，pre-push 结束
            in_pre_push = ln.startswith("pre-push:")
            continue
        if in_pre_push:
            if m := re.match(r"^    ([A-Za-z0-9][\w-]*):", ln):
                commands.append(m[1])
    if not commands:
        return  # 无 pre-push commands 即无注记枚举面
    # 陈述侧：注记行切 token 与命令名取交集（只查 ⊇，多余措辞不罚）
    note_line: int | None = None
    note_text = ""
    for i, ln in enumerate(_lines(readme), 1):
        if "pre-push 并发注记" in ln:
            note_line, note_text = i, ln
            break
    if note_line is None:
        g.fail("tools/git/README.md:1",
               f"R8 pre-push 并发注记行未找到（{len(set(commands))} 个 commands 未被枚举覆盖）")
        return
    listed = set(R8_SPLIT_RE.split(note_text)) & set(commands)
    for name in sorted(set(commands)):
        if name not in listed:
            g.fail(f"tools/git/README.md:{note_line}",
                   f"R8 并发注记缺 pre-push command {name}（lefthook.yml pre-push 共 {len(set(commands))} 闸）")


def _source_line(root: Path, where: str) -> str | None:
    """证据行 'path:line' → 源行文本（行级豁免标记判断用）。"""
    path_part, _, line_part = where.rpartition(":")
    if not path_part or not line_part.isdigit():
        return None
    p = root / path_part
    if not p.is_file():
        return None
    ln = _lines(p)
    idx = int(line_part) - 1
    return ln[idx] if 0 <= idx < len(ln) else None


def main() -> int:
    ap = argparse.ArgumentParser(description="实现↔文档一致性门禁（R1-R8）")
    ap.add_argument("root", nargs="?", default=".",
                    help="仓库根（默认当前目录）")
    ap.add_argument("--allow", action="append", default=[], metavar="REGEX",
                    help="豁免：正则命中证据行即跳过（可重复）")
    args = ap.parse_args()
    if not args.root.strip():
        # 显式空 root 会 resolve 成 cwd、静默扫错仓（夹具事故形态）——拒判
        print("doc-freshness: 结构性错误 root 为空串", file=sys.stderr)
        return 2
    root = Path(args.root).resolve()

    if missing := [
        s
        for s in (".factory", ".factory/README.md", "README.md", "skills")
        if not (root / s).exists()
    ]:
        print(f"doc-freshness: 结构性错误 {root} 缺 {'、'.join(missing)}", file=sys.stderr)
        return 2
    try:
        allows = [re.compile(a) for a in args.allow]
    except re.error as e:
        print(f"doc-freshness: --allow 正则非法: {e}", file=sys.stderr)
        return 2

    g = Gate()
    rule_r1(root, g)
    rule_r2(root, g)
    rule_r3(root, g)
    rule_r4(root, g)
    rule_r5(root, g)
    rule_r6(root, g)
    rule_r7(root, g)
    rule_r8(root, g)

    fails: list[str] = []
    infos: list[str] = []
    waived = 0
    for level, where, msg in g.findings:
        src = _source_line(root, where)
        if src is not None and ALLOW_MARK in src:
            waived += 1
            continue
        rendered = f"[{level}] {where} → {msg}"
        if any(r.search(rendered) for r in allows):
            waived += 1
            continue
        (fails if level == "FAIL" else infos).append(rendered)

    for ln in fails + infos:
        print(ln)
    print(f"doc-freshness: {len(fails)} 项漂移 / {len(infos)} 项 INFO / {waived} 项豁免")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
