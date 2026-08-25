#!/usr/bin/env python3
"""技能上下文消融实验（ablation）。

对 guard 技能的 badcase 夹具跑两臂 omp 调用，测量技能规则正文
（SKILL.md + 引用的 manual-rules）对 LLM 审查检出率的贡献：

  WITH 臂    prompt = 审查任务指令 + SKILL.md 全文 + manual-rules + 输入文件
  WITHOUT 臂 prompt = 审查任务指令 + 输入文件（不含任何技能规则正文）

两臂输入文件字节一致；omp 以 --no-tools --no-skills --no-rules
--no-extensions 隔离运行，禁止脚本执行，纯测 LLM 判断差异。

用法:
  python3 scripts/ablate/ablate.py --dry-run
  python3 scripts/ablate/ablate.py --skills ddl-guard --cases 001-forbidden-type-and-missing-comment,004-bad-index
  python3 scripts/ablate/ablate.py --resident-cost-only
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RAW_DIR = RESULTS_DIR / "raw"

# 技能审查域配置：任务指令模板 + SKILL.md 引用的规则文档（相对技能目录）
SKILL_PROFILES = {
    "ddl-guard": {
        "instruction": (
            "你是数据库规范审查专家。请审查下面的 MySQL 建表语句（DDL），"
            "找出所有违反数据库设计规范的问题。"
        ),
        "references": ["ddl-manual-rules.md"],
    },
    "api-guard": {
        "instruction": (
            "你是后端接口规范审查专家。请审查下面的 Java Controller API 定义，"
            "找出所有违反接口设计规范的问题。"
        ),
        "references": ["api-manual-rules.md"],
    },
}

# 期望规则 → 同义表述（归一化子串匹配用；LLM 措辞与夹具期望措辞常有差异）
SYNONYMS = {
    "禁用类型": ["text类型", "禁用的类型", "类型禁用", "禁用字段类型"],
    "表注释缺失": ["缺少表注释", "表无注释", "表comment缺失", "未设置表注释"],
    "字段注释缺失": ["缺少字段注释", "字段无注释", "字段comment缺失", "未写注释"],
    "必含字段缺失": ["缺少必含字段", "公共字段缺失", "审计字段缺失", "必备字段缺失", "缺少标准字段"],
    "泛化字段名": ["泛化词", "泛化命名", "无信息量字段"],
    "索引名长度": ["索引名过长", "索引名超过64", "索引名长度超", "索引名超长"],
    "唯一索引命名": ["唯一索引未以uk_开头", "uk_命名", "唯一索引命名不规范", "unique命名"],
    "普通索引命名": ["普通索引未以ix_开头", "ix_命名", "普通索引命名不规范", "idx_前缀"],
    "id重复索引": ["id已有主键索引", "主键重复索引", "重复索引", "冗余索引"],
    "索引数量": ["索引过多", "索引个数", "索引数量超", "非主键索引超过", "索引数超"],
    "联合索引字段数": ["联合索引字段过多", "联合索引超过5", "联合索引字段超", "索引字段个数"],
    "禁止path传标识": ["path传标识", "路径变量", "pathvariable", "url传标识", "路径传id", "路径中传参"],
    "路径命名": ["路径命名不规范", "kebab-case", "kebabcase", "驼峰路径", "路径大小写"],
    "动作收敛": ["动词收敛", "动作不在白名单", "动作不在收敛", "末段动词", "动作不合规"],
}

OUTPUT_CONTRACT = """
输出要求：
1. 逐条列出确实违反规范的问题（表名/端点/字段名、违反的规则、修改建议）。
2. 只报告可判定的规范违规，不要输出泛泛的优化建议。
3. 最后必须单独输出一行汇总，格式严格为：
DETECTED: 规则类别1; 规则类别2; ...
   每个规则类别用简短中文短语（如「禁用类型」「索引命名不规范」「表注释缺失」），用分号分隔；
   若未发现任何问题，输出 DETECTED: NONE
"""


def find_skill_dir(skill: str) -> Path:
    d = REPO_ROOT / "skills" / skill
    if not d.is_dir():
        raise FileNotFoundError(f"技能目录不存在: {d}")
    return d


def discover_badcases(skill: str):
    """返回排序后的 (case_name, case_dir) 列表，要求含 input/ 与 expected.md。"""
    base = find_skill_dir(skill) / "badcase"
    cases = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "expected.md").is_file() and (d / "input").is_dir():
                cases.append((d.name, d))
    return cases


def read_prompt_hint(case_dir: Path, fallback: str) -> str:
    """prompts.md 第一条提示词作为用户任务原话；缺失则用 profile 兜底。"""
    p = case_dir / "prompts.md"
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("- "):
                return line[2:].strip()
    return fallback


def parse_expected(expected_path: Path):
    """解析 expected.md「## 预期检查输出」下的『脚本自动检出：A、B、C』规则列表。"""
    text = expected_path.read_text(encoding="utf-8")
    rules = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = "预期检查输出" in line
            continue
        if in_section:
            m = re.match(r"-\s*(?:脚本自动检出|预期检出)\s*[：:]\s*(.+)$", line.strip())
            if m:
                rules.extend(
                    r.strip() for r in re.split(r"[、,，;；]", m.group(1)) if r.strip()
                )
    return rules


def build_prompt(skill: str, case_dir: Path, arm: str) -> str:
    profile = SKILL_PROFILES[skill]
    hint = read_prompt_hint(case_dir, profile["instruction"])
    parts = [
        profile["instruction"],
        f"用户原话：「{hint}」",
        "本次为静态审查：你不具备任何工具、不能执行任何脚本，请仅基于你掌握的规范知识逐条判断。",
        OUTPUT_CONTRACT,
    ]
    if arm == "with":
        skill_md = (find_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
        parts.append("以下是本团队该领域的审查规范（审查依据，请严格按此逐条核对）：\n")
        parts.append(f"===== 规范文档 1/2: skills/{skill}/SKILL.md =====\n{skill_md}\n")
        for i, ref in enumerate(profile["references"], start=2):
            ref_path = find_skill_dir(skill) / ref
            if ref_path.is_file():
                body = ref_path.read_text(encoding="utf-8")
                parts.append(f"===== 规范文档 {i}/2: skills/{skill}/{ref} =====\n{body}\n")

    inputs = sorted((case_dir / "input").iterdir())
    parts.append("待审查内容如下：")
    for f in inputs:
        body = f.read_text(encoding="utf-8")
        parts.append(f"----- 文件 {f.name} 开始 -----\n{body}\n----- 文件 {f.name} 结束 -----")
    parts.append("开始审查。")
    return "\n".join(parts)


def normalize(s: str) -> str:
    return re.sub(r"[\s,，、;；。./_-]", "", s.lower())


def lcs_len(a: str, b: str) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
            best = max(best, cur[j])
        prev = cur
    return best


def rule_hit(expected_rule: str, detected_items) -> bool:
    e = normalize(expected_rule)
    cands = [e] + [normalize(s) for s in SYNONYMS.get(expected_rule, [])]
    for d in detected_items:
        dn = normalize(d)
        if not dn:
            continue
        for c in cands:
            if c and (c in dn or dn in c):
                return True
        if lcs_len(e, dn) >= 3:
            return True
    return False


def extract_detected(output_text: str):
    """提取最后一个 DETECTED: 行的规则类别列表。"""
    matches = re.findall(r"DETECTED\s*[：:]\s*(.+)", output_text)
    if not matches:
        return []
    tail = matches[-1].strip().strip("`*")
    if tail.upper() == "NONE":
        return []
    return [t.strip() for t in re.split(r"[;；]", tail) if t.strip()]


def parse_omp_output(stdout: str):
    """从 omp --mode json 事件流提取 (assistant 文本, usage dict)。

    omp -p --mode json 输出 jsonl 事件流；最后一个含 messages 数组的事件
    （agent_end）带完整对话。assistant 回复 = role=assistant 的 content
    text 拼接。实测无 token usage 事件，usage 恒为 None（调用方估算）。
    """
    text, usage = "", None
    events = []
    try:
        events = [json.loads(stdout)]
    except (json.JSONDecodeError, ValueError):
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    events.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    pass

    # 倒序找最后一个带 messages 数组的事件，拼接 assistant 文本
    for ev in reversed(events):
        msgs = ev.get("messages") if isinstance(ev, dict) else None
        if isinstance(msgs, list):
            for m in msgs:
                if isinstance(m, dict) and m.get("role") == "assistant":
                    content = m.get("content")
                    if isinstance(content, str):
                        text += content
                    elif isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and isinstance(c.get("text"), str):
                                text += c["text"]
            if text:
                break
    if not text.strip():
        text = stdout
    return text, usage


def estimate_tokens(*chunks) -> int:
    return sum(len(c) for c in chunks) // 4


def run_omp(prompt: str, max_time: str, raw_path: Path):
    """执行一次隔离的 omp 调用，返回 (text, usage, wall_seconds, returncode)。"""
    with tempfile.TemporaryDirectory() as td:
        prompt_file = Path(td) / "prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        cmd = [
            "omp", "-p", f"@{prompt_file}",
            "--no-tools", "--no-skills", "--no-rules", "--no-extensions",
            "--no-session", "--no-title", "--no-lsp",
            "--mode", "json", "--max-time", max_time,
            "--cwd", td,
        ]
        budget_sec = 60 * 5
        m = re.fullmatch(r"(\d+)m", max_time)
        if m:
            budget_sec = 60 * int(m.group(1))
        elif max_time.isdigit():
            budget_sec = int(max_time)
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=budget_sec + 60, encoding="utf-8", errors="replace")
            wall = time.monotonic() - t0
            raw_path.write_text(
                f"$ {' '.join(cmd[:2])} … --max-time {max_time}\n--- STDERR ---\n{proc.stderr}\n"
                f"--- STDOUT ---\n{proc.stdout}\n", encoding="utf-8")
            text, usage = parse_omp_output(proc.stdout)
            if not text.strip():
                text = proc.stderr
            return text, usage, wall, proc.returncode
        except subprocess.TimeoutExpired:
            wall = time.monotonic() - t0
            raw_path.write_text(f"TIMEOUT after {budget_sec + 60}s\n", encoding="utf-8")
            return f"ERROR: omp 调用超时（>{budget_sec + 60}s）", None, wall, -1


def resident_cost():
    """统计 skills/*/SKILL.md frontmatter description 的字符与估算 token。"""
    rows = []
    skills_root = REPO_ROOT / "skills"
    for d in sorted(skills_root.iterdir()):
        f = d / "SKILL.md"
        if not d.is_dir() or not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        fm = m.group(1) if m else ""
        desc = ""
        # 单行格式: description: xxx
        m1 = re.search(r"^description:[ \t]*(.+)$", fm, re.MULTILINE)
        # 折叠格式: description: >\n  xxx\n  yyy
        m2 = re.search(r"^description:\s*>-?\s*\n((?:[ \t]+.*\n?)+)", fm, re.MULTILINE)
        if m2:
            desc = " ".join(l.strip() for l in m2.group(1).splitlines() if l.strip())
        elif m1:
            desc = m1.group(1).strip()
        rows.append({
            "skill": d.name,
            "desc_chars": len(desc),
            "frontmatter_chars": len(fm),
            "est_tokens_desc": len(desc) // 4,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(
        prog="ablate.py",
        description="guard 技能上下文成本消融实验：同一 badcase 跑 WITH/WITHOUT 规则正文两臂，"
                    "对比 LLM 审查检出率、墙钟耗时与 token 用量。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--skills", default="ddl-guard,api-guard",
                        help="逗号分隔的技能名（需存在于 skills/ 且有 SKILL_PROFILES 配置）")
    parser.add_argument("--cases", default=None,
                        help="逗号分隔的 badcase 目录名；默认取每技能排序后前 --limit 个")
    parser.add_argument("--limit", type=int, default=2,
                        help="未指定 --cases 时每技能取前 N 个 badcase")
    parser.add_argument("--max-time", default="5m", help="每次 omp 调用的 --max-time 预算")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的调用与 prompt 概要，不调用 omp")
    parser.add_argument("--arms", default="with,without",
                        help="要跑的臂，逗号分隔（如只复测 WITH 臂传 --arms with）")
    parser.add_argument("--resident-cost-only", action="store_true",
                        help="只输出 11 个技能 frontmatter description 常驻成本表后退出")
    args = parser.parse_args()

    if args.resident_cost_only:
        rows = resident_cost()
        total = sum(r["desc_chars"] for r in rows)
        print(f"{'skill':<22}{'desc_chars':>12}{'est_tokens(chars/4)':>22}")
        for r in rows:
            print(f"{r['skill']:<22}{r['desc_chars']:>12}{r['est_tokens_desc']:>22}")
        print(f"{'TOTAL':<22}{total:>12}{total // 4:>22}  ({len(rows)} skills)")
        return 0

    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    for s in skills:
        if s not in SKILL_PROFILES:
            print(f"错误: 技能 {s} 无 SKILL_PROFILES 配置（已支持: {', '.join(SKILL_PROFILES)}）",
                  file=sys.stderr)
            return 2

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = RESULTS_DIR / "ablation.jsonl"

    plan = []
    for skill in skills:
        cases = discover_badcases(skill)
        if args.cases:
            wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
            cases = [(n, d) for n, d in cases if n in wanted]
        else:
            cases = cases[: args.limit]
        for name, cdir in cases:
            expected = parse_expected(cdir / "expected.md")
            if not expected:
                print(f"警告: {skill}/{name} 期望规则为空，跳过", file=sys.stderr)
                continue
            plan.append((skill, name, cdir, expected))

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    # 臂名白名单（PR #53 审查⑧）：build_prompt 把一切非 "with" 值当 WITHOUT
    # 臂——拼错（如 witih）会静默跑错实验还以错名记录，必须在计划期拒绝。
    invalid_arms = [a for a in arms if a not in ("with", "without")]
    if invalid_arms:
        print(f"错误: 臂 {', '.join(invalid_arms)} 无效（已支持: with, without）",
              file=sys.stderr)
        return 2
    total_calls = len(plan) * len(arms)
    print(f"计划: {len(plan)} 个 badcase × {len(arms)} 臂 = {total_calls} 次 omp 调用（预算上限 6）")
    if total_calls > 6:
        print("错误: 计划调用次数超过 6 次预算，请用 --cases/--limit/--arms 收窄", file=sys.stderr)
        return 2

    if args.dry_run:
        for skill, name, cdir, expected in plan:
            for arm in arms:
                prompt = build_prompt(skill, cdir, arm)
                preview = prompt[:160].replace("\n", "⏎")
                print(f"[dry-run] {skill}/{name} arm={arm:<7} prompt_chars={len(prompt)} "
                      f"expected_rules={expected}\n    {preview}…")
        return 0

    records = []
    for skill, name, cdir, expected in plan:
        for arm in arms:
            prompt = build_prompt(skill, cdir, arm)
            raw_path = RAW_DIR / f"{skill}__{name}__{arm}.log"
            print(f"→ 调用 omp: {skill}/{name} arm={arm} …", flush=True)
            text, usage, wall, rc = run_omp(prompt, args.max_time, raw_path)
            detected = extract_detected(text)
            hits = [r for r in expected if rule_hit(r, detected)]
            missed = [r for r in expected if r not in hits]
            tok_desc, tok_in, tok_out = None, None, None
            token_source = "estimated"
            if usage:
                def pick(*keys):
                    for k in keys:
                        for uk, uv in usage.items():
                            if uk.lower() == k:
                                return uv
                    return None
                tok_in, tok_out = pick("inputtokens", "prompttokens", "inputtokencount"), \
                                  pick("outputtokens", "completiontokens", "outputtokencount")
                if tok_in is not None or tok_out is not None:
                    token_source = "usage"
            if tok_in is None and tok_out is None:
                tok_desc = estimate_tokens(prompt, text)
            rec = {
                "skill": skill, "case": name, "arm": arm,
                "prompt_chars": len(prompt), "output_chars": len(text),
                "expected_rules": expected, "detected": detected,
                "hits": hits, "missed": missed,
                "recall": round(len(hits) / len(expected), 3) if expected else None,
                "wall_seconds": round(wall, 1), "returncode": rc,
                "tokens_in": tok_in, "tokens_out": tok_out,
                "tokens_estimated_total": tok_desc, "token_source": token_source,
                "raw": str(raw_path.relative_to(REPO_ROOT)),
                "output_text": text,
            }
            records.append(rec)
            with jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  recall={rec['recall']} ({len(hits)}/{len(expected)}) "
                  f"missed={missed} wall={rec['wall_seconds']}s tokens[{token_source}]="
                  f"{tok_in or ''}/{tok_out or ''} est={tok_desc}")

    # 汇总表
    md_path = RESULTS_DIR / "summary.md"
    lines = ["# 消融实验汇总", "",
             "| 技能 | badcase | 臂 | 检出率 | 命中/期望 | 耗时(s) | token(来源) |",
             "|---|---|---|---|---|---|---|"]
    for r in records:
        tok = (f"{r['tokens_in']}/{r['tokens_out']} ({r['token_source']})"
               if r["token_source"] == "usage" else f"~{r['tokens_estimated_total']} (est)")
        lines.append(f"| {r['skill']} | {r['case']} | {r['arm']} | {r['recall']} | "
                     f"{len(r['hits'])}/{len(r['expected_rules'])} | {r['wall_seconds']} | {tok} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n汇总已写入 {md_path} 与 {jsonl_path}")

    with_avg = [r["recall"] for r in records if r["arm"] == "with"]
    without_avg = [r["recall"] for r in records if r["arm"] == "without"]
    if with_avg and without_avg:
        dw = sum(with_avg) / len(with_avg) - sum(without_avg) / len(without_avg)
        print(f"平均检出率差 (WITH - WITHOUT) = {dw:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
