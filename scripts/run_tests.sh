#!/usr/bin/env bash
# 全量测试门禁 — 逐套件运行 pytest
#
# 各套件有独立 rootdir（pytest.ini / conftest.py 注入 sys.path），不能用一次
# pytest 跑完，故按目录循环。部分套件 pytest.ini 带覆盖率 addopts（--cov），
# 本机未装 pytest-cov 时会被拦，门禁统一覆盖为空 addopts——覆盖率由专职
# 命令负责，门禁只管测试通过与否。
#
# 用法:
#   bash scripts/run_tests.sh            # 测试 + 安装入口 blob 锁定校验
#   bash scripts/run_tests.sh --no-lock  # 仅测试
set -u -o pipefail  # pipefail：badcase | tail 管道下保留 runner 真实退出码

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
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

FAILED=()
for suite in "${SUITES[@]}"; do
  target="tests"
  [ -d "$suite/tests" ] || target="."
  echo "── pytest $suite"
  if ! (cd "$suite" && "$PY" -m pytest "$target" -o addopts="" -q); then
    FAILED+=("$suite")
  fi
  echo
done

# badcase 回归（真实坏例 → 检查脚本 → expected.md 双通道比对，12 例全基线绿）
echo "── badcase"
if ! "$PY" scripts/badcase_runner.py | tail -3; then
  FAILED+=("badcase")
fi
echo

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

# 文档新鲜度（实现↔文档一致性，R1-R5 见 tools/check_doc_freshness.py 头注释）。
# 刻意放在 --no-lock 分支外：工厂链 final_gate 跑的就是本脚本 --no-lock 形态
# （.factory/prompts/plan.md），文档漂移必须在链内被拦——不能随发布面门
# （plugin_lock/md_link_check）一起被 --no-lock 跳过。
echo "── doc_freshness"
if ! "$PY" tools/check_doc_freshness.py; then
  FAILED+=("doc_freshness")
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "❌ 门禁失败: ${FAILED[*]}" >&2
  exit 1
fi
echo "✅ 全量测试门禁通过（${#SUITES[@]} 个套件 + badcase）"
