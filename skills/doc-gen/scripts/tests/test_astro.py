"""builder.astro 测试。

覆盖：copy_astro_template（真实模板复制 + 跳过运行时目录）、create_minimal_skeleton、
_write_article_pages（落盘/空/无文件）、build_astro 编排（api-spec 复制 + article 落盘 + npm）、
npm 缺失/构建失败分支（均不抛异常）。
"""

import json
import subprocess

from builder.astro import (
    build_astro,
    copy_astro_template,
    create_minimal_skeleton,
    _write_article_pages,
)


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ── copy_astro_template / skeleton ────────────────────────────────────────────

def test_copy_astro_template_real(tmp_path):
    """复制真实 template，跳过 node_modules/dist/.astro。"""
    copy_astro_template(tmp_path)
    assert (tmp_path / "package.json").exists()
    assert not (tmp_path / "node_modules").exists()
    assert not (tmp_path / "dist").exists()


def test_create_minimal_skeleton(tmp_path):
    create_minimal_skeleton(tmp_path)
    assert (tmp_path / "package.json").exists()
    assert (tmp_path / "astro.config.mjs").exists()
    assert (tmp_path / "scripts" / "generate-pages.mjs").exists()


# ── _write_article_pages ──────────────────────────────────────────────────────

def test_write_article_pages(tmp_path):
    dm = tmp_path / "doc-manifest"
    dm.mkdir()
    (dm / "articles.json").write_text(
        json.dumps({"articles": [{"slug": "x", "body": "text"}]}), encoding="utf-8")
    _write_article_pages(tmp_path)
    f = tmp_path / "src" / "content" / "docs" / "articles" / "x.md"
    assert f.exists() and f.read_text(encoding="utf-8") == "text"


def test_write_article_pages_empty(tmp_path):
    dm = tmp_path / "doc-manifest"
    dm.mkdir()
    (dm / "articles.json").write_text(json.dumps({"articles": []}), encoding="utf-8")
    _write_article_pages(tmp_path)           # 无文章 → return


def test_write_article_pages_no_file(tmp_path):
    _write_article_pages(tmp_path)           # 无 articles.json → return


# ── build_astro 编排 ──────────────────────────────────────────────────────────

def test_build_astro_orchestration(tmp_path, monkeypatch):
    dm = tmp_path / "doc-manifest"
    dm.mkdir()
    (dm / "api-spec.json").write_text('{"paths":{}}', encoding="utf-8")
    (dm / "articles.json").write_text(
        json.dumps({"articles": [{"slug": "a", "body": "body-text"}]}), encoding="utf-8")
    monkeypatch.setattr("builder.astro.copy_astro_template", lambda out: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc())
    build_astro(tmp_path, dm)
    assert (tmp_path / "public" / "openapi.json").exists()
    assert (tmp_path / "src" / "content" / "docs" / "articles" / "a.md").exists()


def test_build_astro_npm_missing(tmp_path, monkeypatch):
    """npm 不存在（FileNotFoundError）→ 打印警告并返回，不抛。"""
    monkeypatch.setattr("builder.astro.copy_astro_template", lambda out: None)

    def raise_fnf(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    build_astro(tmp_path)                    # 不抛异常


def test_build_astro_build_fails(tmp_path, monkeypatch):
    """install 成功但 build 失败（CalledProcessError）→ 打印并返回。"""
    monkeypatch.setattr("builder.astro.copy_astro_template", lambda out: None)
    state = {"n": 0}

    def fake(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            return _FakeProc()               # npm install 成功
        raise subprocess.CalledProcessError(1, "build", stderr=b"err")

    monkeypatch.setattr(subprocess, "run", fake)
    build_astro(tmp_path)                    # 不抛异常


def test_build_astro_copies_external_manifest(tmp_path, monkeypatch):
    """manifest_dir ≠ output/doc-manifest → 复制 manifest 到站点目录。"""
    ext = tmp_path / "ext" / "doc-manifest"
    ext.mkdir(parents=True)
    (ext / "index.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "site"
    monkeypatch.setattr("builder.astro.copy_astro_template", lambda o: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc())
    build_astro(out, ext)
    assert (out / "doc-manifest" / "index.json").exists()


def test_build_astro_npm_install_fails(tmp_path, monkeypatch):
    """npm install 失败（CalledProcessError）→ 打印并返回。"""
    monkeypatch.setattr("builder.astro.copy_astro_template", lambda o: None)

    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, "install", stderr=b"err")

    monkeypatch.setattr(subprocess, "run", fail)
    build_astro(tmp_path)                    # 不抛异常


def test_build_astro_dist_reports_count(tmp_path, monkeypatch):
    """构建后 dist 存在 → 打印文件数。"""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("x", encoding="utf-8")
    monkeypatch.setattr("builder.astro.copy_astro_template", lambda o: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc())
    build_astro(tmp_path)


def test_write_article_pages_bad_json(tmp_path):
    """articles.json 解析异常 → 静默返回。"""
    dm = tmp_path / "doc-manifest"
    dm.mkdir()
    (dm / "articles.json").write_text("{bad", encoding="utf-8")
    _write_article_pages(tmp_path)           # 不抛异常
