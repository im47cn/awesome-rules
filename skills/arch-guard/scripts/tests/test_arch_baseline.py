"""基线 ratchet 语义测试（只缩不涨，对齐 ArchUnit FreezingArchRule）。

覆盖 Phase 1 四条语义：
- 常规 --baseline：偿还存量 → 基线自动收缩写回；新增违规照报且不入基线
- --refreeze：有意重置债务线（唯一允许基线变大的路径）
- --update-baseline：--refreeze 的弃用别名（打印迁移提示，行为等价）
- --frozen：CI 模式，基线缺失/为空 → exit 2，且不自动创建基线
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import arch_check  # noqa: E402


# ── 测试脚手架：tmp_path 微型项目 ──────────────────────────────────────────

def _impure_domain(cls: str) -> str:
    """领域层污染文件：domain 包 import Spring 框架类 → DOMAIN_PURITY 强制违规。"""
    return (f"package com.example.domain;\n"
            f"\n"
            f"import org.springframework.context.ApplicationContext;\n"
            f"\n"
            f"public class {cls} {{\n"
            f"}}\n")


def _clean_domain(cls: str) -> str:
    return (f"package com.example.domain;\n"
            f"\n"
            f"public class {cls} {{\n"
            f"}}\n")


def _make_project(tmp_path, java_files: dict) -> str:
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".arch-guard.json").write_text(
        json.dumps({"project_package_prefix": "com.example"}), encoding="utf-8")
    for rel, content in java_files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return str(root)


def _write_file(root: str, rel: str, content: str):
    target = os.path.join(root, rel)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fp:
        fp.write(content)


def _run_cli(argv, monkeypatch, capsys):
    """以 CLI 方式驱动 main()，返回 (exit_code, stdout, stderr)。"""
    monkeypatch.setattr(sys, "argv", ["arch_check.py"] + argv)
    code = 0
    try:
        arch_check.main()
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _load_fps(baseline_path: str) -> set:
    with open(baseline_path, "r", encoding="utf-8") as fp:
        return set(json.load(fp)["fingerprints"])


ORDER = "src/main/java/com/example/domain/Order.java"
INVOICE = "src/main/java/com/example/domain/Invoice.java"

PAYMENT = "src/main/java/com/example/domain/Payment.java"

# ── 1. 偿还存量 → 基线自动收缩并写回 ───────────────────────────────────────

def test_repay_shrinks_baseline(tmp_path, monkeypatch, capsys):
    root = _make_project(tmp_path, {
        ORDER: _impure_domain("Order"),
        INVOICE: _impure_domain("Invoice"),
    })
    baseline = str(tmp_path / "baseline.json")

    code, _, _ = _run_cli([root, "--refreeze", baseline], monkeypatch, capsys)
    assert code == 0
    assert len(_load_fps(baseline)) == 2

    # 偿还一条：Order 改干净
    _write_file(root, ORDER, _clean_domain("Order"))

    code, out, _ = _run_cli([root, "--baseline", baseline, "--strict"],
                            monkeypatch, capsys)
    assert code == 0  # 剩余存量被抑制，无新增
    # 全抑制时走通过早退分支；收据规范要求通过路径同样携带证据边界声明
    assert out.strip().startswith("✅ 所有架构分层检查通过")
    assert "── 证据边界 ──" in out

    # 基线文件已写回：偿还的 Order 指纹消失，只剩 Invoice 一条
    assert len(_load_fps(baseline)) == 1

    # 基线文件已写回：只剩 Invoice 一条
    assert len(_load_fps(baseline)) == 1


# ── 2. 新增违规 → 照常上报，基线不变大 ─────────────────────────────────────

def test_new_violation_reported_baseline_not_grown(tmp_path, monkeypatch, capsys):
    root = _make_project(tmp_path, {ORDER: _impure_domain("Order")})
    baseline = str(tmp_path / "baseline.json")

    code, _, _ = _run_cli([root, "--refreeze", baseline], monkeypatch, capsys)
    assert code == 0
    fps_before = _load_fps(baseline)
    assert len(fps_before) == 1

    # 新增一条违规：Invoice 引入 Spring
    _write_file(root, INVOICE, _impure_domain("Invoice"))

    code, out, _ = _run_cli([root, "--baseline", baseline, "--strict",
                             "--format", "json"], monkeypatch, capsys)
    assert code == 1  # 新增违规必须上报
    result = json.loads(out)
    assert result["mandatory_count"] == 1
    assert result["issues"][0]["rule_code"] == "DOMAIN_PURITY"
    assert result["stats"]["baseline_suppressed"] == 1
    assert result["stats"]["baseline_retired"] == 0

    # 基线未变大：仍是原来那 1 条，新增违规指纹未混入
    assert _load_fps(baseline) == fps_before

    # 混合场景：重新冻结 {Order, Invoice}，再偿还 Order + 新增 Payment
    code, _, _ = _run_cli([root, "--refreeze", baseline], monkeypatch, capsys)
    assert code == 0
    assert len(_load_fps(baseline)) == 2
    _write_file(root, ORDER, _clean_domain("Order"))
    _write_file(root, PAYMENT, _impure_domain("Payment"))
    code, out, _ = _run_cli([root, "--baseline", baseline, "--strict"],
                            monkeypatch, capsys)
    assert code == 1  # Payment 新增违规照报
    assert "基线抑制存量违规: 1" in out
    assert "基线自动收缩: 已偿还 1 条存量（已写回基线文件）" in out
    assert len(_load_fps(baseline)) == 1  # 只剩 Invoice，Payment 未混入


# ── 3. --frozen 且基线文件不存在 → exit 2，不创建基线 ─────────────────────

def test_frozen_missing_baseline_exit_2(tmp_path, monkeypatch, capsys):
    root = _make_project(tmp_path, {ORDER: _impure_domain("Order")})
    baseline = str(tmp_path / "missing.json")
    code, _, err = _run_cli([root, "--frozen"], monkeypatch, capsys)
    assert code == 2  # --frozen 必须搭配 --baseline
    assert "--baseline" in err

    code, _, err = _run_cli([root, "--baseline", baseline, "--frozen"],
                            monkeypatch, capsys)
    assert code == 2
    assert "基线" in err
    assert "--refreeze" in err  # 错误信息指引用户先在本地生成基线
    assert not os.path.exists(baseline)  # CI 模式绝不自动创建基线


# ── 4. --refreeze → 基线重写为当前全部违规，随后运行通过 ───────────────────

def test_refreeze_resets_to_all_current_violations(tmp_path, monkeypatch, capsys):
    root = _make_project(tmp_path, {ORDER: _impure_domain("Order")})
    baseline = str(tmp_path / "baseline.json")

    code, _, _ = _run_cli([root, "--refreeze", baseline], monkeypatch, capsys)
    assert code == 0
    assert len(_load_fps(baseline)) == 1

    # 债务线有意重置：新增 Invoice 后 refreeze，基线变大（唯一允许路径）
    _write_file(root, INVOICE, _impure_domain("Invoice"))
    code, _, _ = _run_cli([root, "--refreeze", baseline], monkeypatch, capsys)
    assert code == 0
    assert len(_load_fps(baseline)) == 2

    # 随后常规运行通过（全部被抑制）
    code, out, _ = _run_cli([root, "--baseline", baseline, "--strict"],
                            monkeypatch, capsys)
    assert code == 0


# ── 5. --update-baseline → 打印 deprecation，功能等价 --refreeze ───────────

def test_update_baseline_deprecated_alias(tmp_path, monkeypatch, capsys):
    files = {ORDER: _impure_domain("Order"), INVOICE: _impure_domain("Invoice")}
    root_a = _make_project(tmp_path / "a", dict(files))
    root_b = _make_project(tmp_path / "b", dict(files))
    base_refreeze = str(tmp_path / "refreeze.json")
    base_alias = str(tmp_path / "alias.json")

    code, _, _ = _run_cli([root_a, "--refreeze", base_refreeze],
                          monkeypatch, capsys)
    assert code == 0

    code, _, err = _run_cli([root_b, "--update-baseline", base_alias],
                            monkeypatch, capsys)
    assert code == 0
    assert "--update-baseline" in err and "--refreeze" in err  # deprecation 提示

    # 功能等价：同一项目状态下两种参数产出相同指纹集
    assert _load_fps(base_alias) == _load_fps(base_refreeze)
    assert len(_load_fps(base_alias)) == 2


# ── 6. --frozen 三态语义（缺失/损坏拒绝；合法空基线=零债务放行） ──────────

def test_frozen_empty_baseline_zero_debt_passes(tmp_path, monkeypatch, capsys):
    """合法空基线 = 债务全部还清 → 放行，且干净项目 exit 0（对齐 ArchUnit 空 store 全绿）。"""
    root = _make_project(tmp_path, {ORDER: _clean_domain("Order")})
    baseline = str(tmp_path / "empty.json")
    with open(baseline, "w", encoding="utf-8") as fp:
        json.dump({"version": 1, "fingerprints": []}, fp)

    code, _, err = _run_cli([root, "--baseline", baseline, "--frozen"],
                            monkeypatch, capsys)
    assert code == 0
    assert err == ""
    # 空基线文件保持原样（未被写入）
    with open(baseline, "r", encoding="utf-8") as fp:
        assert json.load(fp)["fingerprints"] == []

    # 空基线 + 存在违规 → 违规不在基线内，按新增照报（exit 1），不放水
    _write_file(root, INVOICE, _impure_domain("Invoice"))
    code, _, _ = _run_cli([root, "--baseline", baseline, "--frozen"],
                          monkeypatch, capsys)
    assert code == 1


def test_frozen_corrupt_baseline_exit_2(tmp_path, monkeypatch, capsys):
    """损坏 JSON / 结构非法 → fail-closed 拒绝运行（无法确认基线可信）。"""
    root = _make_project(tmp_path, {ORDER: _clean_domain("Order")})

    for name, content in [
        ("corrupt.json", "{ not valid json !!!"),
        ("badstruct.json", json.dumps(["fp1", "fp2"])),  # 顶层是数组，非 dict
    ]:
        baseline = str(tmp_path / name)
        with open(baseline, "w", encoding="utf-8") as fp:
            fp.write(content)
        code, _, err = _run_cli([root, "--baseline", baseline, "--frozen"],
                                monkeypatch, capsys)
        assert code == 2
        assert "损坏" in err
