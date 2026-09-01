"""evo_config 单测：默认值 / 极简 toml 解析 / scope 判定。"""
import re
from pathlib import Path

import evo_config as C


def test_defaults_when_no_file(tmp_path):
    cfg = C.load_config(str(tmp_path / "absent.toml"))
    assert cfg["enabled"] is True
    assert cfg["min_messages"] == 6
    assert cfg["scope_dirs"] == ["~/sources"]


def test_kv_parse_types(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text(
        'enabled = false\n'
        'min_messages = 10\n'
        'scope_dirs = ["~/work", "~/proj"]\n'
        '# 注释行\n'
        '[should_be_ignored]\n'
        'unknown_key = "x"\n',
        encoding="utf-8")
    cfg = C.load_config(str(f))
    assert cfg["enabled"] is False
    assert cfg["min_messages"] == 10
    assert cfg["scope_dirs"] == ["~/work", "~/proj"]
    assert "unknown_key" not in cfg          # 未知键忽略
    assert cfg["claude_bin"] == "claude"     # 未覆盖项保默认


def test_in_scope(tmp_path):
    cfg = dict(C.DEFAULTS)
    cfg["scope_dirs"] = [str(tmp_path)]
    assert C.in_scope(str(tmp_path / "repo"), cfg)
    assert C.in_scope(str(tmp_path), cfg)
    assert not C.in_scope(str(tmp_path.parent), cfg)
    assert not C.in_scope(None, cfg)


def test_repo_root_structural_anchor():
    # 结构不变量：repo_root() 是 evo_config.py 的祖先且含 skill-evo 资产。
    # 目录名不是不变量——worktree/CI checkout 目录名任意；旧断言
    # root.name == "awesome-rules" 在任何 worktree 形态下都是假红源
    # （feedback-upstream 曾被迫给上游 worktree 命名 awesome-rules 规避）。
    root = C.repo_root()
    assert Path(C.__file__).resolve().is_relative_to(root)
    assert (root / "skills" / "skill-evo" / "SKILL.md").is_file()
    # 负例：非根祖先（skills/ 目录）不含根 marker，marker 判据有区分度
    assert not (Path(C.__file__).resolve().parents[2] / "skills" / "skill-evo" / "SKILL.md").is_file()


def test_base_paths(tmp_path):
    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    paths = C.base_paths(cfg)
    assert paths["pending"] == tmp_path / "ar" / "proposals" / "pending"
    assert paths["state"].name == "state.json"


def test_idempotent_threshold_default_and_override(tmp_path):
    """idempotent_threshold：默认 0.8（float），toml 可覆盖。"""
    assert C.DEFAULTS["idempotent_threshold"] == 0.8
    assert C.load_config(str(tmp_path / "absent.toml"))["idempotent_threshold"] == 0.8
    f = tmp_path / "config.toml"
    f.write_text("idempotent_threshold = 0.9\n", encoding="utf-8")
    assert C.load_config(str(f))["idempotent_threshold"] == 0.9


def test_config_example_keys_match_defaults():
    """config.example.toml ↔ DEFAULTS 键集合一致（任一端漂移即红）。"""
    example = Path(C.__file__).resolve().parents[1] / "config.example.toml"
    keys = set()
    for ln in example.read_text(encoding="utf-8").splitlines():
        if m := re.match(r"^([A-Za-z_]\w*)\s*=", ln.split("#", 1)[0]):
            keys.add(m[1])
    assert keys == set(C.DEFAULTS)
