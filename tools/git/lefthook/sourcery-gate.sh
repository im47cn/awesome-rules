#!/usr/bin/env bash
# Sourcery pre-push 硬闸（awesome-rules tools/git 分发，由 lefthook 调用）
# opt-in 门禁：仅当仓库根存在 .sourcery.yaml（主动声明，同 wop-java-sdk gate 模式）才启用；
# push 文件含支持语言时跑 review --check（同 .sourcery.yaml 配置），有未解决 issue → 阻断 push。
# fail-safe：未 opt-in / 未装 sourcery CLI / 无语言文件变更均跳过（不因环境缺失误伤）。
# 跳过门禁: git push --no-verify
set -u

# opt-in 信号：仓库根 .sourcery.yaml（评审保留清单的载体，主动声明才启用硬闸）
[ -f .sourcery.yaml ] || { echo "[sourcery] 无 .sourcery.yaml（未 opt-in），跳过"; exit 0; }

command -v sourcery >/dev/null 2>&1 || { echo "[sourcery] 未安装 sourcery CLI，跳过"; exit 0; }

# 语言过滤（与 sourcery 支持面一致；{push_files} 以参数列表传入）
# .lefthook/ 是上游管理的分发面（install.sh 拷贝产物，真源已过本仓同名闸）：
# 消费仓 .sourcery.yaml 是项目级裁决（如 low-code-quality 开关逐仓不同），
# 不审判上游工具——否则每仓阈值差异会逼出下游补丁，违反零拷贝漂移治理
# （先例：消费仓配置对 .factory/ 上游镜像面同样 ignore）。
FILES=()
for f in "$@"; do
  case "$f" in
    .lefthook/*) continue ;;
    *.py|*.go|*.java|*.cs|*.php|*.ts|*.js) FILES+=("$f") ;;
  esac
done
if [ ${#FILES[@]} -eq 0 ]; then
  echo "[sourcery] 无语言文件变更，跳过"
  exit 0
fi

echo "[sourcery] review --check：${#FILES[@]} 个语言文件"
sourcery review --check --config .sourcery.yaml ${FILES[@]+"${FILES[@]}"}
rc=$?
[ "$rc" -ne 0 ] && echo "[sourcery] 存在未解决 issue，push 被拦：跑 skills/sourcery-autofix 修复循环后重试（跳过: git push --no-verify）"
exit "$rc"
