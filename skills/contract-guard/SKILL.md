---
name: contract-guard
description: >
  跨仓契约兼容性设计与审查。当用户提到以下任意意图时激活：契约审查、跨仓兼容、
  API jar 兼容、契约门禁、契约变更、下游编译、japicmp、契约模块变更检查、
  接入跨仓契约门禁。提供两类能力：(1) 按规范为多仓协作项目设计/接入契约兼容性
  门禁（japicmp + 下游编译触发），(2) 用脚本检查本地契约模块变更并提示。
  规范正文见 steering/cross-repo-contract-standards.md。
---

# 跨仓契约兼容性设计与审查

本技能处理**多仓协作下 API 契约模块（供下游仓 Maven 消费的 jar）的兼容性守护**。

## 工作流

### 场景 1：本地开发中，检查契约模块是否变更（防呆提示）

> ⚠️ **直接运行脚本，不要手动 git diff 再逐个判断模块归属。**

脚本位于本 SKILL.md 同级的 `scripts/` 子目录（按本文件实际路径定位，非用户项目 cwd）：

```bash
bash scripts/check-contract.sh [--base <git-ref>] [<仓库根目录>]
```

- `--base`：对比基准，默认 `origin/master`（不存在则退回 `HEAD~1`）；
- 自动发现契约模块（pom `<description>` 含"契约"）、检测 diff 是否命中；
- 命中时逐条列出变更文件并提示后续动作（CI 门禁 + 通知下游），退出码 `1`；
- 未命中退出码 `0`。**脚本只提示不阻断**——门禁在 CI。

### 场景 2：接入契约门禁（设计/配置）

1. 读取 [`../../steering/cross-repo-contract-standards.md`](../../steering/cross-repo-contract-standards.md)
   掌握完整规范（认定标准、baseline 策略、变更纪律、发布顺序）；
2. 上游仓：将 [`templates/japicmp-pom-snippet.xml`](templates/japicmp-pom-snippet.xml)
   合入各契约模块 pom，`verify` 阶段生效；
3. 流水线：参照 [`templates/yunxiao-pipeline-contract.yaml`](templates/yunxiao-pipeline-contract.yaml)
   配置变更路径检测 → deploy → 下游契约编译触发（云效 Flow）；
4. 下游仓：确认存在最小"契约编译"流水线（`mvn -U clean test-compile`）并配置分支映射。

### 场景 3：审查一次契约变更（MR 评审）

1. 运行场景 1 脚本确认变更范围；
2. 按规范"变更纪律"表逐项核对：兼容性/破坏性定性、豁免声明、迁移说明、发布顺序；
3. 输出报告按 `steering/review-report-standards.md` 五段式。

## 边界

- 只管**编译期契约**（Java public API / DTO 字段）；运行时 HTTP 契约走
  `api-guard` / `openapi-standards.md`；
- 不做人工契约清单维护——下游用了哪些字段由下游真实编译发现（C 方案），不做登记。
