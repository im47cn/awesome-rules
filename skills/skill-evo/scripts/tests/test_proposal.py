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
