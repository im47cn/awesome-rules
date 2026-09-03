# 任务书:P2-replay-eval-收尾核对-开发工程师Sam

> 背景:skill-evo replay-eval 设计文档(docs/design/skill-evo-replay-eval.md,2026-09-01)标注「设计中(待实现)」,但主体实现已落地(evo_replay.py + 44 测试 + CLI 接线 + eval 语料),本任务为**收尾核对 + 缺口修正**,非从零实现。设计稿状态头已过期,须如实同步。

# Target
- 文件/符号:
  - scripts/badcase_runner.py:**第 276 行比对分支**(设计稿 §3.2 required 修正点,现仍为 `if strict_exact and expected_rules:`,未修)
  - scripts/badcase_runner.py:exact_match_failures(被 276 行分支调用,勿动签名)
  - docs/design/skill-evo-replay-eval.md:第 3 行状态头 + §7 验收标准(220 行起,8 条)
  - skills/skill-evo/scripts/evo.py:cmd_evolve replay 链路(376 行起,已接线 --skill/--eval/--dry-run/--budget/--seed,勿重写)
  - skills/skill-evo/scripts/evo_replay.py(329+ 行已实现,勿重写)
  - skills/skill-evo/scripts/tests/test_replay.py(618 行已存在,勿重写)
  - .github/workflows/config-evals-gate.yml(若接 CI 需新 job)
- 非目标:不重写已落地实现;不改 evo_replay.py 的 scorer_registry/reconcile/control_gate 语义;不动 test_replay.py 既有 44 测试断言
- 所有权:scripts/badcase_runner.py = 本 agent 专属;其余文件先读后改
- 引用:docs/design/skill-evo-replay-eval.md(设计稿)、templates/task-brief.md.template(本模板)

# Change
按 plan 顺序实施;偏离同 commit 更新设计稿并记录。

1. **badcase_runner.py:276 strict-empty 修正**(设计稿 §3.2 required):
   - 现状(第 274-284 行):`if strict_exact and expected_rules:` → else 分支对放行型(空 expected)恒 `passed=True`,strict 双向比对形同虚设
   - 改为 `if strict_exact:`——strict 模式下无条件双向比对:expected 空时 unexpected 方向照常计算(actual_rules 非空 → unexpected → FAIL)
   - 回归测试(新建或并入既有 scripts/tests/ 套件,按仓库惯例放 scripts/tests/,不新建目录):伪造放行型 clean case(empty expected)实际检出规则 → strict-exact 必须 FAIL;原放行型 007-clean 全绿保持
   - 注意 badcase_runner.py 现无独立测试文件(scripts/tests/ 下无 badcase 专属测试)——本修正必须补测试防再犯,这是本任务第一条验收的前提

2. **设计稿状态头同步**:第 3 行「设计中(待实现)」→ 已实现,记录落地范围(evo_replay.py/44 测试/CLI 接线/评估集语料 007-clean+008-real/门禁 control_gate/split_eval)与剩余项(本任务修正 + CI 接线 + 带 LLM 端到端验证)

3. **replay --dry-run 接 CI(零 LLM)**:config-evals-gate.yml 增加独立 job(或并入既有 gate job 的 run 块,与主 gate 并行不互锁):
   - 命令:`python3 skills/skill-evo/scripts/evo.py evolve --skill ddl-guard --dry-run`(零 LLM 调用,只打印评估集构成 + baseline F1)
   - 断言:exit 0 + 输出含「评估集:」与「脚本基线(完美执行参照) F1」;评估集 ≥ replay_min_cases(8)
   - 目的:评估集语料退化(坏 expected/目录缺失)在 CI 显形——dry-run 是唯一无 LLM 成本的完整性哨兵

4. **带 LLM 端到端验证(手动/会话级,CI 外)**:`evo.py evolve --skill ddl-guard --budget 16` 一次真实跑通:holdout 分数有值、提案落盘 pending(不自动 apply、不自动 commit)、control_gate 通过(全盘拒绝候选 F1 < baseline)。此步需真实 LLM key,是 Acceptance 第 4 条的验收动作

5. **设计稿 §7 验收矩阵反向核对**:8 条逐一核对测试覆盖,产出「条款 → 测试名」矩阵;缺口补测试,测试代码加 `# spec:<ID>` 标签(§7 各条编号即 ID;否定式条款如「expected 空 + actual 非空必须 FAIL」必须有专门测试)

# Acceptance
- §7 验收 8 条全部勾选,验收 = 条款到测试名反向核对(矩阵附交付),非覆盖率数字
- 变更行覆盖率 >=95%,终局测量(全部语义变更后重跑门禁)
- 真实启动验证:①`python3 scripts/badcase_runner.py --skill ddl-guard --strict-exact` exit 0 且「共 N 个 badcase」「0 失败」(含新增 regression case 后计数不变语义);②`python3 skills/skill-evo/scripts/evo.py evolve --skill ddl-guard --dry-run` exit 0 输出评估集构成;③设计稿状态头更新后 `python3 tools/gauntlet.sh` 全绿(设计稿在 docs/ 触发 doc-freshness 层,须无漂移);④带 LLM budget 16 端到端产物为 pending 提案
- 交付物端到端可运行;禁止 stub/占位/TODO 实现、禁止 fake fallback

# 强制条款(MUST,逐条照办,不得裁剪)
1. 【禁止顺延】禁止以既有架构/所有权/历史原因为由顺延或降级 spec 条款;发现 spec 与现状冲突(如本任务 276 行修正未做、状态头过期),按 spec 修,不装"设计取舍"。违反即失败。(教训:gtsp-wop-gateway 2026-08-28)
2. 【条款完整性】§7 每条验收条款必须有对应测试,测试加 `# spec:<ID>` 标签;否定式条款(放行型 strict 下 unexpected 必 FAIL)必须有专门测试。(教训:D2 digest 无条件必填共存 31 绿测)
3. 【覆盖率闭合】覆盖率达标以终局测量为准:所有语义变更完成后统一重跑并提交门禁结果;中途达标数字不算数。(教训:98.17% -> 97.62% 稀释回退)
4. 【证据纪律】代码/测试/文档声明必须可溯源;未直接观察的结论标 [INFERENCE];禁止编造工具输出。
5. 【验证豁免】本任务跳过 formatter/linter/全量测试(并行防互锁);验证由集成负责人最后统一执行一次。
6. 【工具回退链】先 cbm -> tokensave -> LSP -> grep/glob;大体积输出 headroom_compress;日志只看末尾 200 行;只读文件用片段。
7. 【输出纪律】交付给 diff/修改摘要,不重印完整文件;测试失败只报第一处根因和关键堆栈。
8. 【完成定义】不 yield 未完成工作;阶段边界不停止,同一轮内完成验收与交付。

[备注:PR #120(config-evals-gate)与本任务同批推进;CI 平台已定为 macos-latest——pytest-factory 层跑 .factory 生态硬编码 macOS 专有 shlock,ubuntu 恒红(平台失真),见 PR #120 注释。若本任务触碰 .factory/ 需知此约束。]
