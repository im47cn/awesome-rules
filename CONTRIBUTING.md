# 贡献指南

感谢为本仓库贡献！本仓库包含三类内容，各自的贡献方式不同：

| 类型 | 目录 | 谁来维护 | 本文章节 |
| --- | --- | --- | --- |
| **规范文件** | `steering/` | 团队共识，人工评审 | [规范文件](#一规范文件steering) |
| **AI 技能** | `skills/` | 技能开发者 | [AI 技能](#二ai-技能skills) |
| **反例用例** | `skills/{skill}/badcase/` | 全员（审查中发现问题即可沉淀） | [反例用例](#三反例用例badcase) |

---

## 通用约定

### 分支与提交

遵循 [Git 提交规范](steering/git-conventions.md)，要点：

- 分支前缀：`feature/`、`hotfix/`
- Commit 格式：`<type>(<scope>): <subject>`（中文，主题行 ≤50 字符）
- 示例：`feat(ddl-guard): 新增索引命名检查规则`

### Merge Request

- MR 标题格式：`[模块] 功能描述`
- 描述变更内容、影响范围和测试方法
- 关联相关工作项和资料

---

## 一、规范文件（steering/）

`steering/` 是**团队标准的唯一真相源**，所有技能的检查规则均派生自这里。修改规范影响面大，需格外谨慎。

### 目录结构

```
steering/
├── database-design-specification.md   # 数据库设计开发规范
├── api-standards.md                   # API 设计规范
└── git-conventions.md                 # Git 提交规范
```

### 什么时候需要改

- 业务发展导致现有规则不再适用（如新增数据库类型、调整命名约定）
- 发现规范存在遗漏或矛盾，需要补充 / 澄清
- 团队达成新共识，需要新增或废弃某条规则

### 写作要求

- **规则分级**：每条规则标注【强制】或【推荐】，与现有规范风格一致
- **给出理由**：不只写"怎么做"，还要写"为什么"
- **示例对比**：用 ✅ / ❌ 展示正例与反例，降低理解成本

```
✅ 推荐
    `order_no` VARCHAR(32) NOT NULL COMMENT '订单编号'

❌ 禁止
    `orderNo` VARCHAR(32)    -- 命名用 camelCase、缺注释
```

### 贡献流程

1. **先讨论**：在工作项或群里提出修改建议，达成初步共识
2. **改文件**：修改 `steering/` 下对应的规范文件
3. **联动更新**：检查是否需要同步更新关联内容：
   - 对应技能的检查脚本（`scripts/`）能否覆盖新规则
   - 对应技能的人工规则文档（`*-manual-rules.md`）是否需补充
   - 对应技能的 `README.md` 检查项表格是否需更新
4. **提交 MR**：标题 `[规范] xxx`，描述修改原因和影响范围
5. **评审**：规范变更需至少一名 reviewer 确认

---

## 二、AI 技能（skills/）

每个技能是一个独立目录，包含技能定义、检查脚本、人工规则和测试文件。

### 目录结构

```
skills/{skill-name}/
├── SKILL.md                      # 技能定义（AI 入口，含 frontmatter）
├── README.md                     # 技能文档（人类入口，用法和检查项）
├── *-manual-rules.md             # 脚本无法覆盖、需人工核对的规则清单
├── scripts/                      # 检查脚本（Python 3 标准库，无第三方依赖）
│   └── xxx_check.py
├── steering -> ../../steering/   # 规范引用（实际通过相对路径引用）
├── test/                         # 测试文件
│   ├── *.sql / *.java / *.xml    # 正常样例
└── badcase/                      # 反例用例（见下方专章）
```

### 新建技能

1. 在 `skills/` 下新建目录，命名格式 `{领域}-guard`（如 `order-guard`）
2. 创建 `SKILL.md`（参考现有技能的 frontmatter 和结构）
3. 创建 `README.md`，包含能力说明、快速使用、检查覆盖、相关文件
4. 编写检查脚本到 `scripts/`，仅用 Python 3 标准库
5. 补充 `*-manual-rules.md`，列出脚本无法覆盖的规则
6. 在根 `README.md` 的技能表格和项目结构树中注册新技能

#### SKILL.md frontmatter 要求

```yaml
---
name: {skill-name}
description: >
  {一段话描述技能用途，并列出触发关键词。AI 根据这段描述决定何时激活。}
---
```

`description` 中的触发关键词要覆盖用户的常见说法，包括口语化表达。

### 完善现有技能

常见的贡献场景：

| 场景 | 改什么 | 注意 |
| --- | --- | --- |
| 新增自动检查规则 | `scripts/xxx_check.py` | 同步更新 `README.md` 检查项表格 |
| 新增人工检查规则 | `*-manual-rules.md` | 标注与规范文件的对应关系 |
| 修复脚本误报 / 漏报 | `scripts/xxx_check.py` | 添加对应的 badcase 防止回归 |
| 更新文档 | `README.md` / `SKILL.md` | 保持与脚本实际行为一致 |

### 脚本编写约定

- **仅用 Python 3 标准库**，不引入第三方依赖
- 退出码统一：`0`=通过，`1`=有问题，`2`=运行错误
- 支持 `--format json` 输出，便于集成到 CI
- 支持 `--help`，说明用法和检查规则
- 参考现有脚本（`ddl_check.py`、`api_check.py`）的代码结构

### 技能贡献流程

1. 在 `skills/{skill-name}/` 下进行修改
2. 用脚本跑一遍 `test/` 下的样例，确认行为符合预期
3. 提交 MR，标题 `[技能名] 功能描述`

---

## 三、反例用例（Badcase）

反例用例用于沉淀审查中发现的典型问题，帮助回归验证技能的检查能力，也让新成员快速理解"什么是不合规的"。

### 目录约定

每个技能在 `badcase/` 下维护反例，**一个子目录一个 badcase**：

```
skills/{skill-name}/badcase/
├── {序号}-{简短描述}/          # 例：001-missing-column-comment
│   ├── prompt.md              # 【必需】触发审查的提示词
│   ├── input/                 # 【必需】待审查文件（1 个或多个）
│   │   └── example.sql        #   文件类型结合具体技能
│   └── expected.md            # 【推荐】期望检出的违规项及对应规则
└── {序号}-{简短描述}/
    └── …
```

### 文件说明

| 文件 | 必需 | 作用 |
| --- | --- | --- |
| `prompt.md` | ✅ | 模拟用户发起审查时的原话提示词，应贴近真实使用场景（如"帮我审查这个建表语句"） |
| `input/` | ✅ | 待审查的源文件，内含故意埋入的违规点；文件设计需结合具体项目 |
| `expected.md` | 推荐 | 期望检出的违规清单（规则编号 + 违规描述），用于人工或自动化比对实际审查结果 |

### 命名规范

- 子目录名：`{三位序号}-{英文短描述}`，如 `001-missing-column-comment`、`002-wrong-http-method`
- 序号在当前技能内递增，不复用

### 什么时候添加 badcase

- 审查中发现脚本 **漏报** 了某个问题 → 添加 badcase，促使规则完善
- 修复了脚本的误报 / 漏报后 → 添加 badcase 防止回归
- 发现新的典型违规模式 → 添加 badcase 丰富回归集

### 各技能对 input 文件的要求

每个技能的待审查文件类型不同，具体要求见各技能 README：

| 技能 | 文件类型 | 说明 |
| --- | --- | --- |
| ddl-guard | `.sql`、`*Mapper.xml`、`*.java`（PO 类） | DDL 建表语句、MyBatis SQL、MyBatis-Plus 实体类 |
| api-guard | `*.java`（Controller） | Spring MVC Controller 类 |

如需声明更详细的素材要求（如项目结构、包名约定等），在各技能的 `README.md` 中补充。

### 贡献流程

1. 在对应技能的 `badcase/` 下新建子目录（序号取当前最大值 +1）
2. 编写 `prompt.md`（提示词）和 `input/`（待审查文件）
3. 补充 `expected.md`（期望检出的违规项）
4. 用技能实际跑一遍，确认审查结果与预期一致
5. 提交 MR，标题 `[技能名] 添加 badcase: {描述}`，在描述中说明覆盖了哪些规则

### 关于插件分发

当前所有插件平台（Claude Code、Codex、Cursor、Kimi、Grok）均通过 clone 整个 Git 仓库安装，badcase 文件会出现在用户本地。但实际影响很小：

- 插件加载时只读取 `SKILL.md` 和被引用的脚本，badcase 不会进入 AI 上下文
- 这些是小体积文本文件，磁盘开销可忽略

维持现状即可，无需特殊处理。

---

## 检查清单

提交 MR 前对照检查：

- [ ] Commit 信息符合 [Git 提交规范](steering/git-conventions.md)
- [ ] 修改了规范文件 → 已通知关联技能同步更新
- [ ] 新增 / 修改了检查脚本 → 已用 `test/` 下样例验证
- [ ] 修复了脚本的漏报 / 误报 → 已添加对应 badcase 防回归
- [ ] 新增了技能 → 已在根 README 注册
- [ ] 文档与代码实际行为一致
