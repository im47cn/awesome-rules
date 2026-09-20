# 维度 B：脚本与工具健壮性只读合规审查

- 基线：`135b82913f7bc8936327df16fa1b1ec7398bb640`（= origin/main，worktree /tmp/ar-audit 全程只读，收尾 `git status --short` 为空）
- 规范来源：仓内现行条款（steering/testing-standards.md、CLAUDE.md、tools/git/README.md、install.sh:50-51 自身记录的规则）
- 消费场景设定：macOS 原生环境（/bin/bash 3.2.57、UTF-8 默认 locale）——分发钩子经 lefthook 以 `bash .lefthook/xxx.sh` 调用（tools/git/lefthook.yml:8,14,17,38,42,46,50,54），`bash` 由 PATH 解析，stock macOS 恒为 3.2

## 发现

### 1｜tools/git/lefthook/commitmsg-check.sh:27｜🔴 严重

**问题**：放行路径在 macOS 默认环境（bash 3.2 + UTF-8 locale + 脚本自身 `set -u`）下不可达——脚本于第 27 行以 `unbound variable` 中止 rc=1，`exit 0` 放行分支永远执行不到。后果：lefthook commit-msg 钩子失败 → **直接阻断提交**，且发生在「已安装但未定位到可执行文件」这一纯环境问题上，违反脚本自身第 5 行头注声明的原则「commit 钩子不阻塞环境问题，只拦规范违规」。同时构成仓内已知规范的内部一致性违例：install.sh:50-51 已明文记录「变量后紧跟全角字符须用 `${}` 界定，否则 bash 在部分 locale 下会把多字节字符误并入变量名」，install.sh:52 自身遵守（`${TARGET}（`），本行未遵守。

**证据**（`sed -n '27p'`）：

```sh
      echo "⚠ [commitmsg] 已安装但未定位到可执行文件（$CL），本次放行"
```

机制（hexdump 级实证）：bash 3.2 在 UTF-8 locale 下将 `）`（U+FF08，字节 EF BC 88）的首字节并入变量名，实际查找变量 `CL\xef` → set -u 触发 unbound variable 中止；无 set -u 时变量值整体丢失 + 多字节首字节被吞。LC_ALL=C 时正常。

**复现**（端到端，用真实分发脚本 + stub npm 逼出第 27 行路径，输出为实测）：

```sh
cd /tmp/ar-audit
mkdir -p /tmp/f1stub
printf '#!/bin/sh\ncase "$1" in install) exit 0;; prefix) echo /tmp/f1stub;; esac\n' > /tmp/f1stub/npm
chmod +x /tmp/f1stub/npm
printf 'feat: stub test\n' > /tmp/f1msg.txt
PATH="/tmp/f1stub:/usr/bin:/bin" LC_ALL=en_US.UTF-8 \
  bash tools/git/lefthook/commitmsg-check.sh /tmp/f1msg.txt; echo rc=$?
# → [commitmsg] 首次使用: 自动安装 commitlint（一次性，约几十秒）
#   tools/git/lefthook/commitmsg-check.sh: line 27: CL\xef: unbound variable
#   rc=1
PATH="/tmp/f1stub:/usr/bin:/bin" LC_ALL=C \
  bash tools/git/lefthook/commitmsg-check.sh /tmp/f1msg.txt; echo rc=$?
# → ⚠ [commitmsg] 已安装但未定位到可执行文件（/tmp/f1stub/bin/commitlint），本次放行
#   rc=0
```

最小复现（机制级）：

```sh
printf 'set -u\nCL=x\necho "（$CL），放行"\n' > /tmp/su.sh
LC_ALL=en_US.UTF-8 /bin/bash /tmp/su.sh; echo rc=$?   # unbound variable, rc=1
LC_ALL=C /bin/bash /tmp/su.sh; echo rc=$?              # 正常, rc=0
```

**建议**：第 27 行改 `（${CL}）`（与 install.sh:52 既有范式一致）。

---

### 2｜tools/git/lefthook/coverage.sh:184, 225, 235, 241｜🟠 主要

**问题**：与发现 1 同机制的四处 `$var` 紧邻全角字符。该脚本 `set -u`（无 -e），四处全部位于 :162-251 的全量模式子 shell 内，子 shell 以 `) || fail=1` 收口（:251）——子 shell 内 set -u 中止 rc=1 与业务失败不可区分，一律折算为 `fail=1` → 脚本 exit 1 → pre-push `coverage-full` 层（lefthook.yml:39-42）拦截 push。分路径影响：

- **:184**（jacoco 版本为非数字字面量时的「跳过版本校验」提示路径，:182-187）：预期行为 = 打提示后继续跑覆盖率；实际 = 子 shell 中止 → `fail=1` → **环境提示路径被折算成拦截，macOS 下虚假阻断 push**。
- **:225**（预算生效提示路径，:213-226，仅当项目配了 coverage-budget.env 且预算>0 时走到）：预期 = 信息输出后继续；实际 = 同上**虚假阻断 push**。
- **:235 / :241**（全量行/分支覆盖不足红线 ✗ 失败路径，:234-243）：分支条件本已判定失败、后续即 `exit 1`，拦截语义不变，但 ✗ 诊断消息在输出前即中止 → **失败原因对开发者不可见，诊断降级**。

**证据**（`sed -n '184p;225p;235p;241p'`）：

```sh
            echo "[cov] ⚠ $d jacoco 版本「$jver」非数字字面量, 跳过版本校验（确保运行时 ≥0.8.2）"
            echo "[cov] $d 豁免预算生效: 行 ≤$BUDGET_LINE_MISSED / 分支 ≤$BUDGET_BRANCH_MISSED（min(申报, 台账 LEDGER_TOTAL 行$led_l/分支$led_b), 逐项条目归 CR 审查）"
            echo "✗ [cov] $d 全量行覆盖 ${lp}%（实 missed $lm, 预算扣除后 $lme）< ${FAIL_UNDER_JAVA}%（存量+新增红线, 补测或按排除实践豁免后重跑）"
              echo "✗ [cov] $d 全量分支覆盖 ${bp}%（实 missed $bm, 预算扣除后 $bme）< ${FAIL_UNDER_JAVA}%（存量+新增红线）"
```

（同文件 :192 `≥${FAIL_UNDER_JAVA}%` 已正确花括号化，证明四处属遗漏而非范式缺失。）

**复现**（机制级，逐处变量名替换即可；以 :225 的 `BUDGET_BRANCH_MISSED（` 为例）：

```sh
printf 'set -u\nBUDGET_BRANCH_MISSED=3\necho "分支 ≤$BUDGET_BRANCH_MISSED（min(申报)"\n' > /tmp/b.sh
LC_ALL=en_US.UTF-8 /bin/bash /tmp/b.sh; echo rc=$?   # BUDGET_BRANCH_MISSED\xef...: unbound variable, rc=1
LC_ALL=C /bin/bash /tmp/b.sh; echo rc=$?              # 正常输出, rc=0
```

上下文证据：`sed -n '162p;251p' tools/git/lefthook/coverage.sh` → `(` 与 `) || fail=1`。

**建议**：四处统一花括号化：`${jver}」`、`$BUDGET_BRANCH_MISSED}（`（该行实为 `≤$BUDGET_BRANCH_MISSED（` → `${BUDGET_BRANCH_MISSED}（`）、`${lme}）`、`${bme}）`。

---

### 3｜tools/test_dispatch_watch.sh:91｜🟡 次要

**问题**：`bad` 失败诊断函数内 `事件数=$n（` 未花括号。脚本 `#!/bin/sh` + `set -e`（无 -u）：macOS `/bin/sh`（= bash 3.2 sh 模式）+ UTF-8 locale 下 `$n` 值静默丢失（无 -u 不中止，输出「事件数=（应恰 1 条哨兵）：」），自测失败时诊断信息残缺；Linux dash 不受影响。同型第 7 处命中 tools/test_gauntlet_checks.sh:955 为注释文本，无运行时影响，仅备注。

**证据**（`sed -n '91p' tools/test_dispatch_watch.sh`）：

```sh
  bad "NC19e 事件数=$n（应恰 1 条哨兵）：$(grep -E 'outside|owned_deleted' "$LOG")"
```

**复现**：

```sh
printf '#!/bin/sh\nn=1\necho "事件数=$n（应恰 1 条）"\n' > /tmp/t3.sh
LC_ALL=en_US.UTF-8 /bin/sh /tmp/t3.sh    # → 事件数=（应恰 1 条）   ← 值丢失
LC_ALL=C /bin/sh /tmp/t3.sh              # → 事件数=1（应恰 1 条）
```

**建议**：改 `事件数=${n}（`。

---

### 4｜tools/git/lefthook/mutation-gate.sh:10、tools/git/lefthook/coverage.sh:16｜🟡 次要

**问题**：SC2164 ×2 —— `cd "$REPO"` 无 `|| exit`。两脚本均为 set -u only（无 -e）：cd 失败（REPO 为空/非法、cwd 异态）不会中止，脚本以错误 cwd 继续执行后续 `git diff` / 构建命令 → 门禁在错误目录静默运行或静默跳过（分发面纵深缺陷）。现实施展概率低（lefthook 在目标仓内调用时 `git rev-parse --show-toplevel` 常态有效），故定 🟡。

**证据**（shellcheck 0.11.0 实测 + 原文）：

```
tools/git/lefthook/coverage.sh:16:1: warning: Use 'cd ... || exit' or 'cd ... || return' in case cd fails. [SC2164]
tools/git/lefthook/mutation-gate.sh:10:1: warning: ... [SC2164]
```

```sh
REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
```

**复现**：`cd /tmp/ar-audit && shellcheck -f gcc tools/git/lefthook/mutation-gate.sh tools/git/lefthook/coverage.sh | grep SC2164`

**建议**：`cd "$REPO" || { echo "✗ 无法进入 $REPO"; exit 1; }`（分发门禁宜 fail-closed）。

---

### 5｜coverage.sh:153,201,250；mutation-gate.sh:25,29,33（SC2086）；coverage.sh:150,198（SC2035）｜🟡 次要

**问题**：分发钩子内 6 处未引号展开（SC2086：空格路径分词/glob 风险）+ 2 处裸 `ls */target/...` 通配首破折号边缘（SC2035）。分发到下游任意路径的项目，属真实但低概率的面。

**证据**（shellcheck 0.11.0 gcc 格式实测）：

```
tools/git/lefthook/coverage.sh:150:49: note: Use ./*glob* or -- *glob* so names with dashes won't become options. [SC2035]
tools/git/lefthook/coverage.sh:153:18: note: Double quote to prevent globbing and word splitting. [SC2086]
tools/git/lefthook/coverage.sh:198:49: note: ... [SC2035]
tools/git/lefthook/coverage.sh:201:49: note: ... [SC2086]
tools/git/lefthook/coverage.sh:250:12: note: ... [SC2086]
tools/git/lefthook/mutation-gate.sh:25:21: note: ... [SC2086]
tools/git/lefthook/mutation-gate.sh:29:22: note: ... [SC2086]
tools/git/lefthook/mutation-gate.sh:33:22: note: ... [SC2086]
```

**复现**：`cd /tmp/ar-audit && shellcheck -f gcc tools/git/lefthook/*.sh tools/git/install.sh hooks/*.sh 2>/dev/null | grep -E 'SC2086|SC2035'`

**建议**：逐处加引号 / `--`；因属分发面且本仓无 lint 门覆盖（见发现 6），建议随发现 6 一并收口。

---

### 6｜tools/gauntlet.sh:241-250 + scripts/run_tests.sh:133｜🟡 次要（门禁覆盖缺口）

**问题**：仓自身 gauntlet 的 `syntax-sh-n`（:241-245）与 `lint-shellcheck`（:247-250）层清单均不含 `tools/git/install.sh` 与 `tools/git/lefthook/*.sh`（8 钩子）——**9 个分发 shell 脚本无任何语法/lint 门**；镜像清单 scripts/run_tests.sh:133 同口径。:246 注释只声明豁免了 `hooks/`（「hooks/ 属既有代码」），未提及 tools/git/ 的排除依据。缺口已被证实为活性：发现 4 的 SC2164 警告恰存在于该未门控集合内。这些脚本又恰是分发到下游仓、经 lefthook 在他人环境执行的面。

**证据**（gauntlet.sh:241-250 清单原文节选）：

```sh
    run_layer syntax-sh-n sh -n tools/gauntlet.sh tools/must_not_match.sh \
               tools/run_diff_cover.sh tools/test_gauntlet_orchestration.sh \
               tools/test_gauntlet_checks.sh tools/test_spec_check.sh \
               tools/test_pre-push-delete-guard.sh tools/test_dispatch_watch.sh \
               hooks/load-steering.sh hooks/on-session-end.sh
    # lint 范围只含本仓新增 tools/ 脚本：hooks/ 属既有代码，其基线告警不属本门范围；...
    run_layer lint-shellcheck shellcheck tools/gauntlet.sh tools/must_not_match.sh \
                tools/run_diff_cover.sh ... tools/test_dispatch_watch.sh
```

对照枚举：`ls tools/git/*.sh tools/git/lefthook/*.sh` → install.sh + 8 钩子共 9 个，均不在上列。

**复现**：

```sh
cd /tmp/ar-audit
comm -13 <(sed -n '241,250p' tools/gauntlet.sh | grep -oE '[a-z_/-]+\.sh' | sort -u) \
         <(ls tools/git/*.sh tools/git/lefthook/*.sh | sort)   # 9 个全部列出 = 均不在门内
```

**建议**：将 9 脚本并入两层层清单（若担心存量告警，可先修发现 4/5 再入门，与 hooks/ 的「基线豁免」处理方式保持显式记录）。是否有意豁免 → 见上报事项 R2。

---

### 7｜hooks/load-steering.sh:16｜🟡 次要

**问题**：SessionStart 钩子直接 `python3 - <<'PY'` 无 `command -v python3` 守卫；姊妹脚本 hooks/on-session-end.sh:9 有守卫（`command -v python3 >/dev/null 2>&1 || exit 0`）。python3 缺失/CLT 授权失效时，钩子以 rc=127 + 原始 stderr 报错，SessionStart 注入整体失败——同目录内环境降级策略不一致（一边静默放行、一边裸崩）。仓自身在 on-session-end.sh 已认定该前提须守卫，故非风格意见。

**证据**：

```sh
# hooks/load-steering.sh:16（无守卫）
python3 - "$STEERING_DIR" <<'PY'
# hooks/on-session-end.sh:9（有守卫）
command -v python3 >/dev/null 2>&1 || exit 0
```

**复现**：

```sh
cd /tmp/ar-audit
grep -n 'command -v python3\|^python3' hooks/load-steering.sh hooks/on-session-end.sh
env PATH="/usr/bin:/bin" bash hooks/load-steering.sh >/dev/null  # 视机器而定；守卫缺失可直接目验
```

**建议**：load-steering.sh 第 16 行前补同款守卫（放行 + 可选 stderr 提示），或改为输出空 additionalContext 的降级路径。

---

## 待验证

1. **四个自测大脚本的逐行深度未覆盖**：test_gauntlet_checks.sh（约千行）、test_gauntlet_orchestration.sh、test_spec_check.sh、test_pre-push-delete-guard.sh 仅做了 bash -n + shellcheck 级验证（全绿）与抽样上下文阅读；未逐行审读。风险面低（set -e、非分发面、失败即红），但按纪律声明覆盖深度。
2. **发现 1/2 的受影响人群边界**：Homebrew bash ≥5 在 PATH 前列的用户不受影响（bash 4.1+ 已修复多字节变量名扫描）；受影响 = stock macOS（PATH 无 brew bash）+ UTF-8 locale（macOS 默认）。未对真实下游仓人群做抽样统计。
3. **发现 4 的触发现实性**：lefthook 在目标仓内调用时 `git rev-parse --show-toplevel` 常态有效，cd 失败仅限 cwd 被删/REPO 为空等异态；未构造端到端失败场景实证后续命令的具体走向（静默跳过 vs 误判），按代码路径推断为「错误 cwd 下继续执行」。

## 上报事项

**R1｜testing-standards.md:261【强制】条款与分发钩子实现的适用边界冲突（不自行裁定）**

- 条款原文（steering/testing-standards.md:261）：「门禁脚本 fail-closed：`set -e`、禁 `|| true` / `2>/dev/null`、启动即清旧产物；grep 退出码显式分支」
- 实现现状（tools/git/lefthook/*，分发面）：一律 `set -u` 无 `-e`（8/8）；`|| true` 与 `2>/dev/null` 大量使用（如 mutation-gate.sh:19 `... || true`、:22 `>/dev/null 2>&1 || true`、:46；coverage.sh:29 `2>/dev/null || true`）；且钩子头注明示相反设计意图，如 commitmsg-check.sh:5「无 node/npm 时提示后放行 —— commit 钩子不阻塞环境问题，只拦规范违规」——环境问题 fail-open 是分发钩子的显式设计目标。
- 冲突点：条款未区分「本仓门禁」与「分发到下游的钩子」两个面；若条款适用分发面，则 8 个钩子全体违规（须加 set -e 并清除全部 || true）；若不适用，条款应写明适用边界。发现 1 的修复（花括号化）不受该裁定影响，但「是否同时补 set -e」取决于此。请人工终裁。

**R2｜gauntlet lint/语法层排除 tools/git/ 是有意豁免还是清单漂移**

- gauntlet.sh:246 注释为 lint 范围给出的边界是「本仓新增 tools/ 脚本 + hooks/ 属既有代码豁免」，未提 tools/git/；而 tools/git/ 恰是唯一持续分发到外部环境执行的 shell 面。若为有意豁免，建议在注释中补记理由（与 hooks/ 同等待遇显式化）；若为漂移，见发现 6 建议。请仓主裁决。

## 覆盖声明

**范围全量枚举（非抽样）**：

- 命令：`find tools hooks -name '*.sh' | sort`（20 个：tools/ 下 18 = tools/ 根 10 + tools/git/install.sh + tools/git/lefthook/ 8；hooks/ 下 2）；`find tools -name '*.py' | sort`（17 个）；`ls .github/workflows/`（3 个）；`ls hooks/`（hooks.json、load-steering.sh、on-session-end.sh、omp/skill-evo.ts）；`ls tools/git/`（install.sh、lefthook.yml、README.md）
- 逐文件审读：20 .sh 全读或按检查点扫描 + 分发钩子/install.sh/gauntlet 层清单/run_diff_cover/must_not_match/dispatch_watch 主体全读；17 .py 结构化全扫 + 4 个检查器（spec_check / check_factory_portability / check_git_sealing / frontmatter_lib 调用面）深读；3 workflow 全读；hooks 4 项全读；tools/git 3 项全读
- hooks/omp/skill-evo.ts：仅存在性枚举，未深审（TypeScript，非本维度 shell/python 主体），声明覆盖深度

**检查点与命令结果**：

| 检查点 | 命令（在 /tmp/ar-audit 下） | 结果 |
|---|---|---|
| 全角邻接扫描 | `for f in $(find tools hooks -name '*.sh'); do perl -ne 'print "$.: $_" if /\$[A-Za-z_][A-Za-z0-9_]*[\x80-\xff]/' "$f"; done` | 7 命中：commitmsg-check.sh:27、coverage.sh:184/225/235/241、test_dispatch_watch.sh:91、test_gauntlet_checks.sh:955（注释）→ 发现 1/2/3 |
| bash 3.2 语法兼容 | `rg -n 'mapfile\|readarray\|declare -A\|\$\{[a-zA-Z_]+,,\}\|&>>\|coproc' tools hooks .github` | tools/hooks 零命中；workflows 的 mapfile 在 ubuntu（bash≥4）且有注释在案，非违规 |
| 语法解析 | `for f in $(find tools hooks -name '*.sh'); do /bin/bash -n "$f"; done` | 20/20 通过 |
| shellcheck 全量 | `shellcheck -f gcc <20 个 .sh>`（全文存 /tmp/sc_full.txt） | 13 条：SC2164×2（→发现 4）、SC2086×6 + SC2035×2（→发现 5）、SC2004×2（纯风格，不报）、SC1091×1（动态 source，不报） |
| set 指令盘点 | `rg -n '^set -' tools hooks` | install.sh=−euo pipefail；8 钩子+dispatch_watch=−u only；gauntlet/run_diff_cover/test_*（#!/bin/sh）=−e；must_not_match=被 source 无 set；hooks 两脚本=无 set |
| Python 入口守卫 | `rg -c '__main__' tools/*.py` + 顶层调用扫描 | 15 入口全有 `if __name__` 分发；frontmatter_lib.py 为库；顶层副作用调用 0 |
| Python 吞错扫描 | `rg -n -U 'except[^:\n]*:\s*\n\s+(pass\|continue\|return 0\|sys\.exit\(0\))' tools --type py` | 1 命中 spec_check.py:87 TokenError pass——经核 docstring :61-63 为**文档化的有意降级**（截断文件保留已收集标签，缺口方向 fail-closed，条款按 GAP 拦），不构成发现；check_factory_portability.py:61/79、check_git_sealing.py:64 的 `except Exception` 均接 `_fail_closed`（sys.exit 非零），正确 |
| set -u + 零参 `"$@"` | 构造 `/bin/bash -c 'set -u; set --; for x in "$@"; do :; done; echo ok'` | bash 3.2 下正常（sourcery-gate.sh:28 无风险，排除） |
| 空数组展开 | mutation-gate.sh:46 已用 `${PL[@]+"${PL[@]}"}` 惯用法 | 正确（排除） |
| install.sh ↔ tools/git/README.md | DIST 数组（:36-49，12 项）与 README:31 清单逐项比对；--check 语义（README:59-63 ↔ install.sh:57-84）；hook 安装/hooksPath/旧 hook 清理（:156-189 ↔ README:48）；根 lefthook.yml 自用变体 wiring ↔ README:124-127 | 全部一致，无发现 |
| 根 README 声称 | `grep -n -i 'tools/git\|install.sh\|lefthook' README.md` | 仅 skills 表格一处提及 lefthook pre-push，无 tools/git 安装相关声称，无发现 |
| workflows 专项 | 3 文件全读 + `head -1 \|\| true`（config-evals-gate.yml:133）核对 testing-standards.md:271 适用条件 | GHA 默认 shell（bash -e，无 pipefail）不在 :271 条款「启用 pipefail 的脚本」范围内，且 rc 有显式分支兜底 → 不报 |

**明确排除项（查证后不构成发现）**：SC2004×2（风格）、SC1091×1（动态 source 不可避免）、workflows mapfile（ubuntu bash≥4 注释在案）、workflows `head -1 || true`（无 pipefail 语境）、`"$@"` set -u（实测安全）、spec_check.py TokenError（文档化 fail-closed 降级）、Python 入口模式（全合规，CLAUDE.md:24 事故模式在当前 tools/ 不成立）、install.sh/lefthook/README 三方一致性（核对一致）。

**只读声明**：审查全程未修改 /tmp/ar-audit 内任何文件、未执行任何 git 写操作；全部测试产物（fw_test.sh、su_test.sh、f1stub 等）仅落盘 /tmp 树外路径。收尾核验：`git -C /tmp/ar-audit status --short` → 空。

**干扰声明**：本会话期间 claude-mem 注入的并行维度（C 文档一致性 / D 门禁覆盖度 / A 强制条款普查）观察记录与本维度无关，未采信为 B 维度证据；其中对本会话的转述与自采程序化证据不一致处（如 coverage.sh 命中数 3 vs 实测 4），以本文程序化扫描结果为准。
