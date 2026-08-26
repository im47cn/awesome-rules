#!/usr/bin/env python3
"""forge（ADR-007 平台适配层）单元测试——零网络：形状映射/argv 解析/
jq 投影/marker 标签推导/配置 fail-closed。

网络路径（Codeup REST）不在单测覆盖面：契约由「端到端验证 Codeup 链路」
冒烟（真实仓只读 + 标记评论创建/回收）承担。
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
_loader = SourceFileLoader("forge", str(HERE / "forge"))
_spec = importlib.util.spec_from_loader("forge", _loader)
forge = importlib.util.module_from_spec(_spec)
_loader.exec_module(forge)


# ── html_to_text：description JSON 串与裸 HTML 双形态 ──────────────────

def test_html_to_text_json_wrapper():
    d = json.dumps({"htmlValue": "<p>fix <b>sign</b> filter</p>"})
    assert forge.html_to_text(d) == "fix sign filter"


def test_html_to_text_plain():
    assert forge.html_to_text("<a>x</a>  y") == "x y"
    assert forge.html_to_text(None) == ""
    assert forge.html_to_text("") == ""


def test_html_to_text_non_json_brace():
    # 以 { 开头但非 JSON：原样走标签剥离，不崩
    assert "k" in forge.html_to_text("{ok <b>b</b>")


# ── marker 标签模型：PR 侧标签 = 评论标记投影 ─────────────────────────

def _c(content, resolved=False):
    return {"content": content, "resolved": resolved,
            "comment_biz_id": "biz" + content[-4:]}


def test_marker_labels_basic():
    cs = [_c("[factory:label:add] factory:needs-review"),
          _c("[factory:label:add] factory:approved", resolved=True)]
    assert forge.marker_labels(cs) == ["factory:needs-review"]


def test_marker_labels_dedupe_and_ignore_non_marker():
    cs = [_c("[factory:label:add] factory:needs-fix"),
          _c("[factory:label:add] factory:needs-fix"),
          _c("普通评论")]
    assert forge.marker_labels(cs) == ["factory:needs-fix"]


def test_marker_labels_html_content():
    cs = [{"content": "<p>[factory:label:add] factory:needs-review</p>",
           "resolved": False}]
    assert forge.marker_labels(cs) == ["factory:needs-review"]


# ── reviewDecision：TO_BE_MERGED / 标记评论 / 无 ──────────────────────

def test_review_decision_merged():
    assert forge.review_decision({"status": "TO_BE_MERGED"}, []) == "APPROVED"


def test_review_decision_changes_requested_marker():
    cs = [_c("[factory:changes-requested] 打回：证据不足")]
    assert forge.review_decision({"status": "UNDER_REVIEW"}, cs) == "CHANGES_REQUESTED"


def test_review_decision_none():
    assert forge.review_decision({"status": "UNDER_REVIEW"}, []) == ""


# ── MR → PR 形状 ──────────────────────────────────────────────────────

def test_mr_to_pr_shape():
    mr = {"localId": 3, "status": "UNDER_REVIEW", "sourceBranch": "factory/issue-KFPT-16",
          "targetBranch": "develop", "conflictCheckStatus": "NO_CONFLICT",
          "description": json.dumps({"htmlValue": "Closes #KFPT-16"})}
    comments = [_c("[factory:label:add] factory:needs-review")]
    pr = forge.mr_to_pr(mr, comments, want_body=True)
    assert pr["number"] == 3
    assert pr["state"] == "OPEN"
    assert pr["headRefName"] == "factory/issue-KFPT-16"
    assert pr["baseRefName"] == "develop"
    assert pr["mergeable"] == "MERGEABLE"
    assert [l["name"] for l in pr["labels"]] == ["factory:needs-review"]
    assert pr["body"] == "Closes #KFPT-16"


def test_mr_to_pr_closed_state():
    pr = forge.mr_to_pr({"localId": 1, "status": "MERGED"}, [], want_body=False)
    assert pr["state"] == "CLOSED"


# ── 工作项 → issue 形状 ───────────────────────────────────────────────

def test_wi_to_issue_shape():
    wi = {"id": "abc123", "serialNumber": "KFPT-16", "subject": "修过滤器",
          "description": json.dumps({"htmlValue": "<p>正文</p>"}),
          "labels": ["factory:accepted"], "logicalStatus": "NORMAL"}
    out = forge.wi_to_issue(wi, None, want_comments=False)
    assert out["number"] == "KFPT-16"
    assert out["state"] == "OPEN"
    assert out["labels"] == [{"name": "factory:accepted"}]
    assert out["body"] == "正文"
    assert "comments" not in out


def test_wi_state_finished():
    assert forge.wi_state({"logicalStatus": "FINISHED"}) == "CLOSED"
    assert forge.wi_state({"logicalStatus": "NORMAL"}) == "OPEN"
    assert forge.wi_state({}) == "OPEN"  # 缺字段按 OPEN（保守：不误清标签）


# ── argv 解析：fail-closed 与 -q 别名 ─────────────────────────────────

def test_parse_argv_unknown_flag_rejected(capsys):
    try:
        forge.parse_argv(["issue", "view", "1", "--frobnicate", "x"])
        assert False, "未知标志必须 exit 2"
    except SystemExit as e:
        assert e.code == forge.EXIT_USAGE


def test_parse_argv_q_alias():
    cmd, pos, flags, fields, jq = forge.parse_argv(
        ["issue", "view", "KFPT-16", "--json", "labels", "-q", ".labels[].name"])
    assert cmd == "issue" and pos == ["view", "KFPT-16"]
    assert fields == ["labels"]
    assert jq == ".labels[].name"


def test_parse_argv_merge_flag_valueless():
    cmd, pos, flags, fields, jq = forge.parse_argv(
        ["pr", "merge", "3", "--merge", "--admin"])
    assert flags["--merge"] == ["true"] and flags["--admin"] == ["true"]


# ── jq 投影：两个已契约表达式，其他 fail-closed ────────────────────────

def test_apply_jq_closing():
    rows = [{"closingIssuesReferences": [{"number": "KFPT-16"}]},
            {"closingIssuesReferences": []}]
    assert forge._apply_jq(".[].closingIssuesReferences[].number", rows) == ["KFPT-16"]


def test_apply_jq_labels():
    assert forge._apply_jq(".labels[].name",
                           {"labels": [{"name": "a"}, {"name": "b"}]}) == ["a", "b"]


def test_apply_jq_reject_unknown(capsys):
    for bad in (".foo", ".[].x[].y"):
        try:
            forge._apply_jq(bad, {})
            assert False, f"{bad} 必须拒绝"
        except SystemExit as e:
            assert e.code == forge.EXIT_USAGE


# ── 配置解析：forge.json 缺失=github；损坏/缺键 fail-closed ───────────

def test_load_cfg_missing_file_is_github(tmp_path):
    assert forge.load_cfg(tmp_path) == {"backend": "github"}


def test_load_cfg_codeup_missing_keys(tmp_path):
    (tmp_path / ".factory").mkdir()
    (tmp_path / ".factory" / "forge.json").write_text(
        json.dumps({"backend": "codeup", "codeup": {"org_id": "1"}}))
    try:
        forge.load_cfg(tmp_path)
        assert False, "缺键必须 exit 2"
    except SystemExit as e:
        assert e.code == forge.EXIT_USAGE


def test_load_cfg_corrupt(tmp_path):
    (tmp_path / ".factory").mkdir()
    (tmp_path / ".factory" / "forge.json").write_text("{not json")
    try:
        forge.load_cfg(tmp_path)
        assert False
    except SystemExit as e:
        assert e.code == forge.EXIT_USAGE


def test_load_cfg_codeup_ok(tmp_path):
    (tmp_path / ".factory").mkdir()
    (tmp_path / ".factory" / "forge.json").write_text(json.dumps({
        "backend": "codeup",
        "codeup": {"org_id": "o", "repo_id": "r", "space_id": "s",
                   "workitem_type_id": "t", "base_branch": "develop"}}))
    cfg = forge.load_cfg(tmp_path)
    assert cfg["codeup"]["base_branch"] == "develop"


# ── github 后端零配置探测（probe 子命令，CLI 级）──────────────────────

def test_cli_probe_github_when_no_forge_json(tmp_path):
    """上游形态：forge.json 缺失 → probe 输出 github（不依赖 gh 存在）。"""
    r = subprocess.run(
        [sys.executable, str(HERE / "forge"), "probe"],
        capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.strip() == "github"


# ── issue 标签描述标记载体（ADR-007：Task 类型无 labels 字段的等价物）──

def test_desc_labels_parse():
    raw = "<p>正文</p>\n\n<!-- factory:labels:v1: factory:accepted priority:high -->"
    assert forge._desc_labels(raw) == ["factory:accepted", "priority:high"]


def test_desc_labels_empty_variants():
    assert forge._desc_labels(None) == []
    assert forge._desc_labels("<p>无块</p>") == []
    assert forge._desc_labels("<!-- factory:labels:v1: -->") == []


def test_desc_set_labels_roundtrip():
    raw = "<p>正文</p>"
    out = forge._desc_set_labels(raw, ["b", "a"])
    assert out == "<p>正文</p>\n\n<!-- factory:labels:v1: a b -->"
    assert forge._desc_labels(out) == ["a", "b"]


def test_desc_set_labels_replaces_old_block_and_removes_when_empty():
    raw = "旧正文\n\n<!-- factory:labels:v1: x -->"
    out = forge._desc_set_labels(raw, ["y"])
    assert "x -->" not in out and forge._desc_labels(out) == ["y"]
    assert forge._desc_set_labels(raw, []) == "旧正文"


def test_wi_labels_description_mode():
    wi = {"description": "<p>b</p><!-- factory:labels:v1: factory:accepted -->"}
    assert forge.wi_labels(wi, "description") == [{"name": "factory:accepted"}]
    assert forge.wi_labels({"labels": ["a"]}, "native") == [{"name": "a"}]


def test_wi_to_issue_body_strips_marker():
    wi = {"id": "x", "serialNumber": "KFPT-1", "subject": "s",
          "description": "<p>正文</p><!-- factory:labels:v1: a -->",
          "logicalStatus": "NORMAL"}
    out = forge.wi_to_issue(wi, None, want_comments=False)
    # cx=None → native 模式：描述块不进标签；标记被剥离、正文干净
    assert out["labels"] == []
    assert "factory:labels" not in out["body"] and out["body"] == "正文"
