#!/bin/sh
# dispatch_watch.sh 正/负控制自测：证明 L1 守护「记录优先、只拦不可逆」语义真实存在。
# NC19 系（接续 test_pre-push-delete-guard.sh NC18 的编号；交付审查两轮修复的回归面：
# 尾斜杠所有权前缀、-z 解析的 quotepath/rename、末行无换行清单、JSON 转义、
# unborn HEAD 降级、参数校验、A 暂存态分类）。
# 每案例独立临时仓（git init，不触主仓），watcher 以 --interval 1 后台运行。
set -e
cd "$(dirname "$0")/.."

W=tools/dispatch_watch.sh
fails=0
ok()   { echo "  ok:   $1"; }
bad()  { echo "  FAIL: $1"; fails=$((fails + 1)); }

# 建带基线提交的临时仓（含已跟踪文件，供 modified/deleted/rename 用例）
newrepo() {
  REPO=$(mktemp -d /tmp/dwtest.XXXXXX)
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@t.t
  git -C "$REPO" config user.name t
  echo base > "$REPO/tracked.txt"
  (cd "$REPO" && git add tracked.txt && git commit -qm base)
}
cleanup() { [ -n "${WPID:-}" ] && kill "$WPID" 2>/dev/null || true; [ -n "${REPO:-}" ] && rm -rf "$REPO" "$LOG" || true; return 0; }
# 轮询等待事件出现（最长 ~8s）
wait_event() { # wait_event <grep 模式>
  i=0
  while [ $i -lt 16 ]; do
    grep -q "$1" "$LOG" 2>/dev/null && return 0
    sleep 0.5; i=$((i + 1))
  done
  return 1
}

# ── NC19a 参数校验：非数字 interval → rc 1 ─────────────────────────────
newrepo; LOG=$(mktemp)
printf 'tests/\n' > "$REPO/own.txt"
if bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval abc >/dev/null 2>&1; then
  bad "NC19a 非数字 interval 应 rc 1"
else
  ok "NC19a 非数字 interval → rc 1"
fi
cleanup

# ── NC19b 参数校验：缺必需参数 → rc 1 ─────────────────────────────────
if bash "$W" --own /dev/null >/dev/null 2>&1; then
  bad "NC19b 缺参数应 rc 1"
else
  ok "NC19b 缺参数 → rc 1"
fi

# ── NC19c 非 git 目录 → rc 2 ──────────────────────────────────────────
if bash "$W" --dir /tmp --own /dev/null >/dev/null 2>&1; then
  bad "NC19c 非工作树应 rc 2"
else
  rc=$?; [ "$rc" = 2 ] && ok "NC19c 非工作树 → rc 2" || bad "NC19c rc=$rc 应为 2"
fi

# ── NC19d unborn HEAD：warn 降级 + 正常记录 + rc 0 ─────────────────────
REPO=$(mktemp -d /tmp/dwtest.XXXXXX); LOG=$(mktemp)
git -C "$REPO" init -q
printf 'a/\n' > "$REPO/own.txt"
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval 1 --max 2 > "$LOG" 2>&1
rc=$?
grep -q unborn_head "$LOG" && [ "$rc" = 0 ] \
  && ok "NC19d unborn HEAD 降级运行 rc 0" || bad "NC19d rc=$rc 日志=$(cat "$LOG")"
cleanup

# ── NC19e owned 区静默：尾斜杠/无斜杠/末行无换行条目/rename 双端 owned ──
# 哨兵：清单外文件必须恰好产生 1 条事件——证明「快照→diff→判定」链路活着，
# 封死「watcher 未启动致日志空、零事件断言静默通过」的假过方向
newrepo; LOG=$(mktemp)
mkdir -p "$REPO/tests" "$REPO/tests2" && echo b > "$REPO/tests/t1.txt" && echo b > "$REPO/tests2/t1.txt"
(cd "$REPO" && git add tests tests2 && git commit -qm more)
printf 'tools/x.py\ntests/\ntests2\nold.txt' > "$REPO/own.txt"   # old.txt 无尾换行
echo base > "$REPO/old.txt" && (cd "$REPO" && git add old.txt && git commit -qm old)
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval 1 --max 5 > "$LOG" 2>&1 &
WPID=$!
sleep 1.5
mkdir -p "$REPO/tools"
echo x > "$REPO/tools/x.py"          # 文件条目 owned（目录折叠下有条目覆盖 → 跳过）
echo n > "$REPO/tests/new.py"        # 尾斜杠条目内新增
echo m >> "$REPO/tests/t1.txt"       # 尾斜杠条目内已跟踪改
echo m >> "$REPO/tests2/t1.txt"      # 无斜杠条目已跟踪改
(cd "$REPO" && git mv old.txt new.txt)   # 末行无换行条目 rename 双端 owned
echo s > "$REPO/sentry.md"           # 哨兵：唯一应报的清单外事件
wait $WPID
n=$(grep -cE 'outside|owned_deleted' "$LOG")
if [ "$n" = 1 ] && grep -q '"untracked_outside","path":"sentry.md"' "$LOG"; then
  ok "NC19e owned 区零事件 + 哨兵链路活着"
else
  bad "NC19e 事件数=$n（应恰 1 条哨兵）：$(grep -E 'outside|owned_deleted' "$LOG")"
fi
cleanup

# ── NC19f 清单外四类事件：untracked/modified/deleted/rename(真 R) ──────
newrepo; LOG=$(mktemp)
printf 'tests/\n' > "$REPO/own.txt"
# rename 素材在 watcher 启动前提交（运行中 commit 会触发 head_moved 提前退出）
echo t > "$REPO/ren.txt" && (cd "$REPO" && git add ren.txt && git commit -qm ren)
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval 1 --max 8 > "$LOG" 2>&1 &
WPID=$!
sleep 1.5
echo s > "$REPO/stray.md"
echo m >> "$REPO/tracked.txt"
sleep 1.5
rm "$REPO/tracked.txt"
(cd "$REPO" && git mv ren.txt RENAMED.txt)
wait $WPID || true
n=0
grep -q '"untracked_outside","path":"stray.md"' "$LOG" && n=$((n+1))
grep -q '"modified_outside","path":"tracked.txt"' "$LOG" && n=$((n+1))
grep -q '"deleted_outside","path":"tracked.txt"' "$LOG" && n=$((n+1))
grep -q 'rename_outside.*ren.txt -> RENAMED.txt' "$LOG" && n=$((n+1))
[ "$n" = 4 ] && ok "NC19f 四类越界事件全捕获" || bad "NC19f 仅 $n/4：$(grep outside "$LOG")"
cleanup

# ── NC19g 中文+引号路径：捕获 + 全行合法 JSON ──────────────────────────
newrepo; LOG=$(mktemp)
printf 'tests/\n' > "$REPO/own.txt"
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval 1 --max 5 > "$LOG" 2>&1 &
WPID=$!
sleep 1.5
mkdir "$REPO/中文外" && echo n > "$REPO/中文外/文档.md"
mkdir "$REPO/带\"双引\"" && echo y > "$REPO/带\"双引\"/f.md"
wait $WPID
if grep -q '中文外' "$LOG" && grep -q '带\\"双引\\"' "$LOG" \
   && python3 -c "
import json,sys
for l in open('$LOG'): json.loads(l)
" 2>/dev/null; then
  ok "NC19g 中文/引号路径捕获且 JSON 合法"
else
  bad "NC19g 日志非法或缺失：$(head -5 "$LOG")"
fi
cleanup

# ── NC19h head_moved + --kill-on-commit：kill + rc 3 ────────────────────
newrepo; LOG=$(mktemp)
printf 'tests/\n' > "$REPO/own.txt"
zsh -c 'sleep 120' & VPID=$!
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --pid $VPID --interval 1 --max 10 --kill-on-commit > "$LOG" 2>&1 &
WPID=$!
sleep 1.5
echo c > "$REPO/c.txt" && (cd "$REPO" && git add c.txt && git commit -qm c)
rc=0; wait $WPID || rc=$?
if [ "$rc" = 3 ] && grep -q head_moved "$LOG" && grep -q '"killed"' "$LOG" \
   && ! kill -0 $VPID 2>/dev/null; then
  ok "NC19h head_moved → killed + rc 3"
else
  bad "NC19h rc=$rc 日志=$(tail -3 "$LOG")"
fi
kill $VPID 2>/dev/null || true
cleanup

# ── NC19i head_moved 无 pid：rc 3，无 kill 段 ──────────────────────────
newrepo; LOG=$(mktemp)
printf 'tests/\n' > "$REPO/own.txt"
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval 1 --max 10 > "$LOG" 2>&1 &
WPID=$!
sleep 1.5
echo c > "$REPO/c.txt" && (cd "$REPO" && git add c.txt && git commit -qm c)
rc=0; wait $WPID || rc=$?
[ "$rc" = 3 ] && grep -q head_moved "$LOG" && ! grep -q '"killed"' "$LOG" \
  && ok "NC19i head_moved → rc 3 无 kill" || bad "NC19i rc=$rc"
cleanup

# ── NC19j staged add（A 暂存态）→ untracked_outside 且 code 保留 XY ────
newrepo; LOG=$(mktemp)
printf 'tests/\n' > "$REPO/own.txt"
bash "$W" --dir "$REPO" --own "$REPO/own.txt" --interval 1 --max 5 > "$LOG" 2>&1 &
WPID=$!
sleep 1.5
echo a > "$REPO/staged.md" && (cd "$REPO" && git add staged.md)
wait $WPID
grep -q '"untracked_outside","path":"staged.md","detail":"code=A ' "$LOG" \
  && ok "NC19j A 暂存态归类新增" || bad "NC19j $(grep staged "$LOG")"
cleanup

echo
[ "$fails" = 0 ] && echo "dispatch_watch 全部负控制通过" || echo "$fails 项失败"
exit $fails
