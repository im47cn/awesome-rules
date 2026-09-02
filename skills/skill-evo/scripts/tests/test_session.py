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
            {"type": "tool_use", "name": "Read", "input": {"file_path": "schema.sql"}},
        ]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "file body", "is_error": False}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "Error: no such table", "is_error": True}]}},
        {"type": "user", "isMeta": True, "message": {"role": "user", "content": [
            {"type": "text", "text": "<command-name>/init</command-name>"}]}},
    ]
    lines.extend(
        {
            "type": "user",
            "cwd": cwd,
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": f"补充问题 {i}"}],
            },
        }
        for i in range(extra_users)
    )
    write_cc(path, lines)


def omp_fixture(path: Path, cwd="/home/u/sources/demo", sid="0aaaa-bbbb", extra_users=0):
    lines = [
        {"type": "title", "v": 1, "title": "t"},
        {"type": "session", "version": 3, "id": sid, "cwd": cwd},
        {
            "type": "message",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "omp 里跑一下测试"}],
            },
        },
        {
            "type": "message",
            "message": {
                "content": [
                    {"type": "thinking"},
                    {"type": "text", "text": "好的"},
                    {"type": "toolCall", "name": "Bash",
                     "arguments": {"command": "pytest -q"}},
                ],
                "role": "assistant",
            },
        },
        {
            "type": "message",
            "message": {
                "role": "toolResult",
                "isError": True,
                "content": [
                    {"type": "text", "text": "bash: pytest: command not found"}
                ],
            },
        },
        "not-a-json-line",
    ]
    lines.extend(
        {
            "type": "message",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": f"补充问题 {i}"}],
            },
        }
        for i in range(extra_users)
    )
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
    assert any("schema.sql" in (m.text or "") for m in sess.messages)  # input 入语料


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


def test_parse_omp_toolcall_arguments_in_corpus(tmp_path):
    """PR #112 Sourcery 评论①回归：OMP 转录工具块是 toolCall/arguments
    （真实样本 1184 块实证，tool_use 零出现）——arguments 必须入语料，
    否则「执行了 X 命令」类 evidence 在核验语料中全部 miss。"""
    f = tmp_path / "2026-09-01T00-00-00-000Z_0cccc-dddd.jsonl"
    omp_fixture(f)
    sess = S.parse_omp_session(f)
    bash = [m for m in sess.messages if m.tool_name == "Bash"]
    assert bash and "pytest -q" in bash[0].text


# ── 增量去重 ────────────────────────────────────────────────────────────────

def test_is_processed_by_content_hash(tmp_path):
    f = tmp_path / "s.jsonl"
    cc_fixture(f)
    sess = S.parse_cc_session(f)
    assert not S.is_processed({}, sess)
    # 内容哈希记账：记录当前哈希 → 已处理
    digest = S.content_digest(f)
    assert S.is_processed({"processed": {sess.key: digest}}, sess)
    # mtime 变化但内容未变（touch/flush）→ 仍视为已处理（竞态修复）
    import os, time
    os.utime(f, (time.time() + 10, time.time() + 10))
    assert S.is_processed({"processed": {sess.key: digest}}, sess)
    # 内容增长 → 重新处理
    with open(f, "a", encoding="utf-8") as fh:
        fh.write('{"type":"user","message":{"role":"user","content":[{"type":"text","text":"新消息"}]}}\n')
    assert not S.is_processed({"processed": {sess.key: digest}}, sess)
    # 旧 mtime 记账（float）视为未处理 → 自然迁移为哈希
    assert not S.is_processed({"processed": {sess.key: 123.0}}, sess)


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


# ── 会话锁（并发互斥）───────────────────────────────────────────────────────

def _paths(tmp_path: Path) -> dict:
    return {"locks": tmp_path / "locks"}


def test_session_lock_exclusive(tmp_path):
    """同 key 二次获取：让位 False，锁文件仍在；释放后可再获取。"""
    with S.session_lock(_paths(tmp_path), "cc:s-1") as first:
        assert first
        with S.session_lock(_paths(tmp_path), "cc:s-1") as second:
            assert not second                      # 撞锁让位
        assert any((tmp_path / "locks").glob("cc:s-1.lock"))  # 让位者不误删锁
    with S.session_lock(_paths(tmp_path), "cc:s-1") as again:
        assert again                                # 释放后可重入
    assert not any((tmp_path / "locks").glob("*.lock"))        # 全部释放


def test_session_lock_different_keys_independent(tmp_path):
    with S.session_lock(_paths(tmp_path), "cc:s-1"):
        with S.session_lock(_paths(tmp_path), "cc:s-2") as other:
            assert other                            # 不同会话不互斥


def test_session_lock_stale_steal(tmp_path):
    """过期死锁（mtime 超时）被窃取：可重新获取。"""
    import os, time
    paths = _paths(tmp_path)
    with S.session_lock(paths, "cc:s-dead"):
        pass                                        # 正常释放
    lock = paths["locks"] / "cc:s-dead.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("pid=1 ts=0\n", encoding="utf-8")
    os.utime(lock, (0, 0))                          # 模拟远古死锁
    with S.session_lock(paths, "cc:s-dead", stale_seconds=100) as got:
        assert got                                  # 过期 → 窃取成功
    # 撞锁异常路径让位后释放不误删他人锁：直接持有者持有中释放让位者的锁不存在


def test_save_state_concurrent_merge_no_loss(tmp_path, monkeypatch):
    """PR #58 审查①判别：两进程各持不同会话锁，快照互不含对方条目——
    后写者不得抹掉先写者的 processed（合并语义）。"""
    import evo_session as S
    sp = tmp_path / "state.json"
    # 进程 A 快照：只知 sess-a
    snap_a = {"processed": {"agent|sess-a": "digest-a"}}
    S.save_state(sp, snap_a)
    # 进程 B 持旧快照（读于 A 写之前）：只知 sess-b
    snap_b = {"processed": {"agent|sess-b": "digest-b"}}
    S.save_state(sp, snap_b)
    merged = S.load_state(sp)
    assert merged["processed"]["agent|sess-a"] == "digest-a"   # A 条目存活
    assert merged["processed"]["agent|sess-b"] == "digest-b"


def test_lock_steal_old_owner_does_not_delete_new(tmp_path, monkeypatch):
    """PR #58 审查②判别：锁被窃后旧 owner 退出时不得误删新持有者的锁。"""
    import evo_session as S
    paths = {"locks": tmp_path}
    # worker A 拿锁后"卡死"（不释放）
    ctx_a = S.session_lock(paths, "agent|x")
    held_a = ctx_a.__enter__()
    assert held_a is True
    # 伪造过期：mtime 回拨 2h
    lock = tmp_path / ("agent|x".replace("/", "_") + ".lock")
    import os as _os
    old = S.time.time() - 7200
    _os.utime(lock, (old, old))
    # worker B 窃锁成功
    ctx_b = S.session_lock(paths, "agent|x")
    held_b = ctx_b.__enter__()
    assert held_b is True
    # worker A 结束：锁内容是 B 的 token，A 不得删除
    ctx_a.__exit__(None, None, None)
    assert lock.exists(), "旧 owner 误删了新持有者的锁"
    # worker B 正常退出：锁被清
    ctx_b.__exit__(None, None, None)
    assert not lock.exists()
