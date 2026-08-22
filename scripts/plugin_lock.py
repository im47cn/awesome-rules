#!/usr/bin/env python3
"""plugin_lock — 安装入口清单的 blob 锁定（zero-regression 模式，借鉴 archify）

archify 的 zero-regression 测试锁"发布产物字节级可复现"（FIXED_POINT commit +
git blob SHA）。awesome-rules 无 npm 产物，发布物 = 各 AI 工具的插件安装入口
清单——用户经"一行命令安装"直接消费这些文件，意外漂移会破坏安装。

锁定机制：
- 每个入口文件以 `git hash-object`（内容 blob SHA）锁定于 scripts/plugin-lock.json
- check：内容漂移 / 文件缺失 / 目录内出现未锁定的新清单 → 非零退出（exit 1）
- --update：有意变更后刷新锁定值（需随变更一起提交）

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
    """发现全部应锁定的安装入口（目录扫描 + 显式清单）。"""
    found = set(LOCKED_FILES)
    for d in LOCKED_DIRS:
        dp = REPO_ROOT / d
        if not dp.is_dir():
            continue
        for p in sorted(dp.rglob("*.json")):
            found.add(str(p.relative_to(REPO_ROOT)))
    return sorted(found)


def load_lock() -> dict:
    if LOCK_FILE.exists():
        try:
            return json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_lock(entries: dict) -> None:
    LOCK_FILE.write_text(json.dumps(
        {"description": "安装入口清单 blob 锁定（zero-regression 模式）；"
                        "有意变更后运行 scripts/plugin_lock.py --update 刷新",
         "files": dict(sorted(entries.items()))},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update() -> int:
    entries = {}
    for rel in discover():
        h = _file_hash(REPO_ROOT / rel)
        if h:
            entries[rel] = h
    save_lock(entries)
    print(f"✅ 已锁定 {len(entries)} 个安装入口 → {LOCK_FILE}")
    print("   锁定文件需随清单变更一起提交")
    return 0


def check() -> int:
    locked = load_lock().get("files")
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

    # 4. 版本一致性：插件清单版本须与 package.json（release 单源）同步，
    #    防止发布 3 个 minor 后插件侧仍停留在旧版本的双轨漂移
    errors.extend(check_version_sync(current_files))

    if errors:
        print(f"❌ 安装入口锁定校验失败（{len(errors)} 处）:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"✅ {len(locked)} 个安装入口与锁定一致（zero-regression）")
    return 0


def check_version_sync(current_files: list) -> list:
    """插件清单版本与 package.json 不一致 → 错误。

    只比对语义化版本字段：plugin.json 的 version、marketplace.json 的
    metadata.version。marketplace.json 顶层 version 是清单 schema 版本
    （如 kimi 的 "2"），不参与比对。
    """
    pkg = REPO_ROOT / "package.json"
    try:
        expected = json.loads(pkg.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        return [f"package.json 不可读，无法校验版本同步"]
    if not expected:
        return []

    errors = []
    for rel in current_files:
        try:
            data = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # 内容漂移已由 blob 锁定报告
        actual = None
        if rel.endswith("plugin.json"):
            actual = data.get("version")
        elif rel.endswith("marketplace.json"):
            actual = (data.get("metadata") or {}).get("version")
        if actual and actual != expected:
            errors.append(f"版本不同步: {rel} 为 {actual}，package.json 为 "
                          f"{expected}（发布时同步递增）")
    return errors


def main():
    if "--update" in sys.argv:
        sys.exit(update())
    sys.exit(check())


if __name__ == "__main__":
    main()
