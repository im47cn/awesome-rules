#!/usr/bin/env python3
"""plugin_lock — 安装入口清单的 blob 锁定（zero-regression 模式，借鉴 archify）

archify 的 zero-regression 测试锁"发布产物字节级可复现"（FIXED_POINT commit +
git blob SHA）。awesome-rules 无 npm 产物，发布物 = 各 AI 工具的插件安装入口
清单——用户经"一行命令安装"直接消费这些文件，意外漂移会破坏安装。

锁定机制：
- 每个入口文件以 `git hash-object`（内容 blob SHA）锁定于 scripts/plugin-lock.json
- check：内容漂移 / 文件缺失 / 目录内出现未锁定的新清单 → 非零退出（exit 1）
- --update：有意变更后刷新锁定值（需随变更一起提交）
- 锁清单可选纳入 evidence 指纹节（skill → content_hash）：check 时校验技能
  内容漂移；旧锁文件无该节则跳过（向后兼容）。算法与 release_guard
  评测证据门禁同一实现源（sibling import，不复制实现）

用法:
  python3 scripts/plugin_lock.py            # check（默认）
  python3 scripts/plugin_lock.py --update   # 有意变更清单后刷新锁定
"""

from __future__ import annotations  # 兼容 Python 3.9：延迟求值 PEP 604 联合类型注解

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# content_hash 单一真相源在 release_guard（同目录 sibling import），禁止复制实现
sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_guard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_FILE = Path(__file__).resolve().parent / "plugin-lock.json"

# 环境密封（同各套件 conftest）：本脚本可能运行在 hook 注入的 GIT_DIR 下
# （pre-push 链），显式环境变量会覆盖 `git -C REPO_ROOT` 的仓库发现，
# hash-object 读错仓或报错 → 误触发 sha256 降级 → 锁定比对假红。
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
    os.environ.pop(_k, None)

# 安装入口全集：各工具插件目录下的清单 + 共享 hooks 配置
# （.agents 为 Codex 市场安装入口，见 docs/ai-coding-tools-setup.md）
LOCKED_DIRS = [".claude-plugin", ".codex-plugin", ".cursor-plugin",
               ".kimi-plugin", ".grok-plugin", ".agents", ".opencode", ".pi",
               "hooks"]
LOCKED_FILES = [  # 显式入口（目录扫描之外的兜底）
    "hooks/hooks.json",
    ".pi/extensions/awesome-rules.ts",  # .pi 扩展入口（非 json，目录 glob 不覆盖）
]


def _git_blob_sha(path: Path) -> str | None:
    """文件的 git blob SHA（与 git index 中同内容文件的哈希一致）。"""
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "hash-object", str(path)],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def _sha256(path: Path) -> str | None:
    """无 git 时的降级哈希（blob 语义丢失但锁定能力保留）。"""
    try:
        return "sha256:" + hashlib.sha256(
            path.read_bytes()).hexdigest()
    except OSError:
        return None


def _file_hash(path: Path) -> str | None:
    return _git_blob_sha(path) or _sha256(path)


def discover() -> list[str]:
    """发现全部应锁定的安装入口（tracked 面 + 显式清单）。

    tracked 面（2026-08-23 结构性修复）：目录 rglob 与 gitignore 必然漂移
    （同 md_link_check 实证根因）——锁定对象是"进入版本的安装入口"，
    未 add 的本地试验文件不构成回归面。非 git 环境（hook 降级场景）
    退回 rglob（_git_blob_sha 已有对应降级）。
    """
    found = set(LOCKED_FILES)
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--",
         *[f"{d}/*.json" for d in LOCKED_DIRS]],
        capture_output=True)
    if proc.returncode == 0:
        found.update(f for f in proc.stdout.decode("utf-8").split("\0") if f)
    else:
        for d in LOCKED_DIRS:
            dp = REPO_ROOT / d
            if dp.is_dir():
                found.update(str(p.relative_to(REPO_ROOT))
                             for p in dp.rglob("*.json"))
    return sorted(found)


def load_lock() -> dict:
    if LOCK_FILE.exists():
        try:
            return json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_lock(entries: dict, evidence: dict | None = None) -> None:
    """evidence 为可选节：空/缺省时不写入（保持旧锁文件形状）。"""
    data = {"description": "安装入口清单 blob 锁定（zero-regression 模式）；"
                           "有意变更后运行 scripts/plugin_lock.py --update 刷新",
            "files": dict(sorted(entries.items()))}
    if evidence:
        data["evidence"] = dict(sorted(evidence.items()))
    LOCK_FILE.write_text(json.dumps(
        data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update() -> int:
    entries = {}
    for rel in discover():
        h = _file_hash(REPO_ROOT / rel)
        if h:
            entries[rel] = h
    ev = {s: release_guard.compute_content_hash(REPO_ROOT, s)
          for s in release_guard.discover_evidence_skills(REPO_ROOT)}
    save_lock(entries, ev)
    print(f"✅ 已锁定 {len(entries)} 个安装入口 → {LOCK_FILE}")
    if ev:
        print(f"   另含 {len(ev)} 条 evidence 指纹（技能内容 hash，"
              "与 release_guard 评测证据门禁同一算法源）")
    print("   锁定文件需随清单变更一起提交")
    return 0


def check_evidence_lock(lock_data: dict) -> list[str]:
    """evidence 指纹节校验（可选节：旧锁文件无此节 → 空清单，向后兼容）。

    指纹只锁"技能内容 ↔ 重锁时点"的漂移；证据文件本身的绑定校验
    （存在性 / schema / hash 匹配）归 release_guard.verify_skill_evidence，
    两者互补、不重复实现。
    """
    if "evidence" not in lock_data:
        # 旧锁文件无 evidence 节：完全跳过（向后兼容）
        return []
    locked_ev = lock_data["evidence"]
    if not isinstance(locked_ev, dict):
        # 手改锁文件的非 dict 节（含 []/""/0/false/null 等 falsy 值）：
        # 干净报错而非 TypeError 崩溃，也不得混同缺节静默跳过
        return ["锁文件 evidence 节格式非法（期望 skill→hash 映射，"
                f"实际 {type(locked_ev).__name__}）——运行 --update 重新生成"]
    if not locked_ev:
        return []
    errors = []
    current = set(release_guard.discover_evidence_skills(REPO_ROOT))
    for skill in sorted(locked_ev):
        h = str(locked_ev[skill])
        if skill not in current:
            errors.append(f"evidence 指纹悬空: {skill}"
                          "（skill 已删除/改名——运行 --update 刷新）")
            continue
        try:
            actual = release_guard.compute_content_hash(REPO_ROOT, skill)
        except (UnicodeDecodeError, OSError) as e:
            errors.append(f"{skill}: 内容不可读或非 UTF-8，无法计算指纹"
                          f"（{type(e).__name__}）")
            continue
        if actual != h:
            errors.append(f"skill 内容漂移（evidence 指纹）: {skill}\n    "
                          f"锁定 {h[:19]}… 实际 {actual[:19]}…"
                          "（有意变更请 --update 并重跑 replay-eval）")
    for skill in sorted(current - set(locked_ev)):
        errors.append(f"未纳入 evidence 锁定: {skill}"
                      "（新增含 scripts/ 的 skill——运行 --update 或确认其合法性）")
    return errors


def check() -> int:
    lock_data = load_lock()
    locked = lock_data.get("files")
    if not locked:
        print("❌ 锁定文件缺失或为空，先运行: python3 scripts/plugin_lock.py --update",
              file=sys.stderr)
        return 1

    current_files = discover()
    errors = []

    # 1. 锁定的文件缺失
    for rel in sorted(locked):
        if rel not in current_files:
            errors.append(f"缺失: {rel}（已锁定但不存在——被删除或改名）")

    # 2. 新清单未锁定
    for rel in current_files:
        if rel not in locked:
            errors.append(f"未锁定: {rel}（新增入口——运行 --update 或确认其合法性）")

    # 3. 内容漂移
    for rel in current_files:
        if rel not in locked:
            continue
        actual = _file_hash(REPO_ROOT / rel)
        if actual != locked[rel]:
            errors.append(f"漂移: {rel}\n    锁定 {locked[rel][:16]}… "
                          f"实际 {str(actual)[:16]}…"
                          f"（有意变更请 --update，意外漂移请排查）")

    # 4. evidence 指纹节（可选）：技能内容漂移检测；旧锁文件无此节 → 跳过
    #    （向后兼容），算法与 release_guard 评测证据门禁同一实现源。
    errors.extend(check_evidence_lock(lock_data))

    # 5. 版本一致性：委托 tools/check_plugin_versions（单一真相源）。
    #    本脚本原有一份独立的版本比对逻辑，与 gauntlet plugin-versions
    #    层是同一不变量的两处实现——清单增删要改两处、必然漂移。委托后
    #    语义还更强（tracked 面未登记清单硬失败 / 未跟踪发布面漂移 /
    #    非 git 仓 fail-closed，见该检查器 docstring）。
    #    子进程退出码即结论：0=一致；1/2 归入本脚本的 errors 报告。
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "check_plugin_versions.py"),
         str(REPO_ROOT)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        errors.append("版本一致性（check_plugin_versions）:\n    "
                      + "\n    ".join(
                          (proc.stdout + proc.stderr).strip().splitlines()))

    if errors:
        print(f"❌ 安装入口锁定校验失败（{len(errors)} 处）:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"✅ {len(locked)} 个安装入口与锁定一致（zero-regression）")
    return 0



def main():
    if "--update" in sys.argv:
        sys.exit(update())
    sys.exit(check())


if __name__ == "__main__":
    main()
