"""evo_replay 单测：评估集加载、报告解析器、F1 对账、门禁、CLI 链路（LLM 全 mock）。"""
import types
from pathlib import Path

import evo_gepa as G
import evo_replay as R


def _case(cid="c1", expected=None, files=None):
    return G.Case(
        id=cid,
        inputs={"input_dir": "/tmp/x", "files": files or {"a.sql": "CREATE TABLE t (id int);"}},
        reference={"expected_rules": expected or [], "manual_rules": [],
                   "expected_empty": not expected})


# ── 报告解析器（确定性，零 LLM）───────────────────────────────────────────
def test_extract_rules_from_report_happy():
    rules, ok = R.extract_rules_from_report('审查报告…\n{"rules": ["禁用类型", "表注释缺失"]}')
    assert ok and rules == ["禁用类型", "表注释缺失"]


def test_extract_rules_from_report_no_list_is_unparsable():
    # 候选删掉「输出清单」指令 → 报告无 JSON → 不可解析（0 分前置）
    assert R.extract_rules_from_report("五段式报告，无清单") == ([], False)
    assert R.extract_rules_from_report("") == ([], False)
    assert R.extract_rules_from_report('{"rules": broken') == ([], False)


def test_extract_rules_empty_list_is_parsable():
    # 合法空清单 = 放行（该拦的没拦 → recall 惩罚留给对账层）
    rules, ok = R.extract_rules_from_report('{"rules": []}')
    assert ok and rules == []


def test_extract_rules_filters_non_string_and_bad_json():
    # 非 str 规则剔除；json 解析异常 → 不可解析
    rules, ok = R.extract_rules_from_report('{"rules": ["禁用类型", 42, "", null]}')
    assert ok and rules == ["禁用类型"]
    assert R.extract_rules_from_report('{"rules": [1,2,}') == ([], False)
    # 正则命中但 json.loads 抛异常 → except 分支（[nope] 无引号非法 JSON）
    assert R.extract_rules_from_report('{"rules": [nope]}') == ([], False)


# ── F1 对账（双维对称惩罚）────────────────────────────────────────────────
def test_f1_recall_and_precision_dimensions():
    # 拦截型：漏拦一半 → recall 0.5（tp=1；2 actual 中 1 条命中 → n_hit_actual=1）
    assert R.f1_score(1, 2, 2, 1) == 2 * (0.5 * 0.5) / (0.5 + 0.5) == 0.5
    # 放行型：expected 空 + actual 非空 → precision 0 → F1 0（全盘拒绝被对称惩罚）
    assert R.f1_score(tp=0, n_expected=0, n_actual=3, n_hit_actual=0) == 0.0
    # 完美：2 actual 全命中 → n_hit_actual=2
    assert R.f1_score(tp=2, n_expected=2, n_actual=2, n_hit_actual=2) == 1.0
    # 双零 = 空 expected + 空 actual = 干净放行 → F1 1（与实现语义一致）
    assert R.f1_score(tp=0, n_expected=0, n_actual=0, n_hit_actual=0) == 1.0


def test_reconcile_missing_and_unexpected():
    tp, missing, unexpected = R.reconcile(["表注释缺失", "禁用类型"], ["表注释缺失", "全角字符"])
    assert tp == 1
    assert missing == ["禁用类型"]
    assert unexpected == ["全角字符"]


def test_reconcile_empty_expected_any_actual_is_unexpected():
    # 放行 case：任何检出都算误拦（precision 侧核心）
    tp, missing, unexpected = R.reconcile([], ["禁用类型"])
    assert tp == 0 and missing == [] and unexpected == ["禁用类型"]


# ── 评估集加载 ─────────────────────────────────────────────────────────────
def test_load_eval_set_parses_expected_and_empty(tmp_path):
    (tmp_path / "001-bad" / "input").mkdir(parents=True)
    (tmp_path / "001-bad" / "input" / "t.sql").write_text("x", encoding="utf-8")
    (tmp_path / "001-bad" / "expected.md").write_text(
        "# c\n\n## 预期检查输出\n\n- 脚本自动检出：禁用类型、表注释缺失\n- 人工补充：语义\n",
        encoding="utf-8")
    (tmp_path / "007-clean" / "input").mkdir(parents=True)
    (tmp_path / "007-clean" / "input" / "c.sql").write_text("y", encoding="utf-8")
    (tmp_path / "007-clean" / "expected.md").write_text(
        "# c\n\n## 预期检查输出\n\n（本 case 无脚本自动检出项）\n", encoding="utf-8")
    (tmp_path / "002-mix" / "input").mkdir(parents=True)
    (tmp_path / "002-mix" / "input" / "t.sql").write_text("z", encoding="utf-8")
    (tmp_path / "002-mix" / "expected.md").write_text(
        "# c\n\n## 预期检查输出\n\n- 脚本自动检出：禁用类型\n- 独立规则行\n", encoding="utf-8")

    cases = R.load_eval_set("s", tmp_path, {})
    by_id = {c.id: c for c in cases}
    assert by_id["s:001-bad"].reference["expected_rules"] == ["禁用类型", "表注释缺失"]
    assert by_id["s:002-mix"].reference["expected_rules"] == ["禁用类型", "独立规则行"]
    assert by_id["s:001-bad"].reference["expected_empty"] is False
    assert by_id["s:007-clean"].reference["expected_empty"] is True
    assert by_id["s:001-bad"].inputs["files"] == {"t.sql": "x"}


def test_load_eval_set_skips_dir_without_input(tmp_path):
    (tmp_path / "no-input").mkdir()          # 无 input/ → 跳过
    (tmp_path / "ok" / "input").mkdir(parents=True)
    (tmp_path / "ok" / "input" / "f.sql").write_text("x", encoding="utf-8")
    cases = R.load_eval_set("s", tmp_path, {})
    assert [c.id for c in cases] == ["s:ok"]


def test_parse_expected_manual_rule_ids_vs_desc(tmp_path):
    """「人工补充规则：」行 → manual_rules 精确规则 ID；「人工补充：」描述行
    不进 manual_rules（不参与对账）。"""
    f = tmp_path / "e.md"
    f.write_text(
        "# c\n\n## 预期检查输出\n\n"
        "- 脚本自动检出：禁用类型\n"
        "- 人工补充：命名语义（拼音、泛化词）\n"
        "- 人工补充规则：拼音、泛化词、复数\n",
        encoding="utf-8")
    script, rules, manual = R.parse_expected(f)
    assert rules == ["禁用类型"]
    assert manual == ["拼音", "泛化词", "复数"]   # 描述行不混入


def test_load_eval_set_include_manual_merges(tmp_path):
    """include_manual=True：manual_rules 并入 expected_rules（GEPA 专用），
    放行型（无人工规则）expected_empty 不受影响。"""
    for name, content in {
        "001-bad": "- 脚本自动检出：禁用类型\n- 人工补充规则：拼音、泛化词",
        "007-clean": "（无脚本自动检出项）",
    }.items():
        (tmp_path / name / "input").mkdir(parents=True)
        (tmp_path / name / "input" / "f.sql").write_text("x", encoding="utf-8")
        (tmp_path / name / "expected.md").write_text(
            f"# c\n\n## 预期检查输出\n\n{content}\n", encoding="utf-8")
    by_id = {c.id: c for c in R.load_eval_set("s", tmp_path, {}, include_manual=True)}
    assert by_id["s:001-bad"].reference["expected_rules"] == ["禁用类型", "拼音", "泛化词"]
    assert by_id["s:001-bad"].reference["expected_empty"] is False
    assert by_id["s:007-clean"].reference["expected_rules"] == []
    assert by_id["s:007-clean"].reference["expected_empty"] is True


def test_rule_matches_anyof_alias(tmp_path):
    """any-of 别名：| 分隔任一 token 命中即检出；首 token 规范名用于 missing 展示。"""
    assert R._rule_matches("字段与注释对应|注释含义对应", ["字段名与注释含义对应"])
    # 否定插入：短别名命中「字段与注释不对应」？——「注释含义对应」不中，规范名不中，
    # 但别名「对应」类需要真实现（此处验证规范名优先不误报）
    assert not R._rule_matches("字段与注释对应|注释含义对应", ["字段与注释不对应"])
    # 无别名规则兼容（单 token 行为不变）
    assert R._rule_matches("禁用类型", ["使用禁用类型 text"])
    assert not R._rule_matches("禁用类型", ["注释缺失"])
    # 空 token（如「规范名|」）不崩
    assert R._rule_matches("复数形式|", ["表名使用复数形式"])


def test_reconcile_missing_shows_canonical_name():
    """reconcile：别名规则 missing 只显示规范名（reflector 反馈不暴露别名串）。"""
    tp, missing, unexpected = R.reconcile(
        ["表名主体|核心主体", "禁用类型"], ["使用禁用类型 bigint"])
    assert tp == 1                      # 禁用类型命中
    assert missing == ["表名主体"]       # 规范名，非「表名主体|核心主体」
    assert unexpected == []
    # 别名命中 → 不 missing
    tp2, missing2, _ = R.reconcile(
        ["表名主体|核心主体"], ["表名未围绕核心主体"])
    assert tp2 == 1 and missing2 == []


def test_f1_score_merged_hit_bounded():
    """一条 actual 命中多条 expected（合并检出）→ precision 用命中 actual 数，F1 ≤ 1。

    子串匹配下「表名使用拼音和泛化词」同时命中 [拼音, 泛化词] → tp=2 但 actual=1；
    precision 若直接 tp/n_actual 会 2.0 → F1=1.33 越界（score 契约 [0,1]，且合并
    报告可被 gaming 抬高 precision）。命中 actual 数 = len(actual)-len(unexpected)。
    """
    # 合并检出：单条 actual 含两个 expected 子串 → tp=2, unexpected=0, 命中 actual=1
    tp, _, unexpected = R.reconcile(["拼音", "泛化词"], ["表名使用拼音和泛化词"])
    assert tp == 2 and unexpected == []
    s = R.f1_score(tp, 2, 1, 1 - len(unexpected))
    assert s == 1.0                      # 全检出，F1=1 不越界
    # 全 miss：命中 actual=0 → precision=0 → F1=0
    tp2, _, unexpected2 = R.reconcile(["拼音"], ["无关评论"])
    assert R.f1_score(tp2, 1, 1, 1 - len(unexpected2)) == 0.0
    # 混合：1 命中 + 1 无关 → precision=(2-1)/2=0.5
    tp3, _, unexpected3 = R.reconcile(["拼音", "泛化词"], ["表名使用拼音", "无关"])
    assert abs(R.f1_score(tp3, 2, 2, 2 - len(unexpected3)) - 0.5) < 1e-9


def test_parse_expected_missing_file_and_head_fallback(tmp_path):
    assert R.parse_expected(tmp_path / "absent.md") == (None, [], [])
    # 无「## 预期检查输出」段 → head 兜底解析；check_script 行提取
    f = tmp_path / "e.md"
    f.write_text("check: scripts/ddl_check.py\n\n- 禁用类型\n- 表注释缺失\n", encoding="utf-8")
    script, rules, manual = R.parse_expected(f)
    assert script == "scripts/ddl_check.py"
    assert rules == ["禁用类型", "表注释缺失"] and manual == []
    # head 分支内：以 # 开头行跳过（非规则）
    f2 = tmp_path / "e2.md"
    f2.write_text("# 标题\n\n- 规则A\n- 规则B\n", encoding="utf-8")
    assert R.parse_expected(f2)[1] == ["规则A", "规则B"]
    # 列表项内嵌 # 注释 → 跳过（elif not startswith("#") 分支）
    f3 = tmp_path / "e3.md"
    f3.write_text("- # 内部注释\n- 规则C\n", encoding="utf-8")
    assert R.parse_expected(f3)[1] == ["规则C"]


# ── execute（候选 → 报告 → 解析 → 对账）──────────────────────────────────
def test_execute_scores_and_feedback(monkeypatch):
    seen = {}

    def fake_claude_raw(prompt, cfg):
        seen["prompt"] = prompt
        return '报告…\n{"rules": ["禁用类型"]}'

    case = _case(expected=["禁用类型", "表注释缺失"])
    execute = R.make_execute({}, fake_claude_raw, "s")
    score, fb = execute("候选 SKILL.md", case)
    assert score == 2 * 0.5 * 1 / 1.5        # recall=1/2, precision=1/1 → F1=2*0.5*1/1.5
    assert "漏拦: 表注释缺失" in fb
    assert '{"rules"' in seen["prompt"]       # 执行 prompt 强制输出清单契约


def test_execute_full_hit_and_unexpected(monkeypatch):
    def fake(prompt, cfg):
        return '{"rules": ["禁用类型", "全角字符"]}'
    execute = R.make_execute({}, fake, "s")
    score, fb = execute("x", _case(expected=["禁用类型"]))
    assert score == 2 * 1.0 * 0.5 / 1.5       # recall=1/1, precision=1/2 → 0.667
    assert "误拦: 全角字符" in fb

    def fake_clean(prompt, cfg):
        return '{"rules": ["禁用类型"]}'
    execute2 = R.make_execute({}, fake_clean, "s")
    score2, fb2 = execute2("x", _case(expected=["禁用类型"]))
    assert score2 == 1.0 and "全部命中" in fb2


def test_execute_unparsable_report_scores_zero(monkeypatch):
    def fake_claude_raw(prompt, cfg):
        return "报告没有清单 JSON"
    execute = R.make_execute({}, fake_claude_raw, "s")
    score, fb = execute("x", _case(expected=["禁用类型"]))
    assert score == 0.0 and "报告不可解析" in fb


def test_execute_llm_failure_scores_zero(monkeypatch):
    def boom(prompt, cfg):
        raise RuntimeError("claude 超时")
    execute = R.make_execute({}, boom, "s")
    score, fb = execute("x", _case(expected=["禁用类型"]))
    assert score == 0.0 and "执行失败" in fb


# ── make_reflect（reflector 通道）──────────────────────────────────────────
def test_make_reflect_builds_prompt_with_feedback(monkeypatch):
    seen = {}

    def fake(prompt, cfg):
        seen["p"] = prompt
        return "编辑后的 SKILL.md"
    reflect = R.make_reflect(fake, {})
    out = reflect("当前 SKILL", [(_case(cid="c1", expected=["禁用类型"]), 0.5, "漏拦: 表注释缺失")], "x")
    assert out == "编辑后的 SKILL.md"
    assert "score=0.500" in seen["p"] and "漏拦: 表注释缺失" in seen["p"]
    assert "当前 SKILL" in seen["p"]


# ── 门禁：全盘拒绝控制候选（护栏 4，确定性）───────────────────────────────
def test_control_gate_reject_all_below_clean():
    # 放行 case：全盘拒绝报告 → precision 0 → F1 0
    release = _case(cid="r1", expected=[], files={"c.sql": "clean"})
    # 拦截 case：expected 不在全盘拒绝清单 → recall 0 → F1 0
    intercept = _case(cid="i1", expected=["WHERE避免函数转换"])
    gate = R.control_gate([release, intercept])
    assert gate == 0.0
    # 干净执行参照：逐 case F1=1 → 门禁 F1 显著更低
    clean = sum(R.f1_score(len(c.reference["expected_rules"]),
                           len(c.reference["expected_rules"]),
                           len(c.reference["expected_rules"]),
                           len(c.reference["expected_rules"])) for c in [release, intercept]) / 2
    assert gate < clean


def test_control_gate_empty_holdout():
    assert R.control_gate([]) == float("-inf")


def test_split_eval_keeps_release_in_holdout():
    cases = [_case(cid=f"i{i}") for i in range(6)] + [_case(cid="r1", expected=[])]
    train, holdout = R.split_eval(cases, {"gepa_holdout_ratio": 0.2})
    assert any(c.reference["expected_empty"] for c in holdout)   # 放行型至少 1 进 holdout
    assert len(train) + len(holdout) == 7


# ── validate_candidate（frontmatter 契约 + 锚点 + 长度）───────────────────
def test_validate_candidate_rejects_frontmatter_drop_and_oversize():
    v = R.validate_candidate(100)
    good = "---\nname: ddl-guard\ndescription: x\n\n## 审查工作流\n" + "x" * 50
    assert v(good) is True
    assert v("## 审查工作流\n" + "x" * 50) is False         # 删 frontmatter → 拒
    assert v(good + "y" * 120) is False                     # 超长 1.5× → 拒
    assert v("---\nname: x\ndescription: y\n\n" + "x" * 50) is False  # 无 ## 锚点 → 拒


# ── 注册表路径逃逸（护栏 1）───────────────────────────────────────────────
def test_scorer_registry_rejects_escape_and_missing():
    import evo_proposal as PR
    saved = R.SCORER_REGISTRY["ddl-guard"]
    try:
        R.SCORER_REGISTRY["ddl-guard"] = {"scripts": ["../../etc/passwd"], "accepted_dirs": ("skills/",)}
        try:
            R.scorer_registry()
            assert False, "应拒绝越界路径"
        except PR.ApplyError as e:
            assert "越出仓库" in str(e) or "不在允许范围" in str(e)
        # resolve 后越出仓库边界（四层 .. 逃到仓库外）
        R.SCORER_REGISTRY["ddl-guard"] = {"scripts": ["skills/ddl-guard/scripts/../../../.."],
                                          "accepted_dirs": ("skills/",)}
        try:
            R.scorer_registry()
            assert False, "应拒绝 resolve 后越界"
        except PR.ApplyError as e:
            assert "越出仓库" in str(e)

        # 仓库内但前缀不在允许范围（合法 resolve → startswith 检查）
        R.SCORER_REGISTRY["ddl-guard"] = {"scripts": ["docs/design/x.py"],
                                          "accepted_dirs": ("skills/",)}
        try:
            R.scorer_registry()
            assert False, "应拒绝范围外前缀"
        except PR.ApplyError as e:
            assert "不在允许范围" in str(e)

        R.SCORER_REGISTRY["ddl-guard"] = {"scripts": ["skills/ddl-guard/scripts/nope.py"],
                                          "accepted_dirs": ("skills/",)}
        try:
            R.scorer_registry()
            assert False, "应拒绝不存在脚本"
        except PR.ApplyError as e:
            assert "不存在" in str(e)
    finally:
        R.SCORER_REGISTRY["ddl-guard"] = saved


def test_scorer_registry_happy_path():
    reg = R.scorer_registry()
    assert "ddl-guard" in reg and len(reg["ddl-guard"]["scripts"]) == 2
    assert all(p.is_file() for p in reg["ddl-guard"]["scripts"])


# ── script_baseline_f1（dry-run 确定性打分）──────────────────────────────
def test_script_baseline_f1_unknown_skill():
    import pytest
    with pytest.raises(SystemExit):
        R.script_baseline_f1({}, "nope", [])


def test_script_baseline_f1_script_failure(monkeypatch, tmp_path):
    """脚本异常 → 该 case 记 error 不崩溃，F1 降级计算。"""
    import json
    case = _case(cid="c1", expected=["禁用类型"], files={"a.sql": "x"})
    case = G.Case(id="c1", inputs={"input_dir": str(tmp_path), "files": {"a.sql": "x"}},
                  reference={"expected_rules": ["禁用类型"], "manual_rules": [],
                             "expected_empty": False})

    def boom(cmd, capture_output=True, text=True, timeout=None):
        raise subprocess_exc

    import evo_replay
    import subprocess as sp
    global subprocess_exc
    subprocess_exc = sp.TimeoutExpired(cmd="x", timeout=30)
    monkeypatch.setattr(R.subprocess, "run", boom)
    avg, details = R.script_baseline_f1({}, "ddl-guard", [case])
    assert details[0]["error"] and avg == 0.0     # 无 actual → recall 0 → F1 0


# ── write_skill_proposal（产物格式）───────────────────────────────────────
def test_write_skill_proposal_lands_pending_prompt_evolution(tmp_path, monkeypatch):
    import evo_config as C
    monkeypatch.setattr(C, "base_paths", lambda cfg: {
        "pending": tmp_path / "pending", "base": tmp_path})
    best = G.Candidate(id="c3", parent="c1", gen=2, text="新 SKILL 全文")
    path = R.write_skill_proposal({}, "ddl-guard", "旧 SKILL", best, 0.6, 0.9,
                                  [{"c0": 0.6}, {"c3": 0.9}])
    body = path.read_text(encoding="utf-8")
    assert "type: prompt_evolution" in body and "status: pending" in body
    assert "gepa-replay" in path.name and "手动替换" in body
    assert "新 SKILL 全文" in body and "0.600 → evolved 0.900" in body
    assert path.parent == tmp_path / "pending"


# ── CLI 链路（--dry-run，零 LLM）──────────────────────────────────────────
def test_cmd_evolve_replay_dry_run(tmp_path, monkeypatch):
    import subprocess
    import evo_replay
    monkeypatch.setattr(evo_replay.subprocess, "run", _fake_run)
    repo = Path(__file__).resolve().parents[3]
    import evo
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval="", budget=None, seed=0, dry_run=True)
    assert evo.cmd_evolve(sys) == 0


def test_cmd_evolve_replay_unknown_skill():
    import evo
    sys = types.SimpleNamespace(
        skill="no-such-skill", eval="", budget=None, seed=0, dry_run=True)
    assert evo.cmd_evolve(sys) == 1


def test_cmd_evolve_replay_gate_fail(tmp_path, monkeypatch):
    # 门禁失败（全盘拒绝控制候选 F1 >= baseline）→ return 1，不进入 GEPA
    import subprocess
    import evo_replay
    monkeypatch.setattr(evo_replay.subprocess, "run", _fake_run)
    monkeypatch.setattr(evo_replay, "control_gate", lambda holdout: 1.0)
    import evo
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval="", budget=None, seed=0, dry_run=False)
    assert evo.cmd_evolve(sys) == 1


def test_cmd_evolve_replay_full_run(tmp_path, monkeypatch):
    # 门禁通过 + GEPA 进化 → 提案落盘 base_paths/pending，不自动 apply/commit
    import subprocess
    import evo_replay
    monkeypatch.setattr(evo_replay.subprocess, "run", _fake_run)
    monkeypatch.setattr(evo_replay, "control_gate", lambda holdout: 0.0)
    import evo
    import evo_gepa as G
    # fake run_gepa：返回 best(c1 候选) + log 含 holdout 分数，模拟改善 > 0.2
    class FakeCandidate:
        id, parent, gen, text = "c1", "c0", 1, "---\nname: ddl-guard\ndescription: d\n\n## 审查工作流\n新内容"
    def _fake_run_gepa(baseline, train, holdout, execute, reflect, budget,
                       batch_size, rng_seed, validate, asset_desc):
        assert len(train) >= 1 and len(holdout) >= 1
        return (FakeCandidate(),
                {},
                [{"holdout": {"c0": 0.5, "c1": 0.9}}, {"holdout": {"c1": 0.95}}])
    monkeypatch.setattr(evo_replay.G, "run_gepa", _fake_run_gepa)
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval="", budget=None, seed=0, dry_run=False)
    import evo_config as C
    pending = C.base_paths(C.load_config())["pending"]
    before = {f.name for f in pending.glob("*gepa-replay.md")}
    assert evo.cmd_evolve(sys) == 0
    # 本次调用新增 1 个提案（差集）；不自动 apply/commit
    after = {f.name for f in pending.glob("*gepa-replay.md")}
    props = list(after - before)
    assert len(props) == 1
    body = (pending / props[0]).read_text(encoding="utf-8")
    assert "type: prompt_evolution" in body
    assert "手动替换" in body


def test_cmd_evolve_replay_with_budget(monkeypatch):
    # --budget 设置 cfg（356 行）；dry-run 到此返回 0
    import subprocess
    import evo_replay
    monkeypatch.setattr(evo_replay.subprocess, "run", _fake_run)
    import evo
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval="", budget=8, seed=0, dry_run=True)
    assert evo.cmd_evolve(sys) == 0


def test_cmd_evolve_replay_custom_eval_dir_missing():
    # --eval 指向不存在目录 → return 1（367 行）
    import evo
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval="no-such-eval-dir", budget=None, seed=0, dry_run=False)
    assert evo.cmd_evolve(sys) == 1


def test_cmd_evolve_replay_custom_eval_dir_ok(tmp_path, monkeypatch):
    # --eval 指向自定义目录（含 1 case）→ 不足 replay_min_cases → return 1（386 行）
    import evo
    d = tmp_path / "my-eval"
    (d / "101-x" / "input").mkdir(parents=True)
    (d / "101-x" / "input" / "t.sql").write_text("x", encoding="utf-8")
    (d / "101-x" / "expected.md").write_text(
        "# c\n\n## 预期检查输出\n\n- 脚本自动检出：禁用类型\n", encoding="utf-8")
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval=str(d), budget=None, seed=0, dry_run=True)
    assert evo.cmd_evolve(sys) == 1


def test_cmd_evolve_replay_no_improvement(tmp_path, monkeypatch):
    # 进化无改善（best_score - base_score ≤ 0.2）→ 仅存报告，无提案（429 行）
    import subprocess
    import evo_replay
    monkeypatch.setattr(evo_replay.subprocess, "run", _fake_run)
    monkeypatch.setattr(evo_replay, "control_gate", lambda holdout: 0.0)
    import evo
    import evo_config as C
    pending = C.base_paths(C.load_config())["pending"]
    before = {f.name for f in pending.glob("*gepa-replay.md")}
    class FakeCandidate:
        id, parent, gen, text = "c1", "c0", 1, "---\nname: ddl-guard\ndescription: d\n\n## 审查工作流\n新内容"
    def _fake_run_gepa(baseline, train, holdout, execute, reflect, budget,
                       batch_size, rng_seed, validate, asset_desc):
        return (FakeCandidate(), {},
                [{"holdout": {"c0": 0.8, "c1": 0.85}}, {"holdout": {"c1": 0.9}}])
    monkeypatch.setattr(evo_replay.G, "run_gepa", _fake_run_gepa)
    sys = types.SimpleNamespace(
        skill="ddl-guard", eval="", budget=None, seed=0, dry_run=False)
    assert evo.cmd_evolve(sys) == 0
    after = {f.name for f in pending.glob("*gepa-replay.md")}
    assert after - before == set()   # 无新提案


def _fake_run(cmd, capture_output=True, text=True, timeout=None):
    import json
    return types.SimpleNamespace(stdout=json.dumps(
        [{"file": "x", "summary": {"total": 0, "mandatory": 0, "recommended": 0},
          "issues": []}]))


def test_extract_rules_rules_string_rejected():
    """rules 为字符串（非 list）→ 不可解析：正则层挡非 list 语法，isinstance 纵深防御。"""
    assert R.extract_rules_from_report('{"rules": "字符串"}') == ([], False)
    # 数字列表仍为 list → 放行后过滤为空（契约：结构合法即 ok=True）
    rules, ok = R.extract_rules_from_report('{"rules": [1, 2]}')
    assert ok and rules == []


def test_script_baseline_f1_nonzero_exit_recorded(monkeypatch, tmp_path):
    """检查器非零退出且输出可解析 JSON → 记 error，不得当作空结果计入基线。"""
    import types
    case = _case(cid="c1", expected=["禁用类型"], files={"a.sql": "x"})
    case = G.Case(id="c1", inputs={"input_dir": str(tmp_path), "files": {"a.sql": "x"}},
                  reference={"expected_rules": ["禁用类型"], "manual_rules": [],
                             "expected_empty": False})
    calls = []

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        calls.append(cmd)
        return types.SimpleNamespace(stdout="[]", returncode=1)

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    avg, details = R.script_baseline_f1({}, "ddl-guard", [case])
    assert len(calls) == 2 and "exit 1" in details[0]["error"]
    assert avg == 0.0


def test_script_baseline_f1_check_script_selects_matching(monkeypatch, tmp_path):
    """expected.md 声明 check: → 只跑匹配的注册脚本，无关检查器不混入。"""
    import types
    (tmp_path / "expected.md").write_text(
        "## 预期检查输出\n- check: sql_check.py\n- 脚本自动检出：禁用类型\n",
        encoding="utf-8")
    case = G.Case(id="c1", inputs={"input_dir": str(tmp_path), "files": {"a.sql": "x"}},
                  reference={"expected_rules": ["禁用类型"], "manual_rules": [],
                             "expected_empty": False})
    calls = []

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        calls.append(cmd)
        return types.SimpleNamespace(stdout="[]", returncode=0)

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    avg, details = R.script_baseline_f1({}, "ddl-guard", [case])
    assert len(calls) == 1 and calls[0][1].endswith("sql_check.py")
    assert details[0]["score"] == 0.0  # 0 actual vs 1 expected → recall 0


def test_script_baseline_f1_check_script_unregistered_fails_closed(monkeypatch, tmp_path):
    """expected.md 声明未注册脚本 → fail-closed 记 error，不静默空跑。"""
    (tmp_path / "expected.md").write_text(
        "## 预期检查输出\n- check: ghost.py\n- 脚本自动检出：禁用类型\n",
        encoding="utf-8")
    case = G.Case(id="c1", inputs={"input_dir": str(tmp_path), "files": {"a.sql": "x"}},
                  reference={"expected_rules": ["禁用类型"], "manual_rules": [],
                             "expected_empty": False})
    avg, details = R.script_baseline_f1({}, "ddl-guard", [case])
    assert "未注册" in details[0]["error"] and avg == 0.0
