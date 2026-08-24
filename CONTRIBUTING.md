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

### 测试门禁（推送前必过）

hook 由 [lefthook](https://github.com/evilmartians/lefthook) 托管（`lefthook.yml`
入库共享）。克隆后一次性激活：

```bash
npm i -g lefthook && lefthook install   # 或 npm run setup:hooks
```

- **commit-msg**：commitlint 校验提交信息格式（`steering/git-conventions.md`）
- **pre-push**：全量测试 + badcase 回归 + 安装入口 blob 锁定校验，
  任一失败即阻断推送（跳过：`git push --no-verify`）
- 未装 lefthook 时 hook shim 打印警告并放行，不阻塞提交

手动执行 pre-push 同一路径：

```bash
npm test                   # bash scripts/run_tests.sh
```

- Python 基线为 **3.9**（macOS 系统 Python 即此版本），脚本不得使用 3.10+
  的运行时语法（`X | Y` 类型注解须配 `from __future__ import annotations`）
- 新增测试套件时，在 `scripts/run_tests.sh` 的 `SUITES` 中登记
- 个别测试套件配置了覆盖率门禁（如 `skills/arch-guard/scripts/pytest.ini` 的
  `--cov-fail-under`），运行前需安装测试依赖：`pip3 install pytest pytest-cov`，
  否则 pytest 会以 `unrecognized arguments: --cov` 拒绝启动

### Merge Request

- MR 标题格式：`[模块] 功能描述`
- 描述变更内容、影响范围和测试方法
- 关联相关工作项和资料

---

## 一、规范文件（steering/）

`steering/` 是**团队标准的唯一真相源**，所有技能的检查规则均派生自这里。修改规范影响面大，需格外谨慎。

### 目录结构

规范分两组，分组决定索引归属（见下文 [frontmatter 机制](#规范文件-frontmatter必需)）：

```
steering/
├── testing-standards.md              # 通用：测试规范
├── openapi-standards.md                  # 通用：Open API 设计规范
├── database-design-specification.md  # 通用：数据库设计规范
├── git-conventions.md                # 通用：Git 提交规范
└── gtsp/                             # GTSP 工程规范（Java/Spring Cloud，按维度拆分，含 DDD 架构）
    ├── README.md                     #   总入口
    └── 01-project-structure.md … 09-cr-checklist.md   #   各维度
```

- **通用设计规范**：`steering/` 直接子文件，覆盖 API/数据库/测试/Git 等设计阶段
- **GTSP 工程规范**：`steering/gtsp/` 子目录，覆盖 `gtsp-*`/`fss-*` 微服务的编码阶段

### 什么时候需要改

- 业务发展导致现有规则不再适用（如新增数据库类型、调整命名约定）
- 发现规范存在遗漏或矛盾，需要补充 / 澄清
- 团队达成新共识，需要新增或废弃某条规则

### 写作要求

- **规则分级**：通用设计规范在条款中标注【强制】/【推荐】；GTSP 维度文件（01-08）不逐条分级，合并门禁项集中在 `steering/gtsp/09-cr-checklist.md`。正反例用 ✅/❌ 展示
- **给出理由**：不只写"怎么做"，还要写"为什么"
- **示例对比**：用 ✅ / ❌ 展示正例与反例，降低理解成本

```
✅ 推荐
    `order_no` VARCHAR(32) NOT NULL COMMENT '订单编号'

❌ 禁止
    `orderNo` VARCHAR(32)    -- 命名用 camelCase、缺注释
```

### 规范文件 frontmatter（必需）

每个规范 `.md` 必须在头部带 frontmatter，声明 `title` 和 `scenario`：

```yaml
---
title: 规范显示名
scenario: 适用场景（何时该读它）
---
```

随后是正文（`# 标题` + 内容）。

`hooks/load-steering.sh`（SessionStart hook）会**动态扫描** `steering/` 目录、读取每个文件的 frontmatter，自动生成规范索引注入 AI 上下文。新增规范文件只需带 frontmatter，**无需改脚本或 `CLAUDE.md`**。

约定：

- **分组靠目录**：`steering/*.md`（直接子文件）归入「通用设计规范」；`steering/{组}/*.md`（子目录，如 `gtsp/`）归入该组；子目录下的 `README.md` 自动识别为该组总入口
- **排序靠文件名**：用 `00-`/`01-` 数字前缀控制顺序
- frontmatter 字段：
  - `title` — 索引表显示名（缺失时回退到 H1 标题）
  - `scenario` — 适用场景，AI 据此判断何时加载（缺失时显示 `—`，强烈建议填写）
  - `inclusion: always` — 部分历史文件保留的既有字段，新增文件无需写

> 本地验证：`CLAUDE_PLUGIN_ROOT=$(pwd) bash hooks/load-steering.sh` 可查看生成的索引，确认新文件已出现。

### 贡献流程

1. **先讨论**：在工作项或群里提出修改建议，达成初步共识
2. **改文件**：修改 `steering/` 下对应的规范文件；**新增文件须带 frontmatter**（见上节）
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
├── badcase/                      # 反例用例（见下方专章）
│   └── {NN-xxx}/
│       ├── input/               #   共享待审查文件
│       ├── expected.md          #   期望结果（只写一次）
│       └── prompts.md           #   提示词集 + 已知问题
└── test/                         # 测试文件（正常样例）
```

### 新建技能

1. 在 `skills/` 下新建目录。审查类技能命名格式 `{领域}-guard`（如 `order-guard`），工具类技能可使用描述性名称（如 `doc-gen`）
2. 创建 `SKILL.md`（参考现有技能的 frontmatter 和结构）
3. 创建 `README.md`，包含能力说明、快速使用、检查覆盖、相关文件
4. 编写检查脚本到 `scripts/`，仅用 Python 3 标准库（测试文件可使用 pytest）
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

- **检查脚本仅用 Python 3 标准库**，不引入第三方依赖（测试文件可使用 pytest 等测试框架）
- 退出码统一：`0`=通过，`1`=有问题，`2`=运行错误
- 支持 `--format json` 输出，便于集成到 CI（审查类技能必须；工具类技能可选）
- 支持 `--help`，说明用法和检查规则
- 审查类脚本参考 `ddl_check.py`、`api_check.py`；工具类脚本参考 `doc_gen.py`

### 技能贡献流程

1. 在 `skills/{skill-name}/` 下进行修改
2. 用脚本跑一遍 `test/` 下的样例，确认行为符合预期
3. 提交 MR，标题 `[技能名] 功能描述`

---

## 三、反例用例（Badcase）

反例用例用于沉淀审查中发现的典型问题，帮助回归验证技能的检查能力，也让新成员快速理解"什么是不合规的"。

### 目录约定

每个技能在 `badcase/` 下维护反例，**一个子目录一个 badcase**。一个 badcase 共享一份 `input/`，期望结果只写一次（`expected.md`），提示词集中在 `prompts.md` 中维护：

```
skills/{skill-name}/badcase/
├── {序号}-{简短描述}/              # 例：001-missing-column-comment
│   ├── input/                     # 【必需】待审查文件
│   │   └── example.sql
│   ├── expected.md                # 【必需】期望结果（check 脚本 + 规则列表）
│   └── prompts.md                 # 【推荐】提示词集 + 已知问题
└── {序号}-{简短描述}/
    └── …
```

### expected.md 格式

期望结果只写一次，所有提示词共享。统一使用**双通道格式**——`## 预期检查输出` 小节内：
「脚本自动检出」参与 runner 比对，「人工补充」仅记录不比对（把人工审查项计入失败会让 runner 永远红着）：

```markdown
# badcase 标题（可选）

check: ddl_check.py

## 预期检查输出

- 脚本自动检出：禁用类型、表注释缺失、字段注释缺失
- 人工补充：命名语义（拼音、泛化词）需人工核对 ddl-manual-rules.md
```

- `check:` — 指定运行的检查脚本文件名（如 `ddl_check.py`）；不填则自动运行该技能的全部 `*_check.py`
- `脚本自动检出：` — 期望检出的规则名称，顿号分隔；与脚本 JSON 输出中的 `rule` 字段子串匹配，无需逐字一致
- `人工补充：` — 脚本无法覆盖的负向断言/语义判断，runner 不比对，仅提示人工核对
- 列出的自动检出规则 **全部被检出才算通过**；实际多检出不算失败

> 快速获取规则名称：对 `input/` 运行 `python3 scripts/xxx_check.py input/ --format json`，查看输出的 `rule` 字段。

### prompts.md 格式

提示词集中在一个文件中，每条一行。`## 已知问题` 下记录不可自动验证的问题（如提示词无法激活 skill），不影响通过/失败判定：

```markdown
# 提示词集

- 帮我审查这个建表语句。
- 审查一下这个 DDL。
- 这个表设计有没有什么问题？

## 已知问题

- 提示词"这个表设计有没有什么问题？"缺少触发关键词，skill 可能不会被激活。建议在 description 中补充口语化表达。
```

### 回归测试工具

发版前运行回归测试，一键验证所有 badcase 是否通过：

```bash
# 运行全部 badcase
python3 scripts/badcase_runner.py

# 只运行指定技能
python3 scripts/badcase_runner.py --skill ddl-guard

# 显示实际检出详情
python3 scripts/badcase_runner.py --verbose
```

退出码 `0` = 全部通过，`1` = 存在失败，可直接集成到 CI。

### 命名规范

- badcase 子目录名：`{三位序号}-{英文短描述}`，如 `001-missing-column-comment`
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
2. 在 `input/` 放入待审查文件
3. 对 `input/` 运行检查脚本，记录实际检出的规则名称
4. 编写 `expected.md`（用 `check:` 指定脚本，`- xxx` 列出期望规则）
5. 编写 `prompts.md`（列出提示词，有已知问题则补充 `## 已知问题`）
6. 运行 `python3 scripts/badcase_runner.py --skill {技能名}` 确认通过
7. 提交 MR，标题 `[技能名] 添加 badcase: {描述}`

### 关于插件分发

当前所有插件平台（Claude Code、Codex、Cursor、Kimi、Grok）均通过 clone 整个 Git 仓库安装，badcase 文件会出现在用户本地。但实际影响很小：

- 插件加载时只读取 `SKILL.md` 和被引用的脚本，badcase 不会进入 AI 上下文
- 这些是小体积文本文件，磁盘开销可忽略

维持现状即可，无需特殊处理。

#### 版本发布纪律（消费者更新门控）

插件安装是**版本号门控的快照**：`claude plugins update` 比较源仓 `plugin.json`
的版本号，未 bump 则报 "already at the latest version" 拒绝刷新（实测：0.3.0
快照滞后源仓 2 天 20+ 提交，update 不动）。因此合并影响分发内容的 PR
（skills / steering / hooks）后：

- 运行 `npm run release`（首次前 `npm install` 安装 devDependencies）。版本工具
  `commit-and-tag-version` **锁定为 devDependency 精确版本**（13.1.2，npm script
  经 `npx --no-install` 只用本地安装，不回落全局）——v0.4.0 发布实证：全局
  homebrew 版对 `feat` 提交不升 minor（44 个 feat 推导出 patch）。已知问题：
  该版本 recommended-bump 对 feat 不升 minor，需 `--release-as` 显式定级；
  升级新版本时先验证再移除此说明
- 各平台清单版本对齐由门禁 `tools/check_plugin_versions.py` 拦截（gauntlet
  `plugin-versions` 层）：以 `package.json` 为单源锚，六处插件清单漂移即红；
  新平台接入须登记到检查器的 `PLUGIN_MANIFESTS`（或 `EXCLUDED_MANIFESTS`
  并注明语义不同的理由），未登记的清单文件属硬失败
- 对齐清单后运行 `python3 scripts/plugin_lock.py --update`，并提交生成的 `scripts/plugin-lock.json` 更新
- 消费者侧更新：源仓 `git pull` 后执行
  `claude plugins update awesome-rules@awesome-rules`（市场限定名）

---

## 四、本地调试

开发技能或规范后，需要在本地安装插件以验证实际效果。各工具的安装方式如下。

### Claude Code

从本地路径注册 marketplace 并安装插件：

```bash
# 在 awesome-rules 仓库根目录执行
claude plugins marketplace add ./
claude plugins install awesome-rules
```

安装时按 `plugin.json` 版本号快照到
`~/.claude/plugins/cache/awesome-rules/awesome-rules/<版本>/`，会话从快照加载——
修改源仓文件**不会**实时生效，新增技能不 bump 版本则消费者不可见（实测：源仓
新增技能未出现在已装会话）。修改 `SKILL.md`、脚本或 hooks 后，按
「版本发布纪律」bump 版本，再执行下方更新命令。

```bash
# 查看已安装插件
claude plugins list

# 更新插件（拉取最新代码后）
claude plugins update awesome-rules@awesome-rules

# 卸载
claude plugins uninstall awesome-rules
```

### Codex

```bash
codex plugins install .
```

### Cursor / Kimi / Grok

这三个工具通过 marketplace.json 安装。本地调试时，将插件目录链接或复制到工具的插件目录下即可。具体路径参考各工具的插件管理文档。

---

## 检查清单

提交 MR 前对照检查：

- [ ] Commit 信息符合 [Git 提交规范](steering/git-conventions.md)
- [ ] 修改了规范文件 → 已通知关联技能同步更新
- [ ] 新增规范文件 → 头部已带 frontmatter（`title` + `scenario`），运行 `bash hooks/load-steering.sh` 确认已入索引
- [ ] 新增 / 修改了检查脚本 → 已用 `test/` 下样例验证
- [ ] 修复了脚本的漏报 / 误报 → 已添加对应 badcase 防回归
- [ ] 新增 / 修改了 badcase → 已运行 `python3 scripts/badcase_runner.py` 验证通过
- [ ] 新增了技能 → 已在根 README 注册
- [ ] 文档与代码实际行为一致
