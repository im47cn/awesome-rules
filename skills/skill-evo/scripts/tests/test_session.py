"""evo_session 单测：CC/omp 双解析器、增量去重、omp 发现。fixtures 运行时生成（脱敏小样本）。"""
import json
from pathlib import Path

import evo_session as S


# ── 构造器（脱敏样例，结构与真实 transcript 一致）───────────────────────────

def write_cc(path: Path, lines):
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n",
                    encoding="utf-8")


def cc_fixture(path: Path, cwd="/home/u/sources/demo", extra_users=0, sid="s-111"):
    lines = [
        {"type": "summary", "summary": "旧摘要"},
        {"type": "user", "cwd": cwd, "sessionId": sid,
         "message": {"role": "user", "content": [{"type": "text", "text": "帮我审查这个 DDL"}]}},
        {"type": "assistant", "isMeta": True,  # meta 行应跳过
         "message": {"role": "assistant", "content": [{"type": "text", "text": "meta"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "先读取文件"},
            {"type": "tool_use", "name": "Read", "input": {}},
        ]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "file body", "is_error": False}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "Error: no such table", "is_error": True}]}},
        {"type": "user", "isMeta": True, "message": {"role": "user", "content": [
            {"type": "text", "text": "<command-name>/init</command-name>"}]}},
    ]
    for i in range(extra_users):  # 越过 min_messages 门槛用的填充消息
        lines.append({"type": "user", "cwd": cwd,
                      "message": {"role": "user", "content": [
                          {"type": "text", "text": f"补充问题 {i}"}]}})
    write_cc(path, lines)


def omp_fixture(path: Path, cwd="/home/u/sources/demo", sid="0aaaa-bbbb", extra_users=0):
    lines = [
        {"type": "title", "v": 1, "title": "t"},
        {"type": "session", "version": 3, "id": sid, "cwd": cwd},
        {"type": "message", "message": {"role": "user", "content": [
            {"type": "text", "text": "omp 里跑一下测试"}]}},
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "thinking"}, {"type": "text", "text": "好的"}],
            "role": "assistant"}},
        {"type": "message", "message": {"role": "toolResult", "isError": True, "content": [
            {"type": "text", "text": "bash: pytest: command not found"}]}},
        "not-a-json-line",
    ]
    for i in range(extra_users):
        lines.append({"type": "message", "message": {"role": "user", "content": [
            {"type": "text", "text": f"补充问题 {i}"}]}})
    path.write_text("\n".join(
        json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else x for x in lines) + "\n",
        encoding="utf-8")


# ── CC 解析 ──────────────────────────────────────────────────────────────────

def test_parse_cc_session(tmp_path):
    f = tmp_path / "s-111.jsonl"
    cc_fixture(f)
    sess = S.parse_cc_session(f)
    assert sess.agent == "cc"
    assert sess.session_id == "s-111"
    assert sess.cwd == "/home/u/sources/demo"
    users = [m for m in sess.messages if m.role == "user"]
    assert len(users) == 1 and "DDL" in users[0].text      # meta/命令消息被过滤
    tools = [m for m in sess.messages if m.role == "tool"]
    assert len(tools) == 2
    assert tools[1].is_error and "no such table" in tools[1].text
    assert any(m.tool_name == "Read" for m in sess.messages)


# ── omp 解析 ────────────────────────────────────────────────────────────────

def test_parse_omp_session(tmp_path):
    f = tmp_path / "2026-08-18T03-42-00-123Z_0aaaa-bbbb.jsonl"
    omp_fixture(f)
    sess = S.parse_omp_session(f)
    assert sess.agent == "omp"
    assert sess.session_id == "0aaaa-bbbb"
    assert sess.cwd == "/home/u/sources/demo"
    assert sess.user_message_count() == 1
    errs = [m for m in sess.messages if m.role == "tool"]
    assert errs[0].is_error and "command not found" in errs[0].text
    assert not any("thinking" in (m.text or "") and m.role == "assistant"
                   for m in sess.messages)  # thinking 块不产生消息


# ── 增量去重 ────────────────────────────────────────────────────────────────

def test_is_processed(tmp_path):
    f = tmp_path / "s.jsonl"
    cc_fixture(f)
    sess = S.parse_cc_session(f)
    assert not S.is_processed({}, sess)
    assert not S.is_processed({"processed": {sess.key: sess.mtime - 1}}, sess)  # mtime 变化重看?否—
    # ↑ mtime 更新意味着内容变了 → 未处理（is_processed 为 False 表示需处理）
    assert S.is_processed({"processed": {sess.key: sess.mtime}}, sess)


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    S.save_state(p, {"processed": {"cc:x": 1.0}})
    assert S.load_state(p) == {"processed": {"cc:x": 1.0}}
    assert S.load_state(tmp_path / "absent.json") == {}


def test_iter_omp_sessions_lookback(tmp_path, monkeypatch):
    import evo_config as C
    cfg = dict(C.DEFAULTS)
    cfg["omp_sessions_dir"] = str(tmp_path)
    cfg["omp_lookback_days"] = 7
    new_dir = tmp_path / "-sources-demo"
    new_dir.mkdir()
    (new_dir / "2020-01-01T00-00-00-000Z_old-old.jsonl").write_text("", encoding="utf-8")
    (new_dir / "2099-01-01T00-00-00-000Z_new-new.jsonl").write_text("", encoding="utf-8")
    (new_dir / "bad-name.jsonl").write_text("", encoding="utf-8")
    (new_dir / "not-jsonl.txt").write_text("", encoding="utf-8")
    names = [f.name for f in S.iter_omp_sessions(cfg)]
    assert names == ["2099-01-01T00-00-00-000Z_new-new.jsonl"]
