---
name: doc-gen
description: >
  DDD 技术文档自动生成。将 Java DDD 项目自动转换为交互式静态文档站点，
  包括架构图（Mermaid 可点击）、DDD 分层视图、OpenAPI 交互文档（Scalar）、
  数据库 ER 图、全局搜索（Pagefind）和嵌入的 Architecture AI Agent。
  当用户提到：生成技术文档、生成架构文档、项目文档站点、DDD 文档、
  API 文档站点、架构图生成时激活。
---

# DDD 技术文档自动生成 (doc-gen)

## 架构

```
源代码仓库 → CLI 扫描 → DocManifest JSON → Astro 构建 → 静态站点
                                    │
                                    ▼
                          Architecture AI Agent (页面内嵌)
```

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

### 仅生成数据清单

```bash
python3 scripts/doc_gen.py /path/to/java-project --manifest-only --output manifest.json
```

### 从已有 manifest 构建站点

```bash
python3 scripts/doc_gen.py --from-manifest manifest.json --build --output docs-site/
```

## 功能覆盖

| 功能                  | 说明                                                      | 状态 |
| --------------------- | --------------------------------------------------------- | ---- |
| Maven 模块扫描        | 解析 pom.xml 依赖关系、模块结构                           | ✅   |
| Java 源码解析         | 提取类、方法、字段、注解信息                              | ✅   |
| DDD 分层识别          | 按包路径 + 类名后缀 + 注解识别分层                        | ✅   |
| 全景架构图            | Mermaid `graph TD`，节点可点击导航                        | ✅   |
| DDD 分层图            | 展示 Adapter→App→Domain←Infra 依赖方向                    | ✅   |
| 聚合结构图            | Mermaid `classDiagram` 展示聚合根/实体/VO 关系            | ✅   |
| 数据库 ER 图          | 从 DDL 文件解析生成                                       | ✅   |
| REST API 文档         | Scalar 交互式渲染（Try-It）                               | ✅   |
| 全局搜索              | Pagefind 构建后索引                                       | 🚧   |
| Architecture AI Agent | 本地 RAG 检索 + LLM 问答（页面内嵌）                      | ✅   |
| 架构风险扫描          | 复用 arch-guard 规则检测 DDD 违规                         | ✅   |
| 状态转换图            | 扫描状态枚举/Spring/Cola 状态机 → stateDiagram + 质量审查 | ✅   |
| ADR 扫描              | 架构决策记录提取与展示                                    | ✅   |
| 业务全景              | 客户/角色/场景/流程：人工 `business-context.md` + 代码弱信号（`@PreAuthorize`/状态机） | ✅ |
| 多项目聚合            | 已迁移至**架构鹰眼**（`arch-hawkeye/`），doc-gen 专注单项目 | ➡️   |
| CI 集成               | GitHub Actions 自动构建部署                               | 📋   |

> ✅ = 已实现 🚧 = 模板就绪，CLI 集成中 📋 = 计划中

## 生成的站点页面结构

```
/                              首页 — 项目全景架构大图
/impact/                       变更影响分析 — 输入组件实时计算影响链（客户端 BFS，语义对齐 impact-guard）
/architecture/                 架构总览 — 分层依赖图 + 图例
/domains/{domain}/             域概览 — 域内分层图 + 聚合列表
/domains/{domain}/adapter/     接口层 — Controller 表格 + 端点详情
/domains/{domain}/application/ 应用层 — Executor 列表 + 用例说明
/domains/{domain}/domain/      领域层 — 聚合详情 + 实体/VO/事件
/domains/{domain}/infrastructure/ 基础设施层 — 仓储实现 + 网关
/database/                     数据库 — ER 图 + 逐表结构说明
/state-machines/               状态机 — stateDiagram 转换图 + 死状态/不可达审查
/business/                     业务全景 — 客户/角色/场景/流程（可选，有 business-context 时生成）
/api/                          OpenAPI — 交互式 API 文档（Scalar）
```

## Architecture AI Agent

每个生成的站点右下角都嵌入了一个 AI 架构助手，支持：

- **本地 RAG 检索**：从 `doc-manifest.json` 实时搜索组件、聚合、表结构
- **自然语言问答**：支持中文/英文提问
- **免 API Key**：基础模式完全本地运行，基于关键词检索匹配

示例对话：

- "Order 聚合包含哪些实体和值对象？"
- "Adapter 层有哪些 Controller？"
- "哪些地方依赖了 logistics 域？"
- "t_order 表有哪些索引？"

## 项目配置

运行 `--init` 自动生成 `.doc-gen.json`，也可手动创建：

```json
{
  "project_name": "order-system",
  "project_description": "订单管理系统",
  "project_group_id": "com.example",
  "project_repo": "https://github.com/example/order-system",
  "domain_names": {
    "order": "订单域",
    "logistics": "物流域",
    "settlement": "结算域"
  }
}
```

| 配置项                | 作用                         |
| --------------------- | ---------------------------- |
| `project_name`        | 站点标题                     |
| `project_description` | 站点描述（SEO）              |
| `project_group_id`    | Maven groupId（自动推断）    |
| `project_repo`        | GitHub 链接（用于 EditLink） |
| `domain_names`        | 域名英文 → 中文映射          |
| `business_context_file` | 业务上下文 md 路径（默认查根目录/`docs/` 下 `business-context.md`）|

## 与架构鹰眼的关系（职责边界）

doc-gen 专注**单项目**入门文档（初衷 1：新人 5 分钟看懂一个项目）；多项目聚合、跨项目
真实链路、治理闭环等全局能力归**架构鹰眼**（初衷 2），以 `doc-manifest/` 为唯一交接物
（契约见 [`../../arch-hawkeye/AH-MANIFEST.md`](../../arch-hawkeye/AH-MANIFEST.md)）：

```
doc-gen（生产者）                       架构鹰眼（消费者）
scan → doc-manifest/ ──── AH-MANIFEST 契约 ────▶ hawkeye.py aggregate
（单项目文档站渲染复用 doc-gen 的 Astro 模板，单一真相源）
```

原 `doc_gen.py aggregate` 子命令已迁移至 `arch-hawkeye/scripts/hawkeye.py`。

## 与 arch-guard 的关系

```
arch-guard (审查)              doc-gen (文档)
─────────────────              ──────────────
arch_check.py  ──扫描逻辑──→ doc_gen.py (复用)
  ├── pom.xml 解析       → MavenScanner
  ├── Java 文件扫描       → JavaScanner
  ├── 分层识别逻辑        → LayerIdentifier
  └── 命名后缀映射        → SUFFIX_TYPE_MAP

Cypher 查询 (Tier 2)    → 可选深度分析 (Phase 3+)
  └── 方法级依赖图        → 聚合边界自动识别
```

## Manifest Schema 契约

分片结构与 `schemas/*.json` 锁定（JSON Schema 子集，`schema_version: 1` const 锁定，破坏性变更才 bump 2）：

- 生成端：`ManifestWriter.write()` 写入后自检，未通过契约 = 生成器 bug，直接失败
- 消费端：`--from-manifest` 构建前强制校验；旧版 manifest（无 `schema_version`）warn 跳过，不硬失败
- drift 防线：`tests/test_schema_validator.py` 的 COLA golden test——生成器改字段而 schema 未同步即测试红
- 校验器 `scripts/validator.py` 为内置子集实现，零第三方依赖

## Revision-pinned Evidence

`meta.json` 携带生成时刻的证据锚点（借鉴 archify 的钉版本语义，代码即真相故无需二次校验）：

```json
"evidence": { "repo_url": "...", "revision": "<40位SHA>",
              "generatedAt": "...", "dirty": false }
```

- 组件页/聚合页的类名渲染为**钉定版本的源码链接**（指向生成时刻 commit，代码演进不漂移）；无 `revision`/`repo_url` 时降级为纯 tooltip，不渲染链接
- `--from-manifest` 重建时会计算 `staleCommits`（文档落后当前 HEAD 的提交数）并警告
- 无 git / 非 git 目录降级为 `revision: null`，不阻断

**`project_repo` 配置格式**（`.doc-gen.json`）：

```jsonc
// 推荐：完整链接模板，{revision}/{path} 占位符 —— 各平台 URL 形态全覆盖
"project_repo": "https://codeup.aliyun.com/{orgId}/{repo}/blob/{revision}/{path}"
"project_repo": "https://gitlab.com/group/repo/-/blob/{revision}"          // 无 {path} 自动追加

// 兼容：裸仓库 URL —— 默认 GitHub/Gitea 风格 {repo}/blob/{revision}/{path}
"project_repo": "https://github.com/user/repo"
```

## 退出码与验收契约（强制）

- **退出码 0 = 成功；1 = 阶段失败（manifest 校验失败 / npm 缺失或 install/build 失败）；2 = 用法错误。非零退出码绝不可描述为成功**
- 每次运行产出 `doc-manifest/receipt.json`（`ok` 当且仅当无 `fail`；`warn` 是事实降级不阻断）。交付时必须引用 receipt 检查项，不得声称未执行的检查
- 风险扫描的 `critical` 数量必须如实转述给用户，不得省略
- npm 构建失败从静默跳过改为 `exit 1`（breaking）：依赖旧行为的脚本需显式降级

## 架构演进 diff（delta）

```bash
python3 scripts/doc_gen.py diff <base快照目录> <head快照目录> \
  --output delta.json --markdown delta.md
```

- 对比两份 `doc-manifest/` 快照，六维度 receipt：组件（含 moved 分级）/聚合/数据表/状态机/跨域依赖/API 端点
- 锚定 `base.revision → head.revision`（来自 evidence）；退出码 0 = 对比完成（不代表无变化）；schema_version 不相等 → `exit 2` 拒绝
- **站点渲染**：`--output <站点>/doc-manifest/delta.json` 后 `--build` 自动生成「🔀 架构演进」页面（统计卡 + 六维度表 + 变更明细），sidebar 带变化总数徽标
- 信噪比契约：字段分组（semantic/lifecycle/position/behavior），`description` 等 Javadoc 噪声归 `presentation-changed` 不计入 summary；包重命名经 className 恒等启发式判 `moved` 并标注 `inferred: true`（多对一时保守回退 added/removed）
- 典型场景："这次重构只动了 adapter 层、domain 层零变化"的机器验证（治理三角：arch-guard 规则 → impact-guard 预测 → delta 实证）

**CI 归档约定**（delta 的流程前置，样例见 [`ci/archive-manifests.example.yml`](ci/archive-manifests.example.yml)）：
- master push 时 `scan --manifest-only --output archive/<SHA>` 归档到独立分支 `doc-gen-archive`（不污染主分支）
- PR 门禁：merge-base 归档快照 vs PR 当前快照 → `delta.md` 贴 PR；Codeup Flow 按相同步骤翻译

## 相关文件

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 技术设计：[`DESIGN.md`](DESIGN.md)
- 可信化改造设计（schema 契约 + 退出码 + evidence，已落地）：[`../../docs/design/doc-gen-contract-design.md`](../../docs/design/doc-gen-contract-design.md)
- CLI 工具：[`scripts/doc_gen.py`](scripts/doc_gen.py)
- Schema 契约：[`schemas/`](schemas/)（7 个 JSON Schema）
- 契约校验器：[`scripts/validator.py`](scripts/validator.py)（零依赖内置子集实现）
- 演进对比引擎：[`scripts/delta.py`](scripts/delta.py) + CI 归档样例 [`ci/archive-manifests.example.yml`](ci/archive-manifests.example.yml)
- Astro 模板：[`template/`](template/)
- DDD/架构规范：[`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)（架构与分层）
