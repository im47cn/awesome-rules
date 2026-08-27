#!/usr/bin/env python3
"""check_git_sealing —— 测试 git 密封机械化门（ADR-010）。

steering/testing-standards.md §测试密封性是规范事实源；本门把其中靠人
记住的三件事机械化（负控制 NC14，tools/test_gauntlet_checks.sh）：
  R1 conftest 密封：tests/ 下直接 spawn git 的 test_*.py 所在套件，
     conftest.py 必须含 import 期 GIT_* 剥离块（标记
     GIT_ALTERNATE_OBJECT_DIRECTORIES）。hook（lefthook pre-push）注入的
     GIT_DIR 劫持 cwd/-C 仓库发现——两次事故：2026-08-22 真仓 389 文件
     删除；2026-08-27 PR #71 夹具提交落真仓 HEAD、plugin_lock 连锁误拦。
  R2 shell 测试密封：tracked test*.sh 与 tests/ 下 *.sh 调 git 的，必须
     顶层 unset GIT_DIR 等（unset 后子进程继承，覆盖 bash -c 子链）。
  R3 登记表完备：scripts/tests/test_hermetic_git.py 的 GIT_FIXTURE_CASES
     须覆盖全部 R1 检出套件——PR #71 漏 .factory/tests 证明手工登记必然
     漂移，登记义务由门禁强制。

扫描面 = git ls-files（tracked 面，steering「自建关卡脚本反作弊」要求；
非 git 环境 fail-closed 拒判）。
退出码：0 干净 / 1 命中 / 2 门自身错误（fail-closed）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

# conftest 密封块标记：steering 枚举七变量集的稳定锚点成员
SEAL_MARK = "GIT_ALTERNATE_OBJECT_DIRECTORIES"
# shell 密封标记：行首顶层 unset（MULTILINE 锚定）——printf/heredoc 内嵌
# 的 "unset GIT_DIR" 字符串不在行首，不构成密封（NC14 夹具实测曾以
# 字符串字面量假满足子串检测）。
SHELL_SEAL_MARK = re.compile(r"^unset\s+[A-Za-z_ =]*\bGIT_DIR\b", re.M)
# 直接 spawn git 的 argv 列表形态（subprocess.run/Popen(["git", ...)）
PY_GIT_SPAWN = re.compile(r"""[\[(]\s*["']git["']\s*,""")
# shell 真实 git 调用（注释行剔除后按子命令闭集匹配，避免散文/注释误报）
SH_GIT_CALL = re.compile(
    r"\bgit\s+(?:init|clone|add|commit|-C|rev-parse|ls-files|ls-tree|"
    r"hash-object|update-index|worktree|status|diff|log|show|push|pull|"
    r"for-each-ref|rev-list|branch|config)\b")
HERMETIC = Path("scripts/tests/test_hermetic_git.py")


def _fail_closed(cond, msg: str) -> None:
    if not cond:
        print(f"check_git_sealing: {msg}", file=sys.stderr)
        sys.exit(2)


def _tracked(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files"],
                       capture_output=True, text=True)
    _fail_closed(r.returncode == 0,
                 f"git ls-files 失败（{root} 非 git 仓？fail-closed）: {r.stderr.strip()}")
    files = [ln for ln in r.stdout.splitlines() if ln.strip()]
    _fail_closed(bool(files), "tracked 面为空（扫描面异常）")
    return files


def _read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8")
    except Exception as exc:
        _fail_closed(False, f"{rel} 不可读: {exc}")
        raise  # unreachable（_fail_closed 已 sys.exit）


def scan(root: Path) -> int:
    files = _tracked(root)
    hermetic = root / HERMETIC
    _fail_closed(hermetic.is_file(), f"缺 {HERMETIC}（负控制登记表漂移）")
    hermetic_text = _read(root, str(HERMETIC))

    hits = 0
    suites: set[str] = set()

    # R1：tests/ 下 test_*.py 直接 spawn git → 同目录 conftest 密封
    for f in files:
        p = PurePosixPath(f)
        if not (p.name.startswith("test_") and p.suffix == ".py"
                and "tests" in p.parts[:-1]):
            continue
        if not PY_GIT_SPAWN.search(_read(root, f)):
            continue
        suites.add(str(p.parent))
        conftest = root / p.parent / "conftest.py"
        sealed = conftest.is_file() and SEAL_MARK in _read(root, str(conftest))
        if not sealed:
            print(f"R1 conftest 未密封: {f}"
                  f"（同目录 conftest.py 缺 import 期 GIT_* 剥离块，"
                  "见 steering/testing-standards.md §测试密封性）")
            hits += 1

    # R2：shell 测试脚本调 git → 顶层 unset（unset 后子进程继承）
    for f in files:
        p = PurePosixPath(f)
        is_test_sh = p.name.startswith("test") and p.suffix == ".sh"
        under_tests = p.suffix == ".sh" and "tests" in p.parts[:-1]
        if not (is_test_sh or under_tests):
            continue
        text = _read(root, f)
        code = "\n".join(ln for ln in text.splitlines()
                         if not ln.lstrip().startswith("#"))
        if SH_GIT_CALL.search(code) and not SHELL_SEAL_MARK.search(text):
            print(f"R2 shell 未密封: {f}（调 git 但缺顶层 unset GIT_DIR 块）")
            hits += 1
    # R3：登记表覆盖全部 R1 检出套件。登记项为套件目录本身或其父目录
    #     （pytest 套件两种形态：skills/*/scripts（tests 为子目录）与
    #     .factory/tests（pytest 直接跑在 tests 目录））。登记表所在套件
    #     豁免：它测的正是密封机制本身，自登记 = 参数化自跑（子 pytest
    #     spawn 孙 pytest 无限嵌套，实测 300s 超时）；其 conftest 密封由
    #     R1 直接保证，无需负控制副本。
    exempt = str(HERMETIC.parent)
    for s in sorted(suites):
        if s == exempt:
            continue
        parent = str(PurePosixPath(s).parent)
        if f'"{s}"' not in hermetic_text and f'"{parent}"' not in hermetic_text:
            print(f"R3 负控制登记缺: {s}（{HERMETIC} 的 GIT_FIXTURE_CASES "
                  "须覆盖——手工登记无强制力，PR #71 已漏过一次）")
            hits += 1

    if hits:
        print(f"git-sealing: {hits} 命中（R1 conftest / R2 shell / R3 登记表）")
        return 1
    print(f"git-sealing: R1/R2/R3 干净"
          f"（{len(suites)} 个 git 夹具套件全登记，conftest 与 shell 全密封）")
    return 0


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    return scan(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
