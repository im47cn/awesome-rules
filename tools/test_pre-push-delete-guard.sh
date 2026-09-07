#!/bin/sh
# pre-push-delete-guard.sh 正/负控制自测：证明守卫只在「所有行 local SHA
# 全零」的纯删除 push 短路门禁，其余一律放行（fail-open）。
# NC18 系（接续 test_gauntlet_checks.sh NC17 的编号；PR #154 Sourcery
# 两条 bug_risk 修复的回归面：读错误与畸形行不得被误判为纯删除）。
# 本测试不调用 git（守卫消费的是 stdin 文本），R1/R2 密封义务不适用。
# TTY 用例（stdin 是终端须直接放行）不可移植，不在本矩阵内——已由
# 真实 push 场景验证（PR #154 推送门禁全过）。
set -e
cd "$(dirname "$0")/.."

GUARD=tools/git/lefthook/pre-push-delete-guard.sh
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fails=0
ok()  { echo "  ok:   $1"; }
bad() { echo "  FAIL: $1"; fails=$((fails + 1)); }

Z=0000000000000000000000000000000000000000   # git 空 SHA（40 位全零）
S=8838c7ab2f9d3f6a5b1c0d4e7f8a9b0c1d2e3f4a   # 非零 SHA（正常推送形态）

# ── NC18a 纯删除正控制：唯一行 local SHA 全零 → rc 0 且打印跳过提示 ────
if printf 'refs/heads/feat %s refs/heads/feat %s\n' "$Z" "$S" \
     | bash "$GUARD" >"$TMP/a" 2>&1; then
    if grep -q '纯删除' "$TMP/a"; then
        ok "NC18a 纯删除 push 短路门禁（rc 0 + 跳过提示）"
    else
        bad "NC18a rc 0 但无跳过提示: $(head -3 "$TMP/a")"
    fi
else
    bad "NC18a 期望 rc 0，实际 rc=$?: $(head -3 "$TMP/a")"
fi

# ── NC18b 正常推送负控制：local SHA 非零 → rc 1（门禁照常执行）──────────
if printf 'refs/heads/main %s refs/heads/main %s\n' "$S" "$Z" \
     | bash "$GUARD" >"$TMP/b" 2>&1; then
    bad "NC18b 正常推送被误短路（期望 rc 1）"
else
    ok "NC18b 正常推送放行给门禁（rc 1）"
fi

# ── NC18c 混合负控制：删除行 + 正常行并存 → rc 1 ───────────────────────
if printf 'refs/heads/gone %s refs/heads/gone %s\nrefs/heads/main %s refs/heads/main %s\n' \
       "$Z" "$S" "$S" "$Z" | bash "$GUARD" >"$TMP/c" 2>&1; then
    bad "NC18c 混合推送被误短路（期望 rc 1）"
else
    ok "NC18c 删除+正常混合放行给门禁（rc 1）"
fi

# ── NC18d 空 stdin 负控制：无行可判 → rc 1（宁可跑门禁）────────────────
if bash "$GUARD" </dev/null >"$TMP/d" 2>&1; then
    bad "NC18d 空 stdin 被误短路（期望 rc 1）"
else
    ok "NC18d 空 stdin 放行给门禁（rc 1）"
fi

# ── NC18e 二字段全零负控制：NF!=4 不得按纯删除短路 ─────────────────────
if printf 'unexpected %s\n' "$Z" | bash "$GUARD" >"$TMP/e" 2>&1; then
    bad "NC18e 二字段畸形行被误短路（期望 rc 1）"
else
    ok "NC18e 二字段畸形行放行给门禁（rc 1）"
fi

# ── NC18f 三字段负控制：同上 ────────────────────────────────────────────
if printf 'a b c\n' | bash "$GUARD" >"$TMP/f" 2>&1; then
    bad "NC18f 三字段畸形行被误短路（期望 rc 1）"
else
    ok "NC18f 三字段畸形行放行给门禁（rc 1）"
fi

# ── NC18g 五字段全零负控制：字段数超标的「全零行」不可信 ────────────────
if printf 'a %s c d e\n' "$Z" | bash "$GUARD" >"$TMP/g" 2>&1; then
    bad "NC18g 五字段畸形行被误短路（期望 rc 1）"
else
    ok "NC18g 五字段畸形行放行给门禁（rc 1）"
fi

# ── NC18h 读错误负控制：stdin 重定向自目录（cat 读取失败）→ rc 1 ───────
# PR #154 Sourcery：`input="$(cat)"` 未查退出码时，读错误会静默产出空串
# 走「空 stdin → exit 1」侥幸正确；但若判空逻辑变更，空串即短路面。
if bash "$GUARD" <"$TMP" >"$TMP/h" 2>&1; then
    bad "NC18h stdin 读错误被误短路（期望 rc 1）"
else
    ok "NC18h stdin 读错误放行给门禁（rc 1）"
fi

# ── NC18i tag 删除正控制：非 heads 引用形态的纯删除同样短路 ─────────────
if printf 'refs/tags/v1.0 %s refs/tags/v1.0 %s\n' "$Z" "$Z" \
     | bash "$GUARD" >"$TMP/i" 2>&1; then
    ok "NC18i tag 纯删除 push 短路门禁（rc 0，双零形态）"
else
    bad "NC18i 期望 rc 0，实际 rc=$?: $(head -3 "$TMP/i")"
fi

[ "$fails" -eq 0 ] || { echo "test_pre-push_delete_guard: $fails 项失败"; exit 1; }
echo "test_pre-push_delete_guard: 全部通过"
