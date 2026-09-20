"""并行测试门（ADR-016）测试：配置校验 / 栈探测 / 保守档适配 / 编排契约 / CLI。

覆盖面：
- parallel_gate_cfg：可选键缺失 → None；存在即严格校验 fail-closed
  RuntimeError、拒未知键（顶层与段级）、argv XOR shell、tag 唯一且禁
  换行（宿主脚本按行回收失败清单）、intra/stack/workers 取值域。
- detect_stack：构建文件 → 栈 id（maven/gradle/go/cargo/phpunit/dotnet/
  vitest 先于 jest/pytest），未识别 → None 不猜。
- intra_parallel_args：保守档适配表（fork 级分发，无进程内线程交错），
  pytest-xdist 缺席软降级带提示。
- run_parallel_gate：配置序回放（与完成序解耦）、失败 tag 逐行落盘
  （尾带换行）、段日志失败保留/成功即删（TMPDIR 私有化断言）、
  workers 有界并发、$PY 词替换、shell 段 pipefail、cwd 预检 fail-closed。
- main parallel-gate：未知参数/缺路径 → 2，--failed-tags 透传。

运行：python3 -m pytest .factory/tests/test_parallel_gate.py -o addopts= -q
（conftest 注入 .factory 到 sys.path）
"""
from __future__ import annotations

import json
import tempfile

import pytest

import factory_lib as fl


def _argv_seg(tag, code, *extra_words, **extra):
    return {"tag": tag, "argv": ["$PY", "-c", code, *extra_words]} | extra


# ───────────────────────── parallel_gate_cfg ─────────────────────────

class TestParallelGateCfg:
    def _cfg(self, monkeypatch, raw):
        monkeypatch.setattr(fl, "_LOCAL_CFG", {"parallel_gate": raw})
        return fl.parallel_gate_cfg()

    def test_missing_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(fl, "_LOCAL_CFG", {"final_gate_cmd": "x"})
        assert fl.parallel_gate_cfg() is None

    def test_minimal_normalization(self, monkeypatch):
        cfg = self._cfg(monkeypatch, {
            "segments": [{"tag": "s1", "argv": ["$PY", "-m", "pytest", "-q"]}],
        })
        assert cfg == {"workers": 0, "segments": [
            {"tag": "s1", "name": "s1", "intra": "off",
             "argv": ["$PY", "-m", "pytest", "-q"]}]}

    def test_name_explicit_and_empty_fallback(self, monkeypatch):
        cfg = self._cfg(monkeypatch, {"segments": [
            {"tag": "a", "name": "显示名", "argv": ["x"]},
            {"tag": "b", "name": "", "shell": "true"},
        ]})
        assert cfg is not None
        assert [s["name"] for s in cfg["segments"]] == ["显示名", "b"]

    def test_full_segment_normalization(self, monkeypatch):
        cfg = self._cfg(monkeypatch, {"workers": 2, "segments": [
            {"tag": "a", "cwd": "sub", "intra": "auto", "stack": "maven",
             "shell": "mvn test"}]})
        assert cfg == {"workers": 2, "segments": [
            {"tag": "a", "name": "a", "intra": "auto", "stack": "maven",
             "cwd": "sub", "shell": "mvn test"}]}

    @pytest.mark.parametrize("raw", [
        [],                                   # parallel_gate 非对象
        {"segments": [], "workers": 0},       # 空段表
        {"segments": "x"},                    # 段表非数组
        {"segments": ["x"]},                  # 段非对象
        {"segments": [{}], "typo": 1},        # 未知顶层键 + 缺 tag
        {"segments": [{"tag": "a"}], "extra": 1},
    ])
    def test_structural_rejections(self, monkeypatch, raw):
        with pytest.raises(RuntimeError, match="fail-closed"):
            self._cfg(monkeypatch, raw)

    @pytest.mark.parametrize("tag", ["", "  ", "a\nb", "a\rb"])
    def test_bad_tags_rejected(self, monkeypatch, tag):
        with pytest.raises(RuntimeError, match="tag"):
            self._cfg(monkeypatch, {"segments": [{"tag": tag, "argv": ["x"]}]})

    def test_duplicate_tag_rejected(self, monkeypatch):
        with pytest.raises(RuntimeError, match="重复"):
            self._cfg(monkeypatch, {"segments": [
                {"tag": "a", "argv": ["x"]}, {"tag": "a", "shell": "true"}]})

    @pytest.mark.parametrize("seg", [
        {"tag": "a"},                                   # argv/shell 全无
        {"tag": "a", "argv": ["x"], "shell": "true"},   # argv/shell 并存
        {"tag": "a", "argv": []},                       # 空词组 → 视同无 argv
        {"tag": "a", "argv": ["ok", ""]},               # 空词
        {"tag": "a", "shell": "   "},                   # 空白命令串
        {"tag": "a", "argv": ["x"], "intra": "on"},     # intra 取值域
        {"tag": "a", "argv": ["x"], "stack": "pytest2"},  # 栈白名单
        {"tag": "a", "argv": ["x"], "typo": 1},         # 段级未知键
        {"tag": "a", "argv": ["x"], "cwd": "  "},       # cwd 非空串
    ])
    def test_segment_rejections(self, monkeypatch, seg):
        with pytest.raises(RuntimeError):
            self._cfg(monkeypatch, {"segments": [seg]})

    @pytest.mark.parametrize("workers", [-1, "2", 1.5, True])
    def test_bad_workers_rejected(self, monkeypatch, workers):
        with pytest.raises(RuntimeError, match="workers"):
            self._cfg(monkeypatch, {
                "segments": [{"tag": "a", "argv": ["x"]}], "workers": workers})

    def test_stack_whitelist_membership(self, monkeypatch):
        raw = [{"tag": s, "argv": ["x"], "stack": s}
               for s in sorted(fl._PARALLEL_STACKS)]
        cfg = self._cfg(monkeypatch, {"segments": raw})
        assert cfg is not None
        assert {seg["stack"] for seg in cfg["segments"]} == set(fl._PARALLEL_STACKS)


# ───────────────────────── detect_stack ─────────────────────────

class TestDetectStack:
    def _stack(self, tmp_path, files, contents=None):
        contents = contents or {}
        for name in files:
            p = tmp_path / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(contents.get(name, "x"), encoding="utf-8")
        return fl.detect_stack(tmp_path)

    @pytest.mark.parametrize(("files", "expect"), [
        (["pom.xml"], "maven"),
        (["mvnw"], "maven"),
        (["build.gradle"], "gradle"),
        (["build.gradle.kts"], "gradle"),
        (["settings.gradle"], "gradle"),
        (["go.mod"], "go"),
        (["Cargo.toml"], "cargo"),
        (["phpunit.xml"], "phpunit"),
        (["phpunit.xml.dist"], "phpunit"),
        (["app.csproj"], "dotnet"),
        (["solution.sln"], "dotnet"),
        (["pytest.ini"], "pytest"),
        (["conftest.py"], "pytest"),
        ([], None),
    ])
    def test_markers(self, tmp_path, files, expect):
        assert self._stack(tmp_path, files) == expect

    def test_pyproject_tool_pytest(self, tmp_path):
        assert self._stack(tmp_path, ["pyproject.toml"],
                           {"pyproject.toml": "[tool.pytest.ini_options]\n"}) == "pytest"
        assert fl.detect_stack(tmp_path) == "pytest"

    def test_package_json_dep_based(self, tmp_path):
        deps = {"dependencies": {"vitest": "^1.0"}}
        (tmp_path / "package.json").write_text(
            json.dumps(deps), encoding="utf-8")
        assert fl.detect_stack(tmp_path) == "vitest"

    def test_package_json_jest_dep(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"jest": "^29"}}), encoding="utf-8")
        assert fl.detect_stack(tmp_path) == "jest"

    def test_vitest_precedes_jest(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps(
            {"devDependencies": {"jest": "^29", "vitest": "^1.0"}}),
            encoding="utf-8")
        assert fl.detect_stack(tmp_path) == "vitest"

    def test_package_json_test_script(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps(
            {"scripts": {"test": "jest --ci"}}), encoding="utf-8")
        assert fl.detect_stack(tmp_path) == "jest"

    def test_corrupt_package_json_not_guessed(self, tmp_path):
        (tmp_path / "package.json").write_text("{broken", encoding="utf-8")
        assert fl.detect_stack(tmp_path) is None

    def test_build_markers_precede_package_json(self, tmp_path):
        self._stack(tmp_path, ["pom.xml"])
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"jest": "^29"}}), encoding="utf-8")
        assert fl.detect_stack(tmp_path) == "maven"


# ───────────────────────── intra_parallel_args ─────────────────────────

class TestIntraParallelArgs:
    @pytest.mark.parametrize(("stack", "argv", "note_frag"), [
        ("maven", ["-T", "1C", "-DforkCount=1C", "-DreuseForks=true"], None),
        ("gradle", ["--parallel"], None),
        ("jest", ["--maxWorkers=50%"], None),
        ("vitest", [], "默认已并行"),
        ("go", [], "默认已并行"),
        ("cargo", [], "默认已并行"),
        ("phpunit", [], "段内串行"),
        ("dotnet", [], "段内串行"),
        (None, [], "未识别测试栈"),
    ])
    def test_conservative_adapters(self, stack, argv, note_frag):
        got_argv, got_note = fl.intra_parallel_args(stack, "python3")
        assert got_argv == argv
        if note_frag is None:
            assert got_note is None
        else:
            assert note_frag in got_note

    def test_pytest_with_xdist(self, monkeypatch):
        monkeypatch.setattr(fl, "_xdist_available", lambda _py: True)
        assert fl.intra_parallel_args("pytest", "python3") == (["-n", "auto"], None)

    def test_pytest_xdist_missing_soft_degrades(self, monkeypatch):
        monkeypatch.setattr(fl, "_xdist_available", lambda _py: False)
        argv, note = fl.intra_parallel_args("pytest", "python3")
        assert argv == []
        assert note is not None and "pytest-xdist" in note

    def test_maven_excludes_thread_interleaving(self):
        """保守档契约：Maven 不注入 -Dparallel=methods（顺序敏感放大器）。"""
        argv, _ = fl.intra_parallel_args("maven", "python3")
        assert all("parallel=" not in w for w in argv)


# ───────────────────────── run_parallel_gate ─────────────────────────

class TestRunParallelGate:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch, private_tmp):
        monkeypatch.delenv("PYTHON", raising=False)
        monkeypatch.setenv("TMPDIR", str(private_tmp))
        monkeypatch.setattr(tempfile, "tempdir", str(private_tmp))
        self.tmp = private_tmp

    def _gate(self, root, segs, failed, workers=0):
        return fl.run_parallel_gate(
            repo_root=root, cfg={"workers": workers, "segments": segs},
            failed_tags_path=str(root / failed))

    def test_green_replays_in_config_order_and_cleans_logs(
            self, tmp_path, capsys):
        rc = self._gate(tmp_path, [
            _argv_seg("slow-print",
                      "import time; time.sleep(0.3); print('slow-done')"),
            _argv_seg("fast-print", "print('fast-done')"),
        ], failed="tags.txt")
        out = capsys.readouterr().out
        assert rc == 0
        assert "✅ 并行段 2/2 全绿" in out
        # 回放序=配置序：快段先完成也不抢跑
        assert out.index("── slow-print") < out.index("── fast-print")
        assert out.index("slow-done") < out.index("fast-done")
        assert (tmp_path / "tags.txt").read_text(encoding="utf-8") == ""
        assert not list(self.tmp.glob("factory-parallel-gate.*"))

    def test_failure_retains_logs_and_writes_tags(
            self, tmp_path, capsys):
        rc = self._gate(tmp_path, [
            _argv_seg("good", "print('good-out')"),
            _argv_seg("boom", "print('boom-err'); import sys; sys.exit(3)"),
        ], failed="tags.txt")
        out, err = capsys.readouterr()
        assert rc == 1
        assert "❌ 失败段: boom" in out
        assert "❌ 段日志保留" in err
        assert out.index("── good") < out.index("── boom")
        assert "boom-err" in out            # 失败段日志已回放
        # 失败 tag 逐行落盘，尾带换行（宿主 read -r 逐行回收契约）
        assert (tmp_path / "tags.txt").read_text(encoding="utf-8") == "boom\n"
        # 段日志保留（成功即删的失败面）
        retained = list(self.tmp.glob("factory-parallel-gate.*"))
        assert len(retained) == 1
        assert any("boom-err" in p.read_text(encoding="utf-8")
                   for p in retained[0].glob("*.log"))

    def test_failure_tags_follow_config_order(self, tmp_path):
        rc = self._gate(tmp_path, [
            _argv_seg("fail-late",
                      "import time; time.sleep(0.25); import sys; sys.exit(1)"),
            _argv_seg("fail-early", "import sys; sys.exit(1)"),
        ], failed="tags.txt")
        assert rc == 1
        assert (tmp_path / "tags.txt").read_text(encoding="utf-8") \
            == "fail-late\nfail-early\n"

    def test_py_word_replaced_by_interpreter(self, tmp_path, capsys):
        rc = self._gate(tmp_path, [
            _argv_seg("pyv", "import sys; print('exe=' + sys.executable)"),
        ], failed="tags.txt")
        assert rc == 0
        assert "exe=" in capsys.readouterr().out

    def test_shell_segment_gets_interpreter_via_dollar1(
            self, tmp_path, capsys):
        rc = self._gate(tmp_path, [
            {"tag": "sh", "shell": "\"$1\" -c 'print(\"sh-interp-ok\")'"},
        ], failed="tags.txt")
        assert rc == 0
        assert "sh-interp-ok" in capsys.readouterr().out

    def test_shell_pipefail_propagates_real_code(self, tmp_path):
        """管道段退出码不被 cat/tail 吞（ADR-002 缺陷类在编排器内的对应面）。"""
        rc = self._gate(tmp_path, [
            {"tag": "piped",
             "shell": "\"$1\" -c 'import sys; sys.exit(4)' | cat"},
        ], failed="tags.txt")
        assert rc == 1
        assert (tmp_path / "tags.txt").read_text(encoding="utf-8") == "piped\n"

    def test_workers_one_serializes_segments(self, tmp_path):
        m = tmp_path / "m"
        code = ("import sys,time\n"
                "p=sys.argv[1]\n"
                "open(p+'.{s}','w').write(str(time.time()))\n"
                "time.sleep(0.3)\n"
                "open(p+'.{e}','w').write(str(time.time()))\n")
        segs = [_argv_seg(t, code.format(s=f"{t}1", e=f"{t}2"), str(m))
                for t in ("wa", "wb")]
        rc = self._gate(tmp_path, segs, failed="tags.txt", workers=1)
        assert rc == 0
        # 有界=1：后段起点不早于前段终点（wa 先入槽）
        assert float((tmp_path / "m.wb1").read_text()) \
            >= float((tmp_path / "m.wa2").read_text())

    def test_workers_zero_overlaps_segments(self, tmp_path):
        m = tmp_path / "m"
        code = ("import sys,time\n"
                "p=sys.argv[1]\n"
                "open(p+'.{s}','w').write(str(time.time()))\n"
                "time.sleep(0.3)\n"
                "open(p+'.{e}','w').write(str(time.time()))\n"
                "open(p+'.done','w').write('x')\n")
        segs = [_argv_seg(t, code.format(s="start", e="end"), str(m) + t)
                for t in ("oa", "ob")]
        rc = self._gate(tmp_path, segs, failed="tags.txt")
        assert rc == 0
        # 不限并发：后段在前段睡眠窗口内已起跑（真 fan-out 契约）
        assert float((tmp_path / "mob.start").read_text()) \
            < float((tmp_path / "moa.end").read_text())

    def test_missing_cwd_fails_closed_before_spawn(self, tmp_path, capsys):
        rc = self._gate(tmp_path, [
            _argv_seg("ghost", "print('never')", cwd="no-such-dir"),
        ], failed="tags.txt")
        assert rc == 2
        assert "cwd 不存在" in capsys.readouterr().err
        assert not (tmp_path / "tags.txt").exists()   # 半跑状态零产出
        assert not list(self.tmp.glob("factory-parallel-gate.*"))

    def test_unrecognized_stack_note_deduplicated(self, tmp_path, capsys):
        rc = self._gate(tmp_path, [
            _argv_seg("p1", "pass", intra="auto", stack="phpunit"),
            _argv_seg("p2", "pass", intra="auto", stack="phpunit"),
        ], failed="tags.txt")
        assert rc == 0
        assert capsys.readouterr().out.count("phpunit 无 CLI 保守并行参数") == 1

    def test_none_cfg_and_no_config_returns_2(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(fl, "parallel_gate_cfg", lambda: None)
        rc = fl.run_parallel_gate(repo_root=tmp_path)
        assert rc == 2
        assert "未配置 parallel_gate" in capsys.readouterr().err


# ───────────────────────── CLI（main parallel-gate） ─────────────────────────

class TestParallelGateCli:
    def test_unknown_arg_rejected(self, capsys):
        assert fl.main(["factory_lib.py", "parallel-gate", "--bogus"]) == 2
        assert "未知参数" in capsys.readouterr().err

    def test_failed_tags_missing_path_rejected(self, capsys):
        assert fl.main(["factory_lib.py", "parallel-gate", "--failed-tags"]) == 2
        assert "缺路径参数" in capsys.readouterr().err

    def test_dispatch_passes_failed_tags_path(self, monkeypatch):
        seen = {}

        def fake_root(**kwargs):
            seen.update(kwargs)
            return 5

        monkeypatch.setattr(fl, "run_parallel_gate", fake_root)
        assert fl.main(["factory_lib.py", "parallel-gate", "--failed-tags", "/tmp/x"]) == 5
        assert seen == {"failed_tags_path": "/tmp/x"}

    def test_dispatch_default_no_failed_tags(self, monkeypatch):
        seen = {}

        def fake_root(**kwargs):
            seen.update(kwargs)
            return 0

        monkeypatch.setattr(fl, "run_parallel_gate", fake_root)
        assert fl.main(["factory_lib.py", "parallel-gate"]) == 0
        assert seen == {"failed_tags_path": None}
