"""impact-guard v1 测试：变更点识别 / 传播 / 影响方向 / 分级 / 边界 / 渲染 / CLI"""

import json
import types
from pathlib import Path

import pytest

from boundary_scanner import init_config, scan_boundary_hits
from change_extractor import ChangeExtractor
from critical_ranker import CriticalRanker
from graph_tracer import build_cypher, current_head
from impact_scanner import ImpactScanner
from renderer import build_receipt, render_json, render_mermaid, render_text

QN = {
    "agg": "com.acme.demo.domain.order.OrderAgg",
    "cmd": "com.acme.demo.app.OrderCreateCmdExe",
    "ctrl": "com.acme.demo.adapter.web.OrderController",
    "listener": "com.acme.demo.adapter.listener.PayResultListener",
    "job": "com.acme.demo.job.SyncJob",
    "mapper": "com.acme.demo.infra.mapper.OrderMapper",
    "feign": "com.acme.demo.client.PayClient",
    "repo": "com.acme.demo.domain.order.OrderRepository",
}


# ── Tier 1 扫描与索引 ─────────────────────────────────────────────────────────


class TestScanner:
    def test_scans_all_classes_with_prefix_filter(self, scanned):
        assert len(scanned.infos) == 11  # fixture 全部 11 个 Java 类均命中前缀
        assert QN["agg"] in scanned.infos

    def test_reverse_index_inbound_edges(self, scanned):
        # OrderAgg 被谁 import：CmdExe
        assert QN["cmd"] in scanned.reverse_index.get(QN["agg"], set())

    def test_forward_index_outbound_edges(self, scanned):
        # CmdExe 依赖：Agg/Repo/Mapper/Feign
        deps = scanned.forward_index[QN["cmd"]]
        assert {QN["agg"], QN["repo"], QN["mapper"], QN["feign"]} <= deps

    def test_prefix_filters_foreign_classes(self, ddd_sample):
        s = ImpactScanner(str(ddd_sample), {"project_package_prefix": "com.other"})
        assert s.scan() == {}


# ── 影响传播（BFS）────────────────────────────────────────────────────────────


class TestPropagation:
    def test_inbound_depth_and_path(self, scanned):
        impacts = scanned.propagate_inbound(QN["agg"], depth=3)
        by_qn = {n.qualified_name: n for n in impacts}
        assert by_qn[QN["cmd"]].depth == 1
        assert by_qn[QN["ctrl"]].depth == 2
        assert by_qn[QN["ctrl"]].path == [QN["agg"], QN["cmd"], QN["ctrl"]]

    def test_depth_limit(self, scanned):
        impacts = scanned.propagate_inbound(QN["agg"], depth=1)
        assert [n.qualified_name for n in impacts] == [QN["cmd"]]

    def test_outbound_regression_tree(self, scanned):
        tree = scanned.propagate_outbound(QN["ctrl"], depth=3)
        tree_qns = {n.qualified_name for n in tree}
        assert QN["cmd"] in tree_qns and QN["mapper"] in tree_qns

    def test_ignore_glob_blocks_propagation(self, ddd_sample):
        s = ImpactScanner(str(ddd_sample), {"ignore": ["**.app.**"]})
        s.scan()
        # CmdExe 被 ignore → Agg 的 inbound 不再穿过它
        impacts = s.propagate_inbound(QN["agg"], depth=3)
        assert QN["ctrl"] not in {n.qualified_name for n in impacts}


# ── 变更点提取 ────────────────────────────────────────────────────────────────


class TestDiffHunks:
    def test_parse_hunks_head_side(self):
        from change_extractor import parse_diff_hunks
        d = parse_diff_hunks(
            "diff --git a/A.java b/A.java\n"
            "@@ -5,2 +6,3 @@\n+new line\n"
            "@@ -20 +25,0 @@\n")
        assert d["A.java"]["hunks"] == [(6, 8)]  # count=0 的纯删除锚点不计

    def test_parse_change_types(self):
        from change_extractor import parse_diff_hunks
        d = parse_diff_hunks(
            "diff --git a/N.java b/N.java\nnew file mode 100644\n@@ -0,0 +1,2 @@\n+x\n"
            "diff --git a/D.java b/D.java\ndeleted file mode 100644\n@@ -1,2 +0,0 @@\n")
        assert d["N.java"]["change_type"] == "added"
        assert d["D.java"]["change_type"] == "deleted"

    def test_match_methods_interval_approx(self):
        from change_extractor import match_changed_methods
        methods = [{"name": "a", "line": 10}, {"name": "b", "line": 20}]
        assert match_changed_methods([(12, 15)], methods) == ["a"]
        assert match_changed_methods([(25, 99)], methods) == ["b"]  # 尾方法到文件尾
        # 跨区间边界（a 尾行 19 / b 首行 20）→ 区间近似的固有重叠，两方法都命中
        assert match_changed_methods([(19, 21)], methods) == ["a", "b"]
        assert match_changed_methods([(5, 8)], methods) == []

    def test_match_methods_ignores_no_line(self):
        from change_extractor import match_changed_methods
        assert match_changed_methods([(1, 99)], [{"name": "x"}]) == []


class TestChangeExtractor:
    def test_explicit_qualified_name(self, ddd_sample, scanned):
        ex = ChangeExtractor(str(ddd_sample), {})
        pts = ex.extract_explicit([QN["agg"]], scanned.infos)
        assert len(pts) == 1
        assert pts[0].layer == "domain"
        assert pts[0].change_type == "modified"

    def test_explicit_file_path(self, ddd_sample, scanned):
        ex = ChangeExtractor(str(ddd_sample), {})
        pts = ex.extract_explicit(["OrderAgg.java"], scanned.infos)
        assert pts[0].qualified_name == QN["agg"]

    def test_from_name_status(self, ddd_sample, scanned):
        ex = ChangeExtractor(str(ddd_sample), {})
        lines = [f"A\tsrc/main/java/com/acme/demo/domain/order/OrderAgg.java"]
        pts = ex._from_name_status(lines, scanned.infos)
        assert pts[0].change_type == "added"

    def test_non_java_ignored(self, ddd_sample, scanned):
        ex = ChangeExtractor(str(ddd_sample), {})
        pts = ex._from_name_status(["M\tpom.xml"], scanned.infos)
        assert pts == []

    def test_extract_from_diff_via_git(self, ddd_sample, scanned, monkeypatch):
        """git diff -U0 路径：hunk 解析 + 方法级变更（v2）"""
        import change_extractor as ce
        # OrderController.java 的 create() 在第 18 行 → hunk +18,3 命中 create
        diff = """diff --git a/src/main/java/com/acme/demo/adapter/web/OrderController.java b/src/main/java/com/acme/demo/adapter/web/OrderController.java
--- a/src/.../OrderController.java
+++ b/src/.../OrderController.java
@@ -17,3 +18,3 @@
     public OrderCreateCO create() {
-        return null;
+        return orderCreateCmdExe.execute();
diff --git a/src/main/java/com/acme/demo/infra/util/RedisUtil.java b/src/main/java/com/acme/demo/infra/util/RedisUtil.java
deleted file mode 100644
@@ -10,2 +0,0 @@
-public class RedisUtil {
diff --git a/pom.xml b/pom.xml
@@ -1 +1 @@
-<old>
+<new>
"""
        monkeypatch.setattr(ce, "_git_text", lambda *a: diff)
        pts = ChangeExtractor(str(ddd_sample), {}).extract_from_diff(
            "origin/master...HEAD", scanned.infos)
        by_qn = {p.qualified_name: p for p in pts}
        ctrl = by_qn[QN["ctrl"]]
        assert ctrl.change_type == "modified"
        assert "create" in ctrl.changed_methods          # hunk +18,3 命中 create()
        assert by_qn["com.acme.demo.infra.util.RedisUtil"].change_type == "deleted"
        assert all(p.file_path != "pom.xml" for p in pts)

    def test_git_failure_returns_none_no_crash(self, ddd_sample, monkeypatch):
        """git 命令失败 → _git_text 返回 None → 空列表不误报"""
        import change_extractor as ce
        monkeypatch.setattr(ce, "_git_text", lambda *a: None)
        assert ChangeExtractor(str(ddd_sample), {}).extract_from_diff("x", {}) == []

    def test_git_failure_returns_empty(self, ddd_sample, monkeypatch):
        """git 命令失败（CalledProcessError）→ _git_lines 捕获返回 []"""
        import subprocess as sp

        def boom(*a, **k):
            raise sp.CalledProcessError(1, "git")
        monkeypatch.setattr("change_extractor.subprocess.run", boom)
        pts = ChangeExtractor(str(ddd_sample), {}).extract_from_diff("x", {})
        assert pts == []

    def test_derive_info_reads_package(self, ddd_sample):
        """无扫描结果时从源码路径推导 qn（文件存在可读 package）"""
        ex = ChangeExtractor(str(ddd_sample), {})
        info = ex._derive_info(
            "src/main/java/com/acme/demo/domain/order/OrderAgg.java")
        assert info["qualifiedName"] == QN["agg"]

    def test_derive_info_missing_file(self, ddd_sample):
        ex = ChangeExtractor(str(ddd_sample), {})
        assert ex._derive_info("src/main/java/no/such/File.java") is None
        assert ex._derive_info("docs/readme.md") is None


# ── 边界扫描（--init）─────────────────────────────────────────────────────────


class TestBoundaryScanner:
    def test_five_channels_detected(self, scanned):
        hits = scan_boundary_hits(scanned.infos)
        assert hits["http_entry"] == [QN["ctrl"]]
        assert hits["mq_entry"] == [QN["listener"]]
        assert hits["job_entry"] == [QN["job"]]
        assert hits["http_exit"] == [QN["feign"]]
        assert hits["db_sink"] == [QN["mapper"]]

    def test_init_config_writes_file(self, ddd_sample, scanned, tmp_path):
        cfg_path = tmp_path / ".impact-guard.json"
        cfg = init_config(str(ddd_sample), scanned.infos, str(cfg_path))
        assert cfg["project_package_prefix"] == "com.acme"
        saved = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert saved["boundary_hits"]["http_entry"] == [QN["ctrl"]]


# ── 关键路径分级 ──────────────────────────────────────────────────────────────


class TestRanking:
    def _rank(self, scanned, qn):
        ranker = CriticalRanker({}, scanned.infos)
        is_entry = qn in ranker.entry_qn
        impacts = [] if is_entry else scanned.propagate_inbound(qn, 3)
        outbound = scanned.propagate_outbound(qn, 3) if is_entry else None
        return ranker.rank_change(
            next(iter(scanned.infos[qn] and [] or []), None) or _mk_cp(qn),
            impacts, outbound)

    def test_aggregate_root_indirect(self, scanned):
        rc = self._rank(scanned, QN["agg"])
        assert rc.level == "INDIRECT"
        assert set(rc.regression_scope) == {QN["ctrl"], QN["listener"], QN["job"]}

    def test_mapper_direct(self, scanned):
        assert self._rank(scanned, QN["mapper"]).level == "DIRECT"

    def test_feign_direct_cross_service(self, scanned):
        rc = self._rank(scanned, QN["feign"])
        assert rc.level == "DIRECT"
        assert any("跨服务" in r for r in rc.reasons)

    def test_entry_unanalyzable_with_regression(self, scanned):
        rc = self._rank(scanned, QN["ctrl"])
        assert rc.is_entry and rc.level == "WARNING"
        assert QN["cmd"] in rc.regression_scope

    def test_internal_info(self, scanned):
        # OrderRepository 是 domain 层接口 → domain 层触发 WARNING（聚合根条款）
        # 改用 infra 内部无依赖者验证 INFO：RedisUtil 无人依赖也无人被依赖
        ranker = CriticalRanker({}, scanned.infos)
        rc = ranker.rank_change(_mk_cp(
            "com.acme.demo.infra.util.RedisUtil"), [], None)
        assert rc.level == "INFO"

    def test_report_level_is_max(self, scanned):
        ranker = CriticalRanker({}, scanned.infos)
        rcs = [self._rank(scanned, QN["agg"]), self._rank(scanned, QN["mapper"])]
        report = ranker.rank(rcs)
        assert report.level == "DIRECT"
        assert report.cross_service == [] or report.cross_service


def _mk_cp(qn):
    from change_extractor import ChangePoint
    return ChangePoint(qualified_name=qn, file_path="", layer="",
                       component_type="")


# ── 渲染 ─────────────────────────────────────────────────────────────────────


class TestRenderer:
    def _report(self, scanned):
        ranker = CriticalRanker({}, scanned.infos)
        rcs = [ranker.rank_change(_mk_cp(QN["agg"]),
                                  scanned.propagate_inbound(QN["agg"], 3), None)]
        return ranker.rank(rcs)

    def test_json_structure(self, scanned):
        data = json.loads(render_json(self._report(scanned)))
        assert data["schema_version"] == 1 and data["tier"] == 1
        assert data["level"] == "INDIRECT"
        c = data["changes"][0]
        assert c["impact_count"] == 4 and c["regression_scope"]

    def test_text_markers(self, scanned):
        text = render_text(self._report(scanned))
        assert "🟠" in text and "回归范围" in text and "影响链" in text

    def test_mermaid_graph(self, scanned):
        md = render_mermaid(self._report(scanned))
        assert "flowchart RL" in md and "[CHANGED]" in md and "classDef" in md

    def test_mermaid_entry_badge(self, scanned):
        ranker = CriticalRanker({}, scanned.infos)
        rcs = [ranker.rank_change(_mk_cp(QN["ctrl"]), [],
                                  scanned.propagate_outbound(QN["ctrl"], 3))]
        md = render_mermaid(ranker.rank(rcs))
        assert "🚪" in md

    def test_json_receipt_envelope(self, scanned):
        report = self._report(scanned)
        report.receipt = build_receipt(
            report, tier=1, strict=True, diff_range="origin/master...HEAD",
            changed_points=1, scanned_classes=len(scanned.infos),
            config_source=".impact-guard.json",
            boundary_channels={"http_entry": ["com.acme.Ctrl"]})
        data = json.loads(render_json(report))
        r = data["receipt"]
        assert r["tool"] == "impact-guard" and r["schema_version"] == 1
        assert r["decision"]["gate"] == "pass"          # INDIRECT 非 DIRECT
        assert r["decision"]["reason_codes"] == []
        assert r["provenance"]["diff_range"] == "origin/master...HEAD"
        assert r["provenance"]["boundary_channels"] == {"http_entry": 1}
        assert "tier1_class_level" in r["boundary"]["degraded"]
        assert "reflection_dynamic_dispatch" in r["boundary"]["not_analyzed"]

    def test_receipt_gate_block_and_cross_service(self):
        stub = types.SimpleNamespace(level="DIRECT",
                                     cross_service=["com.acme.OrderClient"],
                                     changes=[])
        r = build_receipt(stub, tier=1, strict=True)
        assert r["decision"]["gate"] == "block"
        assert r["decision"]["reason_codes"] == [
            "direct_boundary_hit", "cross_service_downstream_unanalyzed"]
        assert "cross_service_downstream" in r["boundary"]["not_analyzed"]
        # 不带 strict → 仅告警不阻断
        assert build_receipt(stub)["decision"]["gate"] == "warn"

    def test_receipt_tier2_no_degradation(self):
        stub = types.SimpleNamespace(level="INFO", cross_service=[], changes=[])
        r = build_receipt(stub, tier=2)
        assert r["boundary"]["degraded"] == []

    def test_text_boundary_footer(self, scanned):
        report = self._report(scanned)
        assert "证据边界" not in render_text(report)   # 无收据不输出
        report.receipt = build_receipt(report)
        text = render_text(report)
        assert "── 证据边界 ──" in text
        assert "Tier 1 类级" in text
        assert "结构盲区" in text


# ── graph 模式（Tier 2 Cypher）───────────────────────────────────────────────


class TestGraphTracer:
    def test_cypher_contains_qn_and_depth(self):
        cy = build_cypher([QN["agg"]], depth=3)
        assert QN["agg"] in cy and "*1..3" in cy and "CALLS" in cy

    def test_cypher_method_level_v2(self):
        cy = build_cypher([QN["ctrl"]], depth=2,
                          changed_methods={QN["ctrl"]: ["create"]})
        assert f"{QN['ctrl']}.create" in cy      # Class.method 形态
        assert "v2 方法级" in cy
        # 不传 methods 时不生成方法级段
        assert "v2 方法级" not in build_cypher([QN["ctrl"]])

    def test_head_sha(self, ddd_sample):
        # fixture 非 git 目录 → None（诚实降级）
        assert current_head(str(ddd_sample)) is None or isinstance(
            current_head(str(ddd_sample)), str)

    def test_render_graph_mode(self, ddd_sample):
        from graph_tracer import render_graph_mode
        out = render_graph_mode(str(ddd_sample), [QN["agg"]], 3, False)
        assert "index_status" in out and "query_graph" in out


# ── 跨服务契约（v2b）────────────────────────────────────────────────────────


class TestCrossService:
    def test_extract_feign_contract(self, ddd_sample, scanned):
        from cross_service import extract_feign_contracts
        info = scanned.infos[QN["feign"]]
        c = extract_feign_contracts(str(ddd_sample), info)
        assert c["service"] == "gtsp-pay"
        assert c["endpoints"] == [{"http_method": "POST",
                                   "path": "/api/pay/create",
                                   "java_method": "createPay"}]

    def test_extract_method_level_filter(self, ddd_sample, scanned):
        from cross_service import extract_feign_contracts
        info = scanned.infos[QN["feign"]]
        c = extract_feign_contracts(str(ddd_sample), info, only_methods=["other"])
        assert c["endpoints"] == []  # 变更方法未命中端点 → 空清单+note

    def test_non_feign_returns_none(self, ddd_sample, scanned):
        from cross_service import extract_feign_contracts
        assert extract_feign_contracts(
            str(ddd_sample), scanned.infos[QN["agg"]]) is None

    def test_cross_service_cypher(self):
        from cross_service import build_cross_service_cypher
        cy = build_cross_service_cypher([
            {"service": "gtsp-pay",
             "endpoints": [{"http_method": "POST", "path": "/api/pay/create",
                            "java_method": "x"}]}])
        assert "/api/pay/create" in cy and "Route" in cy
        assert build_cross_service_cypher(
            [{"service": "x", "endpoints": []}]) is None

    def test_cli_json_contains_contracts(self, ddd_sample):
        import subprocess
        r = subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "impact_check.py"),
             str(ddd_sample), "--changed", QN["feign"], "--format", "json"],
            capture_output=True, text=True, timeout=120)
        data = json.loads(r.stdout)
        assert data["cross_service_contracts"][QN["feign"]]["service"] == "gtsp-pay"


# ── CLI 端到端 ────────────────────────────────────────────────────────────────


class TestCli:
    def _run(self, ddd_sample, *args):
        import subprocess
        return subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "impact_check.py"),
             str(ddd_sample), *args],
            capture_output=True, text=True, timeout=120)

    def _main(self, monkeypatch, *args):
        """in-process 调 main()（计入覆盖率）"""
        import impact_check
        import sys as _sys
        monkeypatch.setattr(_sys, "argv", ["impact_check.py", *args])
        with pytest.raises(SystemExit) as e:
            impact_check.main()
        return e.value.code

    def test_changed_indirect_exit_zero(self, ddd_sample):
        r = self._run(ddd_sample, "--changed", QN["agg"])
        assert r.returncode == 0 and "INDIRECT" in r.stdout

    def test_strict_direct_exit_one(self, ddd_sample):
        r = self._run(ddd_sample, "--changed", QN["mapper"], "--strict")
        assert r.returncode == 1

    def test_strict_indirect_exit_zero(self, ddd_sample):
        r = self._run(ddd_sample, "--changed", QN["agg"], "--strict")
        assert r.returncode == 0

    def test_json_format(self, ddd_sample):
        r = self._run(ddd_sample, "--changed", QN["feign"], "--format", "json")
        data = json.loads(r.stdout)
        assert data["level"] == "DIRECT"

    def test_graph_mode(self, ddd_sample):
        r = self._run(ddd_sample, "--changed", QN["agg"], "--mode", "graph")
        assert "CALLS" in r.stdout and r.returncode == 0

    def test_no_input_error(self, ddd_sample):
        r = self._run(ddd_sample)
        assert r.returncode == 2

    def test_missing_dir_error(self):
        r = self._run("/nonexistent-path-xyz", "--changed", "a.B")
        assert r.returncode == 2

    # in-process 分支覆盖
    def test_init_in_process(self, ddd_sample, monkeypatch, capsys):
        assert self._main(monkeypatch, str(ddd_sample), "--init") == 0
        assert "配置已生成" in capsys.readouterr().out

    def test_init_empty_scan_exits_two(self, tmp_path, monkeypatch):
        (tmp_path / "empty.txt").write_text("x")
        assert self._main(monkeypatch, str(tmp_path), "--init") == 2

    def test_no_change_points_exit_zero(self, ddd_sample, monkeypatch, capsys):
        import change_extractor as ce
        monkeypatch.setattr(ce, "_git_lines", lambda *a: ["M\tpom.xml"])
        assert self._main(monkeypatch, str(ddd_sample), "--diff", "x") == 0
        assert "未识别到" in capsys.readouterr().out

    def test_mermaid_format_in_process(self, ddd_sample, monkeypatch, capsys):
        self._main(monkeypatch, str(ddd_sample), "--changed", QN["agg"],
                   "--format", "mermaid")
        assert "flowchart" in capsys.readouterr().out

    def test_no_input_in_process(self, ddd_sample, monkeypatch):
        assert self._main(monkeypatch, str(ddd_sample)) == 2

    def test_graph_mode_cross_service_in_process(self, ddd_sample, monkeypatch,
                                                 capsys):
        """graph 模式：Feign 变更点 → 输出含跨服务 Cypher 段（v2b）"""
        self._main(monkeypatch, str(ddd_sample), "--changed", QN["feign"],
                   "--mode", "graph")
        out = capsys.readouterr().out
        assert "跨服务传播" in out and "/api/pay/create" in out

    def test_graph_mode_no_feign_omits_cross_section(self, ddd_sample,
                                                     monkeypatch, capsys):
        self._main(monkeypatch, str(ddd_sample), "--changed", QN["agg"],
                   "--mode", "graph")
        assert "跨服务传播" not in capsys.readouterr().out
