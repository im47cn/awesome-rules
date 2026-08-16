import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mdx from "@astrojs/mdx";

import tailwindcss from "@tailwindcss/vite";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ── 配置读取（支持分片 + 旧版）──

const MANIFEST_DIR = path.resolve("doc-manifest");
const INDEX_FILE = path.join(MANIFEST_DIR, "index.json");
const SINGLE_FILE = path.resolve("doc-manifest.json");
const CONFIG_JSON = path.resolve("src/config/config.json");
const SOCIAL_JSON = path.resolve("src/config/social.json");
const LOCALS_JSON = path.resolve("src/config/locals.json");

function readJSON(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try { return JSON.parse(fs.readFileSync(filePath, "utf-8")); } catch { return null; }
}

// 站点配置
const siteConfig = readJSON(CONFIG_JSON) || {};
const siteTitle = siteConfig.site?.title || "架构鹰眼";
const siteDesc = siteConfig.site?.description || "DDD 架构全景视图";
const siteUrl = siteConfig.site?.base_url || "/";

// 社交链接
const socialConfig = readJSON(SOCIAL_JSON);
// 语言配置（dockit 主题）
const localsConfig = readJSON(LOCALS_JSON);
const locales = localsConfig || {
  root: { label: "简体中文", lang: "zh-CN" },
};

// 多项目 / 单项目 Manifest
let manifestIdx = null;
if (fs.existsSync(INDEX_FILE)) {
  manifestIdx = readJSON(INDEX_FILE);
} else if (fs.existsSync(SINGLE_FILE)) {
  const legacy = readJSON(SINGLE_FILE);
  manifestIdx = legacy?.meta || legacy;
}

// ── 动态构建 Sidebar（支持多项目聚合）──

/** 读域 JSON 提取聚合名列表（供侧边栏"领域模型"分组使用） */
function readDomainAggregates(domainName, projectId) {
  const base = path.resolve(MANIFEST_DIR);
  let domainFile = null;
  if (projectId) {
    domainFile = path.join(base, "projects", projectId, `${domainName}.json`);
  }
  if (!domainFile || !fs.existsSync(domainFile)) {
    domainFile = path.join(base, "domains", `${domainName}.json`);
  }
  if (!fs.existsSync(domainFile)) return [];
  try {
    const data = JSON.parse(fs.readFileSync(domainFile, "utf-8"));
    const domainLayer = data.layers?.domain;
    if (!domainLayer) return [];
    return (domainLayer.aggregates || []).map(a => a.name).filter(Boolean);
  } catch { return []; }
}

/** 收集所有含领域层的业务域及其聚合（兼容多项目/单项目） */
function collectSidebarDomains() {
  if (!manifestIdx || !manifestIdx.domains) return [];
  const result = [];
  const collect = (d, projectId) => ({
    name: d.name,
    displayName: d.displayName || d.name,
    projectName: d._project_name,
    aggregates: readDomainAggregates(d.name, projectId),
  });
  if (manifestIdx.projects) {
    for (const proj of manifestIdx.projects) {
      for (const d of manifestIdx.domains) {
        if (d._project_id !== proj.id || !d.layers?.includes("domain")) continue;
        result.push(collect(d, proj.id));
      }
    }
  } else {
    for (const d of manifestIdx.domains) {
      if (!d.layers?.includes("domain")) continue;
      result.push(collect(d));
    }
  }
  return result;
}

// 分层入口定义（侧边栏"分层架构"分组用，label 对齐 generate-pages.mjs 的 LAYER_TITLES）
const SIDEBAR_LAYERS = [
  { key: "adapter", icon: "external", label: "Adapter" },
  { key: "client", icon: "document", label: "Client" },
  { key: "application", icon: "setting", label: "Application" },
  { key: "domain", icon: "code-branch", label: "Domain" },
  { key: "infrastructure", icon: "server", label: "Infrastructure" },
];

/** 收集"分层架构"分组：按项目/按域，仅保留实际存在的层，避免死链 */
function collectLayerGroups() {
  if (!manifestIdx || !manifestIdx.domains) return [];
  const groups = [];
  if (manifestIdx.projects) {
    for (const proj of manifestIdx.projects) {
      const layers = SIDEBAR_LAYERS.filter((l) => proj.layers?.includes(l.key));
      if (layers.length === 0) continue;
      groups.push({
        label: `${proj.name}`,
        collapsed: false,
        items: [
          { label: "概览", link: `/projects/${proj.id}/` },
          ...layers.map((l) => ({ label: l.label, link: `/projects/${proj.id}/${l.key}/` })),
        ],
      });
    }
  } else {
    for (const d of manifestIdx.domains) {
      const layers = SIDEBAR_LAYERS.filter((l) => d.layers?.includes(l.key));
      if (layers.length === 0) continue;
      groups.push({
        label: `${d.displayName || d.name}`,
        collapsed: false,
        items: [
          { label: "概览", link: `/domains/${d.name}/` },
          ...layers.map((l) => ({ label: l.label, link: `/domains/${d.name}/${l.key}/` })),
        ],
      });
    }
  }
  return groups;
}

function buildSidebar() {
  // 「首页」入口已移除：首页 / 本身即着陆页，侧边栏不再重复列出（避免冗余）。
  const sidebar = [
    { label: "架构全景图", link: "/architecture" },
  ];

  // ① 领域模型：总览入口 link + 每个业务域作顶级 group（聚合扁平展开）。
  //    严格两级，对齐 dockit 扁平设计 —— 不再出现「领域模型 > 业务域 > 聚合」三级嵌套。
  const domains = collectSidebarDomains();
  if (domains.length > 0) {
    sidebar.push({ label: "领域模型", link: "/domain-model/" });
    for (const { name, displayName, aggregates, projectName } of domains) {
      sidebar.push({
        label: `${displayName || name}`,
        collapsed: false,
        badge: projectName ? { text: projectName, variant: "caution", class: "project-tag" } : undefined,
        items: [
          { label: "概览", link: `/domain-model/${name}/` },
          ...aggregates.map((aggName) => ({
            label: aggName,
            link: `/domain-model/${name}/${aggName}/`,
          })),
        ],
      });
    }
  }

  // ② 分层架构（次要视角）：adapter/client/application/domain/infrastructure 入口，默认折叠弱化
  const layerGroups = collectLayerGroups();
  if (layerGroups.length > 0) {
    sidebar.push({ label: "分层架构", collapsed: true, items: layerGroups });
  }

  const risksFile = path.join(MANIFEST_DIR, "risks.json");
  if (fs.existsSync(risksFile)) {
    try {
      const risks = JSON.parse(fs.readFileSync(risksFile, "utf-8"));
      const total = risks.totalIssues || 0;
      const critical = risks.criticalCount || 0;
      if (total > 0) {
        sidebar.push({ label: `架构风险清单 (${critical})`, link: "/risks" });
      }
    } catch { /* ignore */ }
  }

  const adrsFile = path.join(MANIFEST_DIR, "adrs.json");
  if (fs.existsSync(adrsFile)) {
    try {
      const adrs = JSON.parse(fs.readFileSync(adrsFile, "utf-8"));
      if ((adrs.total || 0) > 0) {
        sidebar.push({ label: "架构决策记录", link: "/adr" });
      }
    } catch { /* ignore */ }
  }

  const stateMachinesFile = path.join(MANIFEST_DIR, "state-machines.json");
  if (fs.existsSync(stateMachinesFile)) {
    try {
      const sms = JSON.parse(fs.readFileSync(stateMachinesFile, "utf-8"));
      if (Array.isArray(sms) && sms.length > 0) {
        // git-merge 非 Starlight 内置图标 → 改用 random（状态流转语义）
        sidebar.push({ label: `状态机 (${sms.length})`, link: "/state-machine" });
      }
    } catch { /* ignore */ }
  }

  const deltaFile = path.join(MANIFEST_DIR, "delta.json");
  if (fs.existsSync(deltaFile)) {
    try {
      const delta = JSON.parse(fs.readFileSync(deltaFile, "utf-8"));
      const s = delta?.summary || {};
      const total = Object.values(s).reduce(
        (sum, d) => sum + Object.values(d || {}).reduce((a, v) => a + (v || 0), 0), 0);
      sidebar.push({ label: `🔀 架构演进 (${total})`, link: "/evolution" });
    } catch { /* ignore */ }
  }

  // 手写深度文档：按 category 分组，子组默认折叠
  const articlesFile = path.join(MANIFEST_DIR, "articles.json");
  if (fs.existsSync(articlesFile)) {
    try {
      const arts = JSON.parse(fs.readFileSync(articlesFile, "utf-8"));
      if ((arts.total || 0) > 0 && Array.isArray(arts.articles)) {
        const byCategory = {};
        for (const a of arts.articles) {
          (byCategory[a.category] ||= []).push({ label: a.title, link: a.link });
        }
        const order = ["风险与审查", "架构设计", "接口与数据", "索引", "其他"];
        const items = order
          .filter((c) => byCategory[c])
          .map((c) => ({ label: c, collapsed: true, items: byCategory[c] }));
        // lightbulb 非 Starlight 内置图标 → 改用 magnifier（深度审查语义）
        sidebar.push({ label: "深度分析", collapsed: false, items });
      }
    } catch { /* ignore */ }
  }

  if (manifestIdx?.tableCount > 0) {
    sidebar.push({ label: "数据库设计", link: "/database" });
  }
  if (manifestIdx?.hasOpenApi) {
    // API 文档为独立全屏 Scalar 页面，新标签页打开以免离开文档站框架
    sidebar.push({ label: "API接口", link: "/api", attrs: { target: "_blank", rel: "noopener" } });
  }

  return sidebar;
}

const sidebar = buildSidebar();

// ── Astro Config ──

// Mermaid 代码块 → <div class="mermaid"> raw HTML，绕过 Starlight Expressive Code 的代码高亮。
function remarkMermaid() {
  return (tree) => {
    const walk = (node, parent) => {
      if (!node) return;
      if (node.type === 'code' && node.lang === 'mermaid') {
        const escaped = node.value
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');
        const idx = parent.children.indexOf(node);
        parent.children.splice(idx, 1, {
          type: 'html',
          value: `<div class="mermaid">\n${escaped}\n</div>`,
        });
        return;
      }
      if (node.children) node.children.forEach((c) => walk(c, node));
    };
    walk(tree, null);
  };
}

// 占位 integration：利用 Starlight 官方覆盖机制（仅当 integrations 中未出现
// name === '@astrojs/sitemap' 时，Starlight 才自动添加默认 sitemap）阻止其注册。
// 内部文档站无需 SEO sitemap，亦可消除 site 未配置时的构建告警。
const noopSitemap = () => ({ name: "@astrojs/sitemap", hooks: {} });

// 构建后将 doc-manifest/ 复制到 dist/，供 ChatAgent 运行时 fetch。
// 单一来源（output_dir/doc-manifest/），无需 public/ 冗余副本。
const copyDocManifest = () => ({
  name: "copy-doc-manifest",
  hooks: {
    "astro:build:done": async ({ dir }) => {
      const src = path.resolve("doc-manifest");
      if (!fs.existsSync(src)) return;
      fs.cpSync(src, path.join(fileURLToPath(dir), "doc-manifest"), { recursive: true });
    },
  },
});

export default defineConfig({
  site: (siteUrl && siteUrl !== "/" ? siteUrl : undefined),
  image: {
    service: { entrypoint: "astro/assets/services/noop" },
  },
  markdown: {
    remarkPlugins: [remarkMermaid],
  },
  integrations: [
    noopSitemap(),
    copyDocManifest(),
    starlight({
      title: siteTitle,
      description: siteDesc,
      defaultLocale: "root",
      locales,
      sidebar,
      customCss: ["./src/styles/global.css"],
      components: {
        // 回归 Starlight 原生：仅保留 PageFrame override，用于全局挂载 ChatAgent 与 Mermaid 渲染。
        PageFrame: "./src/components/override-components/PageFrame.astro",
      },
      head: [
        { tag: "link", attrs: { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" } },
        { tag: "meta", attrs: { name: "generator", content: "arch-hawkeye v2.0" } },
      ],
      editLink: manifestIdx?.project?.repo ? {
        baseUrl: manifestIdx.project.repo,
      } : undefined,
      social: socialConfig?.main || (manifestIdx?.project?.repo
        ? [{ label: "GitHub", icon: "github", href: manifestIdx.project.repo }]
        : []),
      pagination: false,
      lastUpdated: true,
    }),
    mdx(),
  ],
  vite: {
    // 注：移除 viewTransitions() —— Astro view transitions 的 SPA 路由拦截所有同源 <a> 点击，
    // 导致 sidebar/卡片的 target="_blank" 失效（无法新 tab 打开 API 等独立页面）。
    // 取消 view transitions 以恢复浏览器原生 target="_blank" 行为。
    plugins: /** @type {any} */ ([tailwindcss()]),
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
        "~": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
  },
  output: "static",
});
