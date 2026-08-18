"""evo CLI 单测：run 全流程（monkeypatch 掉 claude 子进程）/ list / apply / reject。

不打真模型：evo.call_claude 被替换为固定 lessons JSON。
"""
import json
from pathlib import Path
from types import SimpleNamespace

import evo
import evo_config as C
import evo_proposal as PR
from test_session import cc_fixture, omp_fixture

FAKE_LESSONS = {
    "no_signal": False,
    "lessons": [{
        "type": "correction", "evidence": "用户说'不要 select *'",
        "target_file": "steering/demo-spec.md", "confidence": "High",
        "reason": "补充条款",
        "change": {"action": "append_under", "heading": "## 强制条款",
                   "new_text": "- 禁止 `select *`"},
    }],
}


def make_env(tmp_path, monkeypatch):
    """统一测试环境：临时 base_dir + 临时 repo（skills/steering）。"""
    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    cfg["scope_dirs"] = [str(tmp_path)]
    cfg["omp_sessions_dir"] = str(tmp_path / "omp-sessions")
    monkeypatch.setattr(evo.C, "load_config", lambda: cfg)
    # repo_root 指向临时仓库（验证 target 校验与应用走临时文件）
    repo = tmp_path / "repo"
    (repo / "steering").mkdir(parents=True)
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "steering" / "demo-spec.md").write_text(
        "# 测试规范\n\n## 强制条款\n\n1. 既有条款\n", encoding="utf-8")
    monkeypatch.setattr(evo.C, "repo_root", lambda: repo)
    return cfg, tmp_path / "ar", repo


def test_run_creates_proposal_and_state(tmp_path, monkeypatch):
    cfg, base, repo = make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(evo, "call_claude", lambda prompt, c: json.loads(json.dumps(FAKE_LESSONS)))
    transcript = tmp_path / "s-222.jsonl"
    cc_fixture(transcript, cwd=str(tmp_path / "demo-repo"), extra_users=6, sid=transcript.stem)

    args = SimpleNamespace(hook_json_file=None, transcript=str(transcript),
                           no_omp=True, dry_run=False)
    assert evo.cmd_run(args) == 0

    pendings = list((base / "proposals" / "pending").glob("*.md"))
    assert len(pendings) == 1
    state = json.loads((base / "state.json").read_text(encoding="utf-8"))
    assert f"cc:{transcript.stem}" in state["processed"]

    # apply 提案：写入临时 repo 的 steering 文件
    proposal = PR.load_proposal(pendings[0])
    report = PR.apply_proposal(proposal, repo)
    assert "- 禁止 `select *`" in (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    assert len(report) == 1


def test_run_dedup_by_state(tmp_path, monkeypatch):
    """处理过的会话再次 run 不重复提案（增量幂等）。"""
    cfg, base, repo = make_env(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(evo, "call_claude",
                        lambda p, c: calls.append(1) or json.loads(json.dumps(FAKE_LESSONS)))
    transcript = tmp_path / "s-666.jsonl"
    cc_fixture(transcript, cwd=str(tmp_path / "demo-repo"), extra_users=6, sid=transcript.stem)
    args = SimpleNamespace(hook_json_file=None, transcript=str(transcript),
                           no_omp=True, dry_run=False)
    evo.cmd_run(args)
    evo.cmd_run(args)
    assert len(calls) == 1
    assert len(list((base / "proposals" / "pending").glob("*.md"))) == 1


def test_run_no_signal_marks_processed(tmp_path, monkeypatch):
    cfg, base, repo = make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(evo, "call_claude", lambda p, c: {"no_signal": True, "lessons": []})
    transcript = tmp_path / "s-333.jsonl"
    cc_fixture(transcript, cwd=str(tmp_path / "demo-repo"), extra_users=6, sid=transcript.stem)
    args = SimpleNamespace(hook_json_file=None, transcript=str(transcript),
                           no_omp=True, dry_run=False)
    evo.cmd_run(args)
    assert not list((base / "proposals" / "pending").glob("*.md"))
    state = json.loads((base / "state.json").read_text(encoding="utf-8"))
    assert "cc:s-333" in state["processed"]


def test_run_piggyback_omp(tmp_path, monkeypatch):
    cfg, base, repo = make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(evo, "call_claude", lambda p, c: json.loads(json.dumps(FAKE_LESSONS)))
    omp_dir = Path(cfg["omp_sessions_dir"]) / "-sources-demo"
    omp_dir.mkdir(parents=True)
    # scope 外 cwd：应被跳过
    omp_fixture(omp_dir / "2099-01-01T00-00-00-000Z_0omp-1111.jsonl", extra_users=6)
    # scope 内 cwd：应成案
    omp_fixture(omp_dir / "2099-01-01T01-00-00-000Z_0omp-2222.jsonl",
                cwd=str(tmp_path / "demo-repo"), extra_users=6)

    args = SimpleNamespace(hook_json_file=None, transcript=None, no_omp=False, dry_run=False)
    evo.cmd_run(args)
    pendings = list((base / "proposals" / "pending").glob("*.md"))
    assert len(pendings) == 1 and "omp" in pendings[0].name


def test_run_claude_error_does_not_crash(tmp_path, monkeypatch):
    cfg, base, repo = make_env(tmp_path, monkeypatch)

    def boom(prompt, c):
        raise RuntimeError("LLM 挂了")

    monkeypatch.setattr(evo, "call_claude", boom)
    transcript = tmp_path / "s-444.jsonl"
    cc_fixture(transcript, cwd=str(tmp_path / "demo-repo"), extra_users=6, sid=transcript.stem)
    args = SimpleNamespace(hook_json_file=None, transcript=str(transcript),
                           no_omp=True, dry_run=False)
    assert evo.cmd_run(args) == 0                       # 静默失败
    state = json.loads((base / "state.json").read_text(encoding="utf-8"))
    assert "cc:s-444" in state["processed"]             # 失败也记账防反复重试
    log = (base / "logs" / "evo.log").read_text(encoding="utf-8")
    assert "error" in log


def test_list_apply_reject_flow(tmp_path, monkeypatch, capsys):
    cfg, base, repo = make_env(tmp_path, monkeypatch)
    p = PR.Proposal(id="20260818-120000-cc-abcd1234", source_agent="cc",
                    source_session="s", source_path="/t", created="T",
                    lessons=[PR.Lesson(
                        type="correction", evidence="e", target_file="steering/demo-spec.md",
                        confidence="High", reason="r", change=PR.Change(
                            action="append_end", new_text="- 新条款"))])
    PR.write_proposal(p, base / "proposals" / "pending")

    assert evo.cmd_list(SimpleNamespace()) == 0
    out = capsys.readouterr().out
    assert "20260818-120000" in out and "steering/demo-spec.md" in out

    # 前缀匹配 apply；dry-run 不落盘
    assert evo.cmd_apply(SimpleNamespace(id="20260818-12", dry_run=True, force=False)) == 0
    assert "- 新条款" not in (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    assert evo.cmd_apply(SimpleNamespace(id="20260818-12", dry_run=False, force=False)) == 0
    assert "- 新条款" in (repo / "steering" / "demo-spec.md").read_text(encoding="utf-8")
    assert not list((base / "proposals" / "pending").glob("*.md"))
    assert list((base / "proposals" / "applied").glob("*.md"))

    # reject 流转
    p2 = PR.Proposal(id="20260818-130000-cc-eeee5678", source_agent="omp",
                     source_session="s2", source_path="/t2", created="T",
                     lessons=[PR.Lesson(
                         type="failure", evidence="e", target_file="skills/demo/SKILL.md",
                         confidence="Low", reason="r", change=PR.Change(
                             action="append_end", new_text="- x"))])
    PR.write_proposal(p2, base / "proposals" / "pending")
    assert evo.cmd_reject(SimpleNamespace(id="20260818-13", reason="证据不足")) == 0
    assert not list((base / "proposals" / "pending").glob("*.md"))
    assert list((base / "proposals" / "rejected").glob("*.md"))


def test_dry_run_prompt_written(tmp_path, monkeypatch):
    cfg, base, repo = make_env(tmp_path, monkeypatch)
    transcript = tmp_path / "s-555.jsonl"
    cc_fixture(transcript, cwd=str(tmp_path / "demo-repo"), extra_users=6, sid=transcript.stem)
    args = SimpleNamespace(hook_json_file=None, transcript=str(transcript),
                           no_omp=True, dry_run=True)
    evo.cmd_run(args)
    prompt = Path("/tmp/ar-skill-evo-prompt.md").read_text(encoding="utf-8")
    assert "# 会话信息" in prompt
