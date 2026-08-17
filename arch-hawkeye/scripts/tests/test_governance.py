"""治理闭环引擎测试（REQ-D 全覆盖）。

覆盖：基线冻结（D01 同名拒绝）、趋势三分（D02 added/removed/retained）、
债务登记与豁免强制理由（D04）、超期告警（D05）、违规消失自动关债（D06）、
增量零容忍门禁与灰度（D07）、blame 归属透传（D03 数据来自 risks.json）。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from governance import (
    create_baseline,
    diff_risks,
    exempt_debt,
    fingerprint,
    gate,
    load_baseline,
    load_ledger,
    overdue_debts,
    render_gate,
    sync_ledger,
)


def _issue(file="a/Foo.java", ruleCode="L001", desc="违规A", line=10, **kw):
    return {"file": file, "line": line, "severity": "强制", "ruleCode": ruleCode,
            "rule": "分层规范", "description": desc, **kw}


def _write_risks(manifest_dir: Path, issues: list):
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "risks.json").write_text(
        json.dumps({"issues": issues, "totalIssues": len(issues)}),
        encoding="utf-8")


# ── D01 基线 ──────────────────────────────────────────────────────────────────


def test_baseline_creates_and_registers_debts(tmp_path):
    """基线冻结 + 存量违规自动登记债务（owner 取 blame 归属）"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [
        _issue(desc="A", author="zhang", introducedAt="2026-01-01"),
        _issue(desc="B"),
    ])
    info = create_baseline(md, "2026H2")
    assert info["totalIssues"] == 2 and info["debts"] == 2
    ledger = load_ledger(md)
    owners = {d["description"]: d["owner"] for d in ledger["debts"]}
    assert owners["A"] == "zhang" and owners["B"] == "unknown"
    assert all(d["status"] == "pending" for d in ledger["debts"])


def test_baseline_same_name_rejected(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue()])
    create_baseline(md, "v1")
    with pytest.raises(FileExistsError):
        create_baseline(md, "v1")     # 拒绝静默覆盖


# ── D02 趋势 ──────────────────────────────────────────────────────────────────


def test_diff_three_way(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A"), _issue(desc="B"), _issue(desc="C")])
    create_baseline(md, "v1")
    # 演进：B 修复消除，D 新增，A/C 存量
    _write_risks(md, [_issue(desc="A"), _issue(desc="C", line=99), _issue(desc="D")])
    from governance import load_baseline, load_risks
    diff = diff_risks(load_baseline(md, "v1"), load_risks(md))
    assert [i["description"] for i in diff["added"]] == ["D"]
    assert len(diff["removedFingerprints"]) == 1              # B
    assert {i["description"] for i in diff["retained"]} == {"A", "C"}
    assert diff["stats"]["net"] == 0
    # line 漂移（C: 10 → 99）不影响 fingerprint
    fp_c = fingerprint(_issue(desc="C"))
    assert fp_c in {fingerprint(i) for i in diff["retained"]}


# ── D06 闭环 ──────────────────────────────────────────────────────────────────


def test_sync_ledger_auto_closes_repaid(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A"), _issue(desc="B")])
    create_baseline(md, "v1")
    # B 被修复 → 债务自动关闭；A 仍在 → 保持 pending
    _write_risks(md, [_issue(desc="A")])
    current = json.loads((md / "risks.json").read_text(encoding="utf-8"))["issues"]
    result = sync_ledger(md, current)
    assert result["closedCount"] == 1
    ledger = load_ledger(md)
    by_desc = {d["description"]: d for d in ledger["debts"]}
    assert by_desc["B"]["status"] == "repaid"
    assert by_desc["B"]["repaidAt"]
    assert by_desc["A"]["status"] == "pending"


# ── D04 豁免 ──────────────────────────────────────────────────────────────────


def test_exempt_requires_reason(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    fp = fingerprint(_issue(desc="A"))
    with pytest.raises(ValueError):
        exempt_debt(md, fp, "  ")            # 无理由拒绝
    d = exempt_debt(md, fp, "历史遗留，下季度统一重构")
    assert d["status"] == "exempt"
    assert d["exemptReason"]


# ── D05 超期 ──────────────────────────────────────────────────────────────────


def test_overdue_detection(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A"), _issue(desc="B")])
    create_baseline(md, "v1")
    ledger = load_ledger(md)
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    by_desc = {d["description"]: d for d in ledger["debts"]}
    by_desc["A"]["dueDate"] = past
    by_desc["A"]["status"] = "in-progress"
    by_desc["B"]["dueDate"] = future
    (md / "debt-ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    items = overdue_debts(md)
    assert len(items) == 1 and items[0]["description"] == "A"
    assert items[0]["overdueDays"] >= 9


# ── D07 门禁 ──────────────────────────────────────────────────────────────────


def test_gate_blocks_added_violations(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    _write_risks(md, [_issue(desc="A"), _issue(desc="NEW")])
    result = gate(md, "v1")
    assert result["blocked"] is True
    assert result["addedCount"] == 1
    # 门禁语义可直接映射 exit code
    assert bool(result["blocked"]) is True


def test_gate_allows_baseline_shrink_and_new_baseline_additions(tmp_path):
    """存量并存 + 消除 → 放行；灰度模式新增不阻断"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A"), _issue(desc="B")])
    create_baseline(md, "v1")
    _write_risks(md, [_issue(desc="A")])                       # B 消除，无新增
    assert gate(md, "v1")["blocked"] is False
    assert gate(md, "v1")["stats"]["removed"] == 1

    _write_risks(md, [_issue(desc="A"), _issue(desc="X")])     # X 新增
    warn = gate(md, "v1", warn_only=True)
    assert warn["blocked"] is False and warn["addedCount"] == 1   # 灰度放行
    assert gate(md, "v1")["blocked"] is True                      # 强制阻断


# ── 数据可信三态（fail-closed：失败 ≠ 零违规）───────────────────────────────


def test_gate_blocked_on_missing_risks(tmp_path):
    """risks.json 缺失（未接入/丢失）→ fail-closed 阻断，不得当零违规放行"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    (md / "risks.json").unlink()
    r = gate(md, "v1")
    assert r["riskStatus"] == "missing" and r["blocked"] is True
    assert "数据不可信" in render_gate(r)


def test_gate_blocked_on_corrupt_risks(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    (md / "risks.json").write_text("{bad", encoding="utf-8")
    r = gate(md, "v1")
    assert r["riskStatus"] == "corrupt" and r["blocked"] is True


def test_gate_blocked_on_scan_error(tmp_path):
    """生成端 scan 失败（error 字段非空、issues 恒空）→ 阻断"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    (md / "risks.json").write_text(
        json.dumps({"error": "arch_check.py 执行失败", "issues": [], "summary": {}}),
        encoding="utf-8")
    r = gate(md, "v1")
    assert r["riskStatus"] == "scan-error" and r["blocked"] is True


def test_gate_fail_closed_even_in_warn_only(tmp_path):
    """数据不可信不在灰度范围：--warn-only 下仍阻断"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    (md / "risks.json").unlink()
    assert gate(md, "v1", warn_only=True)["blocked"] is True


def test_baseline_rejects_untrusted_risks(tmp_path):
    """从失败/缺失扫描冻结空基线会污染后续所有 gate 判定 → 拒绝"""
    md = tmp_path / "doc-manifest"
    md.mkdir(parents=True)
    with pytest.raises(RuntimeError):
        create_baseline(md, "v1")


# ── CLI 层：友好错误与 exit code（不裸 traceback）───────────────────────────

HAWKEYE = Path(__file__).resolve().parent.parent / "hawkeye.py"


def _run_cli(*argv):
    import subprocess
    import sys
    return subprocess.run([sys.executable, str(HAWKEYE), *argv],
                          capture_output=True, text=True, timeout=60)


def test_cli_gate_missing_baseline_exits_2(tmp_path):
    r = _run_cli("gate", str(tmp_path), "--baseline", "nope")
    assert r.returncode == 2
    assert "基线不存在" in r.stderr
    assert "Traceback" not in r.stderr


def test_cli_trend_corrupt_risks_exits_2(tmp_path):
    """趋势对不可信数据拒绝输出（否则会渲染出'消除 N 条'的假趋势）"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    (md / "risks.json").write_text("{bad", encoding="utf-8")
    r = _run_cli("trend", str(md), "--baseline", "v1")
    assert r.returncode == 2
    assert "数据不可信" in r.stderr
    assert "Traceback" not in r.stderr


# ── fingerprint 信息保全（合并为一条债务，但不丢行号与计数）────────────────

def test_baseline_preserves_duplicate_occurrences(tmp_path):
    """同点重复违规：totalIssues 按条数、fingerprints 按类型，行号全保留"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A", line=10), _issue(desc="A", line=99),
                      _issue(desc="B", line=1)])
    info = create_baseline(md, "v1")
    assert info["totalIssues"] == 3
    base = load_baseline(md, "v1")
    assert base["totalFingerprints"] == 2
    fp_a = fingerprint(_issue(desc="A"))
    entry = base["fingerprints"][fp_a]
    assert entry["occurrences"] == 2 and entry["lines"] == [10, 99]
    # 债务登记带 occurrences/lines，代表 issue 为首条（line=10）
    debt = [d for d in load_ledger(md)["debts"]
            if d["description"] == "A"][0]
    assert debt["occurrences"] == 2 and debt["lines"] == [10, 99]


def test_diff_representative_issue_is_first_occurrence(tmp_path):
    """added/retained 取 fp 首条代表（保序稳定，不受末条覆盖影响）"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    _write_risks(md, [_issue(desc="A", line=1), _issue(desc="A", line=50),
                      _issue(desc="NEW", line=5), _issue(desc="NEW", line=6)])
    diff = diff_risks(load_baseline(md, "v1"),
                      [_issue(desc="A", line=1), _issue(desc="A", line=50),
                       _issue(desc="NEW", line=5), _issue(desc="NEW", line=6)])
    assert diff["stats"] == {"baseline": 1, "current": 2, "added": 1,
                             "removed": 0, "retained": 1, "net": 1}
    assert diff["added"][0]["line"] == 5        # 首条代表，非末条 6
    assert diff["added"][0]["occurrences"] == 2


# ── 豁免状态机 ───────────────────────────────────────────────────────────────

def test_exempt_rejects_repaid_debt(tmp_path):
    """已偿还债务不可豁免（已闭环，豁免混淆台账语义）"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    _write_risks(md, [])                         # A 消除 → 自动 repaid
    sync_ledger(md, [])
    fp = fingerprint(_issue(desc="A"))
    with pytest.raises(ValueError):
        exempt_debt(md, fp, "想豁免已还清的")


def test_exempt_until_enters_overdue_review(tmp_path):
    """带 until 的豁免到期后进入 overdue 复核视野（豁免不再永久免检）"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    fp = fingerprint(_issue(desc="A"))
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    exempt_debt(md, fp, "临时放行", until=past)
    overdue = overdue_debts(md)
    assert len(overdue) == 1 and overdue[0]["status"] == "exempt"
    assert overdue[0]["overdueDays"] >= 9


def test_exempt_until_validates_date(tmp_path):
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    with pytest.raises(ValueError):
        exempt_debt(md, fingerprint(_issue(desc="A")), "r", until="not-a-date")


def test_gate_does_not_write_ledger(tmp_path):
    """gate 只读不写：PR 并发跑 gate 无 load-modify-save 竞态（CI 样例语义）"""
    md = tmp_path / "doc-manifest"
    _write_risks(md, [_issue(desc="A")])
    create_baseline(md, "v1")
    (md / "debt-ledger.json").unlink()           # baseline 登记的 ledger 移除
    _write_risks(md, [_issue(desc="A"), _issue(desc="X")])
    r = gate(md, "v1")
    assert r["blocked"] is True
    assert not (md / "debt-ledger.json").exists()  # gate 未写回
