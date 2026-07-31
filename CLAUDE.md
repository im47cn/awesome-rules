# Awesome Rules — 项目规范与技能

本仓库提供一组可复用的研发规范（steering）和 AI Agent 技能（skills）。
在编写或审查代码时，**主动读取并遵守**以下规范文件：

## 规范文件（按需加载）

| 规范 | 路径 | 适用场景 |
|---|---|---|
| 测试规范 | `steering/testing-standards.md` | 编写/审查测试代码 |
| API 设计规范 | `steering/api-standards.md` | 设计/审查 API |
| 数据库规范 | `steering/database-design-specification.md` | 设计表结构/编写 SQL |
| Git 提交规范 | `steering/git-conventions.md` | 提交代码/创建分支/PR |
| DDD 架构规范 | `steering/ddd-architecture.md` | 架构设计/分层/领域建模 |

## 审查技能（触发式）

- `/ddl-guard` — DDL/SQL 自动审查（脚本 + 人工判断）
- `/api-guard` — API 接口自动审查（脚本 + 人工判断）
- `/arch-guard` — DDD 架构分层守护（脚本 + 人工判断）

## 使用原则

- 在相关任务出现时，先读取对应的 steering 规范，再开始工作
- 规范中有【强制】标记的条款不可违反
- 审查类技能会运行自动化脚本，不要跳过脚本检查步骤
