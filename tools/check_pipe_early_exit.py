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
  - bash 3.2 语法子集：逐物理行解析。引号内的 `|` 不作管道分隔；引号外
    `\|` 转义是字面量；词首未引号 `#` 起行内注释（其后不作数）；`||`
    是逻辑或非管道，但**保留其后的管道边界**（`false || true | cat` 中
    true 仍按管道段判定）；heredoc 起始行可带管道/注释后缀
    （`cat <<'EOF' | sed` 的体整体跳过）；整行注释跳过。
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

# heredoc 起始：<<-? + 可选引号 tag（行中任意位置——起始行可带管道/
# 注释后缀，如 `cat <<'EOF' | sed`；在掩码行上匹配，引号内的 << 不算）
RE_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# grep 段内的 -m<N> / -m <N>（N≥1）
RE_GREP_M = re.compile(r"(?:^|\s)(-m\s*[1-9][0-9]*)")

# 逻辑或占位符：掩码行上引号外 `||` 折叠为该字符——它是"命令分隔符但
# 非管道"，段内再按它拆出子命令（见 check_line 的邻接判定）
OR_PLACEHOLDER = "\x01"


def mask_line(line):
    """返回掩码行：引号区与转义字符 → 空格，行内注释（词首 #）截断。

    栈式扫描：`$( … )` 与反引号命令替换开嵌套层，层内引号状态独立、
    `|` 是真管道——`"$(git diff | true)"`（PR #9 原形）因此不漏报。
    单引号内全字面；双引号内 `\\` 转义下一字符、其余字面；引号外 `\\`
    同样转义（`printf x \\| true` 的 | 是字面量，非分隔符）；词首
    未引号 `#` 起注释（`echo ok # | true` 的后半不是命令）。
    """
    out = []
    # 层栈 (kind, quote)：kind ∈ top/cmdsub($())/backtick；quote ∈ None/'/'"/"
    stack = [("top", None)]
    i, n = 0, len(line)
    while i < n:
        kind, quote = stack[-1]
        c = line[i]
        if quote == "'":
            if c == "'":
                stack[-1] = (kind, None)
            out.append(" ")
        elif quote == '"':
            if c == "\\" and i + 1 < n:
                out.append("  ")
                i += 1
            elif c == '"':
                stack[-1] = (kind, None)
                out.append(" ")
            elif c == "$" and i + 1 < n and line[i + 1] == "(":
                stack.append(("cmdsub", None))  # 双引号内 $( 同样开嵌套层
                out.append("  ")
                i += 1
            elif c == "`":
                stack.append(("backtick", None))
                out.append(" ")
            else:
                out.append(" ")
        elif c == "'" or c == '"':
            stack[-1] = (kind, c)
            out.append(" ")
        elif c == "\\" and i + 1 < n:
            out.append("  ")                     # 引号外转义：\| 不作分隔符
            i += 1
        elif c == "$" and i + 1 < n and line[i + 1] == "(":
            stack.append(("cmdsub", None))
            out.append("  ")
            i += 1
        elif c == "`":
            if kind == "backtick":
                stack.pop()
            else:
                stack.append(("backtick", None))
            out.append(" ")
        elif c == ")" and kind == "cmdsub":
            stack.pop()
            out.append(" ")
        elif c == "#" and (i == 0 or line[i - 1] in " \t;|&(`"):
            break                                # 词首 # 起注释：其后不作数
        else:
            out.append(c)
        i += 1
    return "".join(out)


def split_pipeline(masked):
    """掩码行按单个 `|` 拆管道段；`||`（逻辑或）折叠为占位符留在段内。"""
    return masked.replace("||", OR_PLACEHOLDER).split("|")




# 段首命令 token（含尾部 `)"` 等命令替换收尾杂符的容忍）
RE_SEG_CMD = re.compile(r"(true|grep|head)\b")


def check_line(line):
    """返回该行违规 [(rule, msg)]；非管道行（<2 个非空段）返回空。

    管段判定按**邻接**而非位置：`||` 之后的命令仍可能是其后管道的
    左端——`false || true | cat` = false || (true | cat)，其中 true 是
    真管道段。子命令 = 段内按逻辑或占位符再拆；某子命令是管道段
    当且仅当：
      左邻接 —— 所在段末个子命令且段序 < 末段（其后有 `|`）；
      右邻接 —— 所在段首个子命令且段序 > 0（其前有 `|`）。
    R1/R2 要求左邻接（非末位早退）；R3 要求任一邻接（含末位）。
    `a | b || true` 的 true 无任何邻接 → 放行（这正是吞错码的正确形）。
    """
    segs = [s for s in split_pipeline(mask_line(line)) if s.strip()]
    if len(segs) < 2:
        return []
    out = []
    last_seg = len(segs) - 1
    for si, seg in enumerate(segs):
        subs = [t for t in (u.strip() for u in seg.split(OR_PLACEHOLDER)) if t]
        if not subs:
            continue
        for ci, sub in enumerate(subs):
            m_cmd = RE_SEG_CMD.match(sub)
            if m_cmd is None:
                continue
            cmd = m_cmd.group(1)
            pipe_left = ci == len(subs) - 1 and si < last_seg
            pipe_right = ci == 0 and si > 0
            if cmd == "true":
                if pipe_left or pipe_right:
                    out.append(("R3", "true 作为管道段——吞掉全部 stdout 且掩盖退出码，"
                                      "pipefail 下整管道恒为 true 的 0（PR #9 / #23 形态）；"
                                      "吞错码的正确写法是 `|| true`（逻辑或，非管道段）"))
            elif cmd == "grep":
                m = RE_GREP_M.search(sub)
                if m and pipe_left:
                    out.append(("R1", f"grep {m.group(1).replace(' ', '')} 在管道非末位"
                                      "——读够即退关读端，上游 SIGPIPE(141)，"
                                      "pipefail 放大整管道失败（etf-radar#70 形态）"))
            elif cmd == "head" and pipe_left:
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
        raw = lines[i]
        if raw.lstrip().startswith("#"):
            i += 1
            continue
        tags = [m.group(2) for m in RE_HEREDOC.finditer(raw)]
        # tag 识别在原始行上（引号 tag `<<'EOF'` 是常态，掩码会吃掉引号
        # 内容）；代价：引号字符串里的 `<<TAG` 字面量会被当起始（漏报窗口
        # 有界——跳到 tag 行为止，宁漏报不误报）。同一行多个 heredoc 按
        # 出现序消费。
        for rule, msg in check_line(raw):
            violations.append((i + 1, f"{rule}: {msg}"))
        if tags:
            # heredoc 体是重定向数据而非命令：跳过各 tag 行（未闭合则跳
            # 到文件尾——那是 bash -n 层的语法错误，不归本门）
            i += 1
            for tag in tags:
                while i < len(lines) and lines[i].strip() != tag:
                    i += 1
                i += 1
            continue
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
            try:
                proc = subprocess.run(
                    ["git", "-C", str(p), "ls-files", "-z", "--", "*.sh"],
                    capture_output=True)
                if proc.returncode != 0:
                    print(f"检查器自身失败: {p} 非 git 仓库（扫描面 = tracked 面）",
                          file=sys.stderr)
                    return 2
                targets.extend(p / f for f in proc.stdout.decode("utf-8").split("\0") if f)
            except (OSError, UnicodeDecodeError) as e:
                print(f"检查器自身失败: git 扫描 {p}: {e}", file=sys.stderr)
                return 2
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
