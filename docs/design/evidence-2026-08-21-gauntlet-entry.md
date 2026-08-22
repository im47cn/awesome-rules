# EVIDENCE: awesome-rules 单一门禁入口 tools/gauntlet.sh

- **日期**: 2026-08-21
- **Spec approval**: 已批准（用户原话："批准，开始 RED→GREEN→GAUNTLET→EVIDENCE"，SPEC 内有记录）
- **Source state**（以文件 sha256 前 16 位标识；2026-08-22 提交前重算）:

  | 文件 | sha256（前 16 位） |
  |---|---|
  | tools/gauntlet.sh | 21b363600884b785 |
  | tools/must_not_match.sh | 5982aa2d1c2b5c01 |
  | tools/test_gauntlet_orchestration.sh | 63655b8a80b2bfbc |
  | tools/test_gauntlet_checks.sh | d2e5b7dea429be6c |
  | tools/mutants_gauntlet.py | 75d83e4c7af4f42e |

  注：gauntlet.sh 初记 f8b0f2620c9b45ad 与终值不同，系初算早于其末次编辑；本表为提交时终值。

- **Toolchain**: /bin/sh（bash 3.2.57, POSIX 模式）、pytest 9.0.2 + pytest-cov（CPython 3.14.7，/opt/homebrew）、shellcheck 0.11.0、BSD grep
- **Entry point**: `sh tools/gauntlet.sh`

## Spec → Test 映射

| SPEC 场景 | 验证 | 状态 |
|---|---|---|
| 全绿通过（rc=0 + PASS 标记） | T1（test_gauntlet_orchestration.sh）+ 最终全量运行 | pass |
| 任一层失败整体失败 + 失败层可见 | T2 | pass |
| 层清单缺失硬失败（防漂移） | T3 | pass |
| 死链负控制（md_link_check 会拦） | NC1（test_gauntlet_checks.sh） | pass |
| 秘密负控制（must_not_match 会拦） | NC2（断言 rc=1，区分检查器损坏） | pass |
| 不读陈旧产物（启动清理） | T4 | pass |
| （追加）grep rc=1 好路径不被 errexit 吞 | NC3（真实 set -e 子进程上下文） | pass |
| Must NOT: 零现有文件行为变更 | git status：仅 README.md/steering 索引性修改 + 6 个新增文件；全部 9 个 pytest 套件计数与基线逐一相同 | pass |
| Must NOT: 零新依赖 | 实现仅 POSIX sh + 既有 python/pytest/shellcheck | pass |

## GAUNTLET（最终全新运行，最后一次代码编辑之后）

`sh tools/gauntlet.sh` → **rc=0，15 层全部 PASS**：

| 层 | 结果 |
|---|---|
| orchestration-self-test | T1-T4 4/4 通过 |
| checker-self-test | NC1-NC3 3/3 通过 |
| pytest-scripts | 9 passed |
| pytest-factory | 32 passed |
| pytest-api-guard | 88 passed（覆盖率 100%，fail-under 90 达标） |
| pytest-ddl-guard | 126 passed（覆盖率 95.59% ≥ 90） |
| pytest-arch-guard | 144 passed（覆盖率 96.98% ≥ 90） |
| pytest-impact-guard | 62 passed |
| pytest-skill-evo | 78 passed |
| pytest-doc-gen | 316 passed |
| pytest-arch-hawkeye | 72 passed |
| md-link-check | 115 个 .md 链接/锚点全有效，README 索引零漂移 |
| must-not-secrets | 全仓扫描 0 命中（范围：scripts/tools/hooks/skills/arch-hawkeye/.factory/.github，排除生成产物树） |
| syntax-sh-n | 6 个脚本语法通过 |
| lint-shellcheck | tools/ 4 脚本 0 告警 |

**测试合计 927 passed**（9+32+88+126+144+62+78+316+72），与基线逐套件相同：零新增失败。

**手动变异**（`python3 tools/mutants_gauntlet.py`）：**4/4 KILLED**——
M1 run_layer 吞层失败 / M2 require_dir 失效 / M3 陈旧产物不清理 / M4 grep 分支互换，全部被对应自测击杀；每变异经字节级读回比对还原。

## NC1 非空洞性一次性证明

对 `md_link_check.py` 注入一次性变异（`if not resolved.exists():` → `if False and ...`），NC1 变红（输出缺 `no-such-target`）；字节级还原后复绿。NC1 记录为既有行为的回归护甲。

## 未运行的层

| 层 | 类别 | 原因 |
|---|---|---|
| 静态类型 | N-A | 纯 shell 编排脚本 |
| 变更行覆盖率 | N-A | 同上；以层判定语义测试（T1-T4/NC1-NC3 + 变异）替代 |
| 属性测试 | N-A | 无不变量密集逻辑 |
| 套件随机顺序 | UNAVAILABLE | 本机未装 pytest-randomly；确定性由基线=终跑逐套件同数佐证 |
| 独立验证 | not performed | Tier 2 不要求；未启动 verifier 轮次 |

## 结构性盲点

- 层清单防漂移只锁**目录**存在性，不锁目录内文件（某测试文件被删不会硬失败，但该套件测试数下降会在与基线对比时暴露——目前对比是人工的）
- 变异集 4 条，覆盖门的四类语义（退出码传递/防漂移/产物清理/分支极性），不声称覆盖所有可破坏点
- must-not 模式锚定"凭据名+赋值+引号内≥8字符"，无引号/环境变量形态的凭据不在拦截面

## 诚实记录：过程中的失败与修复

1. **门三次拦截了真实问题**（这正是它存在的意义）：
   - md-link-check 层拦下 SPEC 文件未登记 README 索引 → 补登修复
   - must-not 层拦下 vendored scalar.js 的字段名误报 → 模式/范围修正（理由陈述在代码注释）
   - lint-shellcheck 层拦下我自己刚写的 `# shellcheck` 开头注释（被当指令解析）→ 改措辞
2. **must_not_match 的 errexit 缺陷**：裸 grep 在无匹配（rc=1 好路径）时被调用方 `set -e` 杀死整层；直接调用因 `&&`/`if` 上下文豁免而漏检，全量运行才暴露。修复（`|| _rc=$?` 显式捕获）+ NC3 回归测试（真实子进程上下文，`if` 上下文豁免使其无法复现——这一点写进了测试注释）。讽刺且有益：该缺陷恰违反本仓新条款"检查器 fail-closed"的精神
3. **NC2 曾以错误原因通过**：BSD grep 把 `--` 之后的 `--include` 当文件操作数（rc=2 检查器损坏），早期 NC2 只断言非零、与真拦截不可区分 → 收紧为只认 rc=1，先观察变红再修实现
4. **负控制夹具自匹配**：夹具 heredoc 字面量被全仓扫描命中 → `$K` 拼接构造，与模式 `[e]` 括号防自匹配同一原则
5. **测试脚本自身两次踩 bash 3.2 陷阱**：命令替换失败触发 set -e 杀死测试（受控捕获修复）、`$rc，` 多字节吞字节（`${rc}` + ASCII 标点，已知问题 #17838）
6. 早期对话中"基线 1027"为口算错误，正确基线 927，已与终跑逐套件核对

## 可复现性

- 单入口：`sh tools/gauntlet.sh`
- 变异冒烟：`python3 tools/mutants_gauntlet.py`
- 负控制/编排自测：`sh tools/test_gauntlet_checks.sh`、`sh tools/test_gauntlet_orchestration.sh`（也是 gauntlet 第 1、2 层）
- 解释器探测：自动回退 `/opt/homebrew/bin/python3`（系统 /usr/bin/python3 缺 pytest-cov，探测失败痕迹会打印在 stderr——诚实噪音，非吞错）
