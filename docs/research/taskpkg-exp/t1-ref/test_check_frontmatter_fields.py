"""tools/check_frontmatter_fields.py 的行为测试。

全部样例在 tmp_path 独立构造（负/正控制），不依赖真实 steering/ 内容；
CLI exit code 语义经 sys.executable 子进程端到端验证。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "tools" / "check_frontmatter_fields.py"

_spec = importlib.util.spec_from_file_location("check_frontmatter_fields", _SCRIPT)
assert _spec is not None and _spec.loader is not None
cff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cff)

VALID_FM = ["title: 架构规范", "scenario: 分层与模块划分"]


def write_md(path: Path, fm_lines: list[str] | None, body: str = "# 正文\n",
             closing: bool = True) -> Path:
    """写样例 .md；fm_lines 为 None 时不写 frontmatter 块，
    closing=False 时省略闭合 ``---``（构造未闭合样例）。"""
    if fm_lines is None:
        path.write_text(body, encoding="utf-8")
        return path
    block = "---\n" + "\n".join(fm_lines) + "\n" + ("---\n" if closing else "")
    path.write_text(block + body, encoding="utf-8")
    return path


def run_cli(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(root)],
        capture_output=True, text=True,
    )


# ---------- 解析层 ----------

def test_parse_valid_block_and_first_colon_split():
    # 值中含冒号：按第一个冒号切分，URL 类值保持完整
    fm = cff.parse_frontmatter(
        "---\ntitle: a: b\nscenario: http://x/y\n---\n正文")
    assert fm == {"title": "a: b", "scenario": "http://x/y"}
    # 空文本 / 非 --- 开头：无 frontmatter
    assert cff.parse_frontmatter("") is None
    assert cff.parse_frontmatter("# 标题\n正文") is None


def test_parse_unclosed_block_returns_none():
    assert cff.parse_frontmatter("---\ntitle: x\n正文没有闭合") is None


def test_parse_skips_blank_and_comment_lines():
    # 空行与 # 注释行跳过；注释里的 title 不得注册为字段
    fm = cff.parse_frontmatter(
        "---\n\n# title: 注释陷阱\nscenario: s\n\n---\n")
    assert fm == {"scenario": "s"}


def test_parse_duplicate_key_first_occurrence_wins():
    fm = cff.parse_frontmatter("---\ntitle: 第一\nscenario: s\ntitle: 第二\n---\n")
    assert fm is not None and fm["title"] == "第一"


def test_parse_bare_key_maps_to_empty():
    # 裸 key（无值）解析为空串，由校验层判违规
    assert cff.parse_frontmatter("---\ntitle:\nscenario: s\n---\n") == {
        "title": "", "scenario": "s"}


# ---------- CLI 门禁语义 ----------

def test_cli_all_compliant_exits_zero(tmp_path: Path):
    # 正控制：嵌套目录全合规 + 非 .md 文件不参与扫描
    (tmp_path / "gtsp").mkdir()
    write_md(tmp_path / "a.md", VALID_FM)
    write_md(tmp_path / "gtsp" / "b.md", VALID_FM)
    (tmp_path / "note.txt").write_text("---\n裸文本\n", encoding="utf-8")
    r = run_cli(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 处违规" in r.stdout and "门禁通过" in r.stdout
    assert "a.md" not in r.stdout  # 无违规时不输出文件行


@pytest.mark.parametrize("title_line", ["title:", "title:    ", 'title: ""'])
def test_cli_empty_title_exits_one(tmp_path: Path, title_line: str):
    write_md(tmp_path / "bad.md", [title_line, "scenario: s"])
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "bad.md: 缺少非空 title" in r.stdout
    assert "缺少非空 scenario" not in r.stdout


def test_cli_missing_and_empty_scenario_exits_one(tmp_path: Path):
    # 缺 key 与空值同样判违规，且只报 scenario
    write_md(tmp_path / "a.md", ["title: t", "scenario:   "])
    write_md(tmp_path / "b.md", ["title: t"])
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "a.md: 缺少非空 scenario" in r.stdout
    assert "b.md: 缺少非空 scenario" in r.stdout
    assert "缺少非空 title" not in r.stdout


def test_cli_no_frontmatter_reports_both_fields(tmp_path: Path):
    write_md(tmp_path / "raw.md", None)
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "raw.md: 缺少非空 title" in r.stdout
    assert "raw.md: 缺少非空 scenario" in r.stdout


def test_cli_unclosed_frontmatter_is_violation(tmp_path: Path):
    write_md(tmp_path / "unclosed.md", ["title: t", "scenario: s"], closing=False)
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "unclosed.md: 缺少非空 title" in r.stdout


def test_cli_field_in_body_does_not_count(tmp_path: Path):
    # title 只出现在正文：门禁必须解析 frontmatter 块而非全文扫描
    write_md(tmp_path / "body.md", ["scenario: s"], body="---\ntitle: 正文冒充\n")
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "body.md: 缺少非空 title" in r.stdout


def test_cli_comment_field_does_not_count(tmp_path: Path):
    write_md(tmp_path / "cmt.md", ["# title: 注释冒充", "scenario: s"])
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "cmt.md: 缺少非空 title" in r.stdout


def test_cli_violations_sorted_and_deterministic(tmp_path: Path):
    # 故意按乱序创建含子目录：输出按相对路径字典序，两次运行逐字节一致
    (tmp_path / "sub").mkdir()
    write_md(tmp_path / "c.md", ["scenario: s"])
    write_md(tmp_path / "sub" / "a.md", ["scenario: s"])
    write_md(tmp_path / "b.md", ["scenario: s"])
    r1 = run_cli(tmp_path)
    r2 = run_cli(tmp_path)
    assert r1.returncode == 1
    assert r1.stdout == r2.stdout
    order = [ln.split(":")[0] for ln in r1.stdout.splitlines()
             if ln.endswith("缺少非空 title")]
    assert order == ["b.md", "c.md", "sub/a.md"], f"未按字典序: {order}"


def test_cli_missing_root_exits_two(tmp_path: Path):
    r = run_cli(tmp_path / "nope")
    assert r.returncode == 2
    assert "不是目录" in r.stderr


def test_cli_no_md_files_exits_two(tmp_path: Path):
    (tmp_path / "only.txt").write_text("x", encoding="utf-8")
    r = run_cli(tmp_path)
    assert r.returncode == 2
    assert "没有 .md 文件" in r.stderr
