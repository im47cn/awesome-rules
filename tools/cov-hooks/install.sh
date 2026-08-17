#!/usr/bin/env bash
# 在当前 git 仓库启用变更行覆盖率红线钩子 (共享自 ~/.claude/githooks)
# 用法: bash ~/.claude/githooks/install.sh           # 启用 (设置 core.hooksPath)
#       bash ~/.claude/githooks/install.sh --remove  # 停用 (unset core.hooksPath)
set -eu

# 规范路径恒为 ~/.claude/githooks (可为指向 dotfiles 仓库的符号链接),
# 避免经链接/直连两种调用方式解析出不同文本路径, 触发"已设置不覆盖"守卫误判。
HOOKS="$HOME/.claude/githooks"
[ -d "$HOOKS" ] || { echo "✗ $HOOKS 不存在 (新机器: clone awesome-rules 后 ln -s ~/sources/awesome-rules/tools/cov-hooks ~/.claude/githooks)"; exit 1; }

if [ "${1:-}" = "--remove" ]; then
  git config --unset core.hooksPath 2>/dev/null || true
  echo "✓ 已停用覆盖率钩子"
  exit 0
fi

git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "✗ 不在 git 仓库内"; exit 1; }

cur=$(git config core.hooksPath || true)
if [ -n "$cur" ] && [ "$cur" != "$HOOKS" ]; then
  echo "✗ 本仓库已设置 core.hooksPath=$cur, 不覆盖 (如需改用共享钩子: git config core.hooksPath \"$HOOKS\")"
  exit 1
fi

# .git/hooks 下有非 sample 钩子会被 hooksPath 旁路, 提醒但不阻断
legacy=$(find "$(git rev-parse --git-dir)/hooks" -type f ! -name '*.sample' 2>/dev/null | head -1 || true)
[ -n "$legacy" ] && echo "⚠ 本仓库 .git/hooks 下存在自定义钩子, 将被共享钩子链式执行 (不会被旁路)"

git config core.hooksPath "$HOOKS"
echo "✓ 已启用: core.hooksPath=$HOOKS"
echo "  pre-commit 复用已有 coverage 产物轻检 · pre-push 全量兜底 · 变更行覆盖 ≥95%"
