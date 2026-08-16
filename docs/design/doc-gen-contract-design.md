# doc-gen 可信化改造设计文档（已落地）

> **状态**：已实施 ✅（§3–§6 + §8 D1/D2/D3）· 284 测试全过 · 真实 CLI 端到端冒烟通过（含站点演进页与着色图构建）
> **范围**：#1 Manifest Schema 契约 + #2 诚实退出码/receipt + #3-L1 revision-pinned evidence（数据层 + 模板展示层）+ #4 delta 引擎与站点演进页（D1/D2/D3 已实施，含 CI 归档策略）
> **作者**：— · **日期**：2026-08-14（§8 实施为 2026-08-15/16）

---

## 1. 背景与动机

### 1.1 起源：archify 对比研究

对外部仓库 [`tt-a1i/archify`](https://github.com/tt-a1i/archify)（agent skill：把代码库/系统描述转成交互式架构图）做了设计拆解，并与本仓库 `doc-gen` 对比。

**关键定性**：两者不是直接竞品，是互补范式——

| 维度 | doc-gen | archify |
|---|---|---|
| 核心范式 | 扫描驱动：**代码即真相** | 作者驱动：**schema 即真相** |
| 回答的问题 | "这个 Java DDD 项目长什么样"（全景） | "我描述的系统/变更怎么画清楚"（特写） |
| IR 契约 | Python 类型（弱契约） | JSON Schema 强契约 + 版本锁定 |
| 可信机制 | arch-guard 扫描 | schema+几何校验+诚实退出码+showcase 验收 |

### 1.2 archify 可借鉴点（按性价比排序）

1. 🟢 **IR JSON Schema 契约 + `schema_version` 锁定**（→ 本文档 #1）
2. 🟢 **诚实退出码 + 校验 receipt 纪律**（→ 本文档 #2）
3. 🟡 **revision-pinned evidence**（→ 本文档 #3-L1，文件级；行级缓做）
4. 🟡 delta 快照对比（未实施，后续可选）
5. 🔴 单文件 HTML / 自研 SVG 渲染器 / Git blob 二次校验（不做：低性价比或解决不存在的问题）

### 1.3 关键洞察：doc-gen 不需要照抄 archify 的校验机制

archify 的 evidence 要 Git blob/line 二次校验，因为其 IR 是**作者手写的**——校验防"AI 编造源码位置"。doc-gen 的 IR 是**扫描生成的**：`sourcePath` 天然来自真实文件遍历，**不存在伪造问题，只存在过期问题**。

因此正确借鉴的是"**钉死版本**"语义：生成时锁 SHA，`blob/<SHA>/<path>` 链接永远指向生成那一刻的代码。这一语义一次 `git rev-parse` 即全额获得，无需 L3 级 Git 校验。

## 2. 改造前的问题基线（实证）

- `builder/astro.py`：npm install 失败 / npm 不存在 / `npm run build` 失败**三条路径全部 `print ⚠ + return`，退出码仍为 0**，外层继续打印"✅ 完成"——"非零退出绝不称成功"的反面教材
- `builder/writer.py`：域分片并发写入失败同样吞错（`print ⚠ 继续`），且 index.json 仍引用缺失文件
- `DocManifest` 为 Python 类型：跨语言/跨工具不可校验，schema 漂移无门禁
- `_dict_to_manifest`（旧版单文件兼容）静默有损转换（丢 `stateMachines`/`layerDependencyReal`/`interfaces` 等）
- 无 receipt：AI/CI 无法机器判定"哪些阶段真的成功"

## 3. 方案设计

### 3.1 设计原则

- **KISS**：doc-gen 零第三方依赖（纯标准库），校验器内置子集实现，不引入 `jsonschema`
- **契约对齐分片**：schema 与 `ManifestWriter` 分片一一对应，不发明新结构
- **分层严格度**：结构化事实锁死（`additionalProperties: false`）；自由文本（Mermaid、OpenAPI spec）只校验类型——OpenAPI 有自己的规范，不重复造轮子（YAGNI）
- **诚实降级**：warn 是事实降级不阻断；fail 才阻断；缺事实就明示，不伪造

### 3.2 #1 Schema 契约

```
skills/doc-gen/schemas/
├── common.schema.json         # 共享 $defs（component/table/stateMachine/crossDomainDep...）
├── index.schema.json          # schema_version const 1 + 域列表/统计
├── meta.schema.json           # project + evidence{repo_url,revision,generatedAt,dirty}
├── domain.schema.json         # 6 层结构（layers minProperties=1，空域无信息价值）
├── database.schema.json       # tables/relationships/unmatched_fks/inferred/source
├── state-machines.schema.json
└── cross-domain.schema.json
```

**版本锁定**（archify 式）：`schema_version: {"const": 1}`。index.json 同时保留旧 `schemaVersion: "1.0"` 字符串（generator 格式历史，语义不同，避免破坏消费端）。

**校验器** `scripts/validator.py`（115 行，零依赖）：支持且仅支持所用关键字子集（type/properties/required/items/enum/const/additionalProperties/minProperties/minItems/minLength/minimum/pattern/`$ref` 含跨文件），含联合类型 `["string","null"]` 与 bool≠int 区分。

**注入点**：
- 生成端：`writer.write()` 末尾自检，失败抛 `RuntimeError`（生成器 bug 不静默出劣质产物）
- 消费端：`--from-manifest` 构建前门禁；含 `schema_version:1` 严格校验，无则 warn 跳过（旧文件 additive 兼容，不硬失败）

**Drift 防线**：COLA fixture golden test（`tests/test_schema_validator.py`）——生成器改字段而 schema 未同步即测试红。等价于 archify 的 `check:validators`。

### 3.3 #2 退出码 + Receipt 契约

**退出码表**（唯一权威定义）：

| 码 | 含义 | 触发 |
|---|---|---|
| 0 | 成功 | 所有已执行阶段 ok |
| 1 | 阶段失败 | manifest 校验失败 / 分片写入失败 / npm 缺失 / install/build 失败 / build 成功但无 dist |
| 2 | 用法错误 | 参数缺失、路径无效（保留原行为） |

**Receipt**（`doc-manifest/receipt.json`）：`{schema_version:1, ok, checks{...}}`，每 check `status ∈ {ok, warn, fail, skipped}`；`ok` 当且仅当无 `fail`；**退出码由 receipt 驱动**（单点真相）。`build_receipt`/`write_receipt`/`_finish` 为纯函数（可测性）。

### 3.4 #3-L1 Evidence

```json
"evidence": { "repo_url": "...", "revision": "<40位SHA>",
              "generatedAt": "...", "dirty": <bool> }
```

- `collect_evidence(project_root, config)`：`git rev-parse HEAD` + `status --porcelain`；无 git 降级 `revision: null` 不阻断
- `dirty` 标志：扫描未提交工作区时 SHA 对不上实际内容，必须如实标注（延续 #2 诚实契约）
- **新鲜度**：`--from-manifest` 时 `_stale_commits()` 计算 `rev-list --count revision..HEAD`，>0 警告"文档已落后 N 个提交"
- **模板展示**（`template/scripts/lib/utils.mjs`）：`srcAbbr()` 是全站组件渲染单一汇聚点，改一处全站生效。`sourceLinkUrl()` 三分支：
  - `project_repo` 含 `{revision}` 占位 → 模板格式化（Codeup/GitLab/GitHub 各自 URL 形态全覆盖，OCP：平台差异由配置吸收，渲染端零平台判断）
  - 裸 URL（旧配置兼容）→ 默认 `{repo}/blob/{revision}/{path}`
  - 无 revision/repo_url/sourcePath → `null`，不渲染链接（**没有钉定版本就不给会漂移的链接**，维持纯 tooltip）

### 3.5 明确不做的（YAGNI）

- **L2 行级 evidence**：`_parse_java_file` 正则改造风险集中（泛型嵌套/注解合并等已声明的局限），"跳到这个类"已覆盖 90% 评审需求
- **L3 Git blob/line 二次校验**：解决 doc-gen 不存在的问题（见 §1.3）
- **diagrams.json 结构锁定**：Mermaid 自由文本，只保证 JSON 可解析
- **meta.project / risks / adrs / articles 锁死**：meta 是用户配置自由 dict；其余各有上游规范，后续按需纳入

## 4. 实施记录

### 4.1 文件清单

**新增（5 组）**：`schemas/*.json` ×7、`scripts/validator.py`、`scripts/tests/test_schema_validator.py`（34 测试）

**修改（8）**：`builder/writer.py`（schema_version/evidence/自检/域失败显式化）、`builder/astro.py`（失败传播）、`builder/aggregate.py`（build 失败 exit 1）、`doc_gen.py`（receipt/门禁/staleCommits/统一退出码）、`SKILL.md`/`README.md`（契约条款）、3 个既有测试文件（spy 返回值 + 假数据遵守 IR 契约）

### 4.2 实施中发现的缺陷（golden test 实战价值）

Golden test 首跑即抓到 **3 处 schema 与生成器的真实 drift**：

1. `database.json` 实际有 `unmatched_fks` 字段（预研 grep 漏看）
2. `ComponentDoc.type` 是**开放集合**：`layers.py classify()` 三级兜底（层名兜底 / `class_name.lower()` / start 层 `"application"`），非 SUFFIX_TYPE_MAP 32 值封闭集
3. `endpoints.method` 有 `"*"` 值（`@RequestMapping` 未指定 method）

**修正原则：schema 对现实建模，而非对愿望建模**——type 撤销 enum 改开放 string + minLength 1；另两处补齐真实结构。

实施中额外暴露并根治：`writer.py` 域分片并发写入失败吞错（方案预研只发现 astro.py 三处）；`staleCommits`（int）误入 checks dict 导致 `build_receipt` 对 int 调 `.get()`（自测发现并修复：元数据并入 manifest check，不混入 checks）。

### 4.3 既有测试适配说明

- spy/mock `build_astro` 需返回 `True`（旧 mock 返回 None → falsy → 按失败处理，这正是新契约语义）
- test_writer 假数据改为遵守 IR 契约（`methods` 是方法名 str 数组而非 dict、crossDomainDep.type/fieldKind 用真实枚举值、table 补 columns）
- `test_write_empty_domain_skips_layers` 语义调整：空**层**仍跳过；完全空域由自检拒绝（空域文件无信息价值，视为生成器 bug）

## 5. 验证结果

| 项 | 结果 |
|---|---|
| 全量测试 | 258 passed（新增 34） |
| 覆盖率 | TOTAL 93%；writer 100%、validator 92%、astro 90%；doc_gen 变更行（receipt/门禁/退出码）全覆盖 |
| 真实 CLI 冒烟 | fixtures 扫描 exit 0；receipt.json 全 checks 语义正确（openapi=warn 因 fixture 无端点、build=skipped） |
| evidence 钉定 | 真实 git HEAD SHA + `dirty: true` 如实反映未提交变更 |
| --from-manifest 门禁 | schema_version=1 校验通过 + 真实 npm 构建 exit 0 |
| 模板链接 | Codeup 模板注入 → 13 个 MDX 页面组件类名全部渲染 `blob/<40位SHA>/<repo相对路径>` |
| sourceLinkUrl 分支 | 模板+{path} / 模板无{path} / 裸URL / 绝对路径剥离 / 三种降级 → null，全过 |

## 6. Breaking 变更与边界

- **npm 缺失 / install / build 失败从"静默跳过"变为 `exit 1`**（有意为之：显式 `--build` 后静默跳过即虚假成功）。依赖旧行为的 CI 脚本需显式降级（`|| true`）
- `project_repo` 推荐配置为完整链接模板（含 `{revision}`/`{path}` 占位符）；裸 URL 保持兼容（默认 GitHub/Gitea 风格）
- schema 演进规则：additive 字段不 bump `schema_version`；破坏性变更 bump 2 并让 v1 文件显式报错

## 7. 后续可选

- **#4 delta 快照对比**：D1 已实施（见 §8）；剩余可选：D2 站点「架构演进」页（+0.5 天）、D3 Mermaid 着色 delta 图（YAGNI 暂缓）
- **L2 行级 evidence**：✅ 已实施（2026-08-16）——v2a 的 `_strip_comments` 等长化基石使成本从评估的 ~2 天降至极低：`classLine`/`methods[].line` → `ComponentDoc.sourceLine` → 模板 `#L` 锚点直达类声明行
- **risks/adrs/articles 分片纳入 schema**：结构稳定后按需锁定
- **模板端 receipt 可视化**：站点首页显示构建 checks 与 staleCommits

## 8. #4 delta 可行性评估与实施（D1 已落地）

> **状态**：评估完成 ✅ · **D1（引擎+CLI+测试+CI 归档策略）与 D2（站点演进页）已实施** ✅ · 2026-08-15
> 交付物：`scripts/delta.py`（引擎+markdown 渲染）、`doc_gen.py diff` 子命令、`tests/test_delta.py`（26 测试）、`ci/archive-manifests.example.yml`、`template` 的 `generateDeltaPage` + sidebar 接入
> D2 验证：delta.json 放入 doc-manifest/ → generate-pages 产出 evolution.mdx → astro build 产出 dist/evolution/ 页面，sidebar 显示「🔀 架构演进 (N)」徽标；JS 端渲染与 Python 端 render_markdown 共享同一信噪比契约（presentation-changed 不计入）
> 实施补充：CLI 旧版兼容分发的子命令排除列表已同步加入 `diff`；`moved + 字段同时变化` 时分组合并进 moved 条目（信息不丢失）；真实 CLI 冒烟验证（同内容双快照 → 0 变化、revision 锚定、markdown 渲染正确）

### 8.1 archify delta 的三个核心机制（精读 `delta/architecture-delta.mjs` 68KB 的结论）

1. **字段分组 → 状态分级**（信噪比控制的灵魂）：字段按 `semantic/evidence/geometry` 分组，变化分类决定状态（`changed/moved/rerouted/evidence-changed`）——**不是所有变化等权**
2. **presentation 与语义分离**：`title/preset/legend/cards` 等呈现字段单独报告（`presentationChanged`），绝不混入架构事实
3. **stable ID 对齐 + 诚实失败**：实体靠稳定 ID 对齐，缺 ID 直接拒绝 diff（`delta/stable-id-required`）；canonical 排序归一化保证 key 顺序无关

### 8.2 doc-gen 映射设计

**优势**：doc-gen 有天然 stable ID——`qualifiedName`（扫描产物、全局唯一、零成本），archify 靠作者手写 `id`。

**字段分组**：

| 分组 | 字段 | 状态映射 | 信噪比 |
|---|---|---|---|
| `semantic` | `type`, `qualifiedName` | changed | 高 |
| `lifecycle` | `deprecated` | changed（高亮） | 高（废弃翻转是治理事件） |
| `position` | 所在 `(domain, layer)` | **moved**（域/层迁移） | 高（架构漂移信号） |
| `behavior` | `methods`, `endpoints` | changed | 中 |
| `presentation` | `description` | 单独报告不计入 summary | 噪声源（Javadoc 变化频繁），隔离 |

**moved 两层启发式**：`qualifiedName` 同但 `(domain,layer)` 变 → moved；`className` 同但 `qualifiedName` 变（包重命名）→ moved + `inferred: true` 置信标注（同时重命名+移动时可能误判，如实降级）。

**六个 diff 维度**：components（含 moved）、aggregates（聚合归属变化）、database（表/列/索引）、stateMachines（转换+质量 issue）、crossDomain（耦合增删，治理金矿）、openapi（path+method 端点集合）。`diagrams` 不 diff（派生物）。

**输出**：`doc_gen.py diff <A> <B> --output delta.json [--markdown delta.md]`；JSON receipt 锚定 `base.revision → head.revision`（复用 #3）；markdown 可贴 PR comment。输入 `schema_version` 不相等 → exit 2（复用 #1 门禁）。

### 8.3 成本 / 风险 / 不做清单

- **成本 D1（引擎+CLI+测试）约 250+120+150 行，1–1.5 天**；基础设施复用度极高（#1/#2/#3 全部现成）
- **风险**：包重构 ID 漂移（对策：className 恒等启发式 + 置信标注）；description 噪声（对策：presentation 分组隔离）
- **不做（YAGNI）**：SVG/Mermaid 着色 delta 图（archify `buildDeltaSvg` 等价物）——+1 天、锦上添花、Mermaid 着色表达力弱；若要做，D3 独立立项。D2 站点「架构演进」页 +0.5 天可选
  - **2026-08-16 修订**：D3 已按变化焦点图形态实施（放弃全景图——delta.json 不含完整快照，全景数据不支持）。组件图用 `classDef` 四色（绿新增/红移除/黄变更/蓝迁移）+ `domain/layer` subgraph，moved 节点标注来源位置；跨域依赖变化图用 `linkStyle` 边着色（图形态天然契合）。不做 Before/After 双图（同样受数据约束），这是与 archify `buildDeltaSvg` 的本质取舍：archify 有自研 SVG 渲染器可三视图并存，doc-gen 的 Mermaid 路线只做单焦点图

### 8.4 最大风险不在技术：归档流程前置依赖

delta 依赖"两份 manifest 都被保留"的使用习惯（CI 按 commit 归档，或 PR 流程强制 before 快照）。**若无归档流程，D1 落地即闲置**。立项顺序应为：先归档流程、后 delta 引擎。

### 8.5 价值定位：治理三角收口

与 arch-guard（静态规则）、impact-guard（预测影响）形成三角：**规则 → 预测 → 实证**。"这次重构只动了 adapter 层"从口头承诺变成 receipt 事实。

---

## 9. 再对比 archify（2026-08-16，基于双方最新实现）

> **背景**：初次对比（本文档 §1，2026-08-14）驱动了 #1–#4 全部改造。两天后双方均大幅演进（doc-gen 四件套 + impact v1/v1.1/v2 + 联邦化起步；archify v2.13→v2.14 + DeepSeek Harness 集成 + 25 commit），重验当初判断。

### 9.1 初次借鉴点收口状态：5/5 全部落地，无一后悔

| 借鉴点 | 当初判断 | 收口状态 |
|---|---|---|
| #1 schema 契约 + 版本锁定 | 🟢 强烈建议 | 超越：13 分片（5 必选 + 8 可选）vs archify 7 schema，同为 const 锁定 |
| #2 诚实退出码 + receipt | 🟢 强烈建议 | 更广：archify receipt 仅 validate/deliver；doc-gen 贯穿 11 阶段 + 首页可视化 |
| #3 evidence 钉版本 | 🟡 文件级先做 | L1+L2 完整（#L 行锚点）；archify blob 校验防伪造——doc-gen 扫描即真相不需要，判断经住检验 |
| #4 delta | 🟡 评估后做 | D1–D3 全落地；SVG 三视图 vs Mermaid 焦点图是渲染栈约束下的合理分叉（§8.3 已留痕） |
| #5 不做清单 | 🔴 | 维持不做，无一后悔 |

"schema 对现实建模而非愿望建模"等决策原则在 13 分片扩展中零翻车。

### 9.2 演进方向分道扬镳：竞品定性彻底失效

- **archify 纵深**：视觉打磨（viewport/图例）、分发（DSH bundle）、发布稳定性——把"单张图精雕"做到极致
- **doc-gen 横向**：治理生态（arch-guard/impact-guard/delta 三角）、联邦化（arch-hawkeye）、业务维度（business-context）——把"项目→组织级架构治理"铺开

**终局定性**：archify 是仪器（instrument），doc-gen+鹰眼是观测站（observatory）。§1.2 的"互补范式"判断是整个改造的种子，两天后双方背向演进证实了它。

### 9.3 archify 新演化的两个可借鉴点（按需，未立项）

1. **zero-regression 发布物锁定**：测试锁定 FIXED_POINT commit + git blob SHA（tarball/package 双 blob），发布产物字节级可复现。doc-gen golden test 锁 schema 结构不锁发布物；若 awesome-rules 插件包（7 工具清单）需要防漂移，可加"清单 blob 锁定"测试。属 CI 加固项。
2. **DSH 集成的边界声明风格**：Skill-only 最小 bundle + 明确声明"不注册原生工具/网络/凭证/hooks"。awesome-rules 多工具插件目录是同命题更完整的解，但其"声明不做什么"的边界文档风格值得借鉴。

### 9.4 维持不可借鉴

自研 SVG 渲染器、几何校验引擎（archify 核心资产，服务"作者手写 IR"范式）——doc-gen 无此问题域；Mermaid 着色天花板已由 D3 焦点图形态消化。

> **一句话**：archify 教会 doc-gen"可信"（契约/退出码/钉版本），doc-gen 用它建了 archify 没有的东西（治理三角 + 联邦观测）。师承已消化，赛道已分岔，后续仅跟踪 zero-regression 式工程加固技巧。
