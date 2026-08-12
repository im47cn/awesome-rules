# DDD 技术文档生成：doc-gen

## 1. 背景

DDD 项目的架构文档几乎是个死结——手写架构图跟不上代码迭代，新人入职靠口口相传，架构评审对着过期的 Visio 图空谈。代码是唯一真相，但没人愿意读几千个类来理解架构。

doc-gen 把"读代码"这件事交给机器：扫描 Java DDD 项目，自动生成交互式静态文档站点——架构图可点击钻取、API 可在线试调、ER 图与聚合结构一目了然，还内嵌一个懂你项目的 AI 架构助手。

## 2. 目标

- 从 Java DDD 项目源码自动生成技术文档站点，文档与代码同源、永不过期
- 覆盖架构全景、分层依赖、领域聚合、数据库 ER、REST API、状态机全维度
- 零配置启动，纯静态产物，GitHub Pages / 内网静态托管零成本

## 3. 它能生成什么

| 维度 | 产物 | 说明 |
|---|---|---|
| 项目全景架构图 | Mermaid `graph TD` | 域 → 层 → 组件，节点可点击导航 |
| 分层依赖图 | `flowchart` | Adapter→Application→Domain←Infra，违规跨层边标红 |
| 领域聚合图 | `classDiagram` | 聚合根 / 内部实体 / 值对象关系 |
| 数据库 ER 图 | `erDiagram` | 从 DDL 或 PO `@TableName` 推断，含外键关系 |
| REST API 文档 | OpenAPI 3.0 + Scalar | 交互式 Try-It，从 Controller 端点提取 |
| 状态机图 | `stateDiagram-v2` | Spring/Cola/裸 enum，含死状态/不可达审查 |
| ADR 架构决策 | `docs/adr/*.md` | 自动收录团队的架构决策记录 |
| 多项目聚合 | 公司级全景站 | 多个 Maven 项目合并到一个站点 |
| AI 架构助手 | 页面内嵌 RAG | 自然语言问答，免 API Key 本地运行 |
| 全文搜索 | Pagefind | 构建后索引，支持中文检索 |

## 4. 特点

- **同源**：文档从代码扫描生成，代码即真相，告别过期架构图
- **零配置**：`--init` 从 pom.xml 自动推断 groupId / 域名
- **7 层扫描**：Maven 模块 → Java 类 → 注解 → 方法 → 字段 → DDL → 依赖
- **交互式**：Mermaid 节点可点击钻取，API 可在线试调
- **纯静态**：构建产物为静态文件，任意静态托管零成本部署
- **协同**：与 arch-guard 共享扫描引擎（Maven/Java/分层识别），审查与文档同源
- **质量**：产品代码测试覆盖率 94%，pytest 90% 门禁守护

## 5. 风险提示

Java 源码解析基于正则表达式（无 AST），泛型嵌套超 2 层、Lambda、文本块等场景可能提取不完整；生成内容建议在关键类上人工核对。本工具旨在降低文档维护成本，不能完全替代架构评审与技术方案编写。

## 6. 安装方法

见《【Skills Hub】awesome-rules 做懂技术集团的 AI 搭子》。

---

## 7. 接入案例

### 案例 1：新项目生成文档站点（3 步）

**第 1 步**：初始化配置（从 pom.xml 自动推断）

```bash
python3 skills/doc-gen/scripts/doc_gen.py /path/to/java-project --init
```

生成 `.doc-gen.json`，自动推断 groupId、域名映射。

**第 2 步**：生成 manifest + 构建静态站点

```bash
python3 skills/doc-gen/scripts/doc_gen.py /path/to/java-project --build --output docs-site/
```

扫描 Maven 模块、Java 源码、DDL、状态机，生成 DocManifest 分片，构建 Astro 静态站点。

**第 3 步**：本地预览

```bash
cd docs-site/ && npm run dev      # http://localhost:4321
```

打开站点即可看到：可点击的全景架构图、分层依赖图（违规边标红）、聚合类图、ER 图、Scalar API 文档、状态机图，右下角内嵌 AI 架构助手。

### 案例 2：多项目聚合到公司架构全景

当团队有多个 DDD 项目，可聚合到一个"公司架构鹰眼"站点：

```bash
python3 skills/doc-gen/scripts/doc_gen.py aggregate projects.json --output hawkeye-site/ --build
```

`projects.json` 声明各项目 manifest 路径，聚合后生成公司级全景拓扑图 + 跨项目依赖矩阵 + 合并的 ER 图与 API 规范。

### 案例 3：CI 集成（仅生成数据清单）

只需数据清单（不构建站点），供下游消费：

```bash
python3 skills/doc-gen/scripts/doc_gen.py /path/to/java-project --manifest-only --output manifest/
```

输出 `doc-manifest/` 分片目录（index/domains/database/diagrams/...），可被其他工具或自定义前端消费。

> 众人拾柴火焰高——欢迎大家贡献更多项目的接入案例与模板调优。
