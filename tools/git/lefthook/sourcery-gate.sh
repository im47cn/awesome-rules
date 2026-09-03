#!/usr/bin/env bash
# Sourcery pre-push 硬闸（awesome-rules tools/git 分发，由 lefthook 调用）
# opt-in 门禁：仅当仓库根存在 .sourcery.yaml（主动声明，同 wop-java-sdk gate 模式）才启用；
# push 文件含支持语言时跑 review --check（同 .sourcery.yaml 配置），有未解决 issue → 阻断 push。
# fail-safe：未 opt-in / 未装 sourcery CLI / 无支持语言文件变更均跳过（不因环境缺失误伤）。
# 跳过门禁: git push --no-verify
# CLI 支持面（sourcery CLI 1.45.0 本机实测；语言面随版本漂移，以本机 CLI 实测为准）：
# - 实测有效（进入 review --check）：*.py *.ts *.js
# - 实测未兑现（CLI 报 0 files scanned、静默 exit 0，gate 空转）：*.php（issue #123）
# - 未实测（按不在支持面处理，显式跳过）：*.go *.java *.cs
set -u

# opt-in 信号：仓库根 .sourcery.yaml（评审保留清单的载体，主动声明才启用硬闸）
[ -f .sourcery.yaml ] || { echo "[sourcery] 无 .sourcery.yaml（未 opt-in），跳过"; exit 0; }

command -v sourcery >/dev/null 2>&1 || { echo "[sourcery] 未安装 sourcery CLI，跳过"; exit 0; }

# 语言过滤：仅 CLI 实测有效语言进入评审（py/ts/js）；php/go/java/cs 显式跳过——
# CLI 对其静默不扫（0 files scanned），传给 CLI 即 gate 空转（issue #123）。
FILES=()
SKIPPED=()
for f in "$@"; do
  case "$f" in
    *.py|*.ts|*.js) FILES+=("$f") ;;
    *.php|*.go|*.java|*.cs) SKIPPED+=("$f") ;;
  esac
done
if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo "[sourcery] 跳过 ${#SKIPPED[@]} 个不在 CLI 实测支持面（py/ts/js）的文件，CLI 不扫描即 gate 不评审：${SKIPPED[*]}"
fi
if [ ${#FILES[@]} -eq 0 ]; then
  echo "[sourcery] 无支持语言（py/ts/js）文件变更，跳过"
  exit 0
fi

echo "[sourcery] review --check：${#FILES[@]} 个语言文件"
sourcery review --check --config .sourcery.yaml ${FILES[@]+"${FILES[@]}"}
rc=$?
[ "$rc" -ne 0 ] && echo "[sourcery] 存在未解决 issue，push 被拦：跑 skills/sourcery-autofix 修复循环后重试（跳过: git push --no-verify）"
exit "$rc"
