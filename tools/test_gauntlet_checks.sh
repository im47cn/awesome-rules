#!/bin/sh
# checker 负控制自测：证明本 gauntlet 依赖的检查器"会失败"，而不是只会放行。
# NC1 检查 md_link_check（既有检查器，属回归护甲）；NC2 检查 must_not_match（本次新增）。
set -e
cd "$(dirname "$0")/.."
PY=${GAUNTLET_PY:-$(command -v python3)}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 测试密封性（steering/testing-standards.md §测试密封性，ADR-010）：本脚本
# 大量建 tmp 夹具仓（git init/-C）；hook 注入的 GIT_* 会劫持仓库发现
# （2026-08-22 事故）。顶层剥除，子进程继承。
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE

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
    # shellcheck disable=SC2016  # 同上：夹具字面量防自匹配
    printf 'd="$(python3 -c %sprint(1)%s)"\n' '"' '"'
} >>"$TMP/nc_inline.sh"
if "$PY" tools/check_inline_python.py "$TMP/nc_inline.sh" >"$TMP/out4" 2>&1; then
    _rc4=0
else
    _rc4=$?
fi
if [ "$_rc4" -eq 1 ] && grep -q 'R1' "$TMP/out4" && grep -q 'R2' "$TMP/out4" \
    && grep -q 'R3' "$TMP/out4" && grep -q 'R4' "$TMP/out4"; then
    ok "NC4 -c - 事故原形 + -c/heredoc 并用 + 语法错误 + 双引号块全被拦（rc=1）"
else
    bad "NC4 期望 rc=1 且 R1/R2/R3/R4 全报，实际 rc=${_rc4}: $(head -3 "$TMP/out4")"
fi

# ── NC5 inline-python 好路径：合法形态不误伤 ────────────────────────────
# R4 后合法形态 = 单引号 -c 块 + quoted heredoc。原「双引号块放行」契约
# 2026-08-28 反转（存量清零后禁形，拦截断言并入 NC4）。
cat >"$TMP/nc_inline_ok.sh" <<'EOF'
#!/usr/bin/env bash
json_field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2"
}
c="$(python3 - "$TMP/f" <<'PYX'
import sys
print(sys.argv[1])
PYX
)"
EOF
if "$PY" tools/check_inline_python.py "$TMP/nc_inline_ok.sh" >"$TMP/out5" 2>&1; then
    ok "NC5 合法内联 python（单引号 -c + heredoc）放行"
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

# ── NC8 killpg-strict 负控制：PR #36 两侧原形必须被拦 ─────────────────
# 夹具为单引号 heredoc 字符串：ast 只看语法节点，源码字面形态不自匹配
# （本脚本在 pytest-scripts 扫描面外的 sh 面，Python 夹具经 heredoc 落盘）。
cat >"$TMP/nc8_bad.py" <<'EOF'
import os
import pytest


def kill_strict(pgid):
    try:
        os.killpg(pgid, 9)
    except ProcessLookupError:
        pass


def test_flaky_probe(pgid):
    with pytest.raises(ProcessLookupError):
        os.killpg(pgid, 0)


def test_flaky_probe_kw(pgid):
    with pytest.raises(expected_exception=ProcessLookupError):
        os.killpg(pgid, 0)
EOF
if "$PY" tools/check_killpg_strict.py "$TMP/nc8_bad.py" >"$TMP/out8" 2>&1; then
    _rc8=0
else
    _rc8=$?
fi
if [ "$_rc8" -eq 1 ] && grep -q 'K1' "$TMP/out8" && grep -q 'K2' "$TMP/out8"; then
    ok "NC8 killpg-strict 拦 K1/K2 原形"
else
    bad "NC8 期望 rc=1+K1+K2, 实际 rc=${_rc8}, 输出: $(cat "$TMP/out8")"
fi

# NC8b 安全等价形放行：元组容忍 / 裸 except——检查器边界是确定性缺失，
# 不是见 killpg 就拦
cat >"$TMP/nc8_ok.py" <<'EOF'
import os


def kill_tuple(pgid):
    try:
        os.killpg(pgid, 9)
    except (ProcessLookupError, PermissionError):
        pass
EOF
if "$PY" tools/check_killpg_strict.py "$TMP/nc8_ok.py" >"$TMP/out8b" 2>&1; then
    ok "NC8b killpg-strict 放行容忍形态"
else
    bad "NC8b 期望 rc=0, 实际输出: $(cat "$TMP/out8b")"
fi

# NC8c 检查器损坏路径：rc=2 绝不算通过（与 NC6/NC7c 同一语义）
if "$PY" tools/check_killpg_strict.py "$TMP/definitely-missing" >"$TMP/out8c" 2>&1; then
    :
else
    _rc8c=$?
fi
if [ "$_rc8c" -eq 2 ]; then
    ok "NC8c killpg-strict 损坏路径 rc=2"
else
    bad "NC8c 期望 rc=2, 实际 rc=${_rc8c:-0}"
fi

# ── NC9 插件版本门负控制：版本漂移必须被 check_plugin_versions 拦下 ──
# 夹具是真 git 仓（tracked 面语义同 NC1）；package.json 0.4.0 对
# .claude-plugin/plugin.json 0.3.0 → rc=1 且报告期望/实际。
NC9DIR="$TMP/nc9"; export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
git init -q "$NC9DIR"
printf '{"version": "0.4.0"}' >"$NC9DIR/package.json"
mkdir -p "$NC9DIR/.claude-plugin"
printf '{"version": "0.3.0"}' >"$NC9DIR/.claude-plugin/plugin.json"
git -C "$NC9DIR" add -A
if "$PY" tools/check_plugin_versions.py "$NC9DIR" >"$TMP/out9" 2>&1; then
    _rc9=0
else
    _rc9=$?
fi
if [ "$_rc9" -eq 1 ] && grep -q 'claude-plugin/plugin.json: 期望 0.4.0 实际 0.3.0' "$TMP/out9"; then
    ok "NC9 版本漂移被拦且报告期望/实际"
else
    bad "NC9 期望 rc=1 且报告漂移明细, 实际 rc=${_rc9}: $(cat "$TMP/out9")"
fi

# ── NC9b 未登记清单漂移：新平台 manifest 不登记 = 硬失败 ──────────────
mkdir -p "$NC9DIR/.new-platform"
printf '{"version": "0.4.0"}' >"$NC9DIR/.new-platform/plugin.json"
git -C "$NC9DIR" add -A
if "$PY" tools/check_plugin_versions.py "$NC9DIR" >"$TMP/out9b" 2>&1; then
    _rc9b=0
else
    _rc9b=$?
fi
if [ "$_rc9b" -eq 1 ] && grep -q '未登记' "$TMP/out9b"; then
    ok "NC9b 未登记清单漂移被拦（require_dir 同语义）"
else
    bad "NC9b 期望 rc=1 且报未登记, 实际 rc=${_rc9b}: $(cat "$TMP/out9b")"
fi

# ── NC9c 检查器损坏路径：非 git 仓 rc=2 绝不算通过（NC6/NC8c 同语义）──
if "$PY" tools/check_plugin_versions.py "$TMP/definitely-missing" >"$TMP/out9c" 2>&1; then
    _rc9c=0
else
    _rc9c=$?
fi
if [ "$_rc9c" -eq 2 ]; then
    ok "NC9c 非 git 仓返回 rc=2（检查器损坏 ≠ 通过）"
else
    bad "NC9c 期望 rc=2, 实际 rc=${_rc9c}"
fi

# ── NC9d 父仓子目录：路径基线错位拒判（PR #41 review 3）────────────────
# git 向父目录找仓 → ls-files 相对父仓根，allowlist 相对 root 比较即错位。
mkdir -p "$NC9DIR/sub" && printf '{"version": "0.4.0"}' >"$NC9DIR/sub/package.json"
if "$PY" tools/check_plugin_versions.py "$NC9DIR/sub" >"$TMP/out9d" 2>&1; then
    _rc9d=0
else
    _rc9d=$?
fi
if [ "$_rc9d" -eq 2 ] && grep -q '不是 git 仓库顶层' "$TMP/out9d"; then
    ok "NC9d 父仓子目录拒判 rc=2 且指明错位"
else
    bad "NC9d 期望 rc=2 且报顶层错位, 实际 rc=${_rc9d}: $(cat "$TMP/out9d")"
fi

# ── NC9e 未跟踪 allowlist：发布面漂移（PR #41 review 4）─────────────────
# gitignored 同名清单不参与发布——读了也不算数，未跟踪本身即漂移。
NC9E="$TMP/nc9e"
git init -q "$NC9E"
printf '{"version": "1.0.0"}' >"$NC9E/package.json"
mkdir -p "$NC9E/.claude-plugin"
printf '{"version": "1.0.0"}' >"$NC9E/.claude-plugin/plugin.json"
printf '.claude-plugin/\n' >"$NC9E/.gitignore"
git -C "$NC9E" add -A
if "$PY" tools/check_plugin_versions.py "$NC9E" >"$TMP/out9e" 2>&1; then
    _rc9e=0
else
    _rc9e=$?
fi
if [ "$_rc9e" -eq 1 ] && grep -q 'claude-plugin/plugin.json: 未被 git 跟踪' "$TMP/out9e"; then
    ok "NC9e 未跟踪 allowlist 报发布面漂移（不静默跳过）"
else
    bad "NC9e 期望 rc=1 且报未跟踪, 实际 rc=${_rc9e}: $(cat "$TMP/out9e")"
fi
# ── NC10 doc-freshness 负控制：文档漂移必须被 check_doc_freshness 拦下 ──
# 夹具为最小仓形态（本门只读文件系统事实，无需 git 仓）。覆盖：干净全绿
# 正控制、R1/R2/R4 漏报负控制、豁免双通道（--allow 正则 / 行内标记）、
# rc=2 结构性损坏路径。
nc10_setup() {
    _d=$1; _pc=${2:-3}; _tc=${3:-2}
    mkdir -p "$_d/.factory/prompts" "$_d/skills/foo/scripts"
    {
        echo '# .factory'
        echo
        echo '## 组件'
        echo
        # shellcheck disable=SC2016  # 字面 markdown 反引号，刻意单引号防展开
        echo '- `a.sh` 入口'
        # shellcheck disable=SC2016
        echo '- `run.py` 库'
        echo
        printf '节点共（%s）个提示词。\n' "$_pc"
    } >"$_d/.factory/README.md"
    printf 'x\n' >"$_d/.factory/a.sh"
    printf 'x\n' >"$_d/.factory/run.py"
    printf 'p\n' >"$_d/.factory/prompts/p1.md"
    printf 'p\n' >"$_d/.factory/prompts/p2.md"
    printf 'p\n' >"$_d/.factory/prompts/p3.md"
    printf '# T\n' >"$_d/README.md"
    printf '状态：测试 %s 项。\n' "$_tc" >"$_d/skills/foo/README.md"
    printf 'def test_a():\n    pass\n\n\ndef test_b():\n    pass\n' \
        >"$_d/skills/foo/scripts/test_x.py"
}

NC10="$TMP/nc10"; nc10_setup "$NC10"
if "$PY" tools/check_doc_freshness.py "$NC10" >"$TMP/out10" 2>&1; then
    ok "NC10 干净 fixture 全绿"
else
    bad "NC10 干净 fixture 期望 rc=0: $(cat "$TMP/out10")"
fi

# R1 漏报：顶层新增未提及组件 zz.sh
NC10A="$TMP/nc10a"; nc10_setup "$NC10A"; printf 'x\n' >"$NC10A/.factory/zz.sh"
if "$PY" tools/check_doc_freshness.py "$NC10A" >"$TMP/out10a" 2>&1; then
    _rc10a=0
else
    _rc10a=$?
fi
if [ "$_rc10a" -eq 1 ] && grep -q 'R1' "$TMP/out10a" && grep -q 'zz.sh' "$TMP/out10a"; then
    ok "NC10a R1 组件漏报检出"
else
    bad "NC10a 期望 rc=1+R1+zz.sh, 实际 rc=${_rc10a}: $(cat "$TMP/out10a")"
fi

# R2 数字不符：陈述 （9）个 vs 实际 3
NC10B="$TMP/nc10b"; nc10_setup "$NC10B" 9
if "$PY" tools/check_doc_freshness.py "$NC10B" >"$TMP/out10b" 2>&1; then
    _rc10b=0
else
    _rc10b=$?
fi
if [ "$_rc10b" -eq 1 ] && grep -q 'R2' "$TMP/out10b" && grep -q '陈述 9 vs 实际 3' "$TMP/out10b"; then
    ok "NC10b R2 提示词计数漂移检出"
else
    bad "NC10b 期望 rc=1+R2+陈述 9 vs 实际 3, 实际 rc=${_rc10b}: $(cat "$TMP/out10b")"
fi

# R4 数字不符：陈述 测试 7 项 vs 实际 2（test_x.py 两个 def test_）
NC10C="$TMP/nc10c"; nc10_setup "$NC10C" 3 7
if "$PY" tools/check_doc_freshness.py "$NC10C" >"$TMP/out10c" 2>&1; then
    _rc10c=0
else
    _rc10c=$?
fi
if [ "$_rc10c" -eq 1 ] && grep -q 'R4' "$TMP/out10c" && grep -q '陈述 7 vs 实际 2' "$TMP/out10c"; then
    ok "NC10c R4 技能测试数漂移检出"
else
    bad "NC10c 期望 rc=1+R4+陈述 7 vs 实际 2, 实际 rc=${_rc10c}: $(cat "$TMP/out10c")"
fi

# 豁免通道 1：--allow 正则命中证据行 → 同样的 R4 漂移放行
NC10D="$TMP/nc10d"; nc10_setup "$NC10D" 3 7
if "$PY" tools/check_doc_freshness.py "$NC10D" --allow 'skills/foo.*R4' >"$TMP/out10d" 2>&1; then
    ok "NC10d --allow 正则豁免生效"
else
    bad "NC10d --allow 期望 rc=0: $(cat "$TMP/out10d")"
fi

# 豁免通道 2：行内豁免标记 → 同样的 R4 漂移放行
NC10E="$TMP/nc10e"; nc10_setup "$NC10E" 3 7
printf '状态：测试 7 项。 <!-- doc-freshness:allow -->\n' >"$NC10E/skills/foo/README.md"
if "$PY" tools/check_doc_freshness.py "$NC10E" >"$TMP/out10e" 2>&1; then
    ok "NC10e 行内豁免标记生效"
else
    bad "NC10e 行内标记期望 rc=0: $(cat "$TMP/out10e")"
fi

# 结构性损坏路径：缺 .factory 等必需面 rc=2 绝不算通过（NC6/NC7c 同语义）
if "$PY" tools/check_doc_freshness.py "$TMP/definitely-missing" >"$TMP/out10f" 2>&1; then
    _rc10f=0
else
    _rc10f=$?
fi
if [ "$_rc10f" -eq 2 ]; then
    ok "NC10f 结构性损坏 rc=2 拒判"
else
    bad "NC10f 期望 rc=2, 实际 rc=${_rc10f}"
fi

# ── NC11 doc-freshness R6/R7 负控制：枚举漂移必须被拦下 ────────────────
# 在 NC10 最小仓上加 R6/R7 面：guard 技能（带 SKILL.md，R3 树须覆盖）、
# steering 两规范（frontmatter title 供 R7b 主题）、opencode 清单、
# CONTRIBUTING 树、AGENTS/CLAUDE 枚举行、load-steering 审查清单。
nc11_setup() {
    _d=$1
    nc10_setup "$_d"
    mkdir -p "$_d/skills/ddl-guard" "$_d/steering" "$_d/.opencode" "$_d/hooks"
    printf -- '---\nname: ddl-guard\ndescription: t\n---\n' \
        >"$_d/skills/ddl-guard/SKILL.md"
    printf -- '---\ntitle: 测试规范\nscenario: t\n---\n' \
        >"$_d/steering/testing-standards.md"
    printf -- '---\ntitle: 审查报告输出规范\nscenario: t\n---\n' \
        >"$_d/steering/report-standards.md"
    {
        echo '# T'
        echo '```'
        echo '├── skills/'
        echo '│   ├── foo/'
        echo '│   └── ddl-guard/'
        echo '```'
    } >"$_d/README.md"
    cat >"$_d/.opencode/opencode.json" <<'EOF'
{
  "instructions": [
    "skills/ddl-guard/SKILL.md",
    "steering/testing-standards.md",
    "steering/report-standards.md"
  ]
}
EOF
    {
        echo '# C'
        echo '```'
        echo 'steering/'
        echo '├── testing-standards.md'
        echo '├── report-standards.md'
        echo '└── gtsp/'
        echo '```'
    } >"$_d/CONTRIBUTING.md"
    echo '- **通用设计规范**（设计阶段）：steering/*.md —— 测试、审查报告输出' \
        >"$_d/AGENTS.md"
    echo '- **通用设计规范**（设计阶段）：steering/*.md —— 测试、审查报告输出' \
        >"$_d/CLAUDE.md"
    echo 'parts.append("- 审查类任务可使用 /ddl-guard 自动检查")' \
        >"$_d/hooks/load-steering.sh"
}

NC11="$TMP/nc11"; nc11_setup "$NC11"
if "$PY" tools/check_doc_freshness.py "$NC11" >"$TMP/out11" 2>&1; then
    ok "NC11 干净 fixture 全绿（R6/R7 无误报）"
else
    bad "NC11 干净 fixture 期望 rc=0: $(cat "$TMP/out11")"
fi

# R6 漏报：opencode instructions 缺 guard 技能条目
NC11A="$TMP/nc11a"; nc11_setup "$NC11A"
grep -v 'ddl-guard/SKILL.md' "$NC11A/.opencode/opencode.json" \
    >"$NC11A/.opencode/opencode.json.tmp" && mv "$NC11A/.opencode/opencode.json.tmp" \
    "$NC11A/.opencode/opencode.json"
if "$PY" tools/check_doc_freshness.py "$NC11A" >"$TMP/out11a" 2>&1; then
    _rc11a=0
else
    _rc11a=$?
fi
if [ "$_rc11a" -eq 1 ] && grep -q 'R6' "$TMP/out11a" \
    && grep -q 'ddl-guard/SKILL.md' "$TMP/out11a"; then
    ok "NC11a R6 opencode 清单漏报检出"
else
    bad "NC11a 期望 rc=1+R6+ddl-guard, 实际 rc=${_rc11a}: $(cat "$TMP/out11a")"
fi

# R6 修绿：补回缺失条目后同一夹具转绿（证明检出项可修复、非结构性拒判）
cat >"$NC11A/.opencode/opencode.json" <<'EOF'
{
  "instructions": [
    "skills/ddl-guard/SKILL.md",
    "steering/testing-standards.md",
    "steering/report-standards.md"
  ]
}
EOF
if "$PY" tools/check_doc_freshness.py "$NC11A" >"$TMP/out11a2" 2>&1; then
    ok "NC11a2 R6 补条目后修绿"
else
    bad "NC11a2 修绿后期望 rc=0: $(cat "$TMP/out11a2")"
fi

# R7a 漏报：CONTRIBUTING 目录树缺 steering 顶层文件
NC11B="$TMP/nc11b"; nc11_setup "$NC11B"
grep -v 'report-standards.md' "$NC11B/CONTRIBUTING.md" \
    >"$NC11B/CONTRIBUTING.md.tmp" && mv "$NC11B/CONTRIBUTING.md.tmp" \
    "$NC11B/CONTRIBUTING.md"
if "$PY" tools/check_doc_freshness.py "$NC11B" >"$TMP/out11b" 2>&1; then
    _rc11b=0
else
    _rc11b=$?
fi
if [ "$_rc11b" -eq 1 ] && grep -q 'R7a' "$TMP/out11b" \
    && grep -q 'report-standards.md' "$TMP/out11b"; then
    ok "NC11b R7a 目录树漏报检出"
else
    bad "NC11b 期望 rc=1+R7a+report-standards.md, 实际 rc=${_rc11b}: $(cat "$TMP/out11b")"
fi

# R7c 漏报：审查清单行在但缺 /ddl-guard
NC11C="$TMP/nc11c"; nc11_setup "$NC11C"
echo 'parts.append("- 审查类任务可使用 自动检查")' \
    >"$NC11C/hooks/load-steering.sh"
if "$PY" tools/check_doc_freshness.py "$NC11C" >"$TMP/out11c" 2>&1; then
    _rc11c=0
else
    _rc11c=$?
fi
if [ "$_rc11c" -eq 1 ] && grep -q 'R7c' "$TMP/out11c" \
    && grep -q 'ddl-guard' "$TMP/out11c"; then
    ok "NC11c R7c 审查清单漏报检出"
else
    bad "NC11c 期望 rc=1+R7c+ddl-guard, 实际 rc=${_rc11c}: $(cat "$TMP/out11c")"
fi

# 文件缺失跳过：无 .opencode/CONTRIBUTING/AGENTS/CLAUDE/hooks 面 → 整组
# 跳过而非误报（NC10 最小仓本身即此形态，此处显式再证一次）
NC11E="$TMP/nc11e"; nc10_setup "$NC11E"
if "$PY" tools/check_doc_freshness.py "$NC11E" >"$TMP/out11e" 2>&1; then
    ok "NC11e R6/R7 目标面缺失时跳过"
else
    bad "NC11e 缺面时期望 rc=0: $(cat "$TMP/out11e")"
fi


# ── NC12 hosting-exit 负控制：出口收口两规则都会拦，行文不误报 ──────────
# 夹具 = 临时 git 仓（tracked 面原则）；bad 形态含命令位 gh 直调 + 收口外
# ${HOST} issue 写，ok 形态含注释行文 / issue 创建 / PR 侧写（均合法）。
NC12="$TMP/nc12"; mkdir -p "$NC12/.factory"
git init -q "$NC12"
cat >"$NC12/.factory/evil.sh" <<'EOF'
#!/usr/bin/env bash
gh issue edit 9 --add-label factory:accepted
gh pr list --state open
out="$(gh api repos/o/r/issues/9/events)"
${HOST} issue comment 9 --body-file f
${HOST} issue set-labels 9 --add factory:triaging
EOF
git -C "$NC12" add .factory/evil.sh
if "$PY" tools/check_hosting_exit.py "$NC12" >"$TMP/out12" 2>&1; then
    _rc12=0
else
    _rc12=$?
fi
if [ "$_rc12" -eq 1 ] && grep -q 'R1' "$TMP/out12" && grep -q 'R2' "$TMP/out12"; then
    ok "NC12 hosting-exit 拦 R1（gh 直调）+R2（issue 写绕收口）"
else
    bad "NC12 期望 rc=1+R1+R2, 实际 rc=${_rc12}, 输出: $(cat "$TMP/out12")"
fi

NC12B="$TMP/nc12b"; mkdir -p "$NC12B/.factory"
git init -q "$NC12B"
cat >"$NC12B/.factory/good.sh" <<'EOF'
#!/usr/bin/env bash
# gh label 过滤是「含有」非「仅有」（行文，不在命令位）
echo "报错文案: hosting issue comment 失败（行文，非调用形态）"
${HOST} issue create --title t --body-file f
${HOST} pr comment 7 --body ok
${HOST} pr set-labels 7 --add factory:validated
EOF
git -C "$NC12B" add .factory/good.sh
if "$PY" tools/check_hosting_exit.py "$NC12B" >"$TMP/out12b" 2>&1; then
    ok "NC12b 行文/创建/PR 侧写不误报（收口边界 = issue 评论与标签写）"
else
    bad "NC12b 期望 rc=0, 实际输出: $(cat "$TMP/out12b")"
fi

# ── NC13 factory-portability 负控制：P1/P2/P3 都会拦，中性形态不误报 ──
# 夹具 = 临时 git 仓（含最小 DISTRIBUTION.json + prompts）；bad 形态三规则
# 各一处（宿主专名 / omp 旁路 / 平铺 path hack），ok 形态全中性。
NC13="$TMP/nc13"; mkdir -p "$NC13/.factory/prompts" "$NC13/.factory/db"
git init -q "$NC13"
cat >"$NC13/.factory/DISTRIBUTION.json" <<'EOF'
{"full": ["chain.sh", "lib.py", "db/schema.sql"], "local": {}, "skip": []}
EOF
cat >"$NC13/.factory/chain.sh" <<'EOF'
# 借鉴源仓#42 审查（中性考证：不命中）
awesome-rules && steering/ x
EOF
cat >"$NC13/.factory/lib.py" <<'EOF'
import json
sys.path.insert(0, ".")
EOF
echo "db schema" >"$NC13/.factory/db/schema.sql"
printf '使用阅读范围参数\n' >"$NC13/.factory/prompts/p.md"
git -C "$NC13" add .factory
if "$PY" tools/check_factory_portability.py "$NC13" >"$TMP/out13" 2>&1; then
    bad "NC13 期望 rc=1（P1+P3 命中），实际放行"
else
    if grep -q 'P1 宿主专名' "$TMP/out13" && grep -q 'P3 path hack' "$TMP/out13"; then
        ok "NC13 P1（宿主专名）+P3（平铺 hack）被拦"
    else
        bad "NC13 输出缺 P1/P3 报告: $(cat "$TMP/out13")"
    fi
fi
# P2 引擎旁路：chain.sh 直调 omp
cat >>"$NC13/.factory/chain.sh" <<'EOF'
omp -p "x" --no-session
EOF
git -C "$NC13" add .factory
if "$PY" tools/check_factory_portability.py "$NC13" >"$TMP/out13b" 2>&1; then
    bad "NC13b 期望 rc=1（P2 命中），实际放行"
else
    grep -q 'P2 引擎旁路' "$TMP/out13b" \
        || bad "NC13b 输出缺 P2: $(cat "$TMP/out13b")"
fi
# P2 空白/续行变体（PR #71 Sourcery #3）：字面子串 "omp -p" 被绕过，
# 词边界正则必须拦 `omp   -p` 与 `omp \↵-p`。
cat >"$NC13/.factory/chain.sh" <<'EOF'
echo neutral
omp    -p "x" --no-session
EOF
git -C "$NC13" add .factory
if "$PY" tools/check_factory_portability.py "$NC13" >"$TMP/out13d" 2>&1; then
    bad "NC13d 期望 rc=1（P2 多空格变体命中），实际放行"
else
    if grep -q 'P2 引擎旁路' "$TMP/out13d"; then
        ok "NC13d P2 多空格变体（omp   -p）被拦"
    else
        bad "NC13d 输出缺 P2: $(cat "$TMP/out13d")"
    fi
fi
cat >"$NC13/.factory/chain.sh" <<'EOF'
echo neutral
omp \
    -p "x" --no-session
EOF
git -C "$NC13" add .factory
if "$PY" tools/check_factory_portability.py "$NC13" >"$TMP/out13e" 2>&1; then
    bad "NC13e 期望 rc=1（P2 续行变体命中），实际放行"
else
    if grep -q 'P2 引擎旁路' "$TMP/out13e"; then
        ok "NC13e P2 续行变体（omp \\↵-p）被拦"
    else
        bad "NC13e 输出缺 P2: $(cat "$TMP/out13e")"
    fi
fi
# P3 点号空白变体（与 P2 同根因）：`sys . path . insert` 是合法 Python。
cat >"$NC13/.factory/lib.py" <<'EOF'
import json
sys . path . insert (0, ".")
EOF
git -C "$NC13" add .factory
if "$PY" tools/check_factory_portability.py "$NC13" >"$TMP/out13f" 2>&1; then
    bad "NC13f 期望 rc=1（P3 空白点号变体命中），实际放行"
else
    if grep -q 'P3 path hack' "$TMP/out13f"; then
        ok "NC13f P3 空白点号变体（sys . path . insert）被拦"
    else
        bad "NC13f 输出缺 P3: $(cat "$TMP/out13f")"
    fi
fi
NC13C="$TMP/nc13c"; mkdir -p "$NC13C/.factory/prompts" "$NC13C/.factory/db"
echo "db schema" >"$NC13C/.factory/db/schema.sql"
cp "$NC13/.factory/DISTRIBUTION.json" "$NC13C/.factory/"
cat >"$NC13C/.factory/chain.sh" <<'EOF'
source lib.sh
omp_node . log 5m -- "prompt"
EOF
cat >"$NC13C/.factory/lib.py" <<'EOF'
import json
print(json.dumps({"ok": 1}))
EOF
printf '仓库参数注入\n' >"$NC13C/.factory/prompts/p.md"
git -C "$NC13C" add .factory
if "$PY" tools/check_factory_portability.py "$NC13C" >"$TMP/out13c" 2>&1; then
    ok "NC13c 中性形态零误报（源仓#NN 考证 / omp_node / 无 hack）"
else
    bad "NC13c 期望 rc=0, 实际: $(cat "$TMP/out13c")"
fi
# ── NC14 git-sealing 负控制：R1/R2/R3 都会拦，中性形态不误报 ──────────
# 夹具 = 临时 git 仓（含未密封 test_*.py + conftest 与登记表原件）。
NC14="$TMP/nc14"; mkdir -p "$NC14/mylib/tests" "$NC14/tools"
git init -q "$NC14"
printf 'import subprocess\nsubprocess.run(["git", "init", "-q", "x"])\n' \
    >"$NC14/mylib/tests/test_bad.py"
mkdir -p "$NC14/scripts/tests"
cat >"$NC14/scripts/tests/test_hermetic_git.py" <<'EOF'
GIT_FIXTURE_CASES = []
EOF
cp tools/check_git_sealing.py "$NC14/tools/"
git -C "$NC14" add -A
if "$PY" tools/check_git_sealing.py "$NC14" >"$TMP/out14" 2>&1; then
    bad "NC14 期望 rc=1（R1 未密封+R3 未登记），实际放行"
else
    if grep -q 'R1 conftest 未密封' "$TMP/out14" \
       && grep -q 'R3 负控制登记缺' "$TMP/out14"; then
        ok "NC14 R1（conftest 未密封）+R3（登记缺）被拦"
    else
        bad "NC14 输出缺 R1/R3 报告: $(cat "$TMP/out14")"
    fi
fi
# R2：test*.sh 调 git 无顶层 unset
printf '#!/bin/sh\ngit init -q x\n' >"$NC14/scripts/test_bad.sh"
git -C "$NC14" add -A
if "$PY" tools/check_git_sealing.py "$NC14" >"$TMP/out14b" 2>&1; then
    bad "NC14b 期望 rc=1（R2 命中），实际放行"
else
    if grep -q 'R2 shell 未密封' "$TMP/out14b"; then
        ok "NC14b R2（shell 未密封）被拦"
    else
        bad "NC14b 输出缺 R2: $(cat "$TMP/out14b")"
    fi
fi
# 中性形态：密封 conftest + 登记完备 + shell 有 unset → 零误报
cat >"$NC14/mylib/tests/conftest.py" <<'EOF'
import os
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
    os.environ.pop(_k, None)
EOF
cat >"$NC14/scripts/tests/test_hermetic_git.py" <<'EOF'
GIT_FIXTURE_CASES = [("mylib", "tests/test_bad.py::x")]
EOF
printf '#!/bin/sh\nunset GIT_DIR GIT_WORK_TREE\ngit init -q x\n' \
    >"$NC14/scripts/test_bad.sh"
git -C "$NC14" add -A
if "$PY" tools/check_git_sealing.py "$NC14" >"$TMP/out14c" 2>&1; then
    ok "NC14c 中性形态零误报（密封+登记+unset 全就位）"
else
    bad "NC14c 期望 rc=0, 实际: $(cat "$TMP/out14c")"
fi
# ── 汇总 ───────────────────────────────────────────────────────────────
if [ "$fails" -gt 0 ]; then
    echo "checker-self-test: $fails 项失败"
    exit 1
fi
echo "checker-self-test: 全部通过"
