# doc-gen — DDD 技术文档自动生成

将 Java DDD 项目自动转换为带 AI 助手的交互式静态文档站点。

## 核心特性

- **零配置启动**：`--init` 自动从 pom.xml 推断配置
- **7 层扫描**：Maven 模块 → Java 类 → 注解 → 方法 → 字段 → DDL → 依赖
- **交互式架构图**：Mermaid 渲染，节点可点击导航到详情页
- **AI 架构助手**：页面内嵌 RAG 检索 + 自然语言问答
- **纯静态产物**：构建输出为静态文件，GitHub Pages / Vercel 零成本部署
- **Schema 契约**：manifest 分片由 JSON Schema 锁定（`schema_version: 1`），生成端自检 + 消费端门禁，零依赖校验器
- **诚实退出码**：非零退出绝不代表成功；每次运行产出 `receipt.json` 验收清单；npm 构建失败不再静默跳过
- **Revision-pinned evidence**：manifest 钉定生成时刻的 git SHA，`--from-manifest` 重建时警告文档过期（staleCommits）

## 快速开始

```bash
# 1. 初始化配置
python3 scripts/doc_gen.py /path/to/java-project --init

# 2. 生成文档站点
python3 scripts/doc_gen.py /path/to/java-project --build --output docs-site/

# 3. 本地预览
cd docs-site/
npm install
npm run dev      # http://localhost:4321
```

## 功能覆盖

| 功能 | 说明 | 状态 |
| --- | --- | --- |
| Maven 模块扫描 | 解析 pom.xml 依赖关系、模块结构 | ✅ |
| Java 源码解析 | 提取类、方法、字段、注解信息 | ✅ |
| DDD 分层识别 | 按包路径 + 类名后缀 + 注解识别分层 | ✅ |
| 全景架构图 | Mermaid `graph TD`，节点可点击导航 | ✅ |
| DDD 分层图 | 展示 Adapter→App→Domain←Infra 依赖方向 | ✅ |
| 聚合结构图 | Mermaid `classDiagram` 展示聚合根/实体/VO 关系 | ✅ |
| 数据库 ER 图 | 从 DDL 文件解析生成 | ✅ |
| REST API 文档 | Scalar 交互式渲染（Try-It） | ✅ |
| 全局搜索 | Pagefind 构建后索引 | 🚧 |
| Architecture AI Agent | 本地 RAG 检索 + LLM 问答（页面内嵌，免 API Key 基础模式） | ✅ |
| 架构风险扫描 | 复用 arch-guard 规则检测 DDD 违规 | ✅ |
| 状态转换图 | 扫描状态枚举/Spring/Cola 状态机 → stateDiagram + 质量审查 | ✅ |
| ADR 扫描 | 架构决策记录提取与展示 | ✅ |
| 业务全景 | 客户/角色/场景/流程：人工 `business-context.md` + 代码弱信号（`@PreAuthorize`/状态机） | ✅ |
| 运行时证据提取 | 5 通道供架构鹰眼跨项目链路：Feign/MQ（含常量两层解析）/Redis key/`@XxlJob`/`@Scheduled` | ✅ |
| 违规责任归属 | risks.json 逐条 `git blame`（author + introducedAt，失败降级 null） | ✅ |
| 多项目聚合 | 已迁移至架构鹰眼（`arch-hawkeye/`），doc-gen 专注单项目 | ➡️ |
| CI 集成 | GitHub Actions 自动构建部署 | 📋 |

> ✅ = 已实现 🚧 = 模板就绪，CLI 集成中 📋 = 计划中

## 生成的站点页面结构

```
/                              首页 — 项目全景架构大图
/impact/                       变更影响分析 — 输入组件实时计算影响链（客户端 BFS）
/architecture/                 架构总览 — 分层依赖图 + 图例
/domains/{domain}/             域概览 — 域内分层图 + 聚合列表
/domains/{domain}/adapter/     接口层 — Controller 表格 + 端点详情
/domains/{domain}/application/ 应用层 — Executor 列表 + 用例说明
/domains/{domain}/domain/      领域层 — 聚合详情 + 实体/VO/事件
/domains/{domain}/infrastructure/ 基础设施层 — 仓储实现 + 网关
/database/                     数据库 — ER 图 + 逐表结构说明
/state-machines/               状态机 — stateDiagram 转换图 + 死状态/不可达审查
/business/                     业务全景 — 客户/角色/场景/流程（可选）
/api/                          OpenAPI — 交互式 API 文档（Scalar）
```

## Architecture AI Agent

每个生成的站点右下角嵌入 AI 架构助手：本地 RAG 从 `doc-manifest.json` 实时检索，
支持中英文自然语言问答（如"Order 聚合包含哪些实体？""t_order 表有哪些索引？"），
基础模式完全本地运行、免 API Key。

## 项目配置

`--init` 自动生成 `.doc-gen.json`，常用手工调整项：

| 配置项 | 作用 |
| --- | --- |
| `project_name` / `project_description` | 站点标题 / 描述（SEO） |
| `project_group_id` | Maven groupId（自动推断） |
| `project_repo` | 源码链接模板（含 `{revision}/{path}` 占位符，见 SKILL.md） |
| `domain_names` | 域名英文 → 中文映射 |
| `business_context_file` | 业务上下文 md 路径（默认根目录/`docs/` 下 `business-context.md`） |

## 与架构鹰眼的关系（职责边界）

doc-gen 专注**单项目**入门文档；多项目聚合、跨项目真实链路、治理闭环归**架构鹰眼**
（`arch-hawkeye/`），以 `doc-manifest/` 为唯一交接物（契约见
[`../../arch-hawkeye/AH-MANIFEST.md`](../../arch-hawkeye/AH-MANIFEST.md)）。
原 `doc_gen.py aggregate` 子命令已迁移至 `arch-hawkeye/scripts/hawkeye.py`；
单项目文档站渲染复用 doc-gen 的 Astro 模板（单一真相源）。

## Manifest Schema 契约（原理）

分片结构与 `schemas/*.json` 锁定（`schema_version: 1` const 锁定，破坏性变更才 bump 2）：

- 生成端：`ManifestWriter.write()` 写入后自检，未通过契约 = 生成器 bug，直接失败
- 消费端：`--from-manifest` 构建前强制校验；旧版 manifest（无 `schema_version`）warn 跳过
- drift 防线：`tests/test_schema_validator.py` COLA golden test——生成器改字段而 schema 未同步即红
- 校验器 `scripts/validator.py` 为内置子集实现，零第三方依赖

## Revision-pinned Evidence（原理）

`meta.json` 携带生成时刻证据锚点（`repo_url`/`revision`/`generatedAt`/`dirty`）：
组件页类名渲染为钉定版本源码链接（`sourceLine` 带 `#L` 锚点直达声明行，等长注释剥离
保证行号精确）；`--from-manifest` 重建时计算 `staleCommits` 警告文档过期；无 git 降级
`revision: null` 不阻断。

## CI 归档约定（delta 流程前置）

master push 时 `scan --manifest-only --output archive/<SHA>` 归档到独立分支
`doc-gen-archive`；PR 门禁用 merge-base 快照 vs PR 快照生成 `delta.md` 贴 PR。
样例：[`ci/archive-manifests.example.yml`](ci/archive-manifests.example.yml)。

## 文档
- [技能定义](SKILL.md) — 完整使用文档（含退出码与验收契约）
- [技术设计](DESIGN.md) — 架构设计与数据流
- [Schema 契约](schemas/) — manifest 分片 JSON Schema（v1）
- [Astro 模板](template/) — 静态站点模板源码

## 技术栈

| 层 | 技术 |
|----|------|
| 扫描引擎 | Python 3.10+ |
| 中间格式 | JSON (doc-manifest v1) |
| 站点生成 | Astro 5 + Starlight |
| 图表渲染 | Mermaid.js |
| API 文档 | Scalar |
| 搜索 | Pagefind |
| AI Agent | 本地 RAG + 可选 LLM API |

## 与 arch-guard 协同

两个技能共享扫描基础设施（Maven 解析、Java 类扫描、分层识别），但用途不同：

| | arch-guard | doc-gen |
|----|-----------|---------|
| 目标 | 发现架构违规 | 生成技术文档 |
| 输出 | 问题列表 + 证据链 | 交互式静态站点 |
| 使用场景 | CI 门禁、代码审查 | 新人入职、架构评审、外部分享 |
