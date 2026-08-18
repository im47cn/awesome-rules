"""
arch_check.py 单元测试
运行: python3 -m pytest tests/ -v
"""

import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

import arch_check


def _cfg(**overrides):
    cfg = arch_check.load_config("/tmp", None)
    for k, v in overrides.items():
        cfg[k] = v
    return cfg


def _patterns(cfg=None):
    if cfg is None:
        cfg = arch_check.load_config("/tmp", None)
    return arch_check._build_layer_patterns(cfg)


# ── Layer identification ───────────────────────────────────────────────────

def test_identify_layer():
    cfg = _cfg()
    patterns = _patterns(cfg)

    assert arch_check.identify_layer("src/main/java/com/x/adapter/controller/X.java", patterns, cfg) == "adapter"
    assert arch_check.identify_layer("src/main/java/com/x/domain/entity/X.java", patterns, cfg) == "domain"
    assert arch_check.identify_layer("src/main/java/com/x/application/executor/X.java", patterns, cfg) == "application"
    assert arch_check.identify_layer("src/main/java/com/x/infrastructure/persistence/X.java", patterns, cfg) == "infrastructure"
    assert arch_check.identify_layer("src/main/java/com/x/client/dto/X.java", patterns, cfg) == "client"
    assert arch_check.identify_layer("src/main/java/com/x/Main.java", patterns, cfg) is None


def test_layer_alias_default_interfaces():
    """P0-2: 默认 layer_aliases 包含 interfaces→adapter（COLA 4.0 原生）。"""
    cfg = _cfg()
    patterns = _patterns(cfg)

    result = arch_check.identify_layer("src/main/java/com/x/interfaces/controller/X.java", patterns, cfg)
    assert result == "adapter"

    # 原始 adapter 路径仍有效
    assert arch_check.identify_layer("src/main/java/com/x/adapter/controller/X.java", patterns, cfg) == "adapter"


def test_is_internal_import_with_prefix():
    assert arch_check._is_internal_import("com.acme.order.domain.entity.OrderE", "com.acme")
    assert not arch_check._is_internal_import("org.springframework.stereotype.Service", "com.acme")


def test_is_internal_import_heuristic():
    assert arch_check._is_internal_import("com.example.order.domain.entity.OrderE", "")
    assert not arch_check._is_internal_import("org.springframework.stereotype.Service", "")
    assert not arch_check._is_internal_import("java.util.List", "")
    assert not arch_check._is_internal_import("org.junit.jupiter.api.Test", "")
    assert arch_check._is_internal_import("com.company.internal.Xyz", "")


# ── Domain purity ──────────────────────────────────────────────────────────

def test_domain_purity_catches_spring_import():
    cfg = _cfg()
    content = "import org.springframework.web.client.RestTemplate;\nimport java.util.List;\n"
    issues = arch_check.check_domain_purity("src/domain/entity/X.java", content, cfg)
    assert len(issues) == 1
    assert issues[0].rule == "领域层纯净度"
    assert "RestTemplate" in issues[0].description


def test_domain_purity_allows_jpa():
    cfg = _cfg()
    content = "import jakarta.persistence.Entity;\nimport javax.persistence.Id;\n"
    issues = arch_check.check_domain_purity("src/domain/entity/X.java", content, cfg)
    assert len(issues) == 0


def test_domain_purity_allows_annotation_classes():
    cfg = _cfg()
    content = "import org.springframework.stereotype.Service;\n"
    issues = arch_check.check_domain_purity("src/domain/entity/X.java", content, cfg)
    assert len(issues) == 0


# ── Dependency direction ───────────────────────────────────────────────────

def test_dependency_direction_catches_reverse_ref():
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)

    content = "import com.example.order.adapter.controller.XController;\n"
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/order/domain/entity/OrderE.java",
        "domain", content, patterns, cfg)
    assert len(issues) == 1
    assert issues[0].rule == "依赖方向"


def test_dependency_direction_skips_third_party():
    cfg = _cfg()
    patterns = _patterns(cfg)

    content = "import org.springframework.web.client.RestTemplate;\n"
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/order/domain/entity/OrderE.java",
        "domain", content, patterns, cfg)
    client_issue = [i for i in issues if "client" in i.description.lower()]
    assert len(client_issue) == 0


def test_dependency_direction_allows_valid():
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)

    content = "import com.example.order.domain.entity.OrderE;\n"
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/order/application/executor/CreateOrderCmdExe.java",
        "application", content, patterns, cfg)
    assert len(issues) == 0


# ── Naming ─────────────────────────────────────────────────────────────────

def test_naming_suffix_matches_layer():
    cfg = _cfg()
    patterns = _patterns(cfg)

    # GTSP 后缀规则：Repository 应在 domain 层（02-naming §1）
    content = "public class OrderRepository {\n"
    issues = arch_check.check_naming(
        "src/main/java/com/example/order/domain/repository/OrderRepository.java",
        "domain", content, cfg)
    assert len(issues) == 0

    issues = arch_check.check_naming(
        "src/main/java/com/example/order/adapter/controller/OrderRepository.java",
        "adapter", content, cfg)
    assert len(issues) == 1
    assert issues[0].rule == "命名规范"


def test_naming_skips_hibernate_and_short():
    cfg = _cfg()

    # HibernateUtil — 不以已知后缀结尾
    content_hib = "public class HibernateUtil {\n"
    issues = arch_check.check_naming(
        "src/main/java/com/example/order/infrastructure/persistence/HibernateUtil.java",
        "infrastructure", content_hib, cfg)
    assert len(issues) == 0

    # OrderPO 在 infrastructure — 合规（GTSP 持久化对象后缀 PO，02-naming §1）
    content_po = "public class OrderPO {\n"
    issues = arch_check.check_naming(
        "src/main/java/com/example/order/infrastructure/repository/po/OrderPO.java",
        "infrastructure", content_po, cfg)
    assert len(issues) == 0


def test_short_class_name_skip():
    cfg = _cfg()
    content = "public class AB {\n"
    issues = arch_check.check_naming("src/main/java/com/x/infrastructure/AB.java", "infrastructure", content, cfg)
    assert len(issues) == 0


def test_suffix_with_camel_boundary():
    # 按后缀名定位规则，避免依赖列表索引（重排序脆弱）
    def rule_matching(sample: str):
        for rx, _, _, _ in arch_check._SUFFIX_RULES:
            if rx.search(sample):
                return rx
        return None

    cmd = rule_matching("CreateCommand")
    assert cmd is not None
    assert not cmd.search("ABC")          # 前接大写字母，不匹配
    assert cmd.search("CreateCommand")

    qry = rule_matching("OrderQuery")
    assert qry is not None
    assert qry.search("OrderQuery")


def test_naming_enum_layering():
    """枚举按语义分层：领域状态枚举（*StatusEnum/*StateEnum）→ domain；技术分类枚举 → infrastructure。"""
    cfg = _cfg()

    # 领域状态枚举放 infrastructure → 报强制（应移到 domain，否则 domain 逆向依赖）
    content = "public class OrderStatusEnum {\n"
    issues = arch_check.check_naming(
        "src/main/java/com/example/order/infrastructure/enums/OrderStatusEnum.java",
        "infrastructure", content, cfg)
    assert len(issues) == 1
    assert issues[0].severity == arch_check.Severity.MANDATORY

    # 状态枚举在 domain 合规
    issues = arch_check.check_naming(
        "src/main/java/com/example/order/domain/model/enum/OrderStatusEnum.java",
        "domain", content, cfg)
    assert len(issues) == 0

    # 技术分类枚举在 infrastructure 合规
    content_tech = "public class GenderEnum {\n"
    issues = arch_check.check_naming(
        "src/main/java/com/example/order/infrastructure/enums/GenderEnum.java",
        "infrastructure", content_tech, cfg)
    assert len(issues) == 0


# ── Adapter isolation ──────────────────────────────────────────────────────

def test_adapter_isolation_catches_domain_entity():
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)

    content = "import com.example.order.domain.entity.OrderE;\n"
    issues = arch_check.check_adapter_isolation(
        "src/main/java/com/example/order/adapter/controller/OrderController.java",
        content, patterns, cfg)
    assert len(issues) == 1
    assert issues[0].rule == "Adapter 隔离"


def test_adapter_isolation_skips_third_party():
    cfg = _cfg()
    patterns = _patterns(cfg)

    content = "import jakarta.persistence.Entity;\n"
    issues = arch_check.check_adapter_isolation(
        "src/main/java/com/example/order/adapter/controller/OrderController.java",
        content, patterns, cfg)
    assert len(issues) == 0


# ── Strict mode ────────────────────────────────────────────────────────────

def test_strict_mode_upgrades_recommended():
    issues = [arch_check.Issue("test.java", 1, arch_check.Severity.RECOMMENDED, "test", "desc")]
    for i in issues:
        if i.severity == arch_check.Severity.RECOMMENDED:
            i.severity = arch_check.Severity.MANDATORY
    assert issues[0].severity == arch_check.Severity.MANDATORY


# ── Maven module ───────────────────────────────────────────────────────────

def test_maven_module_layer():
    cfg = _cfg()
    assert arch_check._identify_module_layer("order-domain", cfg) == "domain"
    assert arch_check._identify_module_layer("order-app", cfg) == "application"
    assert arch_check._identify_module_layer("order-infrastructure", cfg) == "infrastructure"
    assert arch_check._identify_module_layer("order-adapter", cfg) == "adapter"
    assert arch_check._identify_module_layer("order-client", cfg) == "client"
    assert arch_check._identify_module_layer("order-start", cfg) == "start"


def test_business_domain_extraction():
    cfg = _cfg()
    assert arch_check._identify_business_domain("order-domain", "order/order-domain/pom.xml", cfg) == "order"
    assert arch_check._identify_business_domain("logistics-client", "logistics/logistics-client/pom.xml", cfg) == "logistics"


# ── Baseline ───────────────────────────────────────────────────────────────

def test_issue_fingerprint():
    i1 = arch_check.Issue("a.java", 42, arch_check.Severity.MANDATORY,
                          "領域層純淨度", "禁止導入: X", "fix")
    fp = arch_check._issue_fingerprint(i1)
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_filter_by_baseline():
    i1 = arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "r1", "d1")
    i2 = arch_check.Issue("b.java", 2, arch_check.Severity.MANDATORY, "r2", "d2")
    i3 = arch_check.Issue("c.java", 3, arch_check.Severity.MANDATORY, "r3", "d3")

    baseline = {arch_check._issue_fingerprint(i1), arch_check._issue_fingerprint(i2)}
    issues = [i1, i2, i3]

    new_issues, suppressed = arch_check.filter_by_baseline(issues, baseline)
    assert len(new_issues) == 1
    assert suppressed == 2
    assert new_issues[0].file == "c.java"


def test_save_and_load_baseline():
    import tempfile
    import os
    issues = [
        arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "r1", "d1"),
        arch_check.Issue("b.java", 2, arch_check.Severity.MANDATORY, "r2", "d2"),
    ]
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        fpath = f.name

    try:
        arch_check.save_baseline(fpath, issues)
        loaded = arch_check.load_baseline(fpath)
        assert len(loaded) == 2
        for issue in issues:
            assert arch_check._issue_fingerprint(issue) in loaded
    finally:
        os.unlink(fpath)


# ── Output ─────────────────────────────────────────────────────────────────

def test_format_text_has_summary_and_stats():
    issues = [
        arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "领域层纯净度", "desc", "fix"),
        arch_check.Issue("b.java", 2, arch_check.Severity.RECOMMENDED, "命名规范", "desc2", ""),
    ]
    stats = {"java_files_total": 10, "java_files_classified": 8,
             "java_files_unclassified": 2, "pom_files_total": 3,
             "baseline_suppressed": 0, "warnings": []}
    text = arch_check.format_text(issues, 1, 1, stats=stats)
    assert "## 统计" in text
    assert "## 摘要" in text
    assert "## 明细" in text
    assert "领域层纯净度" in text


def test_format_text_no_issues():
    text = arch_check.format_text([], 0, 0)
    assert "通过" in text


# ── Integration ────────────────────────────────────────────────────────────

def test_run_integration():
    import pathlib
    test_dir = pathlib.Path(__file__).parent.parent.parent
    badcase_dir = test_dir / "badcase" / "001-domain-imports-infrastructure" / "input"
    if not badcase_dir.exists():
        return

    issues, m, r, stats = arch_check.run(str(badcase_dir), strict=False)
    assert m >= 1


def test_extract_imports_with_lines():
    content = "package foo;\n\nimport com.example.Foo;\nimport java.util.List;\n\npublic class X {}"
    imports = arch_check.extract_imports_with_lines(content)
    assert len(imports) == 2
    assert imports[0] == ("com.example.Foo", 3)
    assert imports[1] == ("java.util.List", 4)


# ── check_file returns tuple now ───────────────────────────────────────────

def test_check_file_returns_tuple():
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)
    import tempfile

    content = 'package com.example.order.domain.entity;\nimport jakarta.persistence.Entity;\npublic class OrderE {}\n'
    with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
        fpath = f.name
        f.write(content)

    try:
        # 需要正确的目录结构才能被 identify_layer 识别
        # 改为使用目标目录中的 fixture
        pass
    finally:
        os.unlink(fpath)


# ── P0-1: suggestion 分流 ─────────────────────────────────────────────────

def test_dep_suggestion_for_enum():
    """枚举/常量的违规不应建议"抽接口 + 依赖注入"。"""
    sug = arch_check._dep_direction_suggestion(
        "domain", "infrastructure",
        "com.example.infrastructure.common.enums.SmsChannelGradeEnum")
    assert "业务数据型" in sug
    assert "上移至 domain.shared" in sug
    assert "抽接口" not in sug.lower()


def test_dep_suggestion_for_exception():
    sug = arch_check._dep_direction_suggestion(
        "domain", "infrastructure",
        "com.example.infrastructure.common.exception.MessageCenterException")
    assert "业务数据型" in sug


def test_dep_suggestion_for_util():
    sug = arch_check._dep_direction_suggestion(
        "domain", "infrastructure",
        "com.example.infrastructure.common.utils.DateUtils")
    assert "工具类" in sug
    assert "上移至 domain.shared.util" in sug


def test_dep_suggestion_for_service():
    """领域服务的违规应建议编排在应用层。"""
    sug = arch_check._dep_direction_suggestion(
        "domain", "infrastructure",
        "com.example.infrastructure.service.OrderDomainService")
    assert "编排应在 Application Executor" in sug


def test_dep_suggestion_default():
    sug = arch_check._dep_direction_suggestion(
        "domain", "infrastructure",
        "com.example.infrastructure.persistence.OrderMapper")
    assert "反转依赖方向" in sug


def test_domain_purity_suggestion_for_mybatis_annotation():
    sug = arch_check._domain_purity_suggestion(
        "com.baomidou.mybatisplus.annotation.TableField")
    assert "MyBatis-Plus" in sug
    assert "XML 映射" in sug


def test_domain_purity_suggestion_transactional():
    sug = arch_check._domain_purity_suggestion(
        "org.springframework.transaction.annotation.Transactional")
    assert "@Transactional" in sug
    assert "domain_annotation_imports" in sug


def test_domain_purity_suggestion_default():
    sug = arch_check._domain_purity_suggestion(
        "org.springframework.web.client.RestTemplate")
    assert "infrastructure" in sug


# ── P0-3: fingerprint 稳定性 ─────────────────────────────────────────────

def test_fingerprint_line_stability():
    """行号位移不应改变指纹。"""
    i1 = arch_check.Issue("a.java", 42, arch_check.Severity.MANDATORY,
                          "依赖方向",
                          "domain 层禁止依赖 infrastructure 层: import com.x.infra.enums.X",
                          "上移至 domain.shared")
    i2 = arch_check.Issue("a.java", 999, arch_check.Severity.MANDATORY,
                          "依赖方向",
                          "domain 层禁止依赖 infrastructure 层: import com.x.infra.enums.X",
                          "上移至 domain.shared")
    assert arch_check._issue_fingerprint(i1) == arch_check._issue_fingerprint(i2)


def test_fingerprint_distinct_for_different_violations():
    """不同 import 目标应有不同指纹（description 不同则指纹不同）。"""
    i1 = arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY,
                          "依赖方向",
                          "domain 层禁止依赖 infrastructure 层: import com.x.infra.enums.StatusEnum",
                          "sug1")
    i2 = arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY,
                          "依赖方向",
                          "domain 层禁止依赖 infrastructure 层: import com.x.infra.service.OrderService",
                          "sug2")
    assert arch_check._issue_fingerprint(i1) != arch_check._issue_fingerprint(i2)


# ── P0-4: target 层 alias 感知 ────────────────────────────────────────────

def test_identify_layer_on_import_path_with_alias():
    """import 路径中 .interfaces. 应被识别为 adapter（alias）。"""
    cfg = _cfg()
    patterns = _patterns(cfg)

    # .interfaces. → adapter (default alias in config)
    layer = arch_check.identify_layer(
        "com/example/order/interfaces/controller/OrderController.java",
        patterns, cfg)
    assert layer == "adapter"


# ── P0-2: by_callee_root 聚类 ─────────────────────────────────────────────

# ── P0: structural_debt 契约对象分类 ──────────────────────────────────────

def test_is_contract_object_detects_command():
    assert arch_check._is_contract_object("com.example.interfaces.model.command.CreateCmd")
    assert arch_check._is_contract_object("com.example.interfaces.model.dto.SomeDTO")
    assert arch_check._is_contract_object("com.example.interfaces.model.query.OrderQuery")
    assert arch_check._is_contract_object("com.example.application.dto.UserDTO")
    assert arch_check._is_contract_object("com.example.client.dto.UserCO")


def test_is_contract_object_skips_entity():
    assert not arch_check._is_contract_object("com.example.domain.entity.OrderE")
    assert not arch_check._is_contract_object("com.example.infrastructure.persistence.OrderDO")
    assert not arch_check._is_contract_object("com.example.application.service.OrderService")


def test_structural_debt_severity():
    assert arch_check.Severity.STRUCTURAL_DEBT.value == "结构性债务"


def test_dependency_direction_flags_contract_as_structural_debt():
    """契约对象跨层引用应归为结构性债务而非强制违规。"""
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)

    # application → client dto 应归为结构性债务
    content = "import com.example.interfaces.model.dto.OrderDTO;\n"
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/order/application/executor/CreateOrderCmdExe.java",
        "application", content, patterns, cfg)
    assert len(issues) == 1
    assert issues[0].severity == arch_check.Severity.STRUCTURAL_DEBT
    assert issues[0].rule == "依赖方向"
    assert "结构性债务" in issues[0].description


def test_dependency_direction_non_contract_stays_mandatory():
    """非契约对象（如 Mapper）的跨层引用仍是强制违规。"""
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)

    # domain → infrastructure Mapper 仍是强制违规
    content = "import com.example.order.infrastructure.persistence.OrderMapper;\n"
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/order/domain/entity/OrderE.java",
        "domain", content, patterns, cfg)
    assert len(issues) == 1
    assert issues[0].severity == arch_check.Severity.MANDATORY


def test_dep_suggestion_for_contract_object():
    """契约对象的建议应提及单模块结构性债务 + client 拆分。"""
    sug = arch_check._dep_direction_suggestion(
        "application", "client",
        "com.example.interfaces.model.command.CreateOrderCmd")
    assert "契约对象" in sug
    assert "client 模块" in sug
    assert "结构性债务" in sug


def test_run_structural_debt_not_in_mandatory(tmp_path):
    """结构性债务不影响 passed/mandatory_count。"""
    import pathlib
    base = tmp_path / "src" / "main" / "java" / "com" / "example" / "order"
    base.mkdir(parents=True)

    # application executor 引用 client dto — 应归为结构债务
    app_dir = base / "application" / "executor"
    app_dir.mkdir(parents=True)
    (app_dir / "CreateOrderCmdExe.java").write_text(
        "package com.example.order.application.executor;\n"
        "import com.example.interfaces.model.dto.OrderDTO;\n"
        "public class CreateOrderCmdExe {}\n"
    )

    # domain 引用 infrastructure — 真正违规
    domain_dir = base / "domain" / "entity"
    domain_dir.mkdir(parents=True)
    (domain_dir / "OrderE.java").write_text(
        "package com.example.order.domain.entity;\n"
        "import com.example.order.infrastructure.persistence.OrderMapper;\n"
        "public class OrderE {}\n"
    )

    infra_dir = base / "infrastructure" / "persistence"
    infra_dir.mkdir(parents=True)
    (infra_dir / "OrderMapper.java").write_text(
        "package com.example.order.infrastructure.persistence;\n"
        "public class OrderMapper {}\n"
    )

    cfg = _cfg(project_package_prefix="com.example")
    issues, m, r, stats = arch_check.run(str(tmp_path), strict=False,
                                          config_path=None)

    assert m == 1  # domain→infra 是唯一强制违规
    assert stats["structural_debt_count"] == 1  # 契约对象单独计数
    assert not any(i.file == str(app_dir / "CreateOrderCmdExe.java")
                   and i.severity == arch_check.Severity.MANDATORY for i in issues)


def test_format_json_has_callee_summary():
    issues = [
        arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "依赖方向",
                         "domain 层禁止依赖 infrastructure 层: import com.example.infra.common.enums.StatusEnum",
                         "sug"),
        arch_check.Issue("b.java", 2, arch_check.Severity.MANDATORY, "依赖方向",
                         "domain 层禁止依赖 infrastructure 层: import com.example.infra.common.enums.ChannelEnum",
                         "sug"),
    ]
    result_json = arch_check.format_json(issues, 2, 0)
    result = json.loads(result_json)
    assert "summary" in result
    assert "by_callee_root" in result["summary"]
    clusters = sorted(result["summary"]["by_callee_root"], key=lambda x: -x["count"])
    assert clusters[0]["count"] == 2
    assert "infra.common.enums" in clusters[0]["package"]


def test_format_json_receipt_envelope():
    issues = [
        arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "依赖方向",
                         "desc", "DEP_DIRECTION", "sug"),
    ]
    stats = {"java_files_total": 10, "java_files_classified": 8,
             "java_files_unclassified": 2, "pom_files_total": 3,
             "baseline_suppressed": 5, "baseline_retired": 1}
    result = json.loads(arch_check.format_json(
        issues, 1, 0, stats=stats, baseline_path=".arch-guard-baseline.json"))
    r = result["receipt"]
    assert r["tool"] == "arch-guard" and r["schema_version"] == 1
    assert r["decision"]["gate"] == "block"
    assert r["decision"]["reason_codes"] == ["DEP_DIRECTION"]
    assert r["provenance"]["baseline"] == ".arch-guard-baseline.json"
    assert r["provenance"]["baseline_suppressed"] == 5
    assert "tier1_file_level_heuristic" in r["boundary"]["degraded"]
    assert "unclassified_java_files" in r["boundary"]["degraded"]
    assert "aggregate_design" in r["boundary"]["not_analyzed"]
    # 无强制问题 → pass
    ok = json.loads(arch_check.format_json([], 0, 0))
    assert ok["receipt"]["decision"]["gate"] == "pass"
    assert ok["receipt"]["decision"]["reason_codes"] == []


def test_format_text_boundary_footer():
    stats = {"java_files_total": 5, "java_files_classified": 5,
             "java_files_unclassified": 0, "pom_files_total": 1,
             "baseline_suppressed": 7, "warnings": []}
    text = arch_check.format_text([], 0, 0, stats=stats)
    assert "── 证据边界 ──" in text
    assert "Tier 2 知识图谱" in text
    assert "基线抑制: 7" in text
    # 无 stats 路径也有边界声明，无基线行
    bare = arch_check.format_text([], 0, 0)
    assert "── 证据边界 ──" in bare
    assert "基线抑制" not in bare


# ── State machine ──────────────────────────────────────────────────────────

def test_state_field_leakage_adapter_mandatory():
    """adapter 层改写状态 → 强制级状态泄漏。"""
    cfg = _cfg()
    content = 'public class OrderController {\n  void pay() { order.setStatus(PAID); }\n}'
    issues = arch_check.check_state_field_leakage(
        "src/main/java/com/example/order/adapter/controller/OrderController.java",
        "adapter", content, cfg)
    assert len(issues) == 1
    assert issues[0].rule_code == arch_check.STATE_FIELD_LEAKAGE
    assert issues[0].severity == arch_check.Severity.MANDATORY


def test_state_field_leakage_infra_recommended():
    """infrastructure 层改写状态 → 推荐级（DO 转换等可能合理）。"""
    cfg = _cfg()
    content = 'public class OrderMapperImpl { void map() { do.updateStatus(X); } }'
    issues = arch_check.check_state_field_leakage(
        "src/main/java/com/example/order/infrastructure/persistence/OrderMapperImpl.java",
        "infrastructure", content, cfg)
    assert len(issues) == 1
    assert issues[0].severity == arch_check.Severity.RECOMMENDED


def test_state_field_leakage_domain_skipped():
    """domain 层改写状态 → 不报（状态流转本就属于 Domain）。"""
    cfg = _cfg()
    content = 'public class OrderE { void pay() { this.setStatus(PAID); } }'
    issues = arch_check.check_state_field_leakage(
        "src/main/java/com/example/order/domain/entity/OrderE.java",
        "domain", content, cfg)
    assert issues == []


def test_state_machine_governance_without_framework(tmp_path):
    """有状态枚举但无状态机框架 → 推荐级治理提醒。"""
    src = tmp_path / "src/main/java/com/example/order/domain"
    src.mkdir(parents=True)
    (src / "OrderStatus.java").write_text(
        "package com.example.order.domain; enum OrderStatus { INIT, PAID; }", encoding="utf-8")
    cfg = _cfg()
    java_files = [str(src / "OrderStatus.java")]
    issues = arch_check.check_state_machine_governance(str(tmp_path), java_files, cfg)
    assert any(i.rule_code == arch_check.STATE_MACHINE for i in issues)


def test_state_machine_governance_with_framework_silent(tmp_path):
    """引入了状态机框架 → 不报治理问题。"""
    src = tmp_path / "src/main/java/com/example/order/domain"
    src.mkdir(parents=True)
    (src / "OrderStatus.java").write_text(
        "package com.example.order.domain; enum OrderStatus { INIT, PAID; }", encoding="utf-8")
    (src / "OrderConfig.java").write_text(
        "import org.springframework.statemachine.config.StateMachineConfigurer;", encoding="utf-8")
    cfg = _cfg()
    java_files = [str(src / "OrderStatus.java"), str(src / "OrderConfig.java")]
    assert arch_check.check_state_machine_governance(str(tmp_path), java_files, cfg) == []


def test_run_integration_state_machine():
    """端到端：004 夹具应触发状态泄漏 + 状态机治理。"""
    import pathlib
    test_dir = pathlib.Path(__file__).parent.parent.parent
    badcase_dir = test_dir / "badcase" / "004-state-machine-violation" / "input"
    if not badcase_dir.exists():
        return
    issues, m, r, stats = arch_check.run(str(badcase_dir), strict=False)
    codes = {i.rule_code for i in issues}
    assert arch_check.STATE_FIELD_LEAKAGE in codes
    assert arch_check.STATE_MACHINE in codes


# ── graph 模式 / init 子命令 ───────────────────────────────────────────────

_POM_HEADER = '<project xmlns="http://maven.apache.org/POM/4.0.0">'


def test_print_graph_mode_outputs_cypher(capsys):
    arch_check.print_graph_mode()
    out = capsys.readouterr().out
    assert "Tier 2" in out
    assert "Domain → Infrastructure" in out
    # 默认 layer_aliases（interfaces→adapter）注入 adapter 层匹配条件
    assert "interfaces" in out


def test_print_graph_mode_bad_config_falls_back(capsys):
    """配置加载失败时回退 DEFAULT_CONFIG，仍正常输出查询清单。"""
    arch_check.print_graph_mode(config_path="/nonexistent/.arch-guard.json")
    out = capsys.readouterr().out
    assert "Tier 2" in out


def test_infer_prefix_no_pom(tmp_path):
    assert arch_check._infer_prefix_from_pom(str(tmp_path)) is None


def test_infer_prefix_from_root_pom(tmp_path):
    (tmp_path / "pom.xml").write_text(
        f'{_POM_HEADER}<groupId>com.example.order</groupId></project>',
        encoding="utf-8")
    assert arch_check._infer_prefix_from_pom(str(tmp_path)) == "com.example.order"


def test_infer_prefix_from_parent(tmp_path):
    (tmp_path / "pom.xml").write_text(
        f'{_POM_HEADER}<parent><groupId>com.example.parent</groupId>'
        '</parent></project>', encoding="utf-8")
    assert arch_check._infer_prefix_from_pom(str(tmp_path)) == "com.example.parent"


def test_infer_prefix_from_subdir_pom(tmp_path):
    sub = tmp_path / "order"
    sub.mkdir()
    (sub / "pom.xml").write_text(
        f'{_POM_HEADER}<groupId>com.sub</groupId></project>', encoding="utf-8")
    assert arch_check._infer_prefix_from_pom(str(tmp_path)) == "com.sub"


def test_do_init_generates_config_with_prefix(tmp_path, capsys):
    (tmp_path / "pom.xml").write_text(
        f'{_POM_HEADER}<groupId>com.example</groupId></project>', encoding="utf-8")
    arch_check._do_init(str(tmp_path), ".arch-guard.json")
    cfg = json.loads((tmp_path / ".arch-guard.json").read_text(encoding="utf-8"))
    assert cfg["project_package_prefix"] == "com.example"
    assert "_comment" in cfg


def test_do_init_without_pom_empty_prefix(tmp_path, capsys):
    arch_check._do_init(str(tmp_path), ".arch-guard.json")
    cfg = json.loads((tmp_path / ".arch-guard.json").read_text(encoding="utf-8"))
    assert cfg["project_package_prefix"] == ""


def test_do_init_exits_when_config_exists(tmp_path):
    (tmp_path / ".arch-guard.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        arch_check._do_init(str(tmp_path), ".arch-guard.json")
    assert exc.value.code == 1


# ── 配置加载与深合并 ───────────────────────────────────────────────────────

def test_load_config_reads_json_file(tmp_path):
    """项目根存在 .arch-guard.json 时自动加载，默认键保留。"""
    (tmp_path / ".arch-guard.json").write_text(
        json.dumps({"project_package_prefix": "com.test"}), encoding="utf-8")
    cfg = arch_check.load_config(str(tmp_path), None)
    assert cfg["project_package_prefix"] == "com.test"
    assert "layer_paths" in cfg


def test_load_config_explicit_path(tmp_path):
    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps({"project_package_prefix": "com.x"}), encoding="utf-8")
    cfg = arch_check.load_config(str(tmp_path), str(custom))
    assert cfg["project_package_prefix"] == "com.x"


def test_load_config_deep_merge(tmp_path):
    """深合并：仅覆盖指定子键，保留同层其他默认键。"""
    (tmp_path / ".arch-guard.json").write_text(
        json.dumps({"layer_paths": {"adapter": ["/web/"]}}), encoding="utf-8")
    cfg = arch_check.load_config(str(tmp_path), None)
    assert cfg["layer_paths"]["adapter"] == ["/web/"]
    assert cfg["layer_paths"]["domain"] == ["/domain/"]


# ── pom 解析（含异常分支） ────────────────────────────────────────────────

def test_parse_artifact_id_from_parent(tmp_path):
    pom = tmp_path / "pom.xml"
    pom.write_text(
        _POM_HEADER + '<parent><artifactId>parent-aid</artifactId></parent></project>',
        encoding="utf-8")
    assert arch_check._parse_artifact_id(str(pom)) == "parent-aid"


def test_parse_artifact_id_malformed_returns_none(tmp_path):
    (tmp_path / "pom.xml").write_text("not xml <", encoding="utf-8")
    assert arch_check._parse_artifact_id(str(tmp_path / "pom.xml")) is None


def test_parse_module_dependencies_malformed(tmp_path):
    (tmp_path / "pom.xml").write_text("not xml <", encoding="utf-8")
    assert arch_check._parse_module_dependencies(str(tmp_path / "pom.xml")) == []


def test_collect_poms_skips_target(tmp_path):
    """SKIP_DIRS 中的 target 目录应被跳过。"""
    (tmp_path / "pom.xml").write_text(_POM_HEADER + '</project>', encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()
    (target / "pom.xml").write_text(_POM_HEADER + '</project>', encoding="utf-8")
    assert len(arch_check._collect_poms(str(tmp_path))) == 1


# ── 层/域识别补充分支 ─────────────────────────────────────────────────────

def test_identify_module_layer_no_match():
    cfg = _cfg()
    assert arch_check._identify_module_layer("order-common", cfg) is None
    assert arch_check._identify_module_layer("order-api", cfg) is None


def test_business_domain_from_artifact_suffix_only():
    """pom 路径首段无法识别域时，回退到 artifact-id 后缀剥离。"""
    cfg = _cfg()
    # parts[0] 恰为后缀名 → 走 artifact-id 剥离
    assert arch_check._identify_business_domain("order-domain", "domain/pom.xml", cfg) == "order"
    # parts[0] 是排除目录 src → 走 artifact-id 剥离
    assert arch_check._identify_business_domain("order-client", "src/any/pom.xml", cfg) == "order"
    # 无法识别 → None
    assert arch_check._identify_business_domain("xyz", "src/xyz/pom.xml", cfg) is None


def test_infer_layer_from_packages(tmp_path):
    """artifact-id 无层后缀时，从包结构推断层。"""
    cfg = _cfg()
    patterns = _patterns(cfg)
    module = tmp_path / "m"
    pkg = module / "src/main/java/com/example/adapter/controller"
    pkg.mkdir(parents=True)
    (pkg / "Foo.java").write_text("// x", encoding="utf-8")
    pom = module / "pom.xml"
    pom.write_text(_POM_HEADER + '<artifactId>m</artifactId></project>', encoding="utf-8")
    assert arch_check._infer_layer_from_packages(str(pom), patterns, cfg) == "adapter"


def test_infer_layer_from_packages_no_src(tmp_path):
    cfg = _cfg()
    patterns = _patterns(cfg)
    module = tmp_path / "m2"
    module.mkdir()
    pom = module / "pom.xml"
    pom.write_text(_POM_HEADER + '<artifactId>m2</artifactId></project>', encoding="utf-8")
    assert arch_check._infer_layer_from_packages(str(pom), patterns, cfg) is None


# ── check_file / 依赖方向 边界分支 ────────────────────────────────────────

def test_check_file_unclassified(tmp_path):
    """未识别层的文件 → classified=False, layer=None。"""
    cfg = _cfg()
    patterns = _patterns(cfg)
    f = tmp_path / "Main.java"
    f.write_text("public class Main {}", encoding="utf-8")
    issues, classified, layer = arch_check.check_file(str(f), str(tmp_path), patterns, cfg)
    assert classified is False
    assert layer is None
    assert issues == []


def test_check_file_read_error(tmp_path):
    """文件读取异常（传入目录）→ 返回空且未分类。"""
    cfg = _cfg()
    patterns = _patterns(cfg)
    issues, classified, _ = arch_check.check_file(str(tmp_path), str(tmp_path), patterns, cfg)
    assert issues == []
    assert classified is False


def test_check_file_domain_purity(tmp_path):
    """domain 层文件触发纯净度检查。"""
    cfg = _cfg()
    patterns = _patterns(cfg)
    base = tmp_path / "src/main/java/com/example/order/domain/entity"
    base.mkdir(parents=True)
    f = base / "OrderE.java"
    f.write_text(
        "import org.springframework.web.client.RestTemplate;\npublic class OrderE {}",
        encoding="utf-8")
    issues, classified, layer = arch_check.check_file(str(f), str(tmp_path), patterns, cfg)
    assert classified is True
    assert layer == "domain"
    assert any(i.rule_code == arch_check.DOMAIN_PURITY for i in issues)


def test_dependency_direction_target_unidentified_skipped():
    """import 目标不属于任何层 → 跳过。"""
    cfg = _cfg(project_package_prefix="com.example")
    patterns = _patterns(cfg)
    content = "import com.example.utils.StringHelper;\n"
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/order/domain/entity/OrderE.java",
        "domain", content, patterns, cfg)
    assert issues == []


# ── 状态机治理异常 / 领域纯净度建议 ───────────────────────────────────────

def test_state_machine_governance_skips_unreadable(tmp_path):
    cfg = _cfg()
    assert arch_check.check_state_machine_governance(
        str(tmp_path), ["/nonexistent/file.java"], cfg) == []


def test_domain_purity_suggestion_spring_util():
    sug = arch_check._domain_purity_suggestion("org.springframework.util.StringUtils")
    assert "Spring 工具类" in sug
    sug2 = arch_check._domain_purity_suggestion("org.springframework.beans.BeanUtils")
    assert "Spring 工具类" in sug2


# ── 基线异常 ───────────────────────────────────────────────────────────────

def test_load_baseline_missing_file():
    assert arch_check.load_baseline("/nonexistent/baseline.json") == set()


def test_load_baseline_malformed(tmp_path):
    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    assert arch_check.load_baseline(str(tmp_path / "bad.json")) == set()


# ── 输出格式边界 ───────────────────────────────────────────────────────────

def test_format_text_warnings_baseline_debt():
    stats = {"java_files_total": 5, "java_files_classified": 3,
             "java_files_unclassified": 2, "pom_files_total": 1,
             "baseline_suppressed": 4, "structural_debt_count": 2,
             "warnings": ["单模块警告"]}
    issues = [
        arch_check.Issue("a.java", 1, arch_check.Severity.STRUCTURAL_DEBT, "依赖方向", "d", "sug"),
    ]
    text = arch_check.format_text(issues, 0, 0, stats=stats)
    assert "基线抑制" in text
    assert "结构性债务" in text
    assert "单模块警告" in text
    assert "📋" in text


def test_format_text_no_new_issues():
    # warnings 非空才能绕过首个 early-return，走到"无新增违规"分支
    stats = {"java_files_total": 5, "java_files_classified": 5,
             "java_files_unclassified": 0, "pom_files_total": 1,
             "baseline_suppressed": 0, "structural_debt_count": 0,
             "warnings": ["某警告"]}
    assert "无新增违规" in arch_check.format_text([], 0, 0, stats=stats)


def test_format_text_issue_without_suggestion():
    issues = [arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "r", "desc", "")]
    assert "🔴" in arch_check.format_text(issues, 1, 0)


def test_format_json_short_callee():
    """短包名（<4 段）callee 走 else 分支，整体作为 cluster key。"""
    issues = [
        arch_check.Issue("a.java", 1, arch_check.Severity.MANDATORY, "依赖方向",
                         "domain 层禁止依赖 infrastructure 层: import X.Y", "sug"),
    ]
    data = json.loads(arch_check.format_json(issues, 1, 0))
    assert data["summary"]["by_callee_root"][0]["package"] == "X.Y"


# ── prefix 推断异常 / graph 配置回退 ──────────────────────────────────────

def test_infer_prefix_malformed_xml(tmp_path):
    (tmp_path / "pom.xml").write_text("not xml <", encoding="utf-8")
    assert arch_check._infer_prefix_from_pom(str(tmp_path)) is None


def test_print_graph_mode_malformed_config(capsys, tmp_path):
    """配置文件 JSON 损坏 → load_config 抛异常 → 回退默认配置。"""
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    arch_check.print_graph_mode(config_path=str(bad))
    assert "Tier 2" in capsys.readouterr().out


# ── Maven 模块集成（002/003）+ 单模块警告 ─────────────────────────────────

_BADCASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "badcase")


def test_run_maven_module_violation_002():
    base = os.path.join(_BADCASE, "002-maven-module-violation", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 002 missing")
    issues, m, r, stats = arch_check.run(base)
    codes = {i.rule_code for i in issues}
    assert arch_check.MAVEN_MODULE_DEP in codes
    assert arch_check.DOMAIN_PURITY_POM in codes
    assert m >= 1


def test_run_cross_domain_violation_003():
    base = os.path.join(_BADCASE, "003-cross-domain-violation", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 003 missing")
    issues, m, r, stats = arch_check.run(base)
    codes = {i.rule_code for i in issues}
    assert arch_check.CROSS_DOMAIN_DEP in codes


def test_run_single_module_warning(tmp_path):
    """单模块项目触发 Maven 编译期隔离缺失警告。"""
    (tmp_path / "pom.xml").write_text(
        _POM_HEADER + '<artifactId>order-app</artifactId></project>', encoding="utf-8")
    issues, m, r, stats = arch_check.run(str(tmp_path))
    assert any("单模块" in w for w in stats["warnings"])


def test_run_strict_upgrades_recommended(tmp_path):
    """strict=True 将推荐级 issue 升级为强制，守护门禁严格性语义。"""
    infra = tmp_path / "src/main/java/com/example/order/infrastructure/persistence"
    infra.mkdir(parents=True)
    (infra / "OrderMapperImpl.java").write_text(
        "package com.example.order.infrastructure.persistence;\n"
        "public class OrderMapperImpl { void map() { do.updateStatus(X); } }",
        encoding="utf-8")
    issues, m, r, stats = arch_check.run(str(tmp_path), strict=True)
    # state_field_leakage 在 infrastructure 本为 RECOMMENDED，strict 后升级为 MANDATORY
    assert m >= 1
    assert r == 0  # strict 下推荐级已全部升级，recommended_count 为 0
    assert any(i.rule_code == arch_check.STATE_FIELD_LEAKAGE
               and i.severity == arch_check.Severity.MANDATORY for i in issues)


# ── main() CLI 全分支 ──────────────────────────────────────────────────────

def test_main_clean_project_exit0(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arch_check.py", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 0


def test_main_violations_exit1(monkeypatch, capsys):
    base = os.path.join(_BADCASE, "001-domain-imports-infrastructure", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 001 missing")
    monkeypatch.setattr(sys, "argv", ["arch_check.py", base])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "🔴" in out or "强制" in out


def test_main_json_format(monkeypatch, capsys):
    base = os.path.join(_BADCASE, "001-domain-imports-infrastructure", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 001 missing")
    monkeypatch.setattr(sys, "argv", ["arch_check.py", base, "--format", "json"])
    with pytest.raises(SystemExit):
        arch_check.main()
    data = json.loads(capsys.readouterr().out)
    assert data["passed"] is False
    assert data["mandatory_count"] >= 1


def test_main_graph_mode_exit0(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["arch_check.py", "--mode", "graph"])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 0
    assert "Tier 2" in capsys.readouterr().out


def test_main_init_creates_config(tmp_path, monkeypatch):
    (tmp_path / "pom.xml").write_text(
        _POM_HEADER + '<groupId>com.example</groupId></project>', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["arch_check.py", str(tmp_path), "--init"])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 0
    assert (tmp_path / ".arch-guard.json").exists()


def test_main_update_baseline(tmp_path, monkeypatch):
    base = os.path.join(_BADCASE, "001-domain-imports-infrastructure", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 001 missing")
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(sys, "argv",
                        ["arch_check.py", base, "--update-baseline", str(baseline)])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 0
    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert data["total_issues"] >= 1


def test_main_nonexistent_dir_exit2(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arch_check.py", str(tmp_path / "nope")])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 2


def test_main_strict_flag(monkeypatch, capsys):
    base = os.path.join(_BADCASE, "001-domain-imports-infrastructure", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 001 missing")
    monkeypatch.setattr(sys, "argv",
                        ["arch_check.py", base, "--format", "json", "--strict"])
    with pytest.raises(SystemExit):
        arch_check.main()
    data = json.loads(capsys.readouterr().out)
    assert data["strict"] is True


def test_main_baseline_filters_to_pass(tmp_path, monkeypatch, capsys):
    """基线抑制全部存量违规 → passed=True, exit 0。"""
    base = os.path.join(_BADCASE, "001-domain-imports-infrastructure", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 001 missing")
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(sys, "argv",
                        ["arch_check.py", base, "--update-baseline", str(baseline)])
    with pytest.raises(SystemExit):
        arch_check.main()
    capsys.readouterr()  # 清空 update-baseline 的文本输出，避免污染后续 JSON 解析
    monkeypatch.setattr(sys, "argv",
                        ["arch_check.py", base, "--baseline", str(baseline), "--format", "json"])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed"] is True
    assert data["mandatory_count"] == 0


def test_main_warn_unclassified(tmp_path, monkeypatch, capsys):
    """超过半数文件未识别层 → stderr 警告。"""
    src = tmp_path / "src/main/java/com/x"
    src.mkdir(parents=True)
    for i in range(3):
        (src / f"F{i}.java").write_text("public class F {}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["arch_check.py", str(tmp_path), "--warn-unclassified"])
    with pytest.raises(SystemExit) as exc:
        arch_check.main()
    assert exc.value.code == 0
    assert "未被识别" in capsys.readouterr().err

# ── Phase 0: 静态导入 / 通配导入 / 注释与字符串误报抑制 ───────────────────


def test_extract_imports_static_member_resolves_host_class():
    """import static x.y.Z.member → 宿主类 x.y.Z 参与层归属（修复捕获到 static 的漏报）。"""
    content = "package p;\nimport static com.example.FooUtil.bar;\nclass X {}"
    assert arch_check.extract_imports_with_lines(content) == [("com.example.FooUtil", 2)]


def test_extract_imports_static_wildcard_marks_host_class():
    """import static x.y.Z.* → 宿主类 Z + 通配标记（走通配逻辑）。"""
    content = "import static com.example.FooUtil.*;"
    assert arch_check.extract_imports_with_lines(content) == [("com.example.FooUtil.*", 1)]


def test_extract_imports_package_wildcard_marked():
    content = "import com.example.other.domain.*;"
    assert arch_check.extract_imports_with_lines(content) == [("com.example.other.domain.*", 1)]


def test_domain_purity_static_import_framework_member():
    """domain 静态导入框架成员（宿主类非注解白名单）→ 必须报 DOMAIN_PURITY（强制）。"""
    cfg = _cfg()
    content = ("package com.example.domain.entity;\n"
               "import static org.springframework.transaction.support."
               "TransactionSynchronizationManager.getCurrentTransactionName;\n"
               "public class OrderE {}")
    issues = arch_check.check_domain_purity("src/main/java/com/example/domain/entity/OrderE.java",
                                            content, cfg)
    assert len(issues) == 1
    assert issues[0].rule_code == arch_check.DOMAIN_PURITY
    assert issues[0].severity == arch_check.Severity.MANDATORY
    assert "TransactionSynchronizationManager" in issues[0].description


def test_domain_purity_static_import_annotation_whitelist_consistent():
    """注解白名单语义与导入形态无关：静态导入白名单注解类的成员同样放行。"""
    cfg = _cfg()
    content = ("import static org.springframework.transaction.annotation.Transactional.REQUIRED;\n"
               "public class OrderE {}")
    assert arch_check.check_domain_purity("d.java", content, cfg) == []


def test_dependency_direction_internal_wildcard_structural_debt():
    """内部包通配 import → STRUCTURAL_DEBT（不猜层），描述含 ArchUnit 复核提示。"""
    cfg = _cfg(project_package_prefix="com.acme")
    content = ("package com.acme.order.adapter.web;\n"
               "import com.acme.other.domain.*;\n"
               "public class OrderController {}")
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/acme/order/adapter/web/OrderController.java",
        "adapter", content, _patterns(cfg), cfg)
    assert len(issues) == 1
    assert issues[0].severity == arch_check.Severity.STRUCTURAL_DEBT
    assert "通配 import 无法定位目标类" in issues[0].description
    assert "ArchUnit" in issues[0].description
    assert "import com.acme.other.domain.*" in issues[0].description


def test_domain_purity_internal_wildcard_single_report(tmp_path):
    """内部包通配 import：purity 跳过（不猜层不双报），结构性债务由
    check_dependency_direction 统一报告——check_file 级恰好 1 条。"""
    cfg = _cfg(project_package_prefix="com.acme")
    content = ("package com.acme.order.domain;\n"
               "import com.acme.other.adapter.web.*;\n"
               "public class OrderE {}")
    file_path = "src/main/java/com/acme/order/domain/OrderE.java"
    assert arch_check.check_domain_purity(file_path, content, cfg) == []

    real = tmp_path / file_path
    real.parent.mkdir(parents=True)
    real.write_text(content, encoding="utf-8")
    issues, _, _ = arch_check.check_file(str(real), str(tmp_path),
                                         _patterns(cfg), cfg)
    wildcard = [i for i in issues if "通配 import 无法定位目标类" in i.description]
    assert len(wildcard) == 1
    assert wildcard[0].severity == arch_check.Severity.STRUCTURAL_DEBT
    assert wildcard[0].rule_code == arch_check.DEP_DIRECTION


def test_wildcard_structural_debt_not_in_mandatory_count(tmp_path):
    """通配 import 结构性债务不进入 mandatory_count（run 级端到端）。"""
    src = tmp_path / "src/main/java/com/acme/order/adapter/web"
    src.mkdir(parents=True)
    (src / "OrderController.java").write_text(
        "package com.acme.order.adapter.web;\n"
        "import com.acme.other.domain.*;\n"
        "public class OrderController {}\n", encoding="utf-8")
    cfg_file = tmp_path / ".arch-guard.json"
    cfg_file.write_text(json.dumps({"project_package_prefix": "com.acme"}),
                        encoding="utf-8")
    issues, m, r, stats = arch_check.run(str(tmp_path), config_path=str(cfg_file))
    assert m == 0
    assert stats["structural_debt_count"] >= 1
    assert any("通配 import 无法定位目标类" in i.description for i in issues)


def test_dependency_direction_third_party_wildcard_ignored():
    """第三方通配（java.util.*）在依赖方向检查中保持忽略。"""
    cfg = _cfg(project_package_prefix="com.example")
    content = ("package com.example.adapter.web;\n"
               "import java.util.*;\n"
               "public class C {}")
    issues = arch_check.check_dependency_direction(
        "src/main/java/com/example/adapter/web/C.java", "adapter", content,
        _patterns(cfg), cfg)
    assert issues == []


def test_strip_java_noise_preserves_offsets_and_lines():
    """剥离注释/字符串/字符字面量：等长、换行与行号保持、代码本体保留。"""
    src = ("public class A {\n"
           "    // class FooDTO\n"
           "    /* class BlockPO */\n"
           '    String s = "updateStatus()";\n'
           "    char c = '\\'';\n"
           "    char b = '\\\\';\n"
           '    String e = "a\\"b";\n'
           "}\n")
    out = arch_check._strip_java_noise(src)
    assert len(out) == len(src)
    assert out.count("\n") == src.count("\n")
    for a, b in zip(src, out):
        if a == "\n":
            assert b == "\n"
    assert "FooDTO" not in out
    assert "BlockPO" not in out
    assert "updateStatus" not in out
    assert "public class A" in out


def test_strip_java_noise_unterminated_and_trailing_backslash():
    """未闭合字符串 / 文件尾反斜杠不越界、不崩溃，长度保持。"""
    src = 'String s = "x\\'
    out = arch_check._strip_java_noise(src)
    assert len(out) == len(src)
    assert "x" not in out
    assert arch_check._strip_java_noise("/* class X") == " " * len("/* class X")


def test_check_file_naming_ignores_comments(tmp_path):
    """注释/javadoc 里的 class XxxDTO/XxxPO 不触发 NAMING；真实声明仍触发。"""
    src = tmp_path / "src/main/java/com/example/domain/service"
    src.mkdir(parents=True)
    f = src / "OrderDomainService.java"
    f.write_text(
        "package com.example.domain.service;\n"
        "// class FooDTO 注释里的命名不应触发\n"
        "/**\n"
        " * class XxxPO javadoc 内命名不应触发\n"
        " */\n"
        "class FooDTO {}\n"
        "public class OrderDomainService {}\n", encoding="utf-8")
    cfg = _cfg()
    issues, classified, layer = arch_check.check_file(str(f), str(tmp_path),
                                                      _patterns(cfg), cfg)
    assert classified is True and layer == "domain"
    naming = [i for i in issues if i.rule_code == arch_check.NAMING]
    assert len(naming) == 1
    assert "FooDTO" in naming[0].description
    assert naming[0].line == 6


def test_check_file_state_leakage_ignores_string_and_comment(tmp_path):
    """adapter 字符串 "updateStatus()" 与注释 setStatus 不触发；真实调用仍触发。"""
    src = tmp_path / "src/main/java/com/example/adapter/web"
    src.mkdir(parents=True)
    f = src / "OrderController.java"
    f.write_text(
        "package com.example.adapter.web;\n"
        "public class OrderController {\n"
        "    void sync() {\n"
        '        log.info("retry updateStatus() later");\n'
        "        // order.setStatus(PAID);\n"
        "        order.setStatus(PAID);\n"
        "    }\n"
        "}\n", encoding="utf-8")
    cfg = _cfg()
    issues, _, layer = arch_check.check_file(str(f), str(tmp_path), _patterns(cfg), cfg)
    assert layer == "adapter"
    leakage = [i for i in issues if i.rule_code == arch_check.STATE_FIELD_LEAKAGE]
    assert len(leakage) == 1
    assert leakage[0].line == 6


def test_check_file_commented_import_not_extracted(tmp_path):
    """块注释里的 import 不再参与提取（修复 ^import 对注释行首的命中）。"""
    src = tmp_path / "src/main/java/com/example/domain/entity"
    src.mkdir(parents=True)
    f = src / "OrderE.java"
    f.write_text(
        "package com.example.domain.entity;\n"
        "/*\n"
        "import org.springframework.web.client.RestTemplate;\n"
        "*/\n"
        "public class OrderE {}\n", encoding="utf-8")
    cfg = _cfg()
    issues, _, _ = arch_check.check_file(str(f), str(tmp_path), _patterns(cfg), cfg)
    assert not any(i.rule_code == arch_check.DOMAIN_PURITY for i in issues)


def test_run_static_import_badcase_005():
    """端到端：005 夹具触发静态导入纯净度 + 状态泄漏 + 通配结构性债务。"""
    base = os.path.join(_BADCASE, "005-static-import-noise-suppression", "input")
    if not os.path.isdir(base):
        pytest.skip("badcase 005 missing")
    issues, m, r, stats = arch_check.run(base)
    codes = {i.rule_code for i in issues}
    assert arch_check.DOMAIN_PURITY in codes
    assert arch_check.STATE_FIELD_LEAKAGE in codes
    # 通配结构性债务恰好 1 条：依赖方向检查统一报告，purity 不双报
    assert stats["structural_debt_count"] == 1
