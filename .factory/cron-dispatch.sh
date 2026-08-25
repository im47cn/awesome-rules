#!/bin/sh
# cron 包装器：cron 环境无 PATH/git/gh/omp —— 在此显式注入。
# 互斥：macOS 无 flock，用原生 shlock（.factory/locks/dispatch.lock）。
# 日志固定尾追 .factory/locks/dispatch.log（gitignored）。
set -u
SELF=$(readlink -f "$0" 2>/dev/null || printf '%s' "$0")
REPO=$(CDPATH='' cd -- "$(dirname -- "$SELF")/.." && pwd)
LOG="${REPO}/.factory/locks/dispatch.log"
LOCK="${REPO}/.factory/locks/dispatch.lock"
METRICS="${REPO}/.factory/metrics"
STREAK="${REPO}/.factory/locks/dispatch-fail-streak"
STALLED_MARK="${METRICS}/dispatch-stalled"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$REPO" || { echo "无法进入 ${REPO}" >&2; exit 2; }
export PATH HOME="${HOME:?cron 环境未设置 HOME}"
mkdir -p "${REPO}/.factory/locks"  # 净克隆首跑：目录 gitignored 不存在时 shlock 建锁 ENOENT 被误读为锁被持而静默退出（etf-radar PR#79 审查）；下方日志重定向同依赖此目录
ts() { date '+%Y-%m-%d %H:%M:%S'; }
# 抢锁；持锁进程已死则清锁重试一次（防 stale lock 卡死调度）
if ! /usr/bin/shlock -f "$LOCK" -p $$; then
  OPID=$(cat "$LOCK" 2>/dev/null || :)
  if [ -n "$OPID" ] && ! kill -0 "$OPID" 2>/dev/null; then
    rm -f "$LOCK"
    /usr/bin/shlock -f "$LOCK" -p $$ || exit 0
  else
    exit 0
  fi
fi
trap 'rm -f "$LOCK"' EXIT INT TERM
{
  # R4 成本熔断（fail-closed）：本 wrapper 先跑 triage-batch 再跑 dispatch，
  # dispatch.sh 入口另有同款门——此处为 triage 批次而设（cron 路径的
  # LLM 裁决在 dispatch 之前跑）。退出码透传 breaker.sh（3=熔断），
  # 停摆信息随块重定向落 dispatch.log。
  bash "${REPO}/.factory/breaker.sh" "${REPO}/.factory/locks" || exit $?
  echo "── $(ts) triage 批次开始"
  "${REPO}/.factory/triage-batch.sh" && rc=0 || rc=$?
  echo "── $(ts) triage 批次结束（exit=${rc}）"
  echo "── $(ts) dispatch 开始"
  "${REPO}/.factory/dispatch.sh"; drc=$?
  echo "── $(ts) dispatch 结束（exit=${drc}）"
  # 停摆可见性（2026-08-25 ssh.github.com slug 回归：LaunchAgent 每轮
  # exit 2 静默停摆 4h 无人察觉——日志是唯一信号，没人盯日志）。仅计
  # exit 2（环境/配置错误：非 git/无 slug/无 gh/MAX_PARALLEL 非法）；
  # breaker rc 3 是 R4 的显式停机语义，不计。连击 ≥3 轮（默认 45min
  # @600s 间隔）写标记；恢复（rc 0）清零并摘标记。
  if [ "$drc" -eq 2 ]; then
    n=$(cat "$STREAK" 2>/dev/null || echo 0)
    n=$((n + 1)); printf '%s\n' "$n" > "$STREAK"
    if [ "$n" -ge "${DISPATCH_STALLED_N:-3}" ]; then
      mkdir -p "$METRICS"
      printf 'dispatch 停摆：连续 %s 轮 exit 2（自 %s）；见 locks/dispatch.log 尾部与环境自检\n' "$n" "$(ts)" > "$STALLED_MARK"
    fi
  elif [ "$drc" -eq 0 ]; then
    rm -f "$STREAK" "$STALLED_MARK"
  fi
} >> "${LOG}" 2>&1
