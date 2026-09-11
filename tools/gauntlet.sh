#!/bin/sh
# Gauntlet 入口：跑完所有层，第一个坏层即失败。
# 语义契约：tools/test_gauntlet_orchestration.sh（编排自测）、
# tools/test_gauntlet_checks.sh（检查器负控制）、
# steering/testing-standards.md「自建关卡脚本的反作弊要求」。
#
# doctor 模式（tools/gauntlet.sh doctor）：环境自诊断，不跑层、不清产物——
# 逐项报告门禁层的外部依赖与层清单目录，跑门禁前先区分「环境坏了」与
# 「代码坏了」。任一项 FAIL 即退出非零，无降级。
#
# .factory/ shell 门（syntax-factory-sh / lint-factory-shellcheck /
# lint-factory-inline-python）：2026-08-22 feedback 事故后补——适配
# 节点产出的 BRANCH 未定义（SC2154）缺陷逃过纯 pytest 门禁
# （scripts/run_tests.sh）。上游门禁应以本脚本为准；shell 层是其
# 严格超集，pytest 层两者等价（同一套件清单）。
set -e
cd "$(dirname "$0")/.."

# ── 共用函数与层目录清单 ─────────────────────────────────────────────────
# 解释器解析（主路径与 doctor 共用，经 stdout 返回，无候选输出空串）：
# GAUNTLET_PY 显式指定时同样做 import 自检，无效即空——不静默回退到
# 其他候选（显式指定优先，fail-closed）。
find_py() {
    if [ -n "${GAUNTLET_PY:-}" ]; then
        if "${GAUNTLET_PY}" -c 'import pytest, pytest_cov' >/dev/null 2>&1; then
            echo "${GAUNTLET_PY}"
        fi
        return 0
    fi
    for _cand in "$(command -v python3)" /opt/homebrew/bin/python3; do
        if [ -n "$_cand" ] && "$_cand" -c 'import pytest, pytest_cov' >/dev/null 2>&1; then
            echo "$_cand"
            return 0
        fi
    done
    return 0
}

run_layer() {
    _name=$1
    shift
    echo "== ${_name}"
    "$@"
    echo "   PASS ${_name}"
}

require_dir() {
    # 层清单防漂移：目录缺失（技能移除/改名）是硬失败，不是静默跳层
    for _d in "$@"; do
        if [ ! -d "$_d" ]; then
            echo "gauntlet: 层清单漂移——目录缺失: ${_d}（须同步更新 gauntlet.sh 层清单）" >&2
            exit 2
        fi
    done
}

# 层清单目录：主路径 require_dir 与 doctor 逐项报告共用（单一事实源，
# 两处引用防漂移——新增层目录只改这里）
LAYER_DIRS='scripts .factory
skills/api-guard/scripts skills/ddl-guard/scripts skills/arch-guard/scripts
skills/impact-guard/scripts/tests skills/skill-evo/scripts/tests
skills/doc-gen/scripts/tests arch-hawkeye/scripts/tests'


# ── doctor 模式：环境自诊断，不跑层、不清产物 ───────────────────────────
# 与门禁语义互补：门禁 fail-closed 首坏即断；doctor 逐项报全量再汇总，
# 任一 FAIL 退出非零（无降级）。检查面 = 层的外部依赖 + 层清单目录 +
# 仓库健康（裸仓是 2026-08-27 实证事故形态），不重复检查代码正确性。
case ${1:-} in
doctor)
    _dfail=0
    _py=$(find_py)
    if [ -n "$_py" ]; then
        echo "  OK   解释器: ${_py}（pytest+pytest_cov）"
    else
        echo "  FAIL 解释器: ${GAUNTLET_PY:+GAUNTLET_PY=${GAUNTLET_PY} 未过 }import 自检，且无带 pytest+pytest_cov 的候选" >&2
        _dfail=$((_dfail + 1))
    fi
    if command -v shellcheck >/dev/null 2>&1; then
        echo "  OK   shellcheck: $(command -v shellcheck)"
    else
        echo "  FAIL shellcheck: 未安装（lint-shellcheck / lint-factory-shellcheck 层依赖）" >&2
        _dfail=$((_dfail + 1))
    fi
    if command -v bash >/dev/null 2>&1; then
        echo "  OK   bash: $(command -v bash)"
    else
        echo "  FAIL bash: 未安装（syntax-factory-sh 层依赖）" >&2
        _dfail=$((_dfail + 1))
    fi
    # diff-cover 经解释器入口调用（非 PATH console script），doctor 用同一
    # 解释器自检（diff-cover 层依赖）
    if [ -n "$_py" ] && "$_py" -c 'import coverage, diff_cover' >/dev/null 2>&1; then
        echo "  OK   diff-cover: ${_py} 可用"
    else
        echo "  FAIL diff-cover: ${_py:-解释器缺失} 缺 coverage/diff_cover 包（pip install diff-cover）" >&2
        _dfail=$((_dfail + 1))
    fi
    if command -v git >/dev/null 2>&1; then
        echo "  OK   git: $(command -v git)"
    else
        echo "  FAIL git: 未安装（FACTORY_SH 枚举与 git-sealing 层依赖）" >&2
        _dfail=$((_dfail + 1))
    fi
    # 裸仓下 git 子命令部分可用但工作区行为异常（2026-08-27 实证：
    # core.bare 被置 true，hermetic 套件 4 例连带失败）
    if [ "$(git rev-parse --is-bare-repository 2>/dev/null)" = false ]; then
        echo "  OK   仓库: 非裸仓"
    else
        echo "  FAIL 仓库: 非仓或裸仓状态（git rev-parse 不可用/失败）" >&2
        _dfail=$((_dfail + 1))
    fi
    # shellcheck disable=SC2086  # 层目录按词展开
    for _d in $LAYER_DIRS; do
        if [ -d "$_d" ]; then
            echo "  OK   目录: ${_d}"
        else
            echo "  FAIL 目录: ${_d}（层清单漂移，须同步 gauntlet.sh 层清单）" >&2
            _dfail=$((_dfail + 1))
        fi
    done
    if [ -n "$(git ls-files -- '.factory/*.sh' 2>/dev/null)" ]; then
        echo "  OK   tracked .factory/*.sh 非空"
    else
        echo "  FAIL tracked .factory/*.sh 为空（层清单漂移）" >&2
        _dfail=$((_dfail + 1))
    fi
    if [ "$_dfail" -eq 0 ]; then
        echo "doctor: 环境健康，可运行 tools/gauntlet.sh"
        exit 0
    fi
    echo "doctor: ${_dfail} 项异常（见上方 FAIL 行）" >&2
    exit 1
    ;;
'')
    ;;
*)
    echo "gauntlet: 未知参数 '${1}'（用法: tools/gauntlet.sh [doctor]）" >&2
    exit 2
    ;;
esac

# ── 解释器探测 ─────────────────────────────────────────────────────────
# 3 个带 --cov addopts 的 pytest.ini 在缺 pytest-cov 的解释器下收集期即报错。
# 探测不到即硬失败，绝不静默降级为跳过这些层。
PY=$(find_py)
if [ -z "$PY" ]; then
    echo "gauntlet: 找不到带 pytest+pytest_cov 的解释器（GAUNTLET_PY 可显式指定）" >&2
    exit 2
fi

# ── 陈旧产物清理 ───────────────────────────────────────────────────────
# 上次运行的 .coverage / __pycache__ 既是 must-not 扫描的 grep 噪音，
# 也可能被当成新结果读取——启动即清，不读取任何先前输出。
find . -name '.coverage*' -type f -not -path './.git/*' -delete
find . -name __pycache__ -type d -prune -not -path './.git/*' -exec rm -rf {} +

# ── 层清单 ─────────────────────────────────────────────────────────────
# GAUNTLET_LAYERS_FILE：编排自测的受控入口（helpers 已就绪后 source），
# 不设该变量时走默认全量清单。
if [ -n "${GAUNTLET_LAYERS_FILE:-}" ]; then
    # shellcheck disable=SC1090
    . "$GAUNTLET_LAYERS_FILE"
else
    run_layer orchestration-self-test sh tools/test_gauntlet_orchestration.sh
    run_layer checker-self-test sh tools/test_gauntlet_checks.sh
    run_layer spec-check-self-test sh tools/test_spec_check.sh
    run_layer delete-guard-self-test sh tools/test_pre-push-delete-guard.sh

    # shellcheck disable=SC2086  # 层目录按词展开
    require_dir $LAYER_DIRS

    run_layer pytest-scripts "$PY" -m pytest scripts -q
    # 收集面收窄到 tests/（issue #166）：整个 .factory 会扫进 .factory/worktrees/*
    # 链工作树全仓副本（副本内 skills/*/tests 依赖各自 rootdir conftest，
    # 在 .factory rootdir 下收集即 import 失败）→ rc=2 短路后续所有层。
    # .factory 的 pytest 套件本就全在 tests/（scripts/run_tests.sh SUITES
    # 同口径），窄面即对齐两处维护点。
    run_layer pytest-factory "$PY" -m pytest .factory/tests -q
    # 3 个带 --cov 的套件各写独立 COVERAGE_FILE（.coverage.<suite>）：既保各套件
    # 自身 --cov-fail-under 的独立评估面不被跨套件数据稀释（评审 F1），又供
    # diff-cover 层 combine 汇总（分产物合计，单套件产物会漏掉其余两个的变更行）
    run_layer pytest-api-guard env COVERAGE_FILE="$PWD/.coverage.api-guard" \
        "$PY" -m pytest skills/api-guard/scripts -q
    run_layer pytest-ddl-guard env COVERAGE_FILE="$PWD/.coverage.ddl-guard" \
        "$PY" -m pytest skills/ddl-guard/scripts -q
    run_layer pytest-arch-guard env COVERAGE_FILE="$PWD/.coverage.arch-guard" \
        "$PY" -m pytest skills/arch-guard/scripts -q
    run_layer pytest-impact-guard "$PY" -m pytest skills/impact-guard/scripts/tests -q
    run_layer pytest-skill-evo "$PY" -m pytest skills/skill-evo/scripts/tests -q
    run_layer pytest-doc-gen "$PY" -m pytest skills/doc-gen/scripts/tests -q
    run_layer pytest-arch-hawkeye "$PY" -m pytest arch-hawkeye/scripts/tests -q
    run_layer plugin-versions "$PY" tools/check_plugin_versions.py
    # 实现↔文档一致性（数字/清单/指向漂移，R1-R9 语义见脚本头注释）
    run_layer doc-freshness "$PY" tools/check_doc_freshness.py
    run_layer md-link-check "$PY" scripts/md_link_check.py .
    # 变更行覆盖率门（steering/testing-standards.md「覆盖率门禁与『覆盖率阈值』
    # 同口径」「本地自验须与门禁同口径」两条的机械化落地）：增量 diff-cover
    # 对 origin/main 核算，阈值 90%（非 Java 线）。度量边界：只核算 coverage
    # 报告中的文件，未带 --cov 套件的变更行不在本门面内。负控制 NC19。
    run_layer diff-cover env GAUNTLET_PY="$PY" DIFF_COVER_BASE=origin/main \
        sh tools/run_diff_cover.sh

    layer_must_not_secrets() {
        # shellcheck disable=SC1091
        . tools/must_not_match.sh
        must_not_match "$SECRET_PATTERN" scripts tools hooks skills arch-hawkeye .factory .github
    }
    run_layer must-not-secrets layer_must_not_secrets

    run_layer syntax-sh-n sh -n tools/gauntlet.sh tools/must_not_match.sh \
               tools/run_diff_cover.sh tools/test_gauntlet_orchestration.sh \
               tools/test_gauntlet_checks.sh tools/test_spec_check.sh \
               tools/test_pre-push-delete-guard.sh \
               hooks/load-steering.sh hooks/on-session-end.sh
    # lint 范围只含本仓新增 tools/ 脚本：hooks/ 属既有代码，其基线告警不属本门范围；清单镜像于 scripts/run_tests.sh lint-shellcheck 层，两处同步维护
    run_layer lint-shellcheck shellcheck tools/gauntlet.sh tools/must_not_match.sh \
                tools/run_diff_cover.sh tools/test_gauntlet_orchestration.sh \
                tools/test_gauntlet_checks.sh tools/test_spec_check.sh \
                tools/test_pre-push-delete-guard.sh

    # ── .factory/ shell 门（2026-08-22 feedback 事故后补） ─────────────
    # 事故：feedback 适配节点产出 BRANCH 未定义（SC2154）的 fix-issue.sh，
    # run_tests.sh 纯 pytest 门禁全绿放行。三层封堵：
    # 扫描面 = tracked .factory/*.sh（2026-08-23 结构性修复）：手工清单
    # 与目录内容必然漂移——factory-lib.sh（链共享收口库）、feedback-upstream.sh、
    # cron-dispatch.sh 曾全部漏扫。tracked 面后新增链脚本自动入门。
    FACTORY_SH=$(git ls-files -- '.factory/*.sh')
    [ -n "$FACTORY_SH" ] || { echo "gauntlet: tracked .factory/*.sh 为空（层清单漂移）" >&2; exit 1; }
    # shellcheck disable=SC2016  # $1 刻意由内层 sh 展开（外层单引号防本层展开）
    run_layer syntax-factory-sh sh -c 'for f in $1; do bash -n "$f" || exit 1; done' \
        sh "$FACTORY_SH"
    # -S warning：SC2154 正是事故形态（引用未赋值变量），不允许降级
    # shellcheck disable=SC2016  # 同上：$1 由内层 sh 展开
    run_layer lint-factory-shellcheck sh -c 'shellcheck -S warning $1' \
        sh "$FACTORY_SH"
    # hooks 纳入（2026-08-28）：load-steering.sh 的 heredoc python 与
    # .factory 同面受 compile 门（此前仅 sh -n 语法门）
    run_layer lint-factory-inline-python "$PY" tools/check_inline_python.py .factory tools scripts hooks
    # 管道早退静态门（issue #30 三犯成类）：pipefail 下非末位早退消费者
    # （grep -m/head）与 true 管道段。扫描面 = tracked *.sh（67c2965b 原则）
    run_layer lint-pipe-early-exit "$PY" tools/check_pipe_early_exit.py \
        .factory tools scripts hooks skills arch-hawkeye .github
    # 进程组信号平台语义门（PR #36 flake 沉淀，约定见 steering/testing-standards.md
    # 「进程组信号的平台语义」）：os.killpg 缺 EPERM 容忍 / raises 单发探活。
    # 扫描面 = tracked *.py（67c2965b 原则）
    run_layer lint-killpg-strict "$PY" tools/check_killpg_strict.py \
        .factory tools scripts hooks skills arch-hawkeye .github
    # 测试 tempdir 枚举静态门（PR #137 泄漏断言隔离的防回归面；该未隔离
    # 形态已扩散 8 个下游仓）：测试进程 gettempdir()/对 /tmp 字面量直接
    # glob/listdir 枚举的是系统共享目录，套件外写者随机打破差集断言——
    # 须走 conftest private_tmp 夹具注入（范式 .factory/tests/conftest.py）。
    # 扫描面 = tracked 测试文件（test_*.py / conftest.py）。负控制 NC17。
    run_layer lint-tempdir-isolation "$PY" tools/check_tempdir_usage.py \
        .factory tools scripts hooks skills arch-hawkeye .github
    # 托管平台出口收口门（ADR-007 层级契约）：零 gh 直调 + issue 副作用
    # 经 factory-lib 收口（hosting.py 仅传输层）。负控制 NC12。
    run_layer lint-factory-hosting-exit "$PY" tools/check_hosting_exit.py .
    # 工厂本地化配置有效性门（M4 本地化外置，设计 §11.3）：
    # factory-local.json = guard.py PERIMETER 与 REJECT_GUIDANCE 的数据载体。
    # JSON 可解析 + 必需键 + guard 实际加载自检（含 MISSION 一致性）。
    # 缺文件也拦——周界门不能在配置缺失下静默放行（fail-closed）。
    run_layer factory-local-validity "$PY" -c 'import sys
sys.path.insert(0, ".factory")
import guard, factory_lib
n = len(guard.PERIMETER)
assert n > 0 and len(factory_lib.REJECT_GUIDANCE) == 3, "配置载入不完整"
# ADR-009 新键：门命令与 prompt 仓库参数必须可渲染（fail-closed 面前移到门）
assert factory_lib.final_gate_cmd().strip(), "final_gate_cmd 为空"
rv = factory_lib.repo_vars_text()
assert "final_gate" in rv and "阅读范围" in rv, "repo_vars 渲染不完整"
print(f"factory-local-validity: perimeter {n} 条 / guidance a,b,c / final-gate+repo-vars 就绪")'
    # 拆分就绪门（ADR-009）：full 面 + prompts 零宿主专名（P1）、omp 单点
    # （P2）、无平铺 path hack（P3）。负控制 NC13。
    run_layer factory-portability "$PY" tools/check_factory_portability.py .
    # 测试 git 密封门（ADR-010）：conftest 密封（R1）/ shell 测试密封（R2）/
    # 负控制登记表完备（R3）。负控制 NC14。规范事实源 =
    # steering/testing-standards.md §测试密封性；两次事故 2026-08-22 /
    # 2026-08-27（PR #71 附记四）。
    run_layer git-sealing "$PY" tools/check_git_sealing.py .
fi

echo "gauntlet: 全部层通过"
