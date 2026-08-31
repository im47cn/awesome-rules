"""sync-from-upstream.sh 回归测试 —— 补齐缺失文件分支（脚本首测）。

缺陷→测试映射:
- 缺失父目录写入崩溃（wop-skills 2026-08-31 事故：tests/ 目录整缺，
  「本地缺失」补齐分支对不存在路径直接重定向 → No such file or directory，
  apply 中途崩、锚点未写）→ TestApplyMissingParentDir：mkdir -p 补齐
  + blob 落地 + mode 恢复 + 锚点写入 + rc=0
- 退出码契约（头注释：0=干净/已同步 1=有漂移 2=用法/上游不可用）
  → TestCheckMissingFile：--check 对本地缺失 full 文件 rc=1
"""

import json
import subprocess
from pathlib import Path

import pytest

from gitenv import git_env

TESTS = Path(__file__).resolve().parent
FACTORY = TESTS.parent
SCRIPT = FACTORY / "sync-from-upstream.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=factory@test", "-c", "user.name=factory-test", *args],
        cwd=repo, env=git_env(), check=True, capture_output=True,
    )


@pytest.fixture()
def repos(tmp_path: Path):
    """上游（含嵌套 full 文件）+ 下游（.factory 仅脚本与 factory_lib，父目录全缺）。"""
    up = tmp_path / "up"
    dn = tmp_path / "dn"
    (up / ".factory" / "tests").mkdir(parents=True)
    (up / ".factory/tools").mkdir()
    (up / ".factory/DISTRIBUTION.json").write_text(json.dumps({
        "full": ["tests/conftest.py", "tools/x.sh"], "local": {}, "skip": [],
    }), encoding="utf-8")
    (up / ".factory/tests/conftest.py").write_text("# upstream canonical\n", encoding="utf-8")
    x = up / ".factory/tools/x.sh"
    x.write_text("#!/usr/bin/env bash\ntrue\n", encoding="utf-8")
    x.chmod(0o755)
    _git(up, "init", "-q", "-b", "main")
    _git(up, "add", "-A")
    _git(up, "commit", "-qm", "upstream fixture")
    anchor = subprocess.run(
        ["git", "-C", str(up), "rev-parse", "HEAD"],
        env=git_env(), check=True, capture_output=True, text=True,
    ).stdout.strip()

    dn.mkdir()
    (dn / ".factory").mkdir()
    for name in ("sync-from-upstream.sh", "factory_lib.py", "hosting.py",
                 "factory-local.json"):
        (dn / ".factory" / name).write_text(
            (FACTORY / name).read_text(encoding="utf-8"), encoding="utf-8")
    _git(dn, "init", "-q", "-b", "main")
    _git(dn, "add", "-A")
    _git(dn, "commit", "-qm", "downstream fixture")
    return up, dn, anchor


class TestApplyMissingParentDir:
    def test_fillin_creates_missing_parent_dirs(self, repos):
        up, dn, anchor = repos
        proc = subprocess.run(
            ["bash", str(dn / ".factory/sync-from-upstream.sh"),
             str(up), "--apply", "--anchor", "main"],
            cwd=dn, env=git_env(), capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        conf = dn / ".factory/tests/conftest.py"
        assert conf.read_text(encoding="utf-8") == "# upstream canonical\n"
        x = dn / ".factory/tools/x.sh"
        assert x.exists() and (x.stat().st_mode & 0o111), "mode 恢复（git show 丢 mode）"
        lock = json.loads((dn / ".factory/upstream-lock.json").read_text(encoding="utf-8"))
        assert lock["anchor"] == anchor


class TestCheckMissingFile:
    def test_check_missing_full_file_exits_1(self, repos):
        up, dn, _ = repos
        proc = subprocess.run(
            ["bash", str(dn / ".factory/sync-from-upstream.sh"),
             str(up), "--check", "--anchor", "main"],
            cwd=dn, env=git_env(), capture_output=True, text=True,
        )
        assert proc.returncode == 1
        assert "本地缺失" in proc.stdout
