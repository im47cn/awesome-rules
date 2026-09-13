---
last-checked: 2026-09-13
re-check-trigger: 仓库新增架构文档（docs/ 体系扩展），或 manifest formatVersion 升级到 3
depth: 代码级（manifest 校验链逐行验证）
---

# Rome（rome-os/rome）

## 一句话定位

面向递归智能体的开源 Agent OS（compounding agent OS），以 App/Capability/Store 为核心实体；与 Rome Tools/Biome 无关。

## 事实快照（2026-09-13）

- MIT；2026-08-23 建仓（与 wemux 同期）；494 stars / 37 forks；当日仍活跃推送
- TypeScript；架构文档 13 篇 + 概念文档 12 篇，组织度高
- App 清单 `app.yaml`（formatVersion 1→2）经 zod strict schema 校验

## 可借鉴点

manifest 校验实现已逐行验证（2026-09-13，浅克隆 `/tmp/rome`，结论以会话记录为准）：

| # | 机制 | 适用点 | 验证状态 | 落地状态 |
| --- | --- | --- | --- | --- |
| 1 | 单一 strict schema 在多关卡复用：parseAppManifest 在 pack/prepare/install/validate/remix 5+ 调用点生效，安装门独立重复校验而非信任 pack 结果 | skills/ 清单门禁 ADR 候选：所有关卡接受完全相同的 manifest，禁止各关卡私设校验 | ✅ 代码级（调用点 rg 全量追踪） | 未裁决（候选 ADR：先 grep 查重 gauntlet 现状） |
| 2 | `resolvePathWithinBase` 路径逃逸防护（`relative().startsWith("..")` 拒绝）+ 专项负控测试 | 门禁脚本处理外部输入路径时的统一防护函数 | ✅ 代码级 | 未裁决 |
| 3 | zod `.strict()` 拒绝未知字段而非剥离（"Store bundles are immutable, so the schema is strict"） | skills/ SKILL.md frontmatter 校验：未知字段报错而非静默丢弃 | ✅ 代码级 | 未裁决 |
| 4 | CJK 感知宽度校验（tagline 80 width units = 80 拉丁/40 汉字） | 校验边界划到 UI 渲染契约而非字符数 | ✅ 代码级 | 未裁决 |
| 5 | 42 个 pack 测试 + 显式负控制（非法 id/未知字段/路径逃逸各有专项失败用例） | gauntlet 检查器的负控制范式：先证明检查器会失败 | ✅ 代码级 | 已有等价实践（gauntlet NC 系列） |

## 不适配点 / 否决

- Rome 是平台级 OS，其 Store/Manager/Installer 生命周期整体对本仓过重（YAGNI），仅吸收校验链设计。
- **已知弱点（反向借鉴）**：`skill-frontmatter.ts:22-49` 用正则逐字段匹配而非 YAML 解析+zod 校验（tools 仅支持单行内联数组）——校验链最弱一层即绕过点；本仓若做清单门禁，全链统一用真解析器。

## 资源链接

- 仓库：<https://github.com/rome-os/rome>
- 调研产出：2026-09-12/13 会话（VISION/DESIGN/architecture 13 篇精读 + packages/core manifest 校验代码级验证）
