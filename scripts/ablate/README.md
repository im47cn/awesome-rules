# 技能上下文消融实验（Ablation）报告

对自家 11 个常驻 guard 技能做一次 coleam00/skills「ablate-ai-layer」式测量：剥离技能规则正文，重跑同一审查任务，diff 两臂，回答一个问题——**技能正文的 token 成本到底买到了多少检出率？**

- 实验日期：2026-08-24
- 引擎：`omp -p`（headless，本仓库默认模型 `zhipu-coding-plan/glm-5.3`）
- 原始数据：`results/ablation.jsonl`（逐次记录）、`results/raw/*.log`（每次调用的完整 stdout/stderr）、`results/summary.md`（机器生成汇总表）

## 方法

### 两臂定义

同一 badcase 夹具（`input/` 输入文件 + `prompts.md` 用户原话 + `expected.md` 期望规则）跑两次 omp：

| 臂 | prompt 构成 | 隔离措施 |
|---|---|---|
| **WITH** | 审查任务指令 + `SKILL.md` 全文 + `*-manual-rules.md` 全文 + 输入文件 | 见下 |
| **WITHOUT** | 审查任务指令 + 输入文件（**不含任何技能规则正文**） | 同 |

两臂的输入文件字节完全一致；任务指令、输出契约（`DETECTED: 规则1; 规则2; ...` 汇总行）也完全一致。唯一变量是技能规则正文的有无。

### 为何这样隔离

1. **omp 本身会自动发现并加载本仓库 `skills/`**——若不隔离，WITHOUT 臂会被仓库技能污染，两臂就不再是干净对照。因此每次调用均加 `--no-skills --no-rules --no-extensions --no-tools --no-lsp --no-session`，并在临时目录 `--cwd` 运行。
2. **`--no-tools` 是关键设计决策**：guard 技能的实际形态是「脚本检查（`ddl_check.py` 等）+ LLM 人工判断」。脚本一跑，两臂都满分，技能正文贡献就被脚本淹没了。禁用工具强制走纯 LLM 判断通道，测的正是 SKILL.md 里「第 3 步补充人工判断」那条链路——即模型只带规范文档读代码时的检出能力。
3. 检出判定：模型按输出契约给出 `DETECTED:` 汇总行，与 `expected.md` 的期望规则做归一化子串/同义词/LCS≥3 匹配（LLM 措辞与夹具期望措辞常有差异，如「单表索引数量超限」vs「索引数量」）。

### 局限（如实声明）

- **样本量极小**：3 badcase × 2 臂 = 6 次调用（成本纪律上限），每格只有一个观测，无重复、无方差，检出率差不能当作统计显著的结论。
- 单模型、单温度、无 few-shot 变体；badcase 本身是为脚本检查设计的反例集，输入里的注释（`-- 违规: ...`）对两臂同等地泄题，可能抬高 WITHOUT 臂基线。
- 匹配依赖同义词表，存在把「正文提过但未列入 DETECTED 行」记为漏检的契约性误差（已按输出契约判定，不算解析错误）。

## 常驻成本计量

11 个技能 SKILL.md frontmatter description 常驻注入每个会话（`--resident-cost-only` 实测）：

| skill | desc chars | 估算 token (chars/4) |
|---|---:|---:|
| alibabacloud-devops | 187 | 46 |
| api-guard | 233 | 58 |
| arch-guard | 171 | 42 |
| code-review | 246 | 61 |
| contract-guard | 215 | 53 |
| ddl-guard | 144 | 36 |
| doc-gen | 196 | 49 |
| impact-guard | 224 | 56 |
| skill-evo | 318 | 79 |
| tokensave-mcp | 253 | 63 |
| work-report | 257 | 64 |
| **合计（11 技能）** | **2444** | **~611** |

> chars/4 是英文启发式，中文实际约 chars/1.5~2 token，**611 是下限估算**；真实常驻成本更可能在 1.2k~1.6k token/会话。另注：SKILL.md 正文（含工作流）并不常驻——仅当技能被激活时注入，所以「常驻成本」只算 description。

## 真实数据（6 次 omp 调用，全部实测）

| # | 技能 | badcase | 臂 | 检出率 | 命中/期望 | 漏检 | 耗时 | 估算 token* |
|---|---|---|---|---|---|---|---:|---:|
| 1 | ddl-guard | 001-禁用类型+缺注释 | WITH | 0.60 | 3/5 | 禁用类型、泛化字段名 | 124.3s | ~1795 |
| 2 | ddl-guard | 001-禁用类型+缺注释 | WITHOUT | 0.60 | 3/5 | 禁用类型、泛化字段名 | 112.4s | ~672 |
| 3 | ddl-guard | 004-索引设计 | WITH | 0.83 | 5/6 | 索引数量（正文提及未列入清单） | 152.1s | ~2906 |
| 4 | ddl-guard | 004-索引设计 | WITHOUT | 1.00 | 6/6 | — | 62.0s | ~1918 |
| 5 | api-guard | 001-path传标识+命名 | WITH | 1.00 | 3/3 | — | 118.3s | ~1228 |
| 6 | api-guard | 001-path传标识+命名 | WITHOUT | 0.00 | 0/3 | 全部 | 65.4s | ~463 |

\* omp `--mode json` 输出实测**不含 token usage 事件**，token 为 prompt+输出 chars/4 估算（中文偏低）。

**汇总**：WITH 平均检出率 0.811，WITHOUT 平均 0.533，**差值 +0.278**；WITH 平均耗时 132s vs WITHOUT 80s（长 prompt 推理更久）；WITH 平均估算 token ~1976 vs ~1018/次。

## 结论

1. **技能正文的价值是「团队特有约定」，不是通用工程常识。** 分化的机制很清晰：
   - api-guard WITHOUT 臂 0/3：模型凭通用 REST 直觉检出了「GET 做写操作」「URL 含动词」，但检不出本团队特有的「禁止 path 传标识」「kebab-case 路径命名」「动作收敛白名单」——这些规则没有任何先验，必须靠注入。
   - ddl-guard 004 WITHOUT 反而 6/6：「索引前缀 uk_/ix_、联合索引≤5 字段、索引名≤64 字符」这类约定恰好是业界常见实践，模型先验已覆盖，规范正文在此是冗余的——WITH 臂还因长上下文多花 90s 与 ~1000 token。
   - ddl-guard 001 两臂都漏「禁用类型」（`remark text`）和「泛化字段名」，说明技能正文对语义类规则（命名是否泛化）的增益也有限——这类规则即便写在文档里，模型执行得也不严格。
2. **成本-收益判断**：常驻 description（~611 估算 token/会话，真实或 1.2k~1.6k）只负责触发路由，真正的成本发生在激活后注入正文（本次 WITH 臂每次 +1.0k~2.4k 估算 token、+50~90s）。按本次数据，正文注入的检出率期望增益为正（+0.278）但高度规则依赖：**团队特有约定收益大，业界通用约定零收益**。
3. **可执行建议**（超出本实验验证范围，标注为推断）：manual-rules 应裁掉「业界通用」条目、只保留团队特有约定（api-guard 模式），通用条目降级到脚本或干脆删除；ddl-manual-rules 里「索引前缀/长度/字段数」一组大概率可整体交给脚本，无需 LLM 读。

## 复现

```bash
python3 scripts/ablate/ablate.py --help
python3 scripts/ablate/ablate.py --dry-run                        # 查看调用计划与 prompt 概要
python3 scripts/ablate/ablate.py --resident-cost-only             # 常驻成本表
python3 scripts/ablate/ablate.py --skills ddl-guard --cases 001-forbidden-type-and-missing-comment,004-bad-index
python3 scripts/ablate/ablate.py --skills api-guard --cases 001-wrong-http-method-and-naming
```

注意：`ablation.jsonl` 为追加式；重跑前清空 `results/` 以免新旧记录混入汇总。
