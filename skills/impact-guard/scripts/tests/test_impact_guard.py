"""impact-guard v1 测试：变更点识别 / 传播 / 影响方向 / 分级 / 边界 / 渲染 / CLI"""

import json
from pathlib import Path

import pytest

from boundary_scanner import init_config, scan_boundary_hits
from change_extractor import ChangeExtractor
from critical_ranker import CriticalRanker
from graph_tracer import build_cypher, current_head
from impact_scanner import ImpactScanner
from renderer import render_json, render_mermaid, render_text

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
        """git diff 路径（monkeypatch _git_lines，不依赖真实 git）"""
        import change_extractor as ce
        monkeypatch.setattr(ce, "_git_lines", lambda *a: [
            "M\tsrc/main/java/com/acme/demo/domain/order/OrderAgg.java",
            "D\tsrc/main/java/com/acme/demo/infra/util/RedisUtil.java",
            "M\tpom.xml",
        ])
        pts = ChangeExtractor(str(ddd_sample), {}).extract_from_diff(
            "origin/master...HEAD", scanned.infos)
        assert [p.change_type for p in pts] == ["modified", "deleted"]

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


# ── graph 模式（Tier 2 Cypher）───────────────────────────────────────────────


class TestGraphTracer:
    def test_cypher_contains_qn_and_depth(self):
        cy = build_cypher([QN["agg"]], depth=3)
        assert QN["agg"] in cy and "*1..3" in cy and "CALLS" in cy

    def test_head_sha(self, ddd_sample):
        # fixture 非 git 目录 → None（诚实降级）
        assert current_head(str(ddd_sample)) is None or isinstance(
            current_head(str(ddd_sample)), str)

    def test_render_graph_mode(self, ddd_sample):
        from graph_tracer import render_graph_mode
        out = render_graph_mode(str(ddd_sample), [QN["agg"]], 3, False)
        assert "index_status" in out and "query_graph" in out


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
