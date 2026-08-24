"""check_killpg_strict 单测：PR #36 两侧原形拦截 / 安全等价形放行 / rc 语义。

负控制原则（steering/testing-standards「自建关卡脚本的反作弊要求」）：
先证明检查器会失败（flake 原形 rc=1 且报行号与规则），再证放行边界
（容忍形态 rc=0），最后证损坏路径 rc=2 绝不算通过。

夹具为字符串字面量——ast 只看语法节点，字符串内的 os.killpg 字面形态
不会自匹配（本文件自身在扫描面内）。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "check_killpg_strict", _TOOLS / "check_killpg_strict.py")
assert _spec is not None and _spec.loader is not None
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

# PR #36 两侧原形：生产侧（严格 except 只容忍 ESRCH）、生产侧（无 try）、
# 测试侧（raises(PLE) 单发探活，flake 原形）
BAD = """import os
import signal
import pytest


def kill_strict(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def kill_unguarded(pgid):
    os.killpg(pgid, signal.SIGKILL)


def test_flaky_probe(pgid):
    with pytest.raises(ProcessLookupError):
        os.killpg(pgid, 0)
"""

# 安全等价形：元组容忍 / OSError 家族超集 / 裸 except / deadline 轮询
# （不用 raises 单发判定）；sig=0 探活在容忍 try 内（K2 不误伤局部容
# 忍形态——EPERM 已被就地捕获，逃不出 raises）
OK = """import os
import signal


def kill_tuple(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def kill_oserror(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def kill_bare(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except:
        pass


def probe_in_tolerant_try(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    return False


def real_kill_alias(pgid):
    real = os.killpg                       # 引用非杀点：不算 Call
    return real
"""


def test_incident_forms_flagged_with_line_and_rule(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(BAD, encoding="utf-8")
    v = M.check_file(f)
    rules_msgs = [msg for _, msg in v]
    # K1 三处：strict except、unguarded、探活调用也无 try（deadline 轮询
    # 形态才局部容忍）；K2 一处：探活处于 raises 单发判定内
    assert sum(1 for m in rules_msgs if m.startswith("K1")) == 3
    assert any(m.startswith("K2") for m in rules_msgs)      # 测试侧 flake 原形
    # 行号指明（1 基）：kill_strict 第 8 行、unguarded 第 14 行、探活第 19 行
    linenos = {ln for ln, _ in v}
    assert {8, 14, 19} <= linenos, v


def test_safe_equivalents_pass(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text(OK, encoding="utf-8")
    assert M.check_file(f) == []


def test_rc_semantics(tmp_path):
    """拦截 rc=1（stderr 带行号+规则）、干净 rc=0、损坏 rc=2。"""
    bad = tmp_path / "bad.py"
    bad.write_text(BAD, encoding="utf-8")
    ok = tmp_path / "ok.py"
    ok.write_text(OK, encoding="utf-8")
    checker = str(_TOOLS / "check_killpg_strict.py")

    r_bad = subprocess.run([sys.executable, checker, str(bad)],
                           capture_output=True, text=True)
    assert r_bad.returncode == 1
    assert "K1" in r_bad.stderr and "K2" in r_bad.stderr
    assert ":8:" in r_bad.stderr                 # 行号指明

    r_ok = subprocess.run([sys.executable, checker, str(ok)],
                          capture_output=True, text=True)
    assert r_ok.returncode == 0

    r_missing = subprocess.run([sys.executable, checker,
                                str(tmp_path / "definitely-missing")],
                               capture_output=True, text=True)
    assert r_missing.returncode == 2
    assert "检查器自身失败" in r_missing.stderr


def test_syntax_error_fail_closed_rc2(tmp_path):
    """ast 解析失败 = 检查器损坏（rc2），不得静默跳过该文件。"""
    f = tmp_path / "broken.py"
    f.write_text("def f(:\n    pass\n", encoding="utf-8")
    checker = str(_TOOLS / "check_killpg_strict.py")
    r = subprocess.run([sys.executable, checker, str(f)],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "解析" in r.stderr
    assert "Traceback" not in r.stderr


def test_dir_scan_face_is_tracked(tmp_path):
    """目录模式：扫描面 = git tracked 面；非 git 目录 fail-closed 拒判。"""
    import os
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "tracked.py").write_text(BAD, encoding="utf-8")
    (repo / "untracked.py").write_text(BAD, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.py"], check=True)
    checker = str(_TOOLS / "check_killpg_strict.py")
    r = subprocess.run([sys.executable, checker, str(repo)],
                       capture_output=True, text=True,
                       env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"})
    assert r.returncode == 1
    assert "tracked.py" in r.stderr
    assert "untracked.py" not in r.stderr

    plain = tmp_path / "plain"
    plain.mkdir()
    r2 = subprocess.run([sys.executable, checker, str(plain)],
                        capture_output=True, text=True)
    assert r2.returncode == 2


def test_handler_coverage_matrix(tmp_path):
    """except 涵盖判定单元矩阵：属性形态、元组、不相关异常均不涵盖。"""
    src = '''import os
def a(p):
    try:
        os.killpg(p, 9)
    except os.PermissionError:      # 属性形态：涵盖
        pass
def b(p):
    try:
        os.killpg(p, 9)
    except (ValueError, KeyError):  # 不相关元组：不涵盖
        pass
'''
    f = tmp_path / "matrix.py"
    f.write_text(src, encoding="utf-8")
    v = M.check_file(f)
    # 只有 b 的 killpg 违规（a 的 except os.PermissionError 属性形态涵盖）
    assert [ln for ln, _ in v] == [9], v


def test_sibling_clause_does_not_guard(tmp_path):
    """调用处于兄弟 except 体（非 try 体）→ 该 try 不守护（K1）。
    精确语义：兄弟子句从不捕获彼此体内的异常。"""
    src = '''import os
def f(p):
    try:
        pass
    except (ProcessLookupError, PermissionError):
        os.killpg(p, 9)            # 在 handler 体内，兄弟容忍不生效
'''
    f = tmp_path / "sibling.py"
    f.write_text(src, encoding="utf-8")
    v = M.check_file(f)
    assert [ln for ln, _ in v] == [6], v


def test_nested_outer_try_guards(tmp_path):
    """内层 except 不涵盖但外层涵盖 → 放行（异常沿栈传播被外层接住）。"""
    src = '''import os
def f(p):
    try:
        try:
            os.killpg(p, 9)
        except ValueError:
            pass
    except PermissionError:
        pass
'''
    f = tmp_path / "nested.py"
    f.write_text(src, encoding="utf-8")
    assert M.check_file(f) == []
