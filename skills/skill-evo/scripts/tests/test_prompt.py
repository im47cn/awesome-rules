"""evo_prompt 单测：脱敏、切片截断、目标资产索引。"""
from pathlib import Path

import evo_config as C
import evo_prompt as P
from evo_session import Msg, Session


def make_session(messages):
    return Session(agent="cc", session_id="t", cwd="/x", path=Path("/x.jsonl"),
                   mtime=0.0, messages=messages)


def test_sanitize_redacts_secrets():
    text = "token: sk-abcdef1234567890abcdef 与 AKIAIOSFODNN7EXAMPLE 和 ghp_" + "x" * 30
    out = P.sanitize(text)
    assert "sk-abcdef" not in out and "AKIAIOSFODNN7EXAMPLE" not in out and "ghp_" not in out


def test_sanitize_collapses_long_tokens_and_ansi():
    out = P.sanitize("\x1b[31mred\x1b[0m " + "A" * 300)
    assert "\x1b" not in out and "A" * 300 not in out and "<LONG-TOKEN>" in out


def test_transcript_view_truncation_and_roles():
    cfg = dict(C.DEFAULTS)
    cfg["max_transcript_chars"] = 100
    sess = make_session([
        Msg(role="user", text="请检查这段代码 " * 50),   # 普通 token，不会被脱敏折叠
        Msg(role="assistant", text="A" * 2000),
        Msg(role="tool", text="ok result", is_error=False),
        Msg(role="assistant", text="", tool_name="Bash"),
    ])
    view = P.build_transcript_view(sess, cfg)
    assert len(view) <= 100 + 40          # 截断标记容忍
    assert "截断" in view
    assert "[user]" in view


def test_transcript_view_limits():
    cfg = dict(C.DEFAULTS)
    sess = make_session([
        Msg(role="assistant", text="A" * 2000),
        Msg(role="tool", text="T" * 500, is_error=False),
        Msg(role="tool", text="T" * 500, is_error=True),
    ])
    view = P.build_transcript_view(sess, cfg)
    assert "A" * 900 not in view                      # assistant 截断
    assert "T" * 300 not in view                      # 工具结果截断（正常/错误均受上限）


def _mk_repo(tmp_path):
    (tmp_path / "skills" / "demo").mkdir(parents=True)
    (tmp_path / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: 测试\n---\n# Demo\n\n## 工作流\n\n- 步骤\n",
        encoding="utf-8")
    (tmp_path / "steering").mkdir(parents=True)
    (tmp_path / "steering" / "demo-spec.md").write_text(
        "---\ntitle: 测试规范\nscenario: 测试\n---\n# 测试规范\n\n## 强制条款\n\n1. 【强制】条款 A\n",
        encoding="utf-8")
    return tmp_path


def test_build_target_index(tmp_path):
    idx = P.build_target_index(_mk_repo(tmp_path))
    assert "skills/demo/SKILL.md" in idx and "steering/demo-spec.md" in idx
    assert "## 工作流" in idx                 # 标题锚点已列出（append_under 可用）
    assert "测试规范" in idx                  # frontmatter title 生效


def test_build_summary_prompt_contains_sections(tmp_path):
    cfg = dict(C.DEFAULTS)
    repo = _mk_repo(tmp_path)
    sess = make_session([Msg(role="user", text="用户要求 X")])
    prompt = P.build_summary_prompt(sess, cfg, repo)
    for sec in ("# 会话信息", "# 目标资产清单", "# 会话记录", '"no_signal"', "append_under"):
        assert sec in prompt
