#!/usr/bin/env python3
"""check_tempdir_usage.py — 测试直接枚举系统共享 tempdir 的静态门。

背景（PR #137 泄漏断言隔离，2026-09 收口）：mktemp 泄漏断言（after-before
差集）原对共享系统 tempdir glob 同模板文件，套件外进程瞬时写入同模板即
随机打破差集（pre-push 闸两次 flake，隔离重跑绿证实环境性）；该未隔离
形态已扩散至 8 个下游仓。修复范式 = conftest private_tmp 夹具
（.factory/tests/conftest.py）：把被测进程 env["TMPDIR"] 指到 pytest 私有
目录、断言 glob 对齐同一目录——外部写者不再可见，泄漏检测语义不变。

规则（扫描面 = 测试文件 test_*.py / conftest.py）：
  R1  测试代码调用 gettempdir() → 违规：tempfile 按进程缓存首次取值，
      测试进程拿到的是系统共享目录；TMPDIR 注入只达子进程，测试进程内
      gettempdir() 永远拿不到注入值。须改 private_tmp 夹具形态。
  R2  枚举调用直接以 /tmp 字面量为对象（glob.glob("/tmp/…")、裸
      glob("/tmp/…")、x.glob("/tmp/…")、os.listdir("/tmp")、
      Path("/tmp").iterdir()/glob() 链）→ 违规：硬编码系统共享目录，
      绕过 TMPDIR 注入。构造器传参（如 RiskScanner("/tmp")）不是枚举
      调用，不在命中面；shell 侧 "${TMPDIR:-/tmp}" 默认值形态尊重注入，
      亦不在本门扫描面（本门只扫 .py）。

用法: check_tempdir_usage.py <file-or-dir>...
      file 参数直接检查（仓外自测夹具路径亦然，不做名称过滤）；dir 参数
      按 git ls-files 枚举 tracked 测试面（gitignored 运行产物天然出局，
      67c2965b 原则）；输入目录非 git 仓库时 fail-closed 拒判。
rc:  0 = 通过（或扫描面内无测试文件）
     1 = 存在违规（检查确实执行且判定失败）
     2 = 检查器自身失败（路径不存在、非 git 仓库、读取错误）——绝不算通过
"""
import re
import subprocess
import sys
from pathlib import Path

RE_GETTEMPDIR = re.compile(r"gettempdir\s*\(")
RE_TMP_ENUM = re.compile(
    r"""(?:
        (?:\bglob\s*\.\s*glob|(?<![\w.])glob|\.\s*glob|os\s*\.\s*listdir)
        \s*\(\s*f?["']/tmp
      | Path\s*\(\s*f?["']/tmp[^)]*\)\s*\.\s*(?:glob|iterdir)
    )""",
    re.VERBOSE,
)


def _is_test_py(name: str) -> bool:
    return name == "conftest.py" or (name.startswith("test_") and name.endswith(".py"))


def check_text(text: str):
    """返回 [(lineno, message)]；纯注释行豁免（防规范转述文字误报）。"""
    out = []
    for i, ln in enumerate(text.split("\n"), 1):
        if ln.strip().startswith("#"):
            continue
        if RE_GETTEMPDIR.search(ln):
            out.append((i, "R1: gettempdir() 恒返回系统共享目录（tempfile 进程级缓存，"
                          "TMPDIR 注入只达子进程）——测试须用 private_tmp 夹具注入私有目录"))
        if RE_TMP_ENUM.search(ln):
            out.append((i, "R2: 枚举调用直接指向 /tmp 字面量（绕过 TMPDIR 注入）——"
                          "须对齐 private_tmp 注入目录"))
    return out


def tracked_test_files(d: Path):
    """dir → tracked 测试文件 Path 清单；非 git 仓库 fail-closed（rc2）。"""
    probe = subprocess.run(["git", "-C", str(d), "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        print(f"check_tempdir_usage: {d} 非 git 仓库，fail-closed 拒判", file=sys.stderr)
        raise SystemExit(2)
    # -z 防文件名含换行；pathspec '.' 限定 -C 目录子树
    ls = subprocess.run(["git", "-C", str(d), "ls-files", "-z", "--", "."],
                        capture_output=True, text=True)
    if ls.returncode != 0:
        print(f"check_tempdir_usage: git ls-files 失败: {ls.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return [d / rel for rel in ls.stdout.split("\0")
            if rel and _is_test_py(rel.rsplit("/", 1)[-1])]


def main(argv):
    args = argv[1:]
    if not args:
        print("用法: check_tempdir_usage.py <file-or-dir>...", file=sys.stderr)
        return 2
    targets: list = []
    for a in args:
        p = Path(a)
        if not p.exists():
            print(f"check_tempdir_usage: 路径不存在: {a}", file=sys.stderr)
            return 2
        if p.is_dir():
            targets.extend(tracked_test_files(p))
        else:
            targets.append(p)  # 显式 file 参数（含仓外夹具）：不做名称过滤
    fails = 0
    for p in sorted(set(targets)):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"check_tempdir_usage: 读取失败 {p}: {e}", file=sys.stderr)
            return 2
        for lineno, msg in check_text(text):
            print(f"{p}:{lineno}: {msg}")
            fails += 1
    if fails:
        print(f"check_tempdir_usage: {fails} 处测试直接枚举系统 tempdir"
              "（隔离范式: .factory/tests/conftest.py private_tmp）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
