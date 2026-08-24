#!/usr/bin/env bash
# factory-lease.sh — Supabase 租约仲裁层客户端（source 引入，勿直接执行）。
#
# 三层架构（README「租约仲裁」节）：
#   仲裁 = 本库 + db/schema.sql（claim/heartbeat/release/fence，全部服务端原子）
#   投影 = GitHub labels + state.py（声明式收敛，sync 多写者安全）
#   围栏 = git refs 服务端保护（factory/* 禁 force push/禁删）
#
# fail-closed 铁律：SUPABASE_DB 未设置 / psql 失败 = 拒绝动作退出，
# 绝不回退到"标签认领碰运气"——降级继续跑等于重新打开多写者竞态。
#
# 环境变量：
#   SUPABASE_DB          PG 连接串（Supabase pooler 或任何 Postgres）
#   FACTORY_LEASE_SECS   租期秒数（默认 900 = 15min，心跳 60s 的 15 倍余量）
#   FACTORY_HB_INTERVAL  心跳间隔秒数（默认 60）
#
# 调用方契约：REPO 已定义（git 仓库根）。兼容 bash 3.2（macOS）。
[ -n "${__FACTORY_LEASE_SH:-}" ] && return 0
__FACTORY_LEASE_SH=1

lease_db() {  # 打印连接串；未配置即失败（fail-closed，不降级）
  if [ -z "${SUPABASE_DB:-}" ]; then
    echo "[error] SUPABASE_DB 未设置：仲裁层缺失，fail-closed 拒绝动作（README「租约仲裁」）" >&2
    return 1
  fi
  printf '%s' "$SUPABASE_DB"
}

lease_psql() {  # lease_psql <sql> —— 单语句执行；任何错误都是失败
  psql "$(lease_db)" -X -q -tA -v ON_ERROR_STOP=1 -c "$1"
}

lease_key_sane() {  # 键/机器 ID 白名单 [A-Za-z0-9._:-]（SQL 注入面收口）
  case "$1" in
    *[!A-Za-z0-9._:-]*) return 1 ;;
    "") return 1 ;;
  esac
  return 0
}

lease_machine_id() {  # 稳定机器身份：主树 .factory/var/machine-id（非 PID）
  # PID 是机器局部命名空间，跨机不可判活性；machine-id 跟主 .git 走，
  # worktree 共享（git-common-dir 锚定，对齐 dispatch.sh 硬锁路径解析）。
  local mf f tmp
  mf="$(git -C "${REPO}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
    | sed 's#/\.git$##' || true)"
  mf="${mf:-${REPO}}/.factory"
  f="${mf}/var/machine-id"
  if [ ! -s "$f" ]; then
    mkdir -p "${mf}/var"
    tmp="${f}.tmp.$$"
    ( umask 077; python3 -c 'import uuid; print(uuid.uuid4().hex)' > "$tmp" ) \
      && mv "$tmp" "$f" || { rm -f "$tmp"; echo "[error] machine-id 生成失败" >&2; return 1; }
  fi
  cat "$f"
}

lease_claim() {  # lease_claim <key> [secs] —— 成功打印 epoch，失败 return 1
  local key="$1" secs="${2:-${FACTORY_LEASE_SECS:-900}}" mid out epoch
  lease_key_sane "$key" || { echo "[error] 非法租约键: ${key}" >&2; return 1; }
  mid="$(lease_machine_id)" || return 1
  out="$(lease_psql "select * from factory_claim('${key}','${mid}',${secs})")" \
    || { echo "[error] 租约仲裁不可达（key=${key}），fail-closed" >&2; return 1; }
  # 输出形如 "t|3"（o_won|o_epoch）；未赢（f|-1）与解析异常一律 return 1
  [ "${out%%|*}" = "t" ] || return 1
  epoch="${out##*|}"
  case "$epoch" in ''|*[!0-9]*) return 1 ;; esac
  [ "$epoch" -gt 0 ] || return 1
  printf '%s\n' "$epoch"
}

lease_heartbeat() {  # lease_heartbeat <key> <epoch> [secs] —— 0=活 1=已被夺走
  local key="$1" epoch="$2" secs="${3:-${FACTORY_LEASE_SECS:-900}}" mid
  lease_key_sane "$key" && lease_key_sane "$epoch" || return 1
  mid="$(lease_machine_id)" || return 1
  lease_psql "select factory_heartbeat('${key}','${mid}',${epoch},${secs})" | grep -qx t
}

lease_fence_ok() {  # lease_fence_ok <key> <epoch> —— 0=仍持有 1=已被夺走
  local key="$1" epoch="$2" mid
  lease_key_sane "$key" && lease_key_sane "$epoch" || return 1
  mid="$(lease_machine_id)" || return 1
  lease_psql "select factory_fence_ok('${key}','${mid}',${epoch})" | grep -qx t
}

lease_release() {  # lease_release <key> <epoch> —— 尽力释放（幂等）
  local key="$1" epoch="$2" mid
  lease_key_sane "$key" && lease_key_sane "$epoch" || return 1
  mid="$(lease_machine_id)" || return 1
  lease_psql "select factory_release('${key}','${mid}',${epoch})" >/dev/null
}

lease_guard() {  # 副作用出口围栏：租约失效即拒绝（诈尸/被吊销防护）
  # 无租约上下文（LEASE_KEY 未设，如本地直跑测试）不拦——拦是链的义务，
  # 不是库的义务；设了就必须过。
  [ -z "${LEASE_KEY:-}" ] && return 0
  lease_fence_ok "${LEASE_KEY}" "${LEASE_EPOCH}"
}

lease_heartbeat_loop() {  # lease_heartbeat_loop <key> <epoch> —— 后台心跳
  # 失效即向父进程（链）发 TERM；链须有 `trap 'exit n' TERM` 使 EXIT trap 级联。
  # 父进程消亡则自退（防孤儿心跳）。
  local key="$1" epoch="$2"
  local int="${FACTORY_HB_INTERVAL:-60}" secs="${FACTORY_LEASE_SECS:-900}"
  (
    while :; do
      sleep "$int"
      kill -0 "$PPID" 2>/dev/null || exit 0
      if ! lease_heartbeat "$key" "$epoch" "$secs"; then
        echo "[lease] 租约失效：key=${key} epoch=${epoch}（被夺/吊销/过期），TERM 链" >&2
        kill -TERM "$PPID" 2>/dev/null
        exit 1
      fi
    done
  ) &
  LEASE_HB_PID=$!
}

lease_cleanup() {  # EXIT trap 用：停心跳 + 尽力释放；永不失败
  [ -n "${LEASE_HB_PID:-}" ] && kill "${LEASE_HB_PID}" 2>/dev/null
  if [ -n "${LEASE_KEY:-}" ] && [ -n "${LEASE_EPOCH:-}" ]; then
    lease_release "${LEASE_KEY}" "${LEASE_EPOCH}" >/dev/null 2>&1 || true
  fi
  return 0
}
