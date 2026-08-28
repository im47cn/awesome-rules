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
                       "sourceBranch": "s", "targetBranch": "t",
                       "title": "T", "description": "D"}},
            # 【live 2026-08-26】MR 详情无 labels 字段，类标专用端点读回
            ("GET", "/changeRequests/3/labels"): [
                {"name": "factory:needs-fix"}],
            # #66 评论标记模型：pr_view 兼查标记评论（空集 = 无标记）
            ("POST", "/comments/list"): {"result": []}}, monkeypatch)
        n = ad.pr_view(3)
        assert n["review"] == "changes_requested"
        assert n["state"] == "open"
        assert n["labels"] == ["factory:needs-fix"]
        assert n["head"] == "s" and n["base"] == "t"

        ad2 = self._ad({("GET", "/changeRequests/4"): {
            "result": {"localId": 4, "newVersionState": "MERGED",
                       "reviewers": [{"reviewOpinionStatus": "PASS"},
                                     {"reviewOpinionStatus": "PASS"}]}},
            ("POST", "/comments/list"): {"result": []}}, monkeypatch)
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

    def test_pr_close_post_empty_body(self, monkeypatch):
        """live 契约：唯一生效形态 = POST /close 空 body；PUT 详情带
        state=closed 是假阳性（result:true 但状态不变）——MR#7 实测。"""
        ad = self._ad({("POST", "/close"): {"result": True}}, monkeypatch)
        ad.pr_close(7)
        m, p, body, _q = ad.seen[0]
        assert (m, p) == ("POST", ad._base() + "/changeRequests/7/close")
        assert body == {}  # 空 body；PUT /changeRequests/7 假阳性形态禁用

    def test_pr_close_github_uses_gh(self, monkeypatch):
        """GitHub 侧 pr_close → gh pr close（_gh 内部按 slug 追加 --repo，
        这里只断言子命令形状）。"""
        calls = []

        def fake(_self, args, repo_override=None, stdin=None):
            calls.append(args)
            return type("R", (), {"returncode": 0, "stderr": "",
                                  "stdout": ""})()
        monkeypatch.setattr(hosting.GitHubAdapter, "_gh", fake)
        assert hosting.GitHubAdapter().pr_close(9) is True
        assert calls[0] == ["pr", "close", "9"]

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
            # #66 标记模型：add 先发标记评论，类标 Link 为补充载体
            ("POST", "/comments"): {"success": True},
            ("POST", "/changeRequests/7/labels"): {"success": True}}, monkeypatch)
        ad.pr_set_labels(7, add=["factory:needs-review"])
        marker = [s for s in ad.seen if s[0] == "POST"
                  and s[1].endswith("/comments")][0]
        assert marker[2]["content"] == "[factory:label:add] factory:needs-review"
        assert marker[2]["resolved"] is False
        link = [s for s in ad.seen if s[0] == "POST" and "labels" in s[1]][0]
        assert link[2] == {"labelIdList": ["lbl-9"]}  # live 破案键名（labelIds 拒）


class TestCodeupGaps:
    """平台缺口收敛后仍 fail-closed（exit 2）的操作集。"""

    def _ad(self, monkeypatch):
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "t")
        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.setenv("CODEUP_REPO_ID", "42")
        ad = hosting.CodeupAdapter()
        ad._req = lambda *a, **k: {"success": True, "result": []}
        return ad

    # 缺口 (b)(c) 已由评论标记模型承载（#66）；真缺口仅剩 diff 全文
    @pytest.mark.parametrize("fn", [
        lambda ad: ad.pr_diff(2),
    ])
    def test_unsupported_ops_exit2(self, fn, monkeypatch):
        with pytest.raises(hosting.HostingError) as e:
            fn(self._ad(monkeypatch))
        assert e.value.code == 2
        assert "ADR-008" in str(e.value)


class TestCodeupMarkerModel:
    """#66 评论标记模型：add/remove 序列、label_history 轮次语义、
    changes-requested 手势映射。"""

    def _ad(self, monkeypatch, comments_by_resolved):
        """comments_by_resolved: {False: [未resolved评论], True: [已resolved评论]}
        自定义 mock 按 body['resolved'] 分流（_ad 简单路由无法区分两态）。"""
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "t")
        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.setenv("CODEUP_REPO_ID", "42")
        ad = hosting.CodeupAdapter()
        ad.seen = []

        def fake_req(method, path, body=None, query=None, _retry_rdc=True):
            ad.seen.append((method, path, body, query))
            if method == "POST" and path.endswith("/comments/list"):
                return {"result": comments_by_resolved.get(
                    (body or {}).get("resolved"), [])}
            return {"success": True, "result": []}
        ad._req = fake_req
        return ad

    def test_remove_resolves_marker_keeps_content(self, monkeypatch):
        """remove = 置 resolved（PUT comments/{id}），内容保留——轮次不减。"""
        ad = self._ad(monkeypatch, {False: [
            {"id": "c-1", "content": "[factory:label:add] factory:needs-fix"},
            {"id": "c-2", "content": "[factory:label:add] factory:approved"}]})
        ad.pr_set_labels(7, remove=["factory:needs-fix"])
        puts = [s for s in ad.seen if s[0] == "PUT"]
        assert len(puts) == 1  # 只 resolve needs-fix，approved 不动
        assert puts[0][1].endswith("/changeRequests/7/comments/c-1")
        assert puts[0][2] == {"resolved": True}

    def test_remove_idempotent_no_marker(self, monkeypatch, capsys):
        ad = self._ad(monkeypatch, {})
        assert ad.pr_set_labels(7, remove=["x"]) is True
        assert not [s for s in ad.seen if s[0] == "PUT"]
        assert "幂等跳过" in capsys.readouterr().err

    def test_pr_labels_merges_two_carriers(self, monkeypatch):
        """labels = 类标 Link ∪ 未 resolved 标记（两载体合并去重）。"""
        ad = self._ad(monkeypatch, {False: [
            {"id": "c-1", "content": "[factory:label:add] factory:needs-fix"}]})

        real_req = ad._req

        def fake_req(method, path, body=None, query=None, _retry_rdc=True):
            if method == "GET" and path.endswith("/labels"):
                return [{"name": "factory:needs-fix"}, {"name": "factory:extra"}]
            return real_req(method, path, body, query, _retry_rdc)
        ad._req = fake_req
        assert ad._pr_labels(7) == ["factory:extra", "factory:needs-fix"]

    def test_label_history_resolved_does_not_decrease(self, monkeypatch):
        """轮次语义：resolved 不减计数——全部 add 标记都计入事件流。"""
        ad = self._ad(monkeypatch, {
            False: [{"id": "c-2", "content": "[factory:label:add] factory:needs-fix"}],
            True: [{"id": "c-1", "content": "[factory:label:add] factory:needs-fix"}]})
        hist = ad.label_history(7)
        assert hist == [{"op": "add", "label": "factory:needs-fix"},
                        {"op": "add", "label": "factory:needs-fix"}]

    def test_changes_requested_gesture_maps_review(self, monkeypatch):
        """[factory:changes-requested] 评论 → changes_requested（无
        reviewDecision 等价物场景）；reviewer PASS 映射不覆盖手势。"""
        ad = self._ad(monkeypatch, {False: [
            {"id": "c-9", "content": "[factory:changes-requested] 命名漂移"}]})

        real_req = ad._req

        def fake_req(method, path, body=None, query=None, _retry_rdc=True):
            if method == "GET" and path.endswith("/changeRequests/5"):
                return {"result": {"localId": 5, "newVersionState": "TO_BE_MERGED",
                                   "reviewers": [{"reviewOpinionStatus": "PASS"}]}}
            if method == "GET" and path.endswith("/labels"):
                return []
            return real_req(method, path, body, query, _retry_rdc)
        ad._req = fake_req
        n = ad.pr_view(5)
        assert n["review"] == "changes_requested"  # 手势取严于 reviewer PASS



class TestCodeupWorkItemFace:
    """#67 工作项面五方法（live 已验形态;forge 参考实现迁移）。"""

    WI_DESC = json.dumps({"htmlValue":
                           "<p>正文</p>\n<!-- factory:labels:v1: factory:accepted -->"},
                          ensure_ascii=False)
    WI = {"result": {"id": "wid1", "serialNumber": "KFPT-18",
                     "subject": "标题", "logicalStatus": "NORMAL",
                     "description": WI_DESC,
                     "labels": None},
          "_comments": [{"author": {"name": "纪柏涛"}, "content": "<p>早</p>"}]}

    def _ad(self, monkeypatch, routes=None, env=None):
        for k, v in {**{"YUNXIAO_ACCESS_TOKEN": "t", "CODEUP_ORG_ID": "org",
                        "CODEUP_REPO_ID": "42", "CODEUP_SPACE_ID": "sp1"}, **(env or {})}.items():
            monkeypatch.setenv(k, v)
        ad = hosting.CodeupAdapter()
        ad.seen = []
        base = routes or {}
        def fake_req(method, path, body=None, query=None, _retry_rdc=True):
            ad.seen.append((method, path, body, query))
            for (m, suf), payload in base.items():
                if m == method and path.endswith(suf):
                    return payload
            if path.endswith("/comments"):
                return self.WI["_comments"]
                if m == method and path.endswith(suf):
                    return payload
            if path.endswith("/workitems/KFPT-18") or path.endswith("/workitems/wid1"):
                return self.WI["result"]
            if path.endswith("/workitems:search"):
                return {"result": [self.WI["result"], {"id": "wid2", "serialNumber": "KFPT-19",
                              "subject": "旧", "logicalStatus": "FINISHED", "description": ""}]}
            raise hosting.HostingError(f"mock 未路由: {method} {path}")
        ad._req = fake_req
        return ad

    def test_issue_view_normalizes_and_strips_marker(self, monkeypatch):
        monkeypatch.setenv("CODEUP_ISSUE_LABELS", "description")
        ad = self._ad(monkeypatch)
        n = ad.issue_view("KFPT-18")
        assert n["number"] == "KFPT-18" and n["state"] == "open"
        assert n["title"] == "标题"
        assert n["body"] == "正文"           # HTML 剥离 + 标记块剥离
        assert "factory:labels" not in n["body"]
        assert n["labels"] == ["factory:accepted"]  # description 载体解析
        assert n["comments"] == [{"author": "纪柏涛", "body": "早"}]

    def test_issue_view_native_labels(self, monkeypatch):
        wi = {**self.WI["result"], "labels": ["factory:rejected"], "description": ""}
        ad = self._ad(monkeypatch, routes={("GET", "/workitems/KFPT-16"): wi})
        assert ad.issue_labels("KFPT-16") == ["factory:rejected"]

    def test_issue_list_paginates_filters_state_and_label(self, monkeypatch):
        monkeypatch.setenv("CODEUP_ISSUE_LABELS", "description")
        ad = self._ad(monkeypatch)
        out = ad.issue_list(state="open", label="factory:accepted", limit=10)
        assert [i["number"] for i in out] == ["KFPT-18"]  # FINISHED 滤出+label 过滤
        m, p, body, _q = ad.seen[0]
        assert (m, p.endswith("/workitems:search")) == ("POST", True)
        assert body["category"] == "Task" and body["spaceId"] == "sp1"  # category 必填（live）

    def test_issue_list_requires_space_env(self, monkeypatch):
        monkeypatch.delenv("CODEUP_SPACE_ID", raising=False)
        ad = hosting.CodeupAdapter()
        ad._req = lambda *a, **k: {}
        with pytest.raises(hosting.HostingError) as e:
            ad.issue_list()
        assert e.value.code == 2

    def test_issue_set_labels_native_put(self, monkeypatch):
        wi = {**self.WI["result"], "labels": ["keep"]}
        ad = self._ad(monkeypatch, routes={("GET", "/workitems/KFPT-18"): wi})
        ad.issue_set_labels("KFPT-18", add=["factory:triaging"], remove=["keep"])
        put = [s for s in ad.seen if s[0] == "PUT"][-1]
        assert put[2] == {"labels": ["factory:triaging"]}  # 排序去重

    def test_issue_set_labels_description_rw(self, monkeypatch):
        monkeypatch.setenv("CODEUP_ISSUE_LABELS", "description")
        ad = self._ad(monkeypatch)
        ad.issue_set_labels("KFPT-18", add=["factory:in-progress"])
        put = [s for s in ad.seen if s[0] == "PUT"][-1]
        assert put[2]["formatType"] == "MARKDOWN"
        # 读-改-写保留原始载体格式（JSON 串不解包）:原 accepted 保留+新增
        # 原文字面 \n（json 转义）保留;块前是真换行（实现拼接语义）
        assert put[2]["description"] == (
            '{"htmlValue": "<p>正文</p>\\n"}'
            '\n\n<!-- factory:labels:v1: factory:accepted factory:in-progress -->')
        # 移除唯一标签 = 块消失,原文保留
        ad2 = self._ad(monkeypatch)
        ad2.issue_set_labels("KFPT-18", remove=["factory:accepted"])
        put2 = [s for s in ad2.seen if s[0] == "PUT"][-1]
        assert put2[2]["description"] == '{"htmlValue": "<p>正文</p>\\n"}'

    def test_issue_comment_uses_id_and_marker_dedupe(self, monkeypatch, capsys):
        monkeypatch.setenv("CODEUP_ISSUE_LABELS", "description")
        ad = self._ad(monkeypatch, routes={
            ("GET", "/workitems/wid1/comments"): [
                {"author": {"name": "x"}, "content": "<p>旧<!-- m1 --></p>"}]})
        assert ad.issue_comment("KFPT-18", "回执", marker="m1") is True  # dedupe 命中
        assert "dedupe" in capsys.readouterr().err
        posts = [s for s in ad.seen if s[0] == "POST"]
        assert not posts
        ad.issue_comment("KFPT-18", "新评论")
        posts = [s for s in ad.seen if s[0] == "POST"]
        assert posts[-1][1].endswith("/workitems/wid1/comments")  # serialNumber→id
        assert posts[-1][2]["contentType"] == "markdown"


class TestCodeupIssueCreate:
    """issue create 实装契约（forge 实装迁移,PR #62 实测破案）:
    本体 4 必填 + customFieldValues 平面对象 + 缺 env fail-closed。"""

    ENV = {"CODEUP_SPACE_ID": "sp1", "CODEUP_WORKITEM_TYPE_ID": "wt9",
           "CODEUP_ASSIGN_USER_ID": "0123456789abcdef01234567"}

    FIELDS = {"result": [
        {"id": 1, "name": "标题", "required": True, "type": "NativeField"},
        {"id": 79, "name": "计划开始时间", "required": True, "format": "date"},
        {"id": 80, "name": "计划结束时间", "required": True, "format": "date"},
        {"id": 101586, "name": "预计工时", "required": True, "format": "float"},
        {"id": 6, "name": "优先级", "required": True,
         "options": [{"id": 11}, {"id": 22}]},
        {"id": 7, "name": "可选字段", "required": False},
    ]}

    def _ad(self, monkeypatch, fields=None, create_resp=None,
            detail_resp=None, fail_fields=False, fail_detail=False):
        for k, v in {**{"YUNXIAO_ACCESS_TOKEN": "t", "CODEUP_ORG_ID": "org",
                        "CODEUP_REPO_ID": "42"}, **self.ENV}.items():
            monkeypatch.setenv(k, v)
        ad = hosting.CodeupAdapter()
        calls = []

        def fake_req(method, path, body=None, query=None, _retry_rdc=True):
            calls.append((method, path, body))
            if "workitemTypes" in path:  # 字段配置发现端点
                if fail_fields:
                    raise hosting.HostingError("codeup GET fields HTTP 404: x")
                return fields if fields is not None else self.FIELDS
            # 【live 2026-08-26】create 响应只含 24-hex id（无 serialNumber/
            # detailUrl）——KFPT-21 实测；详情回查才有可读编号
            if method == "POST" and path.endswith("/workitems"):
                return create_resp or {"result": {"id": "wid123"}}
            if fail_detail:
                raise hosting.HostingError("codeup GET detail HTTP 500: x")
            return detail_resp or {"result": {"serialNumber": "KFPT-42",
                                              "detailUrl": "https://x/KFPT-42"}}

        ad._req = fake_req
        return ad, calls

    def test_missing_env_fail_closed(self, monkeypatch):
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "t")
        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.delenv("CODEUP_SPACE_ID", raising=False)
        ad = hosting.CodeupAdapter()
        with pytest.raises(hosting.HostingError) as e:
            ad.issue_create("t", "b")
        assert e.value.code == 2
        assert "CODEUP_SPACE_ID" in str(e.value)

    def test_create_payload_shape(self, monkeypatch):
        ad, calls = self._ad(monkeypatch)
        out = ad.issue_create("标题", "正文", label="factory:triaging")
        posts = [c for c in calls if c[0] == "POST" and c[1].endswith("/workitems")]
        m, path, body = posts[-1]  # 回查 GET 在 POST 后,calls[-1] 已非 POST
        assert (m, path) == ("POST", "/oapi/v1/projex/organizations/org/workitems")
        assert body["spaceId"] == "sp1" and body["workitemTypeId"] == "wt9"
        assert body["subject"] == "标题"
        assert body["assignedTo"] == "0123456789abcdef01234567"
        # label 载体 = description 尾部 HTML 注释块（云效 Task 常无 labels
        # 字段，ADR-007 实测；PR #64 审查 F1 修复）
        assert body["description"].startswith("正文")
        assert "<!-- factory:labels:v1: factory:triaging -->" in body["description"]
        assert "labels" not in body  # 不再直写 labels 字段（真实平台 400）
        cfvs = body["customFieldValues"]
        # 平面对象 {"fieldId": "value"}（数组形态 = Invalid format 实测）
        assert isinstance(cfvs, dict)
        assert cfvs["79"].endswith("-") or len(cfvs["79"]) == 10  # date ISO
        assert cfvs["101586"] == "0.5"  # float=小数字符串
        assert cfvs["6"] == "22"  # list=末档 option id（str）
        assert 1 not in cfvs and "1" not in cfvs  # NativeField 走本体
        assert 7 not in cfvs and "7" not in cfvs  # 非 required 不带
        assert out == {"number": "KFPT-42", "url": "https://x/KFPT-42"}

    def test_fields_fetch_failure_degrades_with_warning(self, monkeypatch, capsys):
        ad, calls = self._ad(monkeypatch, fail_fields=True)
        out = ad.issue_create("t", "b")
        assert "warn" in capsys.readouterr().err  # 降级可见不静默
        posts = [c for c in calls if c[0] == "POST" and c[1].endswith("/workitems")]
        assert posts and "customFieldValues" not in posts[-1][2]  # POST 仍发出
        assert out["number"] == "KFPT-42"

    def test_create_returns_serial_via_detail_lookup(self, monkeypatch):
        """live 契约：create 响应仅 24-hex id；serialNumber 由详情回查取得。"""
        ad, calls = self._ad(monkeypatch)
        out = ad.issue_create("t", "b")
        gets = [(m, p) for m, p, _b in calls if m == "GET"]
        assert any(p.endswith("/workitems/wid123") for _m, p in gets), \
            "必须回查详情端点"
        assert out == {"number": "KFPT-42", "url": "https://x/KFPT-42"}

    def test_detail_lookup_failure_degrades_to_id(self, monkeypatch, capsys):
        """回查失败降级返回 id + stderr 告警（可读性损失可见，不阻断）。"""
        ad, _calls = self._ad(monkeypatch, fail_detail=True)
        out = ad.issue_create("t", "b")
        assert out["number"] == "wid123"
        assert "serialNumber" in capsys.readouterr().err

    def test_create_resp_with_serial_still_wins(self, monkeypatch):
        """若平台未来在 create 响应补 serialNumber：有 id 仍回查（详情
        是 detailUrl 权威源）；无 id 才直取响应字段。"""
        ad, _calls = self._ad(
            monkeypatch, create_resp={"result": {"serialNumber": "KFPT-9"}})
        out = ad.issue_create("t", "b")
        # create 无 id → 不回查，直接响应字段
        assert out["number"] == "KFPT-9"


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
        """#67 后 issue view 已实装：CLI 边界=无凭据/网络失败 fail-closed
        非零（假 token → 401 → HostingError），不再是无条件 unsupported。"""
        r = subprocess.run(
            [sys.executable, str(Path(hosting.__file__).resolve()),
             "issue", "view", "1"],
            capture_output=True, text=True,
            env={"FACTORY_HOSTING": "codeup", "PATH": "/usr/bin:/bin",
                 "YUNXIAO_ACCESS_TOKEN": "t", "CODEUP_ORG_ID": "o",
                 "CODEUP_REPO_ID": "1"})
        assert r.returncode != 0          # 401 fail-closed（无真凭据环境）
        assert "hosting" in r.stderr or "codeup" in r.stderr

    def test_platform_select_unknown(self):
        with pytest.raises(hosting.HostingError) as e:
            hosting.FACTORY_HOSTING = "gitlab"
            try:
                hosting.current_adapter()
            finally:
                hosting.FACTORY_HOSTING = "github"
        assert e.value.code == 2

    def test_platform_select_unknown_cli_exit2(self, monkeypatch):
        """PR #64 Sourcery：ad=current_adapter() 移入 try 后，未知
        FACTORY_HOSTING 经 CLI 主入口必须 rc=2（fail-closed），
        不再是裸 traceback + Python 通用 rc=1。"""
        import subprocess, sys
        monkeypatch.setenv("FACTORY_HOSTING", "gitlab")
        r = subprocess.run(
            [sys.executable, str(hosting.__file__ or ".factory/hosting.py"), "auth"],
            capture_output=True, text=True, timeout=15)
        assert r.returncode == 2, (r.returncode, r.stderr[-200:])

    def test_req_malformed_json_fail_closed(self, monkeypatch):
        """PR #64 Sourcery：200 + 畸形体必须转 HostingError（exit 2 域），
        裸 JSONDecodeError 不逃出适配器边界。"""
        import io

        class _BadResp:
            def read(self):
                return b"{not-json"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        monkeypatch.setenv("CODEUP_ORG_ID", "org")
        monkeypatch.setenv("CODEUP_REPO_ID", "42")
        # 凭据值非被测语义（被测 = 200+畸形体 fail-closed）：_req 首行
        # _cfg() 读 token，无凭据环境（CI/净克隆）缺此 mock 必红——
        # 2026-08-27 实证其污染 mutations B-106 负例（rc=1 假击杀）。
        monkeypatch.setenv("YUNXIAO_ACCESS_TOKEN", "test-token")
        ad = hosting.CodeupAdapter.__new__(hosting.CodeupAdapter)
        ad._endpoint = "openapi-rdc.aliyuncs.com"
        monkeypatch.setattr(
            hosting.urllib.request, "urlopen",
            lambda req, timeout: _BadResp())
        with pytest.raises(hosting.HostingError) as e:
            ad._req("GET", "/x")
        assert "响应格式错误" in str(e.value)

    def test_issue_comments_author_neutral_string(self):
        """PR #64 Sourcery：中立 schema author 是字符串；分流提示词
        格式化不得 c["author"]["login"]（TypeError）。fix-issue.sh
        内联 python 的等价形态回归（与 triage-batch.sh 同款）。"""
        cs = [{"author": "someone", "body": "hi"},
              {"body": "no-author-entry"}]
        out = "\n\n".join(
            "[作者: %s]\n%s" % (c.get("author") or "?", c["body"])
            for c in cs[-3:])
        assert "[作者: someone]" in out
        assert "[作者: ?]" in out  # 缺 author 不炸
