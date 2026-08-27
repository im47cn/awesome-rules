"""release_guard 防呆逻辑单测——根因为 catv 0.x preMajor 与仓库惯例冲突。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_guard import bump_version, expected_bump, parse_catv_target


def C(header, body=""):
    return {"header": header, "body": body}


class TestExpectedBump:
    def test_feat_minor(self):
        assert expected_bump([C("feat(code-review): 转默认")]) == "minor"

    def test_fix_patch(self):
        assert expected_bump([C("fix: x"), C("docs: y")]) == "patch"

    def test_breaking_body_major(self):
        assert expected_bump([C("fix: x", "BREAKING CHANGE: api")]) == "major"

    def test_breaking_bang_major(self):
        assert expected_bump([C("feat!: x")]) == "major"

    def test_major_wins_over_feat(self):
        # feat 在前、breaking 在后，取最高级
        assert expected_bump([C("feat: a"), C("feat: b", "BREAKING CHANGE: c")]) == "major"

    def test_none_when_no_releasable(self):
        assert expected_bump([C("docs: x"), C("chore: y"), C("Merge pull request #1")]) is None

    def test_merge_and_nonconventional_ignored(self):
        assert expected_bump([C("Merge branch x"), C("随机中文标题")]) is None

    def test_feat_wins_over_fix(self):
        assert expected_bump([C("fix: a"), C("feat: b"), C("fix: c")]) == "minor"

    def test_revert_not_releasable(self):
        assert expected_bump([C("revert: feat xyz")]) is None


class TestBumpVersion:
    def test_from_0_4_0(self):
        assert bump_version("v0.4.0", "minor") == "0.5.0"
        assert bump_version("v0.4.0", "patch") == "0.4.1"
        assert bump_version("0.4.0", "major") == "1.0.0"

    def test_carry(self):
        assert bump_version("v0.9.9", "patch") == "0.9.10"


class TestParseCatvTarget:
    def test_normal(self):
        out = "✔ bumping version in package.json from 0.4.0 to 0.4.1\nother"
        assert parse_catv_target(out) == "0.4.1"

    def test_none(self):
        assert parse_catv_target("no match") is None


class TestRootCauseScenario:
    """2026-08-26 事故场景：区间 23 feat，catv 判 patch，期望必须 minor。"""

    def test_incident_expectation(self):
        commits = [C("feat(code-review): 可视化输出转默认")] + [C("fix: t%d" % i) for i in range(5)]
        bump = expected_bump(commits)
        assert bump == "minor"
        assert bump_version("v0.4.0", bump) == "0.5.0"
        # catv 实际目标（0.x preMajor 降级）
        assert parse_catv_target(
            "✔ bumping version in package.json from 0.4.0 to 0.4.1"
        ) == "0.4.1"
