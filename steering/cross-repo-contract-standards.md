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
- `oldVersion` 由 CI 注入 baseline（见下），本地无 baseline 时默认跳过
  （`japicmp.skip=true`），不拖慢开发构建。

**baseline 策略**（SNAPSHOT 无"上一个 release"可对比）：

- CI 以制品库变量（或 `.contract-baseline` 文件）记录**上次绿构建的 SNAPSHOT
  timestamp 版本**（如 `1.0-20260819.071525-7`）；
  优先制品库变量，避免回写仓库污染历史；
- 构建绿后用本次 timestamp 更新 baseline；
- 运行时注入：`mvn verify -Djapicmp.skip=false -Dcontract.baseline.version=$(baseline)`；
- **两个实测坑**（踩中任一即门禁静默恒绿，详见模板注释）：①pom `<properties>` 定义
  baseline 默认值会遮蔽 CLI `-D` 注入，pom 里只能放 `japicmp.skip` 默认值；②oldVersion
  禁用 GAV 形式——同坐标在多模块构建内被 aether reactor 命中当前模块自身产物（自比自），
  必须用 `file.path` 直指 m2 的 baseline timestamp jar，且 CI 先 `dependency:get` 拉取。

### C：下游编译触发（跨仓）

```
上游仓流水线（MR / 合并）
  ├─ job1: 变更路径检测   git diff --name-only | grep -E '^<契约模块路径>'
  ├─ job2: mvn deploy     （仅契约模块，-U 刷私服 SNAPSHOT）
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

豁免记录每季度复盘一次：豁免后下游是否完成迁移、豁免是否可回收。

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

1. 云效私服保留历史 SNAPSHOT（japicmp 拉旧 jar 依赖它）；不保留则 baseline 改为
   CI 制品库缓存上次绿构建的契约 jar；
2. 云效 Flow 允许组织内跨仓流水线触发（需组织级权限配置）。
