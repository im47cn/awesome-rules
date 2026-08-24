"""owner_check 单测：负控制先行（越权必须红且点名），再证放行边界与 rc 语义。

夹具为临时真 git 仓（conftest 已剥 GIT_* 防真仓劫持）。核心断言锚定
2026-08-24 批次实测缺口：零派发改动（dispatch 下沉）与简报违反（manual-rules
裁剪）都必须被点名拦截——人眼 diff 兜底时代它们曾漏到集成末段才被发现。
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "owner_check", SCRIPTS / "owner_check.py")
assert _spec and _spec.loader
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture()
def repo(tmp_path):
    """临时仓：一个 base commit，供工作区/--base 两模式用。"""
    (tmp_path / ".factory").mkdir()
    (tmp_path / ".factory" / "README.md").write_text("base\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def manifest(path, owners, batch="test"):
    p = Path(path)
    p.write_text(json.dumps({"batch": batch, "owners": owners}, ensure_ascii=False))
    return str(p)


def run(repo, mf, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "owner_check.py"), "--manifest", mf,
         "--root", str(repo), *extra],
        capture_output=True, text=True)


OWNERS = [
    {"name": "reg", "allow": [".factory/regression/*"]},
    {"name": "deci", "allow": [".factory/decisions.md"]},
]


class TestOverreachFails:
    """负控制：门必须红。"""

    def test_undeclared_file_fails_and_names_it(self, repo, tmp_path):
        (repo / ".factory" / "decisions.md").write_text("x\n")       # 已声明
        (repo / "skills" / "api-guard").mkdir(parents=True)
        (repo / "skills" / "api-guard" / "manual-rules.md").write_text("被裁\n")  # 越权
        mf = manifest(tmp_path / "m.json", OWNERS)
        r = run(repo, mf)
        assert r.returncode == 1
        assert "manual-rules.md" in r.stdout
        assert "decisions.md" not in r.stdout.split("越权文件")[1].split("处置")[0]

    def test_untracked_is_a_change(self, repo, tmp_path):
        (repo / ".factory" / "regression").mkdir()
        (repo / ".factory" / "regression" / "x.sh").write_text("#\n")   # 已声明 untracked
        (repo / "rogue.py").write_text("#\n")                            # 越权 untracked
        mf = manifest(tmp_path / "m.json", OWNERS)
        r = run(repo, mf)
        assert r.returncode == 1 and "rogue.py" in r.stdout

    def test_rename_old_path_undeclared_fails(self, repo, tmp_path):
        (repo / ".factory" / "decisions.md").write_text("x\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add decisions")
        git(repo, "mv", ".factory/decisions.md", "elsewhere.md")   # 新侧越权
        mf = manifest(tmp_path / "m.json", OWNERS)
        r = run(repo, mf)
        assert r.returncode == 1 and "elsewhere.md" in r.stdout

    def test_base_mode_catches_zero_dispatch_change(self, repo, tmp_path):
        """2026-08-24 实测缺口复现：--base 验收已提交的零派发改动。"""
        (repo / ".factory" / "factory_lib.py").write_text("下沉\n")   # 无 owner 声明
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "refactor")
        mf = manifest(tmp_path / "m.json", OWNERS)
        r = run(repo, mf, "--base", "HEAD~1")
        assert r.returncode == 1 and "factory_lib.py" in r.stdout


class TestPassBoundaries:
    """放行边界：声明完整即 0。"""

    def test_all_declared_passes(self, repo, tmp_path):
        (repo / ".factory" / "regression").mkdir()
        (repo / ".factory" / "regression" / "weekly.sh").write_text("#\n")
        (repo / ".factory" / "decisions.md").write_text("x\n")
        (repo / ".factory" / "decisions.md").unlink()               # 删除也是改动
        mf = manifest(tmp_path / "m.json", OWNERS)
        r = run(repo, mf)
        assert r.returncode == 0

    def test_glob_crosses_directory(self, repo, tmp_path):
        (repo / ".factory" / "regression").mkdir(parents=True)
        (repo / ".factory" / "regression" / "a" / "b").mkdir(parents=True)
        (repo / ".factory" / "regression" / "a" / "b" / "deep.log").write_text("#\n")
        mf = manifest(tmp_path / "m.json", OWNERS)
        assert run(repo, mf).returncode == 0

    def test_rename_both_sides_declared_passes(self, repo, tmp_path):
        own = [{"name": "m", "allow": ["old.md", "new.md"]}]
        (repo / "old.md").write_text("x\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add")
        git(repo, "mv", "old.md", "new.md")
        mf = manifest(tmp_path / "m.json", own)
        assert run(repo, mf).returncode == 0

    def test_overlap_and_unused_are_warnings_not_failures(self, repo, tmp_path):
        own = [{"name": "a", "allow": ["shared.md", "ghost/*"]},
               {"name": "b", "allow": ["shared.md"]}]
        (repo / "shared.md").write_text("x\n")
        mf = manifest(tmp_path / "m.json", own)
        r = run(repo, mf)
        assert r.returncode == 0
        assert "a & b" in r.stdout and "ghost/*" in r.stdout


class TestConfigErrors:
    def test_missing_manifest_is_rc2(self, repo, tmp_path):
        r = run(repo, str(tmp_path / "nope.json"))
        assert r.returncode == 2

    def test_empty_owners_is_rc2(self, repo, tmp_path):
        mf = manifest(tmp_path / "m.json", [])
        assert run(repo, mf).returncode == 2

    def test_bad_json_is_rc2(self, repo, tmp_path):
        p = tmp_path / "m.json"
        p.write_text("{broken")
        assert run(repo, str(p)).returncode == 2
