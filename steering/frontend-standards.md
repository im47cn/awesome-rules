---
title: 前端工程技术规范（Vue3 管理端）
scenario: 开发或评审 open-platform-admin 等 Vue3 + Vite + Element Plus 管理端项目时加载；涉及 mock 联调开关、动态路由/菜单下发、axios 封装复用、数据可交互性、前端变更验证时必读
---

# 前端工程技术规范（Vue3 管理端）

> 来源：open-platform-admin MR !5 评审修复沉淀（2026-09，回调中心管理域）。
> 适用 Vue3 + Vite + Element Plus 管理端项目。条款分【强制】/【推荐】两级。

> **执行承接**：本规范全部【强制】条款面向外部 Vue3 目标仓（open-platform-admin 等），本仓 gauntlet 结构上无法触达——可机械项（mock 门控、.env 分层）落点为目标仓 CI 片段（候选项：`grep -rn 'enableDev:[[:space:]]*true' build/; test $? -eq 1`、`git grep -in 'VITE_MOCK.*true' -- .env; test $? -eq 1`——仅无匹配 rc=1 视为通过，grep 自身错误 rc≥2 须判失败，禁用 `!` 前缀整体反转），其余仅靠目标仓 CR 评审承接。

## 1. Mock 与本地联调

### 【强制】mock 服务经环境变量显式开启，默认关闭

构建插件层以环境变量门控 mock：`getPluginsList` 第三参透传 `VITE_MOCK`，落到
`vitePluginFakeServer({ logger: { enableDev: VITE_MOCK } })`；`.env` 默认
`VITE_MOCK = false`。`wrapperEnv` 会把 `VITE_*` 布尔值规范化后透传，无需额外接线。

**为什么**：mock 恒开会劫持所有匹配请求——其他不需要 mock 的协作者、CI 环境的
请求也被拦截，且问题隐蔽（表现为"接口返回假数据"而非报错）。MR !5 评审意见
原话：mock 开发配置写死会拦截他人请求。

```
❌ vitePluginFakeServer({ logger: { enableDev: true } })   // 硬编码恒开

✅ .env: VITE_MOCK = false                                 // 默认关闭
✅ build/plugins.ts: enableDev: VITE_MOCK                  // 需要者本地显式开启
```

### 【强制】个人本地覆盖只写 `.env.local`

需要 mock 时在 `.env.local` 置 `VITE_MOCK = true`（gitignore `*.local` 已覆盖，
天然不入库），不改动共享的 `.env`。

**为什么**：个人开关偏好没有理由进团队共享配置——改 `.env` 会随提交影响所有人，
还容易被误提交覆盖他人设置；`.env.local` 被 gitignore 天然隔离，个人与共享严格分层。

### 【强制】mock 数据与真实后端契约同构

mock 返回的结构、字段、层级必须与真实后端一致，不得为省事输出简化形态。菜单
mock 必须按后端 `FunctionModel` 扁平结构构造（resourceId / parentId / hierarchy /
funcType / funcName / actionName / url / funcOption），由前端按 parentId 建树，
组件路径靠 `url` 字段解析——与生产链路完全一致。

**为什么**：同构 mock 验证的是"后端菜单下发后前端真的能渲染"；简化形态的 mock
通过 ≠ 真实链路通过。MR !5 用 8 条同构 mock 菜单（1 根 + 7 子）验证了菜单下发
全链路。

### 【强制】mock 禁止宽容解析——请求侧按冻结契约严格消费

mock 侧解析请求参数时，不得接受契约冻结文本之外的形态（未知字段、已废弃字段、
前端私设嵌套结构）：宽容 = 让 mock 自成第二契约事实源，与真实后端分叉。真实后
端对未知请求字段普遍静默忽略（Jackson 默认关闭 FAIL_ON_UNKNOWN），被忽略的字
段在 mock 里"生效"、在真实链路里"蒸发"，走查在 mock 模式必然全绿。废弃形态应
显式抛错（`throw new Error('契约冻结为 X，Y 已废')`），让漂移在 mock 侧红灯而
不是在生产现场红灯。

**为什么**：gtsp-wop-developer 门户 batchRetry 曾用前端私设嵌套 `timeWindow`
发请求（契约 E 冻结为扁平 `timeFrom`/`timeTo`）：mock 按嵌套形态解析照常过滤，
真实 callback 服务静默忽略 → 条件模式批量重试时间窗失效、重推范围放大
（2026-09-16 四仓对账实证：同窗口扁平形态 60104 无匹配 vs 嵌套形态 matched=1）。
修复时 mock 侧同步加 `assertNoLegacyTimeWindow` 抛错守卫 + 契约锁定测试运行时
对抗用例（4e9bb7c）。

### 【推荐】mock 端点路径与真实网关一致

便于本地 `curl` 对比 mock 与真实响应差异，也便于切换验证（关 mock 后同一 URL
应透传真实网关）。

## 2. 路由与菜单下发

### 【强制】业务页面路由由后端菜单/资源配置下发，前端不得硬编码注册

页面可达性走 `transformRouters(getUserMenu(model))` 链路：后端按用户角色下发
菜单/资源，前端动态注册。`customRouter` 仅允许空占位或明确的过渡期代码。

**为什么**：菜单权威在平台"资源配置"。前端硬编码注册会导致：各环境菜单不一致、
权限控制被绕过、平台菜单配置更新后前端代码与之漂移（后端下架菜单，前端路由还在）。
MR !5 评审意见：路由应走平台菜单配置，不应在代码里写死。

```
❌ // router/custom/callback-center.ts
❌ export const callbackCenterRouter: CustomRouteMetaData[] = [ /* 20+ 条业务路由 */ ]
❌ // router-transform.ts 里展开注入 customRouter

✅ export const customRouter: TransformedRouter[] = [];  // 空占位 + 注释说明路由来源
```

### 【推荐】删除代码路由后，本地验收用同构 mock 菜单兜底

配合 §1 的同构 mock：菜单由 mock 端点下发（模拟后端资源配置），验证
addAsyncRoutes 组件解析、路由守卫、懒加载全链路，与生产行为一致。

### 【推荐】迁移期保留的前端注册必须带回收条件

确实需要过渡期双轨时，代码处须有 TODO 注明回收条件与截止时间，并在 MR 描述中
显式声明，避免"临时"变成永久。

## 3. HTTP 请求层复用

### 【强制】axios 实例统一由 service 层工厂创建，派生实例只覆写差异项

所有 axios 实例经 `createAxios` 工厂派生；业务域需要独立实例时（如不同响应
信封契约），只覆写差异项（通常是 `transform` 拦截器），headers / token 注入 /
网关前缀等公共配置一律继承。

**为什么**：复制粘贴的配置会双份漂移——默认实例改了 token 注入或网关前缀，
业务实例还是旧的，且无人知道有两份。MR !5 评审意见：http.ts 与
service/index.ts 配置重复。

```
❌ // 业务 api/http.ts 里重写整套 VAxios 配置（headers、getToken、
❌ // requestOptions、prefix 全部复制一遍）

✅ export const contractHttp = createAxios({ transform: { ... } });  // 只覆写差异
```

### 【强制】工厂合并配置必须落新对象

工厂内合并默认配置与传入配置时，必须 `merge({}, defaultOptions, opt || {})`
（目标为空对象），禁止 `merge(defaultOptions, opt)`。

**为什么**：lodash `merge` 是原地变更——直接以 defaultOptions 为目标会污染共享
默认配置，后续所有派生实例（含默认实例）被悄悄改坏，且极难排查。MR !5 修复中
顺带发现并修复。

### 【推荐】派生实例的存在理由写注释

为什么不用默认实例？语义冲突点（如：契约信封归一需要静默失败 vs 默认实例
toast + throw）写清楚，防止后人"顺手统一"回退掉差异。

### 【推荐】网关前缀、信封契约差异用配置表达

不同契约的网关前缀（如 `/gtsp-wop-callback` vs 默认 `/gtsp-wop-service-core`）
收敛为具名配置对象传入工厂，不要 if/else 散在业务代码里。

## 4. 数据展示的可交互性

### 【强制】排障标识提供点击复制

traceId / taskId / msgId 等排障用途的长标识，必须提供点击复制：clipboard API
+ 成功提示，空值守卫 + 失败降级提示。

**为什么**：死文本强迫用户肉眼比对 64 位 ID 或手抄进日志系统，排障效率极低。
MR !5 评审意见：traceId 应可复制。

```
❌ <span>{{ row.traceId }}</span>                    // 64 位死文本

✅ <el-link @click="copyText(row.traceId)">{{ row.traceId }}</el-link>
✅ // copyText: 空值守卫 + clipboard 写入 + ElMessage 成功/失败提示
```

### 【强制】外部资源链接必须是真实锚点

OSS 原文、文档、工单等外部资源的展示必须可点击跳转：`href` 真实地址 +
`target="_blank"` + `rel="noopener noreferrer"`。禁止死文本或纯截断展示。

**为什么**：死文本迫使用户手工复制 URL 到新标签页，OSS 回执原文肉眼无法核对。
`_blank` 保留管理端当前页状态；`noopener noreferrer` 防止新页面经 window.opener
反向操控管理端页（安全默认）。

### 【推荐】长文本截断时保留获取原文的途径

表格内长文本截断展示可以，但需 tooltip 显示全量或提供"查看原文"链接。

**为什么**：截断丢上下文，排障时恰恰需要全量文本；保留原文途径让截断只影响
视觉不影响信息获取。

### 【推荐】敏感字段脱敏展示，完整值按需复制

凭证快照、密钥类字段默认脱敏，完整值通过点击复制获取，避免屏幕泄露。

## 5. 前端变更验证

### 【强制】lint 与类型检查按改动文件门控

eslint 对改动文件零告警；类型检查按改动文件过滤与基线对比——存量脏基线
（项目无 typecheck 脚本、历史文件有错）不阻塞，但**改动文件不得新增错误**。

```
✅ npx vue-tsc --build --force 2>&1 | grep -E "改动文件路径"
   // 输出为空 ⇒ 改动文件零类型错误；非空需对照 main 基线差集判定——
   // 仅当错误行是本次改动新引入时才阻塞（改动文件的存量错误不算）
```

**为什么**：全量类型检查在存量脏基线下永远红，会逼人忽略结果；按改动文件过滤
才能让门禁真正生效。

### 【强制】mock / 路由 / 请求层变更必须本地冒烟

- `curl` 验证 mock 端点返回结构与预期一致；
- 浏览器走通关键页面：侧边栏菜单渲染 + 至少一个业务页数据可见。

**为什么**：这三层是管理端骨架，静态检查测不出运行时行为（菜单建树、组件懒加载
解析、拦截器顺序）。MR !5 冒烟实际抓到过路由配置遗漏。

### 【推荐】登录守卫挡冒烟时，按 origin 预置哑令牌 cookie

仅对 localhost 域注入哑令牌 cookie 绕过 SSO 守卫（如 Puppeteer
`page.setCookie`），不碰真实 SSO 环境、不用真实凭证。

**为什么**：绕守卫只有两条路——真实登录（碰真实凭证/环境，可能写进脚本与日志）
或本地注入哑值；限定 localhost + 哑令牌，失败也只影响本地冒烟，零外溢。

### 【推荐】开关/门控类变更做负向验证

改了开关类逻辑（如 mock 门控），验证默认关闭态：端点应透传真实网关（实测返回
`UC_A1_0014 用户未登录` 即证明未被 mock 拦截），确认默认行为未被改变。

**为什么**：门控的默认态影响所有协作者，只验证"开"不验证"关"等于只测了一半。
