#!/bin/sh
# spec_check.py 正/负控制自测：证明检查器会拦截缺口与孤儿，而不是只会放行。
# NC15 系（接续 test_gauntlet_checks.sh 的 NC1-NC14 编号，登记表见
# steering/testing-standards.md §测试密封性 / tools/check_git_sealing.py R3）。
set -e
cd "$(dirname "$0")/.."
PY=${GAUNTLET_PY:-$(command -v python3)}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fails=0
ok()  { echo "  ok:   $1"; }
bad() { echo "  FAIL: $1"; fails=$((fails + 1)); }

cat >"$TMP/spec.md" <<'EOF'
# Spec: demo（from intent.md @abc1234）

## 1. 需求条款
| ID | 条款（断言式表述） | 类型 |
|---|---|---|
| spec:demo-001 | 未登录用户访问必须返回 401 | 正例 |
| spec:demo-002 | 第三方不得访问；缺席即合法 | 否定式 |

## 5. 验收矩阵
| 条款 | 测试名 | 通过 |
|---|---|---|
| spec:demo-001 | test_unauth | [ ] |
EOF

mkdir -p "$TMP/tests"
cat >"$TMP/tests/test_demo.py" <<'EOF'
def test_unauth():
    # spec:demo-001
    assert True

def test_no_adjuster_by_default():
    # spec:demo-002 否定式：缺席即合法
    assert True
EOF

# ── NC15a 正控制：全对应 → rc 0 ────────────────────────────────────────
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" >"$TMP/pos" 2>&1; then
    ok "NC15a 全对应放行（rc 0，spec 内 ID 去重：条款表+验收矩阵重复仅计一次）"
else
    bad "NC15a 期望 rc 0，实际 rc=$?: $(head -3 "$TMP/pos")"
fi

# ── NC15b 缺口负控制：删 demo-002 测试 → 必须被拦 ───────────────────────
cat >"$TMP/tests/test_demo.py" <<'EOF'
def test_unauth():
    # spec:demo-001
    assert True
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" >"$TMP/neg1" 2>&1; then
    bad "NC15b 缺口未被拦（期望 rc!=0）"
elif grep -q '\[GAP\]' "$TMP/neg1" && grep -q 'spec:demo-002' "$TMP/neg1"; then
    ok "NC15b 缺口被拦且报告指明 spec:demo-002"
else
    bad "NC15b 被拦但未指明 demo-002: $(head -5 "$TMP/neg1")"
fi

# ── NC15c 孤儿负控制：测试有、spec 无 → 默认必须被拦 ─────────────────────
cat >"$TMP/tests/test_demo.py" <<'EOF'
def test_unauth():
    # spec:demo-001
    assert True

def test_no_adjuster_by_default():
    # spec:demo-002 否定式：缺席即合法
    assert True

def test_stray():
    # spec:demo-999 孤儿：spec 中无此条款
    assert True
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" >"$TMP/neg2" 2>&1; then
    bad "NC15c 孤儿默认未被拦（期望 rc!=0）"
elif grep -q '\[ORPHAN\]' "$TMP/neg2" && grep -q 'spec:demo-999' "$TMP/neg2"; then
    ok "NC15c 孤儿默认被拦且报告指明 spec:demo-999"
else
    bad "NC15c 被拦但未指明 demo-999: $(head -5 "$TMP/neg2")"
fi

# ── NC15d 孤儿降级正控制：--ignore-orphans → rc 0 ───────────────────────
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" --ignore-orphans >"$TMP/neg3" 2>&1; then
    ok "NC15d --ignore-orphans 孤儿降级放行（rc 0）"
else
    bad "NC15d 期望 rc 0，实际 rc=$?: $(head -3 "$TMP/neg3")"
fi

# ── NC15e 多语言正控制：--ext .java 识别 java 测试标签 ───────────────────
mkdir -p "$TMP/src/test"
cat >"$TMP/src/test/StatusTest.java" <<'EOF'
public class StatusTest {
    @Test public void unauth401() {
        // spec:demo-001
    }
}
EOF
cat >"$TMP/src/test/Demo2Test.java" <<'EOF'
public class Demo2Test {
    @Test public void absentByDefault() {
        // spec:demo-002
    }
}
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/src/test" --ext .java >"$TMP/java" 2>&1; then
    if grep -q '::unauth401' "$TMP/java" && grep -q '::absentByDefault' "$TMP/java"; then
        ok "NC15e --ext .java 识别 java 测试且测试名不退化（rc 0）"
    else
        bad "NC15e rc 0 但测试名退化为 <line N>: $(grep '<-' "$TMP/java")"
    fi
else
    bad "NC15e 期望 rc 0，实际 rc=$?: $(head -3 "$TMP/java")"
fi

# ── NC15h 多语言测试名正控制：go/ts 用例名不退化（审查项补测）─────────
mkdir -p "$TMP/src/go" "$TMP/src/ts"
cat >"$TMP/src/go/status_test.go" <<'EOF'
func TestUnauth401(t *testing.T) {
    // spec:demo-001
}
EOF
cat >"$TMP/src/ts/status.test.ts" <<'EOF'
import { test } from 'vitest'

test('should return 401', () => {
    // spec:demo-002
})
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" \
       --tests "$TMP/src/go" --ext .go --tests "$TMP/src/ts" --ext .ts \
       >"$TMP/lang" 2>&1; then
    if grep -q '::TestUnauth401' "$TMP/lang" && grep -q "::should return 401" "$TMP/lang"; then
        ok "NC15h go/ts 测试名识别（func Test\\w+ / test('描述')）"
    else
        bad "NC15h rc 0 但测试名退化: $(grep '<-' "$TMP/lang")"
    fi
else
    bad "NC15h 期望 rc 0，实际 rc=$?: $(head -3 "$TMP/lang")"
fi

# ── NC15f 混语言负控制：--ext .java 不得再扫 .py（append+default 陷阱回归）──
# argparse append + default=['.py'] 会让 --ext .java 实际得到 ['.py','.java']，
# 混语言目录中未登记的 .py 孤儿标签会误拦（2026-08-31 审查发现，已实测）。
mkdir -p "$TMP/mixed"
cp "$TMP/src/test/StatusTest.java" "$TMP/mixed/"
cp "$TMP/src/test/Demo2Test.java" "$TMP/mixed/"
cat >"$TMP/mixed/py_orphan.py" <<'EOF'
def test_irrelevant():
    # spec:demo-999 孤儿：仅存在于 .py，--ext .java 不应扫到
    assert True
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/mixed" --ext .java >"$TMP/mixed_out" 2>&1; then
    ok "NC15f --ext .java 排除 .py（混语言目录 rc 0）"
else
    bad "NC15f 期望 rc 0（.py 不应被扫入），实际 rc=$?: $(head -5 "$TMP/mixed_out")"
fi

# ── NC15g 函数体外标签负控制：.py 模块级 spec:<ID> 不得闭合缺口 ──────────
cat >"$TMP/tests/test_demo.py" <<'EOF'
# spec:demo-001 模块级注释：不在任何 test_ 函数体内，不得计入覆盖

def test_unauth():
    assert True
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" >"$TMP/mod" 2>&1; then
    bad "NC15g 模块级标签闭合了缺口（期望 rc!=0）"
elif grep -q '\[GAP\]' "$TMP/mod" && grep -q 'spec:demo-001' "$TMP/mod"; then
    ok "NC15g 模块级标签不计入覆盖，demo-001 仍按缺口拦"
else
    bad "NC15g 缺口语义异常: $(head -5 "$TMP/mod")"
fi

# ── NC15i 无标签文件负控制：文件存在但未贴 spec:<ID> → 全按缺口拦 ──────
# 2026-08-31 对照实验教训：夹具无标签会误判为"收集失效"。此用例锁定
# "收集到文件 ≠ 覆盖闭合"的语义——测试文件真实存在但没贴标签时，
# 条款仍必须按缺口拦截（防止收集逻辑被误改成"无标签文件不算数"）。
mkdir -p "$TMP/untagged"
cat >"$TMP/untagged/test_orphan.py" <<'EOF'
def test_exists_but_untagged():
    assert True
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/untagged" >"$TMP/untagged_out" 2>&1; then
    bad "NC15i 无标签文件放行了缺口（期望 rc!=0）"
elif grep -q '\[GAP\]' "$TMP/untagged_out" && grep -q 'spec:demo-001' "$TMP/untagged_out" \
     && grep -q 'spec:demo-002' "$TMP/untagged_out"; then
    ok "NC15i 文件存在但无标签：demo-001/002 仍按缺口拦"
else
    bad "NC15i 缺口语义异常: $(head -5 "$TMP/untagged_out")"
fi

# ── NC15j 粘滞作用域负控制：test_ 函数之后的标签不得闭合缺口 ────────────
# 旧逐行状态机 current_test 首次设置后永不清除：任一 test_ 函数之后的
# 模块级/普通函数注释会被误计入。锁 ast+tokenize 作用域判定。
cat >"$TMP/tests/test_demo.py" <<'EOF'
def test_unauth():
    assert True

# spec:demo-001 模块级注释（位于 test_ 函数之后）：不得计入覆盖

def helper_not_test():
    # spec:demo-002 普通函数内注释：同样不得计入
    return 1
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" >"$TMP/sticky" 2>&1; then
    bad "NC15j 粘滞标签闭合了缺口（期望 rc!=0）"
elif grep -q '\[GAP\]' "$TMP/sticky" && grep -q 'spec:demo-001' "$TMP/sticky" \
     && grep -q 'spec:demo-002' "$TMP/sticky"; then
    ok "NC15j test_ 后模块级/普通函数标签不计入，001/002 仍按缺口拦"
else
    bad "NC15j 缺口语义异常: $(head -5 "$TMP/sticky")"
fi

# ── NC15k 字符串字面量负控制：test_ 函数体内字符串里的标签不得闭合缺口 ──
cat >"$TMP/tests/test_demo.py" <<'EOF'
def test_str_literal():
    msg = "see spec:demo-001 in docs"
    assert msg

def test_docstring_literal():
    """docstring 提及 spec:demo-002 也不算注释标签"""
    assert True
EOF
if "$PY" tools/spec_check.py --spec "$TMP/spec.md" --tests "$TMP/tests" >"$TMP/strlit" 2>&1; then
    bad "NC15k 字符串字面量标签闭合了缺口（期望 rc!=0）"
elif grep -q '\[GAP\]' "$TMP/strlit" && grep -q 'spec:demo-001' "$TMP/strlit" \
     && grep -q 'spec:demo-002' "$TMP/strlit"; then
    ok "NC15k 字符串/docstring 内标签不计入，001/002 仍按缺口拦"
else
    bad "NC15k 缺口语义异常: $(head -5 "$TMP/strlit")"
fi

[ "$fails" -eq 0 ] || { echo "test_spec_check: $fails 项失败"; exit 1; }
echo "test_spec_check: 全部通过"
