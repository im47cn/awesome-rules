#!/usr/bin/env bash
#
# work-report commit 抓取脚本
# 扫描一个或多个 git 仓库，输出指定时间范围、指定 author 的提交（结构化），
# 供 work-report skill 的 AI 做语义聚合。
#
# 用法:
#   fetch-commits.sh [选项] [repo-dir ...]
#
#   选项:
#     --since <days>    天数，默认 14（即最近 14 天）
#     --author <regex>  author 过滤（多身份用 \| 连接）；默认取各仓库 git config user.email
#     --scan <dir>      扫描该目录下所有 git 仓库（替代逐个传 repo-dir）
#     --exclude <glob>  排除匹配的仓库（匹配 basename 或路径片段，可多次）；
#                       排除个人项目 / 第三方 clone / 已归档仓库
#     --team            团队模式：每条 commit 附 author email（供按成员分组，TL 场景）
#
#   无 repo-dir 且无 --scan 时，默认扫描 "$HOME/sources"
#
# 兼容 macOS 自带 bash 3.2（不使用 mapfile / 关联数组）
#
set -euo pipefail

SINCE=14
AUTHOR=""
SCAN_DIR=""
REPOS=()
EXCLUDES=()
TEAM=0

while [ $# -gt 0 ]; do
  case "$1" in
    --since)   SINCE="$2"; shift 2;;
    --author)  AUTHOR="$2"; shift 2;;
    --scan)    SCAN_DIR="$2"; shift 2;;
    --exclude) EXCLUDES+=("$2"); shift 2;;
    --team)    TEAM=1; shift;;
    -*)        echo "未知选项: $1" >&2; exit 2;;
    *)         REPOS+=("$1"); shift;;
  esac
done

# --since 校验：必须为正整数（天数）
case "$SINCE" in
  ''|*[!0-9]*) echo "✘ --since 需为正整数（天数），当前: ${SINCE}" >&2; exit 2;;
esac

# --team 校验：必须配合 --author 指定团队成员（否则会扫描目录下所有人 commit，爆炸）
if [ "$TEAM" -eq 1 ] && [ -z "$AUTHOR" ]; then
  echo "✘ --team 模式需配合 --author 指定团队成员（正则，多成员用 \\| 连接）" >&2
  exit 2
fi

# 将扫描目录下所有 git 仓库收集到 REPOS
# 注：find 对无读权限的子目录会返回非0，但管道位于进程替换 < <(...) 中，
# 其退出码不传播到主 shell（即便开启 pipefail），故不会导致脚本中断
collect_scan() {
  local d
  while IFS= read -r d; do
    [ -n "$d" ] && REPOS+=("$d")
  done < <(find "$1" -maxdepth 2 -name ".git" -type d 2>/dev/null | sed 's|/.git$||')
}

# 输出仓库的"进行中"信号：当前分支 / 未推送 commit / 未合并分支 / 工作区改动
# 作为日报"进行中/未完成"节的近似信号（git log 只反映已提交工作，覆盖不到进行中的）
wip_signal() {
  local repo="$1" branch unpushed main_branch mb unmerged raw dirty n
  branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")

  # 未推送 commit 数（需有上游分支）
  unpushed="无上游"
  if git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    n=$(git -C "$repo" rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)
    unpushed="${n:-0}"
  fi

  # 默认主分支（main 或 master）
  main_branch=""
  for mb in main master; do
    if git -C "$repo" rev-parse --verify "$mb" >/dev/null 2>&1; then
      main_branch="$mb"; break
    fi
  done

  # 未合并到主分支的本地分支
  unmerged="无"
  if [ -n "$main_branch" ]; then
    raw=$(git -C "$repo" branch --no-merged "$main_branch" 2>/dev/null \
          | sed 's/^[* ]*//' | grep -v -E "^(main|master)$" || true)
    if [ -n "$raw" ]; then
      unmerged=$(echo "$raw" | sed -n '1,5p' | tr '\n' ',' | sed 's/,$//')
    fi
  fi

  # 工作区未提交文件数
  dirty=$(git -C "$repo" status --porcelain 2>/dev/null | wc -l | tr -d '[:space:]')

  echo "# WIP: 分支=${branch} | 未推送=${unpushed} | 未合并分支=${unmerged} | 工作区=${dirty}文件"
  # 未推送 commit 最近 3 条 subject（若有上游且未推送数 > 0）
  if [ "$unpushed" != "无上游" ] && [ "$unpushed" -gt 0 ] 2>/dev/null; then
    git -C "$repo" log '@{u}..HEAD' --pretty=format:"  - %s" --no-merges -3 2>/dev/null || true
    echo
  fi
}

# 无显式仓库时确定扫描来源
if [ ${#REPOS[@]} -eq 0 ]; then
  collect_scan "${SCAN_DIR:-$HOME/sources}"
fi

if [ ${#REPOS[@]} -eq 0 ]; then
  echo "✘ 未找到任何 git 仓库（扫描 ${SCAN_DIR:-\$HOME/sources}）" >&2
  echo "  请创建 ~/.config/ar/workspaces.toml 或用 --scan 指定目录" >&2
  exit 1
fi

# 排除匹配的仓库（glob，匹配 basename 或路径片段）
is_excluded() {
  local path="$1" name pat
  name="$(basename "$path")"
  for pat in "${EXCLUDES[@]}"; do
    case "$name" in
      $pat) return 0;;
    esac
    case "$path" in
      *$pat*) return 0;;
    esac
  done
  return 1
}

# 应用排除规则
if [ ${#EXCLUDES[@]} -gt 0 ]; then
  kept=()
  for r in "${REPOS[@]}"; do
    is_excluded "$r" || kept+=("$r")
  done
  if [ ${#kept[@]} -gt 0 ]; then
    REPOS=("${kept[@]}")
  else
    REPOS=()
  fi
fi

if [ ${#REPOS[@]} -eq 0 ]; then
  echo "✘ 排除后无剩余仓库（排除规则: ${EXCLUDES[*]}）" >&2
  exit 1
fi

echo "# 工作日报数据（since: ${SINCE} 天）"
echo "# 扫描仓库数: ${#REPOS[@]}"
echo

valid=0
for repo in "${REPOS[@]}"; do
  [ -d "$repo/.git" ] || continue

  # author：参数优先，否则取该仓库 git config
  a="${AUTHOR}"
  if [ -z "$a" ]; then
    a="$(git -C "$repo" config user.email 2>/dev/null || true)"
  fi

  # 抓取该仓库的提交
  # team 模式：每条附 author email（%ae）供按成员分组；个人模式不带 author（或仅 name）
  if [ "$TEAM" -eq 1 ]; then
    fmt="%ae | %ad | %h | %s"
  elif [ -n "$a" ]; then
    fmt="%ad | %h | %s"
  else
    fmt="%an | %ad | %h | %s"
  fi
  auth_arg=""
  [ -n "$a" ] && auth_arg="--author=$a"
  logs="$(git -C "$repo" log --since="${SINCE} days ago" $auth_arg \
    --pretty=format:"$fmt" --date=short --no-merges 2>/dev/null || true)"

  # author 过滤后无匹配提交则跳过（避免 clone 的第三方仓库污染日报）
  [ -z "$logs" ] && continue

  valid=$((valid + 1))
  echo "## 仓库: $repo"
  [ -n "$a" ] && echo "# author: $a"
  echo "$logs"
  echo
  wip_signal "$repo"
  echo
done

echo "# 有提交的仓库: ${valid}"
