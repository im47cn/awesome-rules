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
# 扫描面 = tracked 面：夹具必须是真 git 仓（非 git 目录 fail-closed 拒判）
git init -q "$TMP" && git -C "$TMP" add dead.md
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

# ── NC1b 产物排除正控制：链运行时审计副本不属文档链接门范围 ────────────
# reject-receipt 的 ../blob/main/ 链接只在发布目的地（issue 评论）可解析，
# 磁盘上必为死链；.factory/artifacts 是 gitignored 运行时产物（2026-08-23
# 实证：本机跑过链的人类推送被假阳性拦死）。死链仍须拦（NC1 同跑）。
mkdir -p "$TMP/.factory/artifacts"
printf '# t\n[产物](../blob/main/MISSION.md)\n' >"$TMP/.factory/artifacts/r.md"
printf '.factory/artifacts/\n' >"$TMP/.gitignore" && git -C "$TMP" add .gitignore
if "$PY" scripts/md_link_check.py "$TMP" >"$TMP/out1b" 2>&1; then :; fi
if grep -q 'artifacts/r.md' "$TMP/out1b"; then
    bad "NC1b 期望 .factory/artifacts 被排除，实际被报告"
elif ! grep -q 'no-such-target' "$TMP/out1b"; then
    bad "NC1b 排除扩面吞掉了真实死链检测"
else
    ok "NC1b 产物死链不误报，真实死链仍拦（tracked 面语义）"
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

# ── NC4 inline-python 负控制：`-c -` 事故原形必须被拦 ─────────────────
# 回归（2026-08-22）：feedback 适配节点产出的内联 python 改形逃过全部
# 既有检查。夹具覆盖 R1（-c -）、R2（-c+heredoc 并用）、R3（语法错误）。
# 夹具经 printf 分段拼接：本脚本在 lint-factory-inline-python 扫描面内，
# 源文件不得出现事故字面形态（与 NC2 的 $K 拼接同一原则）；%s 占位在
printf '#!/usr/bin/env bash\n' >"$TMP/nc_inline.sh"
{
    # shellcheck disable=SC2016  # $(…) 与 $f 是夹具字面量，不得在生成期展开
    printf 'a="$(python3 -c %s "$f" <<%s\n' '-' "'PYX'"
    printf 'import sys\nprint(sys.argv[1])\n'
    printf '%s\n)\n' 'PYX'
    # shellcheck disable=SC2016  # 同上
    printf 'b="$(python3 -c %simport sys print(%s)"\n' "'" "'"
} >>"$TMP/nc_inline.sh"
if "$PY" tools/check_inline_python.py "$TMP/nc_inline.sh" >"$TMP/out4" 2>&1; then
    _rc4=0
else
    _rc4=$?
fi
if [ "$_rc4" -eq 1 ] && grep -q 'R1' "$TMP/out4" && grep -q 'R2' "$TMP/out4" \
    && grep -q 'R3' "$TMP/out4"; then
    ok "NC4 -c - 事故原形 + -c/heredoc 并用 + 语法错误全被拦（rc=1）"
else
    bad "NC4 期望 rc=1 且 R1/R2/R3 全报，实际 rc=${_rc4}: $(head -3 "$TMP/out4")"
fi

# ── NC5 inline-python 好路径：合法双引号形态不误伤 ─────────────────────
# 本仓 .factory 合法形态（json_field 双引号 $2 展开块）必须放行——
# 检查器边界是“静态可验证的才拦”，不是见 python 就拦。
cat >"$TMP/nc_inline_ok.sh" <<'EOF'
#!/usr/bin/env bash
json_field() {
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print($2)" "$1"
}
c="$(python3 - "$TMP/f" <<'PYX'
import sys
print(sys.argv[1])
PYX
)"
EOF
if "$PY" tools/check_inline_python.py "$TMP/nc_inline_ok.sh" >"$TMP/out5" 2>&1; then
    ok "NC5 合法内联 python（双引号块 + heredoc）放行"
else
    bad "NC5 期望 rc=0，实际 rc=$?: $(head -3 "$TMP/out5")"
fi

# ── NC6 inline-python 检查器损坏路径：rc=2 绝不算通过 ──────────────────
if "$PY" tools/check_inline_python.py "$TMP/definitely-missing" >"$TMP/out6" 2>&1; then
    _rc6=0
else
    _rc6=$?
fi
if [ "$_rc6" -eq 2 ]; then
    ok "NC6 路径不存在返回 rc=2（检查器损坏 ≠ 通过）"
else
    bad "NC6 期望 rc=2，实际 rc=${_rc6}"
fi

# ── NC7 pipe-early-exit 负控制：三犯原形必须被拦 ──────────────────────
# 夹具覆盖 R3（| true，PR #9/#23）、R1（grep -m1 中位，etf-radar#70）、
# R2（head -n 中位）。夹具经 printf 分段拼接：本脚本在 lint-pipe-early-exit
# 扫描面内，源码不得出现守卫的字面形态（与 NC2 的 $K 拼接同一原则）。
NCP='|'; NCT='tru'; NCM='-m'; NCH='hea'; NCD='d'
{
    printf '#!/usr/bin/env bash\nset -euo pipefail\n'
    # shellcheck disable=SC2016  # $(…) 是夹具字面量，不得在生成期展开
    printf 'changed="$(git diff main %s %se)"\n' "$NCP" "$NCT"
    # shellcheck disable=SC2016  # 同上
    printf 'slug="$( { git remote; } %s grep %s1 x %s sed s/a/b/)"\n' "$NCP" "$NCM" "$NCP"
    # shellcheck disable=SC2016  # 同上
    printf 'top="$(cat list %s %s%s -n 3 %s wc -l)"\n' "$NCP" "$NCH" "$NCD" "$NCP"
    # shellcheck disable=SC2016  # `||` 后管道边界：true 仍是其后管道左端
    printf 'x || %se | wc -l\n' "$NCT"
} >"$TMP/nc7_bad.sh"
if "$PY" tools/check_pipe_early_exit.py "$TMP/nc7_bad.sh" >"$TMP/out7" 2>&1; then
    _rc7=0
else
    _rc7=$?
fi
if [ "$_rc7" -eq 1 ] && grep -q 'R1' "$TMP/out7" && grep -q 'R2' "$TMP/out7" \
    && grep -q 'R3' "$TMP/out7" && grep -q ':4:' "$TMP/out7" \
    && grep -q ':5:' "$TMP/out7" && grep -q ':6:' "$TMP/out7"; then
    ok "NC7 三犯原形全被拦（rc=1，行号+规则齐备）"
else
    bad "NC7 期望 rc=1 且 R1/R2/R3 与行号 4/5/6 全报，实际 rc=${_rc7}: $(head -3 "$TMP/out7")"
fi
if [ "$_rc7" -eq 1 ] && grep -q ':4:' "$TMP/out7" && grep -q -c 'R3' "$TMP/out7" >/dev/null; then
    ok "NC7 || 后管道边界 R3 报行 4（x || true | wc -l 形）"
else
    bad "NC7 期望 || 边界 R3 报行 4，实际 rc=${_rc7}: $(grep ':4:' "$TMP/out7" || echo 无)"
fi

# NC7b 安全等价形放行：|| true（逻辑或层）、sed -n '1p'（消费全量）、
# head 末位（末位即目的）——检查器边界是"确定性早退"，不是见管道就拦
cat >"$TMP/nc7_ok.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
out="$(git diff main 2>/dev/null || true)"
first="$(printf '%s\n' "$x" | sed -n '1p')"
top="$(cat list | head)"
EOF
# 转义管道（\| 字面量）与行内注释（词首 #）不是命令——放行
# shellcheck disable=SC2016  # 夹具字面量：转义管道在生成期不得被解释
printf 'y="$(printf x \\| z)"\n' >>"$TMP/nc7_ok.sh"
# shellcheck disable=SC2016  # 同上（注释行夹具）
printf 'echo ok # %s %se is fine here\n' "$NCP" "$NCT" >>"$TMP/nc7_ok.sh"
if "$PY" tools/check_pipe_early_exit.py "$TMP/nc7_ok.sh" >"$TMP/out7b" 2>&1; then
    ok "NC7b 安全等价形（|| true / sed -n 1p / head 末位 / 转义 / 注释）放行"
else
    bad "NC7b 期望 rc=0，实际 rc=$?: $(head -3 "$TMP/out7b")"
fi

# NC7c 检查器损坏路径：rc=2 绝不算通过（与 NC6 同一语义）
if "$PY" tools/check_pipe_early_exit.py "$TMP/definitely-missing" >"$TMP/out7c" 2>&1; then
    _rc7c=0
else
    _rc7c=$?
fi
if [ "$_rc7c" -eq 2 ]; then
    ok "NC7c 路径不存在返回 rc=2（检查器损坏 ≠ 通过）"
else
    bad "NC7c 期望 rc=2，实际 rc=${_rc7c}"
fi

# ── 汇总 ───────────────────────────────────────────────────────────────
if [ "$fails" -gt 0 ]; then
    echo "checker-self-test: $fails 项失败"
    exit 1
fi
echo "checker-self-test: 全部通过"
