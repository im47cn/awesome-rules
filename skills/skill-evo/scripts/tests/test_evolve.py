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
