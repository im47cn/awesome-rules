#!/usr/bin/env python3
"""taskflow — 用户业务项目内「五阶段任务工作流运行时」（三层状态 + 门禁驱动 + 可恢复）。

设计来源与本仓适配原则（docs/research/comet.md 借鉴点 #5 的本仓化落地）：
  - 状态三层：人读 taskflow.yaml / 机器 run-state.json / 追加审计 state-events.jsonl
  - 零第三方依赖（纯标准库）、零 postinstall、零网络行为
  - 阶段推进由门禁产物驱动（fail-closed）：产物缺失/校验失败即拒绝推进且不改阶段
  - 不做意图分类路由（六值意图路由与本仓二值哲学冲突，调研已否决）
  - 状态文件落在**用户业务项目**的 .taskflow/（init 生成），本仓自身不产生运行时状态
  - 阶段门禁绑定本仓 steering/ 规范引用：「规范文件存在 + 阶段产物存在」双条件校验

状态机（线性，无跳阶段）：requirements → design → implement → verify → archive
  archive 为终态：状态目录只读（不再写入任何状态文件）。

用法：
  python3 <技能目录>/scripts/taskflow.py <子命令> [选项]
  子命令：init / status / advance / verify / resume / audit
  全局选项（置于子命令之后）：--project DIR（默认当前工作目录）、--repo-root DIR
  （本仓根，用于解析内置绑定的 steering 规范；默认取脚本所在仓）

退出码：0=成功/门禁通过/三层一致；1=门禁未通过/三层不一致（含 audit 检出转移违规）；
2=运行错误（用法非法、状态文件缺失或损坏、配置非法，含 audit 检出事件行损坏）。
未知子命令与损坏状态一律 fail-closed 非零退出。`advance` 拒绝推进时零写入（三层不变）；
需要给失败的判定留痕时改用 `verify`（记录判定，不推进）。

@date 2026-09-20
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

# -- 常量 ---------------------------------------------------------------------

STAGES = ("requirements", "design", "implement", "verify", "archive")
TERMINAL = STAGES[-1]
STAGE_SEQ = " → ".join(STAGES)

STATE_DIR = ".taskflow"
YAML_NAME = "taskflow.yaml"
STATE_NAME = "run-state.json"
EVENTS_NAME = "state-events.jsonl"
STATE_SCHEMA = 1

EXIT_OK = 0
EXIT_GATE = 1
EXIT_ERROR = 2

GATE_TIMEOUT_S = 300
ARTIFACT_KINDS = ("doc", "script")
EVENT_NAMES = ("init", "advance", "gate", "resume")
TRANSITION_EVENTS = ("init", "advance")

# 内置阶段绑定（本仓 steering/ 规范）：不可由 taskflow.yaml 移除，只能追加。
# 解析顺序：先本仓根，后用户项目根；两处皆无 → 门禁判定「规范缺失」。
STAGE_SPECS = {
    "design": (
        "steering/database-design-specification.md",
        "steering/api-contract-freeze-standards.md",
    ),
    "verify": ("steering/testing-standards.md",),
}

# init 生成的默认产物声明（阶段 | 类型 | 相对项目根的路径）。
DEFAULT_ARTIFACTS = (
    ("requirements", "doc", "docs/taskflow/requirements.md"),
    ("design", "doc", "docs/taskflow/design.md"),
    ("implement", "doc", "docs/taskflow/implementation.md"),
    ("verify", "doc", "docs/taskflow/verification.md"),
)

_YAML_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+):(?:\s+(.*))?$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# 行结构守门：控制字符（含 \n\r）+ Unicode 行分隔符（U+0085/U+2028/U+2029）。
# 它们在 str.splitlines 语义下会把「单行文本」劈成多行——人读层格式破坏或审计层假损坏。
_LINE_BREAK_RE = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029]")


class TaskflowError(Exception):
    """运行错误（exit 2）：用法非法、状态缺失/损坏、配置非法。"""


# -- 时间与文件小工具 ---------------------------------------------------------


def _now() -> str:
    """本地时区 ISO8601（秒精度）。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    """同目录临时文件 + os.replace，避免半截写入。"""
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise TaskflowError(f"写入 {path} 失败：{exc}")


def _strip_quotes(value: str) -> str:
    # 双引号标量按 JSON 解码——与 _render_yaml 的标题渲染对称（json.dumps 的转义
    # 可原样读回）；非 JSON 转义时退回裸剥，兼容人工手写的引号包裹值。
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return decoded if isinstance(decoded, str) else value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


# -- yaml 子集解析（纯标准库，fail-closed） -----------------------------------
# 支持子集：顶层 `key: value` / `key:` + 2 空格缩进的块列表（`- item`）/
# `key:` + 2 空格缩进的子映射（`subkey: value`）/ `key: []` / `key: [a, b]`。
# 嵌套、混合形态、其它缩进层级、重复键一律 raise —— 配置损坏不静默猜测。


def _parse_simple_yaml(text: str, rel: str) -> dict:
    data: dict = {}
    pending = None
    pending_kind = None

    def err(lineno: int, msg: str) -> TaskflowError:
        return TaskflowError(
            f"{rel} 第 {lineno} 行：{msg}（本 CLI 只支持两级子集：顶层 `key: value`、"
            f"`key:` + 2 空格缩进的块列表或子映射；子集外语法一律拒绝）"
        )

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent not in (0, 2):
            raise err(lineno, "缩进层级非法（只允许 0 或 2 空格）")
        if indent == 2:
            if pending is None:
                raise err(lineno, "缩进行缺少所属的顶层键")
            if stripped.startswith("- "):
                if pending_kind == "map":
                    raise err(lineno, "同一顶层键下不允许混用块列表与子映射")
                pending_kind = "list"
                data[pending].append(_strip_quotes(stripped[2:].strip()))
                continue
            match = _YAML_KEY_RE.match(stripped)
            if not match or match.group(2) is None:
                raise err(lineno, "子映射行必须形如 `key: value`")
            if pending_kind == "list":
                raise err(lineno, "同一顶层键下不允许混用块列表与子映射")
            if pending_kind is None:
                data[pending] = {}
                pending_kind = "map"
            subkey = match.group(1)
            if subkey in data[pending]:
                raise err(lineno, f"重复键 {subkey!r}")
            data[pending][subkey] = _strip_quotes(match.group(2).strip())
            continue
        match = _YAML_KEY_RE.match(stripped)
        if not match:
            raise err(lineno, "顶层行必须形如 `key: value` 或 `key:`")
        key = match.group(1)
        if key in data:
            raise err(lineno, f"重复键 {key!r}")
        value = match.group(2)
        if value is None:
            data[key] = []
            pending, pending_kind = key, None
            continue
        value = value.strip()
        if value == "[]":
            data[key] = []
        elif value.startswith("[") and value.endswith("]"):
            body = value[1:-1].strip()
            data[key] = [_strip_quotes(v.strip()) for v in body.split(",") if v.strip()]
        else:
            data[key] = _strip_quotes(value)
        pending = None
    return data


# -- 三层状态读写 -------------------------------------------------------------


def _parse_relative(path: str, rel: str, where: str) -> str:
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise TaskflowError(
            f"{rel} 的 {where} 条目 {path!r} 必须是仓/项目内相对路径（禁止绝对路径与 .. 逃逸）"
        )
    return path


def _parse_specs(value, rel: str) -> dict:
    if not isinstance(value, list):
        raise TaskflowError(f"{rel} 的 specs 必须是列表（`specs:` + 块列表，或 `specs: []`）")
    out: dict = {}
    for entry in value:
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) != 2 or not all(parts):
            raise TaskflowError(f"{rel} 的 specs 条目格式非法（须为 `阶段 | 相对路径`）：{entry!r}")
        stage, path = parts
        if stage not in STAGES:
            raise TaskflowError(f"{rel} 的 specs 条目阶段非法：{stage!r}（合法值：{' / '.join(STAGES)}）")
        out.setdefault(stage, []).append(_parse_relative(path, rel, "specs"))
    return out


def _parse_artifacts(value, rel: str) -> dict:
    if not isinstance(value, list):
        raise TaskflowError(f"{rel} 的 artifacts 必须是列表（`artifacts:` + 块列表，或 `artifacts: []`）")
    out: dict = {}
    for entry in value:
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) != 3 or not all(parts):
            raise TaskflowError(
                f"{rel} 的 artifacts 条目格式非法（须为 `阶段 | 类型 | 相对路径`）：{entry!r}"
            )
        stage, kind, path = parts
        if stage not in STAGES:
            raise TaskflowError(f"{rel} 的 artifacts 条目阶段非法：{stage!r}（合法值：{' / '.join(STAGES)}）")
        if kind not in ARTIFACT_KINDS:
            raise TaskflowError(
                f"{rel} 的 artifacts 条目类型非法：{kind!r}（合法值：{' / '.join(ARTIFACT_KINDS)}）"
            )
        items = out.setdefault(stage, [])
        if any(i["kind"] == kind and i["path"] == path for i in items):
            raise TaskflowError(f"{rel} 的 artifacts 存在重复条目：{entry!r}")
        items.append({"kind": kind, "path": _parse_relative(path, rel, "artifacts")})
    return out


def _load_yaml(project: Path) -> dict:
    rel = f"{STATE_DIR}/{YAML_NAME}"
    path = project / STATE_DIR / YAML_NAME
    if not path.is_file():
        raise TaskflowError(f"缺少 {rel}（请先在本项目运行 `taskflow.py init`；项目：{project}）")
    try:
        raw = _parse_simple_yaml(path.read_text(encoding="utf-8"), rel)
    except OSError as exc:
        raise TaskflowError(f"读取 {rel} 失败：{exc}")
    unknown = sorted(set(raw) - {"task", "stage", "specs", "artifacts"})
    if unknown:
        raise TaskflowError(
            f"{rel} 存在未识别的顶层键：{'、'.join(unknown)}；本 CLI 只识别 "
            f"task / stage / specs / artifacts（拼错的键会静默使声明失效，故 fail-closed 拒绝）"
        )
    task = raw.get("task")
    if not isinstance(task, dict):
        raise TaskflowError(f"{rel} 缺少 `task:` 段（须含 id/title/created 子键）")
    for key in ("id", "title", "created"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            raise TaskflowError(f"{rel} 的 task.{key} 缺失或为空")
    stage = raw.get("stage")
    if stage not in STAGES:
        raise TaskflowError(f"{rel} 的 stage 非法：{stage!r}（合法值：{' / '.join(STAGES)}）")
    return {
        "task": task,
        "stage": stage,
        "specs": _parse_specs(raw.get("specs", []), rel),
        "artifacts": _parse_artifacts(raw.get("artifacts", []), rel),
    }


def _load_state(project: Path) -> dict:
    rel = f"{STATE_DIR}/{STATE_NAME}"
    path = project / STATE_DIR / STATE_NAME
    if not path.is_file():
        raise TaskflowError(f"缺少 {rel}（状态损坏或未初始化；项目：{project}）")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TaskflowError(f"读取 {rel} 失败：{exc}")
    except json.JSONDecodeError as exc:
        raise TaskflowError(f"{rel} 不是合法 JSON（状态损坏，拒绝继续）：{exc}")
    if not isinstance(state, dict):
        raise TaskflowError(f"{rel} 顶层必须是 JSON 对象（状态损坏）")
    if state.get("schema") != STATE_SCHEMA:
        raise TaskflowError(
            f"{rel} 的 schema={state.get('schema')!r} 不受支持（期望 {STATE_SCHEMA}）；"
            f"请使用与状态文件匹配的 taskflow 版本"
        )
    if state.get("stage") not in STAGES:
        raise TaskflowError(f"{rel} 的 stage 非法：{state.get('stage')!r}（合法值：{' / '.join(STAGES)}）")
    if not isinstance(state.get("gates"), dict):
        raise TaskflowError(f"{rel} 缺少 gates 对象（状态损坏）")
    return state


def _read_events(project: Path):
    """返回 (good, problems)：good=[(行号, 事件对象)]，problems=[损坏描述]。"""
    rel = f"{STATE_DIR}/{EVENTS_NAME}"
    path = project / STATE_DIR / EVENTS_NAME
    if not path.is_file():
        raise TaskflowError(f"缺少 {rel}（审计层缺失，无法对账；项目：{project}）")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaskflowError(f"读取 {rel} 失败：{exc}")
    good, problems = [], []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"第 {lineno} 行不是合法 JSON：{exc}")
            continue
        if not isinstance(event, dict):
            problems.append(f"第 {lineno} 行不是 JSON 对象")
            continue
        missing = [k for k in ("ts", "event", "from", "to", "detail") if k not in event]
        if missing:
            problems.append(f"第 {lineno} 行缺少字段：{'/'.join(missing)}")
            continue
        if event["event"] not in EVENT_NAMES:
            problems.append(f"第 {lineno} 行事件名未知：{event['event']!r}")
            continue
        if event["from"] not in ("",) + STAGES or event["to"] not in STAGES:
            problems.append(
                f"第 {lineno} 行 from/to 非法：{event['from']!r} → {event['to']!r}"
            )
            continue
        good.append((lineno, event))
    return good, problems


def _append_event(project: Path, event: str, frm: str, to: str, detail: str) -> None:
    rec = {"ts": _now(), "event": event, "from": frm, "to": to, "detail": detail}
    line = json.dumps(rec, ensure_ascii=False)
    # json.dumps(ensure_ascii=False) 不转义 U+0085/U+2028/U+2029，而 str.splitlines 会在
    # 这些字符处断行 → 审计层会被读成「假损坏」。改写为 \uXXXX 转义：语义等价且恒为单行。
    for ch, esc in (("\u0085", "\\u0085"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        line = line.replace(ch, esc)
    path = project / STATE_DIR / EVENTS_NAME
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        raise TaskflowError(f"追加审计事件失败（{STATE_DIR}/{EVENTS_NAME}）：{exc}")


def _write_state(project: Path, state: dict) -> None:
    _atomic_write(
        project / STATE_DIR / STATE_NAME,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def _set_yaml_stage(project: Path, stage: str) -> None:
    """同步人读层的 `stage:` 行（保留文件其余内容与注释；行不唯一即拒绝）。"""
    path = project / STATE_DIR / YAML_NAME
    rel = f"{STATE_DIR}/{YAML_NAME}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaskflowError(f"读取 {rel} 失败：{exc}")
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines) if re.match(r"^stage:\s*\S", line)]
    if len(hits) != 1:
        raise TaskflowError(f"{rel} 的顶层 `stage:` 行必须恰有一处（实际 {len(hits)} 处），无法同步人读层")
    lines[hits[0]] = f"stage: {stage}"
    _atomic_write(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


# -- 三层一致性探针与审计重放 -------------------------------------------------


def _last_transition(events) -> tuple:
    """返回 (行号, 事件) 或 (None, None)：最后一条转移事件（init/advance）。"""
    last = (None, None)
    for lineno, event in events:
        if event["event"] in TRANSITION_EVENTS:
            last = (lineno, event)
    return last


def _probe_layers(yml: dict, state: dict, events) -> dict:
    """三层一致性探针：取值对账（yaml / run-state / jsonl 末转移）+ 审计链重放合法性。"""
    yaml_stage = yml["stage"]
    state_stage = state["stage"]
    lineno, last = _last_transition(events)
    jsonl_stage = last["to"] if last else None
    problems = []
    if yaml_stage != state_stage:
        problems.append(
            f"{STATE_DIR}/{YAML_NAME} 的 stage={yaml_stage} 与 {STATE_DIR}/{STATE_NAME} 的 "
            f"stage={state_stage} 不一致"
        )
    if last is None:
        problems.append(f"{STATE_DIR}/{EVENTS_NAME} 不含任何转移事件（init/advance 皆缺）")
    elif jsonl_stage != state_stage:
        problems.append(
            f"{STATE_DIR}/{EVENTS_NAME} 第 {lineno} 行最后转移事件 to={jsonl_stage} 与 "
            f"{STATE_DIR}/{STATE_NAME} 的 stage={state_stage} 不一致"
        )
    if yml["task"]["id"] != state.get("task_id"):
        problems.append(
            f"任务身份漂移：yaml task.id={yml['task']['id']!r} 与 run-state task_id="
            f"{state.get('task_id')!r} 不一致"
        )
    _, violations, _ = _replay(events)
    if violations:
        problems.append(
            f"{STATE_DIR}/{EVENTS_NAME} 审计链存在 {len(violations)} 条转移违规"
            f"（首条：{violations[0]}）；审计层是事实源，请先 `taskflow.py audit` 复核并人工修复"
        )
    return {
        "ok": not problems,
        "yaml_stage": yaml_stage,
        "state_stage": state_stage,
        "jsonl_stage": jsonl_stage,
        "problems": problems,
    }


def _replay(events) -> tuple:
    """审计重放：线性状态机合法性校验，返回 (timeline, violations, final_stage)。"""
    timeline, violations = [], []
    cur = None
    for lineno, event in events:
        name, frm, to = event["event"], event["from"], event["to"]
        timeline.append({"line": lineno, "ts": event["ts"], "event": name, "from": frm, "to": to})
        if name == "init":
            if cur is not None:
                violations.append(f"第 {lineno} 行：init 事件重复（任务已初始化于 {cur}）")
                continue
            if frm != "" or to != STAGES[0]:
                violations.append(
                    f"第 {lineno} 行：init 事件必须 from='' to='{STAGES[0]}'，实为 "
                    f"{frm!r} → {to!r}"
                )
                continue
            cur = to
            continue
        if name == "advance":
            if cur is None:
                violations.append(f"第 {lineno} 行：advance 事件出现在 init 之前")
                continue
            if cur == TERMINAL:
                violations.append(f"第 {lineno} 行：{TERMINAL} 为终态，不得再推进")
                continue
            expected = _next_stage(cur)
            if frm != cur:
                violations.append(
                    f"第 {lineno} 行：advance 的 from={frm!r} 与重放游标 {cur!r} 不一致"
                )
                continue
            if to != expected:
                violations.append(
                    f"第 {lineno} 行：非法转移 {frm} → {to}（线性状态机要求 → {expected}）"
                )
                continue
            cur = to
            continue
        # gate / resume：不改阶段
        if frm != to:
            violations.append(f"第 {lineno} 行：{name} 事件不得改阶段（from={frm} to={to}）")
            continue
        if cur is None:
            violations.append(f"第 {lineno} 行：{name} 事件出现在 init 之前")
            continue
        if frm != cur:
            violations.append(f"第 {lineno} 行：{name} 事件的 from={frm!r} 与重放游标 {cur!r} 不一致")
    if cur is None and not violations:
        violations.append("事件流不含 init 事件（审计层不完整）")
    return timeline, violations, cur


# -- 门禁求值 -----------------------------------------------------------------


def _check_doc(path: Path) -> tuple:
    if not path.exists():
        return False, "文件不存在"
    if not path.is_file():
        return False, "不是普通文件"
    try:
        if path.stat().st_size <= 0:
            return False, "文件为空"
    except OSError as exc:
        return False, f"读取失败：{exc}"
    return True, "通过（存在且非空）"


def _run_script_gate(path: Path, project: Path) -> tuple:
    if not path.is_file():
        return False, "脚本不存在"
    if path.suffix == ".py":
        cmd = [sys.executable, str(path)]
    elif os.access(str(path), os.X_OK):
        cmd = [str(path)]
    else:
        return False, "不可执行（非 .py 且无执行权限）"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GATE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, f"执行超时（>{GATE_TIMEOUT_S}s）"
    except OSError as exc:
        return False, f"执行失败：{exc}"
    if proc.returncode == 0:
        return True, "通过（exit 0）"
    tail = " ".join((proc.stderr or proc.stdout or "").split())
    if len(tail) > 160:
        tail = tail[:160] + "…"
    return False, f"执行失败（exit {proc.returncode}）" + (f"：{tail}" if tail else "")


def _resolve_spec(repo_root: Path, project: Path, rel_path: str):
    """内置/追加规范解析：先本仓根，后用户项目根；返回命中的路径或 None。"""
    for base in (repo_root, project):
        candidate = base / rel_path
        if candidate.is_file():
            return candidate
    return None


def _eval_gate(project: Path, repo_root: Path, stage: str, artifacts, extra_specs) -> dict:
    """求值单阶段门禁：规范「文件存在」+ 产物「存在/可执行」双条件。"""
    now = _now()
    entries = [("内置", p) for p in STAGE_SPECS.get(stage, ())] + [("追加", p) for p in extra_specs]
    spec_results = []
    for origin, rel_path in entries:
        found = _resolve_spec(repo_root, project, rel_path)
        spec_results.append(
            {
                "origin": origin,
                "path": rel_path,
                "exists": found is not None,
                "resolved": str(found) if found else "",
                "detail": "已解析" if found else (
                    f"未找到（依次尝试 {repo_root / rel_path}、{project / rel_path}）"
                ),
            }
        )
    artifact_results = []
    for item in artifacts:
        target = project / item["path"]
        if item["kind"] == "doc":
            ok, detail = _check_doc(target)
        else:
            ok, detail = _run_script_gate(target, project)
        artifact_results.append(
            {
                "kind": item["kind"],
                "path": item["path"],
                "ok": ok,
                "detail": detail,
                "checked_at": now,
            }
        )
    passed = all(s["exists"] for s in spec_results) and all(a["ok"] for a in artifact_results)
    return {
        "stage": stage,
        "checked_at": now,
        "result": "pass" if passed else "fail",
        "specs": spec_results,
        "artifacts": artifact_results,
    }


def _brief(record: dict, ok: bool = False) -> str:
    if ok:
        return f"产物 {len(record['artifacts'])} 项 + 规范 {len(record['specs'])} 项全部通过"
    failures = [f"{s['path']}（{s['detail']}）" for s in record["specs"] if not s["exists"]]
    failures += [f"{a['path']}（{a['detail']}）" for a in record["artifacts"] if not a["ok"]]
    text = "；".join(failures)
    return text if len(text) <= 200 else text[:200] + "…"


# -- 公共前置 -----------------------------------------------------------------


def _project_dir(args) -> Path:
    return Path(args.project).expanduser().resolve()


def _repo_root(args) -> Path:
    if args.repo_root:
        return Path(args.repo_root).expanduser().resolve()
    # 脚本路径 <repo>/skills/<skill>/scripts/taskflow.py → 上溯三级为仓根
    return Path(__file__).resolve().parents[3]


def _next_stage(stage: str) -> str:
    return STAGES[STAGES.index(stage) + 1]


def _precheck(args) -> tuple:
    """verify/advance 公共前置：项目、三层一致、非终态、产物已声明。"""
    project = _project_dir(args)
    if not project.is_dir():
        raise TaskflowError(f"项目目录不存在：{project}")
    repo_root = _repo_root(args)
    yml = _load_yaml(project)
    state = _load_state(project)
    events, problems = _read_events(project)
    if problems:
        raise TaskflowError(
            f"{STATE_DIR}/{EVENTS_NAME} 损坏：{problems[0]}"
            f"（运行 `taskflow.py audit` 查看全量报告；修复前拒绝推进）"
        )
    probe = _probe_layers(yml, state, events)
    if not probe["ok"]:
        raise TaskflowError(
            "状态三层不一致，拒绝执行（fail-closed）：" + "；".join(probe["problems"])
            + "。请先运行 `taskflow.py resume` 获取修复指引。"
        )
    stage = state["stage"]
    if stage == TERMINAL:
        raise TaskflowError(f"任务已归档（{TERMINAL} 为终态，状态目录只读）：不再执行门禁校验或推进")
    items = yml["artifacts"].get(stage, [])
    if not items:
        raise TaskflowError(
            f"阶段 {stage} 未声明任何产物（{STATE_DIR}/{YAML_NAME} 的 artifacts:）"
            f"——门禁产物驱动要求至少一项，拒绝继续"
        )
    return project, repo_root, yml, state, stage, items


def _print_gate_report(record: dict) -> None:
    print(f"门禁判定：{'通过' if record['result'] == 'pass' else '未通过'}（阶段 {record['stage']}，{record['checked_at']}）")
    if record["specs"]:
        print("绑定规范：")
        for spec in record["specs"]:
            mark = "✅" if spec["exists"] else "❌"
            print(f"  {mark} [{spec['origin']}] {spec['path']} —— {spec['detail']}")
    else:
        print("绑定规范：本阶段无绑定（内置与追加皆空）")
    print("阶段产物：")
    for art in record["artifacts"]:
        mark = "✅" if art["ok"] else "❌"
        print(f"  {mark} [{art['kind']}] {art['path']} —— {art['detail']}")


# -- 子命令 -------------------------------------------------------------------


def cmd_init(args) -> int:
    project = _project_dir(args)
    if not project.is_dir():
        raise TaskflowError(f"项目目录不存在：{project}")
    sdir = project / STATE_DIR
    if sdir.exists():
        raise TaskflowError(
            f"已存在 {STATE_DIR}/（拒绝重复初始化以免覆盖既有状态；如需重建请先人工备份并删除"
            f"）：{sdir}"
        )
    title = (args.title or project.name).strip()
    if not title:
        raise TaskflowError("标题非法：必须是非空文本")
    if _LINE_BREAK_RE.search(title):
        raise TaskflowError(
            "标题非法：不得含控制字符或 Unicode 行分隔符（U+0085/U+2028/U+2029）——"
            "否则会破坏人读层与审计层的单行结构"
        )
    task_id = args.id or f"TF-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    if not _TASK_ID_RE.match(task_id):
        raise TaskflowError(f"任务 id 非法：{task_id!r}（只允许字母/数字/._-）")
    now = _now()
    try:
        sdir.mkdir()
    except OSError as exc:
        raise TaskflowError(f"创建 {STATE_DIR}/ 失败：{exc}（请检查项目目录权限）")
    try:
        _atomic_write(sdir / YAML_NAME, _render_yaml(task_id, title, now))
        _write_state(
            project,
            {"schema": STATE_SCHEMA, "task_id": task_id, "stage": STAGES[0], "entered_at": now, "gates": {}},
        )
        _append_event(project, "init", "", STAGES[0], f"初始化任务 {task_id}（{title}）")
    except TaskflowError as exc:
        raise TaskflowError(
            f"{exc}。初始化按「人读层 → 机器层 → 审计层」三步写入，中途失败会留下残缺 "
            f"{STATE_DIR}/；请人工核对目录内容，无法补齐时删除该目录后重新 `taskflow.py init`"
        )
    print(f"✅ 已初始化任务 {task_id}（{title}）")
    print(f"项目：{project}")
    print(f"状态目录：{STATE_DIR}/（三层：{YAML_NAME} / {STATE_NAME} / {EVENTS_NAME}）")
    print(f"当前阶段：{STAGES[0]}（{STAGE_SEQ}）")
    print("下一步：")
    print("  1) 创建本阶段产物（声明见 " + f"{STATE_DIR}/{YAML_NAME} 的 artifacts:）：")
    for item in DEFAULT_ARTIFACTS:
        if item[0] == STAGES[0]:
            print(f"     - [{item[1]}] {item[2]}")
    print("  2) `taskflow.py verify` 预检门禁，或 `taskflow.py advance` 校验通过后推进")
    return EXIT_OK


def _render_yaml(task_id: str, title: str, created: str) -> str:
    lines = [
        f"# {STATE_DIR}/{YAML_NAME} —— 人读层（任务元数据 + 绑定规范清单 + 阶段产物声明）",
        "# 本文件可人工编辑；机器层 run-state.json 与审计层 state-events.jsonl 由 CLI 写入，请勿手改。",
        "task:",
        f"  id: {task_id}",
        f"  title: {json.dumps(title, ensure_ascii=False)}",
        f"  created: {created}",
        f"# stage 由 CLI 在推进时同步写入；手工修改须与机器层/审计层同时一致（resume 校验三层）。",
        f"stage: {STAGES[0]}",
        "# 追加绑定的规范清单（格式：`- 阶段 | 相对路径`）；先按本仓根解析，其次用户项目根。",
        "# 技能内置的阶段绑定（design → 数据库设计 + API 契约冻结；verify → 测试规范）不可由此移除。",
        "specs: []",
        "# 阶段产物声明（格式：`- 阶段 | 类型 | 相对路径`）；类型 doc=存在且非空，script=exit 0。",
        "# 路径相对项目根解析；每阶段至少声明一项（否则拒绝推进）；archive 为终态，无需声明。",
        "artifacts:",
    ]
    lines += [f"  - {stage} | {kind} | {path}" for stage, kind, path in DEFAULT_ARTIFACTS]
    return "\n".join(lines) + "\n"


def _status_payload(project: Path, repo_root: Path) -> dict:
    yml = _load_yaml(project)
    state = _load_state(project)
    events, problems = _read_events(project)
    if problems:
        raise TaskflowError(
            f"{STATE_DIR}/{EVENTS_NAME} 损坏：{problems[0]}"
            f"（运行 `taskflow.py audit` 查看全量报告；修复前状态不可信）"
        )
    probe = _probe_layers(yml, state, events)
    stage = state["stage"]
    gate = state["gates"].get(stage)
    last_by_path = {}
    if isinstance(gate, dict):
        for art in gate.get("artifacts", []):
            if isinstance(art, dict):
                last_by_path[art.get("path")] = art
    artifacts = []
    for item in yml["artifacts"].get(stage, []):
        last = last_by_path.get(item["path"])
        artifacts.append(
            {
                "kind": item["kind"],
                "path": item["path"],
                "last_result": (
                    {
                        "ok": last.get("ok"),
                        "detail": last.get("detail"),
                        "checked_at": last.get("checked_at"),
                    }
                    if last
                    else None
                ),
            }
        )
    specs = []
    for origin, rel_path in [("内置", p) for p in STAGE_SPECS.get(stage, ())] + [
        ("追加", p) for p in yml["specs"].get(stage, [])
    ]:
        found = _resolve_spec(repo_root, project, rel_path)
        specs.append({"origin": origin, "path": rel_path, "exists": found is not None})
    terminal = stage == TERMINAL
    return {
        "project": str(project),
        "repo_root": str(repo_root),
        "task": yml["task"],
        "stage": stage,
        "entered_at": state.get("entered_at"),
        "stage_sequence": list(STAGES),
        "terminal": terminal,
        "consistent": probe["ok"],
        "consistency": probe,
        "artifacts": artifacts,
        "specs": specs,
        "next_commands": [] if terminal else ["taskflow.py verify", "taskflow.py advance"],
    }


def cmd_status(args) -> int:
    project = _project_dir(args)
    payload = _status_payload(project, _repo_root(args))
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK if payload["consistent"] else EXIT_GATE
    print(f"任务：{payload['task']['id']} —— {payload['task']['title']}")
    print(f"项目：{payload['project']}")
    print(f"阶段：{payload['stage']}（进入于 {payload['entered_at']}）")
    print(f"序列：{STAGE_SEQ}（{TERMINAL} 为终态只读）")
    consistency = payload["consistency"]
    if payload["consistent"]:
        print(f"三层对账：一致（yaml={consistency['yaml_stage']} state={consistency['state_stage']} jsonl={consistency['jsonl_stage']}）")
    else:
        print("三层对账：⚠ 不一致 —— " + "；".join(consistency["problems"]))
        print("  修复指引：运行 `taskflow.py resume`")
    print(f"当前阶段产物（相对项目根，共 {len(payload['artifacts'])} 项）：")
    if not payload["artifacts"]:
        print("  （未声明 —— 门禁将拒绝推进，请在 " + f"{STATE_DIR}/{YAML_NAME} 的 artifacts: 声明）")
    for art in payload["artifacts"]:
        last = art["last_result"]
        last_text = "未校验" if not last else (
            f"{'通过' if last['ok'] else '未通过'}（{last['detail']}）@{last['checked_at']}"
        )
        print(f"  - [{art['kind']}] {art['path']}    上次校验：{last_text}")
    print("绑定规范（当前阶段）：")
    if not payload["specs"]:
        print("  （本阶段无绑定规范）")
    for spec in payload["specs"]:
        print(f"  - [{spec['origin']}] {spec['path']}    {'已解析' if spec['exists'] else '未找到'}")
    if payload["terminal"]:
        print(f"下一步：无（{TERMINAL} 为终态，状态目录只读）")
    else:
        print(f"下一步：`taskflow.py verify`（预检）或 `taskflow.py advance`（推进到 {_next_stage(payload['stage'])}）")
    return EXIT_OK if payload["consistent"] else EXIT_GATE


def cmd_verify(args) -> int:
    project, repo_root, yml, state, stage, items = _precheck(args)
    record = _eval_gate(project, repo_root, stage, items, yml["specs"].get(stage, []))
    state["gates"][stage] = record
    _write_state(project, state)
    passed = record["result"] == "pass"
    if passed:
        _append_event(project, "gate", stage, stage, "门禁通过（预检，未推进）")
    else:
        _append_event(project, "gate", stage, stage, "门禁未通过（预检）：" + _brief(record))
    if args.format == "json":
        print(
            json.dumps(
                {
                    "stage": stage,
                    "passed": passed,
                    "record": record,
                    "next_commands": ["taskflow.py advance"] if passed else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_OK if passed else EXIT_GATE
    _print_gate_report(record)
    if passed:
        print(f"阶段未变（{stage}）；如需推进运行 `taskflow.py advance`")
        return EXIT_OK
    print(f"阶段未变（{stage}，fail-closed）")
    return EXIT_GATE


def cmd_advance(args) -> int:
    project, repo_root, yml, state, stage, items = _precheck(args)
    record = _eval_gate(project, repo_root, stage, items, yml["specs"].get(stage, []))
    if record["result"] != "pass":
        # fail-closed 的完整含义是「拒绝时零写入」：不写机器层、不追加事件。
        # 需要「失败的判定也留痕」时改用 verify（它记录判定与 gate 事件，但不推进）。
        _print_gate_report(record)
        print(f"❌ 拒绝推进：阶段仍为 {stage}（fail-closed，未写入任何状态文件）")
        print("本次判定未留痕；如需留痕请运行 `taskflow.py verify`（记录判定，不推进）")
        return EXIT_GATE
    nxt = _next_stage(stage)
    state["gates"][stage] = record
    state["stage"] = nxt
    state["entered_at"] = _now()
    try:
        _write_state(project, state)
        _set_yaml_stage(project, nxt)
        _append_event(project, "advance", stage, nxt, "门禁通过：" + _brief(record, ok=True))
    except (TaskflowError, OSError) as exc:
        raise TaskflowError(
            f"{exc}。推进按「机器层 → 人读层 → 审计层」三步写入，中途失败会留下三层漂移；"
            f"请运行 `taskflow.py resume` 复核并按修复指引校正"
        )
    _print_gate_report(record)
    print(f"✅ 已推进：{stage} → {nxt}（进入于 {state['entered_at']}）")
    if nxt == TERMINAL:
        print(f"{TERMINAL} 为终态：状态目录进入只读，不再接受推进/门禁写入")
    else:
        print(f"下一步：完成 {nxt} 阶段产物后运行 `taskflow.py advance`（先 `verify` 可预检）")
    return EXIT_OK


def cmd_resume(args) -> int:
    project = _project_dir(args)
    yml = _load_yaml(project)
    state = _load_state(project)
    events, problems = _read_events(project)
    if problems:
        raise TaskflowError(
            f"{STATE_DIR}/{EVENTS_NAME} 损坏，无法对账：{problems[0]}"
            f"（运行 `taskflow.py audit` 查看全量报告；修复前拒绝恢复）"
        )
    probe = _probe_layers(yml, state, events)
    payload = {
        "project": str(project),
        "consistent": probe["ok"],
        "layers": {
            "yaml": probe["yaml_stage"],
            "run_state": probe["state_stage"],
            "events_jsonl": probe["jsonl_stage"],
        },
        "problems": probe["problems"],
        "terminal": state["stage"] == TERMINAL,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not probe["ok"]:
        if args.format != "json":
            print("⚠ 三层状态不一致（拒绝继续）：")
            for problem in probe["problems"]:
                print(f"  - {problem}")
            print("各层当前值：")
            print(f"  - {STATE_DIR}/{YAML_NAME}      stage={probe['yaml_stage']}（人工可编辑层）")
            print(f"  - {STATE_DIR}/{STATE_NAME}   stage={probe['state_stage']}（机器层，请勿手改）")
            print(f"  - {STATE_DIR}/{EVENTS_NAME}  最后转移事件 to={probe['jsonl_stage']}（审计层，事实源）")
            print("修复指引（不自动改写任何层）：")
            print("  1) 先运行 `taskflow.py audit` 确认审计层转移链合法（合法即以审计层末事件为事实源）")
            print("  2) 审计层合法时：把 yaml 的 stage 与机器层的 stage 手工校正为审计层末事件值；")
            print("     仅 yaml 漂移时只改 yaml，仅机器层漂移时只改 run-state.json。")
            print("  3) 审计层本身非法（audit 报违规）时：人工确认实际阶段后，修复 jsonl 末行或备份")
            print("     全量三层状态后重建 .taskflow/（重建会丢失审计链，须在任务说明中记录）。")
            print("  4) 修复后重跑 `taskflow.py resume` 复核；一致前 verify/advance 一律被拒。")
        return EXIT_GATE
    if args.format != "json":
        if payload["terminal"]:
            print(f"任务已归档（{TERMINAL} 终态只读）：三层一致，无恢复动作；本命令不追加事件。")
        else:
            print(f"✅ 三层一致（yaml=run-state=jsonl={probe['state_stage']}），可继续：")
            print(f"  当前阶段：{probe['state_stage']}；下一步 `taskflow.py verify`（预检）或 `taskflow.py advance`（推进到 {_next_stage(probe['state_stage'])}）")
    if state["stage"] == TERMINAL:
        return EXIT_OK
    _append_event(project, "resume", state["stage"], state["stage"], "三层一致，可继续")
    return EXIT_OK


def cmd_audit(args) -> int:
    project = _project_dir(args)
    if not project.is_dir():
        raise TaskflowError(f"项目目录不存在：{project}")
    good, problems = _read_events(project)
    timeline, violations, final_stage = _replay(good)
    ok = not problems and not violations
    payload = {
        "project": str(project),
        "events": len(good),
        "final_stage": final_stage,
        "timeline": timeline,
        "problems": problems,
        "violations": violations,
        "ok": ok,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"审计重放：{'✅ 通过' if ok else '❌ 不通过'}（事件 {len(good)} 条，终态阶段 {final_stage}）")
        for item in timeline:
            print(f"  L{item['line']} {item['ts']} {item['event']}: {item['from'] or '(空)'} → {item['to']}")
        if problems:
            print("损坏行：")
            for problem in problems:
                print(f"  - {problem}")
        if violations:
            print("转移违规：")
            for violation in violations:
                print(f"  - {violation}")
    if problems:
        return EXIT_ERROR
    return EXIT_OK if not violations else EXIT_GATE


# -- 入口 ---------------------------------------------------------------------

COMMANDS = {
    "init": (cmd_init, "初始化 .taskflow/ 三层状态（拒绝重复初始化）"),
    "status": (cmd_status, "查看当前阶段、产物声明、绑定规范与三层对账"),
    "advance": (cmd_advance, "求值当前阶段门禁；通过则推进并追加事件，否则拒绝且不写任何状态（零写入）"),
    "verify": (cmd_verify, "仅求值当前阶段门禁（记录判定与 gate 事件，不推进）"),
    "resume": (cmd_resume, "三层一致性探针：一致则给出可继续指令，不一致则非零退出并给修复指引"),
    "audit": (cmd_audit, "全量重放 state-events.jsonl 校验状态机转移合法性"),
}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # noqa: D102 - argparse 覆写
        self.print_usage(sys.stderr)
        print(f"错误：参数非法 —— {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def _common_parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--project", default=argparse.SUPPRESS, help="用户业务项目根（默认当前工作目录）")
    parent.add_argument(
        "--repo-root",
        default=argparse.SUPPRESS,
        help="本仓根（解析内置绑定的 steering 规范；默认脚本所在仓）",
    )
    return parent


def _build_parser(cmd: str) -> argparse.ArgumentParser:
    parser = _Parser(prog=f"taskflow.py {cmd}", description=COMMANDS[cmd][1], parents=[_common_parent()])
    if cmd == "init":
        parser.add_argument("--title", default="", help="任务标题（缺省用项目目录名）")
        parser.add_argument("--id", default="", help="任务 id（缺省 TF-YYYYMMDD-<6位十六进制>）")
    if cmd in ("status", "verify", "resume", "audit"):
        parser.add_argument(
            "--format", choices=("text", "json"), default="text", help="输出格式（默认 text）"
        )
    return parser


def _usage() -> str:
    lines = [
        "taskflow — 五阶段任务工作流运行时（三层状态 + 门禁驱动 + 可恢复）",
        "",
        "用法：taskflow.py <子命令> [选项]",
        "",
        "子命令：",
    ]
    for name, (_, desc) in COMMANDS.items():
        lines.append(f"  {name:<8} {desc}")
    lines += [
        "",
        f"状态机：{STAGE_SEQ}（archive 为终态只读）",
        "全局选项（置于子命令之后）：--project DIR / --repo-root DIR",
        "退出码：0=成功/门禁通过/三层一致；1=门禁未通过或三层不一致（含审计链违规）；2=运行错误",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_usage())
        return EXIT_OK if argv else EXIT_ERROR
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"错误：未知子命令 {cmd!r}（合法值：{' / '.join(COMMANDS)}）", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return EXIT_ERROR
    parser = _build_parser(cmd)
    try:
        args = parser.parse_args(rest)
    except SystemExit as exc:  # argparse --help / 参数错误
        code = exc.code if isinstance(exc.code, int) else EXIT_ERROR
        return code
    if not hasattr(args, "project"):
        args.project = os.getcwd()
    if not hasattr(args, "repo_root"):
        args.repo_root = None
    if not hasattr(args, "format"):
        args.format = "text"
    handler = COMMANDS[cmd][0]
    try:
        return handler(args)
    except TaskflowError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:  # 兜底：未包装的文件系统错误也走 fail-closed 出口
        print(f"错误：文件系统操作失败 —— {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
