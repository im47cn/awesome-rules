"""find_py 候选解释器的语法/注解兼容探针（tools/gauntlet.sh 调用）。

单测 compile() 只证解析不动模块级注解求值——3.9 遇无 future import 的
PEP 604 注解（`dict | None`），parse 过而 pytest 收集即炸（2026-09-09
实证；Sourcery 2026-09-13 评审指出此盲区）。故每文件两段式：

1. compile 查语法；
2. 隔离子进程 runpy 执行查模块级求值面（run_name 非 __main__，
   不触发 CLI 入口；子进程隔离防单文件崩溃/超时株连整体）。

任一文件失败 = 候选不可用，exit 1（fail-closed，gauntlet 顺延下一候选）。

执行面与门禁实跑面同源：pytest 收集/导入这些文件时同样执行其模块级
代码，探针不引入新的副作用面。

用法: py_syntax_probe.py <dir>...   # 目录按 rglob 递归收集 *.py，
                                    # .factory 顶层与 skills/_shared
                                    # 特例只收一层（.factory 整树含
                                    # gitignored 工厂链 worktree）
"""

import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# 子进程解释器超时：防模块级死循环（fixture/守护进程类代码）株连探针
EXEC_TIMEOUT_S = 30
WORKERS = 8

# 单层收集目录（不递归）及原因：见模块 docstring
FLAT_DIRS = {".factory", "skills/_shared"}


def collect_files(dirs):
    files = set()
    for d in dirs:
        p = pathlib.Path(d)
        pattern = "*.py" if d in FLAT_DIRS else "**/*.py"
        files.update(p.glob(pattern))
    return sorted(f for f in files if "__pycache__" not in f.parts)


def probe_file(p):
    """返回 None（通过）或首行错误摘要。"""
    try:
        compile(p.read_bytes(), str(p), "exec")
    except SyntaxError as e:
        return f"{p}:{e.lineno} {e.msg}"
    # 子进程执行器：复刻 pytest 导入环境——祖先目录至仓库根逐级注入
    # sys.path（否则全量 ModuleNotFoundError 误报）；带 __init__.py 的包内
    # 模块（相对导入）按包名 run_module 执行（run_path 不支持包上下文）
    runner = (
        "import pathlib, runpy, sys\n"
        "f = pathlib.Path(sys.argv[1]).resolve()\n"
        "root = pathlib.Path(sys.argv[2]).resolve()\n"
        "for anc in [f.parent, *f.parent.parents]:\n"
        "    sys.path.insert(0, str(anc))\n"
        "    if anc == root:\n"
        "        break\n"
        "parts = [] if f.stem == '__init__' else [f.stem]\n"
        "d = f.parent\n"
        "while (d / '__init__.py').exists():\n"
        "    parts.append(d.name)\n"
        "    d = d.parent\n"
        "if parts:\n"
        "    name = '.'.join(reversed(parts))\n"
        "    if f.stem == '__init__':\n"
        "        import importlib; importlib.import_module(name)\n"
        "    else:\n"
        "        runpy.run_module(name,"
        " run_name='gauntlet_probe', alter_sys=True)\n"
        "else:\n"
        "    runpy.run_path(str(f), run_name='gauntlet_probe')\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", runner, str(p), str(pathlib.Path.cwd())],
            capture_output=True, timeout=EXEC_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{p} exec timeout (> {EXEC_TIMEOUT_S}s)"
    if r.returncode != 0:
        err = r.stderr.decode(errors="replace").strip().splitlines()
        detail = err[-1][:120] if err else f"exit {r.returncode}"
        return f"{p} {detail}"
    return None


def main():
    files = collect_files(sys.argv[1:])
    # 执行探针并行收集结果；逐文件失败信息保持文件序输出
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        bad = [res for res in pool.map(probe_file, files) if res]
    if bad:
        print("\n".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
