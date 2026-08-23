#!/usr/bin/env python3
"""check_pipe_early_exit.py — pipefail 管道早退的确定性静态门。

背景（issue #30 三犯成类）：set -o pipefail 下，管道中非末位的早退消费者
读够即退、关闭读端 → 上游写端 SIGPIPE(141) → pipefail 把它放大为整个
管道的失败码 → set -e 中止所在函数/trap。本仓三犯：
  PR #9          `git diff … | true`          diff 输出喂 true，changed 恒空，台账全记 no-diff
  issue #23      write_ledger 内 `| true`     trap 中止，清理链断，队列死锁
  etf-radar#70   `git remote … | grep -m1 … | sed`  grep 早退关读端，git 组 SIGPIPE 141

规则（只拦"确定性早退"的字面形态）：
  R1  `grep -m<N>`（N≥1）出现在管道非末位——读够 N 条匹配即 exit
  R2  `head` / `head -n <N>` 出现在管道非末位——读够即 exit
  R3  `true` 作为管道段（任意位置，含末位）——`| true` 吞掉全部 stdout
      且掩盖退出码，从来不是吞错码的正确写法（正确形态 `|| true` 是
      逻辑或层，非管道段）

安全等价形（放行——教机器认识"消费全量输入"）：
  `sed -n '1p'` / `sed -nE '1{…;p}'`   消费全部输入、只打印目标行
  `… || true`                          逻辑或层吞错，非管道段
  head 处于管道末位                    末位即目的（`cat f | head`）

定位（诚实边界，不静默放水）：
  - bash 3.2 语法子集：逐物理行解析。引号内的 `|` 不作管道分隔；`||`
    作逻辑或不作管道；heredoc 体（数据非命令）整体跳过；整行注释跳过。
    跨行引号/命令替换状态不跟踪——`$(…)` 嵌套内的管道可能漏报（宁漏报
    不误报）；case 模式交替 `a|b)` 子集外（本仓 tracked 面无此形态）。
  - awk `exit`、sed `q` 等其它早退形态首版不覆盖（issue 已声明边界），
    出现再扩。
  - 末位早退（`cat f | grep -m1 x`）放行：末位消费者早退正是其语义目的
    （issue 规则 R1/R2 均限定"非末位"）。

用法: check_pipe_early_exit.py <file-or-dir>...
rc:  0 = 全部通过（或无管道早退形态）
     1 = 存在违规（检查确实执行且判定失败）
     2 = 检查器自身失败（路径不存在、非 git 仓、读取错误）——绝不算通过
"""
import pathlib
import re
import subprocess
import sys

# heredoc 起始：<<-? + 可选引号 tag 至行尾（重定向后缀子集外，
# 与 check_inline_python.py 的 RE_HEREDOC_CMD 同一约定）
RE_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1\s*$")
# grep 段内的 -m<N> / -m <N>（N≥1）
RE_GREP_M = re.compile(r"(?:^|\s)(-m\s*[1-9][0-9]*)")

# 逻辑或占位符：split_pipeline 把引号外 `||` 折叠为该字符，使其所在
# 段不再以独立命令 token 开头——`a || true` 因此不会被误判为管道段
OR_PLACEHOLDER = "\x01"


def split_pipeline(line):
    """按引号外单个 `|` 拆管道段；`||`（逻辑或）折叠为占位符不拆段。

    栈式扫描：`$( … )` 与反引号命令替换开嵌套层，层内引号状态独立、
    `|` 是真管道——`"$(git diff | true)"`（PR #9 原形）因此不漏报。
    单引号内全字面；双引号内 `\\` 转义下一字符、其余字面。
    返回段 plain 文本列表：引号内字符以空格替代（token 提取与 -m 检测
    不受引号内 `|`/`-m` 干扰），逻辑或占位符 \\x01 保留在段内。
    """
    segs = []
    cur = []
    # 层栈 (kind, quote)：kind ∈ top/cmdsub($())/backtick；quote ∈ None/'/'"/"
    # cmdsub 与 backtick 层内无引号时与顶层同规则（`|` 是真管道），仅
    # 闭合符不同——`` `git diff | true` `` 与 $() 形态同等覆盖
    stack = [("top", None)]
    i, n = 0, len(line)
    while i < n:
        kind, quote = stack[-1]
        c = line[i]
        if quote == "'":
            if c == "'":
                stack[-1] = (kind, None)
            cur.append(" ")
        elif quote == '"':
            if c == "\\" and i + 1 < n:
                cur.append("  ")
                i += 1
            elif c == '"':
                stack[-1] = (kind, None)
                cur.append(" ")
            elif c == "$" and i + 1 < n and line[i + 1] == "(":
                stack.append(("cmdsub", None))  # 双引号内 $( 同样开嵌套层
                cur.append("  ")
                i += 1
            elif c == "`":
                stack.append(("backtick", None))
                cur.append(" ")
            else:
                cur.append(" ")
        elif c == "'" or c == '"':
            stack[-1] = (kind, c)
            cur.append(" ")
        elif c == "$" and i + 1 < n and line[i + 1] == "(":
            stack.append(("cmdsub", None))
            cur.append("  ")
            i += 1
        elif c == "`":
            if kind == "backtick":
                stack.pop()
            else:
                stack.append(("backtick", None))
            cur.append(" ")
        elif c == ")" and kind == "cmdsub":
            stack.pop()
            cur.append(" ")
        elif c == "|":
            if i + 1 < n and line[i + 1] == "|":
                cur.append(OR_PLACEHOLDER)
                i += 1
            else:
                segs.append("".join(cur))
                cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return segs


# 段首命令 token（含尾部 `)"` 等命令替换收尾杂符的容忍）
RE_SEG_CMD = re.compile(r"(true|grep|head)\b")


def check_line(line):
    """返回该行违规 [(rule, msg)]；非管道行（<2 个非空段）返回空。"""
    segs = [s for s in split_pipeline(line) if s.strip()]
    if len(segs) < 2:
        return []
    out = []
    last = len(segs) - 1
    for i, seg in enumerate(segs):
        s = seg.strip()
        m_cmd = RE_SEG_CMD.match(s)
        if m_cmd is None:
            continue
        cmd = m_cmd.group(1)
        if cmd == "true":
            out.append(("R3", "true 作为管道段——吞掉全部 stdout 且掩盖退出码，"
                              "pipefail 下整管道恒为 true 的 0（PR #9 / #23 形态）；"
                              "吞错码的正确写法是 `|| true`（逻辑或，非管道段）"))
        elif cmd == "grep":
            m = RE_GREP_M.search(s)
            if m and i != last:
                out.append(("R1", f"grep {m.group(1).replace(' ', '')} 在管道非末位"
                                  "——读够即退关读端，上游 SIGPIPE(141)，"
                                  "pipefail 放大整管道失败（etf-radar#70 形态）"))
        elif cmd == "head" and i != last:
            out.append(("R2", "head 在管道非末位——读够即退关读端，上游 SIGPIPE(141)，"
                              "pipefail 放大整管道失败"))
    return out


def check_file(path):
    """返回该文件违规清单 [(lineno, message)]；读取失败抛 OSError（rc2）。"""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    lines = text.split("\n")
    violations = []
    i = 0
    while i < len(lines):
        m = RE_HEREDOC.search(lines[i])
        if m:
            # 起始行本身仍是命令行（如 `cmd | cat <<EOF`），照常检查；
            # heredoc 体是重定向数据而非命令：跳过到 tag 行（未闭合则跳
            # 到文件尾——那是 bash -n 层的语法错误，不归本门）
            if not lines[i].lstrip().startswith("#"):
                for rule, msg in check_line(lines[i]):
                    violations.append((i + 1, f"{rule}: {msg}"))
            tag = m.group(2)
            i += 1
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1
            continue
        if not lines[i].lstrip().startswith("#"):
            for rule, msg in check_line(lines[i]):
                violations.append((i + 1, f"{rule}: {msg}"))
        i += 1
    return violations


def main(argv):
    if len(argv) < 2:
        print("用法: check_pipe_early_exit.py <file-or-dir>...", file=sys.stderr)
        return 2
    targets = []
    for arg in argv[1:]:
        p = pathlib.Path(arg)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            # tracked 面（任意深度，67c2965b tracked 面原则）：gitignored
            # 产物（链 worktree 检出副本）天然出局
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
        print(f"pipe-early-exit: {bad} 处违规（{len(targets)} 文件）", file=sys.stderr)
        return 1
    print(f"pipe-early-exit: {len(targets)} 文件通过（无非末位早退消费者 / 无 true 管道段）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
