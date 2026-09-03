#!/bin/sh
# sourcery-gate.sh 功能回归测试（issue #123）：语言面收紧到 CLI 实测有效集 py/ts/js，
# php/go/java/cs 显式跳过不空转（fail-open → 显式降级）。
# 功能回归测试，不占 NC 编号——NC 登记表在 steering/ 周界（本文件不越界登记）。
set -e
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 测试密封性（steering/testing-standards.md §测试密封性，ADR-010）：
# 本测试不调 git，顶层剥除 hook 注入的 GIT_* 属惯例防御（防未来演化时仓库发现被劫持）。
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE

fails=0
ok()  { echo "  ok:   $1"; }
bad() { echo "  FAIL: $1"; fails=$((fails + 1)); }

# gate 用 bash 数组，必须以 bash 调用；gate 路径在顶层 cd 后立即定死
# （子 shell 内 cd "$FIX" 后 $PWD 已指向夹具，不能在捕获式里现取 $PWD）
GATE=$PWD/tools/git/lefthook/sourcery-gate.sh

# ── stub sourcery（stub-CLI 模式，同 .factory/tests/test_sync_from_upstream.py 范式）──
# 记录每次调用的参数行到 $STUB/calls，退出码取环境 STUB_RC（缺省 0）
STUB=$TMP/stub
mkdir -p "$STUB/bin"
cat >"$STUB/bin/sourcery" <<EOF
#!/bin/sh
printf '%s\n' "\$*" >>"$STUB/calls"
exit "\${STUB_RC:-0}"
EOF
chmod +x "$STUB/bin/sourcery"

# 夹具：每 case 独立目录 + 空 .sourcery.yaml（stub 不读内容，opt-in 信号只需存在）
# + case 涉及的同名空源文件（gate 仅做后缀匹配，创建只为稳妥）
mkfix() {
  FIX=$(mktemp -d "$TMP/fix.XXXXXX")
  : >"$FIX/.sourcery.yaml"
  for f in "$@"; do
    mkdir -p "$FIX/$(dirname "$f")"
    : >"$FIX/$f"
  done
}

# ── C1 纯 php（issue #123 复现）：CLI 不扫 .php → gate 须显式跳过、零调用 ──
: >"$STUB/calls"
mkfix src/WopClient.php src/Transport/CurlTransport.php
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" bash "$GATE" \
  src/WopClient.php src/Transport/CurlTransport.php 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C1 纯 php rc=0"; else bad "C1 纯 php rc=$rc（期望 0）"; fi
if [ ! -s "$STUB/calls" ]; then ok "C1 零 CLI 调用"; else bad "C1 stub 被调用：$(sed -n '1p' "$STUB/calls")"; fi
if printf '%s\n' "$out" | grep -q '不在 CLI 实测支持面'; then ok "C1 显式跳过提示"; else bad "C1 无「不在 CLI 实测支持面」，输出：$out"; fi

# ── C2 实测有效三语言全部进入评审，参数完整一次传齐 ──
: >"$STUB/calls"
mkfix a.py b.ts c.js
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" bash "$GATE" a.py b.ts c.js 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C2 py/ts/js rc=0"; else bad "C2 py/ts/js rc=$rc（期望 0）"; fi
if [ "$(wc -l <"$STUB/calls")" -eq 1 ]; then ok "C2 恰一次 CLI 调用"; else bad "C2 调用 $(wc -l <"$STUB/calls") 次（期望 1）"; fi
if [ "$(sed -n '1p' "$STUB/calls")" = "review --check --config .sourcery.yaml a.py b.ts c.js" ]; then
  ok "C2 首行参数完整"
else
  bad "C2 首行：$(sed -n '1p' "$STUB/calls")"
fi

# ── C3 CLI 非零退出码透传并拦截 ──
: >"$STUB/calls"
mkfix a.py
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" STUB_RC=3 bash "$GATE" a.py 2>&1) || rc=$?
if [ "$rc" -eq 3 ]; then ok "C3 rc 透传=3"; else bad "C3 rc=$rc（期望 3）"; fi
if printf '%s\n' "$out" | grep -q 'push 被拦'; then ok "C3 拦截提示"; else bad "C3 无「push 被拦」，输出：$out"; fi
if [ "$(sed -n '1p' "$STUB/calls")" = "review --check --config .sourcery.yaml a.py" ]; then
  ok "C3 首行参数"
else
  bad "C3 首行：$(sed -n '1p' "$STUB/calls")"
fi

# ── C4 混合输入不阻断：php 显式跳过，py 照常评审 ──
: >"$STUB/calls"
mkfix x.php y.py
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" bash "$GATE" x.php y.py 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C4 php+py rc=0"; else bad "C4 php+py rc=$rc（期望 0）"; fi
if [ "$(wc -l <"$STUB/calls")" -eq 1 ]; then ok "C4 恰一次 CLI 调用"; else bad "C4 调用 $(wc -l <"$STUB/calls") 次（期望 1）"; fi
if [ "$(sed -n '1p' "$STUB/calls")" = "review --check --config .sourcery.yaml y.py" ]; then
  ok "C4 仅 y.py 进 CLI（精确比对蕴含 x.php 未进）"
else
  bad "C4 首行：$(sed -n '1p' "$STUB/calls")"
fi
if printf '%s\n' "$out" | grep -q '不在 CLI 实测支持面'; then ok "C4 x.php 显式跳过提示"; else bad "C4 无「不在 CLI 实测支持面」，输出：$out"; fi

# ── C5 未 opt-in（无 .sourcery.yaml）：跳过不评审 ──
: >"$STUB/calls"
FIX=$(mktemp -d "$TMP/fix.XXXXXX")   # 不放 .sourcery.yaml
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" bash "$GATE" a.py 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C5 未 opt-in rc=0"; else bad "C5 未 opt-in rc=$rc（期望 0）"; fi
if [ ! -s "$STUB/calls" ]; then ok "C5 零 CLI 调用"; else bad "C5 stub 被调用：$(sed -n '1p' "$STUB/calls")"; fi
if printf '%s\n' "$out" | grep -q '未 opt-in'; then ok "C5 opt-in 提示"; else bad "C5 无「未 opt-in」，输出：$out"; fi

# ── C6 sourcery CLI 缺失：fail-safe 跳过 ──
# 目录占位使 command -v 必不命中（bash 3.2 实测：不可执行常规文件仍会被命中，
# 目录在 PATH 查找中被跳过）——宿主机真装有 sourcery 也密封
: >"$STUB/calls"
mkfix
NOCLI=$TMP/nocli
mkdir -p "$NOCLI/bin/sourcery"
rc=0; out=$(cd "$FIX" && PATH="$NOCLI/bin:/bin:/usr/bin" bash "$GATE" a.py 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C6 CLI 缺失 rc=0"; else bad "C6 CLI 缺失 rc=$rc（期望 0）"; fi
if [ ! -s "$STUB/calls" ]; then ok "C6 零 CLI 调用"; else bad "C6 stub 被调用"; fi
if printf '%s\n' "$out" | grep -q '未安装'; then ok "C6 未安装提示"; else bad "C6 无「未安装」，输出：$out"; fi

# ── C7 未实测语言（go/java/cs）同按不在支持面跳过 ──
: >"$STUB/calls"
mkfix a.go b.java c.cs
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" bash "$GATE" a.go b.java c.cs 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C7 go/java/cs rc=0"; else bad "C7 go/java/cs rc=$rc（期望 0）"; fi
if [ ! -s "$STUB/calls" ]; then ok "C7 零 CLI 调用"; else bad "C7 stub 被调用：$(sed -n '1p' "$STUB/calls")"; fi
if printf '%s\n' "$out" | grep -q '不在 CLI 实测支持面'; then ok "C7 显式跳过提示"; else bad "C7 无「不在 CLI 实测支持面」，输出：$out"; fi

# ── C8 非语言文件（README.md）：跳过 ──
: >"$STUB/calls"
mkfix
rc=0; out=$(cd "$FIX" && PATH="$STUB/bin:$PATH" bash "$GATE" README.md 2>&1) || rc=$?
if [ "$rc" -eq 0 ]; then ok "C8 非语言文件 rc=0"; else bad "C8 非语言文件 rc=$rc（期望 0）"; fi
if [ ! -s "$STUB/calls" ]; then ok "C8 零 CLI 调用"; else bad "C8 stub 被调用"; fi
if printf '%s\n' "$out" | grep -q '跳过'; then ok "C8 跳过提示"; else bad "C8 无「跳过」，输出：$out"; fi

[ "$fails" -eq 0 ] || { echo "sourcery-gate 功能回归测试失败 $fails 项" >&2; exit 1; }
echo "sourcery-gate 功能回归测试全部通过（C1-C8）"
