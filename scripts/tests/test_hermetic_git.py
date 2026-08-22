"""负控制回归：git 夹具套件在注入 GIT_DIR 环境下必须密封。

2026-08-22 事故：lefthook pre-push 链（.lefthook/run-tests.sh →
scripts/pre-push-tests.sh → scripts/run_tests.sh）在 git 注入的
GIT_DIR/GIT_WORK_TREE 环境下跑了全量 pytest——套件里 cwd=tmp_path 的
git init/add/commit 因显式环境变量优先于 cwd 发现被劫持到注入仓，
真仓被改写（389 文件删除）。修复：各套件 conftest 在 import 期剥离
GIT_*（见各 conftest「测试密封性」注释与 steering/testing-standards.md）。

本测试还原注入环境跑真实套件代码路径，断言双通道零副作用：
1. 牺牲仓 rev-list --all --count == 0（无任何对象落库）；
2. 真仓 status --porcelain 前后不变（index/worktree 未被波及）。

注意：GIT_DIR 必须指向非裸 gitdir（git init 缺省形态）——指向裸仓时
git 直接 fatal "must be run in a work tree"，测试假红而非演示静默劫持；
hook 注入的 GIT_DIR 恒为完整 gitdir（事故中即真仓 .git）。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# (套件 scripts 目录, pytest node id)——覆盖全部 4 个含 git init/add/commit
# 夹具的测试（见任务简报劫持点清单；新增 git 夹具测试须同步补行）
GIT_FIXTURE_CASES = [
    ("skills/arch-guard/scripts",
     "tests/test_arch_check.py::test_commit_binding_git_semantics"),
    ("skills/impact-guard/scripts",
     "tests/test_impact_guard.py::TestRenderer::test_commit_binding_git_semantics"),
    ("skills/doc-gen/scripts",
     "tests/test_risks.py::test_blame_file_batch_parses_full_file"),
    ("arch-hawkeye/scripts",
     "tests/test_integration.py::test_handoff_docgen_manifest_to_hawkeye"),
]


@pytest.mark.parametrize("suite,nodeid", GIT_FIXTURE_CASES)
def test_git_fixture_hermetic_under_injected_git_dir(tmp_path, suite, nodeid):
    """以牺牲仓还原 hook 注入环境：套件必须绿且零副作用。"""
    sacrificial = tmp_path / "hijack-target"
    subprocess.run(["git", "init", "-q", str(sacrificial)], check=True, timeout=30)
    git_dir = sacrificial / ".git"

    def repo_porcelain():
        # 本套件 conftest 已剥离 GIT_*，-C 正常解析真仓
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout

    before = repo_porcelain()
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)  # 模拟 lefthook/git hook 注入
    r = subprocess.run(
        [sys.executable, "-m", "pytest", nodeid, "-o", "addopts=", "-q"],
        cwd=REPO_ROOT / suite, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, (
        f"子套件测试未通过（密封不应改变正常路径的行为）:\n"
        f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}")

    count = subprocess.run(
        ["git", "--git-dir", str(git_dir), "rev-list", "--all", "--count"],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout.strip()
    assert count == "0", (
        f"劫持复现：{nodeid} 在 GIT_DIR 注入下向牺牲仓写入了 {count} 个提交——"
        "套件 conftest 未在 import 期剥离 GIT_DIR/GIT_WORK_TREE 等（测试密封性失效）")
    assert repo_porcelain() == before, "真仓状态被子测试改变——密封失效"
