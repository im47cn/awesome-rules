/**
 * lib/utils.mjs — 共享工具函数与常量
 *
 * 从 generate-pages.mjs 提取，供各页面生成器模块使用。
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
// 环境变量覆盖：供 pytest 冒烟（test_smoke_pages.py）与 CI 在临时目录运行，不污染模板
const DOCS_DIR = process.env.DOCGEN_DOCS_DIR || path.join(ROOT, 'src', 'content', 'docs');
const MANIFEST_DIR = process.env.DOCGEN_MANIFEST_DIR || path.join(ROOT, 'doc-manifest');
const LEGACY_MANIFEST = path.join(ROOT, 'doc-manifest.json');

// ── 工具函数 ──

export function ensureDir(dir) { fs.mkdirSync(dir, { recursive: true }); }

export function writeMDX(filePath, frontmatter, content) {
  // 支持 string/number/boolean/对象(YAML 嵌套)/数组，用于 hero 等 frontmatter 字段。
  const fmt = (v) => {
    if (typeof v === 'string') return `"${v.replace(/"/g, '\\"')}"`;
    if (typeof v === 'number' || typeof v === 'boolean') return String(v);
    if (Array.isArray(v)) {
      return v.length
        ? '\n' + v.map((i) => `  - ${typeof i === 'object' && i !== null ? JSON.stringify(i) : fmt(i)}`).join('\n')
        : '[]';
    }
    if (v !== null && typeof v === 'object') {
      return '\n' + Object.entries(v).map(([k, val]) => `  ${k}: ${fmt(val)}`).join('\n');
    }
    return '';
  };
  const fm = Object.entries(frontmatter).map(([k, v]) => `${k}: ${fmt(v)}`).join('\n');
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, `---\n${fm}\n---\n\n${content}`, 'utf-8');
}

export function readJSON(filePath) { return JSON.parse(fs.readFileSync(filePath, 'utf-8')); }

export function readJSONMaybe(filePath) {
  if (fs.existsSync(filePath)) {
    try { return JSON.parse(fs.readFileSync(filePath, 'utf-8')); } catch { return null; }
  }
  return null;
}

export function mdTable(headers, rows) {
  const h = `| ${headers.join(' | ')} |`;
  const sep = `| ${headers.map(() => '------').join(' | ')} |`;
  const body = rows.map(r => `| ${r.join(' | ')} |`).join('\n');
  return `${h}\n${sep}\n${body}`;
}

// 废弃标记：@Deprecated 的类/接口/字段 → <del>删除线</del> + 灰色「已废弃」徽章（MDX 原生支持内联 HTML）
export const DEP_BADGE = ' <span class="deprecated-badge">已废弃</span>';
export function dep(text, isDeprecated) {
  return isDeprecated ? `<del>${text}</del>${DEP_BADGE}` : text;
}

// 类路径 tooltip + revision-pinned 源码链接：
// - 页面只显示类名/限定名，hover 显示源代码完整路径（减少页面噪音）
// - meta.json 含 evidence{repo_url, revision} 时渲染钉定版本的源码链接，
//   指向生成时刻的 commit，代码后续演进不会让链接漂移（archify 钉版本语义）
// - 无 evidence / 无 revision → 不渲染链接，维持纯 tooltip（诚实降级）
let _evidence = undefined; // undefined=未加载, null=无 evidence
function loadEvidence() {
  if (_evidence === undefined) {
    const meta = readJSONMaybe(path.join(MANIFEST_DIR, 'meta.json')) || {};
    _evidence = meta.evidence || null;
  }
  return _evidence;
}

export function sourceLinkUrl(sourcePath, evidence, line) {
  // evidence 参数可显式传入（测试用），默认读 meta.json；
  // line（L2 行级 evidence）>0 时追加 #L 锚点，直达类声明行
  const ev = evidence !== undefined ? evidence : loadEvidence();
  if (!ev || !ev.revision || !ev.repo_url || !sourcePath) return null;
  const p = String(sourcePath).replace(/^\/+/, '').replace(/"/g, '&quot;');
  let url;
  if (ev.repo_url.includes('{revision}')) {
    // 完整链接模板（推荐）：兼容 Codeup/GitLab/GitHub 各自的 URL 形态
    //   "https://codeup.aliyun.com/x/y/blob/{revision}/{path}"
    url = ev.repo_url.replaceAll('{revision}', ev.revision);
    url = url.includes('{path}') ? url.replaceAll('{path}', p)
                                 : `${url.replace(/\/+$/, '')}/${p}`;
  } else {
    // 裸仓库 URL（旧配置兼容）：默认 GitHub/Gitea 风格 blob 路径
    url = `${ev.repo_url.replace(/\/+$/, '')}/blob/${ev.revision}/${p}`;
  }
  if (line > 0) url += `#L${line}`;
  return url;
}

export function srcAbbr(text, sourcePath, line) {
  const p = (sourcePath || '').replace(/"/g, '&quot;');
  if (!p) return text || '-';
  const url = sourceLinkUrl(sourcePath, undefined, line);
  return url
    ? `<a href="${url}" title="${p}" target="_blank" rel="noopener noreferrer">${text}</a>`
    : `<abbr title="${p}">${text}</abbr>`;
}

// 域缓存（懒加载）
export const DOMAIN_CACHE = new Map();

export function loadDomain(name) {
  if (DOMAIN_CACHE.has(name)) return DOMAIN_CACHE.get(name);
  const file = path.join(MANIFEST_DIR, 'domains', `${name}.json`);
  if (fs.existsSync(file)) {
    const data = readJSON(file);
    DOMAIN_CACHE.set(name, data);
    return data;
  }
  return null;
}

export function loadManifest() {
  if (fs.existsSync(path.join(MANIFEST_DIR, 'index.json'))) {
    const index = readJSON(path.join(MANIFEST_DIR, 'index.json'));
    const meta = readJSONMaybe(path.join(MANIFEST_DIR, 'meta.json')) || {};
    const diagrams = readJSONMaybe(path.join(MANIFEST_DIR, 'diagrams.json')) || {};
    const crossDeps = readJSONMaybe(path.join(MANIFEST_DIR, 'cross-domain.json')) || [];

    return {
      meta: { ...index, project: meta.project || index.project || {} },
      diagrams,
      crossDomainDependencies: crossDeps,
      _database: null,
      database: {
        get tables() {
          if (!this._tables) {
            const db = readJSONMaybe(path.join(MANIFEST_DIR, 'database.json')) || {};
            this._tables = db.tables || [];
          }
          return this._tables;
        },
      },
      openapiSpecs: {},
      domains: (index.domains || []).map(e => ({
        name: e.name,
        displayName: e.displayName,
        description: e.description,
        componentCount: e.componentCount,
        // 懒加载的域原始数据
        _loaded: false,
        _raw: null,
        get _rawData() {
          if (!this._loaded) { this._raw = loadDomain(this.name); this._loaded = true; }
          return this._raw || {};
        },
        get layers() { return this._rawData.layers || {}; },
      })),
      _index: index,
    };
  }

  if (fs.existsSync(LEGACY_MANIFEST)) {
    console.warn('  ⚠ 使用旧版 doc-manifest.json（建议升级为分片格式）');
    return JSON.parse(fs.readFileSync(LEGACY_MANIFEST, 'utf-8'));
  }

  console.error('❌ doc-manifest/ 目录或 doc-manifest.json 未找到');
  process.exit(1);
}

// ── 页面生成常量 ──

export const LAYER_TITLES = {
  adapter: 'Adapter 接口层', client: 'Client 契约层',
  application: 'Application 应用层', domain: 'Domain 领域层',
  infrastructure: 'Infrastructure 基础设施层',
};

export const LAYER_DESCRIPTIONS = {
  adapter: '负责协议适配：REST Controller、MQ Consumer、定时任务 Scheduler',
  client: '对外暴露的 API 契约：ServiceI 接口、CO/Cmd/Query 对象',
  application: '用例编排层：CmdExe/QryExe 执行器、Assembler 组装器、事务管理',
  domain: '核心领域模型：Entity 实体、ValueObject 值对象、DomainService 领域服务、Repository 仓储接口',
  infrastructure: '技术基础设施：Repository 实现、ACL 防腐层、外部渠道网关、配置',
};

// 状态机业务域推断规则
export const SM_DOMAIN = [
  [/^Send/, '发送域'], [/^Template/, '模板域'], [/^Push/, '推送域'],
  [/^Message/, '消息域'], [/^Audit/, '审计域'], [/^Sms/, '短信域'],
  [/^Statistics/, '统计域'], [/^Access/, '配置域'], [/^Callback/, '回调域'],
];

export { ROOT, DOCS_DIR, MANIFEST_DIR, LEGACY_MANIFEST };
