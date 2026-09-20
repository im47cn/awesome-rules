#!/usr/bin/env python3
"""task-flow CLI 单测：以 tmp_path 模拟用户业务项目，不落真状态、不触发网络。

覆盖：三层状态产出、门禁 fail-closed（缺产物/空产物/脚本非零/规范缺失）、状态机
线性推进与终态只读、resume 三层探针与修复指引、audit 重放违规检出、配置与状态
损坏时的非零退出。

@date 2026-09-20
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import taskflow

# 默认产物声明（与 taskflow.DEFAULT_ARTIFACTS 的路径保持一致，供测试造产物）
DEFAULT_ARTIFACTS = {
    "requirements": "docs/taskflow/requirements.md",
    "design": "docs/taskflow/design.md",
    "implement": "docs/taskflow/implementation.md",
    "verify": "docs/taskflow/verification.md",
}
BUILTIN_SPECS = (
    "database-design-specification.md",
    "api-contract-freeze-standards.md",
    "testing-standards.md",
)


# -- 夹具 ---------------------------------------------------------------------


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """模拟的用户业务项目根（空目录）。"""
    path = tmp_path / "bizproj"
    path.mkdir()
    return path


@pytest.fixture()
def spec_repo(tmp_path: Path) -> Path:
    """模拟的本仓根：内置绑定规范齐备（需缺规的测试自行删除）。"""
    root = tmp_path / "spec-repo"
    (root / "steering").mkdir(parents=True)
    for name in BUILTIN_SPECS:
        (root / "steering" / name).write_text("# 规范\n\n正文\n", encoding="utf-8")
    return root


@pytest.fixture()
def cli(project: Path, spec_repo: Path):
    """调用 CLI：`cli("advance")`；全局选项固定指向 tmp 项目与规范仓桩。"""

    def run(*argv: str) -> int:
        return taskflow.main(
            [argv[0], "--project", str(project), "--repo-root", str(spec_repo), *argv[1:]]
        )

    return run


# -- 工具 ---------------------------------------------------------------------


def sdir(project: Path) -> Path:
    return project / ".taskflow"


def state_of(project: Path) -> dict:
    return json.loads((sdir(project) / "run-state.json").read_text(encoding="utf-8"))


def yaml_text(project: Path) -> str:
    return (sdir(project) / "taskflow.yaml").read_text(encoding="utf-8")


def events_of(project: Path) -> list:
    text = (sdir(project) / "state-events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def json_of(capsys) -> dict:
    """取最近一次 `--format json` 的输出。

    同一测试里此前的命令会把人类可读输出留在缓冲区，故从末尾回溯定位
    顶层 JSON 起始行（顶层 `{` 独占一行、顶格；嵌套对象均带缩进）。
    """
    out = capsys.readouterr().out
    lines = out.splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx] == "{":
            return json.loads("\n".join(lines[idx:]))
    raise AssertionError(f"stdout 中未找到 JSON 输出：\n{out}")


def write_yaml(project: Path, text: str) -> None:
    (sdir(project) / "taskflow.yaml").write_text(text, encoding="utf-8")


def write_artifact(project: Path, rel: str, content: str = "# 产物\n\n正文\n") -> None:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_script(project: Path, rel: str, body: str) -> None:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def set_artifacts(project: Path, stage: str, entries) -> None:
    """重写 yaml 的 artifacts 块为给定条目（保留其余内容）。"""
    path = sdir(project) / "taskflow.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("artifacts:"))
    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    lines[start:end] = ["artifacts:"] + [f"  - {stage} | {kind} | {rel}" for kind, rel in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_raw_event(project: Path, event: dict) -> None:
    with open(sdir(project) / "state-events.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def advance_through(project: Path, cli, *stages: str) -> None:
    """按序造产物并推进（用于把任务推到指定阶段）。"""
    for stage in stages:
        write_artifact(project, DEFAULT_ARTIFACTS[stage])
        assert cli("advance") == 0, f"{stage} 阶段应可推进"


# -- init / 基线 --------------------------------------------------------------


def test_init_creates_three_layers(project, cli):
    assert cli("init", "--title", "示例任务") == 0
    for name in ("taskflow.yaml", "run-state.json", "state-events.jsonl"):
        assert (sdir(project) / name).is_file()
    state = state_of(project)
    assert state["stage"] == "requirements"
    assert state["gates"] == {}
    assert state["task_id"].startswith("TF-")
    assert [(e["event"], e["from"], e["to"]) for e in events_of(project)] == [
        ("init", "", "requirements")
    ]
    text = yaml_text(project)
    assert "stage: requirements" in text
    assert "示例任务" in text
    assert "docs/taskflow/requirements.md" in text


def test_init_refuses_existing_state_dir(project, cli, capsys):
    assert cli("init", "--title", "首次") == 0
    before_state, before_events = state_of(project), events_of(project)
    assert cli("init", "--title", "二次") == 2
    assert "已存在" in capsys.readouterr().err
    assert state_of(project) == before_state
    assert events_of(project) == before_events


def test_unknown_subcommand_fails_closed(project, cli, capsys):
    assert cli("explode") == 2
    err = capsys.readouterr().err
    assert "未知子命令" in err and "合法值" in err
    assert not sdir(project).exists()


def test_missing_state_dir_is_runtime_error(project, cli, capsys):
    assert cli("status") == 2
    assert capsys.readouterr().err.startswith("错误：")
    assert not sdir(project).exists()


# -- 门禁推进 -----------------------------------------------------------------


def test_advance_blocks_on_missing_artifact(project, cli, capsys):
    """fail-closed 的完整含义：拒绝推进时三层零写入。"""
    assert cli("init", "--title", "任务") == 0
    before_state, before_events = state_of(project), events_of(project)
    assert cli("advance") == 1
    out = capsys.readouterr().out
    assert "文件不存在" in out and "拒绝推进" in out and "verify" in out
    assert state_of(project) == before_state  # 机器层未写入（无失败判定留痕）
    assert "stage: requirements" in yaml_text(project)  # 人读层未改动
    assert events_of(project) == before_events  # 审计层未追加


def test_advance_failure_leaves_trace_via_verify(project, cli, capsys):
    """advance 拒绝不留痕；同一判定改走 verify 时判定与 gate 事件都落盘。"""
    assert cli("init", "--title", "任务") == 0
    assert cli("advance") == 1
    capsys.readouterr()
    assert state_of(project)["gates"] == {}
    assert cli("verify") == 1
    assert "门禁判定：未通过" in capsys.readouterr().out
    assert state_of(project)["gates"]["requirements"]["result"] == "fail"
    assert state_of(project)["stage"] == "requirements"
    last = events_of(project)[-1]
    assert (last["event"], last["from"], last["to"]) == ("gate", "requirements", "requirements")


def test_advance_passes_after_artifact_created(project, cli):
    assert cli("init", "--title", "任务") == 0
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"])
    assert cli("advance") == 0
    state = state_of(project)
    assert state["stage"] == "design"
    assert state["gates"]["requirements"]["result"] == "pass"
    assert "stage: design" in yaml_text(project)
    last = events_of(project)[-1]
    assert (last["event"], last["from"], last["to"]) == ("advance", "requirements", "design")


def test_empty_artifact_fails_gate(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"], content="")
    assert cli("advance") == 1
    assert "文件为空" in capsys.readouterr().out
    assert state_of(project)["stage"] == "requirements"


def test_script_artifact_nonzero_exit_blocks(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    write_script(project, "tools/check.py", 'import sys\nsys.stderr.write("字段缺失\\n")\nsys.exit(3)\n')
    set_artifacts(project, "requirements", [("script", "tools/check.py")])
    assert cli("advance") == 1
    out = capsys.readouterr().out
    assert "exit 3" in out and "字段缺失" in out
    assert state_of(project)["stage"] == "requirements"


def test_script_artifact_zero_exit_passes(project, cli):
    assert cli("init", "--title", "任务") == 0
    write_script(project, "tools/check.py", "import sys\nsys.exit(0)\n")
    set_artifacts(project, "requirements", [("script", "tools/check.py")])
    assert cli("advance") == 0
    assert state_of(project)["stage"] == "design"


def test_bound_spec_missing_blocks_design_advance(project, cli, spec_repo, capsys):
    assert cli("init", "--title", "任务") == 0
    advance_through(project, cli, "requirements")
    write_artifact(project, DEFAULT_ARTIFACTS["design"])
    target = spec_repo / "steering" / "database-design-specification.md"
    target.unlink()
    assert cli("advance") == 1
    out = capsys.readouterr().out
    assert "database-design-specification.md" in out and "未找到" in out
    assert state_of(project)["stage"] == "design"
    # 补回规范文件后门禁通过：证明上一步阻塞确由规范缺失引起
    target.write_text("# 规范\n", encoding="utf-8")
    assert cli("advance") == 0
    assert state_of(project)["stage"] == "implement"


def test_stage_without_declared_artifacts_refused(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    set_artifacts(project, "requirements", [])
    assert cli("advance") == 2
    assert "未声明任何产物" in capsys.readouterr().err
    assert state_of(project)["stage"] == "requirements"


def test_artifact_path_escape_refused(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    write_yaml(project, yaml_text(project).replace("docs/taskflow/requirements.md", "../evil.md"))
    assert cli("advance") == 2
    assert ".." in capsys.readouterr().err
    assert state_of(project)["stage"] == "requirements"


def test_verify_records_without_advancing(project, cli):
    assert cli("init", "--title", "任务") == 0
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"])
    assert cli("verify") == 0
    state = state_of(project)
    assert state["stage"] == "requirements"
    assert state["gates"]["requirements"]["result"] == "pass"
    assert events_of(project)[-1]["event"] == "gate"


def test_verify_failure_keeps_stage(project, cli):
    assert cli("init", "--title", "任务") == 0
    assert cli("verify") == 1
    state = state_of(project)
    assert state["stage"] == "requirements"
    assert state["gates"]["requirements"]["result"] == "fail"
    assert all(e["event"] != "advance" for e in events_of(project))


# -- 状态机终态 ---------------------------------------------------------------


def test_archive_is_terminal_readonly(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    advance_through(project, cli, "requirements", "design", "implement", "verify")
    assert state_of(project)["stage"] == "archive"
    assert "stage: archive" in yaml_text(project)
    before_state, before_events = state_of(project), events_of(project)
    assert cli("advance") == 2
    assert "终态" in capsys.readouterr().err
    assert cli("verify") == 2
    capsys.readouterr()
    assert cli("resume") == 0
    assert "无恢复动作" in capsys.readouterr().out
    assert state_of(project) == before_state
    assert events_of(project) == before_events  # 终态只读：任何命令都不写状态


# -- resume 三层探针 ----------------------------------------------------------


def test_resume_consistent_appends_event(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    assert cli("resume") == 0
    out = capsys.readouterr().out
    assert "三层一致" in out and "可继续" in out and "requirements" in out
    last = events_of(project)[-1]
    assert (last["event"], last["from"], last["to"]) == ("resume", "requirements", "requirements")


def test_resume_json_reports_layers(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    assert cli("resume", "--format", "json") == 0
    payload = json_of(capsys)
    assert payload["consistent"] is True
    assert payload["layers"] == {"yaml": "requirements", "run_state": "requirements", "events_jsonl": "requirements"}
    assert payload["terminal"] is False and payload["problems"] == []


def test_resume_detects_yaml_drift(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    write_yaml(project, yaml_text(project).replace("stage: requirements", "stage: design"))
    before = events_of(project)
    assert cli("resume") == 1
    out = capsys.readouterr().out
    assert "stage=design" in out and "stage=requirements" in out
    assert "修复指引" in out
    assert events_of(project) == before  # 不一致时不追加事件


def test_resume_detects_jsonl_drift(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    append_raw_event(
        project,
        {"ts": "2026-09-20T00:00:00+08:00", "event": "advance", "from": "requirements", "to": "design", "detail": "手工外改"},
    )
    assert cli("resume") == 1
    assert "三层状态不一致" in capsys.readouterr().out
    assert cli("resume", "--format", "json") == 1
    payload = json_of(capsys)
    assert payload["consistent"] is False
    assert any("design" in p and "requirements" in p for p in payload["problems"])


def test_advance_refuses_when_layers_drift(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"])
    write_yaml(project, yaml_text(project).replace("stage: requirements", "stage: design"))
    assert cli("advance") == 2
    err = capsys.readouterr().err
    assert "三层不一致" in err and "resume" in err
    assert state_of(project)["stage"] == "requirements"


# -- status -------------------------------------------------------------------


def test_status_json_reports_stage_artifacts_and_specs(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    assert cli("status", "--format", "json") == 0
    payload = json_of(capsys)
    assert payload["stage"] == "requirements" and payload["consistent"] is True
    assert [a["path"] for a in payload["artifacts"]] == [DEFAULT_ARTIFACTS["requirements"]]
    assert payload["artifacts"][0]["last_result"] is None
    assert payload["specs"] == []  # requirements 阶段无绑定规范


def test_status_reports_last_gate_result(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    assert cli("verify") == 1  # 失败判定的留痕走 verify（advance 拒绝时零写入）
    capsys.readouterr()
    assert cli("status", "--format", "json") == 0
    payload = json_of(capsys)
    last = payload["artifacts"][0]["last_result"]
    assert last["ok"] is False and "文件不存在" in last["detail"]


def test_status_shows_design_specs_resolved(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    advance_through(project, cli, "requirements")
    assert cli("status", "--format", "json") == 0
    payload = json_of(capsys)
    assert [s["path"] for s in payload["specs"]] == [
        "steering/database-design-specification.md",
        "steering/api-contract-freeze-standards.md",
    ]
    assert all(s["exists"] and s["origin"] == "内置" for s in payload["specs"])


def test_status_blocks_on_corrupt_run_state(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    (sdir(project) / "run-state.json").write_text("{ 不是 JSON", encoding="utf-8")
    assert cli("status") == 2
    assert "不是合法 JSON" in capsys.readouterr().err


def test_status_blocks_on_corrupt_events(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    append_raw_event(project, {"ts": "x", "event": "advance", "from": "requirements"})  # 缺字段
    assert cli("status") == 2
    err = capsys.readouterr().err
    assert "损坏" in err and "audit" in err


def test_unsupported_yaml_syntax_refused(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    write_yaml(project, yaml_text(project).replace("artifacts:\n", "artifacts:\n    - requirements | doc | x.md\n"))
    assert cli("status") == 2
    assert "缩进层级非法" in capsys.readouterr().err


# -- audit --------------------------------------------------------------------


def test_audit_passes_legal_chain(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    advance_through(project, cli, "requirements", "design")
    assert cli("audit", "--format", "json") == 0
    payload = json_of(capsys)
    assert payload["ok"] is True and payload["final_stage"] == "implement"
    assert [t["event"] for t in payload["timeline"]] == ["init", "advance", "advance"]
    assert payload["violations"] == [] and payload["problems"] == []


def test_audit_flags_illegal_transition(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    append_raw_event(
        project,
        {"ts": "2026-09-20T00:00:00+08:00", "event": "advance", "from": "requirements", "to": "implement", "detail": "跳阶段"},
    )
    assert cli("audit", "--format", "json") == 1  # 违规 = 门禁类退出码
    payload = json_of(capsys)
    assert payload["ok"] is False
    assert any("非法转移" in v and "implement" in v for v in payload["violations"])
    # 重放游标停在最后一个合法阶段
    assert payload["final_stage"] == "requirements"


def test_audit_flags_corrupt_line_with_lineno(project, cli, capsys):
    assert cli("init", "--title", "任务") == 0
    with open(sdir(project) / "state-events.jsonl", "a", encoding="utf-8") as fh:
        fh.write("这不是 JSON\n")
    assert cli("audit", "--format", "json") == 2  # 事件行损坏 = 运行错误
    payload = json_of(capsys)
    assert payload["ok"] is False
    assert any("第 2 行" in p for p in payload["problems"])


# -- 端到端冒烟（任务书验证项 2） ----------------------------------------------


def test_end_to_end_smoke_chain(project, cli, capsys):
    """init → status → advance(应失败) → 造产物 → advance → resume → audit 全链。"""
    assert cli("init", "--title", "冒烟任务") == 0
    assert cli("status") == 0
    capsys.readouterr()
    assert cli("advance") == 1  # 无产物：拒绝推进
    assert "拒绝推进" in capsys.readouterr().out
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"])
    assert cli("advance") == 0
    assert cli("resume") == 0
    capsys.readouterr()
    assert cli("audit", "--format", "json") == 0
    payload = json_of(capsys)
    assert payload["ok"] is True
    assert payload["final_stage"] == "design"
    assert state_of(project)["stage"] == "design"


# -- 输入边界与复审补充 --------------------------------------------------------


@pytest.mark.parametrize("bad", ["\r", "\x00", "\x1f", "\x7f", "\u0085", "\u2028", "\u2029"])
def test_init_rejects_control_chars_in_title(project, cli, capsys, bad):
    """标题含控制字符/Unicode 行分隔符：拒绝初始化，且不落任何状态目录。"""
    assert cli("init", "--title", f"任务{bad}尾部") == 2
    assert "控制字符" in capsys.readouterr().err
    assert not sdir(project).exists()


def test_init_rejects_illegal_task_id(project, cli, capsys):
    assert cli("init", "--title", "任务", "--id", "../evil") == 2
    assert "id 非法" in capsys.readouterr().err
    assert not sdir(project).exists()


def test_init_title_with_meta_chars_roundtrips(project, cli, capsys):
    """标题含 yaml 元字符（括号/冒号/井号/引号）：渲染与解析对称，回读逐字符一致。"""
    title = '[草稿] 订单: 重构 #1 "紧急"'
    assert cli("init", "--title", title) == 0
    capsys.readouterr()  # 清掉 init 自身的回显，避免 status 断言被前一次输出误通过
    assert cli("status") == 0
    assert title in capsys.readouterr().out


def test_yaml_unknown_top_level_key_refused(project, cli, capsys):
    """拼错的顶层键会静默使声明失效，故 fail-closed 拒绝而非忽略。"""
    assert cli("init", "--title", "任务") == 0
    write_yaml(project, yaml_text(project) + "stagesh: design\n")
    assert cli("status") == 2
    assert "未识别的顶层键" in capsys.readouterr().err


def test_absolute_artifact_path_refused(project, cli, capsys):
    """手改 yaml 把产物指向项目外：拒绝执行（防门禁校验逃逸出项目边界）。"""
    assert cli("init", "--title", "任务") == 0
    write_yaml(project, yaml_text(project).replace("docs/taskflow/requirements.md", "/tmp/evil.md"))
    assert cli("advance") == 2
    assert "绝对路径" in capsys.readouterr().err


def test_malformed_specs_entries_refused(project, cli, capsys):
    """specs 条目三类非法（字段数/阶段/路径逃逸）一律 fail-closed。"""
    assert cli("init", "--title", "任务") == 0
    base = yaml_text(project)
    for entry, needle in (
        ("  - requirements | 多余字段 | steering/x.md", "格式非法"),
        ("  - unknownstage | steering/x.md", "阶段非法"),
        ("  - requirements | ../escape.md", "逃逸"),
    ):
        write_yaml(project, base.replace("specs: []", f"specs:\n{entry}"))
        assert cli("status") == 2, entry
        assert needle in capsys.readouterr().err, entry


def test_audit_flags_gate_and_resume_cursor_violations(project, cli, capsys):
    """`gate`/`resume` 只留痕：改阶段与游标错位都必须被重放检出。"""
    assert cli("init", "--title", "任务") == 0
    append_raw_event(
        project,
        {"ts": "t1", "event": "gate", "from": "requirements", "to": "design", "detail": "改阶段"},
    )
    assert cli("audit", "--format", "json") == 1
    payload = json_of(capsys)
    assert any("不得改阶段" in v for v in payload["violations"])
    append_raw_event(
        project,
        {"ts": "t2", "event": "resume", "from": "design", "to": "design", "detail": "游标错位"},
    )
    assert cli("audit", "--format", "json") == 1
    payload = json_of(capsys)
    assert any("与重放游标" in v for v in payload["violations"])


def test_advance_blocked_by_audit_chain_violation(project, cli, capsys):
    """审计链违规进入三层探针：advance 被拒（exit 2），三层零写入。"""
    assert cli("init", "--title", "任务") == 0
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"])
    append_raw_event(
        project,
        {"ts": "t1", "event": "advance", "from": "requirements", "to": "implement", "detail": "跳阶段"},
    )
    before_state = state_of(project)
    assert cli("advance") == 2
    err = capsys.readouterr().err
    assert "审计链" in err and "resume" in err
    assert state_of(project) == before_state
    assert "stage: requirements" in yaml_text(project)


def test_status_reports_layer_inconsistency_as_gate_exit(project, cli, capsys):
    """yaml 手改成与机器层不一致：`status --format json` 以 exit 1 报不一致。"""
    assert cli("init", "--title", "任务") == 0
    write_yaml(project, yaml_text(project).replace("stage: requirements", "stage: design"))
    assert cli("status", "--format", "json") == 1
    payload = json_of(capsys)
    assert payload["consistent"] is False
    assert payload["consistency"]["problems"]


def test_verify_json_stdout_is_pure_json(project, cli, capsys):
    """`--format json` 契约：stdout 整体可被 json 解析（无前导人类可读行）。"""
    assert cli("init", "--title", "任务") == 0
    capsys.readouterr()
    assert cli("verify", "--format", "json") == 1
    out = capsys.readouterr().out
    payload = json.loads(out)  # 整体解析：任何前导文本都会使此断言失败
    assert payload["stage"] == "requirements"
    assert payload["passed"] is False
    assert payload["next_commands"] == []


def test_advance_write_failure_reports_drift_hint(project, cli, capsys, monkeypatch):
    """写入中途失败（TaskflowError 路径）：exit 2，且提示三层漂移并用 resume 复核。"""
    assert cli("init", "--title", "任务") == 0
    write_artifact(project, DEFAULT_ARTIFACTS["requirements"])

    def boom(*_args, **_kwargs):
        raise taskflow.TaskflowError("写入审计层失败（测试桩）")

    monkeypatch.setattr(taskflow, "_append_event", boom)
    capsys.readouterr()
    assert cli("advance") == 2
    err = capsys.readouterr().err
    assert "三层漂移" in err and "resume" in err
    assert state_of(project)["stage"] == "design"  # 漂移真实存在：机器层已先行落盘


def test_verify_write_failure_uses_runtime_error_exit(project, cli, capsys, monkeypatch):
    """未包装的 OSError（磁盘类故障）走 main 兜底：exit 2 + 中文错误，不抛栈。"""
    assert cli("init", "--title", "任务") == 0
    capsys.readouterr()

    def boom(*_args, **_kwargs):
        raise OSError("磁盘只读（测试桩）")

    monkeypatch.setattr(taskflow, "_write_state", boom)
    assert cli("verify") == 2
    assert "文件系统操作失败" in capsys.readouterr().err
