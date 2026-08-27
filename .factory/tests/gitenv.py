"""git 子进程环境密闭（pre-push 钩子防夹具污染，PR #71 实测事故）。

lefthook pre-push 在 git 钩子环境运行测试门禁：GIT_DIR 等仓库发现类
环境变量被导出给钩子进程链，泄漏进测试子进程后，`git -C <tmp仓>` 的
仓库发现被环境变量优先级覆盖——夹具 init/commit 落进真实仓 HEAD
（推送实测：worktree HEAD 出现树仅含 2 个夹具文件的陌生提交，随后
plugin_lock 因 HEAD 树缺文件连锁失败）。

调用：剥除仓库发现类变量，保留用户显式设置的其余变量。
"""
from __future__ import annotations

import os

# 仓库发现/定位类变量（泄漏即改写 -C/子目录发现结果）。GIT_CONFIG_*
# 属配置注入，各测试自行决定（breaker 沙箱显式置 /dev/null）。
_STALE = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_GRAFT_FILE",
    "GIT_INDEX_VERSION", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES",
)


def git_env(base: dict | None = None) -> dict:
    """拷贝环境并剥除 git 仓库发现类变量（默认基于 os.environ）。"""
    env = dict(base if base is not None else os.environ)
    for k in _STALE:
        env.pop(k, None)
    return env
