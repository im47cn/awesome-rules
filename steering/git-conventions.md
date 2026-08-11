---
title: Git 提交规范
scenario: 提交代码/创建分支/PR
inclusion: always
---

# Git 提交规范

## Commit 格式（强制）

```
<type>[(<scope>)][!]: <subject>

<body>

<footer>
```

### type（必选）

| 类型 | 说明 |
|---|---|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更 |
| style | 代码格式（无逻辑变更） |
| refactor | 重构（无功能变更） |
| perf | 性能优化 |
| test | 测试相关 |
| chore | 构建、依赖、配置 |
| revert | 回退之前的提交 |

### scope（可选）

按模块填写，如 `api`、`db`、`ui`、`ci`、`<xx业务域>`。

### 破坏性变更（强制标记）

含破坏性变更的提交**必须**显式标记，这是触发 major 版本号的唯一信号：

- 在 type 后加 `!`：`feat(api)!: <subject>`（无 scope 时 `feat!: <subject>`）
- 或在 footer 写 `BREAKING CHANGE: <破坏点 + 迁移路径>`

两者二选一，**推荐同时使用**——`!` 触发版本号自动化，footer 说清影响面与迁移方式。

### footer（页脚）

footer 用于关联工单与记录元数据，每行一条：

| 关键字 | 用途 | 示例 |
|---|---|---|
| `Closes #N` | 关闭 issue | `Closes #456` |
| `Fixes #N` | 修复 issue（同 Closes） | `Fixes #789` |
| `Refs #N` | 关联但不关闭 | `Refs #101` |
| `BREAKING CHANGE:` | 破坏性变更说明 | `BREAKING CHANGE: 移除 /v1/login，改用 /v2/auth` |

### 示例

```
feat(db): 添加规则状态历史记录表
fix(ui): 修复差异数据表格分页错乱
docs: 更新数据库设计规范文档
```

带破坏性变更与 footer 的完整示例：

```
feat(api)!: 重构登录接口返回结构

- accessToken 拆分为 accessToken + refreshToken
- 移除 userName 字段，改用 userProfile 对象

BREAKING CHANGE: /v1/login 返回结构变更，前端需同步改造
Closes #456
```

原子提交示例（关联但不关闭）：

```
fix(db): 修复分页查询越界

Refs #321
```

## 提交要求

- 使用中文，主题行 ≤50 字符
- 每个 commit 只做一件事（原子提交）
- 不提交未完成功能或调试代码
- 禁止无意义消息（如 "fix"、"update"）
- 破坏性变更必须标记（`!` 或 `BREAKING CHANGE:`）

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
