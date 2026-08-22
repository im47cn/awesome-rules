#!/bin/sh
# gauntlet.sh 编排自测：证明层运行器的 fail-closed 语义真实存在。
# 覆盖 SPEC 场景：全绿通过 / 任一层失败整体失败 / 层清单缺失硬失败 / 不读陈旧产物。
set -e
cd "$(dirname "$0")/.."
G=tools/gauntlet.sh
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fails=0
ok()   { echo "  ok:   $1"; }
bad()  { echo "  FAIL: $1"; fails=$((fails + 1)); }

run_gauntlet() { # $1=layers 文件；rc 与输出落在 $rc/$TMP/out/$TMP/err
    # if 上下文捕获退出码：层失败是测试输入而非脚本错误，不得触发 set -e 中止
    if GAUNTLET_LAYERS_FILE=$1 sh "$G" >"$TMP/out" 2>"$TMP/err"; then
        rc=0
    else
        rc=$?
    fi
}

# ── T1 全绿通过：退出 0 且每层名带 PASS ─────────────────────────────────
cat >"$TMP/l1" <<'EOF'
run_layer alpha true
run_layer beta true
EOF
run_gauntlet "$TMP/l1"
if [ "$rc" -eq 0 ] && grep -q 'PASS.*alpha' "$TMP/out" && grep -q 'PASS.*beta' "$TMP/out"; then
    ok "T1 全绿退出 0 且层名带 PASS"
else
    bad "T1 期望 rc=0+PASS alpha/beta, 实际 rc=${rc}, 输出: $(cat "$TMP/out")"
fi

# ── T2 任一层失败则整体失败，且失败层名可见 ─────────────────────────────
cat >"$TMP/l2" <<'EOF'
run_layer good true
run_layer boom false
run_layer never-reached true
EOF
run_gauntlet "$TMP/l2"
if [ "$rc" -ne 0 ] && grep -q 'boom' "$TMP/out" "$TMP/err" && ! grep -q 'PASS.*never-reached' "$TMP/out"; then
    ok "T2 层失败整体失败，后续层不再执行"
else
    bad "T2 期望 rc!=0+含 boom+不含 never-reached，实际 rc=${rc}"
fi

# ── T3 层清单防漂移：缺失目录硬失败而非静默跳过 ────────────────────────
cat >"$TMP/l3" <<EOF
require_dir "$TMP/definitely-missing"
run_layer t true
EOF
run_gauntlet "$TMP/l3"
if [ "$rc" -ne 0 ] && grep -q 'definitely-missing' "$TMP/out" "$TMP/err"; then
    ok "T3 缺失目录硬失败并指明路径"
else
    bad "T3 期望 rc!=0+报缺失路径，实际 rc=${rc}"
fi

# ── T4 不读陈旧产物：启动即清理旧 .coverage ────────────────────────────
touch tools/.coverage
cat >"$TMP/l4" <<'EOF'
run_layer noop true
EOF
run_gauntlet "$TMP/l4"
if [ "$rc" -eq 0 ] && [ ! -e tools/.coverage ]; then
    ok "T4 启动清理陈旧 .coverage"
else
    bad "T4 期望运行后 tools/.coverage 不存在，rc=$rc"
fi

# ── 汇总 ───────────────────────────────────────────────────────────────
if [ "$fails" -gt 0 ]; then
    echo "orchestration-self-test: $fails 项失败"
    exit 1
fi
echo "orchestration-self-test: 全部通过"
