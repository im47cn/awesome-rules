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
| --- | --- |
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

按模块/技能填写，推荐值（须与 `commitlint.config.js` 的 `scope-enum` 保持一致）：

| 类别 | scope |
| --- | --- |
| 业务域 | `api`、`db`、`ui`、`ci` |
| 工程 | `dependency`、`tools`、`docs`、`deps`、`release` |

新增技能时同步追加到两处。

### 破坏性变更（强制标记）

含破坏性变更的提交**必须**显式标记，这是触发 major 版本号的唯一信号：

- 在 type 后加 `!`：`feat(api)!: <subject>`（无 scope 时 `feat!: <subject>`）
- 或在 footer 写 `BREAKING CHANGE: <破坏点 + 迁移路径>`

两者二选一，**推荐同时使用**——`!` 触发版本号自动化，footer 说清影响面与迁移方式。

### footer（页脚）

footer 用于关联工单与记录元数据，每行一条：

| 关键字 | 用途 | 示例 |
| --- | --- | --- |
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

### 基础要求

- 使用中文，主题行 ≤50 字符
- 每个 commit 只做一件事（原子提交）
- 不提交未完成功能或调试代码
- 禁止无意义消息（如 "fix"、"update"）
- 破坏性变更必须标记（`!` 或 `BREAKING CHANGE:`）

### 历史重写与敏感信息

<!-- 待 apply 的「暂存核验/分支同步/推送复核」类条款视语义落本节或「同步纪律」 -->

- git filter-repo 重写历史时：文本替换规则需覆盖敏感串的变体形态（截断的 org ID、`git@` SSH 形态、`.` 与 `/` 分隔符形态），否则会漏网残留；`--path-rename` 仅锚定路径开头，重命名路径中间的目录需以完整前缀锚定
- 历史重写前先 `git bundle` 做全量备份；重写后在工作区、全部历史 blob、全部提交消息三处复扫验证零残留，并重跑全量测试（目录改名可能破坏 fixtures 路径）
- 提交前自检不得混入公司敏感信息：内网代码托管地址、公司内部包名、内部服务依赖、与根 LICENSE 矛盾的清单 license 声明；提交消息中的仓库链接同样计入
- 仓库开源或对外迁移托管前，先做全历史敏感信息扫描（含全部提交消息与文件路径）；泄漏一旦进入 git 历史，仅删除当前文件无效，必须用 git filter-repo 重写全历史

## 分支命名

| 前缀 | 用途 | 示例 |
| --- | --- | --- |
| `feature/` | 新功能 | `feature/order-export` |
| `fix/` | Bug 修复 | `fix/login-timeout` |
| `hotfix/` | 紧急生产修复 | `hotfix/sql-injection` |
| `release/` | 发布准备 | `release/v1.2.0` |

## 同步纪律

- 任何「本地 vs 远端」状态判断（领先/落后/待推送/是否需要 rebase）前先 `git fetch`：共享 main 且 CI/定时任务高频自动提交的仓库里，陈旧的本地 refs 会导致误判（实证：本地 refs 未刷新时误报「领先 3 个提交待推送」，fetch 后实为落后 11 个）
- 工作开始时先切到 `main` 并 `git pull --ff-only` 同步基线（同步对象是 `main` 而非当前 feature 分支——后者只拉自身 upstream，`main` 基线仍可能过时；无 upstream 的新分支上该命令直接失败，需同步工作分支时须显式指定其 upstream）：长期不 pull 会在下次同步时积累大体积 diff（自动提交的数据文件尤甚），且整个工作过程基于过时状态
- 分叉分支（本地与远端各有新提交）上 `--ff-only` 必然失败并保持旧状态：改走显式 `git pull --rebase`（或 fetch 后 rebase）同步，不得因失败而跳过同步带着过时基线开工

## Pull Request

### 格式要求

- 标题格式：`[模块] 功能描述`
- 描述变更内容、影响范围和测试方法
- UI 变更须附截图

### 内容与验证纪律

<!-- 待 apply 的「stacked PR/自动合并边界/强推收敛」类条款落本节 -->

- PR 描述必须如实注明验证范围：哪些检查已执行、哪些因环境限制未执行（如全量依赖安装、全量类型检查超时），并说明已采用的替代验证（如语法转译、单文件类型检查），不得暗示未执行的检查已通过。
- 给他人未合并的功能分支提修复：先 fork 原仓库，从作者分支最新 head 切出 fix 分支，并向该分支提交 stacked PR，同时在原 PR 下评论附上链接，便于作者直接采纳。
- 打补丁前先在基线分支最新 head 上复核缺陷仍然存在，并排查同文件内是否还有同类遗漏点，再动手修改。

### 历史重写与外部贡献

- 向外部开源项目提交集成、适配或修复前，先检索其 issue 与开放 PR：若已有现成方案（含未合并 PR），优先在该方案基础上验证、修 bug 或补充，不重复自研。
- force-push 重写历史前需临时禁用分支保护 ruleset（无法禁用则被拒推）；挂旧历史的机器人分支（如 dependabot）须连同其 PR 一并关闭，否则旧提交仍可通过该分支访问
- 已合并/关闭 PR 的 `refs/pull/*/head` 会永久持有旧提交，force-push 无法清除；需要彻底清除泄漏历史时，评估删库重建（重建后恢复 ruleset、以旧泄漏 SHA 返回 404 为验收标准）
