# awesome-rules：做懂技术集团的 AI 搭子

> 公司有数据库规范、API 规范、架构规范——但规范停留在文档里，落地靠人肉审核。
> awesome-rules 把规范封装成 AI 技能，让你在 Cursor / Claude Code 里说一句"审查 DDL"，
> AI 就自动对标公司标准，秒级出报告。

## 1. 它解决什么问题

| 没有它 | 有了它 |
|---|---|
| DBA 人工逐条审核 DDL，往返 3–5 轮 | 脚本 1 秒扫出全部强制问题，提交前自检 |
| API 规范靠口头传达，新人不清楚 | 对话中说"审查 API"即触发，自动对标开放平台规范 |
| 架构腐化只能靠 Code Review 人肉发现 | CI 门禁增量零容忍，基线机制自然收敛到零 |
| 规范文档更新了，没人知道 | 规范是唯一真相源，技能自动同步派生 |

## 2. 核心理念

三层结构，一个飞轮：

```
┌─────────────────────────────────────────────────────────┐
│  steering/（人工维护的规范，唯一真相源）                   │
│  数据库规范 · API 规范 · 架构规范 · Git 规范               │
└──────────────────────┬──────────────────────────────────┘
                       │ 派生（规范变更 → 技能自动跟进）
                       ▼
┌─────────────────────────────────────────────────────────┐
│  skills/（自动化的 AI 技能）                               │
│  ┌─────────────┐   脚本粗筛：秒级扫描，不传代码，省 token   │
│  │  check.py   │   AI 精审：读规则文档，补人工判断          │
│  └─────────────┘   两层结合：快且准，兼顾效率与深度        │
└──────────────────────┬──────────────────────────────────┘
                       │ 用户安装插件
                       ▼
┌─────────────────────────────────────────────────────────┐
│  AI 工具入口（Cursor · Claude Code · Codex · Kimi …）     │
│  对话中说一句"审查 DDL" → 秒级出报告                       │
└──────────────────────┬──────────────────────────────────┘
                       │ 发现漏报 / 误报
                       ▼
┌─────────────────────────────────────────────────────────┐
│  badcase/（反例用例 = 回归测试）                           │
│  贡献一条问题 → 跑回归脚本 → 提 MR → 技能变准              │
└──────────────────────┬──────────────────────────────────┘
                       │ 回流
                       ▼
                   回到 skills/
```

**一句话：规范归人，执行归机器，进化归众人。**

- **规范归人**：人只维护 `steering/` 下的规范文档，它是一切检查的唯一依据
- **执行归机器**：脚本做粗筛（快、省 token、不泄露代码），AI 做精审（读规则、补判断），分工互补
- **进化归众人**：每个人用完顺手反馈一条 badcase，就是一条回归测试——用得越多，技能越准，飞轮转得越快

## 3. 能力一览

| 技能 | 干什么 | 一句话触发 |
|---|---|---|
| `ddl-guard` | 数据库设计与审查（DDL + MyBatis SQL + PO 类） | "审查这个建表语句" |
| `api-guard` | API 设计与审查（Java Controller） | "审查这个 Controller" |
| `arch-guard` | DDD 架构分层守护（依赖方向 + 领域层纯净度） | "检查架构分层" |
| `doc-gen` | DDD 技术文档生成（架构图/API/ER/聚合/业务全景 + AI 助手） | "生成项目文档" |
| `impact-guard` | 变更影响分析（直接/间接 + 5 通道分级） | "改这个会影响谁" |

另有独立工程 **架构鹰眼**（`arch-hawkeye/`，已全量落地）：消费各项目 doc-gen 产出的 manifest，做**全局**架构观测与治理——多项目联邦聚合、跨项目真实链路（HTTP/Feign 签名对齐 + MQ/DB/缓存共享证据 + 定时任务资产，confirmed/inferred 双置信度）、变更影响分析（🔴直接/🟠间接）、治理闭环（基线 → 趋势 → git blame 归属 → 债务登记 → 超期告警 → 增量零容忍门禁）。doc-gen 管"一个人看懂一个项目"，架构鹰眼管"一群人看清所有项目"并让违规有归宿、有期限、有闭环。

三个 `*-guard` 技能遵循同一个工作流：**脚本自动检查（粗筛）→ AI 补充人工判断（精审）→ 输出完整报告**；`doc-gen` 则是生成类：**源码扫描 → DocManifest → 交互式静态站点**。

## 4. 典型场景

| 场景 | 用什么 |
|---|---|
| 新项目立项，从零设计表结构 | `ddl-guard` 设计新表 → 脚本自检 |
| 接手存量项目，排查技术债 | `arch-guard` 生成基线 → 增量零容忍 |
| 提交 MR 前自检 | 对应技能的 `*_check.py` 脚本 |
| 开放平台 API 资产盘点 | `api-guard` 批量审查 Controller |
| 新人入职 / 架构评审，需要项目全景文档 | `doc-gen` 生成静态站点 |
| 发现规范有遗漏或矛盾 | 在 `steering/` 修改规范，技能自动跟进 |

## 5. 安装方法

> 众人拾柴火焰高——不同工具配置方式不同，大家可以自行维护，方便后人。
> 以下配置方式未完全测试，如有疏漏尽情指出。

项目地址：https://github.com/im47cn/awesome-rules

### Claude Code

```bash
claude plugin marketplace add git@github.com:im47cn/awesome-rules.git
claude plugin install awesome-rules@awesome-rules
```

验证：`/status` 查看已加载插件。触发：对话中提到"审查 DDL""建表"等关键词，或 `@awesome-rules:ddl-guard`。

> 易错点：安装命令格式是 `插件名@市场名`，两者都是 `awesome-rules`。

### Codex CLI

```bash
codex plugin marketplace add git@github.com:im47cn/awesome-rules.git
codex plugin install awesome-rules@awesome-rules
```

或交互界面：`codex /plugins` → 浏览市场 → 安装。

> 易错点：Codex 的插件清单在 `.codex-plugin/`，市场清单在 `.agents/plugins/`，两者目录不同。

### Cursor

```bash
cursor plugin marketplace add git@github.com:im47cn/awesome-rules.git
```

或在 **Customize → Rules → Add Rule → Remote Rule** 中粘贴仓库 URL。

> 易错点：Cursor 的 `.cursor/rules/` 中只识别 `.mdc` 文件；插件内的 `.cursor-plugin/` 格式不受此限制。

### Kimi / Grok

```bash
kimi plugin marketplace add git@github.com:im47cn/awesome-rules.git
grok plugin marketplace add git@github.com:im47cn/awesome-rules.git
```

### OpenCode

OpenCode 自动读取 `.opencode/opencode.json` 中声明的指令文件和 `AGENTS.md`。将仓库 clone 到任意位置后，在该目录运行 `opencode` 即可。

### Pi

Pi 通过 `.pi/extensions/` 下的 TS 扩展注册 skills 路径。无需手动安装，检出仓库后 Pi 自动发现。

## 6. 风险提示

本工具旨在**减少审查交互次数、提前规避常见问题**，不能完全替代技术方案评审 / DBA 审核环节。

## 7. 共创飞轮

项目能持续变准，靠的不是一个人写规则，而是**每个人用完后顺手反馈一个问题**——这就是飞轮：

```
    用技能审查 ──────────→ 发现漏报 / 误报
         ▲                        │
         │                        ▼
    技能变得更准 ◄──── MR 合入 ◄── 贡献 badcase（一条反例 + 一行期望结果）
```

**飞轮每转一圈，工具变好一分：**

- 你发现的每一个漏报，都会变成一条 **badcase 反例**——它就是回归测试，以后技能每次更新都要跑一遍，防止退化
- badcase 越多，技能的提示词和脚本调得越准，**误报越少、漏报越少**
- 技能越准，用的人越多，贡献的问题越多——**正向循环**

### 贡献一条 badcase 有多简单

每个技能的 `badcase/` 目录下，一条反例只需要三个文件：

```
skills/{skill}/badcase/001-your-case/
├── input/          # 把出问题的代码丢进来
│   └── example.sql
├── expected.md     # 期望检出什么（一行写一条）
└── prompts.md      # 你当时怎么问的（自然语言就行）
```

然后跑回归脚本一键验证：

```bash
python3 scripts/badcase_runner.py
```

通过就可以提 MR。详见 [贡献指南](../CONTRIBUTING.md)。

### 贡献一个新 Skill 有多简单

公司规范不止数据库、API、架构——如果你所在的领域还没有技能（比如消息、缓存、安全），**自己造一个并不难**。每个技能本质上就是这样一个目录：

```
skills/your-guard/
├── SKILL.md              # AI 入口：告诉 AI 什么时候激活、怎么执行
├── README.md             # 人类入口：能力说明、快速使用、检查项
├── scripts/
│   └── your_check.py     # 检查脚本（Python 3 标准库，无第三方依赖）
├── *-manual-rules.md     # 脚本查不了的规则，交给 AI 逐项核对
├── badcase/              # 反例用例（回归测试）
└── test/                 # 正常样例
```

**从零搭建 4 步**：

| 步骤 | 做什么 | 参考谁 |
|---|---|---|
| 1. 定规范 | 把你领域的规范写进 `steering/your-spec.md`，规则标注【强制】/【推荐】 | `steering/openapi-standards.md` |
| 2. 写脚本 | 按规范写 `your_check.py`，能自动查的用脚本（粗筛），退出码 `0`/`1`/`2` | `skills/api-guard/scripts/api_check.py` |
| 3. 补人工规则 | 脚本查不了的写进 `*-manual-rules.md`，让 AI 逐项核对（精审） | `skills/ddl-guard/ddl-manual-rules.md` |
| 4. 加 badcase | 放 2–3 条反例，跑回归脚本确认能检出 | `skills/ddl-guard/badcase/` |

最后在根 `README.md` 的技能表格注册一行，全团队的 AI 工具就能自动发现你的技能。

> 你最懂你负责的领域——把领域规范变成技能，让全团队的 AI 都遵守你的标准。

> 众人拾柴火焰高——你贡献的每一条 badcase、每一个新技能，都在帮整个团队少踩一次坑。
