"""upstream-sync-check.sh 退出码契约回归（wop-skills PR#14 Sourcery 评论 1）。

缺陷：sync --check 的致命 rc=2（用法/上游不可用/锚点不可解析）原被 `&& {}`
短路吞掉——输出不带 [local]/[full] 标记时落入收尾分支，以「仅 local 面漂移」
exit 0 误报无漂移，调用方（dispatch）把致命检查失败当无事发生。

修复：rc≥2 原样上抛（stderr + 同码退出）。本文件锁定 rc 契约矩阵：
  rc=0  干净      → exit 0（"无动作"）
  rc=1  full 漂移 → --dry-run 报告并 exit 1（本测试不触 apply/gauntlet/PR 面）
  rc=2  致命失败  → exit 2，且绝不走 issue/PR 流（fake hosting 计数断言）

凭据面用 fake hosting.py 顶替（auth ok 恒 0，其余调用计数 + 非 0）——
与 gitenv PATH 白名单配合，测试链零出网。
"""

import json
import subprocess
from pathlib import Path

import pytest

from gitenv import git_env

TESTS = Path(__file__).resolve().parent
FACTORY = TESTS.parent
SCRIPT = FACTORY / "upstream-sync-check.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=factory@test", "-c", "user.name=factory-test", *args],
        cwd=repo, env=git_env(), check=True, capture_output=True,
    )


@pytest.fixture()
def synced(tmp_path: Path):
    """up（上游含 full 文件）+ dn（下游 .factory 真实工具链 + fake hosting）+
    基态追平（dn full 面与 up 一致、lock 有效）→ 脚本可跑 rc=0 的干净基态。"""
    up = tmp_path / "up"
    dn = tmp_path / "dn"
    (up / ".factory" / "tools").mkdir(parents=True)
    (up / ".factory" / "DISTRIBUTION.json").write_text(json.dumps({
        "full": ["tools/x.sh"], "local": {}, "skip": [],
    }, ensure_ascii=False), encoding="utf-8")
    x = up / ".factory/tools/x.sh"
    x.write_text("#!/usr/bin/env bash\ntrue\n", encoding="utf-8")
    x.chmod(0o755)
    _git(up, "init", "-q", "-b", "main")
    _git(up, "add", "-A")
    _git(up, "commit", "-qm", "up fixture")

    dn.mkdir()
    (dn / ".factory").mkdir()
    # factory_lib.py import 即 fail-closed 读 factory-local.json（真实文件拷贝）
    for name in ("sync-from-upstream.sh", "upstream-sync-check.sh",
                 "factory_lib.py", "factory-local.json"):
        (dn / ".factory" / name).write_text(
            (FACTORY / name).read_text(encoding="utf-8"), encoding="utf-8")
    calls = tmp_path / "hosting-calls"
    # fake hosting：auth ok 恒过（凭据探测走真路径）；其它命令计数 + 非 0。
    # factory_lib.py 顶部 import hosting → 副作用必须收在 __main__ 内，
    # 否则 sys.exit 在 import 时即杀进程（实测 dist-manifest rc=3）。
    (dn / ".factory" / "hosting.py").write_text(
        "import sys\n"
        "def _log():\n"
        f'    open({str(calls)!r}, "a").write("|".join(sys.argv[1:]) + "\\n")\n'
        'if __name__ == "__main__":\n'
        "    _log()\n"
        '    sys.exit(0 if sys.argv[1:2] == ["auth"] else 3)\n',
        encoding="utf-8")
    (dn / ".factory" / "upstream-lock.json").write_text(
        json.dumps({"upstream": str(up)}, ensure_ascii=False), encoding="utf-8")
    _git(dn, "init", "-q", "-b", "main")
    _git(dn, "add", "-A")
    _git(dn, "commit", "-qm", "dn fixture")

    proc = subprocess.run(
        ["bash", str(dn / ".factory/sync-from-upstream.sh"), str(up), "--apply"],
        cwd=dn, env=git_env(), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return up, dn, calls


class TestSyncRcContract:
    def _run(self, dn: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(dn / ".factory/upstream-sync-check.sh"), *args],
            cwd=dn, env=git_env(), capture_output=True, text=True,
        )

    def test_clean_reports_no_action(self, synced):
        _, dn, calls = synced
        proc = self._run(dn)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "full 面干净，无动作" in proc.stdout
        lines = calls.read_text().splitlines()
        assert lines, "凭据探测须真实发生"
        assert all("auth" in l for l in lines), f"干净基态不得触发远端命令: {lines}"

    def test_fatal_sync_rc2_propagates(self, synced):
        """Sourcery PR#14 评论 1：sync --check 致命 rc=2 原样上抛，
        不得落入「仅 local 面漂移」exit 0 误报无漂移。"""
        up, dn, calls = synced
        (dn / ".factory/upstream-lock.json").write_text(
            json.dumps({"upstream": str(dn / "gone")}, ensure_ascii=False),
            encoding="utf-8")
        proc = self._run(dn)
        assert proc.returncode == 2, (
            f"致命 rc 须原样上抛（实得 rc={proc.returncode}）\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
        assert "上游仓不可用" in proc.stderr, "sync 的诊断须原样透传"
        assert "full 面干净" not in proc.stdout
        assert "仅 local 面漂移" not in proc.stdout
        lines = calls.read_text().splitlines()
        assert all("auth" in l for l in lines), f"rc=2 不得触发 issue/PR 流: {lines}"

    def test_full_drift_dryrun_exits_1(self, synced):
        """full 漂移 rc=1 语义不回归：--dry-run 报告并 exit 1（人工介入信号）。"""
        up, dn, calls = synced
        (dn / ".factory/tools/x.sh").write_text(
            "#!/usr/bin/env bash\ntrue # local drift\n", encoding="utf-8")
        proc = self._run(dn, "--dry-run")
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "[dry-run] full 漂移存在" in proc.stdout
        lines = calls.read_text().splitlines()
        assert all("auth" in l for l in lines), f"dry-run 不得触发远端命令: {lines}"
