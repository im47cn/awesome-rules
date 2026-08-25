#!/usr/bin/env python3
"""dispatch-liveness — 调度器活性检查（回归第三层组件，2026-08-25）。

两种死法都要抓（动机：slug 回归事件暴露的可见性盲区）：
1. 进程在跑但一直失败：cron-dispatch.sh 连击 ≥3 轮 exit 2 会写
   .factory/metrics/dispatch-stalled —— 本检查发现它即 FAIL。
2. 进程根本没跑（LaunchAgent 断档，历史实测 13h）：streak 计数文件
   locks/dispatch-fail-streak 正常应随每轮（600s）被 touch/重写；
   mtime 超过 FRESH_SECS 未更新 = 调度器未运行，FAIL。

全绿前提（文件不存在时的语义）：
- 首次部署（无 streak 文件）：只验 LaunchAgent 断档检测的前提——
  streak 文件不存在视为「调度器从未跑过或已清理」，告警但不 FAIL
  （rc=0，stdout 说明）；这样新克隆/禁用调度器的开发机不误报。

用法: python3 dispatch_liveness.py [--fresh-secs 93600]
  93600s = 26h：日回归节奏下，一轮正常 touch（600s）远远新鲜于阈值；
  周末最长合法静默（周日 03:00 回归 + 周一窗口）也覆盖。
退出码: 0=活 1=死（stalled 标记在或 streak 超龄）2=参数错误
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # .factory/regression/../..
METRICS = REPO / ".factory" / "metrics"
LOCKS = REPO / ".factory" / "locks"


def main() -> int:
    ap = argparse.ArgumentParser(description="dispatch 调度器活性检查")
    ap.add_argument("--fresh-secs", type=int, default=93600,
                    help="streak 文件新鲜度阈值秒（默认 93600=26h）")
    args = ap.parse_args()

    problems: list[str] = []

    stalled = METRICS / "dispatch-stalled"
    if stalled.exists():
        try:
            detail = stalled.read_text(encoding="utf-8").strip().splitlines()[0]
        except (OSError, IndexError):
            detail = "(标记文件不可读)"
        problems.append(f"dispatch 停摆标记在：{stalled} —— {detail}")

    streak = LOCKS / "dispatch-fail-streak"
    if streak.exists():
        age = time.time() - streak.stat().st_mtime
        if age > args.fresh_secs:
            problems.append(
                f"调度器疑似断档：streak 文件 {age/3600:.1f}h 未更新"
                f"（阈值 {args.fresh_secs/3600:.0f}h）——LaunchAgent 未运行？"
                "查 launchctl list | grep factory 与 locks/dispatch.log 尾部")
        else:
            print(f"ok: streak mtime {age/60:.0f}min 前（新鲜）")
    else:
        # 不 FAIL 的理由：调度器未启用/首跑前 streak 尚不存在是合法状态。
        print("note: streak 文件不存在（调度器未启用或从未失败）——跳过断档检测")

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print("ok: 无停摆标记，调度活性新鲜")
    return 0


if __name__ == "__main__":
    sys.exit(main())
