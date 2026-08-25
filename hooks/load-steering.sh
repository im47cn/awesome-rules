#!/bin/bash
# SessionStart hook — 动态扫描 steering/ 生成规范索引
# 索引内容从各规范文件 frontmatter 的 title / scenario 字段读取，
# 新增规范文件只需带 frontmatter（title + scenario），无需改本脚本。
# 分组约定：steering/*.md（直接子文件）= 通用设计规范；steering/gtsp/*.md = GTSP 工程规范。

# 定位 steering 目录：优先 CLAUDE_PLUGIN_ROOT，否则回退到脚本上级目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STEERING_DIR="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/steering"

python3 - "$STEERING_DIR" <<'PY'
import sys, os, re, json

steering = sys.argv[1]

def parse_meta(path):
    """从 frontmatter 读取 title / scenario，缺失则回退到 H1 标题。

    单文件异常（编码损坏/不可读）不阻断整个索引生成——降级为
    文件名 + '—'，SessionStart 注入不致整体丢失。
    """
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return os.path.basename(path), '—'
    title = scenario = None
    if content.startswith('---'):
        end = content.find('\n---', 3)
        if end != -1:
            fm = content[3:end]
            m = re.search(r'^title:\s*(.+)$', fm, re.M)
            if m:
                title = m.group(1).strip()
            m = re.search(r'^scenario:\s*(.+)$', fm, re.M)
            if m:
                scenario = m.group(1).strip()
    if not title:
        m = re.search(r'^#\s+(.+)$', content, re.M)
        title = m.group(1).strip() if m else os.path.basename(path)
    if not scenario:
        scenario = '—'
    return title, scenario

def md_files(base):
    d = os.path.join(steering, base) if base else steering
    if not os.path.isdir(d):
        return []
    return sorted(fn for fn in os.listdir(d) if fn.endswith('.md')
                  and os.path.isfile(os.path.join(d, fn)))

def table(files, base, header):
    lines = [f"| {header} | 路径 | 适用场景 |", "|---|---|---|"]
    for fn in files:
        title, scen = parse_meta(os.path.join(steering, base, fn) if base
                                 else os.path.join(steering, fn))
        rel = f"steering/{base}/{fn}" if base else f"steering/{fn}"
        lines.append(f"| {title} | {rel} | {scen} |")
    return '\n'.join(lines)

# A. 通用设计规范：steering/ 直接子 .md
general = md_files('')
# B. GTSP 工程规范：steering/gtsp/*.md，README 作总入口，其余作维度
gtsp_readme = [fn for fn in md_files('gtsp') if fn.upper() == 'README.MD']
gtsp_dims = [fn for fn in md_files('gtsp') if fn.upper() != 'README.MD']

parts = [
    "## Awesome Rules 规范索引",
    "",
    "规范分两组：**通用设计规范**（设计阶段）与 **GTSP 工程规范**（Java/Spring Cloud 编码）。"
    "两者体系独立，按任务所属体系选择对应规范，勿混用。在相关任务中必须主动 Read 并遵守：",
    "",
    "### A. 通用设计规范（设计阶段）",
    "",
    table(general, '', '规范'),
    "",
    "### B. GTSP 工程规范（编码阶段）",
    "",
]
if gtsp_readme:
    parts.append("总入口 steering/gtsp/README.md，gtsp-*/fss-* 微服务编码按维度加载：")
else:
    parts.append("gtsp-*/fss-* 微服务编码按维度加载：")
parts.append("")
parts.append(table(gtsp_dims, 'gtsp', '维度'))
parts.append("")
parts.append("**使用规则**：")
parts.append("- 遇到对应场景时，先 Read 相关规范文件，再开始工作")
parts.append("- 遵守各项规范；标注【强制】的条款不可违反（不通过则不予合并），【推荐】尽可能遵守")
parts.append("- 审查类任务可使用 /ddl-guard、/api-guard、/arch-guard、/contract-guard、/impact-guard 自动检查")

ctx = '\n'.join(parts)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": ctx}},
                 ensure_ascii=False))
PY
