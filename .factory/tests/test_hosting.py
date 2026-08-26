"""hosting.py 契约测试（ADR-008）——抽象层的两条防线：

1. GitHub 适配器：中立 schema 归一化 + gh 命令构造（含 --repo 追加与
   单请求原子换标签）；gh 失败必须 HostingError（fail-closed 不静默）。
2. Codeup 适配器：请求形状（org 级端点 / comment_type+resolved 必填 /
   mergeType 枚举映射）经 mock _req 锁定；平台缺口三件套必须 exit 2
   （issue 面 / label unlink / label history）——缺口静默降级等于
   状态机半转移。

运行：python3 -m pytest .factory/tests/test_hosting.py -q
（conftest 注入 .factory 到 sys.path）
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import hosting


def _cp(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, out, err)


# ── GitHub：中立归一化 ───────────────────────────────────────────────

class TestGithubNormalize:
    def test_issue_gh_shape_to_neutral(self):
        d = {"number": 7, "state": "CLOSED", "title": "t", "body": "b",
             "labels": [{"name": "factory:accepted"}, {"name": "x"}],
             "comments": [{"author": {"login": "u"}, "body": "c"}]}
        n = hosting.GitHubAdapter._issue(d)
        assert n["state"] == "closed"
        assert n["labels"] == ["factory:accepted", "x"]
        assert n["comments"] == [{"author": "u", "body": "c"}]

    def test_pr_review_and_mergeable_map(self):
        for gh, want in [("APPROVED", "approved"),
                         ("CHANGES_REQUESTED", "changes_requested"),
                         ("REVIEW_REQUIRED", "pending"), (None, "pending")]:
            n = hosting.GitHubAdapter._pr(
                {"number": 1, "state": "OPEN", "reviewDecision": gh,
                 "mergeable": "MERGEABLE", "labels": [],
                 "headRefName": "h", "baseRefName": "b"})
            assert n["review"] == want, gh
        assert hosting.GitHubAdapter._pr(
            {"number": 1, "state": "MERGED", "mergeable": "CONFLICTING"}
        )["mergeable"] is False

    def test_gh_failure_raises_not_silent(self):
        ad = hosting.GitHubAdapter()
        ad.slug = lambda o=None: "o/r"
        ad._gh = lambda a, r=None, s=None: _cp(rc=1, err="boom")
        with pytest.raises(hosting.HostingError):
            ad.issue_view(1)


# ── GitHub：命令构造（含原子换标签）─────────────────────────────────

class TestGithubCommands:
    def _ad(self, calls):
        ad = hosting.GitHubAdapter()
        ad.slug = lambda o=None: "o/r" if o is None else o

        def fake_gh(args, repo_override=None, stdin=None):
            calls.append((tuple(args), repo_override))
            return _cp(out="{}")
        ad._gh = fake_gh
        return ad

    def test_set_labels_single_request_atomic(self):
        calls = []
        ad = self._ad(calls)
        ad.issue_set_labels(9, add=["factory:in-progress"],
                            remove=["factory:accepted"])
        # add+remove 一次 gh edit：半途断裂=双标签的窗口被消除（factory-lib 语义）
        edits = [c for c in calls if c[0][:2] == ("issue", "edit")]
        assert len(edits) == 1
        args = edits[0][0]
        assert "--remove-label" in args and "--add-label" in args

    def test_set_labels_empty_remove_omits_flag(self):
        calls = []
        ad = self._ad(calls)
        ad.issue_set_labels(9, add=["x"])
        args = [c for c in calls if c[0][:2] == ("issue", "edit")][0][0]
        assert "--remove-label" not in args  # bash 3.2 空参守卫的 py 侧等价

    def test_pr_create_overrides_repo(self):
        calls = []
        ad = self._ad(calls)
        ad._gh = lambda args, repo_override=None, stdin=None: (
            calls.append((tuple(args), repo_override)) or _cp(out="https://x/pull/12"))
        out = ad.pr_create("br", "t", "b", label="l", repo="up/stream")
        assert out["number"] == 12
        assert calls[0][1] == "up/stream"  # feedback-upstream 的上游仓显式覆盖

    def test_label_history_neutral_events(self):
        ad = hosting.GitHubAdapter()
        ad.slug = lambda o=None: "o/r"
        events = [{"event": "labeled", "label": {"name": "factory:needs-fix"}},
                  {"event": "unlabeled", "label": {"name": "factory:needs-fix"}},
                  {"event": "labeled", "label": {"name": "other"}},
                  {"event": "commented"}]
        ad._gh_raw = None
        orig = subprocess.run
        hosting.subprocess.run = lambda *a, **k: _cp(out=json.dumps(events))
        try:
            hist = ad.label_history(5)
        finally:
            hosting.subprocess.run = orig
        assert hist == [{"op": "add", "label": "factory:needs-fix"},
                        {"op": "remove", "label": "factory:needs-fix"},
                        {"op": "add", "label": "other"}]


# ── Codeup：请求形状 + 缺口 fail-closed ────────────────────────────

class TestCodeupShapes:
    def _ad(self, routes, monkeypatch):
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "t")
        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.setenv("CODEUP_REPO_ID", "42")
        """routes: {(method, path_suffix): payload}；记录全部请求（env 注入后
        _cfg/_base 可解析，请求本身被 mock 截获——零网络）。"""
        ad = hosting.CodeupAdapter()
        ad.seen = []

        def fake_req(method, path, body=None, query=None, _retry_rdc=True):
            ad.seen.append((method, path, body, query))
            for (m, suf), payload in routes.items():
                if m == method and path.endswith(suf):
                    return payload
            raise hosting.HostingError(f"mock 未路由: {method} {path}")
        ad._req = fake_req
        return ad

    def test_pr_view_review_normalization(self, monkeypatch):
        ad = self._ad({("GET", "/changeRequests/3"): {
            "result": {"localId": 3, "newVersionState": "UNDER_REVIEW",
                       "reviewers": [{"reviewOpinionStatus": "NOT_PASS"}],
                       "labels": [{"name": "factory:needs-fix"}],
                       "sourceBranch": "s", "targetBranch": "t",
                       "title": "T", "description": "D"}}}, monkeypatch)
        n = ad.pr_view(3)
        assert n["review"] == "changes_requested"
        assert n["state"] == "open"
        assert n["labels"] == ["factory:needs-fix"]
        assert n["head"] == "s" and n["base"] == "t"

        ad2 = self._ad({("GET", "/changeRequests/4"): {
            "result": {"localId": 4, "newVersionState": "MERGED",
                       "reviewers": [{"reviewOpinionStatus": "PASS"},
                                     {"reviewOpinionStatus": "PASS"}]}}}, monkeypatch)
        n2 = ad2.pr_view(4)
        assert n2["review"] == "approved" and n2["state"] == "merged"

    def test_pr_comment_required_fields(self, monkeypatch):
        ad = self._ad({("POST", "/comments"): {"success": True}}, monkeypatch)
        ad.pr_comment(5, "LGTM")
        m, p, body, _q = ad.seen[0]
        assert m == "POST" and p.endswith("/changeRequests/5/comments")
        # 【实测】坑位锁定：comment_type 无默认值且 resolved 必填
        assert body["comment_type"] == "GLOBAL_COMMENT"
        assert body["resolved"] is True
        assert body["content"] == "LGTM"

    def test_pr_merge_method_enum(self, monkeypatch):
        ad = self._ad({("POST", "/merge"): {"success": True, "result": True}}, monkeypatch)
        ad.pr_merge(6, method="squash")
        m, p, body, _q = ad.seen[0]
        assert p.endswith("/changeRequests/6/merge")
        assert body["mergeType"] == "squash"

    def test_pr_list_filters_state_and_label(self, monkeypatch):
        page = {"result": [
            {"localId": 1, "newVersionState": "UNDER_REVIEW",
             "labels": [{"name": "factory:needs-fix"}]},
            {"localId": 2, "newVersionState": "MERGED", "labels": []},
            {"localId": 3, "newVersionState": "TO_BE_MERGED",
             "labels": [{"name": "factory:approved"}]},
        ]}
        ad = self._ad({("GET", "/changeRequests"): page}, monkeypatch)
        prs = ad.pr_list(state="open", label=None, limit=10)
        assert [p["number"] for p in prs] == [1, 3]  # MERGED 被滤出 open 集
        only = ad.pr_list(state="open", label="factory:needs-fix", limit=10)
        assert [p["number"] for p in only] == [1]

    def test_label_link_resolves_name_to_id(self, monkeypatch):
        ad = self._ad({
            ("GET", "/labels"): {"result": [
                {"id": "lbl-9", "name": "factory:needs-review"}]},
            ("POST", "/changeRequests/7/labels"): {"success": True}}, monkeypatch)
        ad.pr_set_labels(7, add=["factory:needs-review"])
        link = [s for s in ad.seen if s[0] == "POST" and "labels" in s[1]][0]
        assert link[2] == {"labelIds": ["lbl-9"]}


class TestCodeupGaps:
    """平台缺口三件套必须 fail-closed（exit 2），静默降级=状态机半转移。"""

    def _ad(self, monkeypatch):
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "t")
        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.setenv("CODEUP_REPO_ID", "42")
        ad = hosting.CodeupAdapter()
        ad._req = lambda *a, **k: {"success": True, "result": []}
        return ad

    @pytest.mark.parametrize("fn", [
        lambda ad: ad.issue_view(1),
        lambda ad: ad.issue_list(),
        lambda ad: ad.issue_set_labels(1, add=["x"]),
        lambda ad: ad.issue_create("t", "b"),
        lambda ad: ad.label_history(2),
        lambda ad: ad.pr_set_labels(2, remove=["x"]),
        lambda ad: ad.pr_diff(2),
    ])
    def test_unsupported_ops_exit2(self, fn, monkeypatch):
        with pytest.raises(hosting.HostingError) as e:
            fn(self._ad(monkeypatch))
        assert e.value.code == 2
        assert "ADR-008" in str(e.value)


class TestCodeupEndpointFallback:
    """【实测】默认端点受限网络 TLS 静默丢弃 → 中心版端点一次重试。"""

    def test_urLError_retries_rdc(self, monkeypatch):
        ad = hosting.CodeupAdapter()
        calls = []

        class _Err(Exception):
            pass

        import urllib.error as ue
        monkeypatch.setattr(hosting.urllib.request, "urlopen",
                            lambda req, timeout=None: (_ for _ in ()).throw(
                                ue.URLError("tls dropped")))
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "t")
        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.setenv("CODEUP_REPO_ID", "42")
        with pytest.raises(hosting.HostingError) as e:
            ad._req("GET", "/oapi/v1/codeup/organizations/org/repositories/42")
        # 两次都失败才报错；且报错信息指向重试后的端点
        assert "openapi-rdc.aliyuncs.com" in str(e.value)


class TestCli:
    def test_codeup_issue_view_cli_fails_closed(self, tmp_path):
        r = subprocess.run(
            [sys.executable, str(Path(hosting.__file__).resolve()),
             "issue", "view", "1"],
            capture_output=True, text=True,
            env={"FACTORY_HOSTING": "codeup", "PATH": "/usr/bin:/bin",
                 "YUNXIAO_ACCESS_TOKEN": "t", "CODEUP_ORG_ID": "o",
                 "CODEUP_REPO_ID": "1"})
        assert r.returncode == 2
        assert "ADR-008" in r.stderr

    def test_platform_select_unknown(self):
        with pytest.raises(hosting.HostingError) as e:
            hosting.FACTORY_HOSTING = "gitlab"
            try:
                hosting.current_adapter()
            finally:
                hosting.FACTORY_HOSTING = "github"
        assert e.value.code == 2
