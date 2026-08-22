---
title: work-report 跨仓库工作日报
scenario: 生成日报/周报/工作汇报
---

# 跨仓库工作日报 (work-report)

扫描多个 git 仓库的提交，由 AI 按业务成果语义聚合，生成工作日报 / 周报 / 汇报。

## 三种受众模板

| 模板 | 受众 | 密度 | 内容 |
|---|---|---|---|
| 自用流水 | 自己 | 全量 | 按仓库 + 日期时间线，技术细节完整 |
| **对 leader**（默认） | 直属上级 | 聚合 | 业务成果 + 影响 + 风险 + 下周计划（正文见 SKILL.md 第 4 步） |
| 对外汇报 | 跨部门 / 客户 | 业务 | 纯业务语言，屏蔽技术细节 |
| 团队汇总 | TL | 分组 | `--team` 按 author 分组（模板 D，见下） |

### 模板 B：自用流水

```markdown
# 工作日志（{起止日期}）

## {仓库1}
- {date} {hash} {subject}
```

### 模板 C：对外汇报

```markdown
# 阶段进展（{起止日期}）

- {业务里程碑 1}：{对用户/客户的价值}
```

### 模板 D：团队汇总（按成员分组）

```markdown
# 团队工作汇总（{起止日期}）

## {成员A 姓名}
### 本期成果
- {业务成果}（{repo} {hash}）
### 进行中
- {WIP 信号摘要}

## 团队整体观察
- **产出聚焦**：{谁聚焦什么域}
- **进行中分布**：{谁在做什么}

> ⚠️ 仅反映编码产出，不含 code review / 方案设计 / 线上排查 / 跨团队沟通
```

## 团队模式（TL 视角）

| 诉求 | 做法 |
|---|---|
| 团队整体产出（向上汇报） | `authors` 配团队成员 email，用模板 A |
| 每人产出（按成员分组） | `fetch-commits.sh --team --author 'alice@corp.com\|bob@corp.com'`，用模板 D |

`--team` 让每条 commit 附 author email，AI 据此按成员分组。git author 不规范时配
`[[members]]` 做 email→姓名映射（未映射用 email 原样显示）：

```toml
[[members]]
email = "alice@corp.com"
name = "张三"
```

> **方法论提醒**：git commit 只反映编码，严重低估 review / 设计 / 排查 / 沟通等非编码
> 贡献。团队汇总适合「产出盘点」，不适合个人绩效量化（Goodhart：一旦用于考核，
> commit 会变碎变多，指标失效）。

## 使用

直接对 AI 说：

- 「生成最近两周的工作日报」
- 「本周周报」
- 「生成对外汇报，最近一个月」

AI 读取 `~/.config/ar/workspaces.toml`（无则扫描 `~/sources`），抓取提交并聚合。

## 配置（可选）

零配置即可用。需要精细控制时，拷贝 [`workspaces.example.toml`](workspaces.example.toml) 到 `~/.config/ar/workspaces.toml`：

| 配置项 | 作用 |
|---|---|
| `authors` | 多身份过滤（公司 + 个人邮箱） |
| `scan_dirs` | 扫描目录（默认 `~/sources`） |
| `since` | 扫描时间范围（默认 `14`，单位天） |
| `exclude` | 排除目录/项目（glob），排除个人项目 / 第三方 clone |
| `[[repos]]` | 显式声明仓库 + 业务域，提升聚类质量 |

## 为什么不能只用脚本

脚本能罗列 commit，但「47 条 commit 压缩成 5 条业务成果」需要语义理解——判断哪些 commit 属于同一件事、用业务语言重述、跨仓库合并。这是 AI 的能力，脚本是它的数据源。

详见 [`SKILL.md`](SKILL.md)。
