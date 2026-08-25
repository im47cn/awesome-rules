"""evo_evolve 单测：judge 载荷携带结构化 verdict（Q8 方案 A：事实供给不硬编码权重）。"""
import types

import evo_evolve as V
import evo_gepa as G


def _case():
    return G.Case(
        id="cc:s-1", inputs={"transcript_view": "会话记录", "target_index": "资产清单"},
        reference={"status": "applied", "lessons": [
            {"target_file": "steering/spec.md", "confidence": "High",
             "change_new_text": "- x", "evidence": "e",
             "verdict": "trimmed", "verdict_codes": ["content_overlap"]},
            {"target_file": "steering/spec.md", "confidence": "Low",
             "change_new_text": "- y", "evidence": "e2",
             "verdict": "rejected", "verdict_codes": ["low_value"]}],
            "reject_reason": "超集优先"})


def test_execute_feeds_verdicts_to_judge(monkeypatch):
    seen = {}

    def fake_claude(prompt, cfg):
        if "经验提炼质量" in prompt:        # judge 调用
            seen["judge"] = prompt
            return {"precision": 6, "recall": 6, "negative_avoidance": 7,
                    "format_compliance": 8, "feedback": "ok"}
        return {"no_signal": True, "lessons": []}   # 提炼调用

    execute = V.make_execute({"judge_weights": ["0.25"] * 4}, fake_claude)
    score, fb = execute("SP", _case())
    j = seen["judge"]
    # 载荷含结构化 verdict 与码；prompt 含 verdict 语义说明
    assert '"verdict": "trimmed"' in j and '"low_value"' in j
    assert "negative_avoidance 按 verdict_codes" in j
    assert 0 <= score <= 1 and fb == "ok"


def test_load_proposal_roundtrips_verdict_fields(tmp_path):
    """归档 JSON 的 verdict 字段可被 build_dataset 路径读回（load_proposal）。"""
    import evo_proposal as PR
    ls = PR.Lesson(type="success", evidence="e", target_file="steering/x.md",
                   confidence="High", verdict="edited",
                   verdict_codes=["anchor_defect"],
                   change=PR.Change(action="append_end", new_text="- z"))
    p = PR.Proposal(id="20260821-000003-cc-vt1", source_agent="cc",
                    source_session="s", source_path="/t", created="T", lessons=[ls])
    path = PR.write_proposal(p, tmp_path)
    loaded = PR.load_proposal(path)
    assert loaded.lessons[0].verdict == ""          # pending 态不落 verdict（两态 schema）
    # 注入后读回
    PR.finalize_review(path, ["anchor_defect"], rejected=False)
    assert PR.load_proposal(path).lessons[0].verdict == "applied"


def test_validate_candidate_protects_subsection_contract():
    """进化候选重写掉 ### 子节锚点指引 → 拒绝（防退化回二级标题堆叠）。"""
    check = V.validate_candidate(baseline_len=2000)
    good = ('"no_signal"' in '') or 'x "no_signal" "lessons" append_under append_end '
    base = 'k: "no_signal" "lessons" append_under append_end evidence'
    assert check(base + " heading: ##/### 逐字选取") is True
    assert check(base + " heading: ## 级标题") is False        # 丢子节契约 → 拒绝


def test_build_dataset_reference_carries_heading_and_evidence(tmp_path, monkeypatch):
    """归档案例的 reference 携带 heading 与 evidence_check（judge 据此评锚点与证据质量）。"""
    import json as _json
    import evo_config as C
    import evo_prompt as P
    import evo_proposal as PR
    import evo_session as S

    S_write = lambda p, lines: p.write_text(
        "\n".join(_json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")
    # 6 个会话各 1 提案（越过 holdout≥4 与 train≥2 下限）
    for n in range(6):
        src = tmp_path / f"s-gepa{n}.jsonl"
        S_write(src, [
            {"type": "user", "cwd": str(tmp_path), "sessionId": src.stem,
             "message": {"role": "user", "content": [{"type": "text", "text": f"真实会话原话{n}出现在这里供核验"}]}},
            {"type": "assistant", "message": {"role": "assistant",
             "content": [{"type": "text", "text": "收到"}]}},
        ])
        ls = PR.Lesson(type="success", evidence=f"真实会话原话{n}出现在这里供核验",
                       target_file="steering/demo-spec.md", confidence="High", verdict="applied",
                       change=PR.Change(action="append_under", heading="### 子节",
                                        new_text=f"- z{n}"))
        p = PR.Proposal(id=f"20260821-00000{n}-cc-gepa000{n}", source_agent="cc",
                        source_session=f"s{n}", source_path=str(src), created="T", lessons=[ls])
        PR.write_proposal(p, tmp_path / "ar" / "proposals" / "applied")
    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    cfg["scope_dirs"] = [str(tmp_path)]
    cfg["gepa_min_cases"] = 1
    (tmp_path / "ar" / "proposals" / "applied").mkdir(parents=True, exist_ok=True)
    (tmp_path / "steering").mkdir(exist_ok=True)
    (tmp_path / "steering" / "demo-spec.md").write_text("# t\n\n## a\n\n### 子节\n", encoding="utf-8")
    monkeypatch.setattr(C, "repo_root", lambda: tmp_path)
    train, holdout = V.build_dataset(cfg)
    cases = train + holdout
    assert len(cases) == 6
    ref_lesson = cases[0].reference["lessons"][0]
    assert ref_lesson["heading"] == "### 子节"
    assert ref_lesson["evidence_check"] == "hit"          # 逐字命中被核验进引用
