---
title: Git 提交规范
scenario: 提交代码/创建分支/PR
inclusion: always
---

# Git 提交规范

## Commit 格式（强制）
- 手工创建的合并提交（`git merge` / `git commit-tree`）同样适用本格式与主题行长度限制，示例：`chore: 合并 origin 链分支收敛异哈希重复提交`；不得沿用平台默认的 `Merge branch 'xxx' of ...` 主题行。

```
<type>[(<scope>)][!]: <subject>

<body>

<footer>
```

### type（必选）

| 类型 | 说明 |
| --- | --- |
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更 |
| style | 代码格式（无逻辑变更） |
| refactor | 重构（无功能变更） |
| perf | 性能优化 |
| test | 测试相关 |
| chore | 构建、依赖、配置 |
| revert | 回退之前的提交 |

### scope（可选）

按模块/技能填写，推荐值（须与 `commitlint.config.cjs` 的 `scope-enum` 保持一致）：

| 类别 | scope |
| --- | --- |
| 业务域 | `api`、`db`、`ui`、`ci` |
| 工程 | `dependency`、`tools`、`scripts`、`docs`、`deps`、`release` |

新增技能时同步追加到两处。

### 破坏性变更（强制标记）

含破坏性变更的提交**必须**显式标记，这是触发 major 版本号的唯一信号：

- 在 type 后加 `!`：`feat(api)!: <subject>`（无 scope 时 `feat!: <subject>`）
- 或在 footer 写 `BREAKING CHANGE: <破坏点 + 迁移路径>`

两者二选一，**推荐同时使用**——`!` 触发版本号自动化，footer 说清影响面与迁移方式。

### footer（页脚）

footer 用于关联工单与记录元数据，每行一条：

| 关键字 | 用途 | 示例 |
| --- | --- | --- |
| `Closes #N` | 关闭 issue | `Closes #456` |
| `Fixes #N` | 修复 issue（同 Closes） | `Fixes #789` |
| `Refs #N` | 关联但不关闭 | `Refs #101` |
| `BREAKING CHANGE:` | 破坏性变更说明 | `BREAKING CHANGE: 移除 /v1/login，改用 /v2/auth` |

### 示例

```
feat(db): 添加规则状态历史记录表
fix(ui): 修复差异数据表格分页错乱
docs: 更新数据库设计规范文档
```

带破坏性变更与 footer 的完整示例：

```
feat(api)!: 重构登录接口返回结构

- accessToken 拆分为 accessToken + refreshToken
- 移除 userName 字段，改用 userProfile 对象

BREAKING CHANGE: /v1/login 返回结构变更，前端需同步改造
Closes #456
```

原子提交示例（关联但不关闭）：

```
fix(db): 修复分页查询越界

Refs #321
```

## 提交要求

- 合并/rebase 冲突经工具自动解后，提交前必须核验冲突文件完整性：同一锚点两侧各自新增的测试类/函数应保两侧（union），工具静默删除一侧或整块删除冲突区是常见坏解（表现为文件尾部缺失、测试类丢失）。
- 重写/清洗提交历史前必须验证两个不变量：被剔除段的净效果为零（`git diff 段首 段尾` 为空）、重写前后终态 tree 一致（`git diff 旧终态 新终态` 为空），两者皆空才允许重放

- main 与工作分支（如 factory/base）并存时，推送前先比对两分支指向是否同步：修复提交落在旁支而未快进推送 main，会使远端 main 缺该修复，需二次补推
- 存在 CI 自动提交流（数据流水线、dependabot 等）的仓库，人工结构性变更（目录删除、大范围重构）须当场单独成 commit 并尽快推送，不得悬置在工作区：悬置变更会被下一次自动化提交捎带上 main，污染其提交归属，且可能触发分支保护拦截导致自动化流水线停更

- 提交前核对暂存区文件清单只含本次任务改动：多会话/多链并行时，他人或他链遗留的陈旧暂存（含数日前已 staged 未提交的文件）容易被随车带入；发现即拆分提交，非本任务文件还原为暂存态。
- 合并/rebase 冲突经工具自动解后，提交前必须核验冲突文件完整性：同一锚点两侧各自新增的测试类/函数应保两侧（union），工具静默删除一侧或整块删除冲突区是常见坏解（表现为文件尾部缺失、测试类丢失）。

- 重写/清洗提交历史前必须验证两个不变量：被剔除段的净效果为零（`git diff 段首 段尾` 为空）、重写前后终态 tree 一致（`git diff 旧终态 新终态` 为空），两者皆空才允许重放
- main 与工作分支（如 factory/base）并存时，推送前先比对两分支指向是否同步：修复提交落在旁支而未快进推送 main，会使远端 main 缺该修复，需二次补推

### 基础要求

- 使用中文，主题行 ≤50 字符
- 每个 commit 只做一件事（原子提交）
- 不提交未完成功能或调试代码
- 禁止无意义消息（如 "fix"、"update"）
- 破坏性变更必须标记（`!` 或 `BREAKING CHANGE:`）

### 历史重写与敏感信息

- 撤销误修改分三层（Sourcery PR #135 审查修正：checkout 不清暂存区、reset --hard 默认化有丢数据风险）：仅工作区（`git restore <file>`；`git checkout -- <file>` 同义但**不清暂存区**）、已 staged（`git restore --source=HEAD --staged --worktree <file>`——只 checkout 工作区会把 index 里的坏内容留给下一次提交带出）、已提交（默认 `git revert`；必须 `git reset --hard <好提交>` 时先建 backup ref（`git branch backup/pre-reset`）或 `git bundle` 备份、核对目标提交、确认 `git status --porcelain` 为空——reset 会连带丢弃其后全部本地提交与未提交修改；`checkout --` 已提交文件只是把坏内容写回工作区，status 转净但坏提交仍在分支上，push 即带出）。操作后 `git log --oneline -3` + `git reflog -3` 双确认回滚真实生效，不凭 status 干净下结论。
- 历史重写（剔除提交 / 强推）后立即 `git fsck --lost-found` 盘点孤儿对象，逐一鉴定是否已被现有分支吸收：gc 默认约两周回收，窗口内不鉴定即永久丢失；该操作纯只读、无风险（2026-08-28 实证：剔除 29a0ffde 并强推后盘点约 50 个孤儿，全部确认已吸收或判定丢弃）

<!-- 待 apply 的「暂存核验/分支同步/推送复核」类条款视语义落本节或「同步纪律」 -->

- git filter-repo 重写历史时：文本替换规则需覆盖敏感串的变体形态（截断的 org ID、`git@` SSH 形态、`.` 与 `/` 分隔符形态），否则会漏网残留；`--path-rename` 仅锚定路径开头，重命名路径中间的目录需以完整前缀锚定
- 历史重写前先 `git bundle` 做全量备份；重写后在工作区、全部历史 blob、全部提交消息三处复扫验证零残留，并重跑全量测试（目录改名可能破坏 fixtures 路径）
- 提交前自检不得混入公司敏感信息：内网代码托管地址、公司内部包名、内部服务依赖、与根 LICENSE 矛盾的清单 license 声明；提交消息中的仓库链接同样计入
- 仓库开源或对外迁移托管前，先做全历史敏感信息扫描（含全部提交消息与文件路径）；泄漏一旦进入 git 历史，仅删除当前文件无效，必须用 git filter-repo 重写全历史

## 分支命名

| 前缀 | 用途 | 示例 |
| --- | --- | --- |
| `feature/` | 新功能 | `feature/order-export` |
| `fix/` | Bug 修复 | `fix/login-timeout` |
| `hotfix/` | 紧急生产修复 | `hotfix/sql-injection` |
| `release/` | 发布准备 | `release/v1.2.0` |

## 同步纪律
- 同步远端后编译报「符号已定义 / already defined」类错误时，先怀疑本地在途修改已被上游分支实现：逐字符 diff 本地 staged/unstaged 内容与 HEAD 新增内容，语义重复的部分直接移除（零损失），整组旧版修改 stash 保存备查，不要当普通合并冲突逐行解决（2026-08-26 MR #168 合入后实测）。

- 多会话共享工作区：提交中断发现分支被切、暂存消失时，先 `git log -1 --stat` 核对并发提交内容；与自身改动一致则保留并仅补交剩余部分，不得重复落盘；不一致则披露后再动
- 并发写入者防护：仓库存在后台脚本或其他会话共用主 worktree 时，checkout/merge 等操作可能落在被并发切走的分支上产生污染提交；长占用任务（处理 PR、解冲突）前先确认无并发进程在操作同一分支，必要时用独立 `git worktree add` 隔离执行

- rebase/reset/换基线前先确认工作树干净（commit 或 stash 未提交编辑）：`git reset --hard` 会静默丢弃未提交修改，事后只能靠重读重写恢复
- 并发写入者防护：仓库存在后台脚本或其他会话共用主 worktree 时，checkout/merge 等操作可能落在被并发切走的分支上产生污染提交；长占用任务（处理 PR、解冲突）前先确认无并发进程在操作同一分支，必要时用独立 `git worktree add` 隔离执行

- 任何「本地 vs 远端」状态判断（领先/落后/待推送/是否需要 rebase）前先 `git fetch`：共享 main 且 CI/定时任务高频自动提交的仓库里，陈旧的本地 refs 会导致误判（实证：本地 refs 未刷新时误报「领先 3 个提交待推送」，fetch 后实为落后 11 个）
- 工作开始时先切到 `main` 并 `git pull --ff-only` 同步基线（同步对象是 `main` 而非当前 feature 分支——后者只拉自身 upstream，`main` 基线仍可能过时；无 upstream 的新分支上该命令直接失败，需同步工作分支时须显式指定其 upstream）：长期不 pull 会在下次同步时积累大体积 diff（自动提交的数据文件尤甚），且整个工作过程基于过时状态
- 分叉分支（本地与远端各有新提交）上 `--ff-only` 必然失败并保持旧状态：改走显式 `git pull --rebase`（或 fetch 后 rebase）同步，不得因失败而跳过同步带着过时基线开工

### 受保护 main 的写者治理

- PR 落地竞态双形态：① main 高频合入窗口期，逐次 merge main 的收敛策略可能永远追不上（checks 全部重置 pending → main 再前进 → 回落 CONFLICTING 循环），对策是全绿后立即合并或临时冻结 main 其他合入；② 多会话并行修同一 PR 分支会 push 撞车（非 fast-forward 拒绝），动手修改该 PR 分支前——代码、文档、CI 门禁等任何改动，修 CI 门禁只是典型场景——先 fetch 检查远端是否已有等效修复，确认自己是唯一写者后再开工（wop-go-sdk 2026-08-31 实证：PR #15 两轮全绿→CONFLICTING 回落，本地 7a7d82e 与远端 bf57bdc 撞车后按「远端更完整」弃本地）
- 本地 main 同为需治理的写者：`merge --ff-only` 失败不直接等于分叉——先 `git fetch`、确认工作树干净（`git status --porcelain` 为空）并核对 merge 的具体报错：脏工作树会在 ref 本可快进时中止 merge，直接按分叉处置会把未提交修改误判为可丢弃内容。仅当确认本地与 `origin/main` 各有独有提交后才按 ref 分叉处置，绝不顺手 rebase/merge 修平（feature 分支的分叉收敛处方不适用于 main）
- 分叉处置前必须完成等价性验证三件套——逐条识别本地独有提交、patch-id 对比（判定重放/重写等价）、tree diff 证明无本地独有内容。三件套只证内容等价、不证无损：空提交、合并提交、净效果为零的先改后回退提交没有可比较的 net patch（`.factory/feedback.py` 的 `_patch_id` 对此类返回 None），此类提交只按精确 SHA 匹配，匹配不上即「不可判定」——保持原状收尾，绝不把 patch-id 缺失当等价证据
- `reset --hard origin/main` 前必须留 backup ref（如 `git branch backup/main-<date>`）或 `git bundle` 全量备份，并在提交图上逐条确认每个本地独有提交的处置结果（已等价重放 / SHA 原样存在 / 明确丢弃）——空提交与合并提交的审计、署名、提交说明不体现于 tree diff；验证不充分则保持原状收尾，不强求同步（wop-typescript-sdk 2026-09-02 实证：预备性提交先落本地 main 两提交，PR #21 重开为 #22 经 bot 分支重写重放，合并后本地 main ahead 2/behind 4；patch-id 证明等价、tree diff 仅差远端修复净效果，reset --hard origin/main 无损）
- 根因预防：预备性/阶段性提交禁止落本地 main（一律走分支）；PR 分支经重放/重写合并后立即同步本地 main，不留分叉窗口

### 门禁脚本双向流：本地先实践，成熟后反哺

- `.lefthook/*` 允许本地直接修改并立即生效（fast path）：上游合并节奏不受本地阻塞，实验性改动先在真实项目验证
- 本地改动验证成熟后**必须回流** awesome-rules（走分发链四件套），回流 commit 与本地先行 commit 互相引用哈希
- awesome-rules 是规范权威：同步方向上的冲突以上游为准；本地未回流的差异属于「实验中」，不算漂移，但回流前不得再次从上游覆盖式同步同名文件（否则实验丢失）
- 漂移防线靠**差异可见**而非禁止直改：覆盖式同步（install.sh 重跑）前先 `diff` 本地 `.lefthook/` 与上游 `tools/git/lefthook/`，差异非空时人工确认是「本地实验未回流」还是「上游演进未同步」；`.factory` 工具链自身的同步与漂移检查走 `.factory/sync-from-upstream.sh`（三态清单 + feedback-upstream 反哺闭环，见 .factory/README.md「上游同步」）

## Pull Request

- AI 创建 PR 后即停，合并决定权归人工：不得在创建后自行 `gh pr merge`——即使推送被分支保护拒绝转走 PR 流，也不延伸为自动合并（2026-08-24 PR #50/#51 教训：创建后 15 秒自行合并，人工审查窗口被绕过）
- 触碰治理周界（guard PERIMETER，如 `.factory/`、`steering/`）的 PR 尤其不可自动合并：周界变更的人工审查是设计意图，不是流程仪式
- AI 创建 PR 后即停，合并决定权归人工：不得在创建后自行 `gh pr merge`——即使推送被分支保护拒绝转走 PR 流，也不延伸为自动合并（2026-08-24 PR #50/#51 教训：创建后 15 秒自行合并，人工审查窗口被绕过）
- 触碰治理周界（guard PERIMETER，如 `.factory/`、`steering/`）的 PR 尤其不可自动合并：周界变更的人工审查是设计意图，不是流程仪式

- PR 内容引用其他未合并 PR 的符号/文件时用 stacked PR（base 指向被依赖分支）：被依赖 PR 合并后 GitHub 自动 retarget 到 main；直接 base=main 会引用悬空、CI 必红
- 禁止同内容直推 main：main 前进后 GitHub 会把指向该内容且已无差异的开放 PR 自动标记为 MERGED（指纹：mergedBy=null、无 review 记录），形成「未经批准合并」表象；分支保护须设置 required_approving_review_count ≥ 1。

- 分支与远程出现内容等价但 hash 不同的提交（自动化链式重投/rebase 产物）时，先以 `git cherry` 判定等价，再以合并提交收敛并验证与目标树零差异（`git diff <目标> HEAD --stat` 为空），防止 hash 漂移累积。
- 多远程/双 pushurl 场景验证推送结果，必须逐远程以显式 URL 执行 `git ls-remote` 比对 SHA：截断输出（如 `tail -5`）会吞掉其他 pushurl 的结果行造成误判成功；本地追踪 ref 可能被并行推送短暂污染，令祖先检查出现假阳性。

- codeup（origin）服务端 pre-receive 禁止强推（`--force` / `--force-with-lease` 均被拒）。需收敛已分叉历史时改用合规路径：创建双端共同后代的合并提交使双远程均可 fast-forward，或删除远程分支后重建推送。
- 已推送提交 message 不合规时，不得仅吸纳其内容而保留原提交；应以 `git commit-tree` 生成同树替换提交（树零差异、保留 Co-authored-by 署名、新 message 过 commitlint），必要时复造合并提交后再推送，并在推送前验证新旧树 `git diff` 为空。

### 格式要求

- 标题格式：`[模块] 功能描述`
- 描述变更内容、影响范围和测试方法
- UI 变更须附截图

### 内容与验证纪律
- 清理"疑似垃圾文件"前对非常规产物先 `readlink`/`file` 鉴别类型：符号链接常以极小 size 出现且多为脚本契约产物（指向最近运行/最新版本），AI 巡检报告的"0B 空文件"可能是误判；删除契约性符号链接后按其生成逻辑重建指向。

- 跑构建链验证（依赖变更、配置修复）前先识别 prebuild/postbuild 钩子的写副作用（是否清写 git 跟踪的生成物）；验证优先在独立 worktree 跑，若在主工作区跑，结束后必查 `git status` 并恢复跟踪文件——prebuild 按测试 fixture 生成会覆盖/删除真实示例页（2026-09 实证：doc-gen 模板验证后 3 个示例 MDX 被删）。
- 工单分支只承载与该工单相关的提交：无关工作（其他模块、平台工具等）遴选到独立分支并单独提 MR，避免 MR diff 范围膨胀、回归责任不清

<!-- 待 apply 的「stacked PR/自动合并边界/强推收敛」类条款落本节 -->

- PR 描述必须如实注明验证范围：哪些检查已执行、哪些因环境限制未执行（如全量依赖安装、全量类型检查超时），并说明已采用的替代验证（如语法转译、单文件类型检查），不得暗示未执行的检查已通过。
- 给他人未合并的功能分支提修复：先 fork 原仓库，从作者分支最新 head 切出 fix 分支，并向该分支提交 stacked PR，同时在原 PR 下评论附上链接，便于作者直接采纳。
- 打补丁前先在基线分支最新 head 上复核缺陷仍然存在，并排查同文件内是否还有同类遗漏点，再动手修改。

### 历史重写与外部贡献
- 历史重写波及基于被剔除提交分出的子分支时，用 `rebase --onto` 重放、或直接复用重放结果对齐子分支后强推；放任不管会产生同内容异哈希提交，PR 合回时变为空变更或重复提交（2026-08-28：fix/ledger-issue-quote 对齐重放结果后 PR 自动收敛为单提交）

- 向外部开源项目提交集成、适配或修复前，先检索其 issue 与开放 PR：若已有现成方案（含未合并 PR），优先在该方案基础上验证、修 bug 或补充，不重复自研。
- force-push 重写历史前需临时禁用分支保护 ruleset（无法禁用则被拒推）；挂旧历史的机器人分支（如 dependabot）须连同其 PR 一并关闭，否则旧提交仍可通过该分支访问
- 已合并/关闭 PR 的 `refs/pull/*/head` 会永久持有旧提交，force-push 无法清除；需要彻底清除泄漏历史时，评估删库重建（重建后恢复 ruleset、以旧泄漏 SHA 返回 404 为验收标准）
