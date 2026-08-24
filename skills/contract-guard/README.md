# contract-guard

跨仓契约兼容性设计与审查技能。

## 能力

1. **接入契约门禁** — 按规范为多仓协作项目配置 japicmp 门禁（上游仓）+ 下游编译触发（跨仓）
2. **本地变更防呆检查** — 运行脚本检测契约模块是否被本次变更触及，提示后续动作
3. **审查契约变更** — MR 评审时按规范"变更纪律"核对兼容性定性、豁免声明、迁移说明、发布顺序

## 快速使用

```bash
# 检查本地变更是否触及契约模块（防呆提示，不阻断——门禁在 CI）
bash scripts/check-contract.sh [--base <git-ref>] [<仓库根目录>]
```

- 自动发现契约模块（pom `<description>` 含"契约"，排除聚合父模块）；
- 命中时逐条列出变更文件并提示后续动作（走 CI 门禁 + 通知下游），退出码 `1`；
- 未命中退出码 `0`。脚本只提示不阻断，强制拦截由 CI 门禁承担。

## 接入门禁（三步）

1. 上游仓：将 [`templates/japicmp-pom-snippet.xml`](templates/japicmp-pom-snippet.xml)
   合入各契约模块 pom，`verify` 阶段生效（含 baseline sha 重建方案与实测坑注释）；
2. 流水线：参照 [`templates/yunxiao-pipeline-contract.yaml`](templates/yunxiao-pipeline-contract.yaml)
   配置变更路径检测 → deploy → 下游契约编译触发（云效 Flow）；
3. 下游仓：配置最小"契约编译"流水线（`mvn -U clean test-compile`）与上下游分支映射。

## 边界

- 只管**编译期契约**（Java public API / DTO 字段）；运行时 HTTP 契约走 `api-guard`；
- 不做人工契约清单维护——下游用了哪些字段由下游真实编译发现，不做登记；
- 本地检查只有防呆提示性质，CI 是唯一权威裁决（规范「本地预检的边界」）。

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 检查脚本：[`scripts/check-contract.sh`](scripts/check-contract.sh)
- japicmp 模板：[`templates/japicmp-pom-snippet.xml`](templates/japicmp-pom-snippet.xml)
- 云效流水线模板：[`templates/yunxiao-pipeline-contract.yaml`](templates/yunxiao-pipeline-contract.yaml)
- 规范正文：[`steering/cross-repo-contract-standards.md`](../../steering/cross-repo-contract-standards.md)
