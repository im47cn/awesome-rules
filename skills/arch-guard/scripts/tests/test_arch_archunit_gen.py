"""--mode archunit 生成器测试（Phase 2b）。

覆盖：规则矩阵→ArchUnit 表达的映射、层别名展开、白名单豁免、
allowEmptyShould、Java 8 兼容、prefix 强制、--verify 防漂移。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import arch_check  # noqa: E402


def _cfg(**overrides):
    cfg = json.loads(json.dumps(arch_check.DEFAULT_CONFIG))
    cfg.update(overrides)
    return cfg


def _gen(project_root=".", **overrides):
    return arch_check._generate_archunit_test(_cfg(**overrides), project_root)


def _run_cli(argv, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["arch_check.py"] + argv)
    code = 0
    try:
        arch_check.main()
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ── 1. 分层规则源自 _DEPENDENCY_RULES 列视图 ────────────────────────────────

def test_layering_from_dependency_matrix():
    src = _gen(project_package_prefix="com.x")
    # adapter 列全 False → 禁止任何层访问
    assert '.whereLayer("adapter").mayNotBeAccessedByAnyLayer()' in src
    # domain 列：application/infrastructure 为 True
    assert ('.whereLayer("domain").mayOnlyBeAccessedByLayers("application", "infrastructure")'
            in src)
    # client 列：adapter/application
    assert ('.whereLayer("client").mayOnlyBeAccessedByLayers("adapter", "application")'
            in src)


def test_layer_aliases_expanded_into_defined_by():
    src = _gen(project_package_prefix="com.x")
    # 默认别名 interfaces → adapter：层定义含两个包模式
    assert '.layer("adapter").definedBy("..adapter..", "..interfaces..")' in src


def test_custom_alias_expanded():
    src = _gen(project_package_prefix="com.x",
               layer_aliases={"facade": "adapter", "interfaces": "adapter"})
    assert '.definedBy("..adapter..", "..facade..", "..interfaces..")' in src


# ── 2. 领域层纯净度：禁入包 + 白名单豁免 ───────────────────────────────────

def test_purity_forbidden_and_whitelist():
    src = _gen(project_package_prefix="com.x")
    assert '"org.springframework.."' in src
    assert '"org.apache.ibatis.."' in src
    # 白名单：JPA + 注解包经 DescribedPredicate.not 豁免
    assert "DescribedPredicate.not(resideInAnyPackage(" in src
    assert '"jakarta.persistence.."' in src
    assert '"org.springframework.stereotype.."' in src
    assert '"org.springframework.transaction.annotation.."' in src


# ── 3. 命名规则：数量、后缀正则转换、排除前缀 ─────────────────────────────

def test_naming_rule_count_matches_suffix_rules():
    src = _gen(project_package_prefix="com.x")
    expected = len(arch_check._SUFFIX_RULES) + 4  # +layering +purity +state +cycles
    assert src.count("@ArchTest") == expected


def test_suffix_regex_conversion():
    f = arch_check._suffix_rule_to_name_pattern
    assert f(r"(?<=[a-z])Inter$") == r".*[a-z]Inter$"
    assert f(r"(?<=[a-z])(?:Status|State)Enum$") == r".*[a-z](?:Status|State)Enum$"
    assert f(r"(?<=[a-z])(?<!Status)(?<!State)Enum$") == r".*[a-z](?<!Status)(?<!State)Enum$"
    assert f(r"^Inter") is None  # 非后缀形态 → 跳过


def test_naming_excludes_and_lookbehinds_preserved():
    src = _gen(project_package_prefix="com.x")
    assert "DescribedPredicate.not(nameMatching(" in src
    assert "Hibernate" in src and "Generic" in src
    assert "(?<!Status)(?<!State)Enum$" in src


def test_all_classes_rules_allow_empty_should():
    src = _gen(project_package_prefix="com.x")
    # classes()/noClasses() 家族规则数（排除 slices/layeredArchitecture）
    n_rules = src.count("@ArchTest") - 2
    assert src.count("allowEmptyShould(true)") >= n_rules


# ── 4. 状态泄漏与循环依赖 ──────────────────────────────────────────────────

def test_state_leakage_pattern_single_source():
    src = _gen(project_package_prefix="com.x")
    assert arch_check._STATUS_WRITE_NAME_RE.replace("\\", "\\\\") in src
    assert "callCodeUnitWhere(target(nameMatching(" in src


def test_cycles_rule_with_prefix():
    src = _gen(project_package_prefix="com.wanlianyida")
    assert 'matching("com.wanlianyida.(**)")' in src


# ── 5. Java 8 兼容与 prefix 强制 ───────────────────────────────────────────

def test_java8_syntax_guards():
    src = _gen(project_package_prefix="com.x")
    for token in ("var ", "List.of", "record ", ">>>"):  # record 需 16，var 需 10
        assert token not in src


def test_prefix_required_exit_2(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    code, _, err = _run_cli([str(root), "--mode", "archunit"], monkeypatch, capsys)
    assert code == 2
    assert "project_package_prefix" in err


# ── 6. --verify 防漂移闭环 ─────────────────────────────────────────────────

def _make_proj(tmp_path):
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".arch-guard.json").write_text(
        json.dumps({"project_package_prefix": "com.example"}), encoding="utf-8")
    return str(root)


def test_verify_roundtrip(tmp_path, monkeypatch, capsys):
    root = _make_proj(tmp_path)
    out = str(tmp_path / "out")

    code, _, _ = _run_cli([root, "--mode", "archunit", "--output", out],
                          monkeypatch, capsys)
    assert code == 0
    for name in ("ArchitectureGuardTest.java", "archunit.properties", "INTEGRATION.md"):
        assert os.path.isfile(os.path.join(out, name))

    # 一致 → 0
    code, out_s, _ = _run_cli([root, "--mode", "archunit", "--verify", "--output", out],
                              monkeypatch, capsys)
    assert code == 0
    assert "一致" in out_s

    # 手改 → 1
    with open(os.path.join(out, "ArchitectureGuardTest.java"), "a",
              encoding="utf-8") as fp:
        fp.write("// hand edit\n")
    code, _, err = _run_cli([root, "--mode", "archunit", "--verify", "--output", out],
                            monkeypatch, capsys)
    assert code == 1
    assert "不一致" in err

    # 缺失 → 1
    empty = str(tmp_path / "empty")
    os.makedirs(empty, exist_ok=True)
    code, _, err = _run_cli([root, "--mode", "archunit", "--verify", "--output", empty],
                            monkeypatch, capsys)
    assert code == 1
    assert "不存在" in err


def test_guide_contains_spike_lessons():
    guide = arch_check._generate_archunit_guide(_cfg(project_package_prefix="com.x"))
    assert "lombok" in guide          # spike 踩坑：provided 不传递
    assert "allowStoreCreation=false" in guide  # CI 防误建基线
    assert "1.2.1" in guide           # ArchUnit 版本


def test_properties_freeze_store():
    props = arch_check._generate_archunit_properties()
    assert "freeze.store.default.path=src/test/resources/archguard-store" in props
    assert "allowStoreCreation=true" in props
    assert "allowStoreUpdate=true" in props


# ── 7. 试点教训（cont-task/gateway/wop-service 三项目实测） ────────────────

def test_excludes_test_classes():
    """gateway 教训：测试类在 ..domain.. 包下调用 infrastructure 被误判违规。"""
    src = _gen(project_package_prefix="com.x")
    assert "com.tngtech.archunit.core.importer.ImportOption;" in src
    assert "importOptions = ImportOption.DoNotIncludeTests.class" in src


def test_layers_pruned_to_existing(tmp_path):
    """cont-task 教训：只有 interfaces/infrastructure 两层时，不生成空层规则
    （'Layer X is empty' 也是违规行）。"""
    for d in ("interfaces", "infrastructure"):
        (tmp_path / "src/main/java/com/x" / d).mkdir(parents=True)
    cfg = _cfg(project_package_prefix="com.x")
    existing = arch_check._detect_existing_layers(str(tmp_path), cfg)
    assert existing == {"adapter", "infrastructure"}  # interfaces 是 adapter 别名

    src = _gen(project_root=str(tmp_path), project_package_prefix="com.x")
    assert '.layer("adapter")' in src
    assert '.layer("infrastructure")' in src


def test_find_generated_files_scans_src_test(tmp_path):
    """三试点实测教训：SKIP_DIRS 含 test/tests，若 _find_generated_files 照抄
    会剪掉 src/test/ 整棵子树，--verify 在 Maven 标准布局上恒报"不存在"。"""
    d = tmp_path / "src/test/java/com/x/archguard"
    d.mkdir(parents=True)
    (d / "ArchitectureGuardTest.java").write_text("// x", encoding="utf-8")
    r = tmp_path / "src/test/resources"
    r.mkdir(parents=True)
    (r / "archunit.properties").write_text("k=v", encoding="utf-8")

    test_p, props_p = arch_check._find_generated_files(str(tmp_path))
    assert test_p is not None and test_p.endswith("ArchitectureGuardTest.java")
    assert props_p is not None and props_p.endswith("archunit.properties")
