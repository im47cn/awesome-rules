"""架构治理闭环引擎（REQ-D：基线 → 趋势 → 归属 → 债务 → 告警 → 门禁）。

数据源：doc-gen 产出的 risks.json（arch_check 违规清单，可选含 blame 归属）。

  D01 基线    — 冻结违规清单快照（fingerprint 集合 + revision），可命名回溯
  D02 趋势    — 当前 vs 基线：added（新增）/ removed（消除）/ retained（存量）
  D04 债务    — 存量违规登记 ledger（owner/dueDate/status），豁免强制理由
  D05 告警    — dueDate 超期未偿还 → overdue 列表
  D06 闭环    — 当前清单中消失的债务自动关闭（repaid + repaidAt）
  D07 门禁    — 基线之上的新增违规 → 非零退出（--warn-only 灰度）

fingerprint = sha1(file + ruleCode + description)：line 不参与（行漂移），
description 参与（规则措辞变更视为新违规——保守但可预期）。
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_FILE = "debt-ledger.json"
BASELINE_DIR = "baselines"


# ── 基础 ──────────────────────────────────────────────────────────────────────


def load_risks_status(manifest_dir) -> tuple:
    """读取 risks.json 的 issues 与数据可信状态（gate/baseline 只信任 ok）。

    状态语义（fail-closed：失败 ≠ 零违规）：
      ok         — 分片存在且解析成功（issues 为空 = 真零违规）
      missing    — risks.json 不存在（未接入 arch_check 或分片丢失）
      corrupt    — 存在但 JSON 损坏/不可读
      scan-error — 生成端 scan() 失败（error 字段非空，issues 恒空）
    """
    f = Path(manifest_dir) / "risks.json"
    if not f.exists():
        return [], "missing"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], "corrupt"
    if data.get("error"):
        return data.get("issues", []), "scan-error"
    return data.get("issues", []), "ok"


def load_risks(manifest_dir) -> list[dict]:
    """读取 risks.json 的 issues（向后兼容；需区分可信状态用 load_risks_status）"""
    return load_risks_status(manifest_dir)[0]


def fingerprint(issue: dict) -> str:
    """违规唯一标识：file + ruleCode + description（line 不参与，行漂移）"""
    raw = f"{issue.get('file', '')}|{issue.get('ruleCode', issue.get('rule', ''))}|{issue.get('description', '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── D01 基线 ──────────────────────────────────────────────────────────────────


def create_baseline(manifest_dir, name: str) -> dict:
    """冻结当前违规清单为命名基线；同名校验（拒绝静默覆盖）。

    基线同时把存量违规登记进债务 ledger（status=pending，owner 取 blame
    归属，dueDate 留空待人工规划——债务是有生命周期的，不是一次性清单）。
    """
    manifest_dir = Path(manifest_dir)
    issues, status = load_risks_status(manifest_dir)
    if status != "ok":
        # 从失败扫描冻结出的空基线会污染后续所有 gate 判定——拒绝而非降级
        raise RuntimeError(
            f"risks 数据不可信（{status}），拒绝冻结基线——先修复 doc-gen scan")
    meta = _load_meta(manifest_dir)

    baseline = {
        "schema_version": 1,
        "name": name,
        "createdAt": _now(),
        "revision": meta.get("evidence", {}).get("revision"),
        "totalIssues": len(issues),
        "fingerprints": {fingerprint(i): i for i in issues},
    }
    bdir = manifest_dir / BASELINE_DIR
    bdir.mkdir(parents=True, exist_ok=True)
    bfile = bdir / f"{name}.json"
    if bfile.exists():
        raise FileExistsError(f"基线已存在: {name}（如需重建请先删除）")
    bfile.write_text(json.dumps(baseline, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    # 存量违规自动登记债务（D04 初始条目）
    ledger = load_ledger(manifest_dir)
    known = {d["fingerprint"] for d in ledger["debts"]}
    for fp, issue in baseline["fingerprints"].items():
        if fp in known:
            continue
        ledger["debts"].append({
            "fingerprint": fp,
            "file": issue.get("file", ""),
            "rule": issue.get("rule", issue.get("ruleCode", "")),
            "severity": issue.get("severity", ""),
            "description": issue.get("description", ""),
            "owner": issue.get("author") or "unknown",   # D03 blame（risks.json 可选携带）
            "introducedAt": issue.get("introducedAt"),
            "dueDate": None,          # 待人工规划
            "status": "pending",      # pending / in-progress / repaid / exempt
            "exemptReason": None,
            "registeredAt": baseline["createdAt"],
        })
    save_ledger(manifest_dir, ledger)
    return {"baseline": name, "totalIssues": len(issues),
            "debts": len(ledger["debts"])}


def load_baseline(manifest_dir, name: str) -> dict:
    f = Path(manifest_dir) / BASELINE_DIR / f"{name}.json"
    if not f.exists():
        raise FileNotFoundError(f"基线不存在: {name}")
    return json.loads(f.read_text(encoding="utf-8"))


def _load_meta(manifest_dir) -> dict:
    f = Path(manifest_dir) / "meta.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ── D04 债务 ledger ───────────────────────────────────────────────────────────


def load_ledger(manifest_dir) -> dict:
    f = Path(manifest_dir) / LEDGER_FILE
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"schema_version": 1, "debts": []}


def save_ledger(manifest_dir, ledger: dict) -> None:
    (Path(manifest_dir) / LEDGER_FILE).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def exempt_debt(manifest_dir, fp: str, reason: str) -> dict:
    """豁免债务（强制理由——无理由的豁免就是放水）"""
    ledger = load_ledger(manifest_dir)
    for d in ledger["debts"]:
        if d["fingerprint"] == fp:
            if not reason.strip():
                raise ValueError("豁免必须填写理由")
            d["status"] = "exempt"
            d["exemptReason"] = reason
            d["exemptedAt"] = _now()
            save_ledger(manifest_dir, ledger)
            return d
    raise KeyError(f"债务不存在: {fp[:12]}")


# ── D02 趋势 / D06 闭环 ───────────────────────────────────────────────────────


def diff_risks(baseline: dict, current_issues: list) -> dict:
    """当前 vs 基线：added（新增，D07 门禁对象）/ removed（消除，D06 关债）/ retained"""
    base_fps = set(baseline.get("fingerprints", {}))
    cur_fps = {fingerprint(i): i for i in current_issues}
    added = [i for fp, i in cur_fps.items() if fp not in base_fps]
    removed_fps = base_fps - set(cur_fps)
    retained = [i for fp, i in cur_fps.items() if fp in base_fps]
    return {
        "added": added,
        "removedFingerprints": sorted(removed_fps),
        "retained": retained,
        "stats": {
            "baseline": len(base_fps),
            "current": len(cur_fps),
            "added": len(added),
            "removed": len(removed_fps),
            "retained": len(retained),
            "net": len(cur_fps) - len(base_fps),
        },
    }


def sync_ledger(manifest_dir, current_issues: list) -> dict:
    """D06 处置闭环：当前清单中消失的未偿债务自动关闭（repaid + repaidAt）。"""
    ledger = load_ledger(manifest_dir)
    cur_fps = {fingerprint(i) for i in current_issues}
    closed = []
    for d in ledger["debts"]:
        if d["status"] in ("pending", "in-progress") and d["fingerprint"] not in cur_fps:
            d["status"] = "repaid"
            d["repaidAt"] = _now()
            closed.append(d)
    if closed:
        save_ledger(manifest_dir, ledger)
    return {"closed": closed, "closedCount": len(closed)}


# ── D05 超期告警 ──────────────────────────────────────────────────────────────


def overdue_debts(manifest_dir) -> list[dict]:
    """dueDate 已过且未偿还（pending/in-progress）的债务"""
    now = datetime.now(timezone.utc)
    out = []
    for d in load_ledger(manifest_dir)["debts"]:
        if d["status"] not in ("pending", "in-progress") or not d.get("dueDate"):
            continue
        try:
            due = datetime.fromisoformat(d["dueDate"])
        except ValueError:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due < now:
            out.append({**d, "overdueDays": (now - due).days})
    out.sort(key=lambda d: -d["overdueDays"])
    return out


# ── D07 门禁 ──────────────────────────────────────────────────────────────────


def gate(manifest_dir, baseline_name: str, warn_only: bool = False) -> dict:
    """增量零容忍：基线之上的新增违规非空 → blocked。

    warn_only=True 为灰度模式（仅告警不阻断，D07 推广期过渡）。
    **数据不可信（missing/corrupt/scan-error）不在灰度范围**：没有可信
    数据就没有"放行"可言，fail-closed 恒 blocked——否则扫描故障会让
    门禁在最需要拦截的时刻静默失效。
    """
    baseline = load_baseline(manifest_dir, baseline_name)
    current, risk_status = load_risks_status(manifest_dir)
    if risk_status != "ok":
        return {
            "baseline": baseline_name,
            "mode": "warn-only" if warn_only else "enforce",
            "riskStatus": risk_status,
            "addedCount": 0,
            "added": [],
            "stats": {"baseline": len(baseline.get("fingerprints", {})),
                      "current": 0, "added": 0, "removed": 0,
                      "retained": 0, "net": 0},
            "blocked": True,
            "reason": f"risks 数据不可信（{risk_status}），门禁拒绝在无数据下放行",
        }
    diff = diff_risks(baseline, current)
    added = diff["added"]
    result = {
        "baseline": baseline_name,
        "mode": "warn-only" if warn_only else "enforce",
        "addedCount": len(added),
        "added": added,
        "stats": diff["stats"],
        "blocked": bool(added) and not warn_only,
    }
    if added:
        sync = sync_ledger(manifest_dir, current)   # 顺手闭环已消除债务
        result["repaidInThisRun"] = sync["closedCount"]
    return result


def render_gate(result: dict) -> str:
    lines = [f"🚦 治理门禁（{result['mode']}）| 基线 {result['baseline']}"]
    if result.get("riskStatus"):
        # fail-closed：数据不可信，展示原因而非空趋势误导
        lines.append(f"   ⛔ {result['reason']}")
        lines.append("⛔ 阻断合并（数据不可信，fail-closed）")
        return "\n".join(lines)
    s = result["stats"]
    lines.append(f"   基线 {s['baseline']} → 当前 {s['current']}"
                 f"（新增 {s['added']} / 消除 {s['removed']} / 净 {s['net']:+d}）")
    for i, issue in enumerate(result["added"][:10], 1):
        lines.append(f"   🔴 新增 #{i}: [{issue.get('severity', '?')}] "
                     f"{issue.get('file', '?')}:{issue.get('line', '?')} "
                     f"{issue.get('rule', issue.get('ruleCode', ''))}")
    if len(result["added"]) > 10:
        lines.append(f"   ... 共 {len(result['added'])} 条新增")
    if result.get("repaidInThisRun"):
        lines.append(f"   ✅ 本次自动关闭已消除债务 {result['repaidInThisRun']} 条（D06 闭环）")
    lines.append("⛔ 阻断合并（新增违规零容忍）" if result["blocked"] else "✅ 放行")
    return "\n".join(lines)
