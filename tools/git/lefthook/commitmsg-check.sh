#!/usr/bin/env bash
# commit message 规范校验（awesome-rules tools/git 分发，由 lefthook 调用）
# 用法: bash .lefthook/commitmsg-check.sh <msg-file>
# 单一规则源: commitlint + 项目内 commitlint.config.js；缺 commitlint 时自动安装（一次性）。
# 无 node/npm 时提示后放行 —— commit 钩子不阻塞环境问题，只拦规范违规。
set -u
MSG_FILE="${1:-}"

# git 特殊提交放行（merge/revert/squash 自动生成，不适用规范）
sed -n '1p' "$MSG_FILE" | grep -qE '^(Merge |Revert |Auto-Merged )' && exit 0
grep -vE '^\s*(#|$)' "$MSG_FILE" | grep -q . || exit 0

# 无 commitlint → 有 npm 则自动安装；装完优先重新 command -v（Windows/非标
# prefix 下 npm prefix -g 路径可能不存在，exec 失败会阻断提交，违背本脚本
# "环境问题放行"原则），再回退 npm prefix 绝对路径（受限 PATH 下 command -v 找不到）
CL="$(command -v commitlint || true)"
if [ -z "$CL" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[commitmsg] 首次使用: 自动安装 commitlint（一次性，约几十秒）"
    npm install -g @commitlint/cli @commitlint/config-conventional >/dev/null 2>&1 || {
      echo "⚠ [commitmsg] 安装失败，本次放行；手动执行: npm install -g @commitlint/cli @commitlint/config-conventional"
      exit 0
    }
    CL="$(command -v commitlint || true)"
    [ -n "$CL" ] || CL="$(npm prefix -g)/bin/commitlint"
    [ -x "$CL" ] || {
      echo "⚠ [commitmsg] 已安装但未定位到可执行文件（$CL），本次放行"
      exit 0
    }
  else
    echo "⚠ [commitmsg] 无 node/npm，暂无法校验；装 node 后首次提交自动安装 commitlint"
    exit 0
  fi
fi

# 规则配置是分发物之一，缺失说明未跑 install.sh
[ -f "$(git rev-parse --show-toplevel)/commitlint.config.js" ] || {
  echo "⚠ [commitmsg] 缺 commitlint.config.js，请跑 awesome-rules tools/git/install.sh；本次放行"
  exit 0
}

exec "$CL" --edit "$MSG_FILE"
