#!/usr/bin/env python3
"""check_inline_python.py — shell 脚本内联 python 的确定性语法门。

背景（2026-08-22 事故）：feedback 适配节点把 fix-issue.sh 的
BRANCH="factory/issue-${ISSUE}" 定义行改丢，set -u 下链启动即死——
该形态由 shellcheck -S warning 的 SC2154 拦截（gauntlet 新层）。本检查器
补另一半盲区：shell 内联 python 的确定性语法验证。同类事故原形
`python3 -c - "$f" <<'TAG'`——-c 把字面量 `-` 当程序体，运行时
SyntaxError；bash -n 无感（shell 语法合法）、shellcheck 无感（不解析
python）、上游 pytest 门禁全绿放行。

覆盖形态（本仓 .factory/ tools/ scripts/ 实际使用的全部形态）：
  1. python3 … -c '<代码>'        单引号字面块 → 提取 compile()
  2. python3 … <<'TAG' … TAG      quoted heredoc（无 shell 展开）→ 提取 compile()
规则：
  R1  -c 的参数是字面量 `-` → 违规：-c - 把 `-` 当程序体，运行时必然
      SyntaxError（事故原形）。双引号块（含 shell 展开）无法静态验证，
      不在此层判定——这是诚实的边界，不是放水：双引号形态无事故史，
      且任何静态判定都会是猜测而非确定性检查
  R2  -c 与 <<'TAG' heredoc 并用 → 违规：-c 已取程序体，heredoc 沦为
      无人消费的 stdin，语义错乱（事故原形的完整形态）
  R3  提取的代码块 compile() 失败 → 违规：报告文件与起始行号

用法: check_inline_python.py <file-or-dir>...
rc:  0 = 全部通过（或无内联 python）
     1 = 存在违规（检查确实执行且判定失败）
     2 = 检查器自身失败（路径不存在、读取错误）——绝不算通过
"""
import pathlib
import re
import subprocess
import sys

# 形态 1：python3 … -c '…'（单引号块，DOTALL 跨行；shell 单引号内无转义）
RE_DASH_C = re.compile(r"\bpython3?\s+(?:-[^\s']+\s+)*-c\s+'(.*?)'", re.DOTALL)
# 形态 2：命令行以 heredoc 结尾（<<'TAG'，起始行匹配到行尾）
RE_HEREDOC_CMD = re.compile(r"^\s*.*\bpython3?\b.*<<'([A-Za-z_][A-Za-z0-9_]*)'\s*$")


def extract_heredoc(lines, start):
    """start（0 基）行是 <<'TAG' 命令行；返回 (代码块文本, 结束行号0基)。"""
    m = RE_HEREDOC_CMD.search(lines[start])
    if m is None:
        return None, None
    tag = m.group(1)
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == tag:
            return "\n".join(lines[start + 1:i]), i
    return None, None  # 未闭合


def check_file(path):
    """返回该文件违规清单 [(lineno, message)]；读取失败抛 OSError（rc2）。"""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    lines = text.split("\n")
    violations = []

    # 形态 2 逐行状态机（先做，形态 1 由正则独立扫全文本）
    i = 0
    consumed = set()  # heredoc 体行号集合，避免与 -c 块重复报告
    while i < len(lines):
        if RE_HEREDOC_CMD.match(lines[i]):
            block, end = extract_heredoc(lines, i)
            if block is None:
                violations.append((i + 1, "heredoc <<'…' 未闭合"))
                break
            consumed.update(range(i + 1, end + 1))
            if re.search(r"\s-c\s", lines[i]):
                violations.append((i + 1, "R2: -c 与 heredoc 并用（-c 已取程序体，heredoc 无人消费）"))
            else:
                try:
                    compile(block, f"{path}:{i + 2}", "exec")
                except SyntaxError as e:
                    violations.append((i + 1, f"R3: heredoc python 语法错误: {e}"))
            i = end + 1
        else:
            i += 1

    # 形态 1：全文本扫 -c '…'
    for m in RE_DASH_C.finditer(text):
        lineno = text.count("\n", 0, m.start(1)) + 1
        if any(ln in consumed for ln in range(lineno, text.count("\n", 0, m.end(1)) + 1)):
            continue
        try:
            compile(m.group(1), f"{path}:{lineno}", "exec")
        except SyntaxError as e:
            violations.append((lineno, f"R3: -c 内联 python 语法错误: {e}"))

    # R1：-c 后跟 `-`（dash 字面量）——`-c -` 把 `-` 当程序体，运行时必然
    # SyntaxError。双引号块（含 shell 展开）无法静态验证，不在此层判定。
    for idx, line in enumerate(lines):
        for m in re.finditer(r"\bpython3?\s+(?:-[^\s']+\s+)*-c\s+(\S)", line):
            if m.group(1) == "-":
                violations.append((idx + 1, "R1: -c 参数为字面量 `-`——-c - 把 `-` 当程序体，"
                                            "运行时必然 SyntaxError（2026-08-22 事故原形）"))
    return violations


def main(argv):
    if len(argv) < 2:
        print("用法: check_inline_python.py <file-or-dir>...", file=sys.stderr)
        return 2
    targets = []
    for arg in argv[1:]:
        p = pathlib.Path(arg)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            # tracked 面（任意深度）：此前 p.glob("*.sh") 只扫顶层——
            # .factory/factory-lib.sh（链共享收口库）从未进过本门。
            # gitignored 产物（链 worktree 检出副本）天然出局。
            proc = subprocess.run(
                ["git", "-C", str(p), "ls-files", "-z", "--", "*.sh"],
                capture_output=True)
            if proc.returncode != 0:
                print(f"检查器自身失败: {p} 非 git 仓库（扫描面 = tracked 面）",
                      file=sys.stderr)
                return 2
            targets.extend(p / f for f in proc.stdout.decode("utf-8").split("\0") if f)
        else:
            print(f"检查器自身失败: 路径不存在 {arg}", file=sys.stderr)
            return 2
    if not targets:
        print("检查器自身失败: 无 .sh 目标（层清单漂移）", file=sys.stderr)
        return 2

    bad = 0
    for t in targets:
        try:
            violations = check_file(t)
        except (OSError, UnicodeDecodeError) as e:
            print(f"检查器自身失败: 读取 {t}: {e}", file=sys.stderr)
            return 2
        for lineno, msg in violations:
            print(f"{t}:{lineno}: {msg}", file=sys.stderr)
            bad += 1
    if bad:
        print(f"inline-python: {bad} 处违规（{len(targets)} 文件）", file=sys.stderr)
        return 1
    print(f"inline-python: {len(targets)} 文件通过（内联 python 可编译 / -c 参数合法）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
