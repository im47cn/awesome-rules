#!/usr/bin/env bash
# 全量测试门禁 — 并行门（工厂编排，ADR-016）+ 串行尾段
#
# 各套件有独立 rootdir（pytest.ini / conftest.py 注入 sys.path），不能用一次
# pytest 跑完，故按目录循环。部分套件 pytest.ini 带覆盖率 addopts（--cov），
# 本机未装 pytest-cov 时会被拦，门禁统一覆盖为空 addopts——覆盖率由专职
# 命令负责，门禁只管测试通过与否。
#
# 并行模型（ADR-016，源 perf/tests-gate-parallel）：8 套件 + badcase +
# lease-sql 共 10 段的 fan-out 编排已下沉工厂并行门（.factory/factory_lib.py
# parallel-gate 子命令；段清单/长段白名单数据化 factory-local.json
# parallel_gate.segments，intra:auto = 段内并行档）。本脚本退为组合方：跑
# 并行门 → 回收失败段 tag → 串行尾段 → 末尾一次聚合裁决（一次运行全量
# 暴露失败清单）。历史实测（PR #212）：串行合计 ≈64s，fan-out 后壁钟
# ≈14s；长段叠加段内并行（.factory/tests 43s→11s、ddl-guard 11s→6.6s），
# 秒级段 spawn 开销倒挂保持串行；段日志失败保留/成功即删由编排器自管。
# 秒级尾段（plugin_lock/doc_freshness/lint-shellcheck）不并行：无收益，
# 且 lint-shellcheck 层的文件清单被 NC16 镜像锁按文本抽取
#（tools/test_gauntlet_checks.sh），保持原序原形态以保其解析与负控制语义。
#
# 并行安全（审计 2026-09-04）：各 pytest 段临时文件均唯一命名
# （mkdtemp / NamedTemporaryFile）；skill-evo 固定 /tmp/ar-skill-evo-prompt.md
# 仅 skill-evo 段读写；.factory 泄漏断言已注入私有 TMPDIR（PR #137）；
# lease-sql 固定 /tmp/pgfactory-lease-test 与端口 55432，段内独占——单实例
# 内并行安全，但禁止两个本脚本实例并发运行（固定路径/端口会互撞）。
# 段内 xdist 并行复检（2026-09-20）：worker 间无共享固定路径/端口；唯一
# 竞态 run_gate 的 pgid 文件握手（负载下 bash 启动可晚于超时杀组、文件
# 永不落盘）已改 Popen 派生侧捕获（test_mutations_run._capture_gate_pgid）；
# skill-evo dry-run 固定路径仅单测试内写读（test_evo_cli 唯一触达者）。
#
# 用法:
#   bash scripts/run_tests.sh            # 测试 + 安装入口 blob 锁定校验
#   bash scripts/run_tests.sh --no-lock  # 仅测试
set -u -o pipefail  # pipefail：段内管道已随编排下沉 runner（shell 段自带 bash -o pipefail）；防御性保留

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
PY="${PYTHON:-python3}"

# ── 并行段：8 套件 + badcase + lease-sql（编排=工厂并行门，ADR-016）───
# 段清单登记处：factory-local.json 的 parallel_gate.segments（长段以
# intra:"auto" 白名单段内并行；shell 段自带 pipefail）。编排器职责：段间
# fan-out、按段序回放、段日志失败保留（成功即删）、失败 tag 逐行落
# --failed-tags 文件（每行尾带 \n，供 read -r 逐行回收）。PY 经 PYTHON
# env 传递（编排器内 $PY 词替换）。
FAILED=()  # 先于 trap 注册（set -u 下 trap 引用 ${#FAILED[@]}，提前退出不 unbound）
rc=0  # 先于 trap 注册：trap 串内 rc=$? 对 shellcheck 静态不可见（SC2154 消音，同上先例）
trap 'rc=$?; if [ $rc -ne 0 ] || [ "${#FAILED[@]}" -gt 0 ]; then
  echo "❌ run_tests 失败 (rc=$rc)" >&2
fi' EXIT

if ! FAILED_TAGS="$(mktemp "${TMPDIR:-/tmp}/ar-run-tags.XXXXXX")"; then
  echo "❌ 无法创建并行门失败标签文件（mktemp）" >&2
  exit 2
fi
PAR_RC=0
"$PY" .factory/factory_lib.py parallel-gate --failed-tags "$FAILED_TAGS" || PAR_RC=$?
if [ "$PAR_RC" -eq 2 ]; then
  rm -f "$FAILED_TAGS"
  echo "❌ 并行门配置错误（fail-closed，不产出裁决）" >&2
  exit 2
fi
if [ "$PAR_RC" -ne 0 ]; then
  # 并行门已按段序回放段日志并打印 ❌ 失败段与段日志保留路径；此处仅
  # 回收失败 tag 进 FAILED，串行尾段照跑后末尾统一裁决——与迁移前行为
  # 一致：一次运行全量暴露失败清单，不分批。
  while IFS= read -r t; do
    [ -n "$t" ] && FAILED+=("$t")
  done < "$FAILED_TAGS"
fi
rm -f "$FAILED_TAGS"

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

# 文档新鲜度（实现↔文档一致性，R1-R9 见 tools/check_doc_freshness.py 头注释）。
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
  if ! shellcheck tools/gauntlet.sh tools/must_not_match.sh tools/run_diff_cover.sh \
      tools/test_gauntlet_orchestration.sh tools/test_gauntlet_checks.sh \
      tools/test_spec_check.sh tools/test_pre-push-delete-guard.sh \
      tools/test_dispatch_watch.sh \
      tools/git/install.sh tools/git/lefthook/coverage.sh \
      tools/git/lefthook/commitmsg-check.sh tools/git/lefthook/run-tests.sh \
      tools/git/lefthook/spec-check.sh tools/git/lefthook/sourcery-gate.sh \
      tools/git/lefthook/mutation-gate.sh tools/git/lefthook/coderabbit-gate.sh \
      tools/git/lefthook/pre-push-delete-guard.sh; then
    FAILED+=("lint-shellcheck")
  fi
else
  echo "[lint] 缺 shellcheck，跳过（mac: brew install shellcheck / Linux: apt install shellcheck 启用；CI 侧仍会拦）"
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "❌ 门禁失败: ${FAILED[*]}" >&2
  exit 1
fi
echo "✅ 全量测试门禁通过（8 个套件 + badcase + lease非PG段）"
