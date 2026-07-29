# Awesome Rules

研发规范与 AI Agent 技能库，用于统一团队的设计标准并自动化审查流程。

## 项目结构

```
awesome-rules/
├── steering/                          # 规范文件（团队标准，唯一真相源）
│   ├── database-design-specification.md   # 数据库设计开发规范（MySQL）
│   └── api-standards.md                  # API 设计规范（RESTful）
├── skills/                            # AI Agent 技能
│   └── ddl-review/                    # DDL 设计与审查
└── README.md
```

## 规范文件（steering/）

| 规范 | 说明 |
|---|---|
| [数据库设计开发规范](steering/database-design-specification.md) | MySQL DDL/DML 设计标准，覆盖表、字段、索引、注释、SQL 语句等，规则按【强制】【推荐】分级 |
| [API 设计规范](steering/api-standards.md) | RESTful API 约定，包括 URL 结构、HTTP 方法、响应格式、错误码、分页 |

规范文件由人工维护，是所有审查和设计的唯一依据。

## 技能（skills/）

| 技能 | 说明 |
|---|---|
| [ddl-review](skills/ddl-review/README.md) | MySQL DDL 设计与规范审查 |

各技能的详细文档、用法和检查规则见各自目录下的 README。

## 协作流程

```
开发人员编写 DDL
       │
       ▼
运行 ddl_check.py 自检 ──── 通过 ──→ 提交审核
       │
     未通过
       │
       ▼
按报告修复 ──→ 重新自检
```
