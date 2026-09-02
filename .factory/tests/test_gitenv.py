"""git_env 密闭面契约测试（issue #109：宿主环境渗漏两陷阱）。

缺陷→测试映射：
- #109 陷阱①（宿主 PATH 可见 sourcery → 夹具网络闸挂起/超时）
  → test_path_whitelisted_to_anchor_dirs
- #109 陷阱②（宿主全局 gpgsign=true → 夹具 commit rc=128）
  → test_git_config_sealed_to_dev_null
- 密闭面不可被 base 松开（毒化 PATH/GIT_CONFIG_* 被覆盖）
  → test_sealed_overrides_base_poison
- PR #71 原契约不回归（仓库发现变量剥除）
  → test_stale_repo_discovery_stripped
- base 拷贝语义（不原地改写调用方 dict）
  → test_base_not_mutated
"""
import os
import shutil

from gitenv import _sealed_path, git_env


def test_path_whitelisted_to_anchor_dirs():
    env = git_env()
    dirs = env["PATH"].split(os.pathsep)
    # 白名单 ⊆ 锚定目录 ∪ POSIX 标准目录（宿主私有目录整体剥除）
    allowed = {"/usr/bin", "/bin"}
    for tool in ("python3", "git", "bash"):
        where = shutil.which(tool)
        if where:
            allowed.add(os.path.dirname(where))
    assert set(dirs) <= allowed
    # 锚定工具在密闭 PATH 下仍可解析（测试链不断链）
    for tool in ("python3", "git", "bash"):
        assert shutil.which(tool, path=env["PATH"]) is not None
    # 陷阱①实证：sourcery 若在宿主 PATH 可见且不在白名单目录，
    # 密闭后必须不可见（夹具闸 command -v 跳过 → 零出网）
    sr_host = shutil.which("sourcery")
    if sr_host and os.path.dirname(sr_host) not in allowed:
        assert shutil.which("sourcery", path=env["PATH"]) is None


def test_git_config_sealed_to_dev_null():
    # 陷阱②：宿主全局/系统 gitconfig（gpgsign 等）不渗入夹具
    env = git_env()
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["GIT_CONFIG_SYSTEM"] == "/dev/null"


def test_sealed_overrides_base_poison():
    # 密闭面不可被调用方松开：base 毒化 PATH/GIT_CONFIG_* 被覆盖
    env = git_env({"PATH": "/nonexistent", "GIT_CONFIG_GLOBAL": "/tmp/evil"})
    assert env["PATH"] == _sealed_path()
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["GIT_CONFIG_SYSTEM"] == "/dev/null"


def test_stale_repo_discovery_stripped():
    # PR #71 原契约：GIT_DIR 等仓库发现变量剥除（不回归）
    env = git_env({"GIT_DIR": "/poison", "GIT_WORK_TREE": "/poison"})
    assert "GIT_DIR" not in env
    assert "GIT_WORK_TREE" not in env


def test_base_not_mutated():
    # 拷贝语义：调用方 dict 不被原地改写
    base = {"GIT_DIR": "x"}
    git_env(base)
    assert base == {"GIT_DIR": "x"}
