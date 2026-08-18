# arch-guard badcase 002 — Maven 模块依赖矩阵违规

check: arch_check.py

## 预期检查输出

- 脚本自动检出：Maven 模块依赖、领域层纯净度(POM)

## 背景说明

- 多模块 Maven 工程（order-start/-adapter/-app/-client/-domain/-infrastructure），pom.xml 中存在 `_MAVEN_DEP_MATRIX` 禁止的模块依赖（如 adapter → domain）
- domain 模块 pom.xml 引入 `domain_forbidden_pom` 中的框架依赖（如 spring-boot-starter）→ 领域层纯净度(POM)
