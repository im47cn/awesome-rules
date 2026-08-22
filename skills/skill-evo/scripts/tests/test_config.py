"""evo_config 单测：默认值 / 极简 toml 解析 / scope 判定。"""
import os

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


def test_repo_root_is_awesome_rules():
    root = C.repo_root()
    assert root.name == "awesome-rules"
    assert (root / "skills" / "skill-evo" / "SKILL.md").is_file()


def test_base_paths(tmp_path):
    cfg = dict(C.DEFAULTS)
    cfg["base_dir"] = str(tmp_path / "ar")
    paths = C.base_paths(cfg)
    assert paths["pending"] == tmp_path / "ar" / "proposals" / "pending"
    assert paths["state"].name == "state.json"
