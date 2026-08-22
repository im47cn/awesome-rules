#!/bin/sh
# Gauntlet 入口：跑完所有层，第一个坏层即失败。
# 语义契约：tools/test_gauntlet_orchestration.sh（编排自测）、
# tools/test_gauntlet_checks.sh（检查器负控制）、
# steering/testing-standards.md「自建关卡脚本的反作弊要求」。
#
# .factory/ shell 门（syntax-factory-sh / lint-factory-shellcheck /
# lint-factory-inline-python）：2026-08-22 feedback 事故后补——适配
# 节点产出的 BRANCH 未定义（SC2154）缺陷逃过纯 pytest 门禁
# （scripts/run_tests.sh）。上游门禁应以本脚本为准；shell 层是其
# 严格超集，pytest 层两者等价（同一套件清单）。
set -e
cd "$(dirname "$0")/.."

# ── 解释器探测 ─────────────────────────────────────────────────────────
# 3 个带 --cov addopts 的 pytest.ini 在缺 pytest-cov 的解释器下收集期即报错。
# 探测不到即硬失败，绝不静默降级为跳过这些层。
PY=${GAUNTLET_PY:-}
if [ -z "$PY" ]; then
    for _cand in "$(command -v python3)" /opt/homebrew/bin/python3; do
        if [ -n "$_cand" ] && "$_cand" -c 'import pytest, pytest_cov'; then
            PY=$_cand
            break
        fi
    done
fi
if [ -z "$PY" ]; then
    echo "gauntlet: 找不到带 pytest+pytest_cov 的解释器（GAUNTLET_PY 可显式指定）" >&2
    exit 2
fi

# ── 陈旧产物清理 ───────────────────────────────────────────────────────
# 上次运行的 .coverage / __pycache__ 既是 must-not 扫描的 grep 噪音，
# 也可能被当成新结果读取——启动即清，不读取任何先前输出。
find . -name .coverage -type f -not -path './.git/*' -delete
find . -name __pycache__ -type d -prune -not -path './.git/*' -exec rm -rf {} +

# ── 层运行器 ───────────────────────────────────────────────────────────
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

# ── 层清单 ─────────────────────────────────────────────────────────────
# GAUNTLET_LAYERS_FILE：编排自测的受控入口（helpers 已就绪后 source），
# 不设该变量时走默认全量清单。
if [ -n "${GAUNTLET_LAYERS_FILE:-}" ]; then
    # shellcheck disable=SC1090
    . "$GAUNTLET_LAYERS_FILE"
else
    run_layer orchestration-self-test sh tools/test_gauntlet_orchestration.sh
    run_layer checker-self-test sh tools/test_gauntlet_checks.sh

    require_dir scripts .factory \
        skills/api-guard/scripts skills/ddl-guard/scripts skills/arch-guard/scripts \
        skills/impact-guard/scripts/tests skills/skill-evo/scripts/tests \
        skills/doc-gen/scripts/tests arch-hawkeye/scripts/tests

    run_layer pytest-scripts "$PY" -m pytest scripts -q
    run_layer pytest-factory "$PY" -m pytest .factory -q
    run_layer pytest-api-guard "$PY" -m pytest skills/api-guard/scripts -q
    run_layer pytest-ddl-guard "$PY" -m pytest skills/ddl-guard/scripts -q
    run_layer pytest-arch-guard "$PY" -m pytest skills/arch-guard/scripts -q
    run_layer pytest-impact-guard "$PY" -m pytest skills/impact-guard/scripts/tests -q
    run_layer pytest-skill-evo "$PY" -m pytest skills/skill-evo/scripts/tests -q
    run_layer pytest-doc-gen "$PY" -m pytest skills/doc-gen/scripts/tests -q
    run_layer pytest-arch-hawkeye "$PY" -m pytest arch-hawkeye/scripts/tests -q

    run_layer md-link-check "$PY" scripts/md_link_check.py .

    layer_must_not_secrets() {
        # shellcheck disable=SC1091
        . tools/must_not_match.sh
        must_not_match "$SECRET_PATTERN" scripts tools hooks skills arch-hawkeye .factory .github
    }
    run_layer must-not-secrets layer_must_not_secrets

    run_layer syntax-sh-n sh -n tools/gauntlet.sh tools/must_not_match.sh \
        tools/test_gauntlet_orchestration.sh tools/test_gauntlet_checks.sh \
        hooks/load-steering.sh hooks/on-session-end.sh
    # lint 范围只含本仓新增 tools/ 脚本：hooks/ 属既有代码，其基线告警不属本门范围
    run_layer lint-shellcheck shellcheck tools/gauntlet.sh tools/must_not_match.sh \
        tools/test_gauntlet_orchestration.sh tools/test_gauntlet_checks.sh

    # ── .factory/ shell 门（2026-08-22 feedback 事故后补） ─────────────
    # 事故：feedback 适配节点产出 BRANCH 未定义（SC2154）的 fix-issue.sh，
    # run_tests.sh 纯 pytest 门禁全绿放行。三层封堵：
    run_layer syntax-factory-sh bash -n .factory/dispatch.sh .factory/fix-issue.sh \
        .factory/factory-state.sh .factory/triage-batch.sh .factory/validate-pr.sh
    # -S warning：SC2154 正是事故形态（引用未赋值变量），不允许降级
    run_layer lint-factory-shellcheck shellcheck -S warning \
        .factory/dispatch.sh .factory/fix-issue.sh \
        .factory/factory-state.sh .factory/triage-batch.sh .factory/validate-pr.sh
    run_layer lint-factory-inline-python "$PY" tools/check_inline_python.py .factory tools scripts
fi

echo "gauntlet: 全部层通过"
