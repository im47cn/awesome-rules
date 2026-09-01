"""sync-from-upstream.sh 回归测试 —— 补齐缺失文件分支（脚本首测）。

缺陷→测试映射:
- 缺失父目录写入崩溃（wop-skills 2026-08-31 事故：tests/ 目录整缺，
  「本地缺失」补齐分支对不存在路径直接重定向 → No such file or directory，
  apply 中途崩、锚点未写）→ TestApplyMissingParentDir：mkdir -p 补齐
  + blob 落地 + mode 恢复 + 锚点写入 + rc=0
- 退出码契约（头注释：0=干净/已同步 1=有漂移 2=用法/上游不可用）
  → TestCheckMissingFile：--check 对本地缺失 full 文件 rc=1
- 中心驱动契约（--repo 自任意 cwd 操作目标仓；目标非 git 仓 fail-closed）
  → TestRepoMode：产物落目标仓 + lock 含 upstream 字段 + 非 git/缺路径 rc=2
- --commit 契约（单提交落库 + blame-ignore 滞后一条 + 脏守卫 + 空追平
  不提交——防无漂移重跑链式生成噪音提交）→ TestApplyCommit
"""

import json
import re
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

def _head_count(repo: Path) -> int:
    return int(subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
        env=git_env(), check=True, capture_output=True, text=True,
    ).stdout.strip())


def _head_subject(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        env=git_env(), check=True, capture_output=True, text=True,
    ).stdout.strip()


_IDENTITY = {
    "GIT_AUTHOR_NAME": "factory-test", "GIT_AUTHOR_EMAIL": "factory@test",
    "GIT_COMMITTER_NAME": "factory-test", "GIT_COMMITTER_EMAIL": "factory@test",
}


def _run_env() -> dict:
    """git_env + 提交身份：脚本内 git commit 不依赖宿主全局配置。"""
    env = git_env()
    env.update(_IDENTITY)
    return env


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


class TestRepoMode:
    def test_repo_mode_syncs_target_from_foreign_cwd(self, repos, tmp_path):
        up, dn, anchor = repos
        foreign = tmp_path / "elsewhere"
        foreign.mkdir()
        proc = subprocess.run(
            ["bash", str(dn / ".factory/sync-from-upstream.sh"),
             str(up), "--repo", str(dn), "--apply", "--anchor", "main"],
            cwd=foreign, env=_run_env(), capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert (dn / ".factory/tests/conftest.py").read_text(encoding="utf-8") \
            == "# upstream canonical\n"
        lock = json.loads((dn / ".factory/upstream-lock.json").read_text(encoding="utf-8"))
        assert lock["anchor"] == anchor
        assert lock["upstream"] == str(up)

    def test_repo_mode_rejects_non_git_dir(self, repos, tmp_path):
        up, _, _ = repos
        plain = tmp_path / "plain"
        plain.mkdir()
        proc = subprocess.run(
            ["bash", str(repos[1] / ".factory/sync-from-upstream.sh"),
             str(up), "--repo", str(plain), "--check"],
            cwd=tmp_path, env=_run_env(), capture_output=True, text=True,
        )
        assert proc.returncode == 2
        assert "不是 git 仓库" in proc.stderr

    def test_repo_mode_rejects_missing_path(self, repos, tmp_path):
        up, dn, _ = repos
        proc = subprocess.run(
            ["bash", str(dn / ".factory/sync-from-upstream.sh"),
             str(up), "--repo", str(tmp_path / "nope"), "--check"],
            cwd=tmp_path, env=_run_env(), capture_output=True, text=True,
        )
        assert proc.returncode == 2
        assert "不存在" in proc.stderr


class TestApplyCommit:
    def _run(self, dn: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(dn / ".factory/sync-from-upstream.sh"), *args],
            cwd=dn, env=_run_env(), capture_output=True, text=True,
        )

    def test_first_commit_bootstrap_blame_ignore(self, repos):
        up, dn, anchor = repos
        proc = self._run(dn, str(up), "--apply", "--commit", "--anchor", "main")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _head_count(dn) == 2, "单提交落库（fixture 1 + 追平 1）"
        assert _head_subject(dn) == f"factory: 上游同步追平（{anchor[:9]}）"
        ignore = dn / ".git-blame-ignore-revs"
        lines = ignore.read_text(encoding="utf-8").splitlines()
        assert lines and lines[0].startswith("#"), "带说明头"
        assert not [l for l in lines if re.fullmatch(r"[0-9a-f]{40}", l)], \
            "首跑无历史追平提交可记（lock 此前不存在）"
        cfg = subprocess.run(
            ["git", "-C", str(dn), "config", "blame.ignoreRevsFile"],
            env=git_env(), check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert cfg == str(ignore)
        lock = json.loads((dn / ".factory/upstream-lock.json").read_text(encoding="utf-8"))
        assert lock["anchor"] == anchor
        assert lock["upstream"] == str(up)
        status = subprocess.run(
            ["git", "-C", str(dn), "status", "--porcelain"],
            env=git_env(), check=True, capture_output=True, text=True,
        ).stdout
        assert status.strip() == "", "落库后工作树干净"

    def test_second_sync_records_previous_sync_sha(self, repos):
        up, dn, _ = repos
        assert self._run(dn, str(up), "--apply", "--commit", "--anchor", "main").returncode == 0
        first_sync = subprocess.run(
            ["git", "-C", str(dn), "rev-parse", "HEAD"],
            env=git_env(), check=True, capture_output=True, text=True,
        ).stdout.strip()
        x = up / ".factory/tools/x.sh"
        x.write_text("#!/usr/bin/env bash\ntrue # v2\n", encoding="utf-8")
        _git(up, "add", "-A")
        _git(up, "commit", "-qm", "up v2")
        anchor2 = subprocess.run(
            ["git", "-C", str(up), "rev-parse", "HEAD"],
            env=git_env(), check=True, capture_output=True, text=True,
        ).stdout.strip()
        proc = self._run(dn, str(up), "--apply", "--commit", "--anchor", "main")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _head_count(dn) == 3
        assert _head_subject(dn) == f"factory: 上游同步追平（{anchor2[:9]}）"
        lines = (dn / ".git-blame-ignore-revs").read_text(encoding="utf-8").splitlines()
        assert first_sync in lines, "滞后一条：本轮记上一轮追平提交"

    def test_dirty_factory_refuses_commit(self, repos):
        up, dn, _ = repos
        (dn / ".factory/factory-local.json").write_text("{}\n", encoding="utf-8")
        proc = self._run(dn, str(up), "--apply", "--commit", "--anchor", "main")
        assert proc.returncode == 1
        assert "拒绝 --commit" in proc.stderr
        assert _head_count(dn) == 1, "失败不得产生提交"

    def test_no_drift_rerun_makes_no_commit(self, repos):
        up, dn, _ = repos
        assert self._run(dn, str(up), "--apply", "--commit", "--anchor", "main").returncode == 0
        proc = self._run(dn, str(up), "--apply", "--commit", "--anchor", "main")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "无变更可提交" in proc.stdout
        assert _head_count(dn) == 2, "无漂移重跑不生成空转提交（链式噪音回归）"

    def test_commit_without_apply_is_usage_error(self, repos):
        up, dn, _ = repos
        proc = self._run(dn, str(up), "--check", "--commit")
        assert proc.returncode == 2
        assert "--commit 仅与 --apply 组合" in proc.stderr
