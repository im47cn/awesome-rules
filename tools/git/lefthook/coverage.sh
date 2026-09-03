#!/usr/bin/env bash
# 变更行覆盖率红线（awesome-rules tools/git 分发，由 lefthook 调用）
# 用法: bash .lefthook/coverage.sh light   # pre-commit 轻检：复用已有 coverage 产物，不跑测试
#       bash .lefthook/coverage.sh full    # pre-push 兜底：跑 pytest --cov / vitest --coverage
# 红线: 变更行测试覆盖率 ≥95%（issue #3：与 steering testing 分层标准、模板 Proof ≥95% 统一）；无测试基础设施/无产物时提示后放行（全量兜底在 full）
set -u
MODE="${1:-light}"
FAIL_UNDER=95

REPO=$(git rev-parse --show-toplevel)
cd "$REPO"

# 变更集: light=staged; full=增量基线 @{push}(上次推送点)...HEAD —— 度量"本次推送新增行"，
# 回退 @{u}(上游)；均不可解析=首次推送，跳过。不回退主干：长命特性分支对 master 的全量
# diff 会把历史欠账算进每次推送，红线语义从"变更行"失真为"整分支"。
if [ "$MODE" = "light" ]; then
  changed=$(git diff --cached --name-only --diff-filter=ACMR)
else
  COMPARE=""
  for b in '@{push}' '@{u}'; do
    git rev-parse --verify -q "$b" >/dev/null 2>&1 && { COMPARE="$b"; break; }
  done
  [ -z "$COMPARE" ] && { echo "[cov] 跳过 (@{push}/@{u} 均不可解析, 疑首次推送)"; exit 0; }
  changed=$(git diff --name-only "$COMPARE...HEAD" 2>/dev/null || true)
fi
echo "$changed" | grep -qE '\.py$'       && HAS_PY=1 || HAS_PY=0
echo "$changed" | grep -qE '\.(ts|tsx)$' && HAS_TS=1 || HAS_TS=0
echo "$changed" | grep -qE '\.java$'     && HAS_JAVA=1 || HAS_JAVA=0
[ $((HAS_PY + HAS_TS + HAS_JAVA)) -eq 0 ] && { echo "[cov] 跳过 (变更集无 .py/.ts/.java)"; exit 0; }

# python 解释器探测: python3 → python → py -3 (Windows 常无 python3, Git Bash 下回退 py 启动器)
# pip --user 装出的 diff-cover.exe 在 Windows 落用户 Scripts 目录(多不在 PATH), 故一律以 -m 方式调用
if   command -v python3 >/dev/null 2>&1; then PY=(python3)
elif command -v python  >/dev/null 2>&1; then PY=(python)
elif command -v py      >/dev/null 2>&1; then PY=(py -3)
else PY=(); fi

# diff-cover 入口: PATH → 当前 python 环境 → uv 按需拉取 → pip 装到用户目录后复用; 均失败才提示后放行
dc_pip_install() {
  [ ${#PY[@]} -eq 0 ] && return 1
  "${PY[@]}" -m pip install --user -q diff-cover >/dev/null 2>&1 && return 0
  # PEP 668 受管环境 (Homebrew/Debian 系 python) 二次尝试; Windows 无此限制, 走不到这
  "${PY[@]}" -m pip install --user -q --break-system-packages diff-cover >/dev/null 2>&1
}
dc() {
  if command -v diff-cover >/dev/null 2>&1; then diff-cover "$@"
  elif [ ${#PY[@]} -gt 0 ] && "${PY[@]}" -c 'import diff_cover' >/dev/null 2>&1; then "${PY[@]}" -m diff_cover.diff_cover_tool "$@"
  elif command -v uv >/dev/null 2>&1; then uv tool run diff-cover "$@"
  elif dc_pip_install; then
    echo "[cov] 已自动安装 diff-cover (pip --user)"
    "${PY[@]}" -m diff_cover.diff_cover_tool "$@"
  else echo "[cov] diff-cover 自动安装失败, 跳过 (可手动: pip install --user diff-cover / uv tool install diff-cover)"; return 0
  fi
}

fail=0

# ---- python: . 或 backend/ 下有 pyproject.toml ----
if [ "$HAS_PY" = 1 ]; then
  py_dirs=$(for d in . backend; do [ -f "$d/pyproject.toml" ] && printf '%s ' "$d"; done)
  [ -n "$py_dirs" ] || echo "[cov] python: 跳过 (无 pyproject.toml)"
  for d in $py_dirs; do
    if [ "$MODE" = "light" ]; then
      [ -f "$d/coverage.xml" ] || { echo "[cov] $d 无 coverage.xml, 跳过轻检 (跑一次 pytest --cov 生成; 红线在 pre-push full)"; continue; }
      echo "[cov] pre-commit $d python staged 变更覆盖检查 (≥${FAIL_UNDER}%)"
      out=$(cd "$d" && dc coverage.xml --compare-branch=HEAD --ignore-unstaged --fail-under="$FAIL_UNDER")
      rc=$?
      printf '%s\n' "$out"
      if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -q 'No lines with coverage information'; then
        echo "[cov] ⚠ 轻检放行语义: 变更行均未命中覆盖产物, 本次未实际检查任何行, 红线强制在 pre-push full"
      fi
      if [ "$rc" -ne 0 ]; then fail=1; fi
    else
      (
        cd "$d" || exit 1
        if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then
          PYCHK=(uv run python -c); PYTEST=(uv run pytest)
        else
          [ ${#PY[@]} -gt 0 ] || { echo "[cov] $d 无 python3/python/py, 跳过 python 覆盖"; exit 0; }
          PYCHK=("${PY[@]}" -c); PYTEST=("${PY[@]}" -m pytest)
        fi
        if ! "${PYCHK[@]}" 'import pytest, pytest_cov' >/dev/null 2>&1; then
          echo "[cov] $d 缺 pytest/pytest-cov, 跳过 python 覆盖 (uv add --dev pytest pytest-cov 启用)"; exit 0
        fi
        cov_target="."
        [ -d src ] && cov_target="src"
        echo "[cov] ▶ $d: pytest --cov=$cov_target + diff-cover (≥${FAIL_UNDER}%)"
        "${PYTEST[@]}" --cov="$cov_target" --cov-report=xml:coverage.xml -q
        rc=$?
        [ $rc -eq 5 ] && { echo "[cov] $d 未收集到测试 (pytest rc=5), 跳过"; exit 0; }
        [ $rc -ne 0 ] && exit 1
        dc coverage.xml --compare-branch="$COMPARE" --fail-under="$FAIL_UNDER"
      ) || fail=1
    fi
  done
fi

# ---- java: . 或 backend/ 下有 pom.xml (Maven + JaCoCo, diff-cover 原生读 jacoco.xml) ----
# 多模块: 收集根 + 一级子模块的 jacoco.xml 一并交给 diff-cover（多份 coverage 文件为位置参数），
# 避免多模块 reactor 下根目录无产物导致门禁静默失效
if [ "$HAS_JAVA" = 1 ]; then
  jv_dirs=$(for d in . backend; do [ -f "$d/pom.xml" ] && printf '%s ' "$d"; done)
  [ -n "$jv_dirs" ] || echo "[cov] java: 跳过 (无 pom.xml)"
  for d in $jv_dirs; do
    # mvnd (Maven Daemon) 优先，回退标准 mvn
    if command -v mvnd >/dev/null 2>&1; then MVN=(mvnd)
    elif command -v mvn >/dev/null 2>&1; then MVN=(mvn)
    else echo "[cov] $d 缺 mvn/mvnd, 跳过 java 覆盖"; continue
    fi
    if [ "$MODE" = "light" ]; then
      (
        cd "$d" || exit 0
        xmls=$(ls target/site/jacoco/jacoco.xml */target/site/jacoco/jacoco.xml 2>/dev/null || true)
        [ -n "$xmls" ] || { echo "[cov] 无 jacoco 产物, 跳过轻检 (跑一次 mvn test 生成; 红线在 pre-push full)"; exit 0; }
        echo "[cov] pre-commit $d java staged 变更覆盖检查 (≥${FAIL_UNDER}%)"
        out=$(dc $xmls --compare-branch=HEAD --ignore-unstaged --fail-under="$FAIL_UNDER")
        rc=$?
        printf '%s\n' "$out"
        if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -q 'No lines with coverage information'; then
          echo "[cov] ⚠ 轻检放行语义: 变更行均未命中覆盖产物, 本次未实际检查任何行, 红线强制在 pre-push full"
        fi
        exit "$rc"
      ) || fail=1
    else
      (
        cd "$d" || exit 1
        echo "[cov] ▶ $d: mvn test + jacoco report + diff-cover (≥${FAIL_UNDER}%)"
        # 全限定插件三连: 无需 pom 预配 jacoco（prepare-agent 默认注入 argLine）
        "${MVN[@]}" -q org.jacoco:jacoco-maven-plugin:prepare-agent test org.jacoco:jacoco-maven-plugin:report
        rc=$?
        [ $rc -ne 0 ] && exit 1
        xmls=$(ls target/site/jacoco/jacoco.xml */target/site/jacoco/jacoco.xml 2>/dev/null || true)
        [ -n "$xmls" ] || { echo "[cov] $d 未生成任何 jacoco.xml, 跳过 diff-cover"; exit 0; }
        dc $xmls --compare-branch="$COMPARE" --fail-under="$FAIL_UNDER"
      ) || fail=1
    fi
  done
fi

# ---- node: . 或 frontend/ 下 package.json 声明 vitest ----
if [ "$HAS_TS" = 1 ]; then
  ts_dirs=$(for d in . frontend; do [ -f "$d/package.json" ] && grep -q '"vitest"' "$d/package.json" && printf '%s ' "$d"; done)
  [ -n "$ts_dirs" ] || echo "[cov] node: 跳过 (无声明 vitest 的 package.json)"
  for d in $ts_dirs; do
    if [ "$MODE" = "light" ]; then
      [ -f "$d/coverage/lcov.info" ] || { echo "[cov] $d 无 coverage/lcov.info, 跳过轻检 (跑一次 vitest --coverage 生成; 红线在 pre-push full)"; continue; }
      echo "[cov] pre-commit $d ts staged 变更覆盖检查 (≥${FAIL_UNDER}%)"
      (cd "$d" && dc coverage/lcov.info --compare-branch=HEAD --ignore-unstaged --fail-under="$FAIL_UNDER") || fail=1
    else
      (
        cd "$d" || exit 1
        echo "[cov] ▶ $d: vitest run --coverage + diff-cover (≥${FAIL_UNDER}%)"
        npx vitest run --coverage || exit 1
        [ -f coverage/lcov.info ] || {
          echo "[cov] $d 未见 coverage/lcov.info (需 @vitest/coverage-v8), 跳过 diff-cover"; exit 0; }
        dc coverage/lcov.info --compare-branch="$COMPARE" --fail-under="$FAIL_UNDER"
      ) || fail=1
    fi
  done
fi

[ $fail -ne 0 ] && echo "✗ [cov] 变更行覆盖率红线未通过 (≥${FAIL_UNDER}%)"
exit $fail
