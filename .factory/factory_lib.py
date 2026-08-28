#!/usr/bin/env python3
"""factory_lib —— 工厂链公共逻辑（从 bash 内联 heredoc 提取，使其可单测）。

提取动机（S2 真实链暴露的三类缺陷，全部在本库固化语义并有回归测试）:
1. 解析崩溃: fence 正则捕获组 0 含 ```json 字面量 → JSONDecodeError 链死
   （2026-08-21 issue #2 首次 holdout 后链即死于此）。group(1) 语义在此固化。
2. 证据饥饿: -q 点号输出让 holdout 无法引用测试名 → 永远 FAIL。
   evidence_suites 保证触及的 skills 套件必产出 verbose 证据段。
3. 熔断判定曾藏于 dispatch.sh heredoc，无法独立验证边界（跨天/重置/上限）。
4. dispatch 进程编排（后台链/wait/并发槽/硬锁）曾为 bash 进程原语，缺陷类
   聚集（decisions.md ADR-002）；2026-08-24 下沉本文件（ADR-005）。

CLI:
  factory_lib.py parse   <logfile> <outjson> <allowed-csv>   # 解析 agent 输出 JSON
  factory_lib.py breaker <floor.json> <ledger.jsonl>         # 熔断检查（超限 exit 3）
  factory_lib.py suites  <file...>                           # 证据段套件清单
  factory_lib.py sanitize <file...>                          # 标记中和（原地写回，幂等；评论出口必经）
  factory_lib.py rejected-reconcile < issues.json            # rejected 存量对账报告（TSV）
  factory_lib.py dispatch [--dry-run] [--watch] [--interval N]  # S2 派发器（dispatch.sh shim 的实现体）
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import hosting  # 托管平台抽象层（ADR-008）：中立 schema，gh/云效差异在其内


class CircuitOpen(RuntimeError):
    """熔断打开：超日上限或连续失败上限。"""


def parse_agent_json(text: str, allowed: set[str]) -> dict:
    """从 agent stdout 提取（唯一）JSON 裁决对象。

    fence 优先（```json {...} ```），裸 JSON 贪心兜底；两者均取捕获组 1——
    组 0 含围栏字面量，loads 必炸（见模块 docstring 缺陷 1）。
    verdict 不在 allowed → ValueError（fail-closed，不让坏裁决流入链）。
    """
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("输出中未找到 JSON 对象")
    d = json.loads(m.group(1))
    verdict = d.get("verdict")
    if verdict not in allowed:
        raise ValueError(f"verdict={verdict!r} 不在 {sorted(allowed)}")
    return d


def evidence_suites(changed_files: list[str]) -> list[str]:
    """变更文件 → 需 verbose 证据段的测试套件（布局双适配，M4）。

    monorepo（backend|frontend）与 skills/<name>/scripts 两种布局都识别
    （对齐 下游生产版）；套件名与测试门 --evidence <suite> 的取值
    一一对应。不存在的套件由调用方（fix-issue.sh）的 -d 探测过滤，
    引擎不做仓假设——双布局识别让本函数零本地化（full 分发）。
    """
    suites = set()
    for f in changed_files:
        m = re.match(r"(backend|frontend)/", f)
        if m:
            suites.add(m.group(1))
            continue
        m = re.match(r"(skills/[^/]+)/", f)
        if m:
            suites.add(f"{m.group(1)}/scripts")
    return sorted(suites)


def breaker_check(floor: dict, entries: list[dict], today: str) -> None:
    """熔断判定：当日 runs 或连续失败 streak 超上限 → CircuitOpen。

    streak 跨全部历史条目（不只当日）：连续失败是状态不是流量。
    """
    runs = sum(1 for e in entries if str(e.get("ts", ""))[:10] == today)
    streak = 0
    for e in entries:
        streak = streak + 1 if e.get("exit") != 0 else 0
    if runs >= floor["max_runs_per_day"]:
        raise CircuitOpen(f"熔断：今日已跑 {runs} 次（上限 {floor['max_runs_per_day']}）")
    if streak >= floor["max_consecutive_failures"]:
        raise CircuitOpen(
            f"熔断：连续失败 {streak} 次（上限 {floor['max_consecutive_failures']}），需人工介入"
        )


def _load_ledger(path: str) -> list[dict]:
    entries = []
    ledger = Path(path)
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


# 节点预算（S3 实测校准：#2/#5 链——裁决器秒级、prime/plan/review 分钟级、
# implement 十分钟级）。env 覆盖：FACTORY_TIMEOUT_<NODE>（单节点）>
# FACTORY_TIMEOUT（全局兜底）> 下表默认。
NODE_TIMEOUTS = {
    "triage": "5m",      # 无工具裁决器，实测 ~10s
    "holdout": "5m",     # 无工具验证器，实测 ~15s
    "prime": "15m",
    "plan": "15m",
    "review": "15m",
    "pr-review": "15m",
    "implement": "30m",  # P95 未知前保守；ledger.secs 积累后按分布再调
}


def node_metric_line(node: str, t0: int, now: int, status: str) -> str:
    """节点级计时 jsonl 行（report 子命令的数据源）。

    ADR-005 缺陷驱动下沉（2026-08-27）：fix-issue.sh / validate-pr.sh 各自
    内嵌的逐字节等价 heredoc 收口至此（shell 侧仅留调用 wrapper，与
    node_timeout 同款）；渲染契约与消费端（report）同模块，drift 即测试红。
    """
    return json.dumps(
        {"node": node, "secs": int(now) - int(t0), "status": status},
        ensure_ascii=False)


def node_timeout(name: str, env: dict | None = None) -> str:
    env = env if env is not None else {}
    per_node = env.get(f"FACTORY_TIMEOUT_{name.upper().replace('-', '_')}")
    return per_node or env.get("FACTORY_TIMEOUT") or NODE_TIMEOUTS.get(name, "15m")

def classify_task(files: list[str]) -> str:
    """变更文件 → 任务类型（成本归因用；doc/code 分开统计预算分布）。

    rejected（triage 拒绝）由调用方直接写 "rejected"，不走本函数。
    规则：全 .md → doc；纯测试文件（无 md 无 src）→ test；
    md 与任何代码（含测试）并存 → mixed；其余纯代码 → code。
    """
    if not files:
        return "empty"

    def _is_test(f: str) -> bool:
        # 前端约定也算 test（源仓#69 审查）：.test.* / .spec.* / __tests__
        return ("/tests/" in f or f.startswith("tests/")
                or "/__tests__/" in f or f.startswith("__tests__/")
                or "/test_" in f or f.startswith("test_")
                or ".test." in f or ".spec." in f)

    md = [f for f in files if f.endswith((".md", ".mdx"))]
    code = [f for f in files if not f.endswith((".md", ".mdx"))]
    tests = [f for f in code if _is_test(f)]
    src = [f for f in code if not _is_test(f)]
    if not code:
        return "doc"
    if not src and not md:
        return "test"
    if md:  # md 与任何代码（含测试）并存
        return "mixed"
    return "code"


# 工厂本地化配置（M4 + 拆分前置 ADR-009）：guard.py / 链脚本 / prompts 的
# 仓特定内容（周界、判据措辞、门命令、仓库参数、上游指针）统一由
# factory-local.json 提供——本文件零本地化、跨仓 full 分发。
# fail-closed：配置缺失/损坏/缺键 → RuntimeError（调用方非零退出，禁止降级）。
def _load_local_cfg() -> dict:
    cfg_path = Path(__file__).resolve().parent / "factory-local.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("顶层不是对象")
    except Exception as exc:
        raise RuntimeError(f"factory-local.json 不可用（fail-closed）: {exc}") from exc
    return cfg


_LOCAL_CFG: dict = _load_local_cfg()


def _local_str(key: str) -> str:
    try:
        v = _LOCAL_CFG[key]
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"键 {key} 须为非空字符串")
        return v
    except Exception as exc:
        raise RuntimeError(f"factory-local.json 键 {key} 不可用（fail-closed）: {exc}") from exc


def _local_str_list(key: str) -> list[str]:
    try:
        v = _LOCAL_CFG[key]
        if not isinstance(v, list) or not v or not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError(f"键 {key} 须为非空字符串数组")
        return list(v)
    except Exception as exc:
        raise RuntimeError(f"factory-local.json 键 {key} 不可用（fail-closed）: {exc}") from exc


# 重投指引模板：键 = 未通过的 MISSION 判据（a 使命一致 / b 可判定 / c 不触周界）。
# M4 本地化外置（设计 §11.3）：措辞锚定各仓 MISSION。fail-closed：配置缺失/
# 缺键 → RuntimeError（triage 回执生成失败，链侧 issue_reject 降级为回执告警）。
def _load_reject_guidance() -> dict[str, str]:
    try:
        rg = _LOCAL_CFG["reject_guidance"]
        return {k: str(rg[k]) for k in ("a", "b", "c")}
    except Exception as exc:
        raise RuntimeError(f"factory-local.json reject_guidance 不可用: {exc}") from exc


REJECT_GUIDANCE: dict[str, str] = _load_reject_guidance()


def final_gate_cmd() -> str:
    """确定性测试门命令（整条 shell 词序列，取值见 factory-local.json）。

    ADR-009 门命令数据化：fix-issue / validate-pr / mutations 共用此配置，
    消灭三处硬编码漂移面。拆词由调用方执行——bash 侧 read -r -a 与
    mutations 侧 shlex.split 的语义分叉点有二：引号（shlex 剥除、read
    字面）与反斜杠（shlex 转义、read -r 字面——`a\\ b` 两侧词数即不同：
    2 词 vs 1 词）。故配置值**禁含引号与反斜杠**（引号 review R2-M8；
    反斜杠 ADR-010 漂移锁收口），含即 fail-closed；纯空白分隔下两拆词器
    逐词一致，两门 argv 永远相等。
    """
    v = _local_str("final_gate_cmd")
    if "'" in v or '"' in v:
        raise RuntimeError("final_gate_cmd 禁含引号（read -r -a 与 shlex 拆词一致性）")
    if "\\" in v:
        raise RuntimeError("final_gate_cmd 禁含反斜杠（shlex 转义与 read -r 字面语义分叉，ADR-010）")
    return v


def repo_vars_text() -> str:
    """拼进工作节点 prompt 的「仓库参数」段（prompts 零宿主专名的注入面）。

    run_node / pr-review / feedback-adapt 拼装 prompt 时追加本段；triage 与
    holdout 是物理隔离节点（无工具），不注入——其输入（MISSION/tests-output）
    已由链脚本内联。
    """
    lines = [
        "——仓库参数（本仓工厂本地化配置，prompt 正文不重复这些值）——",
        f"- 仓库身份: {_local_str('repo_identity')}",
        f"- 阅读范围（研究/评审自由阅读）: {'、'.join(_local_str_list('reading_scopes'))}",
        f"- 审查依据目录: {_local_str('review_basis')}",
        f"- final_gate 命令: {final_gate_cmd()}",
    ]
    if "pr_review_skills" in _LOCAL_CFG:
        # 键存在即严格校验（与 local-list 同规）：值损坏 fail-closed；
        # 键缺失 = 本仓无守卫技能面（如纯后端仓），合法省略该行。
        skills = _local_str_list("pr_review_skills")
        lines.append(f"- 守卫技能（PR 评审选配面）: {'、'.join(skills)}")
    return "\n".join(lines)


def neutralize_marker(text: str) -> str:
    """破坏文本中的裸标记子串（issue 评论出口的统一防注入）。

    链产正文（回执 reasons、未来任何 LLM 产物）可能从 issue 评论回显
    `[factory:rejected]`（用户以标记表达异议）。state.py 对 issue 评论做
    子串扫描，链评论原样携带即被识别为人工覆盖 → 永久钉死 rejected。
    本函数是**评论出口**（fix-issue.sh issue_comment → sanitize）的唯一
    中和点，渲染器不各自记得。去括号保留语义；循环替换防 `[[...]]`
    嵌套构造替换一次后重组出标记。
    """
    while "[factory:rejected]" in text:
        text = text.replace("[factory:rejected]", "factory:rejected")
    return text

def rejected_reconcile(issues: list[dict]) -> list[dict]:
    """open+factory:rejected issue → 人工处置活动对账（纯函数）。

    闭环缺口（2026-08-23 审计实证）：4 个 rejected issue 的修复已由人工
    feedback PR 吸收进 main，但 issue 仍 open 挂 rejected——链的 reject
    语义是"不修"，reject→人工路径有效但没有回写闭环，"已修未关"只能靠
    人工审计发现。本函数不判定"是否已修复"（语义判断，机器不可判定），
    只暴露处置信号：reject 回执之后的人工评论数（bot 回执标题为界）。
    有后续人工评论 = 大概率已处置，提示复核关闭；零评论 = 静默滞留。
    输出仅报告（dispatch 每轮尾部 echo），不动作——铁律 4：零 LLM 纯 bash
    调用，关闭决策永远归人类。
    """
    out = []
    for it in issues:
        comments = [c for c in (it.get("comments") or [])
                    if isinstance(c, dict)]
        bot_idx = [i for i, c in enumerate(comments)
                   if "工厂 triage 裁决：reject" in str(c.get("body") or "")]
        after = comments[(max(bot_idx) + 1):] if bot_idx else comments
        # 人工评论 = 有 author 且非 [bot] 后缀（GitHub bot 通用标识）且
        # 非链回执；缺 author 的畸形条目不计（报告宁少勿多）
        human = [c for c in after
                 if str(c.get("author") or "") and not str(c.get("author")).endswith("[bot]")
                 and "工厂 triage 裁决" not in str(c.get("body") or "")]
        out.append({
            "number": it.get("number"),
            "title": str(it.get("title") or "")[:60],
            "human_comments_after_reject": len(human),
        })
    return out


RECEIPT_CLOSURE_NOTE = (
    "> 处置协议：走人工 PR 修复本 issue 时，PR 描述请带 `Closes #<编号>`"
    "——合并即自动关闭，避免「已修未关」滞留（reject→人工路径的闭环盲区）。"
)


def reject_receipt(triage: dict) -> str:
    """triage 裁决（reject）→ 拒绝回执 markdown（五段式：结论/依据/指引/关联/边界）。

    确定性渲染，零 LLM（链脚本纪律，铁律 4 同源）。安全不变量不在本函数：
    标记中和统一在评论出口（issue_comment → factory_lib sanitize）执行，
    渲染器管内容、出口管安全——本函数原样渲染 reasons（可能含标记）。
    rejected 的机器状态由标签承载，人类审计由回执承载；标记评论通道
    保留给人类手动覆盖（人写人删，state.py 语义）。
    """
    raw = triage.get("reasons")
    reasons = raw if isinstance(raw, list) else []  # 标量/缺失 → 空，不抛 TypeError
    lines = [
        "## 工厂 triage 裁决：reject",
        "",
        "**结论**：未通过 [MISSION.md](../blob/main/MISSION.md)「Triage 判据」，链已终止，issue 落标 factory:rejected。",
        "",
        "**依据**（物理隔离 triage 节点产出，逐条判据）：",
    ]
    lines += [f"- {r}" for r in reasons] or ["- （裁决器未给出判据明细）"]

    failed: set[str] = set()
    for r in reasons:
        if not isinstance(r, str):  # LLM 偶发非字符串元素：跳过匹配，
            continue                # 不让回执阶段崩掉整条链的评论
        m = re.match(r"^判据([abc])[:：]", r)
        if m and ("不通过" in r or "存疑" in r):
            failed.add(m.group(1))
    lines += ["", "**重投指引**：不同意裁决可补充上下文后重开，下一轮 triage 全新评估。针对未通过判据："]
    lines += [f"- {REJECT_GUIDANCE[k]}" for k in sorted(failed)] or [
        "- 对照 MISSION.md「Triage 判据」逐条补足 issue 上下文。"
    ]

    lines += [
        "",
        "── 关联 ──",
        "  未识别出因果相关模块——triage 节点 --no-tools 无仓库事实核对能力，",
        "  且拒绝裁决不产生代码变更，无下游影响面；重投协议见 .factory/README.md。",
        "",
        "── 证据边界 ──",
        "  已验证: 判据核对——triage 节点（--no-tools 物理隔离，输入仅 MISSION 全文 + issue 标题正文）",
        "  未覆盖: 仓库事实核对（裁决器无工具权限，不做代码 / 数据检索；重投前请补足具体事实）",
        "  置信度: 二值裁决基于 issue 文本与 MISSION 判据核对，无运行时验证",
        "",
        RECEIPT_CLOSURE_NOTE,
        "",
    ]
    return "\n".join(lines)

# ═════════════════════════════════════════════════════════════════════
# dispatch 进程编排（2026-08-24 自 dispatch.sh 下沉，decisions.md ADR-005）
#
# 动机：ADR-002 记账的缺陷类——jobs 表/wait 落空（0d947f60）、管道吞码
# （61c119c2）、管道早退（a4d81930）、trap 吞错（c749ac5e）——全部是
# bash 进程原语的边角语义。子进程句柄收敛到本模块后，该类缺陷
# 在结构上不可表达：Popen 对象即作业表，poll 即收割，returncode 可观测。
# dispatch.sh 退为入口 shim，CLI/env/退出码契约逐项等价。
# ═════════════════════════════════════════════════════════════════════


class ChainPool:
    """链并发槽：spawn 占槽（满则阻塞让位），wait_all 收割全部。

    bash 时代的「后台链不进 job 表致 wait 落空」（0d947f60）与
    `jobs -rp | wc -l` 竞态清点在此结构性消灭。
    """

    def __init__(self, factory: Path, max_parallel: int, poll_secs: float = 5.0):
        # 防御性校验（PR #53 审查②）：0/负并发使 spawn 的槽满等待永久为真，
        # 调度挂起而非配置错误——直接拒绝构造。
        if max_parallel < 1:
            raise ValueError(
                f"max_parallel 须为正整数（得到 {max_parallel}）——0/负值使并发槽永久等待")
        self.factory = factory
        self.max_parallel = max_parallel
        self.poll_secs = poll_secs
        self._active: list[tuple[int, subprocess.Popen]] = []
        self.done: list[tuple[int, int]] = []  # (issue, returncode) 收割记录

    def _reap(self) -> None:
        for n, p in self._active:
            if p.poll() is not None:
                self.done.append((n, p.returncode))
        self._active = [(n, p) for n, p in self._active if p.poll() is None]

    def spawn(self, issue: int) -> None:
        """占并发槽运行链。FACTORY_DISPATCHED=1：链知道锁已由父持有，
        S1 手动互斥锁免获取（防自锁）。日志尾追 artifacts/issue-N/dispatch.log，
        父目录先建——bash `>>` 对缺目录静默死链是既证缺陷形态。"""
        log_dir = self.factory / "artifacts" / f"issue-{issue}"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = open(log_dir / "dispatch.log", "ab")
        try:
            proc = subprocess.Popen(
                ["bash", str(self.factory / "fix-issue.sh"), str(issue)],
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "FACTORY_DISPATCHED": "1"})
        finally:
            log.close()
        self._active.append((issue, proc))
        while len(self._active) >= self.max_parallel:  # 槽满让位（对齐 bash 轮询节奏）
            time.sleep(self.poll_secs)
            self._reap()

    def wait_all(self) -> None:
        while True:
            self._reap()
            if not self._active:
                return
            time.sleep(self.poll_secs)

    def shutdown(self, grace: float = 10.0) -> list[int]:
        """终止并收割活跃链（TERM/HUP 出口的对应物，PR #53 审查④）。

        孤儿链会在锁释放后与新 dispatcher 并发，故必须先收尸再放锁：
        先全体 SIGTERM，限期内收割，逾期 SIGKILL 兜底。返回未在限期内
        自行退出的 issue 号列表（尽力语义，正常路径 wait_all 后为空）。
        """
        for _n, p in self._active:
            if p.poll() is None:
                p.terminate()
        deadline = time.monotonic() + grace
        while self._active and time.monotonic() < deadline:
            self._reap()
            if self._active:
                time.sleep(self.poll_secs)
        stuck: list[int] = []
        for n, p in self._active:
            try:
                p.kill()
                p.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            stuck.append(n)
        self._active = []
        return stuck


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 进程存在但非属主；bash kill -0 同样 EPERM 却按死接管——此处取 POSIX 正确语义
    except ValueError:
        return False  # 垃圾 pid：kill -0 报错，bash 语义按死处理


def acquire_dispatch_lock(lock_dir: Path, pid: int) -> bool:
    """双实例硬锁：mkdir 原子占锁 + PID 活性检测（macOS 无 flock(1)）。

    锁挂主树 .factory（调用方以 git-common-dir 锚定，39b6b8ec：worktree
    隔离后各树 locks/ 互不可见，锁随树走会绕开互斥）；父目录预建——父缺
    ENOENT 会被误读为「另一 dispatcher 运行中」（源仓 PR#79）。
    cron 重叠是常态：忙时返回 False，调用方 exit 0。
    """
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_dir.mkdir()
    except FileExistsError:
        old = ""
        try:
            old = (lock_dir / "pid").read_text(encoding="ascii").strip()
        except (OSError, ValueError):
            pass
        alive = False
        if old:
            try:
                alive = _pid_alive(int(old))
            except ValueError:
                alive = False
        if old and not alive:
            print(f"锁持有者 pid={old} 已死，接管陈锁", file=sys.stderr)
            shutil.rmtree(lock_dir, ignore_errors=True)
            try:
                lock_dir.mkdir()
            except FileExistsError:
                print("另一 dispatcher 运行中，退出", file=sys.stderr)
                return False
        else:
            print(f"另一 dispatcher 运行中（pid={old}），退出", file=sys.stderr)
            return False
    (lock_dir / "pid").write_text(str(pid), encoding="ascii")
    return True


def release_dispatch_lock(lock_dir: Path) -> None:
    """放锁（幂等）。bash EXIT trap 的对应物；TERM/HUP 处理器转 SystemExit
    保证 finally 路径执行。"""
    shutil.rmtree(lock_dir, ignore_errors=True)


# （slug 解析已迁 hosting.py——平台选择逻辑归抽象层，ADR-008）


_PRIORITY_RANK = {"priority:critical": 0, "priority:high": 1,
                  "priority:medium": 2, "priority:low": 3}


def sort_by_priority(issues: list[dict]) -> list[int]:
    """accepted issue 号按 priority:* 排序（critical>high>medium>low；
    无 priority 垫底，同 rank 按号升序）。labels 为中立 [str]。"""
    rows = sorted(
        (min((_PRIORITY_RANK.get(l, 9) for l in i["labels"]), default=9),
         i["number"])
        for i in issues)
    return [n for _, n in rows]


def approved_prs(prs: list[dict]) -> list[tuple[int, bool]]:
    """open+factory:approved PR → (number, mergeable)，中立 review 字段。"""
    return [(int(p["number"]), bool(p["mergeable"])) for p in prs
            if p["review"] == "approved"]


class _DispatchCfg:
    def __init__(self, factory: Path, main_factory: Path, adapter, dry: bool):
        self.factory = factory
        self.main_factory = main_factory
        self.adapter = adapter  # hosting 适配器实例（ADR-008）
        self.dry = dry
        self.max_parallel = int(os.environ.get("MAX_PARALLEL") or 4)
        self.merge_method = os.environ.get("FACTORY_MERGE_METHOD") or "merge"
        # auto-merge 受 A5 门控：FACTORY_AUTO_MERGE=1 且 metrics/auto-merge-unlocked
        # 存在（mutations kill-rate ≥80% 前不得开启——「未证明的门不是门」）
        self.auto_merge = (os.environ.get("FACTORY_AUTO_MERGE") == "1"
                           and (factory / "metrics" / "auto-merge-unlocked").is_file())
        self.pool = ChainPool(factory, self.max_parallel)

    def say(self, msg: str) -> None:
        print(("  [dry-run] " if self.dry else "  ") + msg)


def _hosting_json(cfg: _DispatchCfg, what: str, fn):
    """hosting 查询；瞬断/输出异常 → 可诊断跳过该批（对齐 triage 批次
    c22130df 的降级形态：失败可见，不静默也不炸轮）。"""
    try:
        return fn()
    except hosting.HostingError as e:
        # 失败必须有痕（PR #53 审查⑤）：平台故障/权限失败若无告警，
        # 空队列会被当成「无事可做」，整轮静默空转还报成功。
        print(f"  [warn] hosting {what} 失败（{e}），跳过该批"
              "——若是持续故障请检查平台凭据/网络", file=sys.stderr)
        return []


def _claim(cfg: _DispatchCfg, n: int) -> bool:
    """消费 accepted → in-progress（幂等重试 ×2，add+remove 单请求——
    GitHub 换标签非 CAS，见 README「S2 落地记录」1；ADR-008 起走 hosting）。"""
    if cfg.dry:
        cfg.say(f"claim issue #{n}: accepted → in-progress")
        return True
    for _ in range(2):
        try:
            cfg.adapter.issue_set_labels(
                n, add=["factory:in-progress"], remove=["factory:accepted"])
            return True
        except hosting.HostingError:
            continue
    print(f"  claim #{n} 失败（并发或权限），跳过", file=sys.stderr)
    return False


def _pr_link_issue(cfg: _DispatchCfg, pr_number: int) -> str:
    """PR body → 关联 issue 号（Closes #N 解析权威在 state.py link）。"""
    try:
        body = cfg.adapter.pr_view(pr_number)["body"]
    except hosting.HostingError:
        return ""
    r = subprocess.run([sys.executable, str(cfg.factory / "state.py"),
                        "link", "/dev/stdin"],
                       input=json.dumps({"body": body}), capture_output=True,
                       text=True)
    return r.stdout.strip()


def _issue_in_progress(cfg: _DispatchCfg, n: int) -> bool:
    """D4（2026-08-21 双派实证）：平台 label 过滤是「含有」非「仅有」，
    accepted+in-progress 双标签条目仍在队列，必须显式跳过在跑的。"""
    try:
        return "factory:in-progress" in cfg.adapter.issue_labels(n)
    except hosting.HostingError:
        return False


def dispatch_round(cfg: _DispatchCfg) -> int:
    """单轮：breaker 门 → sync → triage 批次 → PR 结果 → needs-fix 重派 →
    accepted 队列 → 等链收尾 sync → rejected 对账 → M2 上游同步检查。
    唯一非零返回 = 熔断/门故障透传码（watch 循环据此一并停摆）。"""
    print(f"=== dispatch @ {datetime.datetime.now():%H:%M:%S} ===")
    # R4 成本熔断：每轮派发前检查（DRY 干跑无副作用不检查）。透传 breaker.sh
    # 退出码（3=熔断；1=floor 缺失/损坏 fail-closed）。锁路径对齐硬锁：
    # git-common-dir 锚定主树，worktree 内启动也能读到主台账。
    if not cfg.dry:
        rc = subprocess.run(["bash", str(cfg.factory / "breaker.sh"),
                             str(cfg.main_factory / "locks")]).returncode
        if rc != 0:
            return rc
    cfg.say("sync: factory-state.sh sync --all")
    if not cfg.dry:
        subprocess.run(["bash", str(cfg.factory / "factory-state.sh"),
                        "sync", "--all"])

    print("-- triage 批次（零标签 issue 裁决；失败不阻断派发） --")
    if cfg.dry:
        cfg.say("triage-batch: 零 factory 标签 issue，≤MAX_TRIAGE 个")
    else:
        rc = subprocess.run(["bash", str(cfg.factory / "triage-batch.sh")]).returncode
        print(f"-- triage 批次结束（exit={rc}） --")

    print("-- PR 结果处理（优先） --")
    # approved：sync 已打好标签；此处只做 A5 门内的 merge 动作
    for num, mergeable in approved_prs(_hosting_json(
            cfg, "pr list(approved)",
            lambda: cfg.adapter.pr_list(state="open", label="factory:approved",
                                        limit=50))):
        if cfg.auto_merge and mergeable is True:
            try:
                cfg.adapter.pr_merge(num, method=cfg.merge_method)
                print(f"  PR #{num} 已合并；issue 由平台自动关闭")
            except hosting.HostingError as e:
                print(f"  [warn] PR #{num} merge 失败: {e}", file=sys.stderr)
        else:
            print(f"  PR #{num} approved 但 A5 门未开（FACTORY_AUTO_MERGE + metrics/auto-merge-unlocked）→ 人工合并")

    print("-- needs-fix 重派（计数契约：claim 时移除 needs-fix） --")
    # 计数契约：重派必须 remove factory:needs-fix——label 事件只在添加时
    # 触发，标签滞留则 state.py 轮次计数冻结（test_state.py 有边界测试）
    for pr in _hosting_json(cfg, "pr list(needs-fix)",
                            lambda: cfg.adapter.pr_list(
                                state="open", label="factory:needs-fix",
                                limit=50)):
        p = pr["number"]
        n = _pr_link_issue(cfg, p)
        if not n:
            print(f"  PR #{p} 无关联 issue（body 缺 Closes #N），跳过", file=sys.stderr)
            continue
        if _issue_in_progress(cfg, int(n)):
            print(f"  issue #{n} 已 in-progress，跳过")
            continue
        cfg.say(f"PR #{p} → issue #{n} 重派（remove needs-fix 保计数活性）")
        if not cfg.dry:
            try:
                cfg.adapter.pr_set_labels(p, remove=["factory:needs-fix"])
            except hosting.HostingError as e:
                print(f"  [warn] PR #{p} 移除 needs-fix 失败: {e}", file=sys.stderr)
                continue
        if _claim(cfg, int(n)):
            cfg.pool.spawn(int(n))

    print(f"-- accepted 队列（priority 排序，并发 ≤{cfg.max_parallel}） --")
    for n in sort_by_priority(_hosting_json(
            cfg, "issue list(accepted)",
            lambda: cfg.adapter.issue_list(state="open", label="factory:accepted",
                                           limit=100))):
        if _issue_in_progress(cfg, n):
            print(f"  issue #{n} 已 in-progress，跳过")
            continue
        if _claim(cfg, n):
            cfg.say(f"issue #{n} → 链")
            cfg.pool.spawn(n)

    if not cfg.dry:
        cfg.pool.wait_all()
        print("本轮链全部结束，收尾 sync")
        subprocess.run(["bash", str(cfg.factory / "factory-state.sh"),
                        "sync", "--all"])

    # ── rejected 存量对账（reject→人工闭环缺口，2026-08-23 审计）───────
    # 只报告不动作（铁律 4）：有 reject 后人工评论的 → 提示复核关闭；
    # 零评论的 → 静默滞留计数。关闭决策永远归人类。
    for r in rejected_reconcile(_hosting_json(
            cfg, "issue list(rejected)",
            lambda: cfg.adapter.issue_list(state="open", label="factory:rejected",
                                           limit=100, comments=True))):
        c, t = r["human_comments_after_reject"], r["title"]
        if c > 0:
            print(f"  [rejected] #{r['number']} 裁决后有 {c} 条人工评论——已处置？复核关闭（{t}）")
        else:
            print(f"  [rejected] #{r['number']} 静默滞留（无后续人工评论，{t}）")

    # ── M2 上游同步检查（设计 §11.2）：零 LLM、不占 R4 预算 ─────────────
    # 不复用 fix-issue 链（guard PERIMETER 含 .factory/，链按设计拦工具链
    # 自变更）；exit 0 = 同步已推进 → 当轮即止（自我指涉护栏：后续派发仍跑
    # 内存旧脚本，下一轮生效）；1/2/3 不阻断本轮派发。
    check = cfg.factory / "upstream-sync-check.sh"
    if os.access(check, os.X_OK) and (cfg.factory / "upstream-lock.json").is_file():
        if subprocess.run(["bash", str(check)]).returncode == 0:
            print("上游同步已推进，本轮派发即止（下轮生效）")
            return 0
        print("（upstream-sync 未推进，继续本轮派发）")
    return 0


def dispatch_main(args: list[str]) -> int:
    """dispatch.sh shim 的实现体。CLI/env 契约与 bash 版逐项等价：
    --dry-run（DRY=1 同义，2026-08-21 事故教训：两者都认）/ --watch /
    --interval N（INTERVAL 环境变量同义，默认 300s：链首 triage 批次 30s
    级、全链分钟级，30min 轮询让新 issue 平均等 15min）。"""
    watch = False
    interval = float(os.environ.get("INTERVAL") or 300)
    dry = os.environ.get("DRY", "0") == "1"
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry = True
        elif a == "--watch":
            watch = True
        elif a == "--interval" and i + 1 < len(args):
            interval = float(args[i + 1])
            i += 1
        i += 1
    # MAX_PARALLEL 配置错误 fail-fast（PR #53 审查②）：0/负/非整数值会让
    # ChainPool 槽满等待永久为真——挂起而非报错。config-error = 退出码 2。
    # 前置于 git/gh/slug 环境探测：纯 env 校验与仓库环境无关，配置错误
    # 的报错不应被 slug 解析失败遮蔽（测试环境无 github remote 时先红错处）。
    mp_raw = os.environ.get("MAX_PARALLEL") or "4"
    try:
        int(mp_raw)
    except ValueError:
        print(f"MAX_PARALLEL 非整数: {mp_raw!r}", file=sys.stderr)
        return 2
    if int(mp_raw) < 1:
        print(f"MAX_PARALLEL 须为正整数（得到 {mp_raw!r}）", file=sys.stderr)
        return 2

    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("不在 git 仓库", file=sys.stderr)
        return 2
    repo = Path(r.stdout.strip())
    factory = repo / ".factory"
    try:
        adapter = hosting.current_adapter(repo)
    except hosting.HostingError as e:
        print(f"托管平台配置错误: {e}", file=sys.stderr)
        return 2
    if adapter.name == "github" and not adapter.slug():
        print("无法确定 GitHub 仓库 slug", file=sys.stderr)
        return 2
    if not adapter.auth_ok():
        print("托管平台不可用（hosting auth：gh 凭据或云效令牌）", file=sys.stderr)
        return 2
    # 主树锚定：git-common-dir 在 worktree 中指向主 .git，据此回到主树
    # .factory（39b6b8ec 硬锁语义）；非 git 环境退回 CWD 仓 .factory
    g = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                        "--git-common-dir"], capture_output=True, text=True)
    main_factory = factory
    if g.returncode == 0 and g.stdout.strip():
        main_factory = Path(g.stdout.strip().removesuffix("/.git")) / ".factory"

    cfg = _DispatchCfg(factory, main_factory, adapter, dry)
    lock_dir = main_factory / "locks" / "dispatcher"
    if not acquire_dispatch_lock(lock_dir, os.getpid()):
        return 0  # cron 重叠是常态非错误（bash: acquire_lock || exit 0）
    for sig in (signal.SIGTERM, signal.SIGHUP):
        # EXIT trap 对应物：TERM/HUP → SystemExit 走 finally 放锁
        signal.signal(sig, lambda s, _f: sys.exit(128 + int(s)))
    try:
        if watch:
            while True:
                rc = dispatch_round(cfg)
                if rc != 0:
                    return rc  # 熔断/门故障：watch 一并停摆（bash exit $? 语义）
                time.sleep(interval)
        rc = dispatch_round(cfg)
        if not cfg.dry:
            print("提示: --watch 常驻（或 cron */30 调用单轮）")
        return rc
    finally:
        # 先收尸再放锁（PR #53 审查④）：孤儿链在锁释放后仍跑，会与新
        # dispatcher 并发；TERM/HUP → SystemExit 走到此，正常路径此处
        # 已被 wait_all 收空，shutdown 为空操作。
        stuck = cfg.pool.shutdown()
        if stuck:
            print(f"  [warn] {len(stuck)} 条链未限期退出已 SIGKILL: {stuck}",
                  file=sys.stderr)
        release_dispatch_lock(lock_dir)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "dispatch":
        # dispatch [--dry-run] [--watch] [--interval N] —— S2 派发器
        return dispatch_main(argv[2:])
    if cmd == "classify":
        print(classify_task(argv[2:]))
        return 0
    if cmd == "timeout":
        print(node_timeout(argv[2]))
        return 0
    if cmd == "receipt":
        # receipt <triage.json> —— 拒绝回执 markdown（确定性模板，零 LLM）
        print(reject_receipt(json.loads(Path(argv[2]).read_text(encoding="utf-8"))))
        return 0
    if cmd == "rejected-reconcile":
        # rejected-reconcile < issues.json —— dispatch 尾部对账报告（TSV:
        # number \t human_comments \t title）。见 rejected_reconcile
        for r in rejected_reconcile(json.load(sys.stdin)):
            print(f"{r['number']}\t{r['human_comments_after_reject']}\t{r['title']}")
        return 0
    if cmd == "sanitize":
        # sanitize <file>... —— 评论出口标记中和：原地写回（无变化则跳过，
        # 幂等）。issue_comment 发送前必经；详见 neutralize_marker
        for p in argv[2:]:
            path = Path(p)
            text = path.read_text(encoding="utf-8")
            fixed = neutralize_marker(text)
            if fixed != text:
                path.write_text(fixed, encoding="utf-8")
        return 0
    if cmd == "parse":
        # parse <logfile> <outjson> <allowed-csv>
        text = Path(argv[2]).read_text(encoding="utf-8")
        d = parse_agent_json(text, set(argv[4].split(",")))
        Path(argv[3]).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    if cmd == "breaker":
        floor = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        entries = _load_ledger(argv[3])
        try:
            breaker_check(floor, entries, datetime.date.today().isoformat())
        except CircuitOpen as exc:
            print(exc, file=sys.stderr)
            return 3
        return 0
    if cmd == "report":
        # report <node-metrics.jsonl...>：P50/P95/预算建议（数据源=每链 node-metrics.jsonl）
        rows = []
        for f in argv[2:]:
            rows += _load_ledger(f)
        by_node: dict[str, list[int]] = {}
        for e in rows:
            if e.get("status") == "ok":
                by_node.setdefault(e["node"], []).append(int(e["secs"]))
        if not by_node:
            print("尚无成功样本"); return 0
        def pct(xs, q):
            xs = sorted(xs); i = max(0, min(len(xs) - 1, round(q * (len(xs) - 1))))
            return xs[i]
        for node in sorted(by_node):
            xs = by_node[node]
            cur = NODE_TIMEOUTS.get(node, "15m")
            p95 = pct(xs, 0.95)
            suggest = max(5, int(p95 / 60) + 2)  # P95 分钟 + 2 分钟余量，下限 5m
            print(f"{node:10s} n={len(xs):2d}  p50={pct(xs,0.5):5d}s  p95={p95:5d}s  预算={cur}  建议≤{suggest}m")
        return 0
    if cmd == "suites":
        for s in evidence_suites(argv[2:]):
            print(s)
        return 0
    if cmd == "final-gate":
        # final-gate —— 确定性测试门命令（ADR-009 数据化；链脚本 read -ra 拆词执行）
        print(final_gate_cmd())
        return 0
    if cmd == "local-str":
        # local-str <key> —— 单字符串键输出（feedback-upstream 上游指针等；ADR-009）
        print(_local_str(argv[2]))
        return 0
    if cmd == "metric":
        # metric <node> <t0> <status> —— 节点计时 jsonl 行（shell wrapper 消费）
        print(node_metric_line(argv[2], int(argv[3]), int(time.time()), argv[4]))
        return 0
    if cmd == "local-list":
        # local-list <key> —— 字符串数组键逐行输出（shell for 消费；ADR-009）
        for v in _local_str_list(argv[2]):
            print(v)
        return 0
    if cmd == "repo-vars":
        # repo-vars —— prompt 仓库参数段（run_node / pr-review / adapt 注入）
        print(repo_vars_text())
        return 0
    print(f"未知子命令: {cmd}", file=sys.stderr)
    return 2
if __name__ == "__main__":
    sys.exit(main(sys.argv))
