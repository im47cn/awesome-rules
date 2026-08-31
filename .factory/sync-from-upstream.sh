#!/usr/bin/env bash
# sync-from-upstream.sh — 下游从上游仓库拉取 .factory 工具链。
#
# 定位：替代「移植后手工 diff 对账」。上游是唯一真相源（.factory/
# DISTRIBUTION.json 分类），本脚本按分类三态处理：
#   full  文件：--apply 直接覆盖（零本地化）；--check 漂移即失败（门禁）
#   local 文件：永不覆盖；报告与上游的 diff 摘要，人工合并
#               （漂移的正道是 feedback-upstream 反哺，不是静默分叉）
#   skip  文件：不看（仓特定/运行时产物）
#
# 用法: sync-from-upstream.sh <upstream-path> [--check | --apply] [--anchor <ref>]
#   upstream-path  上游仓路径（工作树或 bare 仓均可——经 git show 读取）
#   --check        只报告漂移；full 文件有漂移 exit 1（可挂 CI/gauntlet）
#   --apply        full 覆盖 + local diff 摘要；写 upstream-lock.json 锚点
#   --anchor <ref> 用指定上游 ref（默认：upstream-lock.json 锚点 → main）
#
# 退出码: 0=干净/已同步  1=有漂移（--check）或应用失败  2=用法/上游不可用
#
# 首次移植仍走 README「移植到其他仓库」四步（MISSION/PERIMETER/测试门/
# 重证 kill rate）；本脚本管的是此后的一切增量。
set -euo pipefail

UP="${1:-}"; MODE="check"; ANCHOR=""
[ -n "$UP" ] || { sed -n '2,20p' "$0" >&2; exit 2; }
shift
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE="check" ;;
    --apply) MODE="apply" ;;
    --anchor) ANCHOR="${2:-}"; shift ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done

REPO="$(git rev-parse --show-toplevel)"
FACTORY="$REPO/.factory"
LOCKFILE="$FACTORY/upstream-lock.json"

# 上游可用性（bare 仓无工作树，一律经 git 对象库读）
git -C "$UP" rev-parse --git-dir >/dev/null 2>&1 \
  || { echo "上游仓不可用: $UP" >&2; exit 2; }

# 锚点解析：--anchor > 上次 lock > main（优先级左→右；下游迁移
# sync 实测：lock 读取无条件覆盖会把 --anchor main 吞掉——只在未显式
# 指定时才读 lock，--anchor 成为唯一强制追新出口）
if [ -z "${ANCHOR:-}" ]; then
  ANCHOR="$(python3 -c '
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
try: print(json.loads(p.read_text())["anchor"])
except Exception: pass' "$LOCKFILE" 2>/dev/null || true)"
fi
[ -n "$ANCHOR" ] && git -C "$UP" rev-parse --verify -q "$ANCHOR^{commit}" >/dev/null \
  || ANCHOR="main"
git -C "$UP" rev-parse --verify -q "$ANCHOR^{commit}" >/dev/null \
  || { echo "上游锚点不可解析: $ANCHOR" >&2; exit 2; }
HEAD_SHA="$(git -C "$UP" rev-parse "$ANCHOR^{commit}")"
echo "上游: ${UP} @ ${ANCHOR} (${HEAD_SHA:0:9})"

# 分发清单——从**上游**对象库读（下游本地副本可能滞后甚至缺失；
# 清单是上游主权，锚点即版本）。无清单=上游版本旧，全部按 local。
# 展开逻辑在 factory_lib.py dist-manifest（2026-08-28 自此处 heredoc 下沉，
# 铁律 4：git 子进程编排归 Python；无清单=空输出，警告走 stderr）
python3 "$FACTORY/factory_lib.py" dist-manifest "$UP" "$HEAD_SHA" > /tmp/.factory-dist.$$

# Sourcery 回归闸（2026-08-31 事故锚：追平所取上游快照早于下游已修复版，
# 100 个已清零 issue 整体回退，PR gate 才拦截——闸前移到追平时点）。
# 语义与 sourcery-review-gate 同构：exit code（0=干净 1=有 issue 其余=异常）。
# 不解析 stdout：CLI 在管道（命令替换）下精简输出、干净时零输出，
# 人类概览（Total 表/No issues detected）仅 tty 形态存在——解析它必脆。
# 注意：多文件入参须相对路径（绝对路径仅接受单个）；点目录不可整目录扫描。
_sr_py_files() {
  (cd "$REPO" && find .factory -name '*.py' -type f | sort)
}
_sr_clean() {  # 0=干净 1=有 issue 2=CLI 异常
  local files rc
  files="$(_sr_py_files | tr '\n' ' ')"
  [ -n "$files" ] || return 0
  sourcery review --check $files >/dev/null 2>&1
  rc=$?
  [ "$rc" -eq 0 ] && return 0
  [ "$rc" -eq 1 ] && return 1
  return 2
}
SR_GATE_ON=0
if [ "$MODE" = apply ] && command -v sourcery >/dev/null 2>&1; then
  SR_GATE_ON=1
  _sr_clean && echo "Sourcery 回归闸基线: .factory 干净" \
            || { echo "Sourcery 回归闸基线: .factory 已有 issue——先清零再追平（闸口径=PR gate）" >&2; exit 2; }
fi

# 上游 mode+blob（git show 丢 mode，覆盖后须恢复执行位）
up_tree() { git -C "$UP" ls-tree "$HEAD_SHA" -- ".factory/$1"; }

DRIFT=0; APPLIED=0; LOCAL_DIFF=0
while IFS=$'\t' read -r kind rel; do
  [ -n "$rel" ] || continue
  dst="$FACTORY/$rel"
  row="$(up_tree "$rel")"
  if [ -z "$row" ]; then
    echo "  [$kind] $rel: 上游不存在（上游已删？本地可退役）"
    continue
  fi
  up_blob="$(echo "$row" | awk '{print $3}')"
  up_mode="$(echo "$row" | awk '{print $1}')"
  if [ "${up_mode:0:2}" = "04" ]; then
    echo "  [$kind] $rel: 目录项——用例随源文件走，人工对齐（不做 blob 级处理）"
    continue
  fi
  if [ ! -f "$dst" ]; then
    echo "  [$kind] $rel: 本地缺失"
    [ "$kind" = full ] && DRIFT=1
    if [ "$MODE" = apply ] && [ "$kind" = full ]; then
      git -C "$UP" cat-file blob "$up_blob" > "$dst"
      chmod "${up_mode: -3}" "$dst" 2>/dev/null || chmod +x "$dst"
      echo "    → 已补齐"; APPLIED=$((APPLIED+1))
    fi
    continue
  fi
  loc_blob="$(git hash-object "$dst")"
  if [ "$loc_blob" = "$up_blob" ]; then
    continue  # 一致，静默
  fi
  if [ "$kind" = full ]; then
    echo "  [full] $rel: 漂移（本地未反哺的热修，或落后于上游）"
    DRIFT=1
    if [ "$MODE" = apply ]; then
      git -C "$UP" cat-file blob "$up_blob" > "$dst"
      chmod "${up_mode: -3}" "$dst" 2>/dev/null || chmod +x "$dst"
      echo "    → 已覆盖（本地差异若有价值，请先走 feedback-upstream 反哺）"
      APPLIED=$((APPLIED+1))
    fi
  else
    # local：只摘要，不碰
    n="$(git -C "$UP" cat-file blob "$up_blob" | diff - "$dst" 2>/dev/null | grep -c '^[<>]' || true)"
    echo "  [local] $rel: 与上游差 ${n} 行（含仓特定区，人工合并；正道=反哺后追平）"
    LOCAL_DIFF=$((LOCAL_DIFF+1))
  fi
done < /tmp/.factory-dist.$$
rm -f /tmp/.factory-dist.$$

if [ "$MODE" = apply ]; then
  # 追平后 Sourcery 回归闸：.factory 必须仍清零（不写锁点，下次重跑）
  if [ "$SR_GATE_ON" = 1 ]; then
    rc=0; _sr_clean || rc=$?
    case $rc in
      0) echo "Sourcery 回归闸通过: .factory 干净" ;;
      1) echo "Sourcery 回归闸拦截: 追平把 issue 带回 .factory（上游快照含已修复回退或新问题）" >&2
         echo "  先在本地修复这批文件后重试追平，或走 feedback-upstream.sh 反哺上游（正道），" >&2
         echo "  不得以静默回退换追平。定位: sourcery review --check \$(_sr_py_files | tr '\\n' ' ')" >&2
         exit 1 ;;
      *) echo "Sourcery 回归闸计数失败（CLI 限流/异常，fail-closed 拦截）" >&2; exit 2 ;;
    esac
  fi

  python3 - "$LOCKFILE" "$HEAD_SHA" <<'PY'
import json, sys, pathlib, datetime
p = pathlib.Path(sys.argv[1])
p.write_text(json.dumps({
    "anchor": sys.argv[2],
    "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  echo "锚点已写: $LOCKFILE @ ${HEAD_SHA:0:9}（覆盖 ${APPLIED} 个 full 文件；local 待人工 ${LOCAL_DIFF}）"
  exit 0
fi

# --check 收尾
if [ "$DRIFT" = 0 ]; then
  echo "full 面干净（local 面 ${LOCAL_DIFF} 项人工漂移不计失败）"
else
  echo "full 面有漂移：追平（--apply）或反哺（feedback-upstream.sh）二选一" >&2
  exit 1
fi
