"""Astro 站点构建模块 — 复制模板、安装依赖、构建静态站点。

从 doc_gen.py 提取，逻辑保持不变。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def build_astro(output_dir: Path, manifest_dir: Path | None = None) -> bool:
    """构建 Astro 站点（使用模板中的 generate-pages.mjs）

    返回 False 表示构建失败（依赖缺失 / npm install / build 失败 / 无产物），
    调用方必须据此以非零退出码结束——非零退出绝不可描述为成功。
    """
    """构建 Astro 站点（使用模板中的 generate-pages.mjs）"""
    # 1. 同步模板到输出目录（始终覆盖源码，确保 template 更新生效；
    #    node_modules/dist/.astro 等运行时产物由 copy_astro_template 跳过，不影响）
    print("  📋 同步 Astro 模板源码...")
    copy_astro_template(output_dir)

    # 2. 确保 doc-manifest/ 分片目录在输出目录（不是单文件）
    target_manifest_dir = output_dir / "doc-manifest"
    if manifest_dir and manifest_dir.resolve() != target_manifest_dir.resolve():
        if target_manifest_dir.exists():
            shutil.rmtree(target_manifest_dir)
        shutil.copytree(manifest_dir, target_manifest_dir)
        shard_count = sum(1 for _ in target_manifest_dir.rglob("*.json"))
        print(f"  ✓ doc-manifest/ 已复制到站点目录 ({shard_count} 个文件)")

    # 2.5 复制 api-spec.json 到 public/ （Scalar 前端 fetch 用）
    api_spec_src = target_manifest_dir / "api-spec.json"
    public_dir = output_dir / "public"
    if api_spec_src.exists():
        public_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(api_spec_src, public_dir / "openapi.json")
        print("  ✓ api-spec.json → public/openapi.json")

    # 2.6 落盘手写深度文档页面（从 articles.json 的 body 写 md 文件）
    _write_article_pages(output_dir)

    # 注：doc-manifest → dist 的部署由 astro.config.mjs 的 copyDocManifest 集成在
    # astro:build:done 时完成，无需在此复制到 public/（避免冗余副本）。

    # 3. 安装依赖
    print("  📦 安装 npm 依赖...")
    try:
        subprocess.run(
            ["npm", "install"],
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        print(f"  ❌ npm install 失败: {stderr[:500]}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("  ❌ 未找到 npm，构建失败（--build 需要 Node.js 环境）", file=sys.stderr)
        return False

    # 4. 执行完整构建（prebuild → astro build → postbuild/pagefind）
    print("  🔨 构建静态站点（generate-pages → astro build → pagefind）...")
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            timeout=180,
        )
        if result.stderr:
            # npm 经常把非错误信息输出到 stderr，仅打印最后几行
            stderr_lines = result.stderr.decode().strip().split("\n")[-5:]
            for line in stderr_lines:
                if "error" in line.lower() or "fail" in line.lower():
                    print(f"  ⚠ {line}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        print(f"  ❌ 构建失败: {stderr[-1000:]}", file=sys.stderr)
        return False

    dist_dir = output_dir / "dist"
    if not dist_dir.exists():
        print("  ❌ 构建退出码为 0 但未产生 dist/ 目录", file=sys.stderr)
        return False

    file_count = sum(1 for _ in dist_dir.rglob("*") if _.is_file())
    print(f"  ✅ 站点已构建: {dist_dir} ({file_count} 个文件)")
    print(f"  💡 本地预览: cd {output_dir} && npm run preview")
    return True


def _write_article_pages(output_dir: Path):
    """从 doc-manifest/articles.json 落盘深度文档 md 到 src/content/docs/articles/。

    body 已含 Starlight frontmatter，直接写文件即可；无需 project_root。
    """
    articles_file = output_dir / "doc-manifest" / "articles.json"
    if not articles_file.exists():
        return
    try:
        data = json.loads(articles_file.read_text(encoding="utf-8"))
    except Exception:
        return
    articles = data.get("articles", [])
    if not articles:
        return
    target_dir = output_dir / "src" / "content" / "docs" / "articles"
    target_dir.mkdir(parents=True, exist_ok=True)
    for art in articles:
        slug = art.get("slug")
        body = art.get("body")
        if slug and body:
            (target_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    print(f"  ✓ {len(articles)} 篇深度文档页面 → src/content/docs/articles/")


def copy_astro_template(output_dir: Path):
    """复制 Astro 站点模板"""
    # 获取模板目录（与此脚本同级的 template/）
    script_dir = Path(__file__).resolve().parent.parent.parent / "template"

    if not script_dir.exists():
        print(f"  ⚠ 模板目录不存在: {script_dir}", file=sys.stderr)
        print("    将创建最小骨架...")
        create_minimal_skeleton(output_dir)
        return

    # 复制模板（在遍历层跳过 node_modules/dist/.astro 等运行时产物；保留软链避免 .bin 损坏）
    # 注：ignore_patterns 仅作用于 copytree 内部递归，无法排除顶层 item，
    # 故须在遍历时直接跳过。symlinks=True 防止 src/public 内软链被展开成损坏副本。
    ignore_dirs = {"node_modules", "dist", ".astro", ".cache"}
    for item in script_dir.iterdir():
        if item.name in ignore_dirs:
            continue
        dest = output_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest, symlinks=True)
        else:
            shutil.copy2(item, dest)

    print(f"  ✓ 模板已复制: {script_dir} → {output_dir}")


def create_minimal_skeleton(output_dir: Path):
    """创建最小 Astro 站点骨架（含完整构建脚本）。

    当模板目录不存在时调用此函数，创建足以运行 --build 的最小项目。
    包含 generate-pages.mjs 和必要的目录结构。
    """
    # package.json
    package = {
        "name": "tech-docs",
        "version": "0.1.0",
        "private": True,
        "scripts": {
            "dev": "node scripts/generate-pages.mjs && astro dev",
            "start": "node scripts/generate-pages.mjs && astro dev",
            "prebuild": "node scripts/generate-pages.mjs",
            "build": "astro build",
            "postbuild": "pagefind --site dist",
            "preview": "astro preview",
        },
        "dependencies": {
            "@astrojs/starlight": "^0.32.0",
            "astro": "^5.0.0",
            "pagefind": "^1.3.0",
        },
    }
    (output_dir / "package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # astro.config.mjs
    astro_config = """import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  integrations: [
    starlight({
      title: '技术文档',
      defaultLocale: 'zh-CN',
      locales: {
        'zh-CN': { label: '简体中文' },
      },
      sidebar: [
        { label: '首页', link: '/' },
        { label: '架构总览', link: '/architecture' },
        { label: 'API 文档', link: '/api' },
        { label: '数据库设计', link: '/database' },
      ],
      components: {
        Head: './src/components/Head.astro',
      },
    }),
  ],
  output: 'static',
  srcDir: './content',
});
"""
    (output_dir / "astro.config.mjs").write_text(astro_config, encoding="utf-8")

    # 创建 scripts 目录和 generate-pages.mjs
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    generate_pages = '''#!/usr/bin/env node
/**
 * generate-pages.mjs — 最小化版本（模板不存在时的降级）
 * 从 doc-manifest/ 生成 MDX 页面。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const DOCS_DIR = path.join(ROOT, 'src', 'content', 'docs');
const MANIFEST_DIR = path.join(ROOT, 'doc-manifest');

function ensureDir(dir) { fs.mkdirSync(dir, { recursive: true }); }
function readJSON(filePath) { return JSON.parse(fs.readFileSync(filePath, 'utf-8')); }

console.log('🦅 架构鹰眼 (最小模式) 读取 doc-manifest/ ...');
const manifest = readJSON(path.join(MANIFEST_DIR, 'index.json'));
const project = manifest.project || {};
console.log(`  项目: ${project.name || '?'}`);
console.log(`  业务域: ${(manifest.domains || []).length}`);

ensureDir(DOCS_DIR);
const indexMdx = `---\ntitle: "${project.name || '技术文档'}"\ndescription: "${project.description || 'DDD 架构技术文档'}"\n---\n\n# ${project.name || '技术文档'}\n\n> ${project.description || 'DDD 架构技术文档'}\n\n## 概览\n\n- **业务域**: ${(manifest.domains || []).length}\n- **组件数**: ${manifest.componentCount || 0}\n- **数据表**: ${manifest.tableCount || 0}\n`;
ensureDir(DOCS_DIR);
fs.writeFileSync(path.join(DOCS_DIR, 'index.mdx'), indexMdx, 'utf-8');
console.log('  ✓ index.mdx');
console.log(`🦅 架构鹰眼: 1 个 MDX 页面 → ${DOCS_DIR}`);
'''
    (scripts_dir / 'generate-pages.mjs').write_text(generate_pages, encoding='utf-8')

    # 创建基本目录
    src_dir = output_dir / "content"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "docs").mkdir(parents=True, exist_ok=True)
    (output_dir / "public").mkdir(parents=True, exist_ok=True)

    print("  ✓ 最小 Astro 骨架已创建（含 generate-pages.mjs）")
