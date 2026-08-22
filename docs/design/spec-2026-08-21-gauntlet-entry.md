# SPEC: awesome-rules 单一门禁入口 tools/gauntlet.sh

- **Tier**: 2（常规小功能，纯新增文件，零行为变更）
- **日期**: 2026-08-21
- **Spec approval**: 已批准（2026-08-21，用户原话："批准，开始 RED→GREEN→GAUNTLET→EVIDENCE"）

## 动机

本仓测试分散于 7+ 个目录（`scripts/tests`、`.factory/tests`、`skills/*/scripts/tests`、`arch-hawkeye/scripts/tests`），无单入口；`steering/testing-standards.md` 新增的「自建关卡脚本的反作弊要求」条款（负控制 / tripwire / 退出码语义）需要落地载体。

## 验收场景

```gherkin
Feature: tools/gauntlet.sh 单一门禁入口

  Scenario: 全绿通过
    Given 仓库所有测试套件与检查均通过
    When 执行 sh tools/gauntlet.sh
    Then 退出码为 0，且输出中每个层名均带 PASS 标记

  Scenario: 任一层失败则整体失败
    Given 任一层（如某个 pytest 套件）失败
    When 执行 sh tools/gauntlet.sh
    Then 退出码非零，且输出指明失败层名

  Scenario: 层清单防漂移（fail-closed）
    Given 显式层清单中的某个测试目录不存在（如技能被移除/改名）
    When 执行 sh tools/gauntlet.sh
    Then 硬失败（非零退出码 + 明确报错），而非静默跳过该层

  Scenario: 负控制——死链检查器会失败
    Given 一个含死链的临时 markdown 文件
    When checker-self-test 层以该文件运行 scripts/md_link_check.py
    Then 该子检查判定失败（证明 md_link_check 层会拦，不是只放行）

  Scenario: 负控制——秘密扫描会失败
    Given 一个含假 API key 字面量的临时文件
    When checker-self-test 层对其运行 must-not 扫描
    Then 该子检查判定失败

  Scenario: 不读取陈旧产物
    When gauntlet.sh 启动
    Then 先删除旧运行产物（各目录 .coverage 等），再开始执行各层
```

## Must NOT（负面约束）

- 不修改任何现有脚本/测试的行为——本任务只新增文件
- 不引入任何新依赖——仅 POSIX `sh`、`python3`、仓库现有 pytest
- 不使用 `|| true`、`2>/dev/null` 或裸 fallthrough 吞错
- 现有测试基线零新增失败（先记录基线）
- grep 退出码显式分支：1=无匹配即通过，0=命中即失败，≥2=检查自身损坏即失败

## 层清单（显式，缺任一即硬失败）

1. checker-self-test：负控制（死链 fixture、假秘密 fixture 各自必须被拦）
2. pytest 套件：`scripts/tests`、`.factory/tests`、`skills/api-guard/scripts`（用其 pytest.ini）、`skills/ddl-guard/scripts`、`skills/arch-guard/scripts`、`skills/impact-guard/scripts/tests`、`skills/skill-evo/scripts/tests`、`skills/doc-gen/scripts/tests`、`arch-hawkeye/scripts/tests`
3. 真实执行：`scripts/md_link_check.py` 全仓扫一遍
4. must-not 扫描：秘密模式 grep（含 CI 配置目录；`[e]` 括号防自匹配）

## Setup plan

- 新增文件（by path）：`tools/gauntlet.sh`（入口 + 层编排）、`tools/test_gauntlet_checks.sh`（checker 自测，作为第 1 层运行）
- 无工具安装、无新依赖、无环境变更
- **Git 策略**：遵循用户全局规则（未主动要求不做 git 操作）——不建分支、不做检查点提交；SPEC/EVIDENCE 以工作树文件为准，源状态用 tree hash 标识。此为声明性降级：变异恢复的验证依赖读回比对 + 重跑套件，弱于 `git diff`
- 隔离机制：无（Tier 2 纯新增文件，不触碰现有代码，风险仅限新增文件本身）

## 预期 GAUNTLET 校准

| 层 | 计划 |
|---|---|
| 全量测试 | 由入口自身聚合（即本任务本体） |
| 静态类型 | N/A（shell 脚本） |
| Lint | `sh -n` 语法检查；shellcheck 若环境有则跑（无则记录 UNAVAILABLE） |
| 覆盖率 | N/A（编排脚本，无逻辑分支密度；以层判定语义测试替代） |
| 变异 | 手动变异 3-5 个：破坏 run_layer 的退出码传递 / 删负控制子检查 / grep 分支翻转，self-test 与场景测试必须抓到每一个 |
| 属性测试 | N/A（无不变量密集的逻辑） |
| 真实执行 | 即层 3 |
| 供应链 | 无新依赖，扫描即层 4 |
| 套件健康 | 各 pytest 套件重跑一次确认确定性 |

## Revisions

（append-only）
