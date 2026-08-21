---
name: doc-gen
description: >
  DDD 技术文档自动生成。将 Java DDD 项目自动转换为交互式静态文档站点，
  包括架构图（Mermaid 可点击）、DDD 分层视图、OpenAPI 交互文档（Scalar）、
  数据库 ER 图、全局搜索（Pagefind）和嵌入的 Architecture AI Agent。
  当用户提到：生成技术文档、生成架构文档、项目文档站点、DDD 文档、
  API 文档站点、架构图生成时激活。
---

# DDD 技术文档自动生成 (doc-gen)

单项目入门文档（新人 5 分钟看懂一个项目）；多项目聚合归架构鹰眼（`arch-hawkeye/`）。
架构图、功能清单、站点结构、Schema 契约原理、CI 归档等背景见
[README](README.md)（渐进式加载：本文件只保留运行与验收所需）。

## 快速使用

### 新项目接入（3 步）

```bash
# 1. 初始化项目配置（从 pom.xml 自动推断 groupId）
python3 scripts/doc_gen.py /path/to/java-project --init

# 2. 生成 manifest + 构建静态站点
python3 scripts/doc_gen.py /path/to/java-project --build --output docs-site/

# 3. 启动预览
cd docs-site/ && npm run dev
```

### 仅生成数据清单 / 从已有 manifest 构建

```bash
python3 scripts/doc_gen.py /path/to/java-project --manifest-only --output manifest.json
python3 scripts/doc_gen.py --from-manifest manifest.json --build --output docs-site/
```

## 项目配置（.doc-gen.json）

`--init` 自动生成；域名中英映射、业务上下文等手工调整项见
[README](README.md#项目配置)。`project_repo` 支持链接模板占位符：

```jsonc
// 推荐：完整链接模板，{revision}/{path} 占位符 —— 各平台 URL 形态全覆盖
"project_repo": "https://codeup.aliyun.com/{orgId}/{repo}/blob/{revision}/{path}"
// 兼容：裸仓库 URL —— 默认 GitHub/Gitea 风格 {repo}/blob/{revision}/{path}
"project_repo": "https://github.com/user/repo"
```

## 架构演进 diff（delta）

```bash
python3 scripts/doc_gen.py diff <base快照目录> <head快照目录> \
  --output delta.json --markdown delta.md
```

- 六维度 receipt：组件（含 moved 分级）/聚合/数据表/状态机/跨域依赖/API 端点；
  schema_version 不相等 → `exit 2` 拒绝
- **站点渲染**：`--output <站点>/doc-manifest/delta.json` 后 `--build` 自动生成
  「🔀 架构演进」页面（统计卡 + 六维度表 + 变更明细）
- CI 归档约定（master push 归档快照、PR 门禁贴 delta.md）见
  [`ci/archive-manifests.example.yml`](ci/archive-manifests.example.yml)

## 退出码与验收契约（强制）

- **退出码 0 = 成功；1 = 阶段失败（manifest 校验失败 / npm 缺失或 install/build 失败）；2 = 用法错误。非零退出码绝不可描述为成功**
- 每次运行产出 `doc-manifest/receipt.json`（`ok` 当且仅当无 `fail`；`warn` 是事实降级不阻断）。交付时必须引用 receipt 检查项，不得声称未执行的检查
- 风险扫描的 `critical` 数量必须如实转述给用户，不得省略
- npm 构建失败从静默跳过改为 `exit 1`（breaking）：依赖旧行为的脚本需显式降级
