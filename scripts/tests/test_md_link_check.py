"""md_link_check 单测：死链/锚点/围栏豁免/外部链接跳过/tracked 面语义。"""
import subprocess
from pathlib import Path

import md_link_check as M



def make_repo(tmp_path: Path) -> Path:
    """tracked 面夹具：git init + add。untracked 的 node_modules 展示
    gitignore 真相源语义（gitignored 产物天然出局，无需逐目录登记）。"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text(
        "# 标题乙\n\n## Sub Heading Here\n", encoding="utf-8")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "dead.md").write_text(
        "[死链](absent.md)\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path

def write_a(tmp_path: Path, body: str) -> Path:
    a = tmp_path / "docs" / "a.md"
    a.write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", str(a)], check=True)
    return a


def test_ok_links_pass(tmp_path):
    root = make_repo(tmp_path)
    write_a(tmp_path, "# 甲\n\n[文件](b.md) [锚点](b.md#标题乙) [英文锚](b.md#sub-heading-here) "
                      "[页内](#甲) [外链](https://x.com/a) [图片](b.md)\n")
    assert M.check_links(root) == []


def test_broken_target_and_anchors(tmp_path):
    root = make_repo(tmp_path)
    write_a(tmp_path, "# 甲\n\n[死链](absent.md) [锚死](b.md#不存在) [页内死锚](#没有)\n")
    issues = M.check_links(root)
    assert len(issues) == 3
    assert any("目标不存在 → absent.md" in i for i in issues)
    assert any("锚点未命中 → b.md#不存在" in i for i in issues)
    assert any("锚点未命中 → #没有" in i for i in issues)   # 页内裸锚


def test_fence_and_inline_code_exempt(tmp_path):
    root = make_repo(tmp_path)
    write_a(tmp_path, "# 甲\n\n```markdown\n[围栏死链](absent.md)\n```\n\n行内 `code [示例](absent2.md)` 结束\n")
    assert M.check_links(root) == []


def test_excluded_dirs_skipped(tmp_path):
    root = make_repo(tmp_path)   # node_modules 内死链不应出现
    write_a(tmp_path, "# 甲\n\n[好](b.md)\n")
    assert M.check_links(root) == []


def test_url_encoded_path(tmp_path):
    root = make_repo(tmp_path)
    (tmp_path / "docs" / "带 空格.md").write_text("# t\n", encoding="utf-8")
    write_a(tmp_path, "# 甲\n\n[编码](%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.md)\n")
    assert M.check_links(root) == []


def test_non_md_anchor_not_checked(tmp_path):
    """非 md 目标的锚点（如 html）不校验锚，只验文件存在。"""
    root = make_repo(tmp_path)
    (tmp_path / "docs" / "x.html").write_text("<html/>", encoding="utf-8")
    write_a(tmp_path, "# 甲\n\n[html](x.html#任意锚)\n")
    assert M.check_links(root) == []


# ── README 索引零漂移（吸收自 readme_index_check）────────────────────────────

def _mk_assets(root: Path):
    (root / "skills").mkdir()
    (root / "skills" / "demo").mkdir()
    (root / "skills" / "demo" / "SKILL.md").write_text("# s\n", encoding="utf-8")
    (root / "skills" / "noskill").mkdir()                       # 无 SKILL/README 不要求登记
    (root / "steering").mkdir()
    (root / "steering" / "spec.md").write_text("# t\n", encoding="utf-8")
    (root / "steering" / "gtsp").mkdir()
    (root / "steering" / "gtsp" / "01.md").write_text("# g\n", encoding="utf-8")  # 子目录不逐个校验
    (root / "docs").mkdir()
    (root / "docs" / "design").mkdir()
    (root / "docs" / "design" / "d.md").write_text("# d\n", encoding="utf-8")


def test_readme_index_all_registered(tmp_path):
    root = tmp_path
    _mk_assets(root)
    (root / "README.md").write_text(
        "[s](skills/demo/SKILL.md) [t](steering/spec.md) [d](docs/design/d.md)\n",
        encoding="utf-8")
    assert M.check_readme_index(root) == []


def test_readme_index_drift_detected(tmp_path):
    root = tmp_path
    _mk_assets(root)
    (root / "README.md").write_text("[只有规范](steering/spec.md)\n", encoding="utf-8")
    drift = M.check_readme_index(root)
    assert any("skills/demo/" in d for d in drift)          # 技能漏登记
    assert any("steering/spec.md" not in d for d in drift)  # spec 已登记不应再报
    assert any("docs/design/d.md" in d for d in drift)      # 设计文档漏登记
    assert not any("gtsp" in d for d in drift)              # 子目录不逐个校验
    assert not any("noskill" in d for d in drift)           # 无技能文件不要求


def test_readme_index_missing_readme(tmp_path):
    assert M.check_readme_index(tmp_path) == [f"缺少 {tmp_path / 'README.md'}"]
