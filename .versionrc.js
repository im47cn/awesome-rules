/**
 * commit-and-tag-version 配置 —— 中文 changelog + 语义化版本号
 *
 * 兼容 standard-version 配置格式（standard-version 已 archived，改用其活跃 fork）
 * 文档：https://github.com/absolute-version/commit-and-tag-version#configuration
 *
 * 版本号规则（仓库惯例，由 scripts/release_guard.py 保证）：
 *   feat       → minor
 *   fix        → patch
 *   feat! / BREAKING CHANGE → major
 *
 * ⚠ 2026-08-26 实证：catv 13.x 对 0.x 版本强制 preMajor 语义（feat→patch、
 * breaking→minor，无 CLI 开关），与上述惯例冲突（v0.4.1 事故：区间 23 个
 * feat 被判 patch）。故 npm run release 已接线 scripts/release_guard.py：
 * 先按惯例独立判定，与 catv dry-run 不一致时 --release-as 纠偏。此规则在
 * 1.0.0 后自然失效（两语义合流），届时可简化。
 */
module.exports = {
  // changelog 中文分节：type → 章节（hidden 表示不出现在 changelog）
  types: [
    { type: 'feat', section: '✨ 新功能' },
    { type: 'fix', section: '🐛 Bug 修复' },
    { type: 'perf', section: '⚡ 性能' },
    { type: 'refactor', section: '♻️ 重构' },
    { type: 'revert', section: '⏪ 回退', hidden: true },
    { type: 'docs', section: '📝 文档' },
    { type: 'test', section: '✅ 测试' },
    { type: 'style', section: '💄 格式', hidden: true },
    { type: 'chore', section: '🔧 构建/依赖', hidden: true },
  ],
  // 版本标签前缀
  tagPrefix: 'v',
  // commit / compare URL 从 git remote 自动推断 host（GitHub / 阿里云 codeup / GitLab 均适配）
  // 如需固定 host，在此覆写 commitUrlFormat / compareUrlFormat
};
