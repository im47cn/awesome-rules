"""evo_proposal 单测：round-trip、路径逃逸、锚点应用、护栏、状态流转、verdict。"""
import json

import pytest

import evo_proposal as PR


def make_lesson(**kw):
    base = dict(type="correction", evidence="用户说'不要用 select *'",
                target_file="steering/demo-spec.md", confidence="Medium",
                reason="补充条款", change=PR.Change(
                    action="append_under", heading="## 强制条款",
                    new_text="- 禁止 `select *`，明确列名"))
    base.update(kw)
    return PR.Lesson(**base)


def make_repo(tmp_path):
    (tmp_path / "steering").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    spec = tmp_path / "steering" / "demo-spec.md"
    spec.write_text("---\ntitle: t\n---\n# 测试规范\n\n## 强制条款\n\n1. 既有条款\n\n## 推荐\n\n- r1\n",
                    encoding="utf-8")
    (tmp_path / "skills" / "demo" / "SKILL.md").write_text(
        "# Demo\n\n## 工作流\n\n- s1\n", encoding="utf-8")
    return tmp_path


def make_proposal(tmp_path, lessons=None, pid="20260818-000000-cc-abcd1234"):
    return PR.Proposal(
        id=pid, source_agent="cc", source_session="s-1",
        source_path="/tmp/s-1.jsonl", created="2026-08-18T00:00:00+00:00",
        lessons=lessons or [make_lesson()])


# ── 序列化 round-trip ──────────────────────────────────────────────────────

def test_write_load_roundtrip(tmp_path):
    p = make_proposal(tmp_path, lessons=[make_lesson(), make_lesson(confidence="Low")])
    path = PR.write_proposal(p, tmp_path / "pending")
    loaded = PR.load_proposal(path)
    assert loaded.id == p.id and loaded.source_agent == "cc"
    assert len(loaded.lessons) == 2
    ls = loaded.lessons[0]
    assert ls.change.action == "append_under" and ls.change.heading == "## 强制条款"
    assert "select" in ls.change.new_text and "select" in ls.evidence


def _multiline_lesson():
    """issue #81 缺陷形态样本：evidence 含多行原文与围栏代码块。"""
    return make_lesson(
        evidence="用户原话（多行）：\n\n```sql\nselect *\nfrom t_order\n```\n要求列名",
        change=PR.Change(action="append_under", heading="## 强制条款",
                         new_text="- 禁止 `select *`\n- 必须显式列出列名"))


def test_write_multiline_lesson_strict_roundtrip(tmp_path):
    """多行 evidence/new_text（含围栏）：机读块严格 JSON 可解析且逐字符保真。

    回归锁（issue #81 判据 1）：json.dumps 转义链被后处理破坏（\n 裸化）时，
    本测试以 strict json.loads 的 Invalid control character 变红。
    """
    ls = _multiline_lesson()
    path = PR.write_proposal(make_proposal(tmp_path, lessons=[ls]), tmp_path / "pending")
    for f in (path, path.parent / f"{path.stem}.orig"):
        m = PR._JSON_BLOCK_RE.search(f.read_text(encoding="utf-8"))
        assert m, f"{f.name}: 机读 JSON 块缺失"
        json.loads(m.group(1))                       # strict 默认：裸换行即抛
    p = PR.load_proposal(path)
    assert p.lessons[0].evidence == ls.evidence      # 围栏不截断，含 \n 逐字符相等
    assert p.lessons[0].change.new_text == ls.change.new_text


def _corrupt_machine_block(path):
    """块内首个转义换行 \\n → 裸换行（重现 issue #81 坏件：非法控制字符）。"""
    text = path.read_text(encoding="utf-8")
    m = PR._JSON_BLOCK_RE.search(text)
    assert m, "机读 JSON 块缺失"
    corrupt = text[:m.start()] + m.group(0).replace("\\n", "\n", 1) + text[m.end():]
    path.write_text(corrupt, encoding="utf-8")


def test_load_proposal_flags_corrupt_block(tmp_path):
    """坏机读块：诊断上浮 parse_errors（Tripwire：禁静默降级为空 lessons）。"""
    path = PR.write_proposal(make_proposal(tmp_path, lessons=[_multiline_lesson()]),
                             tmp_path / "pending")
    _corrupt_machine_block(path)
    p = PR.load_proposal(path)
    assert p.parse_errors, "坏块必须留下诊断痕迹"
    assert any("解析失败" in e and "line" in e for e in p.parse_errors)
    with pytest.raises(PR.ApplyError, match="解析失败"):   # 真因直指坏块，非裸『提案无 lesson』
        PR.apply_proposal(p, make_repo(tmp_path))

def test_write_proposal_sanitizes_raw_ctrl_chars(tmp_path):
    """净化层（issue #81 根修）：夹带裸控制字符的 lesson，落盘后机读块 strict 可解析。

    LLM 输出可夹带 \x08/\x0b/\x00 等裸控制字符；无论序列化路径如何漂移，
    生成器最终产物必须 strict 可解析，且 roundtrip 逐字符保真（\\uXXXX 转义
    复原为原值）。
    """
    ls = make_lesson(evidence="a\x08b\x0bc", reason="r\x00尾")
    path = PR.write_proposal(make_proposal(tmp_path, lessons=[ls]), tmp_path / "pending")
    for f in (path, path.parent / f"{path.stem}.orig"):
        m = PR._JSON_BLOCK_RE.search(f.read_text(encoding="utf-8"))
        assert m, f"{f.name}: 机读 JSON 块缺失"
        loaded = json.loads(m.group(1))                  # strict 默认：裸 <0x20 即抛
        assert loaded["lessons"][0]["evidence"] == "a\x08b\x0bc"
        assert loaded["lessons"][0]["reason"] == "r\x00尾"


def test_write_proposal_sanitizes_raw_tab(tmp_path):
    """净化层（issue #81）：裸 tab（\\x09）是 <0x20 唯一漏网可救字符——必须转义。

    dumps 结构空白用空格+换行，裸 tab 只可能出现在字符串值内（外部破坏
    \\t/\\u0009 转义序列所致），转义为 \\u0009 合法且 roundtrip 保真；
    且产物文本中不得残留裸 tab 字节。
    """
    ls = make_lesson(evidence="a\tb", reason="r\t尾")
    path = PR.write_proposal(make_proposal(tmp_path, lessons=[ls]), tmp_path / "pending")
    for f in (path, path.parent / f"{path.stem}.orig"):
        text = f.read_text(encoding="utf-8")
        m = PR._JSON_BLOCK_RE.search(text)
        assert "\t" not in m.group(1), f"{f.name}: 机读块内裸 tab 未防御转义"
        loaded = json.loads(m.group(1))                  # strict：裸 tab 即抛
        assert loaded["lessons"][0]["evidence"] == "a\tb"
        assert loaded["lessons"][0]["reason"] == "r\t尾"

def test_write_proposal_keeps_structural_newlines(tmp_path):
    """净化层（issue #81）：indent=1 的结构换行（真实 \\n）不得被防御转义误伤。

    LF/CR 是 JSON 合法结构空白，_CTRL_CHARS_RE 显式排除——若改成 [\\x00-\\x1f]
    全量覆盖，结构换行转义为 \\u000a 将破坏可解析性，正常产物全断。此测试
    钉死该不变量：块内真实换行保留且 strict 可解析。
    """
    path = PR.write_proposal(make_proposal(tmp_path, lessons=[_multiline_lesson()]),
                             tmp_path / "pending")
    for f in (path, path.parent / f"{path.stem}.orig"):
        text = f.read_text(encoding="utf-8")
        m = PR._JSON_BLOCK_RE.search(text)
        assert "\n" in m.group(1), f"{f.name}: 结构换行缺失（indent 形态漂移）"
        assert json.loads(m.group(1))["lessons"], f"{f.name}: strict 解析失败"


def test_write_proposal_gate_rejects_corrupt_block(tmp_path, monkeypatch):
    """净化层闸门（issue #81 根修）：序列化产物非 strict 可解析 → 落盘前 fail-fast。

    负控制：_machine_block 被替换为含裸控制字符的坏块时，write_proposal 必须
    在写出前抛 ApplyError——坏件永不静默进入 pending/归档。
    """
    p = make_proposal(tmp_path, lessons=[_multiline_lesson()])
    monkeypatch.setattr(PR, "_machine_block",
                        lambda payload: '```json\n{"lessons": [{"evidence": "\x08"}]}\n```')
    with pytest.raises(PR.ApplyError, match="机读块非严格可解析"):
        PR.write_proposal(p, tmp_path / "pending")


def test_finalize_review_corrupt_block_clean_error(tmp_path):
    """坏机读块 finalize：收敛为 ApplyError 直指解析失败（原裸抛 JSONDecodeError）。"""
    path = PR.write_proposal(
        make_proposal(tmp_path, lessons=[_multiline_lesson()], pid="20260821-000001-cc-corrupt1"),
        tmp_path / "pending")
    _corrupt_machine_block(path)
    with pytest.raises(PR.ApplyError, match="解析失败"):
        PR.finalize_review(path, [], rejected=True)


def test_load_proposal_flags_missing_lessons_key(tmp_path):
    """dict 机读块缺 lessons 键（plan 任务 2 声明分支）：诊断入 parse_errors。"""
    path = PR.write_proposal(make_proposal(tmp_path), tmp_path / "pending")
    text = path.read_text(encoding="utf-8")
    m = PR._JSON_BLOCK_RE.search(text)
    path.write_text(text[:m.start()] + "```json\n{\"no_lessons\": true}\n```"
                    + text[m.end():], encoding="utf-8")
    p = PR.load_proposal(path)
    assert any("缺 lessons 字段" in e for e in p.parse_errors)
    with pytest.raises(PR.ApplyError, match="缺 lessons 字段"):
        PR.apply_proposal(p, make_repo(tmp_path))


# ── lesson_id 与 supersedes ─────────────────────────────────────────────────

def test_derive_lesson_id_deterministic():
    import re
    ls = make_lesson()
    a = PR.derive_lesson_id(ls)
    assert a == PR.derive_lesson_id(make_lesson())            # 内容相同 → ID 相同
    assert re.fullmatch(r"L-[0-9A-F]{8}", a)
    other = make_lesson(change=PR.Change(
        action="append_under", heading="## 强制条款", new_text="- 不同条款"))
    assert PR.derive_lesson_id(other) != a                    # 内容变化 → ID 变化


def test_roundtrip_lesson_id_and_supersedes(tmp_path):
    p = make_proposal(tmp_path, lessons=[make_lesson(supersedes="L-OLDOLD01")])
    path = PR.write_proposal(p, tmp_path / "pending")
    loaded = PR.load_proposal(path)
    ls = loaded.lessons[0]
    assert ls.lesson_id == PR.derive_lesson_id(make_lesson())  # write 时自动派生并持久化
    assert ls.supersedes == "L-OLDOLD01"
    content = path.read_text(encoding="utf-8")
    assert ls.lesson_id in content and "L-OLDOLD01" in content  # 渲染层可追溯
    # 旧提案（无 lesson_id 字段）加载时按内容补派生
    import json
    payload = json.loads(PR._JSON_BLOCK_RE.search(content).group(1))
    payload["lessons"][0].pop("lesson_id")
    path.write_text(content.replace(
        PR._JSON_BLOCK_RE.search(content).group(0),
        "```json\n" + json.dumps(payload, ensure_ascii=False, indent=1) + "\n```"),
        encoding="utf-8")
    assert PR.load_proposal(path).lessons[0].lesson_id == ls.lesson_id


def test_list_proposals(tmp_path):
    PR.write_proposal(make_proposal(tmp_path), tmp_path / "pending")
    PR.write_proposal(make_proposal(tmp_path, pid="20260818-000001-cc-ffff5678"),
                      tmp_path / "pending")
    assert len(PR.list_proposals(tmp_path / "pending")) == 2
    assert PR.list_proposals(tmp_path / "absent") == []


# ── 路径逃逸 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("target", [
    "../../etc/passwd.md", "docs/design/x.md", "steering/x.txt", "steering/absent.md",
])
def test_validate_target_rejects(tmp_path, target):
    make_repo(tmp_path)
    with pytest.raises(PR.ApplyError):
        PR.validate_target(target, tmp_path)


def test_validate_target_ok(tmp_path):
    make_repo(tmp_path)
    assert PR.validate_target("steering/demo-spec.md", tmp_path).is_file()


# ── 应用 ────────────────────────────────────────────────────────────────────

def test_apply_append_under(tmp_path):
    repo = make_repo(tmp_path)
    p = make_proposal(tmp_path)
    report = PR.apply_proposal(p, repo)
    content = (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    assert "- 禁止 `select *`，明确列名" in content
    # 追加在标题行之后、既有条款之前不破坏结构
    assert content.index("## 强制条款") < content.index("禁止") < content.index("既有条款")
    assert len(report) == 1


def test_apply_append_under_table_aware(tmp_path):
    """表格感知追加：标题下是表格时插到末行之后，不破坏表头。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# 索引\n\n## 技能（skills/）\n\n| 技能 | 说明 |\n| --- | --- |\n"
        "| [a](skills/a/README.md) | A |\n| [b](skills/b/README.md) | B |\n\n## 其他\n\n文字\n",
        encoding="utf-8")
    p = make_proposal(tmp_path, lessons=[make_lesson(
        target_file="README.md", change=PR.Change(
            action="append_under", heading="## 技能（skills/）",
            new_text="| [c](skills/c/README.md) | C |"))])
    PR.apply_proposal(p, repo)
    content = (repo / "README.md").read_text(encoding="utf-8")
    assert "| [b](skills/b/README.md) | B |\n| [c](skills/c/README.md) | C |\n" in content
    assert content.index("| [c]") > content.index("| [b]")           # 在表格末行后
    assert content.index("| [c]") < content.index("## 其他")         # 未越出该节
    # 非表格标题行为不变（原 test_apply_append_under 覆盖）


def test_validate_target_root_files(tmp_path):
    make_repo(tmp_path)
    (tmp_path / "README.md").write_text("# r\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# c\n", encoding="utf-8")
    assert PR.validate_target("README.md", tmp_path).is_file()
    assert PR.validate_target("CLAUDE.md", tmp_path).is_file()
    with pytest.raises(PR.ApplyError):
        PR.validate_target("CONTRIBUTING.md", tmp_path)   # 根级白名单外
    with pytest.raises(PR.ApplyError):
        PR.validate_target("docs/design/x.md", tmp_path)
    repo = make_repo(tmp_path)
    p = make_proposal(tmp_path, lessons=[make_lesson(change=PR.Change(
        action="append_end", new_text="- 末尾新条款"))])
    PR.apply_proposal(p, repo)
    content = (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    assert content.rstrip().endswith("- 末尾新条款")


def test_apply_missing_heading_fails_atomically(tmp_path):
    repo = make_repo(tmp_path)
    before = (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    lessons = [make_lesson(), make_lesson(change=PR.Change(
        action="append_under", heading="## 不存在", new_text="- x"))]
    p = make_proposal(tmp_path, lessons=lessons)
    with pytest.raises(PR.ApplyError, match="找不到标题锚点"):
        PR.apply_proposal(p, repo)
    assert (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8") == before  # 不盲写


def test_apply_dry_run_no_write(tmp_path):
    repo = make_repo(tmp_path)
    before = (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    PR.apply_proposal(make_proposal(tmp_path), repo, dry_run=True)
    assert (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8") == before


# ── 护栏 ────────────────────────────────────────────────────────────────────

def test_warning_mandatory_and_low(tmp_path):
    p = make_proposal(tmp_path, lessons=[
        make_lesson(change=PR.Change(action="append_end", new_text="1.【强制】新条款")),
        make_lesson(confidence="Low", change=PR.Change(action="append_end", new_text="- y")),
    ])
    ws = p.warnings()
    assert any("【强制】" in w for w in ws) and any("Low" in w for w in ws)
    with pytest.raises(PR.ApplyError, match="--force"):
        PR.apply_proposal(p, make_repo(tmp_path))
    PR.apply_proposal(p, make_repo(tmp_path), force=True)   # force 后可应用


# ── 重复沉淀与 supersedes 校验 ──────────────────────────────────────────────

def _archive(tmp_path, proposal, applied_dir=None):
    """写入并归档一份提案（内容不落目标文件，仅建归档索引）。"""
    applied_dir = applied_dir or tmp_path / "applied"
    path = PR.write_proposal(proposal, tmp_path / "pending")
    PR.move_proposal(path, applied_dir, {"status": "applied", "applied_at": "T"})
    return applied_dir, list(applied_dir.glob("*.md"))[0]


def test_apply_duplicate_in_archive_warns(tmp_path):
    """同 lesson_id 已在 applied 归档 → 护栏警告（--force 越过）。"""
    repo = make_repo(tmp_path)
    applied, _ = _archive(tmp_path, make_proposal(tmp_path))
    p2 = make_proposal(tmp_path, pid="20260818-000001-cc-ffff5678")  # 同内容 lesson
    with pytest.raises(PR.ApplyError, match="重复沉淀"):
        PR.apply_proposal(p2, repo, applied_dir=applied)
    PR.apply_proposal(p2, repo, applied_dir=applied, force=True)     # force 后可应用


def test_apply_verbatim_dup_warns(tmp_path):
    """new_text 已逐字存在于目标文件 → 护栏警告。"""
    repo = make_repo(tmp_path)
    spec = repo / "steering" / "demo-spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n- 禁止 `select *`，明确列名\n",
                    encoding="utf-8")
    with pytest.raises(PR.ApplyError, match="逐字存在"):
        PR.apply_proposal(make_proposal(tmp_path), repo)


def test_check_idempotent_boundaries():
    """边界钉死：>= 含等、> 实际比率即失、无关内容 None、长中文段落不抖动。"""
    clause = "禁止使用 select 星号，查询必须显式列出全部字段名，避免列序漂移"
    content = f"# 标题\n\n引言段落。\n\n- {clause}\n\n## 其他\n\n- 其他条款\n"
    variant = clause.replace("全部", "所有")
    hit = PR.check_idempotent(variant, content, 0.8)
    assert hit == (3, hit[1]) and hit[1] > 0.85        # 命中第三段（1-based 原序）
    r = hit[1]
    assert PR.check_idempotent(variant, content, r)[1] == r      # 阈值=实际比率 → 命中（>= 含等）
    assert PR.check_idempotent(variant, content, r + 0.01) is None
    assert PR.check_idempotent("推荐使用参数化查询并绑定变量", content, 0.8) is None
    # autojunk 回归：200+ 字中文段落换皮变体——autojunk=True 时比率坍缩（实测 0.07）
    long_para = ("令牌探测顺序应从环境变量开始逐级回退到本地配置文件，"
                 "并记录每次探测的结果与时间戳供后续审计复核使用。") * 4
    long_variant = long_para.replace("逐级回退", "依次回退").replace("后续审计", "事后审计")
    assert PR.check_idempotent(long_variant, f"# 标题\n\n{long_para}\n", 0.8)[1] > 0.9


def test_apply_semantic_dup_requires_force(tmp_path):
    """new_text 与既有段落语义相似（换皮重提）→ 护栏拦截，--force 越过。"""
    repo = make_repo(tmp_path)
    spec = repo / "steering" / "demo-spec.md"
    para = "禁止使用 select 星号，查询必须显式列出全部字段名，避免列序漂移"
    spec.write_text(spec.read_text(encoding="utf-8") + f"\n- {para}\n", encoding="utf-8")
    variant = para.replace("全部", "所有")
    p = make_proposal(tmp_path, lessons=[make_lesson(change=PR.Change(
        action="append_end", new_text=f"- {variant}"))])
    with pytest.raises(PR.ApplyError, match="语义重复") as ei:
        PR.apply_proposal(p, repo)
    assert "0.9" in str(ei.value)                      # 相似度数值进拦截消息
    PR.apply_proposal(p, repo, force=True)             # force 后通过
    assert variant in spec.read_text(encoding="utf-8")


def test_apply_distinct_text_passes(tmp_path):
    """全新条款与既有段落无相似 → 无任何 guard 直接应用（防过度拦截负例）。"""
    repo = make_repo(tmp_path)
    p = make_proposal(tmp_path, lessons=[make_lesson(change=PR.Change(
        action="append_end", new_text="- 推荐使用参数化查询并绑定变量避免拼接"))])
    assert len(PR.apply_proposal(p, repo)) == 1
    assert "参数化查询" in (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")


_ALI_TOKEN_PARA = ("- 令牌探测顺序：优先检查环境变量 `YUNXIAO_ACCESS_TOKEN`（用户可能在其他终端窗口 export，"
                   "非交互 shell 中不可见），再查 `~/.yunxiao_token`、`~/.aliyun/` 等本地配置；"
                   "历史会话的「无令牌」结论不可复用，每次操作前须重新确认。")
"""实证样本（issue #63）：alibabacloud-devops SKILL.md L13 令牌探测段落，冻结为常量防内容演化脆断。"""


def test_apply_real_regress_alibabacloud_dup(tmp_path):
    """实证回归（issue #63）：同段落 ~90% 换皮变体重提 → 被幂等检查拦截。"""
    repo = make_repo(tmp_path)
    ali = repo / "skills" / "alibabacloud-devops" / "SKILL.md"
    ali.parent.mkdir(parents=True)
    ali.write_text(f"# Alibaba DevOps\n\n## 前置：访问令牌\n\n{_ALI_TOKEN_PARA}\n",
                   encoding="utf-8")
    variant = _ALI_TOKEN_PARA.replace("优先检查", "首先检查").replace("重新确认", "再次确认")
    p = make_proposal(tmp_path, lessons=[make_lesson(
        target_file="skills/alibabacloud-devops/SKILL.md",
        change=PR.Change(action="append_end", new_text=variant))])
    with pytest.raises(PR.ApplyError, match="语义重复"):
        PR.apply_proposal(p, repo)


def test_knowledge_type_roundtrip(tmp_path):
    """knowledge_type：write→load 保真；旧式 JSON 无该键 → 默认 pattern。"""
    p = make_proposal(tmp_path, lessons=[make_lesson(knowledge_type="instance")])
    loaded = PR.load_proposal(PR.write_proposal(p, tmp_path / "pending"))
    assert loaded.lessons[0].knowledge_type == "instance"
    legacy = tmp_path / "legacy.md"
    legacy.write_text(
        "# 旧式提案\n\n```json\n" + json.dumps({"lessons": [{
            "type": "success", "evidence": "e", "target_file": "steering/demo-spec.md",
            "confidence": "High", "reason": "r",
            "change": {"action": "append_end", "new_text": "- 旧式条款"}}]},
            ensure_ascii=False) + "\n```\n", encoding="utf-8")
    assert PR.load_proposal(legacy).lessons[0].knowledge_type == "pattern"


def test_lesson_id_excludes_knowledge_type():
    """不变量：knowledge_type 不进哈希——归档索引/supersedes 链/GEPA 标注依赖 ID 稳定。"""
    a = make_lesson(knowledge_type="pattern")
    b = make_lesson(knowledge_type="instance")
    assert PR.derive_lesson_id(a) == PR.derive_lesson_id(b)


def test_apply_instance_guarded(tmp_path):
    """instance 类知识 → 护栏拦截（消息指向代码/ADR），--force 越过。"""
    repo = make_repo(tmp_path)
    p = make_proposal(tmp_path, lessons=[make_lesson(
        knowledge_type="instance",
        change=PR.Change(action="append_end", new_text="- 云效 fieldId 101586 是选项型字段"))])
    with pytest.raises(PR.ApplyError, match="instance") as ei:
        PR.apply_proposal(p, repo)
    msg = str(ei.value)
    assert "代码" in msg and "ADR" in msg
    PR.apply_proposal(p, repo, force=True)             # force 后通过
    assert "101586" in (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")


def test_supersedes_validation(tmp_path):
    repo = make_repo(tmp_path)
    applied, archived = _archive(tmp_path, make_proposal(tmp_path))
    old_id = PR.load_proposal(archived).lessons[0].lesson_id

    # 引用不存在的 lesson_id → 硬错，force 不可越过
    bad = make_proposal(tmp_path, pid="20260818-000002-cc-bad00001",
                        lessons=[make_lesson(supersedes="L-DEADBEEF",
                                             change=PR.Change(action="append_end", new_text="- 新"))])
    with pytest.raises(PR.ApplyError, match="不在已应用归档"):
        PR.apply_proposal(bad, repo, applied_dir=applied, force=True)

    # 自引用 → 硬错
    self_ref = make_lesson(change=PR.Change(action="append_end", new_text="- 自指"))
    self_ref.supersedes = PR.derive_lesson_id(self_ref)
    with pytest.raises(PR.ApplyError, match="指向自身"):
        PR.apply_proposal(make_proposal(tmp_path, pid="20260818-000003-cc-self0001",
                                        lessons=[self_ref]), repo, applied_dir=applied)

    # 合法引用（新内容修正旧 lesson）→ 正常应用
    ok = make_lesson(supersedes=old_id,
                     change=PR.Change(action="append_end", new_text="- 修正后的条款"))
    report = PR.apply_proposal(make_proposal(tmp_path, pid="20260818-000004-cc-okay0001",
                                             lessons=[ok]), repo, applied_dir=applied)
    assert len(report) == 1


# ── evidence 核验 ───────────────────────────────────────────────────────────

def test_verify_evidence(tmp_path):
    p = make_proposal(tmp_path, lessons=[
        make_lesson(),                                # evidence 含于语料
        make_lesson(evidence="会话里根本没有这句话"),   # 不含
        make_lesson(evidence=""),                     # 空证据按未命中处理
    ])
    corpus = "前面有用户消息 用户说'不要用 select *' 后面还有别的内容"
    assert PR.verify_evidence(p, corpus) == [(1, "hit"), (2, "miss"), (3, "miss")]
    assert PR.verify_evidence(p, "") == [(1, "no_corpus"), (2, "no_corpus"),
                                         (3, "no_corpus")]
    # 空白不敏感：换行/缩进不影响命中
    assert PR.verify_evidence(p, "用户说'不要用\n  select *'")[0] == (1, "hit")
    # 引号字形不敏感：evidence 直引号 vs 语料弯引号（实测 2026-08-19 提案回归）
    curly = make_lesson(evidence='把"恰一次"松绑为可兑现语义',
                        change=PR.Change(action="append_end", new_text="- q"))
    p2 = make_proposal(tmp_path, lessons=[curly])
    assert PR.verify_evidence(p2, '把“恰一次”松绑为可兑现语义') == [(1, "hit")]


# ── 状态流转 ────────────────────────────────────────────────────────────────

def test_move_proposal_adds_fm(tmp_path):
    path = PR.write_proposal(make_proposal(tmp_path), tmp_path / "pending")
    dest = PR.move_proposal(path, tmp_path / "applied",
                            {"status": "applied", "applied_at": "T"})
    assert dest.exists() and dest.parent.name == "applied"
    assert not path.exists()
    content = dest.read_text(encoding="utf-8")
    assert "applied_at: T" in content
    # 归档后仍可加载（frontmatter 注入未破坏 JSON 块）
    assert len(PR.load_proposal(dest).lessons) == 1


# ── 结构化 verdict（借鉴 harness-anything verdict 语义）──────────────────────

def test_validate_codes():
    PR.validate_codes(["dup_superset", "other:自定义理由"])     # 合法枚举 + 逃生舱
    with pytest.raises(PR.ApplyError, match="未知语义码"):
        PR.validate_codes(["not_a_code"])


def test_write_proposal_orig_snapshot(tmp_path):
    PR.write_proposal(make_proposal(tmp_path), tmp_path / "pending")
    orig = tmp_path / "pending" / "20260818-000000-cc-abcd1234.orig"
    assert orig.is_file() and orig.suffix == ".orig"           # 无 .md 后缀
    assert orig.read_text(encoding="utf-8") == \
        (tmp_path / "pending" / "20260818-000000-cc-abcd1234.md").read_text(encoding="utf-8")
    # glob 语义：*.md 不应扫到快照
    assert len(list((tmp_path / "pending").glob("*.md"))) == 1


def _mk3(tmp_path, pid="20260821-000000-cc-verdict1"):
    """三 lesson 提案：1 保持、2 裁剪内容、3 修锚点。"""
    lessons = [
        make_lesson(change=PR.Change(action="append_end", new_text="- 保持")),
        make_lesson(change=PR.Change(action="append_end", new_text="- 原始长内容，将被裁剪\n- 第二条冗余")),
        make_lesson(change=PR.Change(action="append_under", heading="## 旧锚点",
                                     new_text="- 锚点修复")),
    ]
    return PR.write_proposal(make_proposal(tmp_path, lessons=lessons, pid=pid),
                             tmp_path / "pending")


def test_finalize_review_derives_verdicts(tmp_path):
    path = _mk3(tmp_path)
    p = PR.load_proposal(path)
    # review 编辑：lesson2 裁剪（内容变→id 变）、lesson3 补 ##
    p.lessons[1].change.new_text = "- 原始长内容，将被裁剪"
    p.lessons[2].change.heading = "## 新锚点"
    # 直接改写 JSON 块模拟人工编辑（绕过 write_proposal 重建）
    payload = {"lessons": [{
        "type": ls.type, "evidence": ls.evidence, "target_file": ls.target_file,
        "confidence": ls.confidence, "reason": ls.reason,
        "lesson_id": ls.lesson_id, "supersedes": ls.supersedes,
        "change": {"action": ls.change.action, "heading": ls.change.heading,
                   "new_text": ls.change.new_text}} for ls in p.lessons]}
    content = path.read_text(encoding="utf-8")
    m = PR._JSON_BLOCK_RE.search(content)
    path.write_text(content[:m.start()] + "```json\n" + json.dumps(
        payload, ensure_ascii=False, indent=1) + "\n```" + content[m.end():],
        encoding="utf-8")

    code_l2 = PR.load_proposal(path).lessons[1].lesson_id
    PR.finalize_review(path, [f"{code_l2}:content_overlap", "anchor_defect"],
                       rejected=False)
    archived = PR.load_proposal(path)
    vs = [(ls.verdict, ls.verdict_codes) for ls in archived.lessons]
    assert vs[0] == ("applied", ["anchor_defect"])             # 提案级码作用于全部
    assert vs[1] == ("trimmed", ["anchor_defect", "content_overlap"])
    assert vs[2] == ("edited", ["anchor_defect"])
    # fm 投影 + JSON 注入
    text = path.read_text(encoding="utf-8")
    assert "review: applied=1, trimmed=1, edited=1" in text
    assert '"verdict": "trimmed"' in text
    # .orig 保留待归档
    assert (tmp_path / "pending" / "20260821-000000-cc-verdict1.orig").is_file()


def test_finalize_review_removed_and_rejected(tmp_path):
    """原版 4 lesson 被剔 1：剔除者无 verdict 位；整包 reject 全 rejected。"""
    lessons = [make_lesson(change=PR.Change(action="append_end", new_text=f"- l{i}"))
               for i in range(4)]
    pid = "20260821-000001-cc-verdict2"
    path = PR.write_proposal(make_proposal(tmp_path, lessons=lessons, pid=pid),
                             tmp_path / "pending")
    # 人工剔除 lesson 3（index 2）
    p = PR.load_proposal(path)
    kept = [ls for i, ls in enumerate(p.lessons) if i != 2]
    payload = {"lessons": [{
        "type": ls.type, "evidence": ls.evidence, "target_file": ls.target_file,
        "confidence": ls.confidence, "reason": ls.reason,
        "lesson_id": ls.lesson_id, "supersedes": ls.supersedes,
        "change": {"action": ls.change.action, "heading": ls.change.heading,
                   "new_text": ls.change.new_text}} for ls in kept]}
    content = path.read_text(encoding="utf-8")
    m = PR._JSON_BLOCK_RE.search(content)
    path.write_text(content[:m.start()] + "```json\n" + json.dumps(
        payload, ensure_ascii=False, indent=1) + "\n```" + content[m.end():],
        encoding="utf-8")
    PR.finalize_review(path, ["dup_superset"], rejected=False)
    assert [ls.verdict for ls in PR.load_proposal(path).lessons] == \
        ["applied"] * 3                                            # 剔除者不占位

    # 整包 reject：全部 rejected
    path2 = PR.write_proposal(make_proposal(tmp_path, pid="20260821-000002-cc-vf3"),
                              tmp_path / "pending")
    PR.finalize_review(path2, ["low_value"], rejected=True)
    assert [ls.verdict for ls in PR.load_proposal(path2).lessons] == ["rejected"]


def test_archive_orig_moves_snapshot(tmp_path):
    path = PR.write_proposal(make_proposal(tmp_path), tmp_path / "pending")
    orig = tmp_path / "pending" / "20260818-000000-cc-abcd1234.orig"
    dest = PR.archive_orig(path, tmp_path / "applied")
    assert dest == tmp_path / "applied" / "20260818-000000-cc-abcd1234.orig"
    assert dest.is_file() and not orig.exists()
    assert PR.archive_orig(tmp_path / "pending" / "absent.md",
                           tmp_path / "applied") is None       # 无快照容错


def test_verify_evidence_paraphrase(tmp_path):
    """转述拼接：整段未逐字命中，但最长连续命中 ≥ 阈值 → paraphrase（不拦 apply）。"""
    corpus = "用户当时说'不要用 select *，明确列名'并且要求改掉全部查询"
    # 真实片段（连续 ≥16 字）+ 连接词缝合 → 整段不命中但片段命中
    stitched = "用户提到过'不要用 select *，明确列名'所以需要新增禁止条款"
    p = make_proposal(tmp_path, lessons=[
        make_lesson(evidence=stitched),
        make_lesson(evidence="完全编造的引用内容根本不存在于语料"),
    ])
    assert PR.verify_evidence(p, corpus) == [(1, "paraphrase"), (2, "miss")]


def test_longest_match_len_threshold():
    """阈值边界：恰 16 字降级、15 字仍 miss。"""
    from evo_proposal import _norm_quote, _longest_match_len
    frag = "一二三四五六七八九十123456"          # 16 字
    corpus = f"前缀{frag}后缀"
    quote = f"改写开头{frag}改写结尾"
    assert _longest_match_len(_norm_quote(quote), _norm_quote(corpus)) >= 16
    frag15 = frag[:-1]
    quote15 = f"改写开头{frag15}改写结尾"
    assert _longest_match_len(_norm_quote(quote15), _norm_quote(corpus)) == 15


def test_apply_append_under_h3_anchor(tmp_path):
    """### 子节锚点：插在子节标题下；文件内重复的 ### 锚点整体拒绝（不唯一）。"""
    repo = make_repo(tmp_path)
    spec = repo / "steering" / "demo-spec.md"
    spec.write_text(spec.read_text(encoding="utf-8")
                    + "\n### 基础要求\n\n- b1\n", encoding="utf-8")
    p = make_proposal(tmp_path, lessons=[make_lesson(change=PR.Change(
        action="append_under", heading="### 基础要求", new_text="- 新子节条款"))])
    PR.apply_proposal(p, repo)
    text = spec.read_text(encoding="utf-8")
    assert "- b1" in text                       # 既有子节内容保留
    assert text.index("### 基础要求") < text.index("- 新子节条款") < text.index("- b1")

    spec.write_text(spec.read_text(encoding="utf-8")
                    + "\n### 基础要求\n\n- b2\n", encoding="utf-8")
    with pytest.raises(PR.ApplyError, match="不唯一"):
        PR.apply_proposal(make_proposal(tmp_path, pid="20260818-000009-cc-h3dupe01",
                                        lessons=[make_lesson(change=PR.Change(
                                            action="append_under", heading="### 基础要求",
                                            new_text="- 再一条"))]), repo)


def test_normalize_headings_auto_prefix(tmp_path):
    """无 # 前缀 heading → `## ` 前缀规范化回写 pending .md，apply 成功。

    verdict 语义：.orig 快照（未规范化）vs 归档 .md（规范化）heading 不同
    → derive_verdicts 落 edited。锚点真缺陷（无命中/多命中）fail-closed
    保留，不被自动猜测掩盖。"""
    repo = make_repo(tmp_path)
    md = tmp_path / "p1.md"
    p = make_proposal(tmp_path, pid="20260825-000001-cc-norm0001", lessons=[
        make_lesson(change=PR.Change(action="append_under", heading="强制条款",
                                     new_text="- 新条款 X"))])
    md.write_text(PR._render_pending_body(p), encoding="utf-8")
    (tmp_path / "p1.orig").write_text(PR._render_pending_body(p), encoding="utf-8")

    log = PR.normalize_headings(p, repo, md)
    assert any("规范化" in ln for ln in log)
    assert p.lessons[0].change.heading == "## 强制条款"
    # 回写落盘：重载后 heading 已规范化
    re_p = PR.load_proposal(md)
    assert re_p.lessons[0].change.heading == "## 强制条款"
    PR.apply_proposal(p, repo)
    text = (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    assert text.index("## 强制条款") < text.index("- 新条款 X") < text.index("## 推荐")
    # verdict 推导：heading 变化 → edited
    verdicts = PR._derive_verdicts(re_p.lessons, PR.load_proposal(tmp_path / "p1.orig").lessons)
    assert verdicts == ["edited"]


def test_normalize_headings_no_guess_on_miss_or_ambiguity(tmp_path):
    """负控制：规范化候选 0 命中 / 多命中 → 不改写，apply 原错误照报。"""
    repo = make_repo(tmp_path)
    md = tmp_path / "p2.md"
    p = make_proposal(tmp_path, pid="20260825-000002-cc-norm0002", lessons=[
        make_lesson(change=PR.Change(action="append_under", heading="不存在的节",
                                     new_text="- x"))])
    md.write_text(PR._render_pending_body(p), encoding="utf-8")
    log = PR.normalize_headings(p, repo, md)
    assert log == [] or all("规范化" not in ln for ln in log)
    with pytest.raises(PR.ApplyError, match="找不到标题锚点"):
        PR.apply_proposal(p, repo)

    spec = repo / "steering" / "demo-spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## 推荐\n\n- r2\n",
                    encoding="utf-8")
    p2 = make_proposal(tmp_path, pid="20260825-000003-cc-norm0003", lessons=[
        make_lesson(change=PR.Change(action="append_under", heading="推荐",
                                     new_text="- y"))])
    log2 = PR.normalize_headings(p2, repo, tmp_path / "p3.md")
    assert any("不唯一" in ln for ln in log2)
    assert p2.lessons[0].change.heading == "推荐"   # 未被改写
    # 多命中拒绝猜测 → apply 以原 heading 找不到锚点失败（fail-closed 保留）
    with pytest.raises(PR.ApplyError, match="找不到标题锚点"):
        PR.apply_proposal(p2, repo)


class TestAttributionWarnings:
    """归因断言核验：2026-08-27 实证「引文真实 ≠ 判断正确」事故的机械化防线。"""

    def test_incident_scenario_blocks(self):
        # 事故原样：归因 + 推断语气 + 无锚 → 两条警告（当年引文核验放行的正是这条）
        ls = make_lesson(
            evidence="会话里推测 .factory 流水线可能把主仓置为 bare",
            change=PR.Change(action="append_end",
                             new_text="2026-08 实证：.factory 流水线把主仓置为 bare，hermetic 4 例连带失败"))
        ws = PR.attribution_warnings(ls)
        assert len(ws) == 2
        assert any("推断语气" in w for w in ws)
        assert any("缺可核对锚" in w for w in ws)

    def test_anchored_evidence_passes(self):
        ls = make_lesson(
            evidence="dispatch.log 行 23031: 13:23:51 triage exit=128，上一轮 13:13:51 exit=0",
            change=PR.Change(action="append_end",
                             new_text="主仓 bare 发生在 13:13–13:23 空档，dispatch 主链日志排除"))
        assert PR.attribution_warnings(ls) == []

    def test_non_attribution_passes(self):
        ls = make_lesson(
            evidence="用户要求先查插件市场再说自研",
            change=PR.Change(action="append_end",
                             new_text="集成类需求先找现成插件再谈自研"))
        assert PR.attribution_warnings(ls) == []

    def test_attribution_warns_flow_into_proposal_guard(self):
        # warnings() 集成：归因证据不足 → apply 护栏阻断（--force 语义）
        p = PR.Proposal(id="t1", source_agent="a", source_session="s",
                        source_path="x", created="now", lessons=[
            make_lesson(evidence="可能是流水线干的",
                        change=PR.Change(action="append_end",
                                         new_text="流水线造成主仓损坏"))])
        assert any("归因" in w for w in p.warnings())
