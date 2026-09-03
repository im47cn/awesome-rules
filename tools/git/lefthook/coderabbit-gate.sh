#!/usr/bin/env bash
# CodeRabbit pre-push 建议性评审闸（awesome-rules tools/git 分发，由 lefthook 调用）
# opt-in 门禁：仅当仓库根存在 .coderabbit.yaml（主动声明，同 sourcery-gate 的 .sourcery.yaml 模式）才启用。
# 建议性而非硬闸的依据：① LLM 评审分钟级延迟（官方文档 7-30 分钟，--light 更快）；② CLI 认证失败也
# exit 0 只打错误行（实测 0.7.5）——退出码不可作阻断信号。findings 打印后放行，不拦 push；
# 硬闸语义由平台侧 CodeRabbit PR 评审承担。
# fail-safe：未 opt-in / 未装 coderabbit CLI / 未登录均跳过（不因环境缺失误伤）。
# {push_files} 参数仅作 lefthook 触发条件（无变更恒 skip），评审范围由 CLI 按 git 状态自定（--committed）。
# 跳过评审: git push --no-verify
set -u

# opt-in 信号：仓库根 .coderabbit.yaml（CodeRabbit 原生配置文件，兼作门禁开关载体，删除即停用）
[ -f .coderabbit.yaml ] || { echo "[coderabbit] 无 .coderabbit.yaml（未 opt-in），跳过"; exit 0; }

command -v coderabbit >/dev/null 2>&1 || { echo "[coderabbit] 未安装 coderabbit CLI，跳过（brew install coderabbit）"; exit 0; }

# 登录预检：auth status 秒级；review 未登录时也 exit 0 只打错误（见头部注释），前置探测避免空跑
coderabbit auth status 2>&1 | grep -q "signed in" || { echo "[coderabbit] 未登录，跳过（coderabbit auth login）"; exit 0; }

echo "[coderabbit] review --light --committed（建议性评审，分钟级延迟）……"
coderabbit review --light --committed
rc=$?
[ "$rc" -ne 0 ] && echo "[coderabbit] 评审异常退出（rc=$rc），不阻断 push；回看结果: coderabbit review findings"
exit 0
