#!/bin/sh
# 变更行覆盖率门：diff-cover 对基线分支的增量核算，阈值 90%。
# 规范事实源：steering/testing-standards.md「覆盖率门禁与『覆盖率阈值』同口径」
# （非 Java ≥ 90%）+「本地自验须与门禁同口径」（直接复用 diff-cover 及其产物，
# 不自写脚本旁路核算）。
#
# 度量边界：diff-cover 只核算 coverage 报告中出现的文件——未带 --cov 的套件
# （scripts/ .factory/ impact-guard 等）变更行不在本门度量面内，由各自套件的
# pytest 门与 shellcheck 门把关；本门不构成「全语言变更行有覆盖」的证明。
# 另：阈值为变更已度量行的聚合比而非逐文件下限（上游聚合语义，非缺陷）。
#
# fail-closed：解释器缺失、coverage/diff_cover 包缺失、无覆盖率产物、
# 产物 combine/xml 失败均 rc=2 拒判（环境坏 ≠ 覆盖率拦截），绝不静默跳层。
# 前置：gauntlet 的 3 个 --cov 套件以独立 COVERAGE_FILE 各写产物
# （.coverage.<suite>，保各套件自身 --cov-fail-under 的独立评估面，不受其他
# 套件数据稀释——评审 F1），本门 combine 汇总后核算。
#
# 语义契约：tools/test_gauntlet_checks.sh NC19（负控制）/ NC19b（正控制）/
# NC19c（损坏路径）。
#
# 用法: tools/run_diff_cover.sh [<repo-dir>]
#   GAUNTLET_PY     解释器（默认 python3），须带 coverage + diff_cover
#   DIFF_COVER_BASE 比较基线（默认 origin/main；gauntlet 层显式钉住防 ambient 指向自身分支）
set -e
ROOT=${1:-$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)}
BASE=${DIFF_COVER_BASE:-origin/main}
PY=${GAUNTLET_PY:-$(command -v python3)}
trap 'rm -f .coverage.xml' EXIT

# 同解释器 fail-closed 预检：console script 可能指向别的环境，不经 PATH 直调
[ -n "$PY" ] || { echo "diff-cover: 无可用解释器" >&2; exit 2; }
if ! "$PY" -c 'import coverage, diff_cover' >/dev/null 2>&1; then
    echo "diff-cover: ${PY} 缺 coverage/diff_cover 包（pip install diff-cover），fail-closed 拒判" >&2
    exit 2
fi
cd "$ROOT" || { echo "diff-cover: 仓库目录不可达: ${ROOT}" >&2; exit 2; }

# 汇总各套件产物：分跑形态 .coverage.<suite> combine 合并；平跑形态 .coverage
# 单文件即最终产物（combine 输入不可与输出同名，单文件无需合并）；两种形态
# 并存时平跑产物临时改名并入。
_plain=0; _sfx=""
[ -f .coverage ] && _plain=1
for _f in .coverage.*; do
    [ -f "$_f" ] && _sfx="$_sfx $_f"
done
if [ "$_plain" -eq 0 ] && [ -z "$_sfx" ]; then
    echo "diff-cover: 无 .coverage* 产物（pytest 层未产出覆盖率即为本门失败，见前置说明）" >&2
    exit 2
fi
if [ -n "$_sfx" ]; then
    if [ "$_plain" -eq 1 ]; then
        mv .coverage .coverage.tmp-plain && _sfx="$_sfx .coverage.tmp-plain"
    fi
    # shellcheck disable=SC2086  # $_sfx 是按空白分词的文件清单，正是意图
    if ! "$PY" -m coverage combine $_sfx 2>&1; then
        echo "diff-cover: 覆盖率产物 combine 失败，fail-closed 拒判" >&2
        exit 2
    fi
    # combine 对个别损坏文件只告警不报错（Combined N, M errored 仍 rc=0）——
    # 用结构性判据收口：成功消费的输入会被其删除，残留即未消费即 fail-closed
    for _f in $_sfx; do
        if [ -e "$_f" ]; then
            echo "diff-cover: 产物 ${_f} 未被 combine 消费（损坏），fail-closed 拒判" >&2
            exit 2
        fi
    done
fi
if ! "$PY" -m coverage xml -o .coverage.xml >/dev/null; then
    echo "diff-cover: 覆盖率产物 xml 生成失败，fail-closed 拒判" >&2
    exit 2
fi
# 经同一解释器进入 diff-cover 入口，避免 PATH 上 console script 环境漂移
"$PY" -c 'import sys; from diff_cover.diff_cover_tool import main; sys.exit(main())' \
    .coverage.xml --compare-branch "$BASE" --fail-under 90
