#!/usr/bin/env python3
"""release 防呆：拦截 commit-and-tag-version 的 0.x preMajor 语义与仓库惯例冲突。

根因（2026-08-26 v0.4.1 事故实证）：
  catv 13.x bumpVersion 对 currentVersion < 1.0.0 强制 presetOptions.preMajor=true
  （无 CLI 开关），preMajor 规则 level<2 → level++，即 0.x 阶段 feat 降为 patch、
  breaking 降为 minor。本仓惯例是 pre-1.0 仍按常规语义发布（v0.3.0/v0.4.0/v0.5.0
  均为 feat 集合的 minor 发布）。实测证据：区间 23 个 feat，catv reason 正确计数
  却返回 level=2 → 0.4.1。

行为：
  1. 按仓库惯例独立计算期望 bump（常规语义，无 preMajor 降级）
  2. catv --dry-run 取工具目标版本
  3. 一致 → 原生执行；不一致 → 打印原因并 --release-as <期望> 纠偏执行
  区间无可发布提交 → 拒绝发布退出（防误发空版本）。

用法：
  npm run release              # 防呆发布（默认）
  python3 scripts/release_guard.py --check   # 只报告决策，不执行
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_HEADER_RE = re.compile(r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s+\S")
_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def sh(*args: str, cwd: Path = REPO) -> str:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def latest_stable_tag() -> str | None:
    """HEAD 可达的最新 v* semver tag（与 catv skipUnstable 语义对齐）。"""
    tags = [t for t in sh("git", "tag", "-l", "v*").splitlines() if _SEMVER_RE.match(t)]
    reachable = [
        t for t in tags
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", t, "HEAD"],
            cwd=REPO, capture_output=True,
        ).returncode == 0
    ]
    if not reachable:
        return None
    return sorted(reachable, key=lambda t: tuple(int(x) for x in t[1:].split(".")))[-1]


def current_version() -> str:
    import json
    return json.loads((REPO / "package.json").read_text())["version"]


def expected_bump(commits: list[dict]) -> str | None:
    """仓库惯例（常规语义，0.x 不降级）：breaking→major, feat→minor, fix/perf→patch。

    commits 项: {"header": str, "body": str}
    """
    level = None  # 0=major 1=minor 2=patch
    for c in commits:
        m = _HEADER_RE.match(c["header"])
        if not m:
            continue
        breaking = bool(m.group("bang")) or "BREAKING CHANGE" in (c["body"] or "") \
            or "BREAKING-CHANGE" in (c["body"] or "")
        if breaking:
            level = 0
        elif level in (None, 2) and m.group("type") in ("feat", "feature"):
            level = 1
        elif level is None and m.group("type") in ("fix", "perf"):
            level = 2
    return None if level is None else ("major", "minor", "patch")[level]


def bump_version(base: str, bump: str) -> str:
    major, minor, patch = (int(x) for x in base.lstrip("v").split("."))
    return {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }[bump]


def parse_catv_target(dry_output: str) -> str | None:
    """从 catv dry-run 输出抓目标版本：`bumping version in package.json from A to B`。"""
    m = re.search(r"bumping version in package\.json from \S+ to (\S+)", dry_output)
    return m.group(1) if m else None


def interval_commits(base: str | None) -> list[dict]:
    rng = f"{base}..HEAD" if base else "HEAD"
    raw = sh("git", "log", rng, "--no-merges", "--format=%s%x01%b%x01")
    commits = []
    for entry in raw.split("\x01\n"):
        if not entry.strip():
            continue
        parts = entry.split("\x01", 1)
        commits.append({"header": parts[0], "body": parts[1] if len(parts) > 1 else ""})
    return commits


def decide(check_only: bool = False) -> int:
    base = latest_stable_tag()
    commits = interval_commits(base)
    bump = expected_bump(commits)
    cur = current_version()

    if bump is None:
        n = len(commits)
        print(f"⛔ 区间 {base or '起点'}..HEAD 含 {n} 个非 merge 提交，无 feat/fix/perf/breaking——无可发布内容，拒绝发布。")
        return 1

    expected = bump_version(base or f"v{cur}", bump)
    dry = subprocess.run(
        ["npx", "--no-install", "commit-and-tag-version", "--dry-run"],
        cwd=REPO, capture_output=True, text=True,
    )
    target = parse_catv_target(dry.stdout + dry.stderr)

    print(f"基线 tag: {base}  当前版本: {cur}")
    print(f"惯例期望: {expected}（{bump}）   catv 目标: {target}")

    if target == expected:
        print("✅ 一致，原生执行 release")
        cmd = ["npx", "--no-install", "commit-and-tag-version"]
    else:
        reason = (
            "catv 0.x preMajor 语义（feat→patch）与仓库惯例（feat→minor）冲突"
            if cur.startswith("0.") and bump == "minor"
            else "catv 判定与仓库惯例不一致"
        )
        print(f"⚠ 拦截：{reason}，按惯例纠偏 --release-as {expected}")
        cmd = ["npx", "--no-install", "commit-and-tag-version", "--release-as", expected]

    if check_only:
        print("（--check：不执行）")
        return 0
    subprocess.run(cmd, cwd=REPO, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(decide(check_only="--check" in sys.argv))
