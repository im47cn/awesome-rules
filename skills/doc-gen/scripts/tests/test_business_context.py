"""业务上下文（businessContext）测试。

覆盖：md 受约束子集解析（四节/场景域名/流程步骤锚点）、代码弱信号提取
（@PreAuthorize 角色、状态机→流程）、合并策略（md 优先、同名角色升 hybrid、
状态机流程去重）、writer 可选分片写出、validator 可选分片校验（缺失合法/存在强校验）。
"""

import json
from pathlib import Path

from builder.writer import ManifestWriter
from doctypes import (
    BusinessContextDoc, BusinessFlowDoc, BusinessFlowStepDoc,
    BusinessItemDoc, DocManifest, StateMachineDoc, StateTransitionDoc,
)
from scanner.business_context import BusinessContextScanner
from validator import validate_manifest_dir

MD_SAMPLE = """# 业务上下文

## 客户
- **商户**：通过开放平台接入的平台商户
- **平台运营**：内部运营人员

## 角色
- **运营管理员**：管理商品上下架

## 业务场景
- **下单**：(order) 客户在门店扫码下单
- **对账**：(settlement) 商户每日拉取对账单

## 业务流程
### 订单履约流程
1. 创建订单 → CreateOrderCmdExe
2. 支付 → PayOrderCmdExe
3. 履约发货
"""

JAVA_WITH_ROLE = """package com.example.demo.adapter.web;

@RestController
public class OrderController {
    @PostMapping("/api/orders")
    @PreAuthorize("hasRole('ADMIN')")
    public String create() { return "ok"; }
}
"""


def _write_md(root: Path, text: str = MD_SAMPLE, name: str = "business-context.md"):
    (root / name).write_text(text, encoding="utf-8")


def _java_files(tmp_path: Path) -> list[dict]:
    src = tmp_path / "src/main/java/com/example/demo/adapter/web/OrderController.java"
    src.parent.mkdir(parents=True)
    src.write_text(JAVA_WITH_ROLE, encoding="utf-8")
    rel = src.relative_to(tmp_path)
    return [{
        "filePath": str(rel),
        "qualifiedName": "com.example.demo.adapter.web.OrderController",
    }]


def _state_machines() -> list[StateMachineDoc]:
    sm = StateMachineDoc(name="OrderStatus", framework="raw",
                         sourceClass="OrderStateMachine")
    sm.transitions = [
        StateTransitionDoc(source="CREATED", target="PAID", event="pay"),
        StateTransitionDoc(source="PAID", target="DELIVERED", event="deliver"),
    ]
    return [sm]


# ── md 解析 ────────────────────────────────────────────────────────────────────


def test_parse_md_four_sections():
    parsed = BusinessContextScanner.parse_md(MD_SAMPLE)
    assert [c.name for c in parsed["customers"]] == ["商户", "平台运营"]
    assert [r.name for r in parsed["roles"]] == ["运营管理员"]
    assert [s.name for s in parsed["scenarios"]] == ["下单", "对账"]


def test_parse_md_scenario_domain_extraction():
    parsed = BusinessContextScanner.parse_md(MD_SAMPLE)
    by_name = {s.name: s for s in parsed["scenarios"]}
    assert by_name["下单"].domain == "order"
    assert by_name["下单"].description == "客户在门店扫码下单"
    assert by_name["对账"].domain == "settlement"


def test_parse_md_flow_steps_with_anchors():
    parsed = BusinessContextScanner.parse_md(MD_SAMPLE)
    assert len(parsed["flows"]) == 1
    flow = parsed["flows"][0]
    assert flow.name == "订单履约流程"
    assert flow.source == "manual"
    assert [s.name for s in flow.steps] == ["创建订单", "支付", "履约发货"]
    assert flow.steps[0].anchors == ["CreateOrderCmdExe"]
    assert flow.steps[2].anchors == []  # 无 → 锚点的步骤


def test_parse_md_ignores_unknown_sections():
    text = MD_SAMPLE + "\n## 附录\n- **杂项**：忽略我\n"
    parsed = BusinessContextScanner.parse_md(text)
    assert all(c.name != "杂项" for c in parsed["customers"])


def test_parse_md_empty():
    assert BusinessContextScanner.parse_md("") == {
        "customers": [], "roles": [], "scenarios": [], "flows": []}


# ── 弱信号 ────────────────────────────────────────────────────────────────────


def test_scan_roles_from_preauthorize(tmp_path):
    scanner = BusinessContextScanner(str(tmp_path))
    roles = scanner._scan_roles(_java_files(tmp_path))
    assert len(roles) == 1
    assert roles[0].name == "ADMIN"
    assert roles[0].source == "code"
    assert roles[0].anchors == ["com.example.demo.adapter.web.OrderController"]


def test_flows_from_state_machines():
    scanner = BusinessContextScanner("/nonexistent")
    flows = scanner._flows_from_state_machines(_state_machines())
    assert len(flows) == 1
    flow = flows[0]
    assert flow.name == "OrderStatus 状态流转"
    assert flow.source == "code"
    assert flow.anchors == ["OrderStateMachine"]
    assert [s.name for s in flow.steps] == ["CREATED → PAID（pay）", "PAID → DELIVERED（deliver）"]


# ── 合并 ──────────────────────────────────────────────────────────────────────


def test_scan_merges_md_and_weak_signals(tmp_path):
    _write_md(tmp_path)
    # 人工写了"运营管理员"，代码有 ADMIN —— 两角色共存
    scanner = BusinessContextScanner(str(tmp_path))
    ctx = scanner.scan(_java_files(tmp_path), _state_machines())
    assert ctx is not None
    role_names = [r.name for r in ctx.roles]
    assert "运营管理员" in role_names and "ADMIN" in role_names
    # md 流程 + 状态机流程共存，不同名不去重
    flow_names = [f.name for f in ctx.flows]
    assert "订单履约流程" in flow_names and "OrderStatus 状态流转" in flow_names


def test_scan_merges_same_role_to_hybrid(tmp_path):
    md = "## 角色\n- **ADMIN**：管理员角色（人工描述）\n"
    _write_md(tmp_path, md)
    scanner = BusinessContextScanner(str(tmp_path))
    ctx = scanner.scan(_java_files(tmp_path), [])
    admin = next(r for r in ctx.roles if r.name == "ADMIN")
    assert admin.source == "hybrid"
    assert admin.description == "管理员角色（人工描述）"
    assert admin.anchors == ["com.example.demo.adapter.web.OrderController"]


def test_scan_returns_none_when_empty(tmp_path):
    scanner = BusinessContextScanner(str(tmp_path))
    assert scanner.scan([], []) is None


def test_find_context_md_priority(tmp_path):
    # 配置指定优先于根目录
    custom = tmp_path / "custom/biz.md"
    custom.parent.mkdir()
    custom.write_text("## 客户\n- **A**：x\n", encoding="utf-8")
    _write_md(tmp_path)
    scanner = BusinessContextScanner(str(tmp_path), {"business_context_file": "custom/biz.md"})
    assert scanner.find_context_md() == custom
    # 无配置时根目录优先于 docs/
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/business-context.md").write_text("x", encoding="utf-8")
    assert BusinessContextScanner(str(tmp_path)).find_context_md() == tmp_path / "business-context.md"


# ── writer + validator 契约往返 ────────────────────────────────────────────────


def _business_ctx() -> BusinessContextDoc:
    ctx = BusinessContextDoc()
    ctx.customers = [BusinessItemDoc(name="商户", description="平台商户")]
    ctx.roles = [BusinessItemDoc(name="ADMIN", source="code",
                                 anchors=["com.example.OrderController"])]
    ctx.scenarios = [BusinessItemDoc(name="下单", description="扫码下单", domain="order")]
    flow = BusinessFlowDoc(name="订单履约流程", description="人工流程",
                           anchors=["CreateOrderCmdExe"])
    flow.steps = [BusinessFlowStepDoc(name="创建订单", anchors=["CreateOrderCmdExe"]),
                  BusinessFlowStepDoc(name="履约发货")]
    ctx.flows = [flow]
    return ctx


def test_writer_writes_optional_shard_and_passes_validator(tmp_path):
    manifest = DocManifest()
    manifest.businessContext = _business_ctx()
    writer = ManifestWriter(tmp_path, evidence=None)
    writer.write(manifest)

    shard = tmp_path / "doc-manifest" / "business-context.json"
    assert shard.exists()
    data = json.loads(shard.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["scenarios"][0]["domain"] == "order"

    # 生成端自检：写出后必须通过 schema 契约
    assert validate_manifest_dir(tmp_path / "doc-manifest") == []


def test_writer_omits_shard_when_none(tmp_path):
    manifest = DocManifest()
    ManifestWriter(tmp_path, evidence=None).write(manifest)
    assert not (tmp_path / "doc-manifest" / "business-context.json").exists()
    # 缺失合法，validator 不报错
    assert validate_manifest_dir(tmp_path / "doc-manifest") == []


def test_validator_rejects_bad_optional_shard(tmp_path):
    manifest = DocManifest()
    ManifestWriter(tmp_path, evidence=None).write(manifest)
    # 篡改：source 非法枚举 + 未知字段
    bad = {"schema_version": 1, "roles": [{"name": "X", "source": "weird", "bogus": 1}]}
    (tmp_path / "doc-manifest" / "business-context.json").write_text(
        json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    errors = validate_manifest_dir(tmp_path / "doc-manifest")
    assert any("business-context.json" in e for e in errors)


def test_validator_rejects_wrong_schema_version(tmp_path):
    manifest = DocManifest()
    ManifestWriter(tmp_path, evidence=None).write(manifest)
    (tmp_path / "doc-manifest" / "business-context.json").write_text(
        json.dumps({"schema_version": 2, "customers": []}, ensure_ascii=False),
        encoding="utf-8")
    errors = validate_manifest_dir(tmp_path / "doc-manifest")
    assert any("schema_version" in e for e in errors)
