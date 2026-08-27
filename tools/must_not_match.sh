# shellcheck shell=sh
# must-not 扫描：秘密模式 grep 门（由 gauntlet.sh 与 test_gauntlet_checks.sh 共用）。
# 语义契约见 steering/testing-standards.md「自建关卡脚本的反作弊要求」。
# shellcheck disable=SC2034  # SECRET_PATTERN 由 source 方消费，本文件内不使用

# SECRET_PATTERN 锚定"凭据名 + 赋值 + 引号内 ≥8 字符字面量"形态：
# 裸词（如 token）在本仓有合法用途（LLM token 计数），误报的修复属于
# 模式本身，绝不属于排除清单。标识符内的括号（[e]）防止模式字面量自匹配。
SECRET_PATTERN='((api[_-]?key|s[e]cret|passw[o]rd|pass[w]d|auth[_-]?t[o]ken|access[_-]?key)["'"'"']?[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"']{8,}["'"'"'])|BEGIN[[:space:]]+[A-Z ]*PRIVATE'

# 扫描面两层原则（2026-08-23 结构性修复）：
# 1. 仓库内 = tracked 面：git ls-files 是唯一清单——gitignored 运行产物
#   （.factory/artifacts、.crush …）与链 worktree 检出副本
#   （.factory/worktrees 含 LLM implement 产物）天然出局。此前手工
#   --exclude-dir 清单与 .gitignore 必然漂移（md_link_check 双实证同根因）。
# 2. tracked vendored（doc-gen Astro 模板）用显式排除——dist/node_modules/
#   template 里的 password:/token: 是字段名不是泄漏凭据，本仓不可能在那里
#   引入凭据。排除是范围对准，不是刷分（与覆盖率排除生成代码同理）。
# 仓库外（自测夹具等非 git 路径）：退化为对给定文件直查。
# grep 的 rc 必须显式捕获：无匹配的 rc=1 是好路径，裸 grep 会触发
# 调用方 set -e 直接杀死脚本（NC3 回归）。
_EXCLUDE_TRACKED_VENDORED='^skills/doc-gen/scripts/template/'
_SCAN_EXTS='\.py$|\.sh$|\.yml$|\.yaml$|\.js$'

_all_args_inside_repo() {
    # _all_args_inside_repo <repo-root> <path>...：每个 arg 都存在且位于 repo 内
    # pwd -P 双侧物理化（PR #71 附记）：逻辑 pwd 与 git rev-parse 的物理输出在
    # 符号链接挂载点（macOS /tmp→/private/tmp）分叉——worktree 场景 args 被
    # 误判"仓库外"走退化分支，目录名直传 grep 报 Is a directory（rc2 假失败，
    # fail-closed 误伤合法环境；/tmp/ar-pr71 实测复现）
    _root=$(cd "$1" 2>/dev/null && pwd -P) || return 1
    shift
    for _p in "$@"; do
        [ -e "$_p" ] || return 1
        case "$(cd "$_p" 2>/dev/null && pwd -P)" in
            "$_root"|"$_root"/*) ;;
            *) return 1 ;;
        esac
    done
    return 0
}

must_not_match() {
    _pat=$1
    shift
    _rc=0
    if _root=$(git rev-parse --show-toplevel 2>/dev/null) \
        && _all_args_inside_repo "$_root" "$@"; then
        # tracked 面：ls-files（受 _root 锚定，hook 注入的 GIT_* 不影响发现）
        _files=$(git -C "$_root" ls-files -- "$@" \
            | LC_ALL=C grep -Ev "$_EXCLUDE_TRACKED_VENDORED" \
            | LC_ALL=C grep -E "$_SCAN_EXTS" || true)
        if [ -n "$_files" ]; then
            # 判定按输出而非 rc：多批 xargs 下 grep rc1（无命中）被聚合为
            # 123，rc 通道不可分。命中 = stdout 非空；损坏 = 无命中且
            # stderr 非空（grep 对不可读文件报 rc2 并写 stderr）。
            _errf=$(mktemp) || { echo "must-not: mktemp 失败" >&2; return 2; }
            _hits=$(printf '%s\n' "$_files" \
                | (cd "$_root" && xargs grep -InE -- "$_pat" 2>"$_errf")) || :
            if [ -n "$_hits" ]; then
                echo "must-not 命中: ${_pat}" >&2
                printf '%s\n' "$_hits" | sed -n '1,20p' >&2
                rm -f "$_errf"
                return 1
            fi
            if [ -s "$_errf" ]; then
                echo "must-not 检查自身损坏（grep stderr）:" >&2
                sed -n '1,5p' "$_errf" >&2
                rm -f "$_errf"
                return 2
            fi
            rm -f "$_errf"
        fi
        return 0
    fi
    # 仓库外路径（自测夹具）：rc 通道可分，沿用 rc 映射
    grep -InE -- "$_pat" "$@" || _rc=$?
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
