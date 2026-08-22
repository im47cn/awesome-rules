"""架构鹰眼 CLI 路由测试（自 doc-gen test_main_aggregate_routes 迁移）。"""

import json
import sys

import pytest

from hawkeye import main


def test_main_aggregate_routes(tmp_path, monkeypatch):
    cfg = tmp_path / "p.json"
    cfg.write_text(json.dumps({"projects": [
        {"id": "x", "name": "X", "manifest": str(tmp_path)}]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv",
                        ["hawkeye.py", "aggregate", str(cfg), "--output", str(tmp_path / "out")])
    main()                                                  # 聚合空 manifest，不抛
    assert (tmp_path / "out" / "doc-manifest" / "index.json").exists()


def test_main_no_command_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["hawkeye.py"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 0
