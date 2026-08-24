#!/usr/bin/env python3
"""check_plugin_versions — 插件清单版本一致性门禁

package.json 是插件版本唯一真相源（834a235f「对齐 package.json 单源」），
但分发链是版本号门控的快照（PR #40 实证：未 bump 则消费者 update 拒刷），
而各平台清单无同步脚本——release 时人肉对齐六处必然漂移。本门把漂移
从「消费者拿到旧版才发现」提前到提交时拦截：

  1. 锚版本 = package.json 的 version
  2. 插件版本清单（allowlist）：version 字段必须与锚一致
  3. 漂移防护：tracked 面上任何 plugin.json / marketplace.json 不在
     allowlist ∨ 排除集内 = 硬失败（新平台接入须显式登记，同 gauntlet
     require_dir 语义——清单漂移不是静默跳过）

排除集（basename 相同但语义不同，须登记理由）：
  .kimi-plugin/marketplace.json   version 是市场 schema 格式号（"2"），非插件版本
  .agents/plugins/marketplace.json 本地路径注册清单，无 version 字段
  .claude-plugin/marketplace.json 注册清单，无 version 字段
  .grok-plugin/marketplace.json   注册清单，无 version 字段

用法:
  python3 tools/check_plugin_versions.py            # 仓库根自动定位
  python3 tools/check_plugin_versions.py <repo_root>

退出码: 0=通过
        1=版本漂移/清单漂移/allowlist 未跟踪（发布面漂移）
        2=结构性错误（非 git 仓/非仓库顶层/缺或坏 package.json）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# 插件版本清单：取值路径相对清单根，version 必须等于 package.json 单源版本
# （.cursor-plugin/marketplace.json 的 version 嵌套于 metadata——平台格式差异）
PLUGIN_MANIFESTS = (
    (".claude-plugin/plugin.json", ("version",)),
    (".codex-plugin/plugin.json", ("version",)),
    (".cursor-plugin/plugin.json", ("version",)),
    (".cursor-plugin/marketplace.json", ("metadata", "version")),
    (".kimi-plugin/plugin.json", ("version",)),
    (".grok-plugin/plugin.json", ("version",)),
)

# 排除集：basename 撞扫描模式但语义不同（理由随行登记）
EXCLUDED_MANIFESTS = {
    ".kimi-plugin/marketplace.json",     # version 是市场 schema 格式号（"2"），非插件版本
    ".agents/plugins/marketplace.json",  # 本地路径注册清单，无 version 字段
    ".claude-plugin/marketplace.json",   # 注册清单，无 version 字段
    ".grok-plugin/marketplace.json",     # 注册清单，无 version 字段
}

_MANIFEST_BASENAMES = {"plugin.json", "marketplace.json"}


def _tracked_files(root: Path) -> list[str]:
    # 扫描面 = git tracked 面：gitignore 是产物排除唯一真相源（md_link_check
    # 同原则）。非 git 目录 fail-closed 拒判，不做全盘猜测。
    # 顶层验证：git 会向父目录找仓——传入父仓的子目录时 ls-files 返回相对
    # 父仓根的路径，与相对 root 的 allowlist 比较即错位（Sourcery #41-3）。
    # 两侧都 resolve()：符号链接路径下 rev-parse 返回物理路径，逻辑路径
    # 比对必不等（must_not_match.sh 同类缺陷的教训）。
    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if Path(toplevel).resolve() != root:
            print(
                f"check_plugin_versions: {root} 不是 git 仓库顶层"
                f"（实际顶层 {toplevel}）——路径基线错位，拒判",
                file=sys.stderr,
            )
            raise SystemExit(2)
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"check_plugin_versions: git rev-parse/ls-files 失败（非 git 仓?）: {root}", file=sys.stderr)
        raise SystemExit(2) from exc
    return out.stdout.splitlines()


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        print(f"check_plugin_versions: 缺 package.json（单源版本无处取）: {pkg_path}", file=sys.stderr)
        return 2
    # 读取/解析/结构三层全捕获（Sourcery #41-1/#41-2）：非 UTF-8、不可读、
    # 根节点非对象都归 rc=2，绝不以 traceback 逃生——门禁的失败必须可判读
    try:
        package = json.loads(pkg_path.read_text(encoding="utf-8"))
        if not isinstance(package, dict):
            raise TypeError("根节点必须是 JSON 对象")
        anchor = package["version"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"check_plugin_versions: package.json 读取/解析失败: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []

    # ── 1. allowlist 逐一对锚（发布面 = tracked：工作树里未被 git 跟踪的
    #     清单不会进入分发，读了也不算数——未跟踪本身即发布面漂移，
    #     报错而非跳过，防 gitignored 同名文件顶替真实发布文件）──────
    tracked = set(_tracked_files(root))
    for rel, vpath in PLUGIN_MANIFESTS:
        if rel not in tracked:
            failures.append(f"{rel}: 未被 git 跟踪（发布面漂移）")
            continue
        path = root / rel
        if not path.is_file():
            failures.append(f"{rel}: 清单文件缺失（allowlist 漂移）")
            continue
        try:
            node = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            failures.append(f"{rel}: 读取/解析失败: {exc}")
            continue
        for key in vpath:
            node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            failures.append(f"{rel}: 无 version（路径 {'.'.join(vpath)}）")
        elif node != anchor:
            failures.append(f"{rel}: 期望 {anchor} 实际 {node}")

    # ── 2. tracked 面漂移防护：未登记的 manifest 硬失败 ────────────────
    known = {rel for rel, _ in PLUGIN_MANIFESTS} | set(EXCLUDED_MANIFESTS)
    for rel in tracked:
        parts = Path(rel).parts
        if parts and parts[-1] in _MANIFEST_BASENAMES and rel not in known:
            failures.append(
                f"{rel}: 未登记的插件清单（新平台接入须登记到 "
                f"PLUGIN_MANIFESTS 或 EXCLUDED_MANIFESTS 并注明理由）"
            )
    if failures:
        print(f"check_plugin_versions: {len(failures)} 处版本/清单漂移（锚 = package.json {anchor}）")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"check_plugin_versions: {len(PLUGIN_MANIFESTS)} 处插件清单版本一致（{anchor}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
