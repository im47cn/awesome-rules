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
| 多项目聚合            | 多个 Maven 项目合并到一个站点                             | ✅   |
| CI 集成               | GitHub Actions 自动构建部署                               | 📋   |

> ✅ = 已实现 🚧 = 模板就绪，CLI 集成中 📋 = 计划中

## 生成的站点页面结构

```
/                              首页 — 项目全景架构大图
/architecture/                 架构总览 — 分层依赖图 + 图例
/domains/{domain}/             域概览 — 域内分层图 + 聚合列表
/domains/{domain}/adapter/     接口层 — Controller 表格 + 端点详情
/domains/{domain}/application/ 应用层 — Executor 列表 + 用例说明
/domains/{domain}/domain/      领域层 — 聚合详情 + 实体/VO/事件
/domains/{domain}/infrastructure/ 基础设施层 — 仓储实现 + 网关
/database/                     数据库 — ER 图 + 逐表结构说明
/state-machines/               状态机 — stateDiagram 转换图 + 死状态/不可达审查
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

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 技术设计：[`DESIGN.md`](DESIGN.md)
- CLI 工具：[`scripts/doc_gen.py`](scripts/doc_gen.py)
- Astro 模板：[`template/`](template/)
- DDD/架构规范：[`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)（架构与分层）
