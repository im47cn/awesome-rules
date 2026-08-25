#!/usr/bin/env python3
"""dispatch-liveness — 调度器活性检查（回归第四层组件，2026-08-25）。

多仓形态（同日升级）：检查对象 = hub 注册表 ~/.config/factory/repos.conf
内全部仓库（# 注释与空行忽略），本仓若无注册表则退化为单仓自检——
hub 是多仓唯一调度入口，任一注册仓库的调度死法都是本层的 FAIL 信号。

两种死法都要抓（动机：slug 回归事件暴露的可见性盲区）：
1. 进程在跑但一直失败：cron-dispatch.sh 连击 ≥3 轮 exit 2 会写
   <repo>/.factory/metrics/dispatch-stalled —— 本检查发现它即 FAIL。
2. 进程根本没跑（LaunchAgent 断档，历史实测 13h）：streak 计数文件
   <repo>/.factory/locks/dispatch-fail-streak 正常应随每轮（600s）被
   touch/重写；mtime 超过 FRESH_SECS 未更新 = 该仓库调度未运行，FAIL。

不 FAIL 的合法状态（每仓独立判定）：
- stalled/streak 均不存在：调度器未启用或从未失败——note 不 FAIL
  （新克隆/禁用调度的开发机不误报）。
- 注册表中的仓库缺 .factory/（未接入工厂的仓库误注册）：note 不 FAIL，
  提示从 repos.conf 移除——registry 是用户侧文件，本检查只读不写。

用法: python3 dispatch_liveness.py [--fresh-secs 93600] [--repos PATH]
  --repos 默认 ~/.config/factory/repos.conf（hub 注册表，与
  ~/.config/factory/dispatch-all.sh 同源——单一注册表两处消费）。
  93600s = 26h：日回归节奏下，一轮正常 touch（600s）远远新鲜于阈值。
退出码: 0=全部活/合法缺省 1=任一仓库死 2=参数/环境错误
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # .factory/regression/../..
DEFAULT_REGISTRY = Path.home() / ".config" / "factory" / "repos.conf"


def registry_repos(registry: Path) -> list[Path]:
    """解析 hub 注册表 → 仓库路径清单（# 注释/空行忽略，形态对齐 dispatch-all.sh）。"""
    repos: list[Path] = []
    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        repos.append(Path(ln).expanduser())
    return repos


def check_repo(repo: Path, fresh_secs: int, problems: list[str]) -> str:
    """单仓库活性检查 → 状态行（ok/note）。FAIL 项追加到 problems。"""
    tag = repo.name
    factory = repo / ".factory"
    if not factory.is_dir():
        print(f"note: [{tag}] 无 .factory/（未接入工厂）——建议从 repos.conf 移除")
        return "note"

    stalled = factory / "metrics" / "dispatch-stalled"
    if stalled.exists():
        try:
            detail = stalled.read_text(encoding="utf-8").strip().splitlines()[0]
        except (OSError, IndexError):
            detail = "(标记文件不可读)"
        problems.append(f"[{tag}] dispatch 停摆标记在：{stalled} —— {detail}")

    streak = factory / "locks" / "dispatch-fail-streak"
    if streak.exists():
        age = time.time() - streak.stat().st_mtime
        if age > fresh_secs:
            problems.append(
                f"[{tag}] 调度器疑似断档：streak 文件 {age/3600:.1f}h 未更新"
                f"（阈值 {fresh_secs/3600:.0f}h）——LaunchAgent 未运行？"
                "查 launchctl list | grep factory 与该仓 locks/dispatch.log 尾部")
            return "fail"
        print(f"ok: [{tag}] streak mtime {age/60:.0f}min 前（新鲜）")
        return "ok"
    # 不 FAIL 的理由：调度器未启用/首跑前 streak 尚不存在是合法状态。
    print(f"note: [{tag}] streak 文件不存在（调度器未启用或从未失败）——跳过断档检测")
    return "note"


def main() -> int:
    ap = argparse.ArgumentParser(description="dispatch 调度器活性检查（多仓：hub 注册表）")
    ap.add_argument("--fresh-secs", type=int, default=93600,
                    help="streak 文件新鲜度阈值秒（默认 93600=26h）")
    ap.add_argument("--repos", default=str(DEFAULT_REGISTRY),
                    help="hub 注册表路径（默认 ~/.config/factory/repos.conf）")
    args = ap.parse_args()

    registry = Path(args.repos).expanduser()
    repos = registry_repos(registry) if registry.is_file() else []
    if not repos:
        # 无注册表/注册表空：单仓自检（检查器随本仓回归线分发，下游仓
        # 无 hub 时仍可用——退化路径不静默：打印明示只查了谁）
        print(f"note: 注册表不存在或为空（{registry}）——退化为单仓自检")
        repos = [REPO]

    problems: list[str] = []
    for repo in repos:
        check_repo(repo, args.fresh_secs, problems)

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"ok: {len(repos)} 个仓库全部活性正常（或合法缺省）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
