/**
 * commitlint 配置 —— 对齐 steering/git-conventions.md
 *
 * 规则等级：2 = error（阻断提交）| 1 = warn（警告不阻断）| 0 = 关闭
 * 文档：https://commitlint.js.org/reference/rules.html
 */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // ── type 必须在枚举内（强制，对应规范的 type 表）──────────────
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'chore', 'revert'],
    ],

    // ── scope 建议在枚举内（warn，业务域靠 warn 放行，不阻断）─────
    //    枚举须与 steering/git-conventions.md 保持一致
    'scope-enum': [1, 'always', ['api', 'db', 'ui', 'ci']],

    // ── 主题行长度（git 经典 50/72 规则，对应规范"主题行 ≤50 字符"）──
    'subject-max-length': [2, 'always', 50],
    'header-max-length': [2, 'always', 72],

    // ── 关闭英文大小写规则（中文 subject 不适用）──────────────────
    'subject-case': [0],
    'type-case': [0],
    'scope-case': [0],

    // ── body / footer 前置空行（推荐，提升可读性）─────────────────
    'body-leading-blank': [1, 'always'],
    'footer-leading-blank': [1, 'always'],

    // ── breaking change：config-conventional 已内置校验
    //    feat!: / BREAKING CHANGE: 两种写法均被识别，并触发 major bump
  },
};
