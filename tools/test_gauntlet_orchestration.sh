#!/bin/sh
# gauntlet.sh 编排自测：证明层运行器的 fail-closed 语义真实存在。
# 覆盖 SPEC 场景：全绿通过 / 任一层失败整体失败 / 层清单缺失硬失败 / 不读陈旧产物 /
# 并发批语义（批内失败整门失败、批内其余层照常报告、批后层不执行 / 批全绿放行）/
# doctor 自诊断（健康全 OK 且不改盘 / 坏解释器 FAIL 且汇总非零 / 未知模式硬失败 /
# find_py 语法探针拒收过 import 桩但解析失败的假解释器 /
# 语法探针执行期盲区：compile 过而模块级执行炸的文件被拦）。
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

# ── T5 doctor 模式：健康环境全 OK、退出 0、不清产物 ────────────────────
touch tools/.coverage
if sh "$G" doctor >"$TMP/d5out" 2>"$TMP/d5err"; then
    drc=0
else
    drc=$?
fi
if [ "$drc" -eq 0 ] && grep -q 'OK   解释器' "$TMP/d5out" \
    && grep -q 'OK   目录: scripts' "$TMP/d5out" && [ -e tools/.coverage ]; then
    ok "T5 doctor 健康环境退出 0、逐项 OK 且不清产物"
else
    bad "T5 期望 rc=0+解释器/目录 OK+产物保留, 实际 rc=${drc}, 输出: $(cat "$TMP/d5out") $(cat "$TMP/d5err")"
fi
rm -f tools/.coverage

# ── T6 doctor 负控制：坏解释器（GAUNTLET_PY 指向不存在路径）────────────
if GAUNTLET_PY=$TMP/definitely-not-python sh "$G" doctor >"$TMP/d6out" 2>"$TMP/d6err"; then
    drc=0
else
    drc=$?
fi
if [ "$drc" -ne 0 ] && grep -q 'FAIL 解释器' "$TMP/d6err" && grep -q '项异常' "$TMP/d6err"; then
    ok "T6 doctor 坏解释器报 FAIL 并汇总退出非零"
else
    bad "T6 期望 rc!=0+FAIL 解释器+异常计数, 实际 rc=${drc}, stderr: $(cat "$TMP/d6err")"
fi

# ── T7 未知模式 fail-closed：不静默落回全量门禁 ────────────────────────
if sh "$G" bogus-mode >"$TMP/d7out" 2>"$TMP/d7err"; then
    drc=0
else
    drc=$?
fi
if [ "$drc" -eq 2 ] && grep -q '未知参数' "$TMP/d7err"; then
    ok "T7 未知参数硬失败（exit 2）"
else
    bad "T7 期望 rc=2+未知参数提示, 实际 rc=${drc}, stderr: $(cat "$TMP/d7err")"
fi

# ── T8 find_py 语法探针负控制：过 import 桩但探针失败的假解释器被拒 ────
# 形态复刻 2026-09-09 实证盲区：解释器 import 自检绿（桩 -c 即过）但解析
# 不动本仓源码（探针 - 调用失败）——必须被 doctor 报 FAIL，不得放行。
mkdir -p "$TMP/fakebin"
cat >"$TMP/fakebin/fakepy" <<'SHEOF'
#!/bin/sh
case "$1" in
  -c) exit 0 ;;
  *)  exit 1 ;;
esac
SHEOF
chmod +x "$TMP/fakebin/fakepy"
if GAUNTLET_PY="$TMP/fakebin/fakepy" sh "$G" doctor >"$TMP/d8out" 2>"$TMP/d8err"; then
    drc=0
else
    drc=$?
fi
if [ "$drc" -ne 0 ] && grep -q 'FAIL 解释器' "$TMP/d8err" && grep -q '语法自检' "$TMP/d8err"; then
    ok "T8 语法探针拒收过 import 桩但解析失败的假解释器"
else
    bad "T8 期望 rc!=0+FAIL 解释器+语法自检, 实际 rc=${drc}, stderr: $(cat "$TMP/d8err")"
fi

# ── T9 探针执行期盲区负控制：compile 过而模块级执行炸的文件被拦 ──────
# 形态复刻 Sourcery 2026-09-13 评审盲区：PEP 604 注解等 parse 过、模块级
# 执行才炸的代码（2026-09-09 3.9 实证形态）。用 raise 版本保证负控制在
# 任意解释器版本上确定性触发（dict | None 仅 <3.10 执行期炸，不可移植）。
mkdir -p "$TMP/t9"
printf 'x: int = 1\nraise TypeError("probe exec negative control")\n' \
    >"$TMP/t9/exec_fails.py"
_pyt=$(command -v python3)
if "$_pyt" "$(dirname "$G")/py_syntax_probe.py" "$TMP/t9" \
    >"$TMP/d9out" 2>&1; then
    drc=0
else
    drc=$?
fi
if [ "$drc" -ne 0 ] && grep -q 'exec_fails.py' "$TMP/d9out"; then
    ok "T9 探针拦下 compile 过而执行炸的文件"
else
    bad "T9 期望 rc!=0+exec_fails.py 被点名, 实际 rc=${drc}, 输出: $(cat "$TMP/d9out")"
fi

# ── T10 批语义负控制：批内失败 → 整体失败，批内其余层照常报告且输出回放，
#    批后层不执行（fail-fast 粒度保持在批，见 gauntlet.sh 头注释）────────
cat >"$TMP/l10" <<'EOF'
run_layer pre true
run_layer_bg bg-fail sh -c 'echo boom-from-bg; exit 7'
run_layer_bg bg-ok true
wait_layers
run_layer never-reached true
EOF
run_gauntlet "$TMP/l10"
if [ "$rc" -ne 0 ] && grep -q 'FAIL bg-fail（rc=7）' "$TMP/out" \
    && grep -q 'boom-from-bg' "$TMP/out" && grep -q 'PASS bg-ok' "$TMP/out" \
    && ! grep -q 'PASS never-reached' "$TMP/out"; then
    ok "T10 批内失败：批内其余层照常报告，批后层不再执行"
else
    bad "T10 期望 rc!=0+FAIL bg-fail+boom-from-bg+PASS bg-ok+无 never-reached，实际 rc=${rc}, 输出: $(cat "$TMP/out")"
fi

# ── T11 批全绿正控制：批内层全 PASS，批后串行层照常执行 ─────────────────
cat >"$TMP/l11" <<'EOF'
run_layer_bg bg-one true
run_layer_bg bg-two true
wait_layers
run_layer after true
EOF
run_gauntlet "$TMP/l11"
if [ "$rc" -eq 0 ] && grep -q 'PASS bg-one' "$TMP/out" \
    && grep -q 'PASS bg-two' "$TMP/out" && grep -q 'PASS after' "$TMP/out"; then
    ok "T11 批全绿：批内层全 PASS 且批后串行层照常执行"
else
    bad "T11 期望 rc=0+bg-one/bg-two/after 全 PASS，实际 rc=${rc}, 输出: $(cat "$TMP/out")"
fi

# ── 汇总 ───────────────────────────────────────────────────────────────
if [ "$fails" -gt 0 ]; then
    echo "orchestration-self-test: $fails 项失败"
    exit 1
fi
echo "orchestration-self-test: 全部通过"
