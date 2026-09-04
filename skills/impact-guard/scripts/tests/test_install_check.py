"""tools/git/install.sh --check 巡检模式的黑盒 CLI 契约测试（issue #124）。

不 import、不解析 install.sh 内容，纯 subprocess 黑盒断言：
- 一致 → exit 0 且报 11/11；缺失/漂移 → 逐件点名 + exit 1（可挂 CI）
- 旧版实况（3 脚本 + 2 根配置）→ 按 11 件全集报告缺失，不误报已装件
- 非交互零副作用：不 mkdir、不写 ~/.gitmessage
- 在 node/npm 检测前短路：PATH 无 node 仍可巡检（负控制）

分发件清单在此硬编码为 DIST 镜像（与 install.sh DIST 单源对账）——
上游 DIST 静默缩水时，用例②点不全 11 件即红，防止门禁能力悄悄降级。
"""

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
INSTALL_SH = REPO_ROOT / "tools" / "git" / "install.sh"
BASH = shutil.which("bash") or "/bin/bash"

# (src 相对仓库根, dst 相对目标项目根) —— install.sh DIST 的镜像清单（11 件）
DIST = [
    ("tools/git/commitlint.config.cjs", "commitlint.config.cjs"),
    ("tools/git/.versionrc.cjs", ".versionrc.cjs"),
    ("tools/git/lefthook.yml", "lefthook.yml"),
    ("tools/git/lefthook/coverage.sh", ".lefthook/coverage.sh"),
    ("tools/git/lefthook/commitmsg-check.sh", ".lefthook/commitmsg-check.sh"),
    ("tools/git/lefthook/run-tests.sh", ".lefthook/run-tests.sh"),
    ("tools/git/lefthook/spec-check.sh", ".lefthook/spec-check.sh"),
    ("tools/git/lefthook/sourcery-gate.sh", ".lefthook/sourcery-gate.sh"),
    ("tools/git/lefthook/mutation-gate.sh", ".lefthook/mutation-gate.sh"),
    ("tools/git/lefthook/coderabbit-gate.sh", ".lefthook/coderabbit-gate.sh"),
    ("tools/spec_check.py", ".lefthook/spec_check.py"),
]
DIST_SRC = {dst: src for src, dst in DIST}

# issue 实况：旧版已装项目（gtsp-wop-* 三仓）装的是 .js 时代 5 件（issue #131 前）
LEGACY_INSTALLED = ("commitlint.config.js", "lefthook.yml",
                    ".lefthook/commitmsg-check.sh", ".lefthook/coverage.sh",
                    ".lefthook/run-tests.sh")
# 按 .cjs 新口径：旧装 .js 不匹配任何分发名 → 缺 7 件，且旧 .js 触发「遗留」检出
LEGACY_MISSING = ("commitlint.config.cjs", ".versionrc.cjs",
                  ".lefthook/spec-check.sh", ".lefthook/sourcery-gate.sh",
                  ".lefthook/mutation-gate.sh", ".lefthook/coderabbit-gate.sh",
                  ".lefthook/spec_check.py")

# 旧 .js 分发名与 .cjs 同字节（git 100% 纯改名，issue #131）→ 种植旧名夹具借 .cjs 源
LEGACY_SRC = {"commitlint.config.js": "tools/git/commitlint.config.cjs"}


def _install(dsts, target):
    """夹具：shutil 拷贝构造「已装」态；绝不真跑 install 模式（node/npm/git 副作用）。"""
    for dst in dsts:
        dest = target / dst
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / (DIST_SRC.get(dst) or LEGACY_SRC[dst]), dest)


def _check(target, env=None):
    """黑盒调 --check：不 import、不解析脚本内容。"""
    return subprocess.run([BASH, str(INSTALL_SH), "--check", str(target)],
                          capture_output=True, text=True, env=env, timeout=60)


def _fake_home_env(tmp_path, path="/usr/bin:/bin"):
    """伪造 HOME（零副作用观测面）；path 传临时 bin 即最小 PATH 负控制。

    PATH 用 POSIX 标准目录兜底（对齐 .factory/tests gitenv 的 _FALLBACK_DIRS
    先例）：dirname/cmp 均可解析，宿主私有目录不参与。
    """
    return {"HOME": str(tmp_path / "home"), "PATH": path}


# ── 正道：全量一致即绿 ───────────────────────────────────────────────────────


def test_all_consistent_exits_zero_with_11_of_11(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    _install(DIST_SRC, target)
    r = _check(target, env=_fake_home_env(tmp_path))
    assert r.returncode == 0
    assert "11/11" in r.stdout


# ── 负道：缺失/漂移逐件点名，exit 1 可挂 CI ─────────────────────────────────


def test_empty_target_names_all_eleven_missing(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    r = _check(target, env=_fake_home_env(tmp_path))
    assert r.returncode == 1
    missing = {ln.split()[-1] for ln in r.stdout.splitlines() if ln.startswith("缺失")}
    assert missing == set(DIST_SRC)  # 11 件全部点名（硬编码镜像防 DIST 缩水）


def test_legacy_project_reports_missing_seven_and_flags_legacy_js(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    _install(LEGACY_INSTALLED, target)
    r = _check(target, env=_fake_home_env(tmp_path))
    assert r.returncode == 1
    missing = {ln.split()[-1] for ln in r.stdout.splitlines() if ln.startswith("缺失")}
    # 按 11 件全集报缺失（旧版 .js 不匹配新分发名即多件缺失），已装 4 件不误报
    assert missing == set(LEGACY_MISSING)
    # 旧 .js 分发名单独点名「遗留」——指引重跑 --update 迁移 .cjs（issue #131）
    assert any(ln.startswith("遗留  commitlint.config.js") for ln in r.stdout.splitlines())
    assert not [ln for ln in r.stdout.splitlines() if ln.startswith("漂移")]


def test_tampered_file_reported_as_drift_not_missing(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    _install(DIST_SRC, target)
    with open(target / "lefthook.yml", "ab") as f:
        f.write(b"x")  # append 一字节
    r = _check(target, env=_fake_home_env(tmp_path))
    assert r.returncode == 1
    drift = [ln for ln in r.stdout.splitlines() if ln.startswith("漂移")]
    assert len(drift) == 1 and "lefthook.yml" in drift[0]
    assert not [ln for ln in r.stdout.splitlines() if ln.startswith("缺失")]


# ── 零副作用：不 mkdir、不写 ~/.gitmessage ──────────────────────────────────


def test_check_has_no_side_effects(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    r = _check(target, env=_fake_home_env(tmp_path))
    assert r.returncode == 1
    assert not list(target.iterdir())          # 未创建 .lefthook/ 等任何文件
    assert not (home / ".gitmessage").exists()   # 未写机器级全局文件


# ── 负控制：node/npm 检测前短路（PATH 白名单对齐 .factory/tests gitenv 先例）─


def test_check_works_without_node_on_path(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "dirname", "cmp"):  # --check 巡检链仅有的外部工具
        real = shutil.which(tool)
        assert real is not None, f"宿主缺 {tool}，测试前置不满足"
        os.symlink(real, bin_dir / tool)
    target = tmp_path / "proj"
    target.mkdir()
    _install(DIST_SRC, target)
    r = _check(target, env=_fake_home_env(tmp_path, path=str(bin_dir)))
    # 若 --check 未在 node 检测前短路：PATH 无 node → exit 1 且「未检测到 node」
    assert r.returncode == 0
    assert "11/11" in r.stdout
    assert "未检测到 node" not in r.stdout


# ── CLI 自描述 ───────────────────────────────────────────────────────────────


def test_help_documents_check_mode():
    r = subprocess.run([BASH, str(INSTALL_SH), "-h"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "--check" in r.stdout
