#!/usr/bin/env python3
"""check_killpg_strict.py — 进程组信号平台语义的确定性静态门（Python 面）。

steering/testing-standards.md「进程组信号的平台语义（macOS 僵尸窗口）」
的机器执行层。背景（PR #36 flake）：孙进程被 SIGKILL 后变僵尸、由
launchd 异步收尸，窗口内 macOS XNU 对含待-reap 僵尸的进程组发信号
（含 sig=0 探活）报 EPERM 而非 ESRCH（同 UID 亦然）；Linux 无此差异。

规则：
  K1  os.killpg(...) 调用缺乏 EPERM 容忍：
      收集调用点的全部「try 体祖先」（调用在 try.body 子树内；处于
      handlers/orelse/finalbody 体的不算——兄弟子句不守护），若无任一
      祖先 try 的 except 子句涵盖 PermissionError → 违规。无任何 try
      祖先同样违规（PR #36 生产侧隐患原形：EPERM 炸调用方而非走
      "超时=无效运行"语义）。
  K2  单发探活判定：with pytest.raises(ProcessLookupError)（无 or /
      元组交替）体内出现缺乏容忍的 os.killpg(..., 0) 探活 → 违规
      （僵尸窗口 EPERM 逃出 raises 即 flake，PR #36 测试侧原形）。
      合规形态是 deadline 轮询（根本不用 raises 单发判定）。

安全等价形（放行——僵尸无需再杀，SIGKILL 对僵尸是 no-op）：
  except (ProcessLookupError, PermissionError) / except OSError /
  裸 except / except Exception——均算涵盖
  带 deadline 轮询的探活（.factory/tests/test_mutations_run.py::
  _assert_group_dead 范式）

定位（诚实边界，不静默放水）：
  - 只解析 Python：ast 是语言自身文法，零启发式零第三方依赖；字符串/
    注释里的字面形态天然不误报（只看语法节点）
  - bash 3.2 子集的 shell 形态（kill -0 单发、kill -- -PGID）首版不
    覆盖——本仓 tracked 面的 shell kill -0 均为单 pid 幂等巡检
    （cron-dispatch/dispatch/fix-issue 锁检查，非终局断言），无事故形态
  - 只认 os.killpg 属性调用；from os import killpg 裸名、os.kill
    负 pid 组信号等变体不覆盖（tracked 面无此形态，出现再扩）
  - ast 解析失败 = 检查器自身失败 rc2：tracked 面的 .py 连本解释器都
    解析不了，pytest 层同样跑不动，fail-closed 而非静默跳过

用法: check_killpg_strict.py <file-or-dir>...
rc:  0 = 全部通过（或无 killpg 形态）
     1 = 存在违规（检查确实执行且判定失败）
     2 = 检查器自身失败（路径不存在、非 git 仓、读取/解析错误）——绝不算通过
"""
import ast
import pathlib
import subprocess
import sys
import warnings

# 涵盖 PermissionError 的异常写法（PE ⊂ OSError ⊂ Exception ⊂ BaseException）
COVERS_EPERM = {"PermissionError", "OSError", "Exception", "BaseException"}


def _exc_name(node):
    """异常类型节点 → 名字（Name.id 或 Attribute.attr），其余返回 None。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def handler_covers_eperm(handler):
    """单个 except 子句是否涵盖 PermissionError：裸 except 全收。"""
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Tuple):
        names = (_exc_name(e) for e in handler.type.elts)
    else:
        names = (_exc_name(handler.type),)
    return any(n in COVERS_EPERM for n in names)


def killpg_calls(tree):
    """全部 os.killpg(...) 调用节点（属性调用；裸名赋值等引用不算杀点）。"""
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "killpg"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
    ]


def _body_ids(stmts):
    """语句列表子树全部节点 id 集（用于「调用在体内」判定）。"""
    return {id(sub) for stmt in stmts for sub in ast.walk(stmt)}


def eperm_tolerated(tree, call):
    """K1 判定：调用点是否存在任一 try 体祖先的 except 涵盖 EPERM。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and id(call) in _body_ids(node.body):
            if any(handler_covers_eperm(h) for h in node.handlers):
                return True
    return False
def is_sig0_probe(call):
    """sig=0 探活形态：第二位置参数是常量 0。"""
    return (len(call.args) >= 2
            and isinstance(call.args[1], ast.Constant)
            and call.args[1].value == 0
            and call.args[1].value is not False)


def in_raises_ple_only(tree, call):
    """K2 判定：调用是否处于 with pytest.raises(ProcessLookupError)
    （单异常、无 or/元组交替）的体内。"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            expr = item.context_expr
            if not (isinstance(expr, ast.Call)
                    and isinstance(expr.func, ast.Attribute)
                    and expr.func.attr == "raises"
                    and isinstance(expr.func.value, ast.Name)
                    and expr.func.value.id == "pytest"
                    and expr.args
                    and _exc_name(expr.args[0]) == "ProcessLookupError"):
                continue
            if id(call) in _body_ids(node.body):
                return True
    return False


def check_file(path):
    """返回该文件违规清单 [(lineno, message)]；读取失败抛 OSError（rc2）。

    ast 解析失败抛 SyntaxError（调用方转 rc2——fail-closed）。
    """
    text = pathlib.Path(path).read_text(encoding="utf-8")
    with warnings.catch_warnings():
        # 被扫文件 docstring 的无效转义（如 \|）触发 SyntaxWarning，与本门
        # 语义无关（语法错误仍抛 SyntaxError → rc2，fail-closed 不弱化）
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(text)
    violations = []
    for call in killpg_calls(tree):
        tolerated = eperm_tolerated(tree, call)
        if not tolerated:
            violations.append((call.lineno,
                               "K1: os.killpg 调用缺乏 EPERM 容忍"
                               "（macOS 僵尸窗口会炸调用方而非走无效运行语义）"))
        if not tolerated and is_sig0_probe(call) and in_raises_ple_only(tree, call):
            violations.append((call.lineno,
                               "K2: pytest.raises(ProcessLookupError) 单发探活判定"
                               "（僵尸窗口 EPERM 逃出 raises 即 flake，须 deadline 轮询）"))
    return sorted(violations)


def main(argv):
    if len(argv) < 2:
        print("用法: check_killpg_strict.py <file-or-dir>...", file=sys.stderr)
        return 2
    targets = []
    for arg in argv[1:]:
        p = pathlib.Path(arg)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            try:
                proc = subprocess.run(
                    ["git", "-C", str(p), "ls-files", "-z", "--", "*.py"],
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
        print("检查器自身失败: 无 .py 目标（层清单漂移）", file=sys.stderr)
        return 2

    bad = 0
    for t in targets:
        try:
            violations = check_file(t)
        except (OSError, UnicodeDecodeError) as e:
            print(f"检查器自身失败: 读取 {t}: {e}", file=sys.stderr)
            return 2
        except SyntaxError as e:
            print(f"检查器自身失败: 解析 {t}: {e}", file=sys.stderr)
            return 2
        for lineno, msg in violations:
            print(f"{t}:{lineno}: {msg}", file=sys.stderr)
            bad += 1
    if bad:
        print(f"killpg-strict: {bad} 处违规（{len(targets)} 文件）", file=sys.stderr)
        return 1
    print(f"killpg-strict: {len(targets)} 文件通过（killpg 调用均有 EPERM 容忍 / 无单发探活判定）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
