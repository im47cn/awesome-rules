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
  - `a7d52b7` 审查修复——单写者锁过期接管 rm+建新双赢家窗口，改 rename 单赢家协议（PR #53 审查①；合并前自愈不计触发器，ADR-006）
  - `a7d52b7` 审查修复——dispatch TERM/HUP 放锁不收尸孤儿链，shutdown 先收尸再放锁（Python 形态首条，PR #53 审查④；合并前自愈不计触发器，ADR-006）
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
- **决策**：`.factory/regression/daily-regression.sh` 每日 03:00（LaunchAgent `com.im47cn.factory.daily`，Hour=3；2026-08-25 由周频提至日频）串联四层，不短路（triage 输入完整）；第四层 dispatch-liveness 抓调度器两种死法（停摆标记在 / streak 超 26h 未更新=LaunchAgent 断档——slug 回归 4h 静默 + 历史断档 13h 的结构性补丁）；失败自动 `gh issue create`（`[factory-regression]` 前缀，**零标签**——机器 issue 与人写 issue 走同一 triage 入口，不绕过裁决）；幂等（open 查重 → 评论追加，不重复开）；全绿记 `.factory/metrics/daily-regression.jsonl`；`--dry-run` 真跑检查但不开 issue。
- **后果**：自挖掘闭环成立；每次失败消耗一轮 triage 裁决（R4 breaker 保护仍在）；LaunchAgent 已 lint 未 load——加载由人类决定。
- **验证**：dry-run 实跑三层全 PASS（13/13 badcase、gauntlet 全层、doc-freshness 0 漂移）；`plutil -lint` 过。

## ADR-005 · 2026-08-24 · dispatch 进程编排下沉 factory_lib.py

- **背景**：ADR-002 证据类的主体（jobs 表/wait 落空 0d947f60、管道吞码 61c119c2、管道早退 a4d81930、trap 吞错 c749ac5e、锁跨树 39b6b8ec）全部是 bash 进程原语的边角语义，且集中于 dispatch 侧。
- **决策**：dispatch.sh 退为入口 shim（`exec python3 factory_lib.py dispatch`），进程编排（ChainPool 并发槽+收割、mkdir+PID 硬锁、watch 循环、TERM/HUP 放锁）以 Python 重写并入 factory_lib.py；CLI/env/退出码契约逐项等价。bash 形态判断不变：dispatch 仍零 LLM（A3 未破）——下沉消灭的不是「智能在壳」，是 shell 进程原语类缺陷的表达面：Popen 句柄即作业表，jobs 表清点竞态与 grep -m1 SIGPIPE 在 Python 形态下结构性不可表达。
- **现状更新**：dispatch.sh 246→19 行，factory_lib.py 342→752 行，factory-lib.sh 103 不变（合计 691→874）；组件数不变（18）；ADR-002 触发器语义不变——进程管理类缺陷此后按新形态继续记账（Python 侧再发同样计 1 条）。
- **验证**：tests/test_breaker_wiring 三路沙箱（熔断门口/干跑/全轮哨兵计数）+ 新增 tests/test_dispatch.py（时间戳区间重叠测真并发峰值、陈锁/垃圾 pid 接管、slug/priority 纯函数）+ 全套 162 测试全绿；真仓 `--dry-run` 冒烟输出格式与 bash 版逐行一致，干跑退出码修正为 0（bash 尾部 `[ $DRY = 0 ] && echo` 的 rc=1 怪癖，测试注释既已点名）。

---

## ADR-006 · 2026-08-25 · ADR-002 触发器计数口径（合并前自愈不计数）

- **背景**：PR #53 审查轮自愈两条进程管理类缺陷（单写者锁接管双赢家、TERM/HUP 孤儿链），按 ADR-002 纪律记账后，触发器 2「此后再记录 ≥2 条进程管理类缺陷」字面命中。人类裁决（2026-08-25）：不计数。
- **决策**：触发器只计**曾进入 main 的缺陷**（主干上发生过、靠事后修复收口）。合并前审查轮自愈照常记账——证据完整性不折损——但证据行标注「不计触发器」，不参与触发器 2 计数。
- **理由**：触发器 2 的语义是「外壳形态在主干持续产生进程缺陷」；审查轮自愈恰恰是评审机制在工作，属反证据。计入会造成「审查越有效 → 越快触发重写评估」的激励倒挂。
- **后果**：ADR-002 证据清单自此区分两类行：默认计数；标注「不计触发器（ADR-006）」的不计。机器消费（skill-evo）以标注为准。

## ADR-007 · 2026-08-25 · forge 平台适配层（GitHub 单平台 → gh 兼容多平台）【已被 ADR-008 取代】

- **背景**：`.factory` 调用面（issue/pr/label/api/auth ≈9 读 + 9 写）结构性绑定 `gh` CLI 与 GitHub JSON 形状（state.py 消费这些形状）；Codeup（云效）托管的下游仓（gtsp-wop-gateway 等）无 gh 可用，移植被平台锁死。
- **决策**：引入 `.factory/forge`（gh 兼容 argv shim，stdlib Python）：`forge.json` 缺失 → github 后端 `exec gh`（上游零行为变化、零配置）；`backend=codeup` → 云效 REST（`openapi-rdc.aliyuncs.com`，`x-yunxiao-token`），输出同形状 JSON。调用面改动仅二进制名 `gh`→`"${FORGE}"`（feedback-upstream.sh 例外：它指向上游 GitHub，保持 gh）。issue 编号统一字符串（GitHub 数字 / Codeup 工作项序号 KFPT-16 同构；state.py `_linked_issue` 正则放宽 `#([\w][\w-]*)`）。
- **Codeup 事实模型**（无 labels/timeline 的等价物）：issue=projex 工作项（labels 直写）；PR 侧标签/事件=MR 全局评论标记——`--add-label` 发 `[factory:label:add] X` 评论、`--remove-label` 置 resolved（内容保留→轮次计数单调，对齐 GitHub label-add 事件语义）；`reviewDecision`：`TO_BE_MERGED`→APPROVED，人工标记评论 `[factory:changes-requested]`→CHANGES_REQUESTED；`pr diff` 用本地 git（远端分支已推）。未知子命令/标志 fail-closed exit 2。
- **后果**：新增 forge（full 分发）+ forge.json（skip，每仓一份：org/repo/space/workitemType/base_branch）；`test_forge.py` 单测（零网络）+ `tests/` 162 绿；`.factory` 脚本 diff 仅 FORGE 定义块与二进制名替换。已知边界：当前云效令牌 projex 写 403（工作项 labels/评论/创建）——issue 侧状态机落地需令牌补项目管理写权限；Codeup MR 评论写已实测可用。
- **引用**：`.factory/forge`；`.factory/test_forge.py`；README「平台适配层（forge）」。


### ADR-007 补记 · 2026-08-25 · issue 侧标签描述载体与网络韧性

- **标签载体双模**（`forge.json codeup.issue_labels`）：云效 Task 类型字段配置可无 labels 字段（PUT 400 "workitem does not contains field"，非权限）。`native` 直写字段；`description` 走描述尾部 HTML 注释块 `<!-- factory:labels:v1: ... -->`——实测云效富文本完整保留注释、单字段 PUT 不触碰其余字段。读取时标记剥离不进 body，标签从原文解析。gtsp-wop-gateway 现用 description 模式（字段配置后可切回）。
- **握手级重试**：公司网关对快速连续 TLS 握手偶发 RST（SSLEOFError，2026-08-25 实测）。握手失败=请求未发出，全方法重试皆安全（非幂等 POST 不重复执行）；forge.call 内建 3 次退避。

### ADR-007 勘误与补记 · 2026-08-26 · 评论权限放开 + issue create 破案

- **勘误（上节「已知边界」）**：「projex 写 403（工作项 labels/评论/创建）」已过时——令牌权限 2026-08-26 放开后实测：工作项**评论读/写全通**、**标签写（description 模式）全通**。issue 侧状态机链路（triage 落标/回执评论）完整可用。
- **issue create 破案**（此前误判 403/字段不可发现）：根因是 create API 无「计划开始时间」本体字段——它是模板层 SystemCustomField，必经 `customFieldValues {"fieldId":"value"}` **平面对象**（数组形态报 Invalid format）。fieldId 由字段配置接口发现（`GET projects/{spaceId}/workitemTypes/{wit}/fields`，实测 79/80=计划起止、101586=预计工时）；value 形态：date=ISO、float=小数字符串、list=**option id**（非文本）；assignedTo=24-hex 用户 id（配置 `forge.json codeup.assign_user_id`，成员端点不可达）。forge 现按字段配置自动构造默认值，create 全链路实测打通（gtsp-wop-gateway）。
- **空体容错**：云效写操作可返回 200+空 body；`json.load` 裸崩改为按长度守卫返回 `{}`。
- ~~权限矩阵（首测）~~：首测口径（评论写 403）已被上行勘误推翻，勿引用；当前有效矩阵见 forge「Codeup 工作项 OpenAPI 实测知识」（skills/alibabacloud-devops/SKILL.md）——权限随令牌 scope 动态，**以复验为准**。

## ADR-008 · 2026-08-26 · 托管平台抽象层 hosting.py（取代 ADR-007：核心与 GitHub/Codeup 解耦）

- **背景**：链/调度/同步/验证/回归九个脚本 + factory_lib.py 直调 `gh`，GitHub
  schema（reviewDecision/labels[].name/events API）渗入核心逻辑；Codeup 仅作
  git 推送镜像（factory-state/fix-issue 的 REPO_SLUG 双 remote 扫描即为此补丁）。
- **决策**：引入 `.factory/hosting.py` 唯一平台出口——中立 schema
  （issue/pr/label_history：state=open|closed|merged、review=三态、labels=[str]）
  + 双适配器（GitHub=gh CLI 行为保持；Codeup=云效 oapi/v1 org 级端点，
  `x-yunxiao-token`，端点 TLS 失联自动切 openapi-rdc 一次）。state.py 输入
  契约切中立 schema（转移表/语义零变更，9 测试原样通过）；slug 解析自
  factory_lib 迁入 hosting；GH_REPO→FACTORY_HOSTING（默认 github）。
- **Codeup 平台缺口（文档+API 面实证，fail-closed exit 2 绝不静默降级）**：
  (a) issue create 已破案（PR #62 实测：create 本体必填仅 assignedTo/
  spaceId/subject/workitemTypeId；模板必填 SystemCustomField 经
  customFieldValues 平面对象 {"fieldId":"value"} 传，fieldId 从字段配置
  端点发现，value 形态 date=ISO/float=小数字符串/list=option id；
  assignedTo=24-hex 用户 id）——hosting.CodeupAdapter 已实装迁移（env：
  CODEUP_SPACE_ID/WORKITEM_TYPE_ID/ASSIGN_USER_ID）；工作项读/写面五方法
  （view/list/set-labels/comment/get-labels）已实装（#67，2026-08-26 live
  验收：KFPT-18 标签 add→读回→remove→读回空、描述零残留；双键寻址
  serialNumber/id；标签载体 CODEUP_ISSUE_LABELS=native|description——
  Task 类型常无 labels 字段，description 尾部注释块为等价载体；评论端点
  仅认 24-hex id；search category 必填）；(b) MR 类标仅
  LinkMergeRequestLabel、无 Unlink——needs-fix→approved 全部换标转移
  不可表达；(c) 无标签事件时间线——轮次计数（MAX_FIX_ROUNDS）不可派生。
  故 Codeup 上链状态机的 issue 面（a）已解锁；剩余缺口集中在 MR 面
  (b)(c)（#66 评论标记模型承载）；可用面 = MR 读写/评论（comment_type
  +resolved 必填，skills 实测坑位已锁定进适配器）/合并/类标 Link + 工作项
  全套（create/view/list/labels/comment）。
- **验证边界（live 基线已锁定，2026-08-26 更新）**：GitHub 侧行为保持由
  测试（含 hosting 契约：gh 命令构造/原子换标/归一化/CLI 缺口）+ 沙箱
  端到端冒烟覆盖；**Codeup 侧 MR 面已在 gtsp-wop-gateway live 验证**
  （auth/list/view/comment/类标 Link 全通）。live 修正了五处文档推导偏差：
  ① MR 集合是**组织级端点**（无 /repositories 段 + projectIds query，
  仓库级集合 404），分页参数 perPage（非 pageSize）；② 组织级端点返回
  **裸 JSON 数组**（success 包裹仅 dict 响应有）；③ MR 详情**无 labels
  字段**，类标须专用端点读回；④ LinkMergeRequestLabel body 键是
  **labelIdList**（labelIds/labels/labelId 均拒）；⑤ label create body
  形态未破案（多形态探针均拒）——类标创建走云效界面人工路径，
  ensure 的 400 兜底语义保留。issue create 字段形态来自 PR #62 真实
  创建实测，hosting 迁移已对齐。
- **MR close 与 issue create 编号（live 2026-08-26 第二批，gtsp-wop-gateway MR#7/KFPT-21 实测）**：
  ① close 唯一生效形态 = `POST /changeRequests/{n}/close` 空 body；**PUT 详情端点带
  `{"state":"closed"}` 返回 `{"result":true}` 但状态不变（假阳性）**——多形态探针中仅
  POST /close 改变状态。hosting 两侧补 `pr_close`（GitHub=gh pr close 直通）。
  ② issue create 响应只含 24-hex id，无 serialNumber——人类可读编号（KFPT-N）须回查
  详情；回查失败降级 id + stderr 告警。mock 契约同步对齐（create_resp 仅 id、
  detail_resp 承载 serialNumber）。
- **后果**：MISSION 铁律 4「纯 bash + gh」措辞需人类修宪为「纯 bash/Python +
  托管适配层（零 LLM 不变）」；组件数 18→19（ADR-002 触发器 3 余量充足）；
  核心脚本自此禁直调 gh（doc-freshness R1 已盯 README 登记，新增写点必须走
  hosting 出口，租约围栏/factory-lib 收口不变量原样保留）。

## ADR-009 · 2026-08-27 · 拆分前置：本地化全量数据化 + 引擎单点 + portability 门

**背景**：工厂拆独立仓库的评估结论（S2 会话）——现在不拆（实例 2 < 3 阈值，
设计 §2.2 重估条件），但先消灭全部结构性耦合，使拆分当天只剩 git mv + 锚点锁。
审计发现四类残留：门命令三处硬编码（fix-issue/validate-pr/mutations）、
prompts 七文件含宿主专名、DISTRIBUTION 缺件（omp-isolated.yml、db/schema.sql
不在任何面）、local 面三项未清零（feedback-upstream/tests/test_state）、
omp CLI 七处直调无单点。

**决策**：
1. **门命令数据化**：`factory-local.json` 增 `final_gate_cmd`；
   `factory_lib.py final-gate` 子命令（fail-closed）为唯一取值口，
   fix-issue/validate-pr `read -ra` 拆词执行，mutations `FINAL_GATE` 拆词
   （首词解析为仓库根绝对路径）。
2. **prompts 参数化**：增 `repo_identity/reading_scopes/review_basis/
   pr_review_skills`；`repo-vars` 子命令渲染「仓库参数」段，由 run_node /
   pr-review / feedback-adapt 拼装时注入；triage/holdout 物理隔离不注入。
   prompts 正文零宿主专名（triage 判据 a 改为指向内联 MISSION 原文，
   真相源唯一化是顺带修正）。
3. **上游指针数据化**：`upstream_repo/upstream_path/feedback_branch_prefix`；
   feedback-upstream.sh 默认值改读配置（env 显式覆盖保留，镜像拓扑逃生口），
   PR 文案/分支前缀用 `SELF_ID`/`FB_PREFIX`，升 full。
4. **引擎单点**：`factory-lib.sh omp_node()`（omp CLI 唯一执行点，设计 §4
   runNode 的 bash 形态）；七处直调全部收口，dry-run 文案同步。
5. **分发补缺与归零**：full += omp-isolated.yml、db/schema.sql、
   feedback-upstream.sh、tests/（用例随源走；tests 内仓名是夹具样例数据，
   合法）；local = {}。test_state.py 随源入 tests/（去自带 path hack）。
6. **防回归门**：gauntlet 新层 `factory-portability`（checker
   tools/check_factory_portability.py，负控制 NC13）三规则——P1 full 面+
   prompts 零宿主专名（awesome-rules/im47cn/gtsp-/fss-/etf-radar/steering//
   scripts/run_tests；刻意不含 skills/——双布局识别是通用机制词）；P2
   `omp -p` 仅 factory-lib.sh；P3 full 面 .py 禁 sys.path.insert（tests/
   豁免：conftest 注入与跨目录被测 import 属测试布局语义）。
   `factory-local-validity` 层扩 final-gate/repo-vars 渲染断言。
7. **历史考证中性化**：注释中 etf-radar#NN → 源仓#NN（编号保留可溯）、
   hosting 实测项目名泛化；feedback.py record 上游 repo 改读配置。

**验收**：local 面归零；`factory-portability` P1/P2/P3 干净；omp 单点；
factory-local.json 变更后 mutations 重证全绿（指纹绑定强制）。

**边界**：tests/ 内夹具专名（slug 解析、作者名）不属 P1 管辖；M2 同步流
设计未动；拆分本身（独立仓 + 版本 tag + guard.self_check 跨仓核对）留待
第 3 个消费者出现，按设计 §2.2 纪律执行。

### ADR-009 附记 · 2026-08-27 · R2 审查回流（ralph 轮 1）

reviewer 审出 3 BLOCKER + 4 MAJOR + 4 MINOR，处置：
- **B1** feedback-upstream.sh 补 `source factory-lib.sh`（omp_node 此前未定义，
  反哺真跑必炸 rc=127 被 `|| NODE_RC=$?` 吞）——已修并单元验证（omp 真进程）。
- **B2** upstream_path `~/` 字面 tilde 不展开（git -C 回归）——消费端
  `${VAR/#\~/$HOME}` 前缀展开，配置保持 `~/` 人类形态。已验证。
- **B3** validate-pr `SKILLS_ARG=""` 初始化被误删（set -u 下首触守卫技能即
  unbound 崩溃）——恢复。已验证。
- **M4** mutations FINAL_GATE 首词不再绝对化（PATH 型命令 `uv run pytest`
  变 `<repo>/uv` rc=127）——词保持原样，cwd=REPO_ROOT 解析。
- **M5** sync-from-upstream 目录项（tests/）静默跳过 = 漂移盲区——清单生成
  时 `ls-tree -r` 递归展开为文件项。fixture 端到端：同版 0/漂移 1/apply
  覆盖/追平 0。
- **M6** P1 禁词放宽 bare `run_tests`（抓出 feedback-upstream PR 文案真残留，
  与实际门禁 gauntlet 不符一并修正）；fix-issue/validate-pr 注释与 dry-run
  文案同步中性化。
- **M7** prompts/ 由 skip 升 **full**——中性化后即引擎无关资产，上游 prompt
  修复必须可达下游；README 三态描述同步。
- **M8** final_gate_cmd 禁含引号（read -ra 与 shlex 两拆词器一致性），
  fail-closed。
- **M9** triage.md 判据编号 a/b/c → 1/2/3（对齐 MISSION 数字编号）。
- **M10** repo_vars_text 的 pr_review_skills：键存在即严格校验（与 local-list
  同规），键缺失 = 无守卫面仓合法省略；删除死 try/except。
- **遗留（M11 及 MINOR）**：feedback.py record 独立读 factory-local.json
  （纯函数层刻意不 import factory_lib；KeyError→非零=fail-closed 语义已达，
  记录不改）；feedback-upstream 在上游仓运行时的语义错位（f6835d15 下游
  SHA 不在上游对象库，main 预存，工具设计为下游运行）。

### ADR-009 附记二 · 2026-08-27 · R2 复审收口

复审判定 8✓/2部分,新发现 N1-N9,处置：
- **N1(MAJOR)** upstream-lock.json 夹具运行时锚点(bad object)误入库 → 移除
  (skip 面运行时产物,上游自身无上游)。
- **N4** state.py 污染恢复丢执行位 → chmod +x(否则经 sync 的 chmod 语义
  传播到全部下游)。
- **N3** 编号体系:M9 只改 prompt 流程文字造成与回执消费链(receipt 正则
  ^判据([abc])/guidance 键 a/b/c/夹具)割裂 → 回退字母并显式声明映射
  (a/b/c ↔ MISSION 1/2/3,输出契约=字母)。教训:跨文件契约改动必须
  全链同步,单点"对齐"制造新割裂。
- **N2** README 三态描述与 DISTRIBUTION 同步(prompts 入 full 枚举)。
- **N5/N6/N8** 陈旧注释、目录消失零告警、run.py 引号拒绝补齐。
- **N7** ~user 形态误展开:fail-closed 兜底,配置约定 ~/ 形态,记录不改。
- **N9** evidence-stamp.json 被跟踪 → mutation 重证后须提交 stamp,既有
  设计(证据可审计),非缺陷。

### ADR-009 附记三 · 2026-08-27 · Sourcery R3 三评论处置

Sourcery 三条审查评论全部成立,处置:
- **S1(bug)** mutations run_gate 硬编码 `bash` 前缀破坏 PATH 型
  final_gate_cmd(`uv run pytest` 变 `bash uv ...`,首词被当脚本文件名)
  → 改直执 `FINAL_GATE`,与 shell 侧 fix-issue/validate-pr 的
  `"${GATE_ARGS[@]}"` 同构——两侧消费方执行形态统一(单测锁行为:
  monkeypatch Popen 断言 argv 无 bash 前缀)。killpg 审计注释随
  「bash 直子」措辞一并校正(直子=门命令进程,进程组语义不变)。
- **S2(bug)** `_final_gate_words` 先 `str()` 再校验:数字/列表等非字符串
  值 py 侧放行、shell 侧(factory_lib._local_str)拒绝——两消费方行为
  割裂 → 加 `isinstance(raw_val, str)` 前置校验,参数化负例锁四类
  JSON 类型;函数签名增可选 cfg_path(可测性,默认调用方不变)。
- **S3(bypass)** portability P2 字面子串 `omp -p` 可被 `omp   -p`/
  `omp \↵-p` 绕过 → 词边界正则 `\bomp[\s\\]+-p\b` + 全文 finditer
  (续行跨行,逐行扫描结构性漏报);P3 `sys . path . insert`(合法
  Python 空白点号变体)同根因一并正则化。NC13 负控制扩 d/e/f 三
  变体(多空格/续行/点号空白)。
- 附带:run_gate 安全审计注释更新——tests 分支命令词源自
  factory-local.json(治理周界内,禁引号+shlex 拆词后纯 argv 元素),
  闭集语义随直执重述。mutations 周界内改动 → kill rate 重证。

### ADR-009 附记四 · 2026-08-27 · pre-push 钩子 GIT_* 泄漏夹具污染事故

推送实测:lefthook pre-push 的 git 钩子环境向测试子进程泄漏 GIT_DIR
等仓库发现变量,`git -C <tmp夹具仓>` 的目标被环境变量优先级覆盖——
TestStampRoundtrip 的夹具 init/commit 落进真实仓 HEAD(树仅含 2 个
夹具文件),plugin_lock 随 HEAD 树缺文件连锁失败,推送被误拦。
处置(环境密闭):
- tests/gitenv.py git_env():剥除 10 个仓库发现类变量;三处消费
  (test_factory_local._git / test_breaker_wiring._sandbox /
  test-lease-sql.sh)接入。
- mutations/run.py perimeter_blob/tracked_and_dirty 同根因加固
  (测试 monkeypatch REPO_ROOT 后同样可被劫持),模块级 _GIT_ENV。
- 回归锁 TestGitEnvSealing:受害者仓复现泄漏机制(无密闭 → 提交落
  受害者仓;密闭 → -C 语义恢复)。
教训:与附记二夹具污染事故同类——tmp git 仓夹具必须视为不可信环境
边界,git 子进程一律显式环境密闭,不依赖 ambient environ。

## ADR-010 · 2026-08-27 · 测试 git 密封制度化（机械化门）+ final gate 双实现漂移锁

**背景**：同一根因（hook 注入 GIT_* 劫持仓库发现）两次事故（2026-08-22
真仓 389 文件删除；2026-08-27 PR #71 夹具提交落真仓 HEAD）。既有处置是
逐套件 conftest 打补丁 + steering §测试密封性规范 + 手工登记表——
规范靠人记住、登记靠人补行，PR #71 漏 .factory/tests 证明手工模式必然
漂移。另：pre-push 推送实测 exit=141（SIGPIPE）——hook 运行 ~45s 期间
git 已打开的 ssh.github.com:443 连接被中间设备空闲回收，钩子后复用死
连接即死；修复 = 仓本地 core.sshCommand keepalive（ServerAliveInterval=15,
CountMax=4），dry-run 带 hook 实测 141→0。

**决策**：
1. **机械化门 tools/check_git_sealing.py**（gauntlet 层 git-sealing，
   负控制 NC14）：R1 spawn git 的 test_*.py 所在套件 conftest 必须
   import 期密封；R2 调 git 的 test*.sh 必须 top-level unset（标记
   行首锚定，printf/heredoc 内嵌字符串不构成密封——NC14 自测实测的
   假满足形态）；R3 scripts/tests/test_hermetic_git.py GIT_FIXTURE_CASES
   覆盖全部 R1 检出套件（登记表所在套件豁免自跑：自登记 = 参数化
   自我 spawn 无限嵌套，实测 300s 超时）。规范事实源仍是 steering/
   testing-standards.md §测试密封性,门是机械执行者。
2. **密封补齐**：.factory/tests 与 skills/skill-evo conftest 接入
   import 期剥离；test-lease-sql.sh / test_gauntlet_checks.sh 顶层
   unset；登记表补 .factory 条目（TestStampRoundtrip 注入实跑）。
3. **final gate 双实现漂移锁（保留 python 实现的决策）**：shell 侧
   （final-gate 输出 + read -ra）与 python 侧（_final_gate_words +
   shlex）继续并存，一致性机械化：TestFinalGateDriftLock 锁三件事——
   同配置双侧拆词逐词相等（含 PATH 型）；活配置单一事实源
   （FINAL_GATE == final_gate_cmd().split()）；引号拒绝双侧互为镜像。
   PR #71 Sourcery S1 的 bash 前缀漂移即双实现无锁的产物。
4. **SIGPIPE 修复不入库**：core.sshCommand 是仓本地配置（git config
   --local，worktree 共享），非周界文件——不随 PR 走；本条目即交接
   记录（其他 clone 遇 141 同方处置）。

**验证**：check_git_sealing 真仓 R1/R2/R3 干净（6 套件全登记）；NC14
三态（R1+R3 拦 / R2 拦 / 中性零误报）；hermetic 5 案例注入实跑全绿；
drift-lock 5 例；带 hook push dry-run exit=0。

### ADR-010 附记 · 2026-08-27 · 反斜杠分叉收口

审查发现漂移锁遗留真实分歧点：反斜杠。`read -r -a` 字面（`a\ b` →
2 词 `a\` + `b`）vs `shlex.split` POSIX 转义（→ 1 词 `a b`）——词数
即不同，且旧校验（仅禁引号）双侧都放行，「过校验 ⇒ 两侧拆词一致」
不变量有洞。处置：两侧校验同禁反斜杠（fail-closed，与禁引号并列：
final_gate_cmd 与 _final_gate_words 互为镜像），TestFinalGateDriftLock
参数化三形态（`a\ b` 转义词 / `x\y` 词内 / `tail\` 尾随）钉死双侧同拒。
分叉点至此闭集：引号 + 反斜杠之外，两拆词器都只按空白切词、其余字符
全字面（shlex.split 的 comments 默认 False，`#` 亦字面）——纯空白分隔
下逐词相等，不变量闭环。
