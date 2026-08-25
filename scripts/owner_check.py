#!/usr/bin/env python3
"""owner_check.py — 并发批次集成所有权比对门。

场景：herdr/多 agent 并发批次集成时，派发简报的「只许动这些文件」是软约束
（2026-08-24 实测：消融子代理违反简报直接裁剪 manual-rules；dispatch 下沉重构
零派发出现在工作区——两者都靠集成 owner 人眼 git diff 兜底）。本脚本把该兜底
机械化：**git 事实改动集 vs 派发清单白名单，任何未声明文件即 fail**。

负控制语义（steering/testing-standards）：门必须先证明会红（越权文件点名 +
exit 1），再证放行边界（全声明 exit 0）。真实批次 retrospective 见 README 例。

用法:
  python3 scripts/owner_check.py --manifest manifest.json            # 工作区模式
  python3 scripts/owner_check.py --manifest m.json --base HEAD~3     # 提交后验收
  python3 scripts/owner_check.py --manifest m.json --root /path/repo

清单格式（JSON）:
  {
    "batch": "herdr-batch-20260824",           # 可选，仅展示
    "owners": [
      {"name": "reg",   "allow": [".factory/regression/*"]},
      {"name": "integrator", "allow": [".factory/README.md"]}
    ]
  }

匹配语义:
  - fnmatch glob，`*` 跨目录匹配（`.factory/regression/*` 覆盖子目录全部文件）
  - rename/copy 同时校验新旧两侧路径（移走旧文件也是动它）
  - 工作区模式含 untracked（?? 也是改动）；--base 模式为 git diff --name-only
  - 清单中 repo 外路径（如 ~/Library/...）git 不可见 → 计入 unused 提示，
    须另行验证（plutil -lint 等），本门不覆盖

exit: 0 = 全部改动在白名单；1 = 存在越权文件；2 = 配置/环境错误
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import List, NoReturn, Optional, Tuple


def die(msg: str) -> NoReturn:
    print(f"[owner-check] 配置错误: {msg}", file=sys.stderr)
    sys.exit(2)


def load_manifest(path: Path) -> List[Tuple[str, List[str]]]:
    """载入并校验清单 → [(owner_name, [glob...])]。结构缺陷 exit 2。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        die(f"清单不可读: {path} ({e})")
    except json.JSONDecodeError as e:
        die(f"清单不是合法 JSON: {e}")
    owners = raw.get("owners")
    if not isinstance(owners, list) or not owners:
        die("清单缺 owners 非空数组")
    out: List[Tuple[str, List[str]]] = []
    for i, o in enumerate(owners):
        if not isinstance(o, dict) or not o.get("name") or not isinstance(o.get("allow"), list):
            die(f"owners[{i}] 须为 {{name, allow:[glob...]}}")
        if not all(isinstance(g, str) and g for g in o["allow"]):
            die(f"owners[{i}].allow 含空/非字符串 glob")
        out.append((str(o["name"]), [str(g) for g in o["allow"]]))
    return out


def _git(root: Path, args: List[str]) -> bytes:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if r.returncode != 0:
        die(f"git {' '.join(args)} 失败: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def changed_paths(root: Path, base: Optional[str], exclude: Optional[Path] = None) -> List[Tuple[str, str, bool]]:
    """git 事实改动 → [(status_xy, path, is_orig)]。rename/copy 展开新旧两侧，
    匹配一律用 raw 路径（is_orig 仅用于展示加注）。清单文件自豁免（门的 spec
    非产品改动）。"""
    if base:
        # --no-renames（PR #53 审查⑥）：关 rename/copy 检测，新旧两侧各自
        # 成行进入比对——R 状态的 --name-only 只报新路径，只声明了旧路径的
        # 重命名会绕门；diff.renames 用户配置也一并压平。
        out = _git(root, ["diff", "--name-only", "-z", "--no-renames", base])
        paths = [p for p in out.decode("utf-8", "replace").split("\0") if p]
        if exclude is not None:
            ex = _rel_or_abs(exclude, root)
            paths = [p for p in paths if p != ex]
        return [("D*", p, False) for p in paths]
    out = _git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    toks = out.decode("utf-8", "replace").split("\0")
    triples: List[Tuple[str, str, bool]] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if not t:
            i += 1
            continue
        xy, path = t[:2], t[3:]
        triples.append((xy, path, False))
        if "R" in xy or "C" in xy:  # 下一个 token 是原路径
            i += 1
            if i < len(toks) and toks[i]:
                triples.append((xy, toks[i], True))
        i += 1
    if exclude is not None:
        ex = _rel_or_abs(exclude, root)
        triples = [t for t in triples if t[1] != ex]
    return triples


def _rel_or_abs(p: Path, root: Path) -> str:
    """git 报相对 root 的路径；清单在仓内则相对化，仓外保持绝对（永不匹配=保留改动）。"""
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def covering_owners(path: str, owners: List[Tuple[str, List[str]]]) -> List[str]:
    return [name for name, globs in owners if any(fnmatch.fnmatch(path, g) for g in globs)]


def main() -> None:
    ap = argparse.ArgumentParser(description="并发批次集成所有权比对门")
    ap.add_argument("--manifest", required=True, help="派发清单 JSON 路径")
    ap.add_argument("--base", help="提交后验收：比对 REF..HEAD（默认工作区模式）")
    ap.add_argument("--root", default=".", help="git 仓库根（默认 cwd）")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    mf_path = Path(args.manifest).resolve()
    owners = load_manifest(mf_path)
    changes = changed_paths(root, args.base, exclude=mf_path)

    if not changes:
        print("[owner-check] 无改动，门空转通过（exit 0）")
        sys.exit(0)

    overreach: List[Tuple[str, str, List[str]]] = []  # (xy, path, covers)
    used: set = set()
    overlap: List[str] = []

    def disp(path: str, is_orig: bool) -> str:
        return f"{path} (旧路径)" if is_orig else path

    for xy, path, is_orig in changes:
        covers = covering_owners(path, owners)
        for name, globs in owners:
            for g in globs:
                if fnmatch.fnmatch(path, g):
                    used.add((name, g))
        if not covers:
            overreach.append((xy, disp(path, is_orig), covers))
        elif len(covers) > 1:
            overlap.append(f"  [{xy}] {disp(path, is_orig)} ← {' & '.join(covers)}")

    print(f"[owner-check] 改动 {len(changes)} 条 / owners {len(owners)} 个"
          f"（模式: {'--base ' + args.base if args.base else '工作区'}）")
    if overreach:
        print(f"\n越权文件 {len(overreach)} 条（不在任何 owner 白名单）：")
        for xy, path, _ in overreach:
            print(f"  [{xy}] {path}")
        print("\n处置二选一：revert 越权改动，或补 owner 声明后重跑本门（显式决策）。")
    if overlap:
        print(f"\n警告: 多 owner 重叠声明 {len(overlap)} 条（写冲突候选，集成时人工裁决）：")
        print("\n".join(overlap))
    unused = [(n, g) for n, globs in owners for g in globs if (n, g) not in used]
    if unused:
        print(f"\n提示: {len(unused)} 条声明未匹配任何改动（清单腐烂信号；repo 外路径如 plist 本就不可见）：")
        for n, g in unused:
            print(f"  [{n}] {g}")

    if overreach:
        sys.exit(1)
    print("\n[owner-check] 全部改动在白名单内（exit 0）")


if __name__ == "__main__":
    main()
