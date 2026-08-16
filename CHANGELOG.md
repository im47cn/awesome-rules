# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

## [0.3.0](https://github.com/im47cn/awesome-rules/compare/v0.2.0...v0.3.0) (2026-08-16)

### ⚠ BREAKING CHANGES

* **arch-hawkeye:** doc_gen.py aggregate 子命令移除，改用
  arch-hawkeye/scripts/hawkeye.py aggregate（参数兼容）

### ✨ 新功能

* **doc-gen:** business-context 可选扩展分片 ([8970fe7](https://github.com/im47cn/awesome-rules/commit/8970fe7f90ae0a2c89b44ea4f8bab102bd449586))

### 🐛 Bug 修复

* **doc-gen:** 补齐业务全景站点渲染（8970fe7 前端遗漏部分） ([e1919ce](https://github.com/im47cn/awesome-rules/commit/e1919cec47c14fd3b341aca60ab42c9b90225439))

### ♻️ 重构

* **arch-hawkeye:** 多项目聚合迁移至架构鹰眼独立工程 ([051c06e](https://github.com/im47cn/awesome-rules/commit/051c06ee4fa87605d4c349ce0397771f51356718))
## 0.2.0 (2026-08-16)

### ⚠ BREAKING CHANGES

* **doc-gen:** npm 缺失/install/build 失败从静默跳过改为 exit 1，
  依赖旧行为的 CI 脚本需显式降级（|| true）
* **impact-guard:** v2 方法级 diff 与跨服务传播

### ✨ 新功能

* **alibabacloud-devops:** 新增云效 DevOps 技能，mcporter 代理模式 ([b90cc53](https://github.com/im47cn/awesome-rules/commit/b90cc5317abc57c284f706fda7b13b3ce4d0737a))
* **api-check:** 增强 API 检查功能，添加动作收敛和边界测试用例 ([631aa7d](https://github.com/im47cn/awesome-rules/commit/631aa7d79e19038d9fea27612624f9847296d68d))
* **arch-guard:** 新增 DDD 架构分层守护技能 ([33facbb](https://github.com/im47cn/awesome-rules/commit/33facbb97f93fe1fa068a833e21a211595cd0919))
* **ddl-check:** 增加日志/流水表字段豁免规则及泛化字段名命名建议 ([24ba483](https://github.com/im47cn/awesome-rules/commit/24ba483269988c9363bce116c51a5959b17a2942))
* **ddl-guard:** 优化触发优先级与审查工作流，贡献指南新增本地调试章节 ([aecfd96](https://github.com/im47cn/awesome-rules/commit/aecfd9672684bfe466627445d2730e16aa126442))
* **doc-gen:** /impact/ 变更影响分析页内嵌 impact-guard 语义 ([7763daa](https://github.com/im47cn/awesome-rules/commit/7763daaa840bb6c0ce3946178f02f5aa784a8495))
* **doc-gen:** evidence 源码链接与架构演进页 ([11d7a0b](https://github.com/im47cn/awesome-rules/commit/11d7a0bafa7b08dffc2bff86560dafb8c2ae5d1b))
* **doc-gen:** evolution 页着色 delta 图 ([1a2ea26](https://github.com/im47cn/awesome-rules/commit/1a2ea26398c61db7230c92eb613e1216d2ca2c6f))
* **doc-gen:** manifest schema 契约与诚实退出码 ([95b4b10](https://github.com/im47cn/awesome-rules/commit/95b4b10174c632255aeb91e244594e3b9fc35d18))
* **doc-gen:** 新增 DDD 技术文档自动生成技能 ([2fb124f](https://github.com/im47cn/awesome-rules/commit/2fb124ff2a0ed94feea758df17452b77ce565646))
* **gitignore:** 添加 .coverage 文件夹到忽略列表 ([701bde7](https://github.com/im47cn/awesome-rules/commit/701bde756a6eb21c777304842b629f57820dafa4))
* **git:** 更新提交规范，新增性能优化与回退类型 ([2729079](https://github.com/im47cn/awesome-rules/commit/2729079e1c77ed353a22e218350441361ba7d677))
* **impact-guard:** v1 脚本落地 + scope 补齐 ([b668a38](https://github.com/im47cn/awesome-rules/commit/b668a3885e6d312b66109c85bf81c46566034b9a))
* **impact-guard:** v2 方法级 diff 与跨服务传播 ([faf9ba4](https://github.com/im47cn/awesome-rules/commit/faf9ba431245d4c88dca5154296d96c2adb3be60))
* **skills:** 增强 api/arch/ddl-guard 审查能力并补齐单测 ([057e9b2](https://github.com/im47cn/awesome-rules/commit/057e9b233b062530b69c13aef18bc07d8cf5ce68))
* **skills:** 新增 work-report 跨仓库工作日报技能 ([a991bab](https://github.com/im47cn/awesome-rules/commit/a991bab1d9a258a850b228fa61339e84b2684776))
* **tools:** 新增 git 提交工具链与 commitlint 规范 ([b43e7d4](https://github.com/im47cn/awesome-rules/commit/b43e7d435ffcb43d3bffe500d3a100979501729d))
* 新增 badcase 回归测试工具及示例用例 ([b678ca0](https://github.com/im47cn/awesome-rules/commit/b678ca0267b30bd0f441c082a2fa9e19a70863fe))
* 新增规范入口文档与 SessionStart 自动注入 hook ([8049594](https://github.com/im47cn/awesome-rules/commit/80495946e44c84c96c9f94d3404087df75df4312))

### ♻️ 重构

* **api-guard:** 聚焦业务接口规范，剥离 openapi 四段式检查 ([750d9fa](https://github.com/im47cn/awesome-rules/commit/750d9fac1a007d8a5f2ef0456b0906f3cca06325))
* **steering:** GTSP 规范按维度拆分，openapi-standards 重命名 ([d6817ae](https://github.com/im47cn/awesome-rules/commit/d6817aee58fb59c9668dbaf1c54cfa6ab7b83a76))
* **steering:** 规范索引改为 frontmatter 动态扫描 ([5486e93](https://github.com/im47cn/awesome-rules/commit/5486e93ff3db6727f55e954bff817dab21023e3a))

### 📝 文档

* **doc-gen:** 可信化改造设计文档与索引更新 ([718de20](https://github.com/im47cn/awesome-rules/commit/718de2022205962daa7697ed2824d7d3f9194ba4)), references [1-#4](https://github.com/im47cn/awesome-rules/issues/4)
* **impact-guard:** 修正 §5 集成表两处过时状态 ([37b2d53](https://github.com/im47cn/awesome-rules/commit/37b2d53e07fa2e6d483631c09af2efca92cf46e1))
* **openapi:** 移除 URL path 禁传 token 安全条款 ([75d6f77](https://github.com/im47cn/awesome-rules/commit/75d6f774952797aedcaf96ac1d9ebb4cb4d6e9fd))
* **steering:** 新增 DDD 架构规范与测试规范 ([34a8625](https://github.com/im47cn/awesome-rules/commit/34a86257b9506349f3e16ece37d0693d6638ae72))
* 新增技能编写约束，禁止静态复制可动态获取内容 ([73ddb84](https://github.com/im47cn/awesome-rules/commit/73ddb84c0c79a023a99c2880b73a0d1bf2b52440))
* 新增贡献指南，README 补充贡献入口 ([a8a5b3d](https://github.com/im47cn/awesome-rules/commit/a8a5b3d0b435ed6043b227666c605d21423677ff))
* 更新技能说明文档，新增 doc-gen 并补质量指标 ([1758173](https://github.com/im47cn/awesome-rules/commit/17581732a1a20550c6f966a26972091c1d30b905))

### ✅ 测试

* **api-guard:** 添加 pytest 覆盖率门禁配置 ([c0474f3](https://github.com/im47cn/awesome-rules/commit/c0474f3b19ce5037bf0ee1150fbc4f5e689bfb9d))
* **arch-guard:** 增强架构检查测试并添加覆盖率门禁 ([b1c55cd](https://github.com/im47cn/awesome-rules/commit/b1c55cd4d77449b5f534f101fdc3267cbe89c2b8))
* **ddl-guard:** 增强 SQL 检查测试并添加覆盖率门禁 ([89ccdf8](https://github.com/im47cn/awesome-rules/commit/89ccdf8873333928d852507f110505df21998174))
## 0.1.1 (2026-08-11)

### ✨ 新功能

* **arch-guard:** 新增 DDD 架构分层守护技能 ([33facbb](https://github.com/im47cn/awesome-rules/commit/33facbb97f93fe1fa068a833e21a211595cd0919))
* **ddl-guard:** 优化触发优先级与审查工作流，贡献指南新增本地调试章节 ([aecfd96](https://github.com/im47cn/awesome-rules/commit/aecfd9672684bfe466627445d2730e16aa126442))
* **skills:** 增强 api/arch/ddl-guard 审查能力并补齐单测 ([057e9b2](https://github.com/im47cn/awesome-rules/commit/057e9b233b062530b69c13aef18bc07d8cf5ce68))
* 新增 badcase 回归测试工具及示例用例 ([b678ca0](https://github.com/im47cn/awesome-rules/commit/b678ca0267b30bd0f441c082a2fa9e19a70863fe))
* 新增规范入口文档与 SessionStart 自动注入 hook ([8049594](https://github.com/im47cn/awesome-rules/commit/80495946e44c84c96c9f94d3404087df75df4312))

### ♻️ 重构

* **api-guard:** 聚焦业务接口规范，剥离 openapi 四段式检查 ([750d9fa](https://github.com/im47cn/awesome-rules/commit/750d9fac1a007d8a5f2ef0456b0906f3cca06325))
* **steering:** GTSP 规范按维度拆分，openapi-standards 重命名 ([d6817ae](https://github.com/im47cn/awesome-rules/commit/d6817aee58fb59c9668dbaf1c54cfa6ab7b83a76))
* **steering:** 规范索引改为 frontmatter 动态扫描 ([5486e93](https://github.com/im47cn/awesome-rules/commit/5486e93ff3db6727f55e954bff817dab21023e3a))

### 📝 文档

* **openapi:** 移除 URL path 禁传 token 安全条款 ([75d6f77](https://github.com/im47cn/awesome-rules/commit/75d6f774952797aedcaf96ac1d9ebb4cb4d6e9fd))
* **steering:** 新增 DDD 架构规范与测试规范 ([34a8625](https://github.com/im47cn/awesome-rules/commit/34a86257b9506349f3e16ece37d0693d6638ae72))
* 新增贡献指南，README 补充贡献入口 ([a8a5b3d](https://github.com/im47cn/awesome-rules/commit/a8a5b3d0b435ed6043b227666c605d21423677ff))
