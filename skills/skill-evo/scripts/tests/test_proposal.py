"""evo_proposal 单测：round-trip、路径逃逸、锚点应用、护栏、状态流转。"""
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


def test_apply_append_end(tmp_path):
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
