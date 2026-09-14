---
last-checked: 2026-09-13
re-check-trigger: 首个外部贡献者 PR 被合并，或 star 突破 1k，或发布首个带版本号 release
depth: README 级（未做代码级验证）
---

# wemux（wemux-ai/wemux）

## 一句话定位

自托管的 AI Agent 协作平台（"AI Native organization OS"），核心差异是 worker 优先执行——Agent 在自己机器的隔离 Git worktree 里干活，控制面只做调度和人工审核。

## 事实快照（2026-09-13）

- Apache-2.0 社区版；**2026-08-25 建仓，仅约 3 周龄**；112 stars / 32 forks
- 单人主导维护（DrKyro）+ dependabot 流水，bus factor = 1
- TypeScript monorepo：React+Vite 控制台 / Hono 控制面 / worker daemon / Electron 桌面 / RN 移动端；Postgres(Drizzle) + S3 兼容存储
- 商业能力（模型网关、托管云节点池、计费、合作商）不在仓库内，代码中为自述"中性空 stub"
- 遥测：每日匿名聚合计数（5 个累计计数器），字段白名单在 `packages/shared/src/types/community-usage.ts`，`WEMUX_USAGE_REPORTING_DISABLED=1` 一键关闭

## 可借鉴点

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | Worker 优先执行 + 隔离 worktree：repo prepare → worktree → runtime(OpenCode/Claude Code/Codex) → git delivery 四段式生命周期，diff 回传人工确认 | 与 herdr + omp headless + worktree 手工编排同构；可为工厂链子任务建立正式派发契约 | ⚠️ 仅 README 自述 | 未裁决 |
| 2 | 配对安装协议：`curl \| bash --pairing-code` 一条命令把 worker 加入任意控制面 | 工厂链新增节点的接入仪式：从"记住命令"变成"生成配对码" | ⚠️ 未验证 | 未裁决 |
| 3 | 遥测字段白名单放源码 + payload 文档化 + 单变量 opt-out | `.factory/metrics/` 度量采集的诚实模式：白名单可审计、退出不依赖口头承诺 | ✅ README 核实字段路径 | 未裁决（落地前需核对 metrics 现状） |
| 4 | 商业能力中性 stub（自述不拦截不收费不限流） | gauntlet 可选层占位模式：stub 化 fail-closed，不静默降级 | ⚠️ stub 中立性未验证 | 未裁决 |
| 5 | 许可边界切割声明：平台 Apache-2.0 vs 被编排 CLI 各自专有 | skills/ 引用外部工具时的"本仓规范 vs 外部工具条款"边界条款 | ✅ 纯文档主张 | 未裁决（需评估可机械检查性） |

## 不适配点 / 否决

- 无显式否决项；架构级借鉴（#1）需先与 `docs/design/factory-harness-design.md` 的方案 B（omp headless，S0 已落地）对齐，避免平行建设。

## 资源链接

- 仓库：<https://github.com/wemux-ai/wemux>
- 调研产出：本仓库 2026-09-13 会话（README 全文精读 + 仓库/提交 API 快照）
