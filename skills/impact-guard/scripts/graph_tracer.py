"""GraphTracer — Tier 2（主）：动态 Cypher 生成 + 新鲜度指引

脚本不直连 codebase-memory-mcp（Agent 层持有 MCP 工具），职责：
1. 检测 git HEAD（新鲜度比对的基准）
2. 为每个变更点生成 inbound 多跳 caller Cypher（对齐 arch-guard --mode graph
   的"动态生成、不手抄"惯例），Agent 粘贴到 query_graph 执行拿方法级证据链
"""

import subprocess
from pathlib import Path


def current_head(project_root: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


def build_cypher(change_qns: list[str], depth: int = 3) -> str:
    """生成 inbound caller 链查询（变更点 ← 调用方，1..depth 跳）。"""
    qn_list = ", ".join(f'"{q}"' for q in change_qns)
    return f"""// impact-guard Tier 2：变更点 inbound caller 链（方法级证据）
// 变更点: {qn_list}
MATCH (changed {{qualified_name: {qn_list}}})
MATCH (changed)<-[c:CALLS*1..{depth}]-(caller)
RETURN caller.qualified_name        AS caller,
       caller.file_path             AS caller_file,
       length(c)                    AS hops,
       [r IN c | r.line]            AS call_lines
ORDER BY hops, caller
LIMIT 500;"""


def build_entry_check_cypher() -> str:
    """入站入口核查：受影响类中哪些是框架入口（回归范围）。"""
    return """// 回归范围核查：受影响类中的入站入口（Controller/Listener/Job）
MATCH (f) WHERE f.qualified_name IN $AFFECTED
MATCH (f) WHERE exists(f.annotations)
RETURN f.qualified_name, f.annotations
ORDER BY f.qualified_name;"""


def render_graph_mode(project_root: str, change_qns: list[str],
                      depth: int = 3, skip_reindex: bool = False) -> str:
    """--mode graph 输出：新鲜度指引 + Cypher 清单（Agent 执行编排）。"""
    head = current_head(project_root)
    lines = ["## impact-guard Tier 2（graph 模式）", ""]
    lines.append("### 1. 图谱新鲜度检测")
    lines.append("")
    lines.append(f"- git HEAD: `{head or '获取失败（非 git 目录？）'}`")
    lines.append("- 执行 `index_status(project)`，对比图谱 `head_sha` 与上方 HEAD：")
    lines.append("  - 一致 → 继续第 2 步")
    lines.append("  - 不一致 → 先执行 `index_repository(repo_path)` reindex"
                 + ("（本次已 --skip-reindex，跳过并告警 ⚠️ 图谱过期，结果可能失真）"
                    if skip_reindex else ""))
    lines.append("")
    lines.append("### 2. inbound caller 链（粘贴到 query_graph 执行）")
    lines.append("")
    lines.append("```cypher")
    lines.append(build_cypher(change_qns, depth))
    lines.append("```")
    lines.append("")
    lines.append("### 3. 回归范围核查（把第 2 步 caller 列表填入 $AFFECTED）")
    lines.append("")
    lines.append("```cypher")
    lines.append(build_entry_check_cypher())
    lines.append("```")
    lines.append("")
    lines.append("> Tier 2 与 Tier 1 差异是粒度（方法 vs 类），非盲区：反射/动态代理"
                 "/多态分发两者同样盲。方法级证据链用于精确回归定位。")
    return "\n".join(lines)
