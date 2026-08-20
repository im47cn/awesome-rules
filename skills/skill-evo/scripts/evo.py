#!/usr/bin/env python3
"""evo — skill-evo CLI 入口

子命令：
  run        （hook 后台入口）总结当前 CC 会话 + 搭车增量扫描 omp 会话
  scan-omp   仅扫描 omp 会话（调试/手动补偿）
  list       列出 pending 进化提案
  apply      应用提案（--dry-run 预演；--force 越过护栏警告）
  reject     驳回提案（--reason 记录原因）

所有命令对用户会话零影响：异常只写日志，exit 0/1 不抛栈。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evo_config as C
import evo_gepa as G
import evo_prompt as P
import evo_proposal as PR
import evo_session as S


def _log(cfg: dict, msg: str) -> None:
    paths = C.base_paths(cfg)
    try:
        paths["logs"].mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (paths["logs"] / "evo.log").open("a", encoding="utf-8").write(f"{stamp} {msg}\n")
    except OSError:
        pass


# ── LLM 总结 ────────────────────────────────────────────────────────────────

def call_claude(prompt: str, cfg: dict) -> dict:
    """headless 总结：禁 hooks 防递归；输出容错解析为 JSON dict。"""
    out = call_claude_raw(prompt, cfg)
    start, end = out.find("{"), out.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"claude -p 输出非 JSON：{out[:200]!r}")
    data = json.loads(out[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("claude -p 输出顶层不是对象")
    return data


def call_claude_raw(prompt: str, cfg: dict) -> str:
    """headless 纯文本通道（reflector 用；JSON 解析交给调用方）。"""
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)          # 去 CC 注入面
    env["AR_SKILL_EVO_CHILD"] = "1"      # 二次保险：即使 hooks 未禁，hook 脚本自会退出
    proc = subprocess.run(
        [str(cfg["claude_bin"]), "-p", prompt,
         "--settings", '{"hooks":{}}', "--max-turns", "1", "--output-format", "text"],
        capture_output=True, text=True,
        timeout=int(cfg["claude_timeout"]), env=env)
    return proc.stdout or ""


def _mk_proposal(sess: S.Session, data: dict) -> PR.Proposal | None:
    lessons = []
    for ls in data.get("lessons") or []:
        ch_raw = ls.get("change") or {}
        lessons.append(PR.Lesson(
            type=str(ls.get("type", "")), evidence=str(ls.get("evidence", "")),
            target_file=str(ls.get("target_file", "")),
            confidence=str(ls.get("confidence", "")),
            reason=str(ls.get("reason", "")),
            change=PR.Change(action=str(ch_raw.get("action", "append_end")),
                             heading=str(ch_raw.get("heading", "")),
                             new_text=str(ch_raw.get("new_text", ""))) if ch_raw else None))
    if not lessons:
        return None
    now = datetime.now(timezone.utc)
    pid = (f"{now.strftime('%Y%m%d-%H%M%S')}-{sess.agent}-{sess.session_id[:8]}")
    return PR.Proposal(id=pid, source_agent=sess.agent, source_session=sess.session_id,
                       source_path=str(sess.path), created=now.isoformat(timespec="seconds"),
                       lessons=lessons)


def process_session(sess: S.Session, cfg: dict, repo: Path, dry_run: bool) -> str:
    """单会话总结 → 落盘提案。返回处理结果一句话（供日志）。"""
    if sess.user_message_count() < int(cfg["min_messages"]):
        return f"skip: 用户消息 {sess.user_message_count()} < min_messages"
    prompt = P.build_summary_prompt(sess, cfg, repo)
    if dry_run:
        Path("/tmp").joinpath("ar-skill-evo-prompt.md").write_text(prompt, encoding="utf-8")
        return "dry-run: prompt 已写入 /tmp/ar-skill-evo-prompt.md"
    data = call_claude(prompt, cfg)
    if data.get("no_signal") or not data.get("lessons"):
        return "no_signal: 无可提炼经验"
    proposal = _mk_proposal(sess, data)
    if proposal is None:
        return "no_signal: lessons 为空"
    paths = C.base_paths(cfg)
    out = PR.write_proposal(proposal, paths["pending"])
    return f"proposal: {out}（{len(proposal.lessons)} lessons）"


# ── run ─────────────────────────────────────────────────────────────────────

def cmd_run(args) -> int:
    cfg = C.load_config()
    if not cfg["enabled"]:
        return 0
    repo = C.repo_root()
    paths = C.base_paths(cfg)
    state_path = paths["state"]
    state = S.load_state(state_path)

    targets: list[S.Session] = []
    # 1) 本会话：CC hook（stdin JSON）或调试直传 session 文件（--agent 默认嗅探）
    hook_json = {}
    if args.hook_json_file:
        try:
            raw = Path(args.hook_json_file).read_text(encoding="utf-8")
            hook_json = json.loads(raw) if raw.strip() else {}
        except (OSError, json.JSONDecodeError) as e:
            _log(cfg, f"hook json 解析失败: {e}")
        finally:
            try:
                Path(args.hook_json_file).unlink()
            except OSError:
                pass
    session_file = args.session_file or args.transcript or hook_json.get("transcript_path")
    if session_file and Path(session_file).is_file():
        agent = args.agent if args.agent != "auto" else S.sniff_agent(Path(session_file))
        sess = S.parse_session(agent, Path(session_file))
        if agent == "cc" and hook_json.get("session_id"):
            sess.session_id = hook_json["session_id"]
        if C.in_scope(sess.cwd, cfg) and not S.is_processed(state, sess):
            targets.append(sess)
    elif args.cwd:
        # 2) omp 原生 hook 入口：只给 cwd，由 Python 定位最近会话文件
        for f in S.find_latest_omp_sessions(cfg, args.cwd, limit=int(cfg["omp_max_per_run"])):
            sess = S.parse_omp_session(f)
            if C.in_scope(sess.cwd, cfg) and not S.is_processed(state, sess):
                targets.append(sess)
    # 3) 搭车：omp 增量扫描（omp hook 未安装时的兜底；state 去重收敛重复）
    if not args.no_omp:
        for f in S.iter_omp_sessions(cfg):
            if len([t for t in targets if t.agent == "omp"]) >= int(cfg["omp_max_per_run"]):
                break
            sess = S.parse_omp_session(f)
            if C.in_scope(sess.cwd, cfg) and not S.is_processed(state, sess):
                targets.append(sess)

    for sess in targets:
        try:
            # 单会话单提案守卫：已有提案（任意状态）则跳过总结，防重复整包提案
            if not args.dry_run and PR.session_proposal_exists(
                    paths, sess.agent, sess.session_id):
                result = "skip: 该会话已有提案（单会话单提案守卫）"
            else:
                result = process_session(sess, cfg, repo, args.dry_run)
        except Exception as e:  # 后台失败静默：写日志，不影响其他会话
            result = f"error: {type(e).__name__}: {e}"
        _log(cfg, f"run {sess.key} cwd={sess.cwd} → {result}")
        # 处理过即记账（内容哈希；含 error，防失败会话反复重试；no_signal 同样不重提）。
        # dry-run 例外：预演不记账，否则会话被跳过导致之后不真正总结。
        if not args.dry_run:
            state.setdefault("processed", {})[sess.key] = S.content_digest(sess.path)
            S.save_state(state_path, state)
    return 0


def cmd_scan_omp(args) -> int:
    cfg = C.load_config()
    roots = S.discover_omp_roots(cfg)
    if not roots:
        print(f"未发现 omp 会话目录（{cfg['omp_sessions_dir']}）")
        return 1
    state = S.load_state(C.base_paths(cfg)["state"])
    n_all = n_new = 0
    for f in S.iter_omp_sessions(cfg):
        n_all += 1
        sess = S.parse_omp_session(f)
        flag = "new" if (C.in_scope(sess.cwd, cfg) and not S.is_processed(state, sess)) else "skip"
        n_new += flag == "new"
        print(f"{flag}\t{f.parent.name}/{f.name}\tcwd={sess.cwd}\t用户消息={sess.user_message_count()}")
    print(f"共 {n_all} 个会话文件（lookback {cfg['omp_lookback_days']} 天），待处理 {n_new}")
    return 0


def _find_pending(cfg: dict, pid: str) -> Path:
    pending = C.base_paths(cfg)["pending"]
    hits = [p for p in pending.glob("*.md") if p.stem == pid or p.stem.startswith(pid)]
    if not hits:
        raise SystemExit(f"未找到提案：{pid}（pending 目录 {pending}）")
    return hits[0]


def cmd_list(args) -> int:
    cfg = C.load_config()
    paths = C.base_paths(cfg)
    props = PR.list_proposals(paths["pending"])
    if not props:
        print(f"无 pending 提案（{paths['pending']}）")
        return 0
    for p in props:
        print(f"{p.id}  [{len(p.lessons)} lessons]")
        for w in p.warnings():
            print(f"  ⚠ {w}")
        for ls in p.lessons:
            print(f"  - [{ls.confidence}] {ls.type} → {ls.target_file}")
    return 0


def cmd_apply(args) -> int:
    cfg = C.load_config()
    paths = C.base_paths(cfg)
    path = _find_pending(cfg, args.id)
    proposal = PR.load_proposal(path)
    try:
        report = PR.apply_proposal(proposal, C.repo_root(),
                                   dry_run=args.dry_run, force=args.force)
    except PR.ApplyError as e:
        print(f"❌ 应用失败：{e}")
        return 1
    for line in report:
        print(("DRY-RUN " if args.dry_run else "APPLIED ") + line)
    if args.dry_run:
        return 0
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dest = PR.move_proposal(path, paths["applied"], {"status": "applied", "applied_at": stamp})
    print(f"提案已归档：{dest}")
    print("提示：变更已写入工作区，请 git diff 检查；满意后自行提交（本技能不自动 commit）")
    return 0


def cmd_reject(args) -> int:
    cfg = C.load_config()
    paths = C.base_paths(cfg)
    path = _find_pending(cfg, args.id)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dest = PR.move_proposal(path, paths["rejected"],
                            {"status": "rejected", "rejected_at": stamp,
                             "reject_reason": args.reason or ""})
    print(f"已驳回并归档：{dest}")
    return 0


def cmd_evolve(args) -> int:
    """GEPA 进化（手动低频命令）：v2 唯一 target = skill-evo 自身 SYSTEM_PROMPT。"""
    import evo_evolve as V
    cfg = C.load_config()
    if args.budget:
        cfg["gepa_budget"] = args.budget
    train, holdout = V.build_dataset(cfg)
    n_sessions = len({c.id for c in train + holdout})
    print(f"dataset：{len(train)} train / {len(holdout)} holdout cases"
          f"（{n_sessions} sessions，标注源 applied/rejected）")
    if args.dry_run:
        return 0
    from evo_prompt import SYSTEM_PROMPT
    best, matrix, log = G.run_gepa(
        baseline=SYSTEM_PROMPT, train=train, holdout=holdout,
        execute=V.make_execute(cfg, call_claude),
        reflect=V.make_reflect(call_claude_raw, cfg),
        budget=int(cfg["gepa_budget"]), batch_size=int(cfg["gepa_batch_size"]),
        rng_seed=args.seed, validate=V.validate_candidate(len(SYSTEM_PROMPT)),
        asset_desc="skill-evo lessons 提炼 SYSTEM_PROMPT")
    base_score = log[0]["holdout"].get("c0", float("-inf"))
    best_score = log[0]["holdout"].get(best.id, base_score)
    print(f"baseline(c0) holdout={base_score:.3f}  best({best.id}) holdout={best_score:.3f}")
    # 报告目录
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = C.base_paths(cfg)["base"] / "evolve" / stamp
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(
        {"best": {"id": best.id, "parent": best.parent, "gen": best.gen},
         "holdout": log[0]["holdout"], "iterations": log[1:]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (report_dir / "evolved_prompt.txt").write_text(best.text, encoding="utf-8")
    print(f"迭代日志与候选 prompt：{report_dir}")
    if best.id != "c0" and best_score - base_score > 0.2:
        path = V.write_evolution_proposal(cfg, SYSTEM_PROMPT, best, base_score, best_score, log)
        print(f"✅ holdout 改善 {best_score - base_score:.3f} > 0.2，已产出进化提案：{path}")
        print("   采纳方式见提案正文（人工编辑 evo_prompt.py 的 SYSTEM_PROMPT）")
    else:
        print("未达提案阈值（holdout 改善 ≤ 0.2 或 baseline 仍最优），仅存报告")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="evo", description="skill-evo 会话经验进化")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="hook 后台入口：总结会话 + 搭车 omp 扫描")
    p_run.add_argument("--hook-json-file", help="hook stdin JSON 落盘路径（CC SessionEnd）")
    p_run.add_argument("--session-file", help="直接指定会话文件路径（cc/omp 格式均可嗅探）")
    p_run.add_argument("--transcript", help="--session-file 的兼容别名（v1）")
    p_run.add_argument("--agent", choices=["cc", "omp", "auto"], default="auto",
                       help="会话格式（auto=嗅探，默认）")
    p_run.add_argument("--cwd", help="omp 原生 hook 入口：按 cwd 定位最近 omp 会话")
    p_run.add_argument("--no-omp", action="store_true", help="跳过 omp 搭车扫描")
    p_run.add_argument("--dry-run", action="store_true", help="只生成 prompt 不调用 LLM")
    p_run.set_defaults(func=cmd_run)

    p_scan = sub.add_parser("scan-omp", help="列出 omp 会话与增量状态")
    p_scan.set_defaults(func=cmd_scan_omp)

    p_list = sub.add_parser("list", help="列出 pending 提案")
    p_list.set_defaults(func=cmd_list)

    p_apply = sub.add_parser("apply", help="应用提案")
    p_apply.add_argument("id", help="提案 id（可前缀匹配）")
    p_apply.add_argument("--dry-run", action="store_true", help="预演不落盘")
    p_apply.add_argument("--force", action="store_true", help="越过护栏警告（人工已确认）")
    p_apply.set_defaults(func=cmd_apply)

    p_rej = sub.add_parser("reject", help="驳回提案")
    p_rej.add_argument("id")
    p_rej.add_argument("--reason", default="")
    p_rej.set_defaults(func=cmd_reject)

    p_ev = sub.add_parser("evolve", help="GEPA 进化 SYSTEM_PROMPT（手动低频，有 LLM 成本）")
    p_ev.add_argument("--target", default="prompt", choices=["prompt"],
                      help="进化对象（v2 仅 prompt）")
    p_ev.add_argument("--budget", type=int, default=None, help="rollout 预算（默认 config）")
    p_ev.add_argument("--seed", type=int, default=0, help="随机种子（可复现）")
    p_ev.add_argument("--dry-run", action="store_true", help="只打印 dataset 统计不调 LLM")
    p_ev.set_defaults(func=cmd_evolve)

    args = ap.parse_args()
    try:
        return args.func(args)
    except subprocess.TimeoutExpired:
        print("claude -p 超时，本次丢弃（幂等，下次会话再来）")
        return 1
    except SystemExit:
        raise
    except Exception as e:  # CLI 兜底：不抛栈
        print(f"❌ {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
