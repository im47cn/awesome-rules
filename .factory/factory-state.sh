#!/usr/bin/env bash
# factory-state.sh — 标签同步器：GitHub 事实 → state.py plan → 应用。
#
# 第一性原理（防"转移实现一半"）：issue/PR 的可观测状态不由链各步骤顺手
# 写标签维护，而是本脚本从仓库可见事实（PR 存在性、reviewDecision、
# label-add 事件计数、链标记评论）整体推导并幂等收敛。链内的即时打标
# 保留作新鲜度优化；本脚本兜底完整性——漏写转移在这里不存在，因为没有
# 转移代码，只有状态函数。锁（triaging/in-progress）除外，见 state.py。
#
# 用法: factory-state.sh sync [N|--all] [--plan]
#   sync 2        同步单个 issue（含其关联 PR 两侧标签）
#   sync --all    同步所有带 factory:* 标签的 issue
#   --plan        只打印计划操作，不执行
set -u
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "不在 git 仓库" >&2; exit 2; }
FACTORY="$REPO/.factory"
# ADR-007 平台适配：codeup 后端时 slug 为占位（forge 忽略 --repo）
FORGE="${FACTORY}/forge"
if [ "$("${FORGE}" probe 2>/dev/null || true)" = codeup ]; then
  REPO_SLUG="${GH_REPO:-codeup:$(basename "${REPO}")}"
else
REPO_SLUG="${GH_REPO:-$(
  # 双 remote 布局：origin pushurl 可能多条（codeup 镜像 + github），
  # 逐条扫含 github.com 者（github remote 名优先）；443 端口形态兼容
  { git -C "$REPO" remote get-url --all --push github 2>/dev/null
    git -C "$REPO" remote get-url --all --push origin 2>/dev/null
  # grep 去 -m1（消费全量防 SIGPIPE，issue #30）；sed 1!d 语义同旧形态
  } | grep 'github\.com' | sed -E '1!d; s#^.*github\.com(:[0-9]+)?[/:]##; s#\.git$##'
)}"
fi
[ -n "$REPO_SLUG" ] || { echo "无法确定 GitHub 仓库 slug（GH_REPO 或 github remote）" >&2; exit 2; }

TARGET=""; PLAN=0
for a in "$@"; do
  case "$a" in
    --all) TARGET="--all" ;;
    --plan) PLAN=1 ;;
    *) TARGET="$a" ;;
  esac
done
[ -n "$TARGET" ] || { echo "用法: $0 sync <N|--all> [--plan]" >&2; exit 2; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

find_pr_for_issue() {  # <issue-number> → PR number（空=无）
  "${FORGE}" pr list --repo "$REPO_SLUG" --state open --limit 100 \
    --json number,body,reviewDecision,labels,state \
    | python3 -c '
import json, re, sys
n = int(sys.argv[1])
for pr in json.load(sys.stdin):
    if re.search(r"[Cc]loses #%d\b" % n, pr.get("body") or ""):
        print(pr["number"]); break
' "$1"
}

sync_one() {  # <issue-number>
  local N="$1" P="" plan=""
  "${FORGE}" issue view "$N" --repo "$REPO_SLUG" \
    --json number,state,labels,comments > "$TMP/issue.json" 2>/dev/null \
    || { echo "  issue #$N 不可读，跳过" >&2; return 0; }
  P="$(find_pr_for_issue "$N")"
  if [ -n "$P" ]; then
    "${FORGE}" pr view "$P" --repo "$REPO_SLUG" \
      --json number,state,reviewDecision,labels > "$TMP/pr.json"
    "${FORGE}" api "repos/${REPO_SLUG}/issues/${P}/events" --paginate > "$TMP/events.json"
    plan="$(python3 "$FACTORY/state.py" plan \
      --issue "$TMP/issue.json" --pr "$TMP/pr.json" --events "$TMP/events.json")"
  else
    plan="$(python3 "$FACTORY/state.py" plan --issue "$TMP/issue.json")"
  fi

  local phase; phase="$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["phase"])')"
  echo "issue #$N phase=${phase}"

  if [ "$PLAN" = 1 ]; then
    printf '%s' "$plan" | python3 -c 'import json,sys
for o in json.load(sys.stdin)["ops"]:
    print("  [plan] %s %s %s" % (o["target"], o["op"], o["label"]))'
    return 0
  fi

  printf '%s' "$plan" | python3 -c 'import json,sys
for o in json.load(sys.stdin)["ops"]:
    print("%s\t%s\t%s" % (o["target"], o["op"], o["label"]))' \
    | while IFS=$'\t' read -r tgt op label; do
        if [ "$tgt" = issue ]; then
          "${FORGE}" issue edit "$N" --repo "$REPO_SLUG" "--${op}-label" "$label" >/dev/null \
            && echo "  [label] issue $op $label" \
            || echo "  [label] issue $op $label 失败（仅告警）" >&2
        else
          "${FORGE}" pr edit "$P" --repo "$REPO_SLUG" "--${op}-label" "$label" >/dev/null \
            && echo "  [label] pr $op $label" \
            || echo "  [label] pr $op $label 失败（仅告警）" >&2
        fi
      done
}

if [ "$TARGET" = "--all" ]; then
  { "${FORGE}" issue list --repo "$REPO_SLUG" --state all --limit 200 --json number,labels \
      | python3 -c '
import json, sys
for i in json.load(sys.stdin):
    if any(l["name"].startswith("factory:") for l in i["labels"]):
        print(i["number"])'
    # 零标签 issue 也会被 open PR 关联（链中途死亡 → trap 清标签但 PR 已建），
    # 并入 PR 的 closingIssues 引用，--all 才能收敛完整
    "${FORGE}" pr list --repo "$REPO_SLUG" --state open --limit 100 \
      --json closingIssuesReferences --jq '.[].closingIssuesReferences[].number'; } \
    | sort -un | while read -r N; do sync_one "$N"; done
else
  sync_one "$TARGET"
fi
