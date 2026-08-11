/**
 * generate-pages.mjs — 从 doc-manifest/ 分片生成 MDX 页面
 *
 * 用法: node scripts/generate-pages.mjs
 * 前置: doc-manifest/ 分片目录（或 doc-manifest.json 旧版兼容）
 * 输出: src/content/docs/ 下生成所有 MDX 页面
 *
 * 模块拆分：
 *   lib/utils.mjs      — 共享工具函数与常量
 *   lib/generators.mjs — 页面生成器函数
 *   generate-pages.mjs — 主流程（入口，调用各生成器并统计）
 */

import path from 'node:path';
import fs from 'node:fs';
import {
  readJSON, readJSONMaybe,
  DOMAIN_CACHE, loadManifest, LAYER_TITLES,
  generateIndex, generateArchitecture,
  generateDomainOverview, generateLayerPage,
  generateDatabase, generateApiDocs,
  generateDomainModelPages,
  generateRisks, generateAdrPage, generateStateMachines,
  generateProjectPanorama,
  DOCS_DIR, MANIFEST_DIR,
} from './lib/generators.mjs';

async function main() {
  console.log('🦅 架构鹰眼 读取 doc-manifest/ ...');
  const manifest = loadManifest();
  const domains = manifest.domains || [];
  const projects = manifest._index?.projects || [];
  const isMultiProject = projects.length > 0;

  if (isMultiProject) {
    console.log(`  标题: ${manifest._index?.project?.name || '架构全景'}`);
    console.log(`  项目: ${projects.length} | 域: ${domains.length}`);
  } else {
    console.log(`  项目: ${manifest._index?.project?.name || manifest.meta?.project?.name || '?'}`);
    console.log(`  业务域: ${domains.length}`);
  }

  let totalPages = 0;

  // 清理旧页面
  for (const dir of ['domains', 'projects', 'domain-model']) {
    const d = path.join(DOCS_DIR, dir);
    if (fs.existsSync(d)) fs.rmSync(d, { recursive: true, force: true });
  }

  // ── 通用页面 ──
  generateIndex(manifest); console.log('  ✓ index.mdx'); totalPages++;
  generateArchitecture(manifest); console.log('  ✓ architecture.mdx'); totalPages++;

  // ── 🧠 领域模型 ──
  const dmCount = generateDomainModelPages(manifest);
  if (dmCount > 0) { console.log(`  ✓ domain-model/ (${dmCount} 页)`); totalPages += dmCount; }

  // ── 多项目模式 ──
  if (isMultiProject) {
    generateProjectPanorama(manifest);
    console.log('  ✓ projects/index.mdx (全景)');
    totalPages++;

    const projResults = await Promise.all(projects.map(proj => {
      return new Promise((resolve) => {
        const projDir = path.join(MANIFEST_DIR, 'projects', proj.id);
        if (!fs.existsSync(projDir)) return resolve({ id: proj.id, pages: 0 });

        const domainFiles = fs.readdirSync(projDir).filter(f => f.endsWith('.json'));
        let count = 0;

        for (const df of domainFiles) {
          const domainData = readJSON(path.join(projDir, df));
          const domain = {
            name: domainData.name,
            displayName: domainData.displayName,
            description: domainData.description,
            _project_id: proj.id,
            _project_name: proj.name,
            layers: domainData.layers || {},
          };

          generateDomainOverview(manifest, domain, proj);
          count++;

          for (const layerName of Object.keys(LAYER_TITLES)) {
            if (domainData.layers?.[layerName]?.components?.length) {
              generateLayerPage(manifest, domain, layerName, proj);
              count++;
            }
          }
        }
        resolve({ id: proj.id, pages: count });
      });
    }));

    for (const r of projResults) {
      console.log(`  ✓ projects/${r.id}/ (${r.pages} 页)`);
      totalPages += r.pages;
    }
  } else {
    // ── 单项目模式 ──
    if (manifest._index) {
      const domainFiles = domains.map(d => path.join(MANIFEST_DIR, 'domains', `${d.name}.json`));
      await Promise.all(domainFiles.map(async (f) => {
        if (fs.existsSync(f)) DOMAIN_CACHE.set(path.basename(f, '.json'), readJSON(f));
      }));
      console.log('  ✓ 域文件预加载完成');
    }

    let layerPageCount = 0;
    const domainTasks = domains.map(domain =>
      new Promise((resolve) => {
        const layers = domain.layers || {};
        generateDomainOverview(manifest, domain);
        let local = 0;
        for (const ln of Object.keys(LAYER_TITLES)) {
          if (layers[ln]?.components?.length) { generateLayerPage(manifest, domain, ln); local++; }
        }
        resolve({ name: domain.name, layerPages: local });
      })
    );

    const results = await Promise.all(domainTasks);
    for (const r of results) {
      layerPageCount += r.layerPages;
      console.log(`  ✓ domains/${r.name}/`);
    }
    totalPages += domains.length + layerPageCount;
  }

  // ── 架构风险清单 ──
  const riskCount = generateRisks();
  if (riskCount > 0) { console.log('  ✓ risks.mdx'); totalPages += riskCount; }

  // ── 架构决策记录 ──
  const adrCount = generateAdrPage();
  if (adrCount > 0) { console.log('  ✓ adr.mdx'); totalPages += adrCount; }

  // ── 状态机 ──
  const smCount = generateStateMachines();
  if (smCount > 0) { console.log('  ✓ state-machine.mdx'); totalPages += smCount; }

  // ── 数据库 ──
  const db = readJSONMaybe(path.join(MANIFEST_DIR, 'database.json'))
    || (manifest.database?.tables ? { tables: manifest.database.tables } : null);
  if (db?.tables?.length) {
    generateDatabase(manifest); console.log('  ✓ database.mdx'); totalPages++;
  }

  const apiCount = generateApiDocs(manifest);
  if (apiCount) { console.log('  ✓ api.mdx'); totalPages += apiCount; }

  console.log(`\n🦅 架构鹰眼: ${totalPages} 个 MDX 页面 → ${DOCS_DIR}`);
}

main().catch(e => { console.error('💥', e); process.exit(1); });
