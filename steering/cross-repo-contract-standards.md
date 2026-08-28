---
title: 跨仓契约兼容性规范
scenario: 变更会被其他仓库依赖的 API 模块（api jar / Feign 契约 / DTO）、配置跨仓 CI 门禁
inclusion: always
---

# 跨仓契约兼容性规范

## 背景

多仓协作下，上游仓对 API 契约模块（供下游仓以 Maven 依赖消费的 jar）的破坏性变更，
若仅靠 `1.0-SNAPSHOT` 依赖隐式传递，下游会在**联调或下一次构建时**才断裂，且无迁移提示。
典型案例：service 仓将 `appSecret` 从 `AppSecretDTO` 拆除，gateway 仓 `LegacyAuthFilter`
仍在调用 `secret.getAppSecret()`，SNAPSHOT 每日自动更新后下游构建即断。

## 核心原则

1. **门禁在 CI，不在本地 hook**：本地 commit hook 可绕过（`--no-verify`）、且开发者机器
   未必有对端仓 clone，只承担"提前提示"职责；强制拦截由 CI 门禁承担。
2. **机器发现优先于人工登记**：契约清单（哪些类/字段被下游使用）不做人工维护，
   用工具自动发现 public API 破坏（japicmp）+ 真实编译验证（下游触发）。
3. **破坏性变更必须显式**：无法兼容时，走豁免声明（可审计），不允许静默合入。

## 跨仓契约模块的认定
- 认定契约模块时只解析 pom 的 `<description>` 标签内容，禁止全文 grep「契约」字样：聚合父 pom（packaging=pom）的 description 与各模块注释中出现的「契约」表述均会造成误命中（两类误报源均实测复现过）

同时满足以下条件的 Maven 模块即为本规范约束的**跨仓契约模块**：

- 模块 pom 的 `<description>` 含"契约"字样（如 `gtsp-wop-service-api-gateway`：
  "开放平台-网关数据接口契约(网关各 Filter 配置数据...)"）；
- 非聚合父模块（description 含"聚合"/"父模块"的不算——契约的载体是可被依赖的具体 jar 模块）；
- 被其他仓库以 Maven 依赖消费（不论 SNAPSHOT 还是 release）。

新设契约模块时，pom description 必须含"契约"二字，保证 CI 路径检测规则可自动识别。

## 门禁机制（B：japicmp + C：下游编译触发）

### B：japicmp 门禁（上游仓）

契约模块 pom 挂 `japicmp-maven-plugin`（模板见
`skills/contract-guard/templates/japicmp-pom-snippet.xml`）：

- 阶段 `verify`，`breakBuildOnBinaryIncompatibleModifications=true`：
  删除/改签名 public 成员即构建红；
- `oldVersion` 以 `file.path` 指向重建的 baseline jar（见下），本地默认跳过
  （`japicmp.skip=true`），不拖慢开发构建。

**baseline 策略（sha 重建方案）**：

- CI 以制品库变量记录**上次绿构建的 commit sha**——sha 随 git 永存，不依赖私服
  SNAPSHOT 保留策略，换设备/清 m2 均可重建（消灭"外部依赖假设 1"）；
- 门禁运行前，CI/预检脚本用 `git worktree add <tmp> <sha>` + `mvn install -pl 契约模块
  -DskipTests` 重建契约 jar 到各契约模块 `.japicmp-baseline/<artifactId>-baseline.jar`
  （gitignore，不受 `clean` 影响）；重建脚本见 `skills/contract-guard/templates/japicmp-pom-snippet.xml`；
- 门禁命令统一为 `mvn verify -pl <契约模块> -Djapicmp.skip=false`，无需注入版本号；
- **红线：sha 必须是"上次绿构建"**，更新动作在 job 全绿之后，记了红 sha 会永久洗白
  区间内已放过的破坏；
- 可靠性依据：japicmp 只比 API 签名（重建的时间戳/环境差异无关）；契约模块依赖全
  `provided` + `ignoreMissingClasses=true`，依赖 SNAPSHOT 漂移不渗入对比。若未来契约模块
  引入 compile 期 SNAPSHOT 依赖，需重新评估；
- **三个实测坑**（踩中任一即门禁静默恒绿，详见模板注释）：①pom `<properties>` 给
  baseline 属性设默认值会遮蔽 CLI `-D` 注入，pom 里只能放 `japicmp.skip`；②oldVersion
  禁用 GAV 形式——同坐标在多模块构建内被 aether reactor 命中当前模块自身产物（自比自），
  必须 `file.path` 直指重建 jar；③baseline jar 缺失时 japicmp 直接报错（fail-closed），
  见到 "path does not point to an existing file" 即先跑重建脚本，不要绕过。

### C：下游编译触发（跨仓）

```
上游仓流水线（MR / 合并）
  ├─ job1: 变更路径检测   git diff --name-only | grep -E '^<契约模块路径>'
  ├─ job2: 重建 baseline + japicmp 门禁 + 自检 + mvn deploy（仅契约模块，-U 刷私服 SNAPSHOT）
  │          └─ 见 B 节 baseline 策略与「门禁自检」
  └─ job3: 触发下游仓「契约编译」流水线（云效 Flow 流水线触发器）
             └─ mvn -U clean test-compile   # -U 强拉最新 SNAPSHOT，字段被拆当场红
```

- 下游"契约编译"是独立最小流水线：只编译 + 契约相关测试，分钟级；
- 失败必须回写上游 MR（commit status / 评论），仅下游流水线红而上游无感知视为门禁失效；
- **分支映射进配置**：上下游分支名不保证同名（如 `feature/20260812-open_platform_v1`
  ↔ `feature_20260808_init`），映射表由流水线变量维护，禁止硬编码同名假设。

## 变更纪律

| 场景 | 要求 |
| --- | --- |
| 兼容性变更（新增字段/方法） | 正常合入，japicmp 绿 |
| 破坏性变更（删除/改签名 public 成员） | japicmp `<excludes>` 显式豁免 + MR 描述注明受影响下游 + 迁移说明 |
| 契约对应的存储结构变更（如表拆分） | 发布顺序强制：先建表 → 迁数据 → 下游升级切换新接口 → 清理旧字段 |
| 新增跨仓契约模块 | pom description 含"契约"；登记进下游触发配置 |
- 契约变更的断裂可能被 SNAPSHOT 缓存静默掩盖：下游拉到新 SNAPSHOT 则编译失败，沿用本地 m2 旧缓存则编译通过但运行时反序列化错位、功能整体失效（实测：上游单方把契约返回类型 ResultMode 改为 ResponseMessage，下游网关零同步）。因此不得以「下游暂未编译报错」认定契约兼容，契约变更必须同批联动下游仓库或被门禁拦截。

豁免记录每季度复盘一次：豁免后下游是否完成迁移、豁免是否可回收。

## 本地预检的边界（防漏报）

本地跑门禁的漏报源不是 jar 内容（sha 重建产物不可变），而是 **baseline sha 本身**：
凭记忆/本地残留的旧 sha 跑门禁，会漏掉区间内的破坏。因此：

1. **本地跑门禁只具预检性质**，CI 是唯一权威裁决；本地绿不代表 CI 绿；
2. baseline sha 不靠记忆/猜测——从流水线制品库变量（或流水线页面）读取；
3. 预检流程与 CI 完全一致：同一份重建脚本（worktree + install）→ `mvn verify
   -Djapicmp.skip=false`，不引入第二套做法；
4. baseline jar 缺失时 japicmp 直接报错（fail-closed，实测验证），不会静默漏报——
   见到 "path does not point to an existing file" 即先跑重建脚本，不要绕过。

## 门禁自检【强制】

假门禁（看起来在跑、实际恒绿）比没有门禁更危险——三个实测坑（properties 遮蔽 CLI 注入、
reactor 自比自、配置形式错误）全部表现为**静默恒绿**而非报错。因此：

1. **对比对象断言**（每次契约门禁运行顺带执行，零额外成本）：门禁绿后检查
   `target/japicmp/*.diff` 首行，`Comparing source compatibility of <A> against <B>`
   中 **A ≠ B**（A 应为当前构建产物、B 应为 m2 的 baseline jar）。A == B 即自比自，
   门禁已失效，流水线按失败处理。
2. **接入验收**（一次性）：用一份已知含破坏性变更的 baseline（相对当前代码有 public API
   移除的历史版本）跑门禁，断言必须 `BUILD FAILURE` 且错误信息含 `METHOD_REMOVED`/
   `incompatible` 等破坏标志。未做过此验收的门禁视为未接入。
3. **环境变更重验**：升级 Maven/japicmp 版本或调整仓库结构后，重跑第 2 条验收。

## 本地 hook 的定位

commit hook 仅做防呆提示（检测到契约模块 diff 时打印提醒"走 CI 门禁 + 通知下游"），
不承担拦截职责。提示脚本见 `skills/contract-guard/scripts/check-contract.sh`。

## 外部依赖假设（接入前须确认）

- SNAPSHOT 版本的契约 jar 会无预警自动拉取新快照：上游破坏性改名（仅类名变、字段不变）可在下游零变更时突然打断编译。归因路径：对报「找不到符号」的类，在本地仓库并存的两个快照 jar 中对比类清单（unzip -l），先确认是上游改名而非本地笔误，再决定修复面（通常为纯改名对齐）
- 下游编译基线应感知快照漂移：本地构建突然失败且本仓无变更时，第一怀疑对象是 SNAPSHOT 依赖拉新，而非本地环境损坏
- SHA 重建 baseline 不受依赖快照漂移影响存在前提：契约模块依赖须全为 `provided`（不进 jar）且 japicmp 开启 `ignoreMissingClasses=true`；一旦契约模块引入 compile 期 SNAPSHOT 依赖，重建产物会渗入依赖漂移，须重新评估该方案可靠性

1. ~~云效私服保留历史 SNAPSHOT~~——已由 sha 重建方案消灭（baseline 只依赖 git）；
2. 云效 Flow 允许组织内跨仓流水线触发（需组织级权限配置）；
3. CI runner 可访问仓库完整历史（`git fetch` 得到任意历史 sha，用于 worktree 重建）。
