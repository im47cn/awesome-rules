#!/usr/bin/env bash
# 变异测试红线（awesome-rules tools/git 分发，由 lefthook pre-push 调用）
# 用法: bash .lefthook/mutation-gate.sh   # push 集含 src/main/java 生产代码时触发
# 红线: PIT 变异分 ≥ pom <mutationThreshold>（各仓/模块自定；未配置阈值时 PIT 只报告不拦截）
# 语义: 只约束生产代码变更——纯测试/文档/脚本变更跳过（变异分门禁防"生产行为改了而测试没跟上"）
#       无 pitest 配置的模块提示后跳过（接入: pom 加 pitest-maven + mutationThreshold）
set -u

REPO=$(git rev-parse --show-toplevel)
cd "$REPO"

# 增量基线: @{push}(上次推送点)...HEAD，回退 @{u}(上游)；均不可解析=首次推送，跳过
# （与 coverage.sh full 模式同口径：度量"本次推送"，不回退主干避免长命分支欠账失真）
COMPARE=""
for b in '@{push}' '@{u}'; do
  git rev-parse --verify -q "$b" >/dev/null 2>&1 && { COMPARE="$b"; break; }
done
[ -z "$COMPARE" ] && { echo "○ [mutation] 无推送基线(首次推送), 跳过"; exit 0; }
changed=$(git diff --name-only "$COMPARE"...HEAD 2>/dev/null)
# 非阻断告警: 删除测试文件会削弱断言强度（变异分/覆盖率红线），本门禁不拦纯测试变更，
# 弱化在下次生产代码变更时由 mutationThreshold 兜底吸收 —— 删除意图请走 MR/评审自行把关
deleted_tests=$(git diff --name-only --diff-filter=D "$COMPARE"...HEAD 2>/dev/null | grep -E 'src/test/.*\.(java|kt)$' || true)
if [ -n "$deleted_tests" ]; then
  echo "⚠ [mutation] 本次推送删除了测试文件(不拦截; 变异分由下次生产变更时阈值兜底):"
  printf '  - %s\n' $deleted_tests
fi

# 触发条件: 生产 java 代码变更（src/main/java）；纯测试/文档/配置变更直接跳过
prod=$(printf '%s\n' $changed | grep -E 'src/main/java/.*\.java$' || true)
[ -z "$prod" ] && { echo "○ [mutation] 无 src/main/java 生产代码变更, 跳过"; exit 0; }

# 候选模块: 变更文件一级目录；根结构(src/main/java 直接在仓库根)映射为 "."
mods=$(printf '%s\n' $prod | awk -F/ '{print ($1=="src") ? "." : $1}' | sort -u)

fail=0
for m in $mods; do
  pom="pom.xml"; [ "$m" != "." ] && pom="$m/pom.xml"
  if [ ! -f "$pom" ] || ! grep -q 'pitest-maven' "$pom"; then
    echo "○ [mutation] $m 未配置 pitest, 跳过 (接入: pom 加 pitest-maven + mutationThreshold)"
    continue
  fi
  PL=(); [ "$m" != "." ] && PL=(-pl "$m")
  echo "▶ [mutation] $m: PIT mutationCoverage (阈值见 pom mutationThreshold)"
  # 单模块跑 PIT 时 minion 从本地仓库取兄弟模块 jar —— 先静默 install 依赖(跳测试)消除 classpath 漂移
  mvn -B -q ${PL[@]+"${PL[@]}"} -am install -DskipTests >/dev/null 2>&1 || true
  if mvn -B ${PL[@]+"${PL[@]}"} org.pitest:pitest-maven:mutationCoverage; then
    echo "✓ [mutation] $m 变异分达标"
  else
    echo "✗ [mutation] $m 变异分低于阈值或执行失败 (报告: target/pit-reports)"
    fail=1
  fi
done
[ $fail -ne 0 ] && echo "✗ [mutation] 变异测试红线未通过"
exit $fail
