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
    run_layer plugin-versions "$PY" tools/check_plugin_versions.py
    # 实现↔文档一致性（数字/清单/指向漂移，R1-R5 语义见脚本头注释）
    run_layer doc-freshness "$PY" tools/check_doc_freshness.py
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
    run_layer lint-factory-inline-python "$PY" tools/check_inline_python.py .factory tools scripts
    # 管道早退静态门（issue #30 三犯成类）：pipefail 下非末位早退消费者
    # （grep -m/head）与 true 管道段。扫描面 = tracked *.sh（67c2965b 原则）
    run_layer lint-pipe-early-exit "$PY" tools/check_pipe_early_exit.py \
        .factory tools scripts hooks skills arch-hawkeye .github
    # 进程组信号平台语义门（PR #36 flake 沉淀，约定见 steering/testing-standards.md
    # 「进程组信号的平台语义」）：os.killpg 缺 EPERM 容忍 / raises 单发探活。
    # 扫描面 = tracked *.py（67c2965b 原则）
    run_layer lint-killpg-strict "$PY" tools/check_killpg_strict.py \
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
fi

echo "gauntlet: 全部层通过"
