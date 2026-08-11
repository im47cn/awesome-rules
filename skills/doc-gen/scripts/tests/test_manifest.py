"""ManifestGenerator 聚合构建与域归属启发式测试

覆盖：
- _find_domain：层段前一段启发式（COLA/GTSP 通用，取代项目业务域白名单）
- _build_aggregates VO 归属：字段引用判断（修复所有聚合挂相同 VO）
- _build_aggregates 同前缀内部实体：适配「实体间通过 ID 关联、不对象持有」的 DDD 实践
- COLA fixture 端到端：域=demo、6 层归类、全景图含 client

设计依据见 generator/manifest.py 中 _build_aggregates / _find_domain 的方法注释。
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from doctypes import (
    ComponentDoc, DocManifest, DomainDoc, FieldDoc, LayerDoc, StateMachineDoc, StateTransitionDoc,
)
from generator.manifest import ManifestGenerator

# ── JavaScanner.knownLimitations（issue #1 修复）──────────────────────────────


def test_java_scanner_has_known_limitations():
    """JavaScanner 暴露已知局限性列表，供文档生成器使用（issue #1 修复）。"""
    from scanner.java import JavaScanner
    assert hasattr(JavaScanner, 'KNOWN_LIMITATIONS')
    assert isinstance(JavaScanner.KNOWN_LIMITATIONS, list)
    assert len(JavaScanner.KNOWN_LIMITATIONS) > 0
    limitation_text = ' '.join(JavaScanner.KNOWN_LIMITATIONS)
    assert '泛型' in limitation_text
    assert 'Lambda' in limitation_text


def _entity(cn, fields=None,
            qn_prefix="com.acme.messagecenter.domain.model.entity"):
    """构造实体组件"""
    return ComponentDoc(
        type="entity", className=cn,
        qualifiedName=f"{qn_prefix}.{cn}",
        fields=fields or [],
    )


def _vo(cn):
    return ComponentDoc(
        type="valueObject", className=cn,
        qualifiedName=f"com.acme.messagecenter.domain.model.vo.{cn}")


# ── _find_domain：层段前一段启发式（COLA/GTSP 通用） ─────────────────────────


def test_find_domain_layer_preceding_segment_cola():
    """单模块按层分包: 域 = 层段前一段。COLA com.example.demo.adapter.web → demo。"""
    g = ManifestGenerator("/tmp")
    fi = {"qualifiedName": "com.example.demo.adapter.web.DemoController",
          "className": "DemoController", "filePath": "x/DemoController.java"}
    assert g._find_domain(fi, {}) == "demo"


def test_find_domain_layer_preceding_segment_gtsp():
    """GTSP 包前缀: com.acme.order.infrastructure... → order。"""
    g = ManifestGenerator("/tmp")
    fi = {"qualifiedName": "com.acme.order.infrastructure.repository.mapper.OrderMapper",
          "className": "OrderMapper", "filePath": "x/OrderMapper.java"}
    assert g._find_domain(fi, {}) == "order"


def test_find_domain_multi_module_strips_layer_suffix():
    """多模块: artifactId 去层后缀得域; -app/-start/-infrastructure 均剥离。"""
    from generator.layers import LayerIdentifier
    ident = LayerIdentifier()
    assert ident.identify_domain_from_module("demo-app", {}) == "demo"
    assert ident.identify_domain_from_module("demo-start", {}) == "demo"
    assert ident.identify_domain_from_module("demo-infrastructure", {}) == "demo"


def test_find_domain_no_layer_falls_back_to_parts2():
    """无层段(顶层包, 如启动类) → 回退 parts[2]。"""
    g = ManifestGenerator("/tmp")
    fi = {"qualifiedName": "com.example.demo.Application",
          "className": "Application", "filePath": "x/Application.java"}
    assert g._find_domain(fi, {}) == "demo"


# ── COLA fixture 端到端扫描 ──────────────────────────────────────────────────

COLA_FIXTURE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cola-sample"


def test_cola_sample_domain_and_six_layers():
    """扫描 COLA fixture: 域=demo, 6 层正确归类, 全景图含 client 子图。"""
    from scanner.maven import MavenScanner
    from scanner.java import JavaScanner
    root = str(COLA_FIXTURE)
    maven_info = MavenScanner(root).scan()
    java_files = JavaScanner(root).scan_java_files()
    manifest = ManifestGenerator(root, {}).generate(java_files, maven_info, [])

    domains = [d.name for d in manifest.domains]
    assert "demo" in domains, f"期望域 demo, 实际 {domains}"
    demo = next(d for d in manifest.domains if d.name == "demo")
    layers = demo.layers

    def names(layer):
        return {c.className for c in layers[layer].components}

    assert "Application" in names("start"), f"start 层: {names('start')}"
    assert "DemoController" in names("adapter"), f"adapter 层: {names('adapter')}"
    assert {"DemoServiceI", "DemoCO"} <= names("client"), f"client 层: {names('client')}"
    assert "DemoCmdExe" in names("application"), f"application 层: {names('application')}"
    assert {"DemoEntity", "DemoGateway"} <= names("domain"), f"domain 层: {names('domain')}"
    assert {"DemoGatewayImpl", "DemoMapper", "DemoDO"} <= names("infrastructure"), \
        f"infrastructure 层: {names('infrastructure')}"

    # 全景图纳入 client 层(动态化回归)
    assert "demo_client" in manifest.diagrams.architectureOverview


# ── _build_aggregates：VO 归属（字段引用）──────────────────────────────────


def test_should_attach_vo_only_when_entity_field_references_it():
    """① VO 仅在聚合根字段引用时才挂；不引用则不挂(避免所有聚合挂相同 VO)。"""
    g = ManifestGenerator("/tmp")
    vo = _vo("ReceiverVO")
    # 实体不引用 VO → 不挂
    aggs = g._build_aggregates([_entity("MsgInfoEntity"), vo])
    assert len(aggs) == 1
    assert aggs[0].valueObjects == []
    assert aggs[0].name == "MsgInfo"
    # 实体字段引用 VO → 挂该聚合
    e_ref = _entity("MsgInfoEntity", fields=[FieldDoc(name="receiver", type="ReceiverVO")])
    aggs2 = g._build_aggregates([e_ref, vo])
    assert [v.className for v in aggs2[0].valueObjects] == ["ReceiverVO"]


# ── _build_aggregates：同前缀内部实体（②）──────────────────────────────────


def test_should_absorb_prefixed_entity_as_internal():
    """② 同前缀启发式：MsgSendTaskDetail 归入 MsgSendTask 聚合为内部实体。"""
    g = ManifestGenerator("/tmp")
    aggs = g._build_aggregates([
        _entity("MsgSendTaskEntity"),
        _entity("MsgSendTaskDetailEntity"),
    ])
    assert len(aggs) == 1                      # Detail 不再独立成聚合
    assert aggs[0].name == "MsgSendTask"
    assert [e.className for e in aggs[0].entities] == ["MsgSendTaskDetailEntity"]


def test_should_not_over_aggregate_unrelated_entities():
    """② 无前缀从属关系(且无主干实体)的实体各自独立，避免过度聚合。"""
    g = ManifestGenerator("/tmp")
    aggs = g._build_aggregates([
        _entity("MsgInfoEntity"),
        _entity("MsgTemplateInfoEntity"),
    ])
    assert len(aggs) == 2
    assert sorted(a.name for a in aggs) == ["MsgInfo", "MsgTemplateInfo"]


# ── _render_state_diagram：状态机 Mermaid 渲染 ───────────────────────────────


def test_should_render_isolated_states_when_no_transitions():
    """raw enum 无转换时改用 flowchart（stateDiagram 对无边 state 声明渲染为空）。"""
    g = ManifestGenerator("/tmp")
    sm = StateMachineDoc(
        name="SendDetailStatus", framework="raw",
        states=["FILTERED", "WAIT_CALLBACK", "SUCCESS", "FAIL"])
    out = g._render_state_diagram(sm)
    assert out.startswith("flowchart TD")
    for s in ["FILTERED", "WAIT_CALLBACK", "SUCCESS", "FAIL"]:
        assert s in out  # 每个状态都渲染为带框节点


def test_should_not_duplicate_states_already_in_transitions():
    """spring 状态机：已在转换/初始/终态出现的状态不重复声明(stateDiagram-v2)。"""
    g = ManifestGenerator("/tmp")
    sm = StateMachineDoc(
        name="OrderSM", framework="spring",
        states=["CREATED", "PAID", "DONE"],
        initialState="CREATED", endStates=["DONE"],
        transitions=[StateTransitionDoc(source="CREATED", target="PAID", event="pay")])
    out = g._render_state_diagram(sm)
    assert "[*] --> CREATED" in out
    assert "DONE --> [*]" in out
    assert "CREATED --> PAID : pay" in out
    for s in ["CREATED", "PAID", "DONE"]:
        assert f"state {s}" not in out  # 已 involved，不再显式声明


# ── 行为域/跨域/聚合图：领域模型修复覆盖 ────────────────────────────────────


def test_behavior_domain_when_no_entity():
    """无实体的行为域: 不产 Unknown 伪聚合, 标记 kind=behavior 并以域名命名。"""
    g = ManifestGenerator("/tmp")
    svc = ComponentDoc(
        type="domainService", className="SendDomainService",
        qualifiedName="com.acme.messagecenter.domain.service.send.SendDomainService")
    aggs = g._build_aggregates([svc], domain_name="send")
    assert len(aggs) == 1
    assert aggs[0].kind == "behavior"
    assert aggs[0].name == "send"
    assert aggs[0].rootEntity is None
    assert [s.className for s in aggs[0].domainServices] == ["SendDomainService"]


def test_cross_domain_detection_single_base_package():
    """单 base-package 项目: _find_domain 统一识别域, send import messagecenter 实体
    → 捕获跨域依赖(替代原 parts[2] 恒判同域导致的空结果)。"""
    g = ManifestGenerator("/tmp", {"domain_names": {"send": "发送域", "messagecenter": "消息域"}})
    java_files = [
        {"qualifiedName": "com.acme.messagecenter.domain.service.send.SendTaskService",
         "className": "SendTaskService", "filePath": "a/SendTaskService.java",
         "imports": ["com.acme.messagecenter.domain.model.entity.MsgSendTaskEntity"]},
        {"qualifiedName": "com.acme.messagecenter.domain.model.entity.MsgSendTaskEntity",
         "className": "MsgSendTaskEntity", "filePath": "a/MsgSendTaskEntity.java",
         "imports": []},
    ]
    deps = g._find_cross_domain_from_imports(java_files, {})
    assert len(deps) >= 1
    dep = next(d for d in deps if d.fromDomain == "send" and d.toDomain == "messagecenter")
    assert dep.type == "domain-coupling"


def test_aggregate_diagram_includes_internal_entities():
    """聚合 classDiagram 应画出 root → 内部实体(contains) 关系, 不再只画 VO。"""
    g = ManifestGenerator("/tmp")
    root = _entity("MsgSendTaskEntity")
    detail = _entity("MsgSendTaskDetailEntity")  # 同前缀 → 归并为内部实体
    aggs = g._build_aggregates([root, detail], domain_name="messagecenter")
    domain = DomainDoc(name="messagecenter", displayName="消息中心")
    domain.layers["domain"] = LayerDoc(aggregates=aggs)
    manifest = DocManifest()
    manifest.domains.append(domain)
    ds = g._generate_diagrams(manifest)
    diag = ds.domainAggregates.get("messagecenter", "")
    assert "MsgSendTaskEntity" in diag
    assert "MsgSendTaskDetailEntity" in diag
    assert "contains" in diag


def test_layer_dependency_real_shows_illegal_edges():
    """层间真实依赖图: 基于真实 import 计算, app→adapter 违规边用 ==> 并染红, 合法边用 -->。"""
    g = ManifestGenerator("/tmp")
    java_files = [
        {"qualifiedName": "com.x.application.assembler.SendAssembler",
         "className": "SendAssembler", "filePath": "a/SendAssembler.java",
         "imports": ["com.x.interfaces.command.SendCommand"]},   # application→adapter 违规
        {"qualifiedName": "com.x.interfaces.web.SendController",
         "className": "SendController", "filePath": "a/SendController.java",
         "imports": ["com.x.application.service.SendAppService"]},  # adapter→application 合法
    ]
    edges = g._compute_layer_edges(java_files)
    assert edges.get(("application", "adapter")) == 1
    assert edges.get(("adapter", "application")) == 1
    diag = g._generate_layer_dependency_real(edges)
    assert "application" in diag and "adapter" in diag
    assert "==>" in diag            # 违规边粗线
    assert "linkStyle" in diag      # 违规边染红
    assert "adapter -->|" in diag   # 合法边
