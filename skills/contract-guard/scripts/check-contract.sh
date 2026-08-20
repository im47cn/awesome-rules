#!/usr/bin/env bash
# 跨仓契约模块变更检查（防呆提示，不阻断——门禁在 CI）
# 用法: check-contract.sh [--base <git-ref>] [<仓库根目录>]
# 退出码: 0=无契约模块变更; 1=有变更(已提示); 2=运行错误
set -euo pipefail

REPO_DIR="${PWD}"
BASE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    *) REPO_DIR="$1"; shift ;;
  esac
done

cd "$REPO_DIR" 2>/dev/null || { echo "错误: 目录不存在 $REPO_DIR" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "错误: 非 git 仓库 $REPO_DIR" >&2; exit 2; }

# 基准解析: 优先显式 --base, 其次 origin/master / origin/main, 退回 HEAD~1
if [[ -z "$BASE" ]]; then
  for ref in origin/master origin/main; do
    git rev-parse --verify --quiet "$ref" >/dev/null && { BASE="$ref"; break; }
  done
  [[ -z "$BASE" ]] && BASE="HEAD~1"
fi
git rev-parse --verify --quiet "$BASE" >/dev/null || { echo "错误: 基准不存在 $BASE" >&2; exit 2; }

# 契约模块自动发现: pom 的 <description> 标签内容含"契约"字样(只认 description, 注释提及不算)
# 排除聚合父模块(description 含"聚合"/"父模块"或即仓库根的 pom), 否则模块路径为 "." 全仓误报
CONTRACT_MODULES=()
while IFS= read -r m; do
  [[ -n "$m" && "$m" != "." ]] && CONTRACT_MODULES+=("$m")
done < <(
  find . -name pom.xml -not -path '*/target/*' \
    | while IFS= read -r p; do
        desc=$(grep -m1 '<description>' "$p" || true)
        [[ -z "$desc" ]] && continue
        echo "$desc" | grep -q '契约' || continue
        echo "$desc" | grep -qE '聚合|父模块' && continue
        dirname "$p" | sed 's|^\./||'
      done
)
if [[ ${#CONTRACT_MODULES[@]} -eq 0 ]]; then
  echo "未发现契约模块(pom description 含「契约」), 无需检查。"
  exit 0
fi

# diff 检测(未提交 + 已提交到基准)
CHANGED=$( { git diff --name-only "$BASE" -- ; git diff --name-only ; } | sort -u || true)
[[ -z "$CHANGED" ]] && { echo "无变更。"; exit 0; }

HITS=()
for m in "${CONTRACT_MODULES[@]}"; do
  while IFS= read -r f; do
    [[ -n "$f" ]] && HITS+=("$f")
  done < <(echo "$CHANGED" | grep -E "^${m}/" || true)
done

if [[ ${#HITS[@]} -eq 0 ]]; then
  echo "契约模块无变更(${#CONTRACT_MODULES[@]} 个模块受监控)。"
  exit 0
fi

cat >&2 <<EOF
⚠️  跨仓契约模块变更(共 ${#HITS[@]} 个文件, 基准 ${BASE})
$(printf '  - %s\n' "${HITS[@]}")

后续动作:
  1. 破坏性变更(删除/改签名 public 成员)将触发 CI japicmp 门禁, 无法静默合入;
  2. 如为破坏性变更: MR 描述注明受影响下游仓 + 迁移说明(规范: cross-repo-contract-standards.md);
  3. 通知下游仓负责人关注「契约编译」流水线结果;
  4. 涉及存储结构变更时遵守发布顺序: 建表 → 迁数据 → 下游升级 → 清理。
EOF
exit 1
