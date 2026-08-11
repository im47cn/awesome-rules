# doc-gen — DDD 技术文档自动生成

将 Java DDD 项目自动转换为带 AI 助手的交互式静态文档站点。

## 核心特性

- **零配置启动**：`--init` 自动从 pom.xml 推断配置
- **7 层扫描**：Maven 模块 → Java 类 → 注解 → 方法 → 字段 → DDL → 依赖
- **交互式架构图**：Mermaid 渲染，节点可点击导航到详情页
- **AI 架构助手**：页面内嵌 RAG 检索 + 自然语言问答
- **纯静态产物**：构建输出为静态文件，GitHub Pages / Vercel 零成本部署

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

## 文档

- [技能定义](SKILL.md) — 完整使用文档
- [技术设计](DESIGN.md) — 架构设计与数据流
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
