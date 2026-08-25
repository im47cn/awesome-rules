# .factory 决策记录（decisions.md）

> 用途：设计文档 §2.3——本文件喂给 skills/skill-evo/，完成「流程数据 → 规则进化」闭环。
> 纪律：ADR 风格，每条 ≤30 行；ADR-002 生效后，进程管理类缺陷修复必须在证据清单追加一行。

---

## ADR-001 · 2026-08-24 · 租约仲裁层引入（单机锁 → 多写者）

- **背景**：S2 派发形态假设单实例，互斥靠本地锁（`locks/dispatcher`）；多写者（多机/多租户）下本地锁互不可见，且 GitHub 换标签是读-改-写整集替换、非 CAS，claim（accepted→in-progress）存在跨机竞态窗口。
- **决策**：引入 Postgres 线性化仲裁层——claim / heartbeat / release / fence 全部服务端原子，epoch 每次易主 +1（fencing token）；链副作用经出口围栏（`lease_guard`）在发送前校验 epoch，被夺/吊销的诈尸链在出口被拒。同机保留 dispatcher 锁；锁标签只是租约的投影。
- **后果**：新增外部依赖 Supabase/PG（`SUPABASE_DB` 必设；未设/不可达 fail-closed exit 4，绝不降级裸跑——降级等于重开多写者竞态）；单实例假设退役，dispatch / M2 确定性 PR 流可多机并行。
- **引用**：`.factory/README.md`「租约仲裁」节；`.factory/db/schema.sql`；设计文档 §2.1 修正 1、§7 落地记录 1。

## ADR-002 · 2026-08-24 · A3 维护成本记账（核心）

- **背景**：公理 A3（可靠性反比于外壳复杂度）推断「bash 零 LLM 外壳 = 低复杂度」，但 git 历史显示进程管理类缺陷在 `.factory/` 持续聚集。A3 的隐含前提（外壳简单 ⇒ 缺陷少）须用数据复核，防情绪化推翻、也防情绪化坚守。
- **证据**（均经 `git log --oneline -- .factory/` 核实）：
  - `8bb356fa` killpg 断言与杀组容忍 macOS 僵尸窗口 EPERM
  - `ca312ce4` 门超时改杀整个进程组——防孤儿污染还原窗口
  - `0d947f60` 管道子shell后台链不进job表致wait落空，改主shell for 迭代
  - `a4d81930` REPO_SLUG 管道去 grep -m1 早退形态
  - `61c119c2` write_ledger 管道吞码 | true → || true——pipefail (#70)
  - `c749ac5e` 节点函数裸调用根治 set-e 豁免面 + trap pipefail 吞错假象
  - `39b6b8ec` 硬锁挂主工作树——worktree 隔离后跨树互斥
  - `8dc079d0` 三链并发事故修复——D1手动互斥/D2链禁推main/D4队列跳过在跑issue
  - `b01c6eae` 审查修复——配额串行化/围栏全量覆盖/注入面收口
  - `a7d52b7` 审查修复——单写者锁过期接管 rm+建新双赢家窗口，改 rename 单赢家协议（PR #53 审查①）
  - `a7d52b7` 审查修复——dispatch TERM/HUP 放锁不收尸孤儿链，shutdown 先收尸再放锁（Python 形态首条，PR #53 审查④）
- **现状量化**（2026-08-24 实测）：README 组件表 18 项；dispatch.sh 246 行 + factory-lib.sh 103 行 + factory_lib.py 342 行 = **691 行**。
- **决策**：维持 bash 形态——A3 仍然成立：智能在资产（`.factory/prompts/*.md`）不在外壳，dispatcher 零 LLM 未破；缺陷模式集中于 bash 进程原语（管道/信号/作业表/锁）的边角语义，属可记账的外壳维护成本，非「智能漏进外壳」。缺陷记账本就此文件化。
- **重估触发器**（写死；命中任一即重开 Archon 评估，届时设计 §4 适配层是唯一改动点）：
  1. 设计文档 §2.2 原条件：≥3 个工厂实例需统一编排，或出现跨仓工作流编排需求；
  2. 本文件此后再记录 ≥2 条进程管理类缺陷；
  3. `.factory/` 组件数（README 组件表行数）> 35。
- **后果**：每次进程管理类缺陷修复，须在上方证据清单追加一行（哈希 + 一行摘要）——守门成本从「重写冲动」降为「一行记账」；skill-evo 直接消费本文件。

## ADR-003 · 2026-08-24 · SUPABASE_DB 未设降级单写者（双态铁律）

- **背景**：ADR-001 定为 `SUPABASE_DB` 必设、未设即 fail-closed；下游复制工厂在无 PG 环境下链直接不可跑，最小形态被外部依赖堵死。人类决策（2026-08-24）：未设是显式选择单写者形态，应降级而非阻断。
- **决策**：双态——未设 `SUPABASE_DB` = 单写者降级：claim / heartbeat / release / fence 全走本地锁（主树 `.factory/locks/leases/`，git-common-dir 锚定，worktree 共享），O_EXCL 判代、过期 = mtime+租期、过期可夺 epoch+1、fence 校验 machine-id+epoch、过期不复活；`<key>.epoch` 计数器使 fencing token 跨 release 单调不回零（对齐 PG 行常驻）。已设但 psql 不可达 = 配置错误，**维持 fail-closed**——把配置错误伪装成单写者形态等于重开多写者竞态。
- **后果**：下游无 PG 可跑；同机持有中二次 claim 拒（严于 PG 同机续约——本地锁互斥对象就是同机进程，同机并发双链正是要防的）。代价：跨机互斥不存在（本地锁互不可见，每条降级路径 stderr 告警是唯一防线）、无配额。出口围栏（`lease_guard`）经 `LEASE_KEY/LEASE_EPOCH` 契约在降级态继续生效。ADR-001「必设」表述由本条修正，ADR 不可变故不就地改写。
- **引用**：`.factory/factory-lease.sh`「单写者降级」节；`.factory/README.md`「单写者降级」；`tests/test-lease-sql.sh` 单写者用例组（PASS=14）。

## ADR-004 · 2026-08-24 · 自挖掘周回归闭环（借鉴 dark-factory comprehensive-test）

- **背景**：仓库已有三层门（badcase `--strict-exact` / gauntlet / doc-freshness）但无定时串联与失败自动流转——bug 靠人发现，与「工厂找自己的 bug 排队给自己修」差最后一环。
- **决策**：`.factory/regression/weekly-regression.sh` 每周日 03:00（LaunchAgent `com.im47cn.factory.weekly`，Weekday=0——launchd 语义 0=周日）串联三层，不短路（triage 输入完整）；失败自动 `gh issue create`（`[factory-regression]` 前缀，**零标签**——机器 issue 与人写 issue 走同一 triage 入口，不绕过裁决）；幂等（open 查重 → 评论追加，不重复开）；全绿记 `.factory/metrics/weekly-regression.jsonl`；`--dry-run` 真跑检查但不开 issue。
- **后果**：自挖掘闭环成立；每次失败消耗一轮 triage 裁决（R4 breaker 保护仍在）；LaunchAgent 已 lint 未 load——加载由人类决定。
- **验证**：dry-run 实跑三层全 PASS（13/13 badcase、gauntlet 全层、doc-freshness 0 漂移）；`plutil -lint` 过。

## ADR-005 · 2026-08-24 · dispatch 进程编排下沉 factory_lib.py

- **背景**：ADR-002 证据类的主体（jobs 表/wait 落空 0d947f60、管道吞码 61c119c2、管道早退 a4d81930、trap 吞错 c749ac5e、锁跨树 39b6b8ec）全部是 bash 进程原语的边角语义，且集中于 dispatch 侧。
- **决策**：dispatch.sh 退为入口 shim（`exec python3 factory_lib.py dispatch`），进程编排（ChainPool 并发槽+收割、mkdir+PID 硬锁、watch 循环、TERM/HUP 放锁）以 Python 重写并入 factory_lib.py；CLI/env/退出码契约逐项等价。bash 形态判断不变：dispatch 仍零 LLM（A3 未破）——下沉消灭的不是「智能在壳」，是 shell 进程原语类缺陷的表达面：Popen 句柄即作业表，jobs 表清点竞态与 grep -m1 SIGPIPE 在 Python 形态下结构性不可表达。
- **现状更新**：dispatch.sh 246→19 行，factory_lib.py 342→752 行，factory-lib.sh 103 不变（合计 691→874）；组件数不变（18）；ADR-002 触发器语义不变——进程管理类缺陷此后按新形态继续记账（Python 侧再发同样计 1 条）。
- **验证**：tests/test_breaker_wiring 三路沙箱（熔断门口/干跑/全轮哨兵计数）+ 新增 tests/test_dispatch.py（时间戳区间重叠测真并发峰值、陈锁/垃圾 pid 接管、slug/priority 纯函数）+ 全套 162 测试全绿；真仓 `--dry-run` 冒烟输出格式与 bash 版逐行一致，干跑退出码修正为 0（bash 尾部 `[ $DRY = 0 ] && echo` 的 rc=1 怪癖，测试注释既已点名）。
