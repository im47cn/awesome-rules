---
name: doc-gen
description: >
  DDD 技术文档自动生成。将 Java DDD 项目自动转换为交互式静态文档站点，
  包括架构图（Mermaid 可点击）、DDD 分层视图、OpenAPI 交互文档（Scalar）、
  数据库 ER 图、全局搜索（Pagefind）和嵌入的 Architecture AI Agent。
  当用户提到：生成技术文档、生成架构文档、项目文档站点、DDD 文档、
  API 文档站点、架构图生成时激活。
files:
  - DESIGN.md
  - README.md
  - ci/archive-manifests.example.yml
  - fixtures/cola-sample/.doc-gen.json
  - fixtures/cola-sample/business-context.md
  - fixtures/cola-sample/pom.xml
  - fixtures/cola-sample/src/main/java/com/example/demo/Application.java
  - fixtures/cola-sample/src/main/java/com/example/demo/adapter/consumer/DemoMQConsumer.java
  - fixtures/cola-sample/src/main/java/com/example/demo/adapter/scheduler/DemoJob.java
  - fixtures/cola-sample/src/main/java/com/example/demo/adapter/web/DemoController.java
  - fixtures/cola-sample/src/main/java/com/example/demo/app/executors/DemoCmdExe.java
  - fixtures/cola-sample/src/main/java/com/example/demo/client/api/DemoInter.java
  - fixtures/cola-sample/src/main/java/com/example/demo/client/api/DemoServiceI.java
  - fixtures/cola-sample/src/main/java/com/example/demo/client/dto/DemoCO.java
  - fixtures/cola-sample/src/main/java/com/example/demo/domain/DemoEntity.java
  - fixtures/cola-sample/src/main/java/com/example/demo/domain/gateway/DemoGateway.java
  - fixtures/cola-sample/src/main/java/com/example/demo/infrastructure/DemoDO.java
  - fixtures/cola-sample/src/main/java/com/example/demo/infrastructure/gatewayimpl/DemoGatewayImpl.java
  - fixtures/cola-sample/src/main/java/com/example/demo/infrastructure/mapper/DemoMapper.java
  - schemas/adrs.schema.json
  - schemas/articles.schema.json
  - schemas/business-context.schema.json
  - schemas/common.schema.json
  - schemas/cross-domain.schema.json
  - schemas/database.schema.json
  - schemas/domain.schema.json
  - schemas/index.schema.json
  - schemas/meta.schema.json
  - schemas/risks.schema.json
  - schemas/state-machines.schema.json
  - scripts/builder/__init__.py
  - scripts/builder/astro.py
  - scripts/builder/writer.py
  - scripts/delta.py
  - scripts/doc_gen.py
  - scripts/doctypes.py
  - scripts/generator/__init__.py
  - scripts/generator/adr.py
  - scripts/generator/article.py
  - scripts/generator/layers.py
  - scripts/generator/manifest.py
  - scripts/generator/openapi.py
  - scripts/generator/risks.py
  - scripts/scanner/__init__.py
  - scripts/scanner/business_context.py
  - scripts/scanner/ddl.py
  - scripts/scanner/infra_db.py
  - scripts/scanner/java.py
  - scripts/scanner/maven.py
  - scripts/scanner/po_scanner.py
  - scripts/scanner/state_machine.py
  - scripts/tests/conftest.py
  - scripts/tests/test_adr.py
  - scripts/tests/test_article.py
  - scripts/tests/test_astro.py
  - scripts/tests/test_business_context.py
  - scripts/tests/test_ddl.py
  - scripts/tests/test_delta.py
  - scripts/tests/test_deprecated.py
  - scripts/tests/test_doc_gen.py
  - scripts/tests/test_infra_db.py
  - scripts/tests/test_java.py
  - scripts/tests/test_layers.py
  - scripts/tests/test_manifest.py
  - scripts/tests/test_manifest_extend.py
  - scripts/tests/test_maven.py
  - scripts/tests/test_openapi.py
  - scripts/tests/test_po_scanner.py
  - scripts/tests/test_risks.py
  - scripts/tests/test_schema_validator.py
  - scripts/tests/test_smoke_pages.py
  - scripts/tests/test_state_machine.py
  - scripts/tests/test_suffix_map.py
  - scripts/tests/test_writer.py
  - scripts/validator.py
  - template/.gitignore
  - template/astro.config.mjs
  - template/package-lock.json
  - template/package.json
  - template/public/favicon.svg
  - template/public/hero-icon.svg
  - template/public/impact.js
  - template/public/sitepins-manifest.json
  - template/scripts/generate-pages.mjs
  - template/scripts/lib/generators.mjs
  - template/scripts/lib/utils.mjs
  - template/src/.well-known/sitepins.json
  - template/src/assets/changelogs.svg
  - template/src/assets/code-block.svg
  - template/src/assets/content.svg
  - template/src/assets/element.svg
  - template/src/assets/layouts.svg
  - template/src/assets/logo-dark.svg
  - template/src/assets/logo-light.svg
  - template/src/components/ArchitectureDiagram.astro
  - template/src/components/ChatAgent.astro
  - template/src/components/override-components/PageFrame.astro
  - template/src/config/config.json
  - template/src/config/locals.json
  - template/src/config/social.json
  - template/src/content.config.ts
  - template/src/content/docs/architecture.mdx
  - template/src/content/docs/domains/demo/adapter.mdx
  - template/src/content/docs/domains/demo/index.mdx
  - template/src/content/docs/domains/demo/infrastructure.mdx
  - template/src/content/docs/index.mdx
  - template/src/content/i18n/en.json
  - template/src/content/i18n/fr.json
  - template/src/pages/api/index.astro
  - template/src/styles/global.css
  - template/tsconfig.json
---

# DDD 技术文档自动生成 (doc-gen)

单项目入门文档（新人 5 分钟看懂一个项目）；多项目聚合归独立仓架构鹰眼（`~/sources/arch-hawkeye`）。
架构图、功能清单、站点结构、Schema 契约原理、CI 归档等背景见
[README](README.md)（渐进式加载：本文件只保留运行与验收所需）。

## 快速使用

### 新项目接入（3 步）

```bash
# 1. 初始化项目配置（从 pom.xml 自动推断 groupId）
python3 scripts/doc_gen.py /path/to/java-project --init

# 2. 生成 manifest + 构建静态站点
python3 scripts/doc_gen.py /path/to/java-project --build --output docs-site/

# 3. 启动预览
cd docs-site/ && npm run dev
```

### 仅生成数据清单 / 从已有 manifest 构建

```bash
python3 scripts/doc_gen.py /path/to/java-project --manifest-only --output manifest.json
python3 scripts/doc_gen.py --from-manifest manifest.json --build --output docs-site/
```

## 项目配置（.doc-gen.json）

`--init` 自动生成；域名中英映射、业务上下文等手工调整项见
[README](README.md#项目配置)。`project_repo` 支持链接模板占位符：

```jsonc
// 推荐：完整链接模板，{revision}/{path} 占位符 —— 各平台 URL 形态全覆盖
"project_repo": "https://codeup.aliyun.com/{orgId}/{repo}/blob/{revision}/{path}"
// 兼容：裸仓库 URL —— 默认 GitHub/Gitea 风格 {repo}/blob/{revision}/{path}
"project_repo": "https://github.com/user/repo"
```

## 架构演进 diff（delta）

```bash
python3 scripts/doc_gen.py diff <base快照目录> <head快照目录> \
  --output delta.json --markdown delta.md
```

- 六维度 receipt：组件（含 moved 分级）/聚合/数据表/状态机/跨域依赖/API 端点；
  schema_version 不相等 → `exit 2` 拒绝
- **站点渲染**：`--output <站点>/doc-manifest/delta.json` 后 `--build` 自动生成
  「🔀 架构演进」页面（统计卡 + 六维度表 + 变更明细）
- CI 归档约定（master push 归档快照、PR 门禁贴 delta.md）见
  [`ci/archive-manifests.example.yml`](ci/archive-manifests.example.yml)

## 退出码与验收契约（强制）

- **退出码 0 = 成功；1 = 阶段失败（manifest 校验失败 / npm 缺失或 install/build 失败）；2 = 用法错误。非零退出码绝不可描述为成功**
- 每次运行产出 `doc-manifest/receipt.json`（`ok` 当且仅当无 `fail`；`warn` 是事实降级不阻断）。交付时必须引用 receipt 检查项，不得声称未执行的检查
- 风险扫描的 `critical` 数量必须如实转述给用户，不得省略
- npm 构建失败从静默跳过改为 `exit 1`（breaking）：依赖旧行为的脚本需显式降级
