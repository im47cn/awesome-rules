#!/bin/bash
# SessionEnd hook — skill-evo 异步会话总结入口
# 设计原则：同步段极薄（只 nohup spawn），任何情况 exit 0，绝不阻塞会话结束。
# 防递归：由本 hook 派生的后台进程带 AR_SKILL_EVO_CHILD=1，再次进入本脚本即退出
# （claude -p 子进程会继承该标记，即使其 hooks 未被 --settings 禁用也不会再触发）。

[ "${AR_SKILL_EVO_ENABLED:-1}" = "1" ] || exit 0   # 总开关
[ -z "${AR_SKILL_EVO_CHILD:-}" ] || exit 0          # 防递归
command -v python3 >/dev/null 2>&1 || exit 0

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
EVO="$PLUGIN_ROOT/skills/skill-evo/scripts/evo.py"
[ -f "$EVO" ] || exit 0

HOOK_JSON="$(mktemp "${TMPDIR:-/tmp}/ar-skill-evo.XXXXXX")"
cat > "$HOOK_JSON"

nohup env AR_SKILL_EVO_CHILD=1 python3 "$EVO" run \
  --hook-json-file "$HOOK_JSON" >/dev/null 2>&1 &

exit 0
