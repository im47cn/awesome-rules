---
title: Git 自动化工具
scenario: 提交校验/生成 changelog/发版
---

# Git 自动化工具

对齐 [`steering/git-conventions.md`](../../steering/git-conventions.md) 的三类工程化能力，基于 [Conventional Commits](https://www.conventionalcommits.org/)：

| 工具 | 作用 | 技术方案 |
|---|---|---|
| commit 模板 | 提交前预填格式提示（IDE / 编辑器） | `.gitmessage` + `commit.template` |
| commitlint | 提交时校验 message 格式 | `@commitlint/cli` + `config-conventional` |
| commit-and-tag-version | 自动生成 changelog + 按语义 bump 版本号 | `commit-and-tag-version` |

> **选型说明**：`standard-version` 自 2022 年起 archived，本工具采用其活跃 fork [`commit-and-tag-version`](https://github.com/absolute-version/commit-and-tag-version)，配置完全兼容。

## 快速安装

前置：已 clone 本仓库。在你的**业务项目根目录**执行：

```bash
bash /path/to/awesome-rules/tools/git/install.sh .
```

`install.sh` 会：

1. 检测 node / npm（需 node ≥ 16）
2. 拷贝 `commitlint.config.js` + `.versionrc.js` 到项目根；`commit-template.txt` → `~/.gitmessage`（全局 commit 模板）
3. **全局**安装工具（`@commitlint/cli`、`@commitlint/config-conventional`、`commit-and-tag-version`，检测已装则跳过）
4. 写入 `.git/hooks/commit-msg`（调全局 commitlint，**无需 husky**）
5. 在 `package.json` 注入 `release` / `release:dry` 脚本（调全局 commit-and-tag-version）

### 更新已装项目

awesome-rules 的配置是「拷贝」到各业务项目的，后续规范演进不会自动触达已装项目。先拉取本仓库最新版，再对每个已装项目执行刷新：

```bash
cd /path/to/awesome-rules && git pull          # 先更新本仓库
bash /path/to/awesome-rules/tools/git/install.sh --update /path/to/业务项目
```

`--update` 与首次安装的区别：

- 配置文件（`commitlint.config.js` / `.versionrc.js`）与 commit 模板：**无条件覆盖**（首次安装遇已存在会询问）
- `commit-msg` hook：仅覆盖「本工具生成的」；非本工具生成的（husky/lefthook）**一律跳过**，避免破坏既有方案
- 全局工具、`package.json` scripts：与首次相同（检测补装 / 幂等注入）

## 使用

### 提交校验

安装后每次 `git commit` 自动触发，不合规则的提交会被拦截。

### 生成 changelog + 版本号

```bash
npm run release:dry   # 预览将生成的 CHANGELOG 与版本号（不落盘）
npm run release       # 正式执行：bump 版本 + 更新 CHANGELOG.md + 打 tag
```

## 配置

三份配置单一对齐 `steering/git-conventions.md`，是规范的「可执行镜像」：

- `~/.gitmessage` —— commit 模板（装主目录 + 全局 `commit.template`，所有仓库/IDEA 一次识别）
- `commitlint.config.js` —— type/scope 枚举、主题行 ≤50 字符、breaking 标记（事后校验）
- `.versionrc.js` —— changelog 中文分节、emoji 前缀

> 修改规则时请**同步更新 `steering/git-conventions.md`**，保持规范文档为唯一事实源。

## 适用场景

- ✅ **Node / 前端 / 全栈项目**：原生支持
- ⚠️ **Java / Maven 等非 node 项目**：需先装 node；changelog/版本号功能依赖 node 运行时，提交校验可独立使用

## IDE 兼容性（commit template）

`install.sh` 配置的 `.gitmessage` + `commit.template` 是各 IDE 的最大公约数，支持度不同：

| IDE | 读 `.gitmessage`? | 配置方式 |
|---|---|---|
| **IntelliJ IDEA** | ✅ 原生 | `commit.template` 自动生效，Cmd+K 预填，零额外配置 |
| **命令行 `git commit`** | ✅ 原生 | 打开编辑器预填 |
| **VS Code** | ⚠️ 需扩展 | GitLens（读 .gitmessage）或 Git Commit Editor（settings.json），见 FAQ |
| **Cursor** | ❌ AI commit 不读 template | 用 Copy Changes(Patch) → Chat + 规范 prompt，或手动写 |

> **折中策略**：`.gitmessage` 为单一事实源（提交仓库团队共享），各 IDE 按能力消费。Cursor 是唯一短板（其 AI commit 不支持 template 自定义）。无论 template 在各 IDE 是否生效，**commitlint 的 commit-msg hook 一律兜底**——走 git 原生 hook，所有 IDE 绕不过。

## FAQ

**Q: 为什么不用 husky / lefthook？**
A: `install.sh` 直接写 `.git/hooks/commit-msg`，零额外依赖。代价是 `.git/hooks` 不被 git 跟踪，团队成员需各自执行一次 `install.sh`；若要共享 hook，可自行接入 husky/lefthook。

**Q: scope 用了枚举外的业务域被警告怎么办？**
A: scope 校验为 `warn` 级别，不阻断提交。新增业务域请在 `commitlint.config.js` 的 `scope-enum` 补充，并同步 `steering/git-conventions.md`。

**Q: breaking change 如何触发 major 版本号？**
A: 提交时标记 `feat!:` 或在 footer 写 `BREAKING CHANGE:`，`npm run release` 会自动 bump major。

**Q: VSCode 不认 `.gitmessage` 怎么办？**
A: VSCode 的 Source Control 面板不读 git 的 `commit.template`（已知限制——`.gitmessage` 只在命令行 `git commit` 打开编辑器时生效）。两个替代：

- **VS Code Git Commit Editor 扩展**（交互式填空）：装后在 `.vscode/settings.json` 配置，对齐本规范：
  ```json
  { "vscodeGitCommit.template": ["{type}({scope}): {title}\n\n{body}\n\nCloses #{issue}"] }
  ```
  > `{scope}` 占位符取决于扩展版本；不支持则在 title 手写 `(scope)`，commitlint 会 warn 提醒。
- **GitLens 扩展**：读取 `.gitmessage` 预填。

无论用哪种 template，commitlint 的 `commit-msg` hook 都在 VSCode 提交时生效（底层调 `git commit`，绕不过 hook）。
