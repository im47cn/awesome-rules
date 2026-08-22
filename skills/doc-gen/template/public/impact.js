/**
 * impact.js — /impact/ 页客户端影响分析（impact-guard v1.1 站点内嵌）
 *
 * 数据源：dist/doc-manifest/domains/*.json（组件 deps 依赖边 + annotations）
 * 分级语义与 skills/impact-guard/scripts/critical_ranker.py 对齐：
 *   入口组件（Controller/Listener/Job）→ 影响不可分析 + 下游回归树
 *   出站/落点（Feign/Mapper/Redis）→ 🔴 DIRECT（+跨服务告警）
 *   inbound 链抵达入口 → 🟠 INDIRECT + 回归范围
 *   领域层/实体 → 🟡 WARNING；其余 → 🟢 INFO
 */

// 5 通道边界模式（对齐 impact-guard boundary_scanner.DEFAULT_BOUNDARY_PATTERNS）
const ENTRY_PATTERNS = {
  http: ['RestController', 'Controller'],
  mq: ['RocketMQMessageListener', 'KafkaListener'],
  job: ['XxlJob'],
};
const EXIT_PATTERNS = {
  http: ['FeignClient'],
  db: ['Mapper'],
};

const state = { graph: null, loading: false };

// ── 纯函数（node 冒烟可断言）────────────────────────────────────────────────

function buildGraph(domainFiles) {
  const nodes = new Map();   // qn -> {className, annotations, layer, domain}
  const forward = new Map(); // qn -> Set(qn)
  const reverse = new Map(); // qn -> Set(qn)
  for (const { domain, data } of domainFiles) {
    for (const [layerName, layer] of Object.entries(data.layers || {})) {
      for (const c of layer.components || []) {
        const qn = c.qualifiedName || c.className;
        if (!qn) continue;
        nodes.set(qn, { className: c.className, annotations: c.annotations || [],
                        layer: layerName, domain, componentType: c.type || '' });
        for (const dep of c.deps || []) {
          // 边先记（跨域依赖的节点稍后在其他域文件遍历时补全）
          (forward.get(qn) || forward.set(qn, new Set()).get(qn)).add(dep);
          (reverse.get(dep) || reverse.set(dep, new Set()).get(dep)).add(qn);
        }
      }
      for (const agg of layer.aggregates || []) {
        for (const key of ['rootEntity', 'entities', 'valueObjects']) {
          const v = agg[key];
          const comps = Array.isArray(v) ? v : (v ? [v] : []);
          for (const c of comps) {
            const qn = c.qualifiedName || c.className;
            if (qn && !nodes.has(qn)) {
              nodes.set(qn, { className: c.className, annotations: [],
                              layer: layerName, domain, componentType: c.type || '' });
            }
          }
        }
      }
    }
  }
  return { nodes, forward, reverse };
}

function matchChannel(annotations, patterns) {
  for (const [ch, pats] of Object.entries(patterns)) {
    if (annotations.some(a => pats.some(p => a.includes(p)))) return ch;
  }
  return null;
}

function bfs(graph, start, index, depth) {
  const found = new Map();   // qn -> {depth, path}
  let frontier = [[start, [start]]];
  const visited = new Set([start]);
  for (let hop = 1; hop <= depth; hop++) {
    const next = [];
    for (const [qn, path] of frontier) {
      for (const nb of (index.get(qn) || new Set())) {
        if (visited.has(nb) || !graph.nodes.has(nb)) continue;
        visited.add(nb);
        found.set(nb, { depth: hop, path: [...path, nb] });
        next.push([nb, [...path, nb]]);
      }
    }
    frontier = next;
    if (!frontier.length) break;
  }
  return found;
}

function analyze(graph, qn, depth = 3) {
  const node = graph.nodes.get(qn);
  if (!node) return { error: `未找到组件: ${qn}` };
  const annos = node.annotations;

  const entryCh = matchChannel(annos, ENTRY_PATTERNS);
  if (entryCh) {
    const out = bfs(graph, qn, graph.forward, depth);
    return { level: 'WARNING', isEntry: true, entryChannel: entryCh,
             reasons: [`框架入口（${entryCh}），inbound 不可见，给出回归范围而非影响分析`],
             impacts: [], regressionScope: [...out.keys()] };
  }

  const exitCh = matchChannel(annos, EXIT_PATTERNS);
  if (exitCh) {
    const impacts = bfs(graph, qn, graph.reverse, depth);
    const cross = annos.some(a => a.includes('FeignClient'));
    const reasons = [`变更点是出站/落点（${exitCh}）`];
    if (cross) reasons.push('跨服务契约（@FeignClient）— ⚠️ 跨服务影响未分析');
    return { level: 'DIRECT', reasons, impacts: [...impacts.values()],
             regressionScope: [], crossService: cross };
  }

  const impacts = bfs(graph, qn, graph.reverse, depth);
  const entriesHit = [...impacts.entries()].filter(
    ([n]) => matchChannel(graph.nodes.get(n).annotations, ENTRY_PATTERNS));
  const reasons = [];
  let level = 'INFO';
  if (entriesHit.length) {
    level = 'INDIRECT';
    reasons.push(`影响链 ${entriesHit[0][1].depth} 跳抵达入口`);
  }
  if (node.layer === 'domain' || node.componentType === 'entity') {
    if (level === 'INFO') level = 'WARNING';
    reasons.push('触及聚合根/领域层');
  }
  return { level, reasons, impacts: [...impacts.values()],
           regressionScope: entriesHit.map(([n]) => n) };
}

function toMermaid(qn, analysis) {
  const lines = ['flowchart RL'];
  const icons = { DIRECT: '🔴', INDIRECT: '🟠', WARNING: '🟡', INFO: '🟢' };
  const mm = (s) => String(s).replace(/[^a-zA-Z0-9_]/g, '_');
  const short = (s) => s.split('.').pop();
  lines.push(`  ${mm(qn)}[["${short(qn)} [CHANGED]"]]:::changed`);
  lines.push('  classDef changed fill:#dc2626,color:#fff,stroke-width:3px');
  lines.push('  classDef entry fill:#7c3aed,color:#fff');
  lines.push('  classDef info fill:#16a34a,color:#fff');
  const entrySet = new Set(analysis.regressionScope);
  for (const n of analysis.impacts.slice(0, 25)) {
    const isEntry = entrySet.has(n.path[n.path.length - 1]);
    lines.push(`  ${mm(n.path[n.path.length - 1])}["${short(n.path[n.path.length - 1])}${isEntry ? ' 🚪' : ''}"]:::${isEntry ? 'entry' : 'info'}`);
    // 边：只画相邻跳（path 相邻对）
    for (let i = 0; i + 1 < n.path.length; i++) {
      lines.push(`  ${mm(n.path[i])} -.-> ${mm(n.path[i + 1])}`);
    }
    if (n.path.length > 1) {
      lines.push(`  ${mm(n.path[n.path.length - 2])} -.-> ${mm(qn)}`);
    }
  }
  lines.push(`  %% ${icons[analysis.level]} ${analysis.level}`);
  return lines.join('\n');
}

// ── UI 编排（浏览器）────────────────────────────────────────────────────────

async function loadGraph() {
  if (state.graph || state.loading) return state.graph;
  state.loading = true;
  try {
    const index = await fetch('/doc-manifest/index.json').then(r => r.json());
    const domainFiles = await Promise.all(
      (index.domains || []).map(async d => ({
        domain: d.name,
        data: await fetch(`/doc-manifest/${d.file}`).then(r => r.json()),
      })));
    state.graph = buildGraph(domainFiles);
  } finally {
    state.loading = false;
  }
  return state.graph;
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function runAnalysis() {
  const input = document.getElementById('impact-input');
  const out = document.getElementById('impact-result');
  const graph = await loadGraph();
  if (!graph) { out.innerHTML = '<p>⚠️ manifest 数据加载失败</p>'; return; }
  const q = input.value.trim();
  if (!q) return;
  // 模糊匹配：类名精确 > 类名包含 > qn 包含
  const qn = graph.nodes.has(q) ? q
    : ([...graph.nodes.keys()].find(k => k.endsWith('.' + q))
       || [...graph.nodes.keys()].find(k => k.includes(q)));
  if (!qn) {
    out.innerHTML = `<p>❌ 未匹配到组件：<code>${esc(q)}</code></p>`;
    return;
  }
  const analysis = analyze(graph, qn, 3);
  const icons = { DIRECT: '🔴', INDIRECT: '🟠', WARNING: '🟡', INFO: '🟢' };
  let html = `<h2>${icons[analysis.level] || ''} ${esc(qn)}</h2>`;
  html += `<p>级别 <strong>${analysis.level}</strong>（${analysis.reasons.map(esc).join('；') || '仅内部实现'}）</p>`;
  if (analysis.impacts.length) {
    html += `<h3>影响链（${analysis.impacts.length} 类）</h3><ul>`;
    for (const n of analysis.impacts.slice(0, 15)) {
      const node = graph.nodes.get(n.path[n.path.length - 1]);
      html += `<li>d${n.depth} <code>${esc(n.path[n.path.length - 1])}</code>` +
              `（${node ? esc(node.domain + '/' + node.layer) : '?'}）` +
              ` <small>${n.path.map(p => esc(p.split('.').pop())).join(' → ')}</small></li>`;
    }
    html += '</ul>';
  }
  if (analysis.regressionScope.length) {
    html += `<h3>回归范围（${analysis.regressionScope.length}）</h3><p>` +
            analysis.regressionScope.slice(0, 12).map(esc).join(', ') + '</p>';
  }
  html += '<div class="mermaid">' + esc(toMermaid(qn, analysis)) + '</div>';
  html += '<p><small>分级语义与 impact-guard CLI 对齐（Tier 1 类级）；精确门禁请用 ' +
          '<code>impact_check.py --strict</code></small></p>';
  out.innerHTML = html;
  if (window.mermaid) window.mermaid.run({ nodes: [out.querySelector('.mermaid')] });
}

if (typeof document !== 'undefined') {
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('impact-input');
  if (!input) return;
  input.addEventListener('keydown', e => { if (e.key === 'Enter') runAnalysis(); });
  document.getElementById('impact-run')?.addEventListener('click', runAnalysis);
  loadGraph().then(g => {
    if (!g) return;
    const dl = document.getElementById('impact-datalist');
    for (const qn of [...g.nodes.keys()].slice(0, 500)) {
      const opt = document.createElement('option');
      opt.value = qn; opt.label = qn.split('.').pop();
      dl.appendChild(opt);
    }
  });
});
}

// node 冒烟导出
if (typeof module !== 'undefined') {
  module.exports = { buildGraph, analyze, matchChannel, toMermaid };
}
