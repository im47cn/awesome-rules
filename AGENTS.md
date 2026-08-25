# Awesome Rules — 项目规范与技能

本仓库提供一组可复用的研发规范（steering）和 AI Agent 技能（skills）。
在编写或审查代码时，**主动读取并遵守**以下规范文件。

规范分两组，体系独立，按当前任务所属体系选择对应规范，勿混用：

- **通用设计规范**（设计阶段）：`steering/*.md` —— API 设计、数据库设计、测试、Git 提交、审查报告输出、跨仓契约兼容性
- **GTSP 工程规范**（编码阶段，Java/Spring Cloud）：`steering/gtsp/*.md`，总入口 `steering/gtsp/README.md` —— 覆盖 `gtsp-*`/`fss-*` 微服务的项目结构、分层架构、命名、Feign、MyBatis、日志、异常、配置等

> 完整规范索引由 SessionStart hook（`hooks/load-steering.sh`）动态扫描各文件 frontmatter 生成并注入上下文。新增规范只需带 frontmatter（`title` + `scenario`），无需手动维护本文件。

## 审查技能（触发式）

- `/ddl-guard` — DDL/SQL 自动审查（脚本 + 人工判断）
- `/api-guard` — 业务接口自动审查（脚本 + 人工判断）
- `/arch-guard` — DDD 架构分层守护（脚本 + 人工判断）
- `/impact-guard` — 变更影响分析（改码前预估 + PR/CI 门禁，🔴直接/🟠间接分级）
- `doc-gen` — DDD 单项目文档站生成；多项目聚合归 `arch-hawkeye/`（全局观测与治理独立工程，契约见 `arch-hawkeye/AH-MANIFEST.md`）

## 使用原则

- 在相关任务出现时，先读取对应的 steering 规范，再开始工作
- 遵守各项规范；标注【强制】的条款不可违反（不通过则不予合并），【推荐】尽可能遵守
- 审查类技能会运行自动化脚本，不要跳过脚本检查步骤

## 交付前审查（强制）

产生代码/脚本/文档变更的任务，宣布完成前必须：

1. 派发一次独立审查子代理（omp 会话：task 工具 `agent: "reviewer"`）
   审查本任务全部 diff
2. 审查发现的可操作问题：修复后复审；确不处理的，列为交付说明中的
   显式遗留项
3. 收尾思考或总结中承认的未处理边界、假设、风险，同样按第 2 条处置——
   不允许只在思考里提及后交付

纯问答/咨询类任务豁免。
