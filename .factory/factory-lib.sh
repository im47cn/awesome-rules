#!/usr/bin/env bash
# factory-lib.sh — 链脚本共享库（source 引入，勿直接执行）。
# 与 factory_lib.py 命名成对：py 侧管解析/渲染/净化，本库管链对 issue
# 副作用的收口。调用方契约：source 前已定义 REPO / REPO_SLUG / ISSUE。
#
# 两条收口不变量（新增写点必须复用，不得旁路；详见 README 架构段）：
# 1. 链写 issue 评论唯一出口 = issue_comment()：发送前 factory_lib sanitize
#    原地中和正文中的 [factory:rejected] 子串。
# 2. 拒绝 = 单一动作 issue_reject()：落标与判据回执评论一次收口。两入口
#    （fix-issue.sh 链 / triage-batch.sh 批次）曾各自只做一半——#59 二次
#    拒绝静默实证：散落的动作必然被漏做一半。
# 3. 租约围栏（2026-08-24 多写者化）：链副作用出口（label/评论）在发送前
#    校验租约 epoch——被接管/吊销的诈尸链在出口被拒，秒级残窗由评论
#    幂等键兜底。LEASE_KEY 未设（无租约上下文）不拦。
source "${REPO}/.factory/factory-lease.sh"

# ADR-007 平台适配层：调用方（fix-issue/triage-batch）已定义 FORGE；兜底
FORGE="${FORGE:-${REPO}/.factory/forge}"


issue_label_swap() { # issue_label_swap <"删,删"|空> <"加,加"> —— 单请求原子转移
  # 逐个 add/remove 会把状态机跳变拆成可失败的顺序依赖（半途断裂=双标签或裸奔）；
  # 单请求换标签消除顺序问题。失败 return 1，终止语义由调用方决定
  # （链：exit 1 → EXIT trap 清理 + factory-state.sh sync 兜底；批次：告警下一 issue）。
  # 兼容 bash 3.2（macOS）：空 remove 不走空参 --remove-label（gh 报错），分支处理。
  # 出口围栏：租约失效（被夺/吊销）即拒绝——标签是投影，但诈尸写投影同样有毒。
  lease_guard || {
    echo "[error] 租约 ${LEASE_KEY:-?} 已失效（epoch=${LEASE_EPOCH:-?}），标签转移拒绝" >&2
    return 1
  }
  if [ -n "${1:-}" ]; then
    if "${FORGE}" issue edit "${ISSUE}" --repo "${REPO_SLUG}" \
        --remove-label "${1}" --add-label "${2}" >/dev/null 2>&1; then
      echo "  [label] -${1} +${2}"
    else
      echo "[error] 标签转移失败：-${1} +${2}（issue #${ISSUE}）" >&2
      return 1
    fi
  else
    if "${FORGE}" issue edit "${ISSUE}" --repo "${REPO_SLUG}" \
        --add-label "${2}" >/dev/null 2>&1; then
      echo "  [label] +${2}"
    else
      echo "[error] 标签添加失败：+${2}（issue #${ISSUE}）" >&2
      return 1
    fi
  fi
}

issue_comment() { # issue_comment <body-file> [dedupe-marker] —— 链写 issue 评论的唯一出口
  # 安全不变量在出口：发送前 factory_lib sanitize 原地中和正文中的
  # [factory:rejected] 子串——链产正文（LLM reasons 等）可能回显用户评论
  # 里的标记，state.py 子串扫描会把携带标记的链评论当人工覆盖、永久钉死
  # rejected。渲染器不各自记得，出口统一管。中和失败 fail-closed 不发送
  # （防毒丸放出），正文文件保留供排查。
  #
  # 幂等键（可选第二参）：给正文尾埋 <!-- marker --> 并发送前查重——
  # fence_check 与 gh 调用之间的秒级残窗里，诈尸链可能重复发回执；
  # 命中即视为已发送（return 0），漏网代价从"重复评论"降为"无"。
  # 标记刻意不含 [factory:rejected] 子串（sanitize/state.py 双通道安全）。
  python3 "${REPO}/.factory/factory_lib.py" sanitize "${1}" || {
    echo "  [warn] 评论正文标记中和失败（${1}），不发送" >&2; return 1; }
  lease_guard || {
    echo "[error] 租约 ${LEASE_KEY:-?} 已失效（epoch=${LEASE_EPOCH:-?}），评论拒绝（防诈尸副作用）" >&2
    return 1
  }
  if [ -n "${2:-}" ]; then
    if "${FORGE}" issue view "${ISSUE}" --repo "${REPO_SLUG}" --json comments 2>/dev/null \
        | python3 -c 'import json, sys
m = "<!-- " + sys.argv[1] + " -->"
comments = json.load(sys.stdin).get("comments") or []
sys.exit(0 if any(m in (c.get("body") or "") for c in comments) else 1)' "$2"; then
      echo "  [dedupe] 回执已存在（${2}），跳过评论" >&2
      return 0
    fi
    printf '\n<!-- %s -->\n' "$2" >> "${1}"
  fi
  "${FORGE}" issue comment "${ISSUE}" --repo "${REPO_SLUG}" --body-file "${1}"
}

issue_reject() { # issue_reject <remove-csv|空> <triage.json> —— 拒绝的单一动作
  # 落标（→ factory:rejected）+ 判据回执评论，一次收口：
  #   <remove-csv>  落标同时原子移除的标签。链入口传 "factory:triaging,
  #                 factory:in-progress"；批次入口（零标签 issue）传 ""
  #   <triage.json> 判据源；回执渲染于同目录 reject-receipt.md
  # 失败语义分两级：落标失败 return 1——裁决未落定，调用方终止/跳过；
  # 回执生成/评论失败仅告警——裁决已由标签落定，回执是透明度而非门，
  # 正文留档可手动补发。评论经 issue_comment 唯一出口，标记中和不因入口
  # 不同而绕过；回执刻意不含裸标记——标记评论通道保留给人类手动覆盖。
  # 回执带幂等键：同轮次重放（诈尸残窗/人工重跑）查重跳过；链侧带轮次
  # ROUND、批次侧固定 batch——同 issue 两入口的回执键天然互不冲突。
  local marker="factory:receipt:issue-${ISSUE}:r${ROUND:-batch}"
  local dir
  dir="$(dirname "$2")"
  issue_label_swap "${1:-}" "factory:rejected" || return 1
  if python3 "${REPO}/.factory/factory_lib.py" receipt "$2" \
      > "${dir}/reject-receipt.md" 2>/dev/null; then
    if issue_comment "${dir}/reject-receipt.md" "${marker}" >/dev/null 2>&1; then
      echo "  [receipt] 拒绝回执已评论到 issue #${ISSUE}"
    else
      echo "  [warn] 拒绝回执评论失败，正文在 ${dir}/reject-receipt.md（可手动补发）" >&2
    fi
  else
    echo "  [warn] 拒绝回执生成失败（triage.json 解析异常），跳过评论" >&2
  fi
}
