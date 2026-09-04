#!/usr/bin/env bash
# Sourcery pre-push 硬闸（awesome-rules tools/git 分发，由 lefthook 调用）
# opt-in 门禁：仅当仓库根存在 .sourcery.yaml（主动声明，同 wop-java-sdk gate 模式）才启用；
# push 文件含实测支持语言时跑 review --check（同 .sourcery.yaml 配置），有未解决 issue → 阻断 push。
# fail-safe：未 opt-in / 未装 sourcery CLI 均跳过（不因环境缺失误伤）。
# 语言口径（issue #123）：以 CLI 实测为准，不照抄宣称支持面——
#   实测有效：.py/.ts/.js（sourcery 1.45.0 review --check 实跑产出评审）
#   实测不扫描：.php（送审零输出，静默空转 = fail-open，不再进闸面）
#   未实测：.go/.java/.cs（保持送审面外显式披露，不默认放行进闸）
# 纯面外语 → 显式降级说明后 exit 0（可审计，非静默）；混合 → 对有效子集
# review，并打印未送审数与清单。升级 CLI 须复测口径并同步本注释与 CI pin。
# 跳过门禁: git push --no-verify
set -u

# opt-in 信号：仓库根 .sourcery.yaml（评审保留清单的载体，主动声明才启用硬闸）
[ -f .sourcery.yaml ] || { echo "[sourcery] 无 .sourcery.yaml（未 opt-in），跳过"; exit 0; }

command -v sourcery >/dev/null 2>&1 || { echo "[sourcery] 未安装 sourcery CLI，跳过"; exit 0; }

# 语言过滤（{push_files} 以参数列表传入）
# .lefthook/ 是上游管理的分发面（install.sh 拷贝产物，真源已过本仓同名闸）：
# 消费仓 .sourcery.yaml 是项目级裁决（如 low-code-quality 开关逐仓不同），
# 不审判上游工具——否则每仓阈值差异会逼出下游补丁，违反零拷贝漂移治理
# （先例：消费仓配置对 .factory/ 上游镜像面同样 ignore）。
SUPPORTED=()   # 实测有效：进 review 闸面
UNSENT=()      # 实测不扫描 / 未实测：显式披露，不进闸面
for f in "$@"; do
  case "$f" in
    .lefthook/*) continue ;;
    *.py|*.ts|*.js) SUPPORTED+=("$f") ;;
    *.go|*.java|*.cs|*.php) UNSENT+=("$f") ;;
  esac
done

if [ ${#SUPPORTED[@]} -eq 0 ]; then
  if [ ${#UNSENT[@]} -gt 0 ]; then
    echo "[sourcery] ${#UNSENT[@]} 个变更文件在实测支持面外（.php 实测不扫描；.go/.java/.cs 未实测），降级跳过："
    printf '  %s\n' "${UNSENT[@]}"
    echo "[sourcery] 该集不经 Sourcery 评审——如需覆盖，复测 CLI 口径后扩支持面（见脚本头注）"
  else
    echo "[sourcery] 无语言文件变更，跳过"
  fi
  exit 0
fi

if [ ${#UNSENT[@]} -gt 0 ]; then
  echo "[sourcery] ⚠ ${#UNSENT[@]} 个语言文件未送审（实测支持面外）："
  printf '  %s\n' "${UNSENT[@]}"
fi
echo "[sourcery] review --check：${#SUPPORTED[@]} 个实测支持文件"
sourcery review --check --config .sourcery.yaml "${SUPPORTED[@]}"
rc=$?
[ "$rc" -ne 0 ] && echo "[sourcery] 存在未解决 issue，push 被拦：跑 skills/sourcery-autofix 修复循环后重试（跳过: git push --no-verify）"
exit "$rc"
