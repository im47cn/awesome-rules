---
title: Git 自动化工具
scenario: 提交校验/生成 changelog/发版
---

# Git 自动化工具

对齐 [`steering/git-conventions.md`](../../steering/git-conventions.md) 的三类工程化能力，基于 [Conventional Commits](https://www.conventionalcommits.org/)：

| 工具 | 作用 | 技术方案 |
|---|---|---|
| commit 模板 | 提交前预填格式提示（IDE / 编辑器） | `.gitmessage` + `commit.template` |
| commitlint | 提交时校验 message 格式 | `@commitlint/cli` + `config-conventional`，hook 由 [lefthook](https://github.com/evilmartians/lefthook) 托管 |
| 变更行覆盖率红线 | pre-commit 轻检 / pre-push 全量兜底，≥95% | `lefthook.yml` + `.lefthook/coverage.sh`（diff-cover，支持 pytest-cov / vitest / Maven+JaCoCo） |
| commit 规范校验（自动装环境） | Java 等后端机器 clone 后首次提交自动补装 commitlint | `.lefthook/commitmsg-check.sh`：缺 commitlint 时 `npm install -g` 自动安装，规则单一来源 commitlint |
| commit-and-tag-version | 自动生成 changelog + 按语义 bump 版本号 | `commit-and-tag-version` |

> **选型说明**：`standard-version` 自 2022 年起 archived，本工具采用其活跃 fork [`commit-and-tag-version`](https://github.com/absolute-version/commit-and-tag-version)，配置完全兼容。

## 快速安装

前置：已 clone 本仓库。在你的**业务项目根目录**执行：

```bash
bash /path/to/awesome-rules/tools/git/install.sh .
```

`install.sh` 会：

1. 检测 node / npm（需 node ≥ 16）
2. 拷贝 `commitlint.config.js` + `.versionrc.js` + `lefthook.yml` + `.lefthook/` 门禁脚本（coverage / commitmsg-check / run-tests / spec-check / sourcery-gate / mutation-gate / coderabbit-gate + spec_check.py）到项目（**入库共享给全团队**）；`commit-template.txt` → `~/.gitmessage`（全局 commit 模板）
3. **全局**安装工具（`@commitlint/cli`、`@commitlint/config-conventional`、`commit-and-tag-version`、`lefthook`，检测已装则跳过）
4. 执行 `lefthook install` 写入 hook shim（读项目内 `lefthook.yml`，调全局 commitlint）
5. 在 `package.json` 注入 `release` / `release:dry` 脚本（调全局 commit-and-tag-version）

### 更新已装项目

awesome-rules 的配置是「拷贝」到各业务项目的，后续规范演进不会自动触达已装项目。先拉取本仓库最新版，再对每个已装项目执行刷新：

```bash
cd /path/to/awesome-rules && git pull          # 先更新本仓库
bash /path/to/awesome-rules/tools/git/install.sh --update /path/to/业务项目
```

`--update` 与首次安装的区别：

- 配置文件（`commitlint.config.js` / `.versionrc.js` / `lefthook.yml` / `.lefthook/*.sh` + `.lefthook/spec_check.py`）与 commit 模板：**无条件覆盖**（首次安装遇已存在会询问）
- hook：自动清理本工具旧版直写的 `commit-msg` 后重跑 `lefthook install`；非本工具、非 lefthook 生成的 hook **一律跳过**，`core.hooksPath` 被 husky 等接管时同样跳过，避免破坏既有方案
- 全局工具、`package.json` scripts：与首次相同（检测补装 / 幂等注入）

### 团队成员激活（装过一次的仓库）

`lefthook.yml` 随仓库共享，新成员 clone 后只需激活 hook（无需完整 `install.sh`）：

```bash
npm i -g lefthook   # 一次安装，所有项目共用
lefthook install    # 写入 .git/hooks/* shim
```

commitlint 无需手动装——首次提交时 `.lefthook/commitmsg-check.sh` 自动 `npm install -g` 补装（一次性）。未装 lefthook 时 hook shim 会打印警告并放行，不阻塞提交。

> **awesome-rules 本仓库例外**：根 `lefthook.yml` 是自用变体，直接引用
> `tools/git/lefthook/`（单一源，不产生 `.lefthook/` 运行时目录，避免双份漂移）。
> **不要对本仓库执行 `install.sh --update`**——会用分发模板覆盖根 yml 的路径。

### 覆盖率红线依赖（diff-cover）

`.lefthook/coverage.sh` 自动解析 diff-cover，**无需手动安装**，获取链依次为：

1. PATH 上已有的 `diff-cover`
2. 当前 python 环境已安装（探测顺序 `python3` → `python` → `py -3`）
3. 有 `uv` 则 `uv tool run` 按需拉取（首次自动下载并缓存）
4. 均无则 `pip install --user` **自动安装**后复用；仍失败才提示跳过放行（不阻塞提交）

前置条件仅两个：**bash**（macOS/Linux 自带；Windows 随 Git for Windows 自带）+ **任一 python 或 uv**。

**Windows 用户**：

- python.org 安装的 python 没有 `python3` 命令，脚本自动回退 `python` / `py -3`，无需手动处理
- `pip --user` 装出的 `diff-cover.exe` 落在用户 Scripts 目录（通常不在 PATH），脚本统一以 `python -m diff_cover.diff_cover_tool` 调用，不依赖 PATH
- 想免去首次联网拉取，可提前手动装：`uv tool install diff-cover`（跨平台单二进制，推荐）或 `pip install --user diff-cover`

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
- `lefthook.yml` —— hook 编排（commit-msg → 规范校验；pre-commit/pre-push → 覆盖率红线），入库随 clone 共享
- `.lefthook/commitmsg-check.sh` —— commit 规范校验（缺 commitlint 自动 `npm install -g`；无 node 提示后放行，装 node 后首次提交自动补装）
- `.lefthook/coverage.sh` —— 变更行覆盖率红线（diff-cover ≥95%，light/full 双模式；python/node/java；缺 diff-cover 自动安装，见「覆盖率红线依赖」），入库随 clone 共享
- `.lefthook/run-tests.sh` —— pre-push 项目自定义测试入口壳：项目有 `scripts/pre-push-tests.sh` 则执行（非零退出阻断 push），无则跳过。**`lefthook.yml` 是分发物（`--update` 会覆盖，勿手工加段）**，项目级测试/构建门禁一律写进 `scripts/pre-push-tests.sh`
- `.versionrc.js` —— changelog 中文分节、emoji 前缀

> 修改规则时请**同步更新 `steering/git-conventions.md`**，保持规范文档为唯一事实源。

## 适用场景

- ✅ **Node / 前端 / 全栈项目**：原生支持
- ✅ **Java / Maven 项目**：提交规范校验（无 node 也有 bash 兜底）+ 覆盖率红线（Maven + JaCoCo → diff-cover）原生支持；changelog/版本号功能仍依赖 node
- ✅ **Windows**：Git Bash（随 Git for Windows 自带）下完整可用，python 解释器自动探测，见「覆盖率红线依赖」
- ⚠️ **Gradle 等其他构建**：覆盖率暂未接入（可自行扩展 `.lefthook/coverage.sh`）

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

**Q: 为什么用 lefthook 而不是直写 `.git/hooks` 或 husky？**
A: 三种方式的取舍：

| 方案 | 优势 | 代价 |
|---|---|---|
| 直写 `.git/hooks`（旧版） | 零依赖 | hook 不入库，无法团队共享，扩展 pre-commit 等需自写脚本 |
| husky | 生态成熟，配 lint-staged | 每项目一个 devDependency，深绑 npm 生命周期，非 node 项目不友好 |
| **lefthook（当前）** | `lefthook.yml` 入库共享；单二进制语言无关；后续加 pre-commit lint（staged 文件过滤、并行执行）零成本 | 需全局装一次 lefthook |

工具仍走**全局安装**（不进业务项目 `package.json`），延续「项目零依赖」原则。

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
