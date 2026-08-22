# shellcheck shell=sh
# must-not 扫描：秘密模式 grep 门（由 gauntlet.sh 与 test_gauntlet_checks.sh 共用）。
# 语义契约见 steering/testing-standards.md「自建关卡脚本的反作弊要求」。
# shellcheck disable=SC2034  # SECRET_PATTERN 由 source 方消费，本文件内不使用

# SECRET_PATTERN 锚定"凭据名 + 赋值 + 引号内 ≥8 字符字面量"形态：
# 裸词（如 token）在本仓有合法用途（LLM token 计数），误报的修复属于
# 模式本身，绝不属于排除清单。标识符内的括号（[e]）防止模式字面量自匹配。
SECRET_PATTERN='((api[_-]?key|s[e]cret|passw[o]rd|pass[w]d|auth[_-]?t[o]ken|access[_-]?key)["'"'"']?[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"']{8,}["'"'"'])|BEGIN[[:space:]]+[A-Z ]*PRIVATE'

# must_not_match <pattern> <path>...：
#   命中即失败（rc 1，grep 输出即命中证据）；
#   无匹配通过（grep rc 1）；
#   grep 自身损坏（rc >= 2：坏模式、不可读输入）是检查的硬失败（rc 2），绝不是通过。
must_not_match() {
    _pat=$1
    shift
    # BSD grep 要求选项在 -- 终结符之前，否则 --include 被当文件操作数。
    # --exclude-dir 排除生成/ vendored 产物：doc-gen template 整棵是 Astro
    # 构建输出树（dist/public/scalar.js 等），其中的 password:/token: 是
    # 字段名不是泄漏凭据，本仓不可能在那里引入凭据——排除是范围对准，
    # 不是刷分（与覆盖率排除生成代码同理）。
    # grep 的 rc 必须显式捕获：无匹配的 rc=1 是好路径，裸 grep 会触发
    # 调用方 set -e 直接杀死脚本（NC3 回归）。
    _rc=0
    grep -rEn \
        --include='*.py' --include='*.sh' --include='*.yml' --include='*.yaml' --include='*.js' \
        --exclude-dir='dist' --exclude-dir='node_modules' --exclude-dir='vendor' \
        --exclude-dir='template' \
        -- "$_pat" "$@" || _rc=$?
    if [ "$_rc" -eq 0 ]; then
        echo "must-not 命中: ${_pat}" >&2
        return 1
    elif [ "$_rc" -eq 1 ]; then
        return 0
    else
        echo "must-not 检查自身损坏 (grep rc=${_rc})" >&2
        return 2
    fi
}
