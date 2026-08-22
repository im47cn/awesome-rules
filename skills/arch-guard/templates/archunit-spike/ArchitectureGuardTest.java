// SPIKE 2a — 手写验证 ArchUnit 与 gtsp-parent/JDK17 兼容性
// 由 awesome-rules docs/design/arch-guard-evolution-design.md Phase 2a 产生
import com.tngtech.archunit.core.domain.JavaCall;
import com.tngtech.archunit.core.domain.properties.HasName;

import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;
import static com.tngtech.archunit.core.domain.JavaCall.Predicates.target;
import static com.tngtech.archunit.core.domain.properties.HasName.Predicates.nameMatching;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.layeredArchitecture;
import static com.tngtech.archunit.library.freeze.FreezingArchRule.freeze;

@AnalyzeClasses(packages = "com.wanlianyida.conttask")
class ArchitectureGuardTest {

    // ── 1. 分层依赖方向（layer_aliases: interfaces → adapter 语义） ──────────
    // 该项目实际包：interfaces（入口）与 infrastructure（实现），无标准 domain。
    // 规则：interfaces 可依赖 infrastructure；infrastructure 禁止反依赖 interfaces。
    @ArchTest
    static final ArchRule layering = freeze(layeredArchitecture().consideringOnlyDependenciesInLayers()
            .layer("interfaces").definedBy("..conttask.interfaces..")
            .layer("infrastructure").definedBy("..conttask.infrastructure..")
            .whereLayer("interfaces").mayNotBeAccessedByAnyLayer()
            .whereLayer("infrastructure").mayOnlyBeAccessedByLayers("interfaces"));

    // ── 2. 命名后缀 × 分层（对齐 _SUFFIX_RULES 的示例） ──────────────────────
    @ArchTest
    static final ArchRule dtoNaming = freeze(classes()
            .that().haveSimpleNameEndingWith("DTO")
            .should().resideInAPackage("..infrastructure.domain.dto..")
            .because("DTO 属于基础设施层契约对象（对齐 02-naming）"))
            .allowEmptyShould(true); // 项目无 *DTO 类时跳过（生成器必备处理）

    // ── 3. 状态泄漏（adapter/infrastructure 禁止改写状态，对齐 _STATUS_WRITE_RE） ──
    @ArchTest
    static final ArchRule noStatusWriteFromInfrastructure = freeze(noClasses()
            .that().resideInAnyPackage("..conttask.infrastructure..")
            .should().callCodeUnitWhere(target(
                    nameMatching("(set|change|update|modify)\\w*(Status|State)")))
            .because("状态流转属领域知识，infrastructure 不得直接改写（01 §12/§17）"));

    // ── 4. 循环依赖（Tier 1 无此能力，ArchUnit 增量价值） ────────────────────
    @ArchTest
    static final ArchRule noCycles = freeze(slices()
            .matching("com.wanlianyida.conttask.(**)")
            .should().beFreeOfCycles());

}
