/**
 * lib/generators.mjs — 页面生成器函数
 *
 * 从 generate-pages.mjs 提取，按功能分组导出。
 * 入口 generate-pages.mjs 负责调用并统计。
 */

import fs from 'node:fs';
import path from 'node:path';
import {
  ensureDir, writeMDX, readJSON, readJSONMaybe, mdTable,
  dep, srcAbbr, DOMAIN_CACHE, loadManifest,
  LAYER_TITLES, LAYER_DESCRIPTIONS, SM_DOMAIN,
  ROOT, DOCS_DIR, MANIFEST_DIR,
} from './utils.mjs';

// 转发工具符号供 generate-pages.mjs 统一从本模块导入
export { ensureDir, readJSON, readJSONMaybe, DOMAIN_CACHE, loadManifest, LAYER_TITLES, DOCS_DIR, MANIFEST_DIR };

// ── 通用页面 ──

export function generateIndex(manifest) {
  const project = manifest.meta?.project || {};
  const domains = manifest.domains || [];
  const tableCount = manifest._index?.tableCount || 0;
  const hasOpenApi = manifest._index?.hasOpenApi;

  let content = `<div class="landing-cards">\n`;
  const cards = [
    { href: '/architecture/', icon: '🏗️', title: '架构总览', desc: 'DDD 分层架构 + 全景依赖图' },
    { href: '/domain-model/', icon: '🧩', title: '领域模型', desc: `${domains.length} 个业务域 · 聚合/实体/值对象` },
  ];
  if (tableCount > 0) cards.push({ href: '/database', icon: '🗄️', title: '数据库设计', desc: `${tableCount} 张表结构 · ER 图` });
  if (hasOpenApi) cards.push({ href: '/api', icon: '🔌', title: 'API 接口', desc: '交互式 OpenAPI 文档', target: true });
  cards.push({ href: '/risks', icon: '⚠️', title: '架构风险', desc: 'DDD 规范自动检测结果' });
  const adrTotal = readJSONMaybe(path.join(MANIFEST_DIR, 'adrs.json'))?.total || 0;
  const smData = readJSONMaybe(path.join(MANIFEST_DIR, 'state-machines.json'));
  const smTotal = Array.isArray(smData) ? smData.length : 0;
  const articleTotal = readJSONMaybe(path.join(MANIFEST_DIR, 'articles.json'))?.total || 0;
  if (adrTotal > 0) cards.push({ href: '/adr', icon: '📋', title: '架构决策', desc: `${adrTotal} 条架构决策记录 (ADR)` });
  if (smTotal > 0) cards.push({ href: '/state-machine', icon: '🔀', title: '状态机', desc: `${smTotal} 个状态机 · 转换图与审查` });
  if (articleTotal > 0) cards.push({ href: '/articles/README', icon: '📚', title: '深度分析', desc: `${articleTotal} 篇架构深度文档` });
  for (const c of cards) {
    const ext = c.target ? ' target="_blank" rel="noopener"' : '';
    content += `<a class="landing-card" href="${c.href}"${ext}><span class="lc-icon">${c.icon}</span><span class="lc-title">${c.title}</span><span class="lc-desc">${c.desc}</span></a>\n`;
  }
  content += `</div>\n`;

  // ── 构建验收面板（receipt.json 存在才渲染；旧 manifest 诚实降级不显示）──
  const receipt = readJSONMaybe(path.join(MANIFEST_DIR, 'receipt.json'));
  if (receipt && receipt.checks) {
    const statusMark = { ok: '✅', warn: '⚠️', fail: '❌', skipped: '⏭️' };
    const overall = receipt.ok ? '✅ 全部通过' : '❌ 存在失败阶段';
    content += `## 构建验收\n\n`;
    content += `> 本文档由 doc-gen 于生成时刻产出，验收状态：**${overall}**\n\n`;
    content += `| 阶段 | 状态 | 明细 |\n| --- | --- | --- |\n`;
    for (const [phase, c] of Object.entries(receipt.checks)) {
      const mark = statusMark[c.status] || c.status;
      const detail = Object.entries(c)
        .filter(([k]) => k !== 'status' && k !== 'error')
        .map(([k, v]) => `${k}=${v}`).join(', ')
        || (c.error ? String(c.error).slice(0, 60) : '');
      content += `| ${phase} | ${mark} ${c.status} | ${detail} |\n`;
    }
    const metaFile = readJSONMaybe(path.join(MANIFEST_DIR, 'meta.json')) || {};
    const ev = metaFile.evidence;
    if (ev) {
      const sha = ev.revision ? ev.revision.slice(0, 12) : '未钉定';
      const dirty = ev.dirty ? ' ⚠️ **生成时工作区有未提交变更，revision 可能与内容不一致**' : '';
      content += `\n<small>证据锚点：revision \`${sha}\`（生成时刻钉定，代码演进不漂移）${dirty}</small>\n`;
    }
    const stale = receipt.checks?.manifest?.staleCommits;
    if (stale > 0) {
      content += `\n> ⚠️ **文档已落后当前代码 ${stale} 个提交**，建议重新生成。\n`;
    }
    content += `\n`;
  }

  writeMDX(path.join(DOCS_DIR, 'index.mdx'), {
    title: project.name || '技术文档',
    description: project.description || 'DDD 架构技术文档',
    tableOfContents: false,
    hero: { title: project.name || '技术文档', tagline: project.description || 'DDD 架构技术文档' },
  }, content);
}

export function generateArchitecture(manifest) {
  let content = `import ArchitectureDiagram from '../../components/ArchitectureDiagram.astro';\n\n<ArchitectureDiagram />\n\n`;
  content += '## DDD 分层架构\n\n';
  content += '```mermaid\n' + (manifest.diagrams?.architectureOverview || '') + '\n```\n\n';

  // Java 正则扫描局限性提示（issue #1 修复）
  const scanInfo = manifest.meta?.scanLimitations;
  if (scanInfo && scanInfo.hasIssues) {
    content += '> ⚠️ **扫描局限性提示**：本项目部分 Java 文件因正则解析限制未能完整扫描（覆盖率 ';
    content += `${scanInfo.scannedRatio * 100}%，${scanInfo.scannedJavaFiles}/${scanInfo.totalJavaFiles} 个文件）。`;
    content += '以下语法需 AST 解析才能正确处理：';
    content += scanInfo.knownLimitations.map(l => `- ${l}`).join('\n');
    content += '\n\n> 建议对关键类手动补充文档。\n\n';
  }

  if (manifest.diagrams?.layerDependencyReal) {
    content += '## 层间真实依赖（基于 IMPORTS）\n\n';
    content += '> 边为真实 Java import 计数。`==>`（红色）为违规跨层依赖，与 arch-guard 审查口径一致；`-->` 为合法依赖。\n\n';
    content += '```mermaid\n' + manifest.diagrams.layerDependencyReal + '\n```\n\n';
  }

  content += '## 分层说明\n\n';
  for (const [layer, title] of Object.entries(LAYER_TITLES)) {
    content += `### <span class="layer-badge ${layer}">${title}</span>\n\n`;
    content += `${LAYER_DESCRIPTIONS[layer]}\n\n`;
  }

  content += '## 依赖方向\n\n';
  content += '```mermaid\n' + (manifest.diagrams?.layeredDependency || '') + '\n```\n';

  writeMDX(path.join(DOCS_DIR, 'architecture.mdx'), {
    title: '架构总览', description: 'DDD 分层架构总览',
  }, content);
}

// ── 域与层页面 ──

export function generateDomainOverview(manifest, domain, project = null) {
  const dName = domain.displayName || domain.name;
  const layers = domain.layers || {};
  const prefix = project ? `/projects/${project.id}` : `/domains/${domain.name}`;
  let content = '';
  if (project) content += `> 所属项目: **${project.name}**\n\n`;
  content += `${domain.description || ''}\n\n`;

  content += '## 分层架构\n\n```mermaid\n';
  content += `graph TD\n  subgraph ${domain.name.replace(/-/g, '_')}["${dName} 域"]\n`;
  content += '    A[Adapter] --> B[Application]\n    B --> C[Domain]\n    C <-- D[Infrastructure]\n    B --> D\n  end\n';
  content += '```\n\n';

  content += '## 各层组件\n\n';
  for (const [layerName, title] of Object.entries(LAYER_TITLES)) {
    const comps = layers[layerName]?.components || [];
    if (comps.length > 0) {
      content += `### [${title}](${prefix}/${layerName}/) (${comps.length} 个组件)\n\n`;
      content += mdTable(
        ['类名', '类型'],
        comps.slice(0, 15).map(c => [srcAbbr(c.className, c.sourcePath, c.sourceLine), c.type])
      );
      if (comps.length > 15) content += `\n> ... 还有 ${comps.length - 15} 个组件\n`;
      content += '\n';
    }
  }

  const aggregates = layers.domain?.aggregates || [];
  if (aggregates.length > 0) {
    content += '## 聚合\n\n';
    for (const agg of aggregates) {
      content += `### ${agg.name}\n\n`;
      content += '| 属性 | 值 |\n|------|----|\n';
      const re = agg.rootEntity;
      if (re) {
        content += `| 聚合根 | \`${re.className}\` |\n| 限定名 | ${srcAbbr(re.qualifiedName, re.sourcePath)} |\n`;
        if (re.methods?.length) content += `| 方法 | ${re.methods.map(m => `\`${m}()\``).join(', ')} |\n`;
        if (re.fields?.length) content += `| 字段 | ${re.fields.map(f => `\`${f.name}: ${f.type}\``).join('<br/>')} |\n`;
      }
      if (agg.entities?.length) content += `| 实体 | ${agg.entities.map(e => `\`${e.className}\``).join(', ')} |\n`;
      if (agg.valueObjects?.length) content += `| 值对象 | ${agg.valueObjects.map(v => `\`${v.className}\``).join(', ')} |\n`;
      if (agg.domainServices?.length) content += `| 领域服务 | ${agg.domainServices.map(s => `\`${s.className}\``).join(', ')} |\n`;
      if (agg.domainEvents?.length) content += `| 领域事件 | ${agg.domainEvents.map(e => `\`${e.className}\``).join(', ')} |\n`;
      content += '\n';
    }
  }

  const aggDiagram = manifest.diagrams?.domainAggregates?.[domain.name];
  if (aggDiagram) {
    content += '## 聚合类图\n\n```mermaid\n' + aggDiagram + '\n```\n';
  }

  const outDir = project ? path.join(DOCS_DIR, 'projects', project.id) : path.join(DOCS_DIR, 'domains', domain.name);
  writeMDX(path.join(outDir, 'index.mdx'), { title: `${dName} - 业务域概览` }, content);
}

export function generateLayerPage(manifest, domain, layerName, project = null) {
  // domain 分支依赖 manifest.diagrams.domainAggregates 渲染领域模型关系图
  const dName = domain.displayName || domain.name;
  const title = LAYER_TITLES[layerName] || layerName;
  const layerData = (domain.layers || {})[layerName] || {};
  const comps = layerData.components || [];
  const prefix = project ? `/projects/${project.id}` : `/domains/${domain.name}`;

  let content = '';
  content += `> 所属业务域: [${dName}](${prefix}/)\n`;
  if (project) content += `> 所属项目: **${project.name}**\n`;
  content += `> Java 包: \`${layerData.javaPackage || ''}\`\n`;
  content += `> Maven 模块: \`${layerData.mavenModule || ''}\`\n`;
  content += `> 组件数: ${comps.length}\n\n`;
  content += `${LAYER_DESCRIPTIONS[layerName]}\n\n`;

  const byType = {};
  for (const c of comps) { (byType[c.type] ||= []).push(c); }

  for (const [compType, items] of Object.entries(byType).sort()) {
    content += `## ${compType}\n\n`;
    content += mdTable(
      ['类名'],
      items.map(c => [dep(srcAbbr(c.className, c.sourcePath, c.sourceLine), c.deprecated)])
    );
    content += '\n';

    for (const c of items.slice(0, 10)) {
      content += `### ${dep('`' + c.className + '`', c.deprecated)}\n\n`;
      content += mdTable(
        ['属性', '值'],
        [
          ['类型', c.type], ['限定名', srcAbbr(c.qualifiedName || '-', c.sourcePath, c.sourceLine)],
        ].concat(
          c.methods?.length ? [['方法', c.methods.map(m => `\`${m}()\``).join(', ')]] : [],
          c.fields?.length ? [['字段', c.fields.map(f => dep(`\`${f.name}: ${f.type}\``, f.deprecated)).join(', ')]] : [],
        )
      );
      content += '\n';

      if (c.endpoints?.length) {
        content += '**REST 端点**:\n\n';
        content += mdTable(
          ['方法', '路径', '说明', '请求体'],
          c.endpoints.map(ep => [
            `\`${ep.method}\``, dep(`\`${ep.path}\``, ep.deprecated),
            dep(ep.summary || '-', ep.deprecated), `\`${ep.requestBody || '-'}\``,
          ])
        );
        content += '\n';
      }
    }
  }

  if (layerName === 'domain') {
    const aggDiagram = manifest.diagrams?.domainAggregates?.[domain.name];
    if (aggDiagram) {
      content += '## 领域模型关系图\n\n```mermaid\n' + aggDiagram + '\n```\n\n';
    }
    content += `> 💡 详细领域模型请查看 [🧠 领域模型](/domain-model/${domain.name}/)\n\n`;
  }

  const outDir = project ? path.join(DOCS_DIR, 'projects', project.id) : path.join(DOCS_DIR, 'domains', domain.name);
  const fileName = layerName === 'domain' ? path.join('domain', 'index.mdx') : `${layerName}.mdx`;
  writeMDX(path.join(outDir, fileName), { title: `${dName} - ${title}` }, content);
}

// ── 数据库页面 ──

export function generateDatabase(manifest) {
  const db = readJSONMaybe(path.join(MANIFEST_DIR, 'database.json'))
    || (manifest.database?.tables ? manifest.database : { tables: [] });
  const tables = db.tables || [];
  if (!tables.length) return;

  let content = '';
  if (db.inferred) {
    content += `> ⚠️ **推断说明**：表结构与关系基于 PO 的 ${db.source || '@TableName/@TableField'} 注解推断，未经 DDL 验证；关系为启发式匹配（\`*_id\`/\`*_no\` 外键列名），请以实际 DDL 核对。\n\n`;
  }

  if (manifest.diagrams?.erDiagram) {
    content += '## 📊 ER 图（表关系拓扑）\n\n';
    content += '> 仅展示表名与外键关系连线，字段详情见下方「表结构」。\n\n';
    content += '```mermaid\n' + manifest.diagrams.erDiagram + '\n```\n\n';
  }

  const unmatched = db.unmatched_fks || [];
  if (unmatched.length) {
    content += '## ⚠️ 疑似外键（未自动匹配，需人工核对）\n\n';
    content += mdTable(
      ['所在表', '外键列', '列前缀(去_id/_no)'],
      unmatched.map(f => [`\`${f.table}\``, `\`${f.column}\``, `\`${f.prefix}\``])
    );
    content += '\n';
  }

  content += `## 表结构 (${tables.length} 张表)\n\n`;
  for (const table of tables) {
    content += `### ${table.name}\n\n`;
    if (table.comment) content += `> ${table.comment}\n\n`;

    content += `**📋 字段列表（${table.columns.length} 列）**\n\n`;
    content += mdTable(
      ['字段', '类型', '主键', '非空', '默认值', '说明'],
      table.columns.map(col => [
        `\`${col.name}\``, col.type, col.primaryKey ? '✅' : '',
        col.nullable === false ? '✅' : '', col.defaultValue || '', col.comment || '',
      ])
    );
    content += '\n';

    if (table.indexes?.length) {
      content += `**🔍 索引（${table.indexes.length} 个）**\n\n`;
      content += mdTable(
        ['索引名', '字段', '唯一'],
        table.indexes.map(idx => [
          `\`${idx.name}\``, idx.columns.map(c => `\`${c}\``).join(', '),
          idx.unique ? '✅' : '',
        ])
      );
      content += '\n';
    }
  }

  writeMDX(path.join(DOCS_DIR, 'database.mdx'), {
    title: '🗄️ 数据库设计', description: '数据库表结构设计文档',
  }, content);
}

// ── API 文档页面 ──

export function generateApiDocs(manifest) {
  const hasSpec = (manifest.openapiSpecs && Object.keys(manifest.openapiSpecs).length > 0)
    || manifest._index?.hasOpenApi
    || fs.existsSync(path.join(MANIFEST_DIR, 'api-spec.json'));

  if (!hasSpec) return 0;

  const apiSpecSrc = path.join(MANIFEST_DIR, 'api-spec.json');
  const publicDir = path.join(ROOT, 'public');
  if (fs.existsSync(apiSpecSrc)) {
    ensureDir(publicDir);
    fs.copyFileSync(apiSpecSrc, path.join(publicDir, 'openapi.json'));
  }
  const scalarSrc = path.join(ROOT, 'node_modules', '@scalar', 'api-reference', 'dist', 'browser', 'standalone.js');
  if (fs.existsSync(scalarSrc)) {
    ensureDir(publicDir);
    fs.copyFileSync(scalarSrc, path.join(publicDir, 'scalar.js'));
  }

  const oldApiMdx = path.join(DOCS_DIR, 'api.mdx');
  if (fs.existsSync(oldApiMdx)) fs.unlinkSync(oldApiMdx);
  return 1;
}

// ── 领域模型页面 ──

export function collectDomainModelData(manifest) {
  const result = [];
  const projects = manifest._index?.projects || [];
  const isMulti = projects.length > 0;

  if (isMulti) {
    for (const proj of projects) {
      const projDir = path.join(MANIFEST_DIR, 'projects', proj.id);
      if (!fs.existsSync(projDir)) continue;
      for (const df of fs.readdirSync(projDir).filter(f => f.endsWith('.json'))) {
        const dd = readJSON(path.join(projDir, df));
        const domainLayer = dd.layers?.domain;
        if (!domainLayer) continue;
        result.push({
          domainName: dd.name, displayName: dd.displayName || dd.name,
          description: dd.description || '', projectId: proj.id, projectName: proj.name,
          aggregates: domainLayer.aggregates || [],
          entities: (domainLayer.components || []).filter(c => c.type === 'entity'),
          valueObjects: (domainLayer.components || []).filter(c => c.type === 'valueObject'),
          domainServices: (domainLayer.components || []).filter(c => c.type === 'domainService'),
          domainEvents: (domainLayer.components || []).filter(c => c.type === 'domainEvent'),
          repositoryInterface: (domainLayer.components || []).find(c => c.type === 'repositoryInterface'),
          gateways: (domainLayer.components || []).filter(c => c.type === 'gateway'),
          javaPackage: domainLayer.javaPackage || '', mavenModule: domainLayer.mavenModule || '',
        });
      }
    }
  } else {
    for (const domain of manifest.domains) {
      const layers = domain.layers || {};
      const domainLayer = layers.domain;
      if (!domainLayer) continue;
      result.push({
        domainName: domain.name, displayName: domain.displayName || domain.name,
        description: domain.description || '', projectId: null, projectName: null,
        aggregates: domainLayer.aggregates || [],
        entities: (domainLayer.components || []).filter(c => c.type === 'entity'),
        valueObjects: (domainLayer.components || []).filter(c => c.type === 'valueObject'),
        domainServices: (domainLayer.components || []).filter(c => c.type === 'domainService'),
        domainEvents: (domainLayer.components || []).filter(c => c.type === 'domainEvent'),
        repositoryInterface: (domainLayer.components || []).find(c => c.type === 'repositoryInterface'),
        gateways: (domainLayer.components || []).filter(c => c.type === 'gateway'),
        javaPackage: domainLayer.javaPackage || '', mavenModule: domainLayer.mavenModule || '',
      });
    }
  }
  return result;
}

/** 渲染领域间跨域依赖 Mermaid 图。无依赖时返回空串。
 *  边样式: --> 同步 Client API · -.-> 异步领域事件 · ==> 直接领域耦合(建议解耦) */
export function renderCrossDomainDeps(deps) {
  if (!deps || deps.length === 0) return '';
  const nid = (n) => n.replace(/[^a-zA-Z0-9]/g, '_');
  const nodes = new Set();
  const pairType = new Map();
  const severity = { 'domain-coupling': 3, 'client-api': 2, 'domain-event': 1 };
  const edgeStyle = { 'client-api': '-->', 'domain-event': '-.->', 'domain-coupling': '==>' };
  for (const d of deps) {
    nodes.add(d.fromDomain); nodes.add(d.toDomain);
    const key = `${d.fromDomain}->${d.toDomain}`;
    const prev = pairType.get(key);
    if (!prev || (severity[d.type] || 0) > (severity[prev] || 0)) pairType.set(key, d.type);
  }
  const coupling = deps.filter(d => d.type === 'domain-coupling').length;
  let out = '## 🔗 领域间关系\n\n';
  out += `> 共 ${deps.length} 条跨域依赖（其中 ${coupling} 条直接领域层耦合）。`;
  out += '边样式：`-->`同步 Client API · `-.->`异步领域事件 · `==>`直接领域耦合（建议解耦）。\n\n';
  out += '```mermaid\ngraph LR\n';
  for (const n of nodes) out += `  ${nid(n)}["${n}"]\n`;
  for (const [key, typ] of pairType) {
    const [f, t] = key.split('->');
    out += `  ${nid(f)} ${edgeStyle[typ] || '-->'} ${nid(t)}\n`;
  }
  out += '```\n\n';
  return out;
}

export function generateDomainModelPages(manifest) {
  const dmData = collectDomainModelData(manifest);
  if (dmData.length === 0) return 0;

  let content = '';
  content += '> 所有业务域的领域层模型全景 — 聚合根、实体、值对象、领域服务、领域事件\n\n';
  content += renderCrossDomainDeps(manifest.crossDomainDependencies || []);

  content += '## 业务域\n\n';
  for (const d of dmData) {
    const projectLabel = d.projectName ? ` · ${d.projectName}` : '';
    content += `### [${d.displayName}](${d.domainName}/)${projectLabel}\n\n`;
    content += `${d.description || ''}\n\n`;
    if (d.javaPackage) content += `- **Java 包**: \`${d.javaPackage}\`\n`;
    content += `- **聚合**: ${d.aggregates.length} | **实体**: ${d.entities.length} | **值对象**: ${d.valueObjects.length}\n`;
    content += `- **领域服务**: ${d.domainServices.length} | **领域事件**: ${d.domainEvents.length}\n\n`;

    if (d.aggregates.length > 0) {
      content += '| 聚合 | 聚合根 | 实体 | 值对象 |\n|------|--------|------|--------|\n';
      for (const agg of d.aggregates) {
        if (agg.kind === 'behavior') {
          content += `| **${agg.name}** <span class="behavior-domain">行为域</span> | —（无聚合根） | - | - |\n`;
        } else {
          content += `| [${agg.name}](${d.domainName}/${agg.name}/) | \`${agg.rootEntity?.className || '-'}\` | ${(agg.entities||[]).map(e => `\`${e.className}\``).join(', ') || '-'} | ${(agg.valueObjects||[]).map(v => `\`${v.className}\``).join(', ') || '-'} |\n`;
        }
      }
      content += '\n';
    }
  }

  ensureDir(path.join(DOCS_DIR, 'domain-model'));
  writeMDX(path.join(DOCS_DIR, 'domain-model', 'index.mdx'), {
    title: '🧠 领域模型', description: '所有业务域的领域层模型全景',
  }, content);

  let count = 1;

  for (const d of dmData) {
    let dmContent = `# ${d.displayName} 领域模型\n\n`;
    if (d.projectName) dmContent += `> 所属项目: **${d.projectName}**\n\n`;
    dmContent += `${d.description || ''}\n\n`;

    dmContent += '## 聚合\n\n';
    for (const agg of d.aggregates) {
      const isBehavior = agg.kind === 'behavior';
      const title = isBehavior
        ? `### ${agg.name} <span class="behavior-domain">行为域·无聚合根</span>`
        : `### [${agg.name}](${d.domainName}/${agg.name}/)`;
      dmContent += `<div class="aggregate-card">\n\n${title}\n\n`;
      const re = agg.rootEntity;
      if (re) {
        dmContent += `- **聚合根**: ${srcAbbr(re.className, re.sourcePath, re.sourceLine)} <span class="aggregate-root">Root</span>\n`;
        if (re.methods?.length) dmContent += `- **方法**: ${re.methods.map(m => `\`${m}()\``).join(', ')}\n`;
      }
      if (agg.entities?.length) dmContent += `- **实体**: ${agg.entities.map(e => `\`${e.className}\``).join(', ')}\n`;
      if (agg.valueObjects?.length) dmContent += `- **值对象**: ${agg.valueObjects.map(v => `\`${v.className}\``).join(', ')}\n`;
      if (agg.domainServices?.length) dmContent += `- **领域服务**: ${agg.domainServices.map(s => `\`${s.className}\``).join(', ')}\n`;
      if (isBehavior && d.gateways?.length) dmContent += `- **防腐网关**: ${d.gateways.map(g => `\`${g.className}\``).join(', ')}\n`;
      if (agg.domainEvents?.length) dmContent += `- **领域事件**: ${agg.domainEvents.map(e => `\`${e.className}\``).join(', ')}\n`;
      dmContent += '\n</div>\n\n';
    }

    if (d.entities.length > 0) {
      dmContent += '## 实体\n\n';
      dmContent += '| 类名 | 方法 |\n|------|------|\n';
      for (const e of d.entities) {
        dmContent += `| ${srcAbbr(e.className, e.sourcePath)} | ${(e.methods||[]).slice(0,5).map(m => `\`${m}()\``).join(', ') || '-'} |\n`;
      }
      dmContent += '\n';
    }

    if (d.valueObjects.length > 0) {
      dmContent += '## 值对象\n\n';
      dmContent += '| 类名 | 字段 |\n|------|------|\n';
      for (const vo of d.valueObjects) {
        dmContent += `| ${srcAbbr(vo.className, vo.sourcePath)} | ${(vo.fields||[]).map(f => `\`${f.name}: ${f.type}\``).join(', ') || '-'} |\n`;
      }
      dmContent += '\n';
    }

    if (d.domainEvents.length > 0) {
      dmContent += '## 领域事件\n\n';
      dmContent += '| 事件名 | 来源 |\n|------|------|\n';
      for (const ev of d.domainEvents) {
        dmContent += `| \`${ev.className}\` | \`${ev.sourcePath || '-'}\` |\n`;
      }
      dmContent += '\n';
    }

    ensureDir(path.join(DOCS_DIR, 'domain-model', d.domainName));
    writeMDX(path.join(DOCS_DIR, 'domain-model', d.domainName, 'index.mdx'), {
      title: `${d.displayName} — 领域模型`,
      description: `${d.displayName} 领域模型 · ${d.aggregates.length} 聚合`,
    }, dmContent);
    count++;

    for (const agg of d.aggregates) {
      if (agg.kind === 'behavior') continue;
      generateAggregateDetail(d, agg);
      count++;
    }
  }

  return count;
}

export function generateAggregateDetail(dmData, agg) {
  let content = '';
  content += '> [← 领域模型概览](../) | ';
  content += `[← ${dmData.displayName}](../${dmData.domainName}/)\n\n`;

  const re = agg.rootEntity;

  if (re) {
    content += '## 聚合结构\n\n```mermaid\nclassDiagram\n';
    const rc = re.className || agg.name;
    content += `  class ${rc} {\n    &lt;&lt;Aggregate Root&gt;&gt;\n`;
    for (const f of (re.fields || [])) content += `    +${f.type} ${f.name}\n`;
    content += '  }\n';
    for (const e of (agg.entities || [])) {
      content += `  class ${e.className} {\n    &lt;&lt;Entity&gt;&gt;\n  }\n`;
      content += `  ${rc} "1" --> "*" ${e.className}\n`;
    }
    for (const v of (agg.valueObjects || [])) {
      content += `  class ${v.className} {\n    &lt;&lt;ValueObject&gt;&gt;\n  }\n`;
      content += `  ${rc} --> ${v.className}\n`;
    }
    for (const ev of (agg.domainEvents || [])) {
      if (ev.className) {
        content += `  class ${ev.className} {\n    &lt;&lt;DomainEvent&gt;&gt;\n  }\n`;
        content += `  ${rc} ..> ${ev.className} : emits\n`;
      }
    }
    content += '```\n\n';
  }

  if (re) {
    content += '## 聚合根\n\n';
    content += '| 属性 | 值 |\n|------|----|\n';
    content += `| 类名 | \`${re.className}\` |\n`;
    content += `| 完整限定名 | ${srcAbbr(re.qualifiedName, re.sourcePath)} |\n`;
    if (re.methods?.length) content += `| 方法 | ${re.methods.map(m => `\`${m}()\``).join(', ')} |\n`;
    content += '\n';

    if (re.fields?.length) {
      content += '### 字段\n\n';
      content += '| 字段 | 类型 | 说明 |\n|------|------|------|\n';
      for (const f of re.fields) {
        const kind = { identifier: '标识符', valueObject: '值对象', enum: '枚举', entityCollection: '实体集合' }[f.kind] || '';
        content += `| \`${f.name}\` | \`${f.type}\` | ${kind || f.comment || ''} |\n`;
      }
      content += '\n';
    }
  }

  if (agg.entities?.length) {
    content += '## 实体\n\n';
    for (const e of agg.entities) {
      content += `### \`${e.className}\`\n\n| 属性 | 值 |\n|------|----|\n| 限定名 | ${srcAbbr(e.qualifiedName, e.sourcePath)} |\n`;
      if (e.fields?.length) content += `| 字段 | ${e.fields.map(f => `\`${f.name}: ${f.type}\``).join(', ')} |\n`;
      content += '\n';
    }
  }

  if (agg.valueObjects?.length) {
    content += '## 值对象\n\n';
    for (const vo of agg.valueObjects) {
      content += `### \`${vo.className}\`\n\n| 属性 | 值 |\n|------|----|\n| 限定名 | ${srcAbbr(vo.qualifiedName, vo.sourcePath)} |\n`;
      if (vo.fields?.length) content += `| 字段 | ${vo.fields.map(f => `\`${f.name}: ${f.type}\``).join(', ')} |\n`;
      content += '\n';
    }
  }

  if (agg.domainServices?.length) {
    content += '## 领域服务\n\n';
    for (const ds of agg.domainServices) {
      content += `### \`${ds.className}\`\n\n| 属性 | 值 |\n|------|----|\n| 限定名 | ${srcAbbr(ds.qualifiedName, ds.sourcePath)} |\n`;
      if (ds.methods?.length) content += `| 方法 | ${ds.methods.map(m => `\`${m}()\``).join(', ')} |\n`;
      content += '\n';
    }
  }

  if (agg.domainEvents?.length) {
    content += '## 领域事件\n\n';
    content += '| 事件名 |\n|------|\n';
    for (const ev of agg.domainEvents) {
      content += `| ${srcAbbr(ev.className, ev.sourcePath)} |\n`;
    }
    content += '\n';
  }

  if (dmData.repositoryInterface) {
    const ri = dmData.repositoryInterface;
    content += '## 仓储接口\n\n';
    content += `| 属性 | 值 |\n|------|----|\n| 类名 | \`${ri.className}\` |\n| 限定名 | ${srcAbbr(ri.qualifiedName, ri.sourcePath)} |\n`;
    if (ri.methods?.length) content += `| 方法 | ${ri.methods.map(m => `\`${m}()\``).join(', ')} |\n`;
    content += '\n';
  }

  ensureDir(path.join(DOCS_DIR, 'domain-model', dmData.domainName));
  writeMDX(path.join(DOCS_DIR, 'domain-model', dmData.domainName, `${agg.name}.mdx`), {
    title: `${agg.name} 聚合 — ${dmData.displayName} 领域模型`,
    description: `${dmData.displayName} · ${agg.name} · 聚合根: ${agg.rootEntity?.className || '?'}`,
  }, content);
}

// ── 风险与 ADR 页面 ──

export function generateRisks() {
  const risksFile = path.join(MANIFEST_DIR, 'risks.json');
  if (!fs.existsSync(risksFile)) return 0;
  const risks = readJSON(risksFile);
  if (!risks || !risks.issues || risks.issues.length === 0) return 0;

  const levelLabels = { critical: '🔴 高危', warning: '🟡 警告', info: '🔵 建议' };

  let content = '';
  content += `> 基于 DDD 架构规范自动检测 · ${risks.totalIssues} 个风险项\n\n`;

  content += '<div class="risk-summary">\n';
  content += `  <div class="risk-stat risk-critical"><span class="risk-count">${risks.criticalCount || 0}</span> 高危</div>\n`;
  content += `  <div class="risk-stat risk-warning"><span class="risk-count">${risks.warningCount || 0}</span> 警告</div>\n`;
  content += `  <div class="risk-stat risk-info"><span class="risk-count">${risks.infoCount || 0}</span> 建议</div>\n`;
  content += '</div>\n\n';

  const byRule = {};
  for (const iss of risks.issues) { (byRule[iss.ruleCode] ||= []).push(iss); }

  const ruleNames = {
    DEP_DIRECTION: '依赖方向违规', DOMAIN_PURITY: '领域层纯净度',
    DOMAIN_PURITY_POM: '领域层 POM 纯净度', NAMING: '命名规范',
    ADAPTER_ISOLATION: 'Adapter 隔离', MAVEN_MODULE_DEP: 'Maven 模块依赖',
    CROSS_DOMAIN_DEP: '跨域依赖',
  };

  for (const [ruleCode, issues] of Object.entries(byRule)) {
    const ruleName = ruleNames[ruleCode] || ruleCode;
    const firstLevel = levelLabels[issues[0].level] || '';

    content += `<details class="risk-rule-group" open>\n`;
    content += `<summary>${firstLevel} ${ruleName}（${issues.length} 项）</summary>\n\n`;
    content += '| 级别 | 文件 | 行 | 说明 | 建议 |\n|------|------|----|------|------|\n';

    for (const iss of issues) {
      const level = levelLabels[iss.level] || iss.severity;
      content += `| ${level} | \`${iss.file}:${iss.line}\` | ${iss.line} | ${iss.description} | ${iss.suggestion || '-'} |\n`;
    }
    content += '\n</details>\n\n';
  }

  const byFile = {};
  for (const iss of risks.issues) { (byFile[iss.file] ||= []).push(iss); }

  content += '<details>\n<summary>📁 按文件分组（' + Object.keys(byFile).length + ' 个文件）</summary>\n\n';
  for (const [file, issues] of Object.entries(byFile)) {
    content += `### \`${file}\`\n\n`;
    content += '| 级别 | 行 | 规则 | 说明 |\n|------|----|------|------|\n';
    for (const iss of issues) {
      content += `| ${levelLabels[iss.level] || iss.severity} | ${iss.line} | ${iss.rule} | ${iss.description} |\n`;
    }
    content += '\n';
  }
  content += '</details>\n\n';

  writeMDX(path.join(DOCS_DIR, 'risks.mdx'), {
    title: '⚠️ 架构风险清单', description: `DDD 架构风险 · ${risks.totalIssues} 项`,
  }, content);
  return 1;
}

export function generateAdrPage() {
  const adrFile = path.join(MANIFEST_DIR, 'adrs.json');
  if (!fs.existsSync(adrFile)) return 0;
  const data = readJSON(adrFile);
  const adrs = data?.adrs || [];
  if (adrs.length === 0) return 0;

  const statusLabels = {
    proposed: '💡 提议', accepted: '✅ 已接受', deprecated: '🗑️ 已废弃',
    superseded: '🔄 已替代', rejected: '❌ 已拒绝', draft: '📝 草稿',
  };

  const statusBadge = (s) => {
    const label = statusLabels[s] || `📄 ${s}`;
    return `<span class="adr-status adr-${s}">${label}</span>`;
  };

  let content = '> Architecture Decision Records — 记录关键架构决策及其背景、权衡和后果\n\n';

  for (const adr of adrs) {
    content += `<details class="adr-detail">\n`;
    content += `<summary>#${adr.number || '-'} ${adr.title} ${statusBadge(adr.status || 'draft')}</summary>\n\n`;
    content += '| 属性 | 值 |\n|------|----|\n';
    content += `| 编号 | ${adr.number || '-'} |\n`;
    content += `| 标题 | ${adr.title} |\n`;
    content += `| 状态 | ${adr.status || 'draft'} |\n`;
    content += `| 日期 | ${adr.date || '-'} |\n`;
    content += `| 源文件 | \`${adr.sourcePath || adr.filename || '-'}\` |\n`;
    content += '\n</details>\n\n';
  }

  writeMDX(path.join(DOCS_DIR, 'adr.mdx'), {
    title: '架构决策记录', description: 'Architecture Decision Records',
    tableOfContents: false,
  }, content);
  return 1;
}

// ── 业务全景页面（business-context.json 可选扩展分片）──

export function generateBusinessPage() {
  const bcFile = path.join(MANIFEST_DIR, 'business-context.json');
  if (!fs.existsSync(bcFile)) return 0;
  const bc = readJSONMaybe(bcFile);
  if (!bc) return 0;
  const customers = bc.customers || [];
  const roles = bc.roles || [];
  const scenarios = bc.scenarios || [];
  const flows = bc.flows || [];
  const total = customers.length + roles.length + scenarios.length + flows.length;
  if (total === 0) return 0;

  const srcBadge = (s) =>
    s === 'code' ? '\u{1F916} 代码提取' : s === 'hybrid' ? '\u{1F91D} 人工+锚定' : '\u270D\uFE0F 人工';
  const anchorsInline = (anchors) =>
    (anchors || []).map((a) => '<code>' + a + '</code>').join(' ');

  let content = '> 业务全景 — 客户、角色、业务场景与流程（人工 business-context.md + 代码弱信号）\n\n';

  if (customers.length) {
    content += '## 客户\n\n';
    content += mdTable(
      ['客户', '说明', '代码锚点'],
      customers.map((it) => [
        '**' + it.name + '**',
        it.description || '-',
        anchorsInline(it.anchors) || '-',
      ]),
    ) + '\n\n';
  }

  if (roles.length) {
    content += '## 角色\n\n';
    content += mdTable(
      ['角色', '说明', '来源', '代码锚点'],
      roles.map((it) => [
        '**' + it.name + '**',
        it.description || '-',
        srcBadge(it.source),
        anchorsInline(it.anchors) || '-',
      ]),
    ) + '\n\n';
  }

  // 流程 → 场景归属索引（多对多）：场景卡下挂关联流程锚点链接
  const flowsByScenario = {};
  flows.forEach((f, i) =>
    (f.scenarios || []).forEach((sn) => (flowsByScenario[sn] ||= []).push(i)));

  if (scenarios.length) {
    content += '## 业务场景\n\n';
    for (const s of scenarios) {
      const domainTag = s.domain ? ' \u00B7 `' + s.domain + '` 域' : '';
      content += '### ' + s.name + domainTag + ' ' + srcBadge(s.source) + '\n\n';
      if (s.description) content += s.description + '\n\n';
      if (s.anchors?.length) content += '代码锚点: ' + anchorsInline(s.anchors) + '\n\n';
      if (flowsByScenario[s.name]?.length) {
        content += '**关联流程**: ' +
          flowsByScenario[s.name].map((i) => `[${flows[i].name}](#flow-${i + 1})`).join(' \u00B7 ') + '\n\n';
      }
    }
  }

  if (flows.length) {
    content += '## 业务流程\n\n';
    flows.forEach((f, flowIdx) => {
      const scTag = (f.scenarios?.length ? f.scenarios : ['通用'])
        .map((sn) => '`' + sn + '`').join(' \u00B7 ');
      content += `<a id="flow-${flowIdx + 1}"></a>\n\n`;
      content += '### ' + f.name + ' \u00B7 ' + scTag + ' ' + srcBadge(f.source) + '\n\n';
      if (f.description) content += f.description + '\n\n';
      // 人工/混合流程：Mermaid 流程图（步骤序 → 节点链）；code 流程不画（状态机页已有 stateDiagram）
      if (f.source !== 'code' && f.steps?.length > 1) {
        const escNode = (t) =>
          String(t).replace(/"/g, '#quot;').replace(/[\r\n]+/g, ' ').trim();
        const nodeLines = f.steps.map((st, i) => `    s${i + 1}["${i + 1}. ${escNode(st.name)}"]`);
        const edgeLines = f.steps.slice(1).map((_, i) => `    s${i + 1} --> s${i + 2}`);
        content += '```mermaid\nflowchart TD\n' + nodeLines.concat(edgeLines).join('\n') + '\n```\n\n';
      }
      if (f.steps?.length) {
        const lines = f.steps.map((st, i) => {
          let line = (i + 1) + '. **' + st.name + '**';
          if (st.description) line += '：' + st.description;
          if (st.anchors?.length) {
            line += ' → `' + st.anchors.join('` `') + '`';
          }
          return line;
        });
        content += lines.join('\n') + '\n\n';
      }
      if (f.anchors?.length) {
        content += '代码锚点: ' + anchorsInline(f.anchors) + '\n\n';
      }
      if (f.source === 'code' && fs.existsSync(path.join(MANIFEST_DIR, 'state-machines.json'))) {
        content += '> 🤖 本流程由状态机代码提取，完整状态转换图与质量审查见[状态机](/state-machine/)。\n\n';
      }
    });
    if (fs.existsSync(path.join(MANIFEST_DIR, 'state-machines.json'))) {
      content += '> 流程中状态流转的技术细节（stateDiagram + 死状态/不可达审查）见[状态机](/state-machine/)。\n\n';
    }
  }

  writeMDX(path.join(DOCS_DIR, 'business.mdx'), {
    title: '业务全景',
    description: '客户、角色、业务场景与业务流程',
  }, content);
  return 1;
}

// ── 跨项目链路页面（cross-project.json，鹰眼聚合产物）──

export function generateCrossProjectPage() {
  const cpFile = path.join(MANIFEST_DIR, 'cross-project.json');
  if (!fs.existsSync(cpFile)) return 0;
  const cp = readJSONMaybe(cpFile);
  const edges = cp?.edges || [];
  if (edges.length === 0) return 0;
  const st = cp.stats || {};

  let content = `> 跨项目真实链路 · ${edges.length} 条边（HTTP/Feign 签名对齐 + MQ 通道 + DB 共享表 + 缓存 key；confirmed=双侧证据 / inferred=推断）\n\n`;
  content += '<div class="risk-summary">\n';
  content += `  <div class="risk-stat risk-critical"><span class="risk-count">${st.confirmed || 0}</span> confirmed</div>\n`;
  content += `  <div class="risk-stat risk-warning"><span class="risk-count">${st.inferred || 0}</span> inferred</div>\n`;
  content += `  <div class="risk-stat risk-info"><span class="risk-count">${st.sharedTables || 0}</span> 共享表</div>\n`;
  content += `  <div class="risk-stat risk-info"><span class="risk-count">${Object.keys(st.unmatchedByService || {}).length}</span> 池外服务</div>\n`;
  content += '</div>\n\n';

  content += '## 链路边清单\n\n';
  content += mdTable(
    ['置信', '类型', 'from → to', '证据'],
    edges.map((e) => [
      e.confidence === 'confirmed' ? '✅ confirmed' : '⚠️ inferred',
      e.type || 'http',
      `${e.from} → ${e.to}`,
      e.type === 'db'
        ? `共享表 <code>${e.evidence?.table || ''}</code>`
        : `<code>${e.evidence?.consumer?.call || (e.evidence?.keys || []).join(' ')}</code>`,
    ]),
  ) + '\n\n';

  if (st.unmatchedByService && Object.keys(st.unmatchedByService).length) {
    content += '## 池外服务（被调用但未接入鹰眼）\n\n';
    content += mdTable(
      ['服务', '未命中调用数'],
      Object.entries(st.unmatchedByService).slice(0, 20).map(([svc, n]) => [svc, String(n)]),
    ) + '\n\n';
  }

  writeMDX(path.join(DOCS_DIR, 'cross-project.mdx'), {
    title: '跨项目链路',
    description: '跨项目真实调用/共享证据（confirmed/inferred）',
  }, content);
  return 1;
}

// ── 治理仪表盘页面（governance.json，E03）──

export function generateGovernancePage() {
  const govFile = path.join(MANIFEST_DIR, 'governance.json');
  if (!fs.existsSync(govFile)) return 0;
  const gov = readJSONMaybe(govFile);
  const projects = gov?.projects || [];
  if (projects.length === 0) return 0;

  const statusLabels = { pending: '⏳ 待处理', 'in-progress': '🔧 进行中',
                         repaid: '✅ 已偿还', exempt: '📋 已豁免' };
  let content = '> 治理仪表盘 — 基线趋势 / 债务归属 / 超期告警（数据源：各项目 baselines + debt-ledger）\n\n';

  for (const proj of projects) {
    content += `## ${proj.projectName || proj.projectId}\n\n`;
    if (proj.baselines?.length) {
      content += mdTable(
        ['基线', '冻结时间', '违规数', 'revision'],
        proj.baselines.map((b) => [b.name || '-', (b.createdAt || '').slice(0, 10),
                                   String(b.totalIssues ?? '-'), (b.revision || '').slice(0, 8)]),
      ) + '\n\n';
    }
    const debts = proj.debts || [];
    if (debts.length) {
      const byStatus = {};
      for (const d of debts) byStatus[d.status] = (byStatus[d.status] || 0) + 1;
      content += `**债务 ${debts.length} 条**：` + Object.entries(byStatus)
        .map(([k, v]) => `${statusLabels[k] || k} ${v}`).join(' · ') + '\n\n';
      content += mdTable(
        ['fingerprint', '严重度', '文件', '归属人', '状态'],
        debts.slice(0, 20).map((d) => [
          `<code>${String(d.fingerprint || '').slice(0, 8)}</code>`,
          d.severity || '-', d.file || '-', d.owner || 'unknown',
          statusLabels[d.status] || d.status,
        ]),
      ) + '\n\n';
    } else {
      content += '_未接入治理（无债务登记）_\n\n';
    }
  }

  writeMDX(path.join(DOCS_DIR, 'governance.mdx'), {
    title: '治理仪表盘',
    description: '基线 / 债务 / 超期全景（E03）',
  }, content);
  return 1;
}

// ── 状态机页面 ──

export function generateStateMachines() {
  const smFile = path.join(MANIFEST_DIR, 'state-machines.json');
  if (!fs.existsSync(smFile)) return 0;
  const sms = readJSON(smFile);
  if (!Array.isArray(sms) || sms.length === 0) return 0;

  const diagrams = readJSONMaybe(path.join(MANIFEST_DIR, 'diagrams.json')) || {};
  const smDiagrams = diagrams?.stateMachines || {};

  const frameworkLabels = {
    raw: '裸 enum', spring: 'Spring StateMachine', cola: 'Cola Statemachine',
  };
  const fwBadge = (f) => `<span class="layer-badge domain">${frameworkLabels[f] || f}</span>`;
  const sevLabels = { critical: '🔴 高危', warning: '🟡 警告', info: '🔵 建议' };

  const totalStates = sms.reduce((s, sm) => s + (sm.states?.length || 0), 0);
  const totalIssues = sms.reduce((s, sm) => s + (sm.issues?.length || 0), 0);

  let content = `> 枚举状态机全景 · ${sms.length} 个状态机（自动识别 raw/spring/cola 框架，含状态转换图与质量审查）\n\n`;
  if (fs.existsSync(path.join(MANIFEST_DIR, 'business-context.json'))) {
    content += '> 业务视角（客户/角色/场景/流程叙事）见[业务全景](/business/)；本页聚焦状态流转的工程审查。\n\n';
  }
  content += '<div class="risk-summary">\n';
  content += `  <div class="risk-stat risk-info"><span class="risk-count">${sms.length}</span> 状态机</div>\n`;
  content += `  <div class="risk-stat risk-warning"><span class="risk-count">${totalStates}</span> 状态</div>\n`;
  content += `  <div class="risk-stat risk-critical"><span class="risk-count">${totalIssues}</span> 审查项</div>\n`;
  content += '</div>\n\n';

  const inferSmDomain = (n) => { for (const [re, d] of SM_DOMAIN) if (re.test(n)) return d; return '其他'; };
  const smByDomain = {};
  for (const sm of sms) (smByDomain[inferSmDomain(sm.name)] ||= []).push(sm);

  for (const [smDomain, smList] of Object.entries(smByDomain)) {
    content += `## 📂 ${smDomain}（${smList.length}）\n\n`;
    for (const sm of smList) {
      const states = sm.states || [];
      const initials = sm.initialState ? [sm.initialState] : [];
      const ends = sm.endStates || [];
      const trans = sm.transitions || [];
      const issues = sm.issues || [];

      content += `### ${sm.name} ${fwBadge(sm.framework)}\n\n`;
      content += '| 属性 | 值 |\n|------|----|\n';
      content += `| 源类 | \`${sm.sourceClass || sm.name}\` |\n`;
      content += `| 源文件 | \`${sm.sourcePath || '-'}\` |\n`;
      content += `| 状态数 | ${states.length} |\n`;
      content += `| 初始态 | ${sm.initialState ? '`' + sm.initialState + '`' : '—（未标注）'} |\n`;
      content += `| 终态 | ${ends.length ? ends.map((e) => '`' + e + '`').join('、') : '—'} |\n`;
      if (sm.managedEnum) content += `| 管理枚举 | \`${sm.managedEnum}\` |\n`;
      content += '\n';

      const diagram = smDiagrams[sm.name];
      if (diagram && diagram.trim()) {
        content += '#### 状态转换图\n\n```mermaid\n' + diagram.trim() + '\n```\n\n';
      }

      if (states.length) {
        content += '#### 状态清单\n\n| 状态 | 类型 |\n|------|------|\n';
        for (const st of states) {
          const type = initials.includes(st) ? '★ 初始态' : ends.includes(st) ? '⚑ 终态' : '中间态';
          content += `| \`${st}\` | ${type} |\n`;
        }
        content += '\n';
      }

      if (trans.length) {
        content += '#### 状态转换\n\n| 起点 | 终点 | 事件 | 守卫 |\n|------|------|------|------|\n';
        for (const t of trans) {
          content += `| \`${t.source || '-'}\` | \`${t.target || '-'}\` | ${t.event || '-'} | ${t.guard || '-'} |\n`;
        }
        content += '\n';
      }

      if (issues.length) {
        content += `<details>\n<summary>🔍 质量审查（${issues.length} 项）</summary>\n\n`;
        content += '| 级别 | 说明 |\n|------|------|\n';
        for (const iss of issues) {
          content += `| ${sevLabels[iss.severity] || iss.severity} | ${iss.message} |\n`;
        }
        content += '\n</details>\n\n';
      }
    }
  }

  writeMDX(path.join(DOCS_DIR, 'state-machine.mdx'), {
    title: '🔀 状态机', description: `枚举状态机 · ${sms.length} 个`,
  }, content);
  return 1;
}

// ── 多项目全景页面 ──

export function generateProjectPanorama(manifest) {
  const projects = manifest._index?.projects || [];
  const project = manifest._index?.project || {};
  let content = '';
  content += `${project.description || ''}\n\n`;

  content += '<div class="hero-section">\n';
  content += `  <h1>🦅 ${project.name || '架构鹰眼'}</h1>\n`;
  content += `  <p>${project.description || '全公司 DDD 架构全景视图 — 自动从代码生成'}</p>\n`;
  content += '  <div class="hero-stats">\n';
  const totalDomains = projects.reduce((s,p) => s + (p.domainCount||0), 0);
  const totalComps = projects.reduce((s,p) => s + (p.componentCount||0), 0);
  const totalTables = projects.reduce((s,p) => s + (p.tableCount||0), 0);
  content += `    <div class="hero-stat"><div class="hero-stat-number">${projects.length}</div><div class="hero-stat-label">项目</div></div>\n`;
  content += `    <div class="hero-stat"><div class="hero-stat-number">${totalDomains}</div><div class="hero-stat-label">业务域</div></div>\n`;
  content += `    <div class="hero-stat"><div class="hero-stat-number">${totalComps}</div><div class="hero-stat-label">组件</div></div>\n`;
  content += `    <div class="hero-stat"><div class="hero-stat-number">${totalTables}</div><div class="hero-stat-label">数据表</div></div>\n`;
  content += '  </div>\n</div>\n\n';

  content += '## 项目拓扑\n\n';
  content += '<div class="panorama-container">\n\n';
  content += '```mermaid\n' + (manifest.diagrams?.architectureOverview || '') + '\n```\n\n';
  content += '</div>\n\n';

  if (manifest.diagrams?.crossProjectDependencies) {
    content += '## 项目间依赖\n\n';
    content += '```mermaid\n' + manifest.diagrams.crossProjectDependencies + '\n```\n\n';
  }

  content += '## 项目列表\n\n<div class="project-dashboard">\n';
  for (const proj of projects) {
    content += `<div class="project-card">\n`;
    content += `  <h3><a href="/projects/${proj.id}/">📁 ${proj.name}</a></h3>\n`;
    if (proj.description) content += `  <p>${proj.description}</p>\n`;
    content += '  <div class="project-card-meta">\n';
    content += `    <span class="project-stat">📦 ${proj.domainCount||0} 域</span>\n`;
    content += `    <span class="project-stat">⚙️ ${proj.componentCount||0} 组件</span>\n`;
    content += `    <span class="project-stat">🗄️ ${proj.tableCount||0} 表</span>\n`;
    if (proj.repo) content += `    <span class="project-stat">🔗 <a href="${proj.repo}">仓库</a></span>\n`;
    content += '  </div>\n</div>\n';
  }
  content += '</div>\n\n';

  ensureDir(path.join(DOCS_DIR, 'projects'));
  writeMDX(path.join(DOCS_DIR, 'projects', 'index.mdx'), {
    title: '🏢 公司架构全景', description: project.description || '',
  }, content);
}

// ── 影响分析（/impact/ 交互页）───────────────────────────────────────────────
// 客户端 BFS：manifest 组件 deps 边 + 注解边界匹配，分级语义与
// impact-guard CLI（critical_ranker.py）对齐。纯静态站点的"实时"=
// 前端计算，依赖 dist/doc-manifest/ 的可 fetch 分片。

export function generateImpactPage() {
  const content = `> 输入变更组件（qualified_name 或类名，支持模糊匹配），实时计算影响链与回归范围。
> 分级语义与 \`impact-guard\` CLI 对齐：🔴直接（出站/落点）· 🟠间接（链抵达入口）· 🟡入口/领域层 · 🟢内部实现。
> 数据为构建时快照（类级 Tier 1 精度）；精确门禁请用 \`impact_check.py --strict\`。

<div id="impact-tool">
  <input id="impact-input" list="impact-datalist" placeholder="如 OrderCreateCmdExe 或完整限定名"
         style="width:60%;padding:0.5rem 0.75rem;border:1px solid var(--sl-color-gray-5);border-radius:0.5rem;background:var(--sl-color-black);color:var(--sl-color-white)" />
  <datalist id="impact-datalist"></datalist>
  <button id="impact-run" class="sl-button" style="padding:0.5rem 1rem">分析</button>
</div>
<div id="impact-result" style="margin-top:1.5rem"><p><small>💡 在上方输入组件名（支持模糊匹配，输入框有候选提示），点击「分析」查看影响链与回归范围。</small></p></div>
<script src="/impact.js"></script>
`;
  writeMDX(path.join(DOCS_DIR, 'impact.mdx'), {
    title: '🎯 变更影响分析', description: '输入变更组件，实时计算影响链与回归范围',
  }, content);
  return 1;
}

// ── 架构演进（delta）──────────────────────────────────────────────────────────
// 数据来源：doc_gen.py diff 生成 delta.json 后放入 doc-manifest/。
// 信噪比契约与 Python 端 render_markdown 一致：presentation-changed 不计入
// summary、不列入明细（Javadoc 措辞噪声不进演进报告）。

const DELTA_STATUS_LABELS = {
  added: '新增', removed: '移除', changed: '变更', moved: '迁移',
  'presentation-changed': '文档措辞',
};
const DELTA_DIM_TITLES = {
  components: '组件', aggregates: '聚合', tables: '数据表',
  stateMachines: '状态机', crossDomain: '跨域依赖', openapi: 'API 端点',
};

function _deltaStatusBadge(status) {
  const cls = { added: 'ok', removed: 'critical', changed: 'warning',
                moved: 'info' }[status] || 'info';
  return `<span class="layer-badge ${cls}">${DELTA_STATUS_LABELS[status] || status}</span>`;
}

function _shortSha(revision) {
  return revision ? revision.slice(0, 12) : '?';
}

// Mermaid 节点 id 必须去除点号/特殊字符（qualifiedName 含点），用索引 id + label 展示
const DELTA_STATUS_EMOJI = {
  added: '✨', removed: '🗑️', changed: '✏️', moved: '🚚',
};

function _mermaidId(s) {
  return String(s).replace(/[^a-zA-Z0-9_]/g, '_');
}

function _mermaidEsc(s) {
  return String(s).replace(/["<>{}|]/g, ' ');
}

// 组件变化焦点图：只画变化实体（delta.json 不含完整快照，全景图数据不支持）。
// subgraph = domain/layer，classDef 按状态着色；moved 节点置于新位置并标注来源。
function _deltaComponentGraph(entries) {
  const sig = ['added', 'removed', 'changed', 'moved'];
  const relevant = entries.filter(c => sig.includes(c.status));
  if (!relevant.length) return null;

  const lines = ['flowchart LR'];
  for (const [status, color] of Object.entries({
    added: 'fill:#16a34a,color:#fff',
    removed: 'fill:#dc2626,color:#fff',
    changed: 'fill:#d97706,color:#fff',
    moved: 'fill:#2563eb,color:#fff',
  })) {
    lines.push(`  classDef ${status} ${color}`);
  }

  const groups = new Map();  // location -> [{node, cls}]
  relevant.forEach((c, i) => {
    const loc = c.location || c.wasLocation || 'unknown';
    if (!groups.has(loc)) groups.set(loc, []);
    let label = `${DELTA_STATUS_EMOJI[c.status] || ''} ${_mermaidEsc(c.className || c.id)}`;
    if (c.status === 'moved' && c.changedFields?.length) {
      // moved: 标注迁移路径（changedFields[0] 为 "原位置 → 新位置"）
      label += `<br/>from ${_mermaidEsc(c.changedFields[0].split('→')[0].trim())}`;
      if (c.inferred) label += ' (推断)';
    }
    groups.get(loc).push(`    n${i}["${label}"]:::${c.status}`);
  });

  let g = 0;
  for (const [loc, nodes] of groups) {
    lines.push(`  subgraph SG${g++}["${_mermaidEsc(loc)}"]`);
    lines.push(...nodes);
    lines.push('  end');
  }
  return lines.join('\n');
}

// 跨域依赖变化图：域为节点、依赖为边，边按增删着色（天然图形态）。
function _deltaCrossDomainGraph(entries) {
  const relevant = entries.filter(c => c.status === 'added' || c.status === 'removed');
  if (!relevant.length) return null;

  const lines = ['flowchart LR'];
  for (const c of relevant) {
    // id 形如 "order→logistics:client-api"
    const [pair, type] = c.id.split(':');
    const [from, to] = pair.split('→');
    lines.push(`  ${_mermaidId(from)}["${_mermaidEsc(from)}"]`);
    lines.push(`  ${_mermaidId(to)}["${_mermaidEsc(to)}"]`);
    const emoji = c.status === 'added' ? '✨' : '🗑️';
    const style = c.status === 'added'
      ? 'stroke:#16a34a,stroke-width:2px' : 'stroke:#dc2626,stroke-width:2px';
    const idx = lines.filter(l => l.includes('-->')).length;
    lines.push(`  ${_mermaidId(from)} -->|"${emoji} ${_mermaidEsc(type || 'dep')}"| ${_mermaidId(to)}`);
    lines.push(`  linkStyle ${idx} ${style}`);
  }
  return lines.join('\n');
}

export function generateDeltaPage() {
  const deltaFile = path.join(MANIFEST_DIR, 'delta.json');
  if (!fs.existsSync(deltaFile)) return 0;
  let delta;
  try { delta = readJSON(deltaFile); } catch { return 0; }
  if (!delta?.summary) return 0;

  const s = delta.summary;
  const totals = { added: 0, removed: 0, changed: 0, moved: 0 };
  for (const [, d] of Object.entries(s)) {
    for (const k of Object.keys(totals)) totals[k] += d[k] || 0;
  }

  let content = `> 架构演进实证 · \`${_shortSha(delta.base?.revision)}\` → \`${_shortSha(delta.head?.revision)}\`（revision-pinned，代码演进不漂移）\n\n`;

  content += '<div class="risk-summary">\n';
  content += `  <div class="risk-stat risk-info"><span class="risk-count">${totals.added}</span> 新增</div>\n`;
  content += `  <div class="risk-stat risk-critical"><span class="risk-count">${totals.removed}</span> 移除</div>\n`;
  content += `  <div class="risk-stat risk-warning"><span class="risk-count">${totals.changed}</span> 变更</div>\n`;
  content += `  <div class="risk-stat risk-ok"><span class="risk-count">${totals.moved}</span> 迁移</div>\n`;
  content += '</div>\n\n';

  content += '| 维度 | 新增 | 移除 | 变更 | 迁移 |\n| --- | --- | --- | --- | --- |\n';
  for (const [dim, title] of Object.entries(DELTA_DIM_TITLES)) {
    const d = s[dim] || {};
    if (dim === 'openapi') {
      content += `| ${title} | ${d.added || 0} | ${d.removed || 0} | - | - |\n`;
    } else {
      content += `| ${title} | ${d.added || 0} | ${d.removed || 0} | ${d.changed || 0} | ${d.moved || 0} |\n`;
    }
  }
  content += '\n';

  // 变化焦点图（只画变化实体；颜色即状态：绿=新增 红=移除 黄=变更 蓝=迁移）
  const compGraph = _deltaComponentGraph(delta.changes?.components || []);
  if (compGraph) {
    content += '## 组件变化图\n\n```mermaid\n' + compGraph + '\n```\n\n';
  }
  const cdGraph = _deltaCrossDomainGraph(delta.changes?.crossDomain || []);
  if (cdGraph) {
    content += '## 跨域依赖变化图\n\n```mermaid\n' + cdGraph + '\n```\n\n';
  }

  const dimOrder = ['components', 'aggregates', 'tables', 'stateMachines', 'crossDomain'];
  for (const dim of dimOrder) {
    const entries = (delta.changes?.[dim] || []).filter(c => c.status !== 'presentation-changed');
    if (!entries.length) continue;
    content += `## ${DELTA_DIM_TITLES[dim]}（${entries.length}）\n\n`;
    for (const c of entries) {
      const inferred = c.inferred ? ' <em>(推断)</em>' : '';
      let detail = '';
      if (c.status === 'moved' && c.changedFields?.length) {
        detail = ` — <code>${c.changedFields[0].replace(/</g, '&lt;')}</code>`;
      } else if (c.status === 'changed' && c.changedFields?.length) {
        detail = ` — ${c.changedFields.map(f => `<code>${f.slice(1)}</code>`).join(', ')}`;
      }
      const loc = c.location || c.wasLocation || '';
      content += `- ${_deltaStatusBadge(c.status)} <code>${c.className || c.id}</code>${inferred}${loc ? `（${loc}）` : ''}${detail}\n`;
    }
    content += '\n';
  }

  const oa = delta.openapi || { added: [], removed: [] };
  if (oa.added?.length || oa.removed?.length) {
    content += '## API 端点\n\n';
    for (const [m, p] of oa.added || []) content += `- ${_deltaStatusBadge('added')} <code>${m} ${p}</code>\n`;
    for (const [m, p] of oa.removed || []) content += `- ${_deltaStatusBadge('removed')} <code>${m} ${p}</code>\n`;
    content += '\n';
  }

  const grand = totals.added + totals.removed + totals.changed + totals.moved;
  content += grand === 0
    ? '> ✅ 该区间架构零变化。\n'
    : `> 共 ${grand} 处架构变化；文档措辞变化（presentation-changed）未计入。\n`;

  writeMDX(path.join(DOCS_DIR, 'evolution.mdx'), {
    title: '🔀 架构演进', description: '两份 manifest 快照的架构演进 delta',
  }, content);
  return 1;
}
