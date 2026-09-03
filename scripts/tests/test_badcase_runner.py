"""badcase_runner strict-exact 比对分支单测。

历史缺陷（docs/design/skill-evo-replay-eval.md §3.2 required，2026-09-03 修正）：
`if strict_exact and expected_rules:` 使放行型 case（expected 为空）在 strict
模式下落入 else 分支恒 passed=True——strict 双向比对对空 expected 形同虚设，
夹具意外触发的任何规则都不显形。修正后 strict 模式无条件双向比对。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from badcase_runner import run_badcase

# 放行型 expected.md（与 skills/ddl-guard/eval/007-clean 同构：
# 「预期检查输出」小节内无「脚本自动检出」行 → expected_rules = []）
RELEASE_EXPECTED = (
    "# f.sql\n\n"
    "## 预期检查输出\n\n"
    "（本 case 无脚本自动检出项——预期检查脚本检出为空）\n"
)

# 拦截型 expected.md：声明两条脚本规则
INTERCEPT_EXPECTED = (
    "# f.sql\n\ncheck: fake_check.py\n\n"
    "## 预期检查输出\n\n"
    "- 脚本自动检出：禁用类型、表注释缺失\n"
)


def _make_case(tmp_path, expected_md, detected_rules):
    """最小 fake 技能 + 单 case 语料：fake_check.py 固定检出给定规则。"""
    root = tmp_path / "proj"
    skill = root / "skills" / "fake-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "scripts" / "fake_check.py").write_text(
        "import json\n"
        "print(json.dumps([{'issues': [{'rule': r} for r in "
        + repr(detected_rules) + "]}]))\n",
        encoding="utf-8")
    case = skill / "badcase" / "090-clean-fake"
    (case / "input").mkdir(parents=True)
    (case / "input" / "f.sql").write_text("-- fake input\n", encoding="utf-8")
    (case / "expected.md").write_text(expected_md, encoding="utf-8")
    return root, case


class TestStrictExact:
    def test_empty_expected_with_findings_fails(self, tmp_path):
        # spec:replay-eval-1 否定式条款：放行型（expected 空）strict 下
        # 实际检出规则必须 FAIL（旧逻辑落入 else 恒 passed=True，漏检）
        root, case = _make_case(tmp_path, RELEASE_EXPECTED, ["禁用类型"])
        result = run_badcase("fake-skill", "090-clean-fake", case, root,
                             strict_exact=True)
        assert result.passed is False
        assert result.unexpected_rules == ["禁用类型"]
        assert result.missing_rules == []

    def test_empty_expected_clean_stays_green(self, tmp_path):
        # spec:replay-eval-1 放行型干净输入（零检出）strict 模式保持全绿
        root, case = _make_case(tmp_path, RELEASE_EXPECTED, [])
        result = run_badcase("fake-skill", "090-clean-fake", case, root,
                             strict_exact=True)
        assert result.passed is True
        assert result.unexpected_rules == []

    def test_non_strict_empty_expected_ignores_findings(self, tmp_path):
        # 非 strict 模式不检查 unexpected 方向（语义分界：仅 strict 管双向）
        root, case = _make_case(tmp_path, RELEASE_EXPECTED, ["禁用类型"])
        result = run_badcase("fake-skill", "090-clean-fake", case, root,
                             strict_exact=False)
        assert result.passed is True
        assert result.unexpected_rules == []

    def test_non_strict_declared_rules_missing_only(self, tmp_path):
        # spec:replay-eval-1 非 strict 单向语义锚：只查 missing，多出不罚（分界）
        root, case = _make_case(tmp_path, INTERCEPT_EXPECTED,
                                ["禁用类型", "全角字符"])
        result = run_badcase("fake-skill", "090-clean-fake", case, root,
                             strict_exact=False)
        assert result.passed is False            # 表注释缺失 → missing 挂
        assert result.missing_rules == ["表注释缺失"]
        assert result.unexpected_rules == []     # 非 strict 不算 unexpected

    def test_non_strict_declared_rules_all_hit_passes(self, tmp_path):
        # spec:replay-eval-1 非 strict 全命中保持绿（既有主路径不回归）
        root, case = _make_case(tmp_path, INTERCEPT_EXPECTED,
                                ["禁用类型", "表注释缺失"])
        result = run_badcase("fake-skill", "090-clean-fake", case, root,
                             strict_exact=False)
        assert result.passed is True
        assert result.missing_rules == []

    def test_declared_rules_bidirectional(self, tmp_path):
        # spec:replay-eval-1 拦截型 strict 双向既有语义锚：漏检 + 多出未声明均 FAIL
        root, case = _make_case(tmp_path, INTERCEPT_EXPECTED,
                                ["禁用类型", "全角字符"])
        result = run_badcase("fake-skill", "090-clean-fake", case, root,
                             strict_exact=True)
        assert result.passed is False
        assert result.missing_rules == ["表注释缺失"]
        assert result.unexpected_rules == ["全角字符"]
