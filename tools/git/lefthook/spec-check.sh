#!/usr/bin/env bash
# spec 条款↔测试反向核对门（awesome-rules tools/git 分发，由 lefthook 调用）
# 用法: bash .lefthook/spec-check.sh {staged_files}
# 语义: 本次提交含"遵循 spec:<ID> 条款约定"的 spec 文档时，对该 spec 跑 spec_check.py
#       反向核对：
#       - 缺口（spec 条款无测试）→ 阻断提交
#       - 孤儿（测试有、spec 无条款）→ 阻断提交（--ignore-orphans 可降级）
#       - 无 spec 变更 / spec 文档不含 spec:<ID> 条款 → 跳过（非 spec 工作流文档）
# 判定"是 spec 文档"：文件名含 spec 子串且内容含 CLAUSE_RE 匹配的 spec:<ID> 字面量。
# 判定后缺条款仍 fail-closed（spec_check.py 零条款 rc=1）。
# 解释器缺失 / 脚本缺失 → 提示后放行（全量兜底在 CI gauntlet spec-check-self-test 层）
# 跳过门禁: git commit --no-verify
set -u

[ "$#" -gt 0 ] || exit 0

# 筛选本次提交中的 spec 文档与测试文件。lefthook 的 {staged_files} 含已删除文件
# （git rm / 重命名的源端），删除/改名 spec 或测试的提交必须放行——文件不存在
# 的直接跳过，不进入核对面（2026-08-31 审查发现：不过滤则删除类提交必被误拦）。
SPECS=()
TESTS=()
for f in "$@"; do
  [ -f "$f" ] || continue
  case "$f" in
    *spec*.md)
      # 文件名含 spec 子串不等于 spec 工作流文档（inspection.md 等普通文档）。
      # 内容不含 spec:<ID> 条款字面量 → 视为非 spec 文档跳过，不拦。
      if grep -qE 'spec:[A-Za-z0-9][A-Za-z0-9_-]*-[0-9]+' "$f"; then
        SPECS+=("$f")
      fi;;
    *.py|*.java|*.go|*.ts|*.tsx|*.js|*.jsx|*.kt) TESTS+=("$f");;
  esac
done
if [ "${#SPECS[@]}" -eq 0 ]; then
  echo "[spec-check] 无 spec 文档变更（含 spec:<ID> 条款者），跳过"
  exit 0
fi
echo "[spec-check] 检测到 spec 变更: ${SPECS[*]}"

# 解释器探测
if   command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python  >/dev/null 2>&1; then PY=python
else echo "[spec-check] 无 python 解释器，跳过（CI gauntlet 兜底）"; exit 0; fi

ROOT="$(git rev-parse --show-toplevel)"
# 双路径：分发模式（业务项目 install.sh 拷贝到 .lefthook/）与自用模式
# （本仓库根 lefthook.yml 直引 tools/git/lefthook/，spec_check.py 在 tools/）。
SPEC_CHECK="$ROOT/.lefthook/spec_check.py"
[ -f "$SPEC_CHECK" ] || SPEC_CHECK="$ROOT/tools/spec_check.py"
[ -f "$SPEC_CHECK" ] || { echo "[spec-check] 缺 spec_check.py（.lefthook/ 与 tools/ 均无），跳过（CI gauntlet 兜底）"; exit 0; }

# 本次提交未带测试文件时，回落 tracked 测试文件清单（spec 早已合入、测试在后续提交的场景）。
# 扫 tracked 面（与 gauntlet 扫描面一致，67c2965b 原则）；显式排除 .lefthook/ 自身——
# 否则 spec_check.py 副本会被扫入，其源码中的示例串/注释会误报为孤儿标签。
if [ "${#TESTS[@]}" -eq 0 ]; then
  while IFS= read -r f; do TESTS+=("$f"); done < <(
    git ls-files '*.py' '*.java' '*.go' '*.ts' '*.tsx' '*.js' '*.jsx' '*.kt' \
      | grep -v '^\.lefthook/'
  )
fi
if [ "${#TESTS[@]}" -eq 0 ]; then
  # 有 spec 条款却无任何测试文件：全部条款按缺口计，fail-closed 拦截。
  # 不给 spec_check.py 传裸 --tests（argparse rc=2 用法错误，误导排障）。
  echo "[spec-check] 仓库无测试文件，spec 条款全部无测试，阻断提交"
  exit 1
fi

rc=0
for s in "${SPECS[@]}"; do
  echo "[spec-check] 核对 $s"
  "$PY" "$SPEC_CHECK" --spec "$s" --tests "${TESTS[@]}" || rc=$?
done
exit $rc
