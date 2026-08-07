---
title: Git 提交规范
scenario: 提交代码/创建分支/PR
inclusion: always
---

# Git 提交规范

## Commit 格式（强制）

```
<type>(<scope>): <subject>

<body>
```

### type（必选）

| 类型 | 说明 |
|---|---|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更 |
| style | 代码格式（无逻辑变更） |
| refactor | 重构（无功能变更） |
| test | 测试相关 |
| chore | 构建、依赖、配置 |

### scope（可选）

按模块填写，如 `api`、`db`、`ui`、`ci`。

### 示例

```
feat(db): 添加规则状态历史记录表

fix(ui): 修复差异数据表格分页错乱

docs: 更新数据库设计规范文档
```

## 提交要求

- 使用中文，主题行 ≤50 字符
- 每个 commit 只做一件事（原子提交）
- 不提交未完成功能或调试代码
- 禁止无意义消息（如 "fix"、"update"）

## 分支命名

| 前缀 | 用途 | 示例 |
|---|---|---|
| `feature/` | 新功能 | `feature/order-export` |
| `fix/` | Bug 修复 | `fix/login-timeout` |
| `hotfix/` | 紧急生产修复 | `hotfix/sql-injection` |
| `release/` | 发布准备 | `release/v1.2.0` |

## Pull Request

- 标题格式：`[模块] 功能描述`
- 描述变更内容、影响范围和测试方法
- UI 变更须附截图
