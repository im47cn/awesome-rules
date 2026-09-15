# skills 清单门禁 + frontmatter 单一事实源（设计决策记录）

- 状态：已落地（gauntlet `frontmatter-manifests` 层）
- 日期：2026-09-14
- 背景：2026-09 对 rome-os/rome 的四轮代码级调研（协议层/状态层/执行层/分发层），
  实证其校验链最薄弱环节是「正则解析无 schema」（skill-frontmatter.ts）。
  对照本仓发现同款病灶：`hooks/load-steering.sh` 与 `tools/check_doc_freshness.py`
  各持一份 frontmatter 解析逻辑，靠注释声明「口径对齐」——纪律同步，无机械守护。

## 目标与非目标

**目标**
1. 消灭 frontmatter 双解析器（单一事实源，机械保证口径一致）
2. 新增 skills 声明式清单门禁：`files` 断链单向检查 + 路径围栏

**非目标**
- 反向闭包（磁盘文件必须被声明）——漂移代价不对称，死文件是认知噪音非运行时断裂
- 全仓 markdown 统一 schema——docs/ 等文档族无已验证的消费场景，不为假想消费者立法
- 崩溃收敛/事件重读等架构级移植（调研 P2 项）——另行立项

## 决策记录（grilling 六项裁决）

### ADR-1 范围：共享解析器 + skills 清单门禁
选项 A（仅修病灶）/ B（+清单门禁）/ C（+P2 架构移植），裁决 B：
gauntlet 31 层中无等价层（真空白），且 skills 漂移有运行时断裂代价。

### ADR-2 双层严格度
声明字段严格校验（类型/必填/路径存在/重复键拒绝）；未知字段容忍但惰性。
不照搬 Rome「未知字段一律拒绝」——那是为机器写的不可变发布物设计的；
本仓 frontmatter 是人手写的活文档，封闭 schema 是为 0 个已发生事故买持续维护税。
typo 由必填缺失兜底（`scenario` 缺失即失败，拼错的 `scenrio` 自然现形）。

### ADR-3 断链单向
只验证「声明的路径必须存在」；不反向要求「磁盘文件必须被声明」。
理由：断链 = 技能执行时当场炸（高代价）；死文件 = 人工审查可见的噪音（低代价）。
门禁优先覆盖不可逆/高代价方向。falsifier：出现死脚本被误认为活代码并引发
误改的真实事故 → 升级反向闭包。

### ADR-4 覆盖 steering + skills 两族
- steering/*.md 与 steering/gtsp/*.md：title/scenario 必填、单行、非空（M1）
- skills/*/SKILL.md：name 必填 + files 断链单向 + 路径围栏（M2）
只修解析器不挂 steering 校验 = 病灶只修一半：分叉压力仍在。

### ADR-5 存量程序化一次性补全
`tools/backfill_skill_manifests.py` 枚举 skill 目录全部 git 跟踪文件（SKILL.md
自身除外）生成存量声明；此后 files 必填（纯文档型可显式 `files: []`）。
渐进可选（缺失静默通过）= 门禁上线首日覆盖率 0%，旁路即最薄弱环节。
已知代价：ddl-guard 167 项、doc-gen 112 项（fixtures 全量入清单）；
PR 中可裁剪（门禁只查断链不查多声明，ADR-3），裁剪须在 PR 说明。

### ADR-6 hook 单实现
`hooks/load-steering.sh` 改为 import `tools/frontmatter_lib.py`，
消灭第二份实现。不用「双实现+一致性负控」（养两份代码再雇裁判，
只能证明测试时刻一致）；不用「hook 读预生成索引」（把确定性问题换成
缓存新鲜度问题）。

## 解析分层（实现要点）

`frontmatter_lib` 同模块两条路径，分叉被结构性封死：

| 路径 | 依赖 | 消费者 | 契约 |
|---|---|---|---|
| `simple_fields` | 纯 stdlib | SessionStart hook、doc-freshness R7b | 单行 `key: value` 标量子集 |
| `parse_frontmatter` | PyYAML（fail-closed） | frontmatter-manifests 检查器 | 完整 YAML（折叠块/列表/重复键拒绝） |

M1 校验强制 steering title/scenario 为单行标量 ⇒ simple 路径的假设恒成立。
hook 不引入第三方依赖（SessionStart 环境），检查器 fail-closed（缺 PyYAML
报错而非静默降级）。

## 门禁语义

- 层名：`frontmatter-manifests`（gauntlet，紧随 doc-freshness）
- 检查器：`tools/check_frontmatter_manifests.py`
- 错误码：M1（steering 族）/ M2（skills 族）
- 负控制：test_gauntlet_checks.sh NC22a-e（编号自 NC19 顺延——rebase 到 main
  时 NC19-21 已被 diff-cover/md-link-check/sourcery-gate 占用）
  （M1 缺 scenario / M2 断链 / M2 路径逃逸 / M2 缺键 + 正控制放行）

## 维护规则

- 改 `tools/frontmatter_lib.py` 须跑全量 gauntlet（口径变更同时影响
  SessionStart 注入与门禁校验——这是特性不是缺陷）
- 新增 skill：起草 frontmatter 后可复跑 `backfill_skill_manifests.py`
  生成基线清单再按需裁剪（裁剪在 PR 中说明）
- 新增 steering 规范：带 frontmatter（title + scenario）即自动进索引与门禁
