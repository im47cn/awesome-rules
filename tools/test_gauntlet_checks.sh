#!/bin/sh
# checker 负控制自测：证明本 gauntlet 依赖的检查器"会失败"，而不是只会放行。
# NC1 检查 md_link_check（既有检查器，属回归护甲）；NC2 检查 must_not_match（本次新增）。
set -e
cd "$(dirname "$0")/.."
PY=${GAUNTLET_PY:-$(command -v python3)}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fails=0
ok()  { echo "  ok:   $1"; }
bad() { echo "  FAIL: $1"; fails=$((fails + 1)); }

. tools/must_not_match.sh

# ── NC1 死链负控制：含死链的 markdown 必须被 md_link_check 拦下 ────────
cat >"$TMP/dead.md" <<'EOF'
# 负控制夹具
[死链](./no-such-target.md)
EOF
if "$PY" scripts/md_link_check.py "$TMP" >"$TMP/out1" 2>&1; then
    rc1=0
else
    rc1=$?
fi
if [ "$rc1" -ne 0 ] && grep -q 'no-such-target' "$TMP/out1"; then
    ok "NC1 死链被拦且报告指明死链目标"
else
    bad "NC1 期望 rc!=0 且输出含 no-such-target，实际 rc=$rc1: $(head -3 "$TMP/out1")"
fi

# ── NC2 秘密负控制：含假凭据字面量的文件必须被 must_not_match 拦下 ────
# 只认 rc=1（真拦截）；rc=2 是检查器自身损坏，同样判负——坏检查器不算通过。
# 夹具经 $K 拼接：本脚本自身在被扫描面内，源码不得出现守卫的字面形态
# （与 must_not_match.sh 的 [e] 括号防自匹配同一原则）。
K=key
cat >"$TMP/leak.py" <<EOF
config = {
    "api_${K}": "AKIAIOSFODNN7EXAMPLE",
}
EOF
if must_not_match "$SECRET_PATTERN" "$TMP/leak.py"; then
    _rc2=0
else
    _rc2=$?
fi
if [ "$_rc2" -eq 1 ]; then
    ok "NC2 假凭据被拦（rc=1）"
else
    bad "NC2 期望 rc=1, 实际 rc=${_rc2}（0=未拦, 2=检查器损坏）"
fi

# ── NC3 放行路径在 set -e 上下文必须 rc=0 ──────────────────────────────
# 回归：grep 无匹配返回 1 是好路径，曾被 set -e 当失败吞掉整层（2026-08-21）。
# 注意不能写成 if (set -e; ...)：if 上下文豁免 errexit，复现不了真实陷阱；
# 必须用子进程——其内部的 set -e 是真实的非测试上下文。
cat >"$TMP/clean.py" <<'EOF'
value = "just some ordinary data"
EOF
out3=$(sh -c 'set -e; . "$1/tools/must_not_match.sh"; must_not_match "$SECRET_PATTERN" "$2"; echo SURVIVED' sh "$PWD" "$TMP/clean.py") || out3=""
if [ "$out3" = "SURVIVED" ]; then
    ok "NC3 干净文件在真实 set -e 上下文通过"
else
    bad "NC3 干净文件应存活到 echo（out3='$out3'）——errexit 吞掉 grep rc=1 好路径"
fi

# ── 汇总 ───────────────────────────────────────────────────────────────
if [ "$fails" -gt 0 ]; then
    echo "checker-self-test: $fails 项失败"
    exit 1
fi
echo "checker-self-test: 全部通过"
