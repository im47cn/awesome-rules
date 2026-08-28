---
name: skill-evo
description: >
  会话经验自动总结与规范/技能进化（Hermes 式自进化闭环）。Claude Code 会话结束后由
  SessionEnd hook 异步总结会话，提炼用户纠正/失败模式/成功模式，生成对 skills/*/SKILL.md
  与 steering/*.md 的进化提案（置信度分级、pending 人工审核、只追加不改写、永不自动应用）；
  同时搭车增量扫描 omp（oh-my-pi）会话与插件哑故障巡检。数据在 ~/.config/ar/skill-evo/。
  当用户提到：skill-evo、进化提案、审核提案、查看提案、应用提案、驳回提案、会话总结、
  经验沉淀、规范进化、插件巡检、插件加载失败、为什么 AI 又犯同样错误时激活。
---

# 会话经验进化 (skill-evo)

把每次会话中「用户纠正 AI / 反复失败后找到正确做法 / 被认可的模式」自动沉淀为
本仓库规范与技能的进化提案。**提取全自动，应用必须人工审核**——这是 Hermes
self-evolution 的核心护栏（一切进化走人工评审，绝不直改）。

架构、omp hook 安装、GEPA 原理、配置详解、设计边界等背景知识见
[README](README.md)（渐进式加载：本文件只保留审核操作所需的指引）。

## 工作流（人工审核入口）
- 手工构造提案（write_proposal API）时 heading 锚点须含 `##` 级前缀且与目标标题整行逐字相等——apply 的匹配逻辑是 `ln.strip() == heading.strip()` 且行首为 #，漏 `##` 前缀会报「找不到标题锚点」；构造后先 `apply --dry-run` 验证锚点解析

- pending 大量积压时（如 39 份提案 118 条 lesson）逐条人工审不可扩展：起独立 AI 预审 agent 按三点核对法（证据可追溯/目标合理/变更得当）全量核对，产出 apply/reject/灰区分级报告与竞态重叠群图谱，人只终裁灰区条目与结构性决策；预审不改变处置路径，apply/reject 仍走本节命令（2026-08-24 实战：118 条 → apply 65 / reject 36 / 灰区 17，人终裁 3 项）
- 实验/调研类任务的交付边界是报告本身：agent 自产的方向性结论（样本量小、自述不显著）不构成执行依据，结论落地须另开提案走人工审核。实测案例（2026-08-24 消融实验）：子代理在报告自述「不显著、夹具泄题」的同时直接删除 manual-rules 7 条规范（含两条安全规则），被集成验收 revert——安全类规则的裁剪证据门槛须高于普通条目。

- 内容重叠的重复提案（如竞态期间同会话产出两份）：应用内容更完整的超集版本，驳回被包含的子集，并在 reject_reason 注明取代关系与产生根因——驳回同时为 GEPA 积累带精准反馈理由的负样本
- 审核「模式归纳」类提案时警惕单例过拟合：从单一来源归纳的结构可能不完整或误判必选项（实测案例：初版模板在 5 条样本下即被修正，14 条样本后才区分出必选段与可选段）。优先采纳有跨会话/多样本复现证据的条目；仅凭单例归纳的模式即使采纳也应保持低置信度。

### 第 1 步：列出待审提案

```bash
python3 scripts/evo.py list
```

输出每个提案的 id、lessons（lesson_id + 证据核验标记 + 置信度 + 类型 + 目标文件）与护栏警告。
证据核验标记：`✓` = evidence 逐字命中来源会话原文；`⚠` = 转述拼接（整段未逐字命中，
但最长连续命中 ≥16 字——总结器缝合原文片段的常见形态，不拦 apply，人工抽查可关注）；
`✗` = 未命中（可疑编造，apply 会拦截）；`?` = 来源会话缺失无法核验。

若置顶出现「⚠️ 插件哑故障」段（CC 插件 failed to load 巡检台账），一并提示用户；
复查命令：`python3 scripts/evo.py patrol [--force]`。

### 第 2 步：逐条审核

对每个 lesson 核对四点（AI 协助时必须打开提案原文展示）：

1. **证据可追溯**：evidence 是否真出现在来源会话中——`list`/`apply` 已自动做空白与引号字形不敏感的
   逐字核验（脚本代人工抽查），`✗` 时仍应人工打开来源会话确认
2. **目标合理**：target_file 与 heading 锚点是否是该经验的正确落点
3. **变更得当**：new_text 是否与目标文件既有风格一致、无重复条款
4. **归因断言须定案证据**：new_text 含归因句式（「X 把 Y 置为/造成/所致」）时，
   引文真实 ≠ 判断正确——evidence 须无推断语气且带可核对锚（时间窗/file:line/
   命令输出），`attribution_warnings` 已机械化此项。2026-08-27 实证：会话推测
   「.factory 流水线置 bare」逐字命中引文核验被放行，dispatch 日志后证主链清白
   （作案在两轮空档），错误归因已随条款扩散、需人工矫正——在场 ≠ 所为

护栏规则（apply 会自动检查，命中则需 `--force`）：
- new_text 含**【强制】**标记 → 强制级别是人工评审决策，自动化只能提【推荐】级内容
- 置信度 Low → 建议先人工核实
- **归因断言证据不足**（推断语气 / 缺锚）→ 归因类断言证据等级高一档，须人工
  以时间窗证据定案后 `--force`（`attribution_warnings` 检测）
- **重复沉淀**（三分支）：lesson_id（按 target|type|new_text 内容哈希确定性派生）已存在于
  applied 归档 / new_text 已逐字存在于目标文件 / **new_text 与既有段落语义相似
  （difflib 相似度 >= `idempotent_threshold`，默认 0.8）→ 疑似同一教训换皮重提，
  需人工 diff 后改写合并**
- `knowledge_type=instance`（随环境实例变化的 ID/路径/字段名/账号/时间戳/版本号）
  → 不入技能文档，正确位置是代码（运行时发现）或 ADR（决策记录）；技能只沉淀稳定
  方法论（pattern）
- **steering 既有【强制】条款不可被削弱**——v1 仅支持追加（append_under/append_end），
  改写删除类变更一律驳回并等待人工直接编辑规范文件

硬错（`--force` 不可越过）：`supersedes` 引用不在 applied 归档中的 lesson_id 或指向自身。
修正既有 lesson 的方式不是改写，而是新 lesson 填写 `supersedes: L-XXXXXXXX` 指向旧
lesson_id（人工审核时在提案 JSON 块中填写），保留完整的演进链。

### 第 3 步：应用或驳回

```bash
# 预演（不落盘，展示将追加的内容与位置）
python3 scripts/evo.py apply <id> --dry-run

# 确认后应用（直接写入目标文件；护栏警告命中时加 --force）
python3 scripts/evo.py apply <id> [--force] [--codes "L-XXXX:content_overlap"]

# 驳回
python3 scripts/evo.py reject <id> --reason "证据不足" --codes "dup_superset"
```

**结构化 verdict（GEPA 标注）**：apply/reject 归档时自动 diff 原始快照（`<id>.orig`）
推导每条 lesson 的最终处置（applied 原样 / trimmed 裁剪后应用 / edited 修锚点后应用 /
rejected 剔除或驳回）——review 时对 pending 文件的任何裁剪、锚点修正、lesson 剔除
都会被确定性捕获。`--codes` 补充机器推不出的**语义原因**（裸码=提案级；`L-XXXX:码`
=lesson 级，可混用逗号分隔）。合法码：`dup_superset`（被超集包含）/`content_overlap`
（与目标现文重复）/`anchor_defect`（锚点缺陷）/`low_value`（单例过拟合等价值不足）/
`off_target`（落点不当）/`scope_mismatch`（个人偏好非团队资产）/`style_mismatch`
（风格不符）/`other:<自由文本>`（逃生舱，GEPA 不消费）。未知码 fail-closed 拒收。

应用后：
- 变更已写入工作区，**提示用户 `git diff` 检查，满意后自行提交**（本技能永不自动 commit）
- 锚点失配/不唯一时 apply 整体失败不盲写——此时应人工打开目标文件与提案，改由人工编辑
- 归档文件携带 verdict（frontmatter `review:` 投影 + 机读 JSON 字段），`.orig` 快照
  随归档保留（LLM 原始输出 vs 人工修订对照，GEPA 最有价值的标注信号）

> ⚠️ **prompt_evolution 型提案不走 apply**（apply 仅支持 markdown 追加语义）。人工审阅
> 提案中新 SYSTEM_PROMPT 后，手动编辑 `scripts/evo_prompt.py` 的 `SYSTEM_PROMPT` 常量采纳。

GEPA 进化（`evolve`）有真实 LLM 成本，仅在用户明确要求时运行；命令与冷启动条件见
[README](README.md#快速使用)。配置项速查见 [config.example.toml](config.example.toml)。
