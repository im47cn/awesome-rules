#!/usr/bin/env bash
# 全量测试门禁 — 逐套件运行 pytest
#
# 各套件有独立 rootdir（pytest.ini / conftest.py 注入 sys.path），不能用一次
# pytest 跑完，故按目录循环。部分套件 pytest.ini 带覆盖率 addopts（--cov），
# 本机未装 pytest-cov 时会被拦，门禁统一覆盖为空 addopts——覆盖率由专职
# 命令负责，门禁只管测试通过与否。
#
# 并行模型（perf/tests-gate-parallel）：8 套件 + badcase + lease-sql 共 10 段
# 一次 fan-out 后台并发（串行合计 ≈64s），日志各落 mktemp 私有文件，wait
# 全部完成后按原段序回放——输出形态与串行版一致，壁钟压到最长段
# （.factory/tests ≈43s）。秒级尾段（plugin_lock/md_link_check/
# doc_freshness/lint-shellcheck）不并行：无收益，且 lint-shellcheck 层的
# 文件清单被 NC16 镜像锁按文本抽取（tools/test_gauntlet_checks.sh），
# 保持原序原形态以保其解析与负控制语义。
#
# 并行安全（审计 2026-09-04）：各 pytest 段临时文件均唯一命名
# （mkdtemp / NamedTemporaryFile）；skill-evo 固定 /tmp/ar-skill-evo-prompt.md
# 仅 skill-evo 段读写；.factory 泄漏断言已注入私有 TMPDIR（PR #137）；
# lease-sql 固定 /tmp/pgfactory-lease-test 与端口 55432，段内独占——单实例
# 内并行安全，但禁止两个本脚本实例并发运行（固定路径/端口会互撞）。
#
# 用法:
#   bash scripts/run_tests.sh            # 测试 + 安装入口 blob 锁定校验
#   bash scripts/run_tests.sh --no-lock  # 仅测试
set -u -o pipefail  # pipefail：badcase | tail 管道下保留 runner 真实退出码

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
PY="${PYTHON:-python3}"

# 测试套件目录（有 tests/ 子目录用之，否则收集目录本身）
SUITES=(
  "skills/api-guard/scripts"
  "skills/arch-guard/scripts"
  "skills/ddl-guard/scripts"
  "skills/doc-gen/scripts"
  "skills/impact-guard/scripts"
  "skills/skill-evo/scripts"
  "arch-hawkeye/scripts"
  ".factory/tests"
)

# ── 并行段：8 套件 + badcase + lease-sql ────────────────────────────────
FAILED=()  # 先于 trap 注册（set -u 下 trap 引用 ${#FAILED[@]}，提前退出不 unbound）
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ar-run-tests.XXXXXX")"
# 失败保留证据（2026-09-05 bg_9 教训：tests ✗ 44.88s 段日志被无条件删，
# 手动串行复现即绿 → 只能归因瞬态。失败时保留 LOG_DIR 供定位失败段）。
trap 'rc=$?; if [ $rc -ne 0 ] || [ "${#FAILED[@]}" -gt 0 ]; then
  echo "❌ run_tests 失败 (rc=$rc)——段日志保留: $LOG_DIR" >&2
else
  rm -rf "$LOG_DIR"
fi' EXIT

PAR_HEADERS=()  # 段头（与串行版逐字一致）
PAR_TAGS=()     # 失败聚合标签
PAR_LOGS=()     # 段日志私有文件
PAR_PIDS=()     # 后台段进程

par_launch() {  # par_launch <段头> <失败标签> <命令串，"\$1" 为 PY 占位>
  local log="$LOG_DIR/seg-$(( ${#PAR_PIDS[@]} + 1 )).log"
  PAR_HEADERS+=("$1")
  PAR_TAGS+=("$2")
  PAR_LOGS+=("$log")
  # -o pipefail：段内管道（badcase | tail）保留真实退出码。
  # PY 经位置参数 $1 传入、不拼入命令串：撇号路径不再炸语法，调用方可控
  # 的 PYTHON 也不会被重解析为 shell 源码（PR #139 review：注入面）。
  bash -o pipefail -c "$3" _ "$PY" >"$log" 2>&1 &
  PAR_PIDS+=("$!")
}

for suite in "${SUITES[@]}"; do
  target="tests"
  [ -d "$suite/tests" ] || target="."
  par_launch "── pytest $suite" "$suite" \
    "cd '$suite' && \"\$1\" -m pytest '$target' -o addopts='' -q"
done
par_launch "── badcase" "badcase" "\"\$1\" scripts/badcase_runner.py | tail -3"
par_launch "── lease-sql(非PG段)" "lease-sql" \
  "LEASE_SKIP_PG=1 bash .factory/tests/test-lease-sql.sh"

# 两轮：先全量 wait 收状态，再按段序回放——早段日志不抢跑（全部段
# 真正结束后才 cat），失败聚合仍在回放时按段序进行。
PAR_STATUS=()
for pid in "${PAR_PIDS[@]}"; do
  if wait "$pid"; then
    PAR_STATUS+=(0)
  else
    PAR_STATUS+=(1)
  fi
done

i=0
for header in "${PAR_HEADERS[@]}"; do
  echo "$header"
  if [ "${PAR_STATUS[$i]}" -ne 0 ]; then
    FAILED+=("${PAR_TAGS[$i]}")
  fi
  cat "${PAR_LOGS[$i]}"
  echo
  i=$((i + 1))
done

# ── 串行尾段（秒级，不并行；lint-shellcheck 受 NC16 文本镜像锁约束）───

# 安装入口锁定（zero-regression 门禁，与测试同为推送前置）
if [ "${1:-}" != "--no-lock" ]; then
  echo "── plugin_lock"
  if ! "$PY" scripts/plugin_lock.py; then
    FAILED+=("plugin_lock")
  fi
  echo "── md_link_check"
  if ! "$PY" scripts/md_link_check.py; then
    FAILED+=("md_link_check")
  fi
fi

# 文档新鲜度（实现↔文档一致性，R1-R8 见 tools/check_doc_freshness.py 头注释）。
# 刻意放在 --no-lock 分支外：工厂链 final_gate 跑的就是本脚本 --no-lock 形态
# （plugin_lock/md_link_check）一起被 --no-lock 跳过。
echo "── doc_freshness"
if ! "$PY" tools/check_doc_freshness.py; then
  FAILED+=("doc_freshness")
fi

# lint-shellcheck：tools/ 门禁脚本静态检查，文件清单镜像自 gauntlet.sh 的
# lint-shellcheck 层（权威清单），两处须同步维护。本地 push 面此前缺此层，
# CI（config-evals-gate 全量 gauntlet）拦下而本地四闸放行（2026-09-04
# SC2016 实证「本地绿 CI 红」）。软门禁：未装 shellcheck 时提示安装指引后
# 跳过（安装指引见层内提示；CI 侧仍会拦），装好即自动生效硬拦。
echo "── lint-shellcheck"
if command -v shellcheck >/dev/null 2>&1; then
  if ! shellcheck tools/gauntlet.sh tools/must_not_match.sh \
      tools/test_gauntlet_orchestration.sh tools/test_gauntlet_checks.sh \
      tools/test_spec_check.sh; then
    FAILED+=("lint-shellcheck")
  fi
else
  echo "[lint] 缺 shellcheck，跳过（mac: brew install shellcheck / Linux: apt install shellcheck 启用；CI 侧仍会拦）"
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "❌ 门禁失败: ${FAILED[*]}" >&2
  exit 1
fi
echo "✅ 全量测试门禁通过（${#SUITES[@]} 个套件 + badcase + lease非PG段）"
