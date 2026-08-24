#!/usr/bin/env bash
# test-lease-sql.sh —— 仲裁层 schema 行为测试（真 Postgres，非 mock）。
#
# 前置：本机可 runuser（root 跑）；postgresql server/binaries 在位。
# 自建一次性实例（initdb -A trust，端口 55432，socket /tmp），不碰系统库。
# 覆盖：claim/续约/接管/heartbeat/fence/release 的 epoch 语义、配额、
# 机器自注册、RLS 直表全拒、worker 不可调管理员函数、吊销/停机即时生效、
# 未知租户 fail-closed、审计有痕。
#
# 用法：bash .factory/tests/test-lease-sql.sh   （root；非 root 需能 runuser postgres）
set -u

PGDATA=/tmp/pgfactory-lease-test
PORT=55432
PASS=0; FAIL=0
ck() { # ck <名称> <期望> <实得>
  if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "PASS: $1"
  else FAIL=$((FAIL+1)); echo "FAIL: $1（期望 [$2] 实得 [$3]）"; fi
}

command -v initdb >/dev/null || { echo "缺 initdb（postgresql-server 未装）" >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo "需 root（runuser -u postgres）" >&2; exit 2; }

# --- 一次性实例 ---
rm -rf "$PGDATA"
runuser -u postgres -- initdb -D "$PGDATA" -A trust --locale=C >/dev/null 2>&1
cd /tmp || exit 2   # postgres 用户进不了 /root，避开 "could not change directory" 噪音
runuser -u postgres -- pg_ctl -D "$PGDATA" -o "-p $PORT -k /tmp" -l /tmp/lease-test-pg.log -w start >/dev/null 2>&1 \
  || { echo "postgres 启动失败"; cat /tmp/lease-test-pg.log; exit 2; }
trap 'runuser -u postgres -- pg_ctl -D "$PGDATA" stop -m immediate >/dev/null 2>&1; rm -rf "$PGDATA"' EXIT

PG() { runuser -u postgres -- psql -h 127.0.0.1 -p $PORT -U postgres -d postgres -X -q -tA "$@"; }
W()  { runuser -u postgres -- psql -h 127.0.0.1 -p $PORT -U factory-e2e -d postgres -X -q -tA "$@"; }

REPO="$(git -C "$(dirname "$0")/../.." rev-parse --show-toplevel)"
# schema 以 owner=postgres 建立并 apply（幂等迁移走一遍即可）。
# postgres 用户读不了 /root 下的仓库 —— /tmp 副本过桥
cp "$REPO/.factory/db/schema.sql" /tmp/lease-test-schema.sql && chmod 644 /tmp/lease-test-schema.sql
PG -v ON_ERROR_STOP=1 -f /tmp/lease-test-schema.sql >/dev/null || { echo "schema apply 失败" >&2; exit 2; }
# 租户 onboarding（README 运维手册同款）：role + grant + 租户行
PG -c "create role \"factory-e2e\" login; grant factory_worker to \"factory-e2e\";
       insert into factory_tenants (tenant, rolname) values ('e2e','factory-e2e');" >/dev/null

# --- 1-6：claim / 续约 / fence / heartbeat / 抢占 ---
ck "新键认领 t|1"          "t|1"  "$(W -c "select * from factory_claim('issue:1','machA',900)")"
ck "同机续约 epoch 不变"    "t|1"  "$(W -c "select * from factory_claim('issue:1','machA',900)")"
ck "持有者 fence t"         "t"    "$(W -c "select factory_fence_ok('issue:1','machA',1)")"
ck "heartbeat t"            "t"    "$(W -c "select factory_heartbeat('issue:1','machA',1,900)")"
ck "未过期他机抢 f|-1"      "f|-1" "$(W -c "select * from factory_claim('issue:1','machB',900)")"
ck "陈旧 epoch fence f"     "f"    "$(W -c "select factory_fence_ok('issue:1','machA',99)")"

# --- 7-12：过期接管（fencing token 递增）与 release ---
W -c "select * from factory_claim('issue:1','machA',1)" >/dev/null   # 租期缩到 1s
sleep 1.2                                                            # 等过期
ck "过期接管 epoch+1"       "t|2"  "$(W -c "select * from factory_claim('issue:1','machB',900)")"
ck "旧链 fence f"           "f"    "$(W -c "select factory_fence_ok('issue:1','machA',1)")"
ck "旧链 heartbeat f"       "f"    "$(W -c "select factory_heartbeat('issue:1','machA',1,900)")"
ck "新主 fence t"           "t"    "$(W -c "select factory_fence_ok('issue:1','machB',2)")"
ck "release 成功"           "t"    "$(W -c "select factory_release('issue:1','machB',2)")"
ck "release 后再抢 e+1"     "t|3"  "$(W -c "select * from factory_claim('issue:1','machA',900)")"

# --- 13-15：配额（max_parallel=2）与机器自注册 ---
ck "第二键在配额内 t|1"     "t|1"  "$(W -c "select * from factory_claim('issue:2','machA',900)")"
ck "超配额第三键拒"         "f|-1" "$(W -c "select * from factory_claim('issue:3','machA',900)")"
ck "满配自有键续约 t"       "t|3"  "$(W -c "select * from factory_claim('issue:1','machA',900)")"
# 机器自注册：machB 在 5 的失败 claim 里也应登记（admin 侧盘点；worker 直表读被 RLS 拒，见 16）
ck "机器自动登记=2"         "2"    "$(PG -c "select count(*) from factory_machines" | tr -d ' ')"

# --- 16-17：权限收口 ---
W -c "select * from factory_leases" >/dev/null 2>&1; r=$?
ck "直表读被拒(rc!=0)"      "deny" "$([ $r -ne 0 ] && echo deny || echo allow)"
W -c "select factory_revoke('e2e')" >/dev/null 2>&1; r=$?
ck "worker 调 revoke 被拒"  "deny" "$([ $r -ne 0 ] && echo deny || echo allow)"

# --- 18-19：管理员吊销 → 秒级生效（不等心跳/过期）---
PG -c "select factory_revoke('e2e')" >/dev/null
ck "吊销后持有者 fence f"   "f"    "$(W -c "select factory_fence_ok('issue:1','machA',3)")"
ck "吊销租户 claim 拒"      "f|-1" "$(W -c "select * from factory_claim('issue:9','machA',900)")"

# --- 20：单机停用（精确止损）---
PG -c "update factory_tenants set status='active' where tenant='e2e'; truncate factory_leases;" >/dev/null
W -c "select * from factory_claim('issue:5','machA',900)" >/dev/null
PG -c "select factory_machine_disable('machA')" >/dev/null
ck "停用机器 fence f"       "f"    "$(W -c "select factory_fence_ok('issue:5','machA',1)")"
ck "停用机器 claim 拒"      "f|-1" "$(W -c "select * from factory_claim('issue:6','machA',900)")"

# --- 21-22：未知租户 fail-closed；审计有痕 ---
PG -c "create role nobody_e2e login; grant factory_worker to nobody_e2e;" >/dev/null
out=$(runuser -u postgres -- psql -h 127.0.0.1 -p $PORT -U nobody_e2e -d postgres -X -q -tA \
        -c "select * from factory_claim('issue:7','machA',900)" 2>&1 | tail -1)
ck "无租户行 claim 拒"      "f|-1" "$out"
ck "审计事件有痕"           "y"    "$(PG -c "select case when count(*)>0 then 'y' else 'n' end from factory_events" | tr -d ' ')"

echo "-----"
echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
