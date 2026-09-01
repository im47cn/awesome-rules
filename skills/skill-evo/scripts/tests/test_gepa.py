"""evo_gepa / evo_evolve 单测：纯逻辑（execute/reflect/claude 全 mock）。"""
import json
from pathlib import Path

import evo_gepa as G
import evo_evolve as V
import evo_proposal as PR


def case(cid, **kw):
    return G.Case(id=cid, inputs=kw.get("inputs", {}), reference=kw.get("reference", {}))


# ── Pareto ──────────────────────────────────────────────────────────────────

def test_pareto_front_union_and_ties():
    m = G.ScoreMatrix()
    # c0 在 case1 最优；c1/c2 在 case2 并列最优，但 c2 在 case1 被 c1 支配 → 剔除
    m.set("c0", "case1", 0.9); m.set("c0", "case2", 0.4)
    m.set("c1", "case1", 0.5); m.set("c1", "case2", 0.8)
    m.set("c2", "case1", 0.1); m.set("c2", "case2", 0.8)
    front = G.pareto_front(m)
    assert set(front) == {"c0", "c1"}
    assert front["c0"] == 1 and front["c1"] == 1


def test_pareto_keeps_true_tie_not_dominated():
    m = G.ScoreMatrix()
    # c2 与 c1 完全同分（无严格支配）→ 并列保留在前沿
    m.set("c0", "case1", 0.9); m.set("c0", "case2", 0.4)
    m.set("c1", "case1", 0.5); m.set("c1", "case2", 0.8)
    m.set("c2", "case1", 0.5); m.set("c2", "case2", 0.8)
    front = G.pareto_front(m)
    assert set(front) == {"c0", "c1", "c2"}


def test_pareto_front_dominance_pruning():
    m = G.ScoreMatrix()
    # c3 在两 case 上都被 c1 支配（≤ 且有 <），且从未逐 case 最优 → 不在前沿
    m.set("c0", "case1", 0.9); m.set("c0", "case2", 0.4)
    m.set("c1", "case1", 0.5); m.set("c1", "case2", 0.8)
    m.set("c3", "case1", 0.5); m.set("c3", "case2", 0.7)
    assert "c3" not in G.pareto_front(m)


def test_sample_candidate_weighted_reproducible():
    import random
    freq = {"a": 9, "b": 1}
    rng1, rng2 = random.Random(7), random.Random(7)
    assert G.sample_candidate(freq, rng1) == G.sample_candidate(freq, rng2)
    assert G.sample_candidate({}, rng1) is None


# ── run_gepa 主循环 ─────────────────────────────────────────────────────────

def make_env_for_run(n_train=3, n_holdout=1):
    train = [case(f"t{i}") for i in range(n_train)]
    holdout = [case(f"h{i}") for i in range(n_holdout)]
    calls = {"execute": 0, "reflect": 0}

    def execute(text, c):
        calls["execute"] += 1
        # 「MUTATED」候选在所有 case 上更优（供局部接受）
        return (0.9 if "MUTATED" in text else 0.5), "fb"

    def reflect(current, results, desc):
        calls["reflect"] += 1
        return f"{current} MUTATED"

    return train, holdout, execute, reflect, calls


def test_run_gepa_budget_respected_and_mutant_accepted():
    train, holdout, execute, reflect, calls = make_env_for_run()
    best, matrix, log = G.run_gepa(
        "baseline", train, holdout, execute, reflect, budget=20,
        batch_size=2, rng_seed=0)
    assert calls["execute"] >= 20                    # rollout 用满预算
    assert log[0]["holdout"]                         # holdout 独立必评（验收信号）
    assert "c0" in log[0]["holdout"]                 # baseline 锚必有分
    assert "MUTATED" in best.text or best.id == "c0"  # 变异被接受或 baseline 持平
    assert any(e.get("accepted") for e in log[1:])    # 至少一次变异被接受


def test_run_gepa_discards_invalid_mutation():
    train, holdout, execute, reflect, calls = make_env_for_run()

    def validate(text):
        return "FORBIDDEN" not in text

    def bad_reflect(current, results, desc):
        return f"{current} FORBIDDEN"

    best, matrix, log = G.run_gepa(
        "baseline", train, holdout, execute, bad_reflect, budget=8,
        batch_size=2, rng_seed=0, validate=validate)
    assert best.id == "c0"                            # 违约候选全被丢弃
    assert any(e.get("reason") == "违反候选约束，丢弃" for e in log[1:])


def test_run_gepa_reflector_exception_skips_iteration():
    train, holdout, execute, reflect, calls = make_env_for_run()

    def boom(current, results, desc):
        raise RuntimeError("reflector 挂了")

    best, matrix, log = G.run_gepa(
        "baseline", train, holdout, execute, boom, budget=6, batch_size=2, rng_seed=0)
    assert best.id == "c0"
    assert any(e.get("error") for e in log[1:])


# ── evo_evolve 应用层 ───────────────────────────────────────────────────────

def test_validate_candidate():
    v = V.validate_candidate(100)
    ok = ('x "no_signal" "lessons" append_under append_end evidence "knowledge_type" ##/### '
          + "y" * 50)
    assert v(ok)
    assert not v(ok.replace("append_under", ""))      # 契约关键词缺失
    assert not v(ok.replace("##/###", "##"))          # 丢子节锚点契约
    assert not v(ok + "z" * 200)                      # 长度超 baseline×1.5


def test_build_dataset_from_proposals(tmp_path, monkeypatch):
    """applied/rejected 提案 → dataset；session 分层切；不足时 SystemExit。"""
    import evo_config as C
    import evo_proposal as PR
    import evo
    from test_session import cc_fixture

    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    cfg["scope_dirs"] = [str(tmp_path)]
    cfg["gepa_min_cases"] = 3
    paths = C.base_paths(cfg)
    repo = tmp_path / "repo"
    (repo / "steering").mkdir(parents=True)
    (repo / "steering" / "s.md").write_text("# t\n\n## H\n\n- a\n", encoding="utf-8")
    monkeypatch.setattr(V, "repo_root", lambda: repo, raising=False)

    # 造 8 个 session 的 applied/rejected 提案（holdout 门槛 ≥4 sessions）
    for i, status in enumerate(["applied", "rejected"] * 4):
        src = tmp_path / f"s-{i}.jsonl"
        cc_fixture(src, cwd=str(tmp_path), extra_users=1, sid=f"s-{i}")
        p = PR.Proposal(id=f"20260818-00000{i}-cc-a{i}", source_agent="cc",
                        source_session=f"s-{i}", source_path=str(src), created="T",
                        lessons=[PR.Lesson(
                            type="correction", evidence="e", target_file="steering/s.md",
                            confidence="High", reason="r",
                            change=PR.Change(action="append_end", new_text="- n"))])
        d = paths[status]
        d.mkdir(parents=True, exist_ok=True)
        PR.write_proposal(p, d)
        if status == "rejected":
            f = d / f"{p.id}.md"
            content = f.read_text(encoding="utf-8")
            content = content.replace("created: T\n", "created: T\nreject_reason: 证据不足\n", 1)
            f.write_text(content, encoding="utf-8")

    train, holdout = V.build_dataset(cfg)
    ids = {c.id for c in train + holdout}
    assert ids == {f"cc:s-{i}" for i in range(8)}
    rejected = [c for c in train + holdout if c.reference["status"] == "rejected"]
    assert rejected and rejected[0].reference["reject_reason"] == "证据不足"
    assert train and holdout                        # 分层切分生效
    assert all("transcript_view" in c.inputs and "target_index" in c.inputs
               for c in train + holdout)


def test_make_execute_scores_and_feedback(tmp_path):
    import evo_config as C
    cfg = dict(C.DEFAULTS)

    def fake_claude(prompt, c):
        if "评审" in prompt:   # judge 通道
            return {"precision": 10, "recall": 8, "negative_avoidance": 6,
                    "format_compliance": 10, "feedback": "改进召回"}
        return {"no_signal": False, "lessons": [{"type": "correction"}]}

    execute = V.make_execute(cfg, fake_claude)
    c = case("t0", inputs={"transcript_view": "V", "target_index": "I"},
             reference={"status": "applied", "lessons": [], "reject_reason": ""})
    score, fb = execute("SYSTEM_PROMPT 候选", c)
    expected = (10 / 10 * 0.35 + 8 / 10 * 0.35 + 6 / 10 * 0.2 + 10 / 10 * 0.1)
    assert abs(score - expected) < 1e-9
    assert fb == "改进召回"


def test_write_evolution_proposal(tmp_path, monkeypatch):
    import evo_config as C
    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    best = G.Candidate(id="c2", text="NEW PROMPT\n\"no_signal\" ok", parent="c0", gen=1)
    path = V.write_evolution_proposal(cfg, "OLD", best, 0.5, 0.8,
                                      [{"holdout": {"c0": 0.5, "c2": 0.8}}])
    content = path.read_text(encoding="utf-8")
    assert "type: prompt_evolution" in content and "NEW PROMPT" in content
    # 可被 list 流程加载（frontmatter 完整）
    p = PR.load_proposal(path)
    assert p.status == "pending" and p.lessons == []
