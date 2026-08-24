# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

## [0.4.0](https://ssh.github.com/443/im47cn/awesome-rules/compare/v0.3.0...v0.4.0) (2026-08-24)

### ✨ 新功能

* **arch-guard:** ArchUnit 规则生成器与三项目试点 ([dbb01ec](https://ssh.github.com/443/im47cn/awesome-rules/commit/dbb01ec2cc4e2daa639a452b14791786752db328))
* **arch-guard:** 架构守护演进设计与 badcase/基线测试补齐 ([ace2340](https://ssh.github.com/443/im47cn/awesome-rules/commit/ace23401b23fb35223d765eda354ebf6efbb7230))
* **arch-hawkeye:** DB 通道——共享表耦合边（GTSP 5 通道之三） ([b9f056c](https://ssh.github.com/443/im47cn/awesome-rules/commit/b9f056c7141aefbe51d8ae6819e22db4821ac986))
* **arch-hawkeye:** MQ 证据源——订阅/发布声明对齐（GTSP 5 通道之二） ([1e83ca5](https://ssh.github.com/443/im47cn/awesome-rules/commit/1e83ca5be2cdbbfee0305365283950b4c22e0619))
* **arch-hawkeye:** Phase2 跨项目真实链路——Feign×Controller 签名对齐（AH-C01/C04） ([42f154c](https://ssh.github.com/443/im47cn/awesome-rules/commit/42f154c6d39e90742144efa89303b7a6e03feed1))
* **arch-hawkeye:** Phase2-C 跨项目变更影响分析（AH-C03） ([da313df](https://ssh.github.com/443/im47cn/awesome-rules/commit/da313dfbb5cb50c1225054287027330eed198bba))
* **arch-hawkeye:** Phase3 治理闭环——检测长出牙齿（REQ-D 全落地） ([ac5c6ba](https://ssh.github.com/443/im47cn/awesome-rules/commit/ac5c6ba15c6ffff974e5ea63e5d6ae820598cc5a))
* **arch-hawkeye:** Phase4 双模式 + 可查询站点收官（B01-B03/C02/E03） ([91bc77a](https://ssh.github.com/443/im47cn/awesome-rules/commit/91bc77af96a3481f322f7803a1128a06d836d5b1))
* **arch-hawkeye:** 缓存/定时通道——GTSP 5 通道全覆盖 ([c38afe6](https://ssh.github.com/443/im47cn/awesome-rules/commit/c38afe6a3c7fd596756f289b09675dc7d55ceb47))
* **code-review:** 新增两轴代码审查技能（规范轴+规格轴并行子代理+聚合抽验） ([7f62500](https://ssh.github.com/443/im47cn/awesome-rules/commit/7f62500d29474e7c02fd657009edaea87082ee10))
* **contract-guard:** 契约门禁自检与接入验收 ([bfa87a5](https://ssh.github.com/443/im47cn/awesome-rules/commit/bfa87a50defdd26aebf9dfaae5fba74f57b49e56))
* **contract-guard:** 跨仓契约兼容性守护技能 ([7faaa73](https://ssh.github.com/443/im47cn/awesome-rules/commit/7faaa73198050393bfae53d7f5811a4d801c016a))
* **cov-hooks:** 跨项目变更行覆盖率红线共享钩子 (≥95%, 链式代理 .git/hooks) ([dc15977](https://ssh.github.com/443/im47cn/awesome-rules/commit/dc15977f2bf0912b71de6133a0f81ba9706fffec))
* **doc-gen:** L2 行级 evidence——sourceLine → #L 锚点直达类声明行 ([78dc283](https://ssh.github.com/443/im47cn/awesome-rules/commit/78dc283da1fa9ff80db45a0cd494a030941366d8)), references [#L](https://ssh.github.com/443/im47cn/awesome-rules/issues/L) [#L](https://ssh.github.com/443/im47cn/awesome-rules/issues/L)
* **doc-gen:** risks/adrs/articles 分片纳入 schema + 首页 receipt 可视化 ([4030352](https://ssh.github.com/443/im47cn/awesome-rules/commit/40303527723334ab2ac127e32e2c4c4e051c7889))
* **factory:** holdout FAIL 证据按轮存档 + prime/plan 回流 + worktree 兼容 ([7b16a18](https://ssh.github.com/443/im47cn/awesome-rules/commit/7b16a18e97fe5338953c950cd94c9b24c94ced0b)), references [#5](https://ssh.github.com/443/im47cn/awesome-rules/issues/5)
* **factory:** merge feedback PR [#7](https://ssh.github.com/443/im47cn/awesome-rules/issues/7) ([6fd4320](https://ssh.github.com/443/im47cn/awesome-rules/commit/6fd432041ada53b99e72c416e4d5335406de7952))
* **factory:** mutations 扩充 tests 门与行为破坏类缺陷集 ([2708dd3](https://ssh.github.com/443/im47cn/awesome-rules/commit/2708dd37f911393993dc1ec5635cdf94bd61094c))
* **factory:** triage 批次——补齐'写 issue→自动看见'的 S2 缺口 ([2af5d64](https://ssh.github.com/443/im47cn/awesome-rules/commit/2af5d64e4ec8d7d897f9adcf7bae09855dafcc47)), references [57-#60](https://ssh.github.com/443/im47cn/awesome-rules/issues/60)
* **factory:** 专属分支+main 防护落地 ([211875f](https://ssh.github.com/443/im47cn/awesome-rules/commit/211875f6590aeb2d7a500f6adf5ff2e633c872c0))
* **factory:** 对齐吸收上游 main 重整后的链演化（7b16a18e…c1ef09f3） ([d254254](https://ssh.github.com/443/im47cn/awesome-rules/commit/d254254a3b4987d0b56445793ce56e14f3d1aec9))
* **factory:** 租约仲裁层——多写者互斥与 epoch fencing ([c885cf6](https://ssh.github.com/443/im47cn/awesome-rules/commit/c885cf6fd13cdf4f81c284ab9a8938716ed88abd))
* **factory:** 链改独立 git worktree, 根治多驱动方工作区冲突 ([10d3d18](https://ssh.github.com/443/im47cn/awesome-rules/commit/10d3d185c142e5d4e8073ec5fba6c4f1450abd09))
* **feedback:** trailer 判定升级——逐资产最后触碰者链 ([3ccdc88](https://ssh.github.com/443/im47cn/awesome-rules/commit/3ccdc88840f585ebe0c954db514a73371455c09e))
* **feedback:** 依赖闭包检查——樱桃前 fail-closed 防 PR[#18](https://ssh.github.com/443/im47cn/awesome-rules/issues/18) 断件复演 ([886a3e4](https://ssh.github.com/443/im47cn/awesome-rules/commit/886a3e4088cbc149f18665c13691d37433192c00))
* **guard:** 收据信封 commitSha 内容绑定（verified） ([925be42](https://ssh.github.com/443/im47cn/awesome-rules/commit/925be42042b5f52d8ffca926a021237c6fc2ee20))
* **license:** 添加 Apache 2.0 许可证文件 ([066ef52](https://ssh.github.com/443/im47cn/awesome-rules/commit/066ef528a482ea1d0d535a4670f37d5ac600fb51))
* **openapi:** 实现超阈值 tag 按 URI 前缀细分功能 ([9f4b88d](https://ssh.github.com/443/im47cn/awesome-rules/commit/9f4b88de6ff7256299061d2d066ce32493fd14a3))
* **scripts:** Markdown 链接完整性统一门禁（合并 readme_index_check） ([8e301cc](https://ssh.github.com/443/im47cn/awesome-rules/commit/8e301cc94f9caf8ebaacb2a347538abbe83713be))
* **skill-evo:** lesson 溯源三件套（lesson_id/supersedes/证据核验） ([0fa6812](https://ssh.github.com/443/im47cn/awesome-rules/commit/0fa6812512ddd179072e98f6f1b6e489a0af8b92))
* **skill-evo:** omp 原生触发与 GEPA 进化引擎 ([3d16cfb](https://ssh.github.com/443/im47cn/awesome-rules/commit/3d16cfb37c5e9d39c0e022a6cff2b0acd3294369))
* **skill-evo:** 会话经验提取与技能进化提案机制 ([07eae52](https://ssh.github.com/443/im47cn/awesome-rules/commit/07eae522adfa0f568cf38149a05a074994b98497))
* **skill-evo:** 提案目标扩展至根 README/CLAUDE.md 与表格感知应用 ([83f031e](https://ssh.github.com/443/im47cn/awesome-rules/commit/83f031e4cdaeb2d0fc1008aa656ea4b920dbd63f))
* **skill-evo:** 插件哑故障巡检挂车与 patrol 子命令 ([a729445](https://ssh.github.com/443/im47cn/awesome-rules/commit/a72944539a5f028a5669623258707c25405c17aa))
* **skill-evo:** 结构化审核标注（lesson 级 verdict + 语义码） ([45d394c](https://ssh.github.com/443/im47cn/awesome-rules/commit/45d394c4913f9e16901b0c5ceff81857330bd22b))
* **tools:** gauntlet 单一门禁入口——15 层 fail-closed 编排与负控制自测 ([80ecac7](https://ssh.github.com/443/im47cn/awesome-rules/commit/80ecac79dd40ff3d385c6423700431505fe4aed0))
* **tools:** killpg 严格断言静态门 lint-killpg-strict（PR [#37](https://ssh.github.com/443/im47cn/awesome-rules/issues/37) 约定的机器执行层） ([e6d0664](https://ssh.github.com/443/im47cn/awesome-rules/commit/e6d0664371422b64ab6d291b3de52877609f33d5))
* **tools:** plugin_lock 纳入 .agents 入口 + 版本同步检查 ([4e32b96](https://ssh.github.com/443/im47cn/awesome-rules/commit/4e32b9688287668ede6860339748b58eaef1b409))
* **tools:** rejected 存量对账+回执处置协议 ([351f727](https://ssh.github.com/443/im47cn/awesome-rules/commit/351f72705cb6e8dec70a501b1acbc21fcb0e51de))
* **tools:** watch poll interval 1800s to 300s ([939ba8f](https://ssh.github.com/443/im47cn/awesome-rules/commit/939ba8f54173d4923456adb344767a9e22e4fb57)), references [#5](https://ssh.github.com/443/im47cn/awesome-rules/issues/5)
* **tools:** 依赖闭包检查同步——樱桃前 fail-closed ([0227b22](https://ssh.github.com/443/im47cn/awesome-rules/commit/0227b227e238984ac1c17da2420ca13fc4952e22)), references [#22](https://ssh.github.com/443/im47cn/awesome-rules/issues/22)
* **tools:** 安装入口清单 blob 锁定（zero-regression 模式） ([fee7af6](https://ssh.github.com/443/im47cn/awesome-rules/commit/fee7af61ce87c34ae6f0b939ab915a1c5892cab4))
* **tools:** 插件清单版本一致性门禁——gauntlet plugin-versions 层 + NC9 负控制 ([f20afe2](https://ssh.github.com/443/im47cn/awesome-rules/commit/f20afe27712f924d8b92100ad68783f0b8a70634))
* **tools:** 管道早退静态拦截层 lint-pipe-early-exit（[#30](https://ssh.github.com/443/im47cn/awesome-rules/issues/30)） ([c028c58](https://ssh.github.com/443/im47cn/awesome-rules/commit/c028c58011de46650cc9bfa55f13ad7bedeed2c0)), references [#9](https://ssh.github.com/443/im47cn/awesome-rules/issues/9) [#23](https://ssh.github.com/443/im47cn/awesome-rules/issues/23) [etf-radar#70](https://ssh.github.com/443/im47cn/awesome-rules/issues/70)
* 守护报告收据信封与审查报告输出规范 ([8bd5d38](https://ssh.github.com/443/im47cn/awesome-rules/commit/8bd5d389511ae2af4cd285d1d12b94c3209e5542))

### 🐛 Bug 修复

* **api-guard:** 路径命名检查新增畸形短横线检测（段首/段尾/连续） ([54d40b2](https://ssh.github.com/443/im47cn/awesome-rules/commit/54d40b2c0c882077c55105ffc118aaed502ebbcd))
* **arch-hawkeye:** 8 真实仓库聚合实测驱动的边构建层修复 ([66c3236](https://ssh.github.com/443/im47cn/awesome-rules/commit/66c3236a0a1aa5612b4732041688824544c2339d))
* **arch-hawkeye:** CI 样例三处杂项 + 两个真 bug ([2e62075](https://ssh.github.com/443/im47cn/awesome-rules/commit/2e6207583ec36c7bfc625dbed6c2ab67631dac8f))
* **arch-hawkeye:** fingerprint 信息保全 + 豁免状态机收口 ([4ff1615](https://ssh.github.com/443/im47cn/awesome-rules/commit/4ff1615363555a23a1b9babf3c521f08a809eebb))
* **arch-hawkeye:** local_mode 健壮性——路径口径/防混叠/假成功/3.9 ([0a6ea6b](https://ssh.github.com/443/im47cn/awesome-rules/commit/0a6ea6bbf934771b469a70068c2af1c17060529a))
* **arch-hawkeye:** 治理门禁三态语义——失败 ≠ 零违规（fail-closed） ([4884aec](https://ssh.github.com/443/im47cn/awesome-rules/commit/4884aec4a0a7090734b49db52b0e3c598438a586))
* **commitlint:** 添加 'dependency' 到 scope-enum 规则中 ([7a536b9](https://ssh.github.com/443/im47cn/awesome-rules/commit/7a536b9624eb29487407f9a8e7068ef9e07202bf))
* **cov-hooks:** install.sh 缺失提示改指 awesome-rules 克隆路径 ([6a62285](https://ssh.github.com/443/im47cn/awesome-rules/commit/6a6228583595c4473e7ddb13cafa541ce81ffe44))
* **coverage:** 优化 diff-cover 自动安装逻辑，提供安装失败提示 ([7bb6a5b](https://ssh.github.com/443/im47cn/awesome-rules/commit/7bb6a5bfd94d8b252a97c57fa91f5271242e76c5))
* **coverage:** 优化 diff-cover 自动安装逻辑，支持多种 Python 解释器 ([770c76a](https://ssh.github.com/443/im47cn/awesome-rules/commit/770c76a1144fb1c3d5015f9c434ef4cb9538d10e))
* **ddl-guard:** 缩写字典剔除 description→desc（撞保留字） ([35ef7ac](https://ssh.github.com/443/im47cn/awesome-rules/commit/35ef7acfcc668629249f1463eeb87077a91c9d97))
* **ddl-guard:** 表注释正则去嵌套量词，免疫灾难回溯（CodeQL [#1](https://ssh.github.com/443/im47cn/awesome-rules/issues/1)） ([0716221](https://ssh.github.com/443/im47cn/awesome-rules/commit/071622126f0eb775dad72a6dde6fad313450570a))
* **dispatch:** 撞锁提示 $pid 花括号包裹——bash3.2 把紧贴的多字节字符吞进变量名 ([d53b80c](https://ssh.github.com/443/im47cn/awesome-rules/commit/d53b80c15b7dc81ebea75b2ff3516f927d04ef9f))
* **dispatch:** 硬锁挂主工作树——worktree 隔离后跨树互斥 ([39b6b8e](https://ssh.github.com/443/im47cn/awesome-rules/commit/39b6b8ecb6474a57dee859525467a240e3d659f9))
* **dispatch:** 管道子shell后台链不进job表致wait落空，改主shell for 迭代 ([0d947f6](https://ssh.github.com/443/im47cn/awesome-rules/commit/0d947f603ff145f46db1a2251f6bbc7491c57473))
* **doc-gen:** Feign/Kafka/Rabbit 真实形态补验（yp 双仓库实测驱动） ([c1e1b54](https://ssh.github.com/443/im47cn/awesome-rules/commit/c1e1b5429e344fb85943f56bd6b90448d59c56f8))
* **doc-gen:** HTTP 注解正则嵌套量词改单层字符类，免疫 ReDoS（CodeQL [#2](https://ssh.github.com/443/im47cn/awesome-rules/issues/2)/[#3](https://ssh.github.com/443/im47cn/awesome-rules/issues/3)） ([eda1e4d](https://ssh.github.com/443/im47cn/awesome-rules/commit/eda1e4de59611e0599e4c7df51c300b8be6b3ea8))
* **doc-gen:** mermaid/dompurify/nanoid 安全版本升级 ([0fcf5d3](https://ssh.github.com/443/im47cn/awesome-rules/commit/0fcf5d37f84a25908a4852a69d3f335475616bf9)), references [#1-7](https://ssh.github.com/443/im47cn/awesome-rules/issues/1-7)
* **doc-gen:** OpenAPI 细分 tag 撞名消歧（tags 唯一性） ([18ac601](https://ssh.github.com/443/im47cn/awesome-rules/commit/18ac601ba2406814b9cb5eb6fb00647c11cebaf1))
* **doc-gen:** OpenAPI 细分幂等 + {var} 预演一致 + 治理页门控对齐 ([80a6c79](https://ssh.github.com/443/im47cn/awesome-rules/commit/80a6c79162ebe6bffe7482921a1eba37fa4b3802))
* **doc-gen:** 真实仓库实测驱动的提取器修复 + 鹰眼消费者义务落地 ([400cb63](https://ssh.github.com/443/im47cn/awesome-rules/commit/400cb630ff66da12319bb47bd767646a85af2ba2))
* **factory:** feedback 门禁升级 gauntlet + 收编在途改动 ([628e8fc](https://ssh.github.com/443/im47cn/awesome-rules/commit/628e8fc1bd999de62f43d4a70d778b7e8ac8e9c2)), references [#7](https://ssh.github.com/443/im47cn/awesome-rules/issues/7)
* **factory:** gh pr create 显式 --repo/--head——origin fetch URL 是 codeup，gh 无法解析 ([9bc677b](https://ssh.github.com/443/im47cn/awesome-rules/commit/9bc677bcf3d5d286b824157e87ff0eab772d1d92))
* **factory:** REPO_SLUG 管道去 grep -m1 早退形态 ([a4d8193](https://ssh.github.com/443/im47cn/awesome-rules/commit/a4d8193019bcb0a71fc4885f7ba50efe8c95ff8f)), references [#30](https://ssh.github.com/443/im47cn/awesome-rules/issues/30) [etf-radar#70](https://ssh.github.com/443/im47cn/awesome-rules/issues/70) [#30](https://ssh.github.com/443/im47cn/awesome-rules/issues/30)
* **factory:** trap set+e 纵深+失败链 salvage push（[#23](https://ssh.github.com/443/im47cn/awesome-rules/issues/23) [#14](https://ssh.github.com/443/im47cn/awesome-rules/issues/14)） ([610c5c2](https://ssh.github.com/443/im47cn/awesome-rules/commit/610c5c21a5a022e178e7ea0ad023be7dc6932938))
* **factory:** triage 批次 gh 瞬断输出降级为可诊断跳过 ([c22130d](https://ssh.github.com/443/im47cn/awesome-rules/commit/c22130dffbd7fe8d4c769be31858e35e1d6859e5)), references [#30](https://ssh.github.com/443/im47cn/awesome-rules/issues/30)
* **factory:** triage 拒绝附判据明细回执评论——根治静默拒绝 ([5f97551](https://ssh.github.com/443/im47cn/awesome-rules/commit/5f975518e4e4fdc9c04ba3557c739bb0d5ad568b))
* **factory:** write_ledger 管道吞码 | true → || true——pipefail ([#70](https://ssh.github.com/443/im47cn/awesome-rules/issues/70)) ([61c119c](https://ssh.github.com/443/im47cn/awesome-rules/commit/61c119c2df59d391da9d91ebbe6de80c3e93cc56)), closes [PR#18](https://ssh.github.com/443/im47cn/awesome-rules/issues/18), references [etf-radar#57](https://ssh.github.com/443/im47cn/awesome-rules/issues/57) [#23](https://ssh.github.com/443/im47cn/awesome-rules/issues/23) [#18](https://ssh.github.com/443/im47cn/awesome-rules/issues/18) [#26](https://ssh.github.com/443/im47cn/awesome-rules/issues/26) [#9](https://ssh.github.com/443/im47cn/awesome-rules/issues/9) [#23](https://ssh.github.com/443/im47cn/awesome-rules/issues/23)
* **factory:** 三链并发事故修复——D1手动互斥/D2链禁推main/D4队列跳过在跑issue ([8dc079d](https://ssh.github.com/443/im47cn/awesome-rules/commit/8dc079d04bbbf47c2e30f7fab82ba8a13ebe6048))
* **factory:** 审查修复——回执数据侧标记中和/标量 reasons/关联段 ([c3dde8c](https://ssh.github.com/443/im47cn/awesome-rules/commit/c3dde8c52b377f6458959e10d4f19d82f768a888)), references [#20](https://ssh.github.com/443/im47cn/awesome-rules/issues/20)
* **factory:** 审查修复——回执数据侧标记中和/标量 reasons/关联段 ([#67](https://ssh.github.com/443/im47cn/awesome-rules/issues/67)) ([2a866f9](https://ssh.github.com/443/im47cn/awesome-rules/commit/2a866f90919b2b2149482a96c8fe8d3eeed3ddac))
* **factory:** 审查修复——配额串行化/围栏全量覆盖/注入面收口 ([b01c6ea](https://ssh.github.com/443/im47cn/awesome-rules/commit/b01c6eae181f481a9a1c9d9d6312639dbb1b4dab)), references [PR#34](https://ssh.github.com/443/im47cn/awesome-rules/issues/34)
* **factory:** 干净合流 c6 终版，剔除 alice/t 污染提交 ([baccf3c](https://ssh.github.com/443/im47cn/awesome-rules/commit/baccf3c04629e6f1197d835d6c783dc4baf266b9))
* **factory:** 恢复 cron 包装器 + 修 triage REPO_SLUG 单 remote 缺陷 ([f12d51b](https://ssh.github.com/443/im47cn/awesome-rules/commit/f12d51b20dc7bc7d145b48e54e58ff425bda5ff7)), references [14/#10](https://ssh.github.com/443/im47cn/awesome-rules/issues/10) [#10](https://ssh.github.com/443/im47cn/awesome-rules/issues/10)
* **factory:** 标签转移改单请求原子换，失败链终止 ([726c80e](https://ssh.github.com/443/im47cn/awesome-rules/commit/726c80ee02b5b109eaab0901080065f49fe8ef96))
* **factory:** 节点函数裸调用根治 set-e 条件上下文豁免面 + trap pipefail 吞错假象 ([c749ac5](https://ssh.github.com/443/im47cn/awesome-rules/commit/c749ac5ead8f06213e33bc6db213db2bbb3b7a02)), references [#9](https://ssh.github.com/443/im47cn/awesome-rules/issues/9)
* **factory:** 链分支 checkout -B 从 main 重建——|| true 掩盖落在当前分支事故 ([d516a8c](https://ssh.github.com/443/im47cn/awesome-rules/commit/d516a8c2276f83591769fca564658e647734a268))
* **factory:** 链读 issue 评论——整改重投指令的载体 ([8589567](https://ssh.github.com/443/im47cn/awesome-rules/commit/8589567f0a8a3f1c5f1e51ca341f01114b7a3978))
* **factory:** 门超时改杀整个进程组——防孤儿污染还原窗口 ([ca312ce](https://ssh.github.com/443/im47cn/awesome-rules/commit/ca312ce4db5a7e89d40e4db2dfd9945c993a8b85)), references [#33](https://ssh.github.com/443/im47cn/awesome-rules/issues/33)
* **factory:** 预建 needs-review 标签 + S1 链占 in-progress 防派发器重复认领 ([e696415](https://ssh.github.com/443/im47cn/awesome-rules/commit/e69641574675569a7ae9390f658863ea7ca7efa1))
* **feedback:** dry-run 不再做上游配置变更——remote add 移至出口后 ([#71](https://ssh.github.com/443/im47cn/awesome-rules/issues/71)) ([db09bba](https://ssh.github.com/443/im47cn/awesome-rules/commit/db09bba1c1889f9c7082d8fe879f4b6775c320cf)), references [im47cn/awesome-rules#26](https://ssh.github.com/443/im47cn/awesome-rules/issues/26)
* **feedback:** 上游仓 bare 化适配——git 层探测 + 漂移报告走 worktree ([c874666](https://ssh.github.com/443/im47cn/awesome-rules/commit/c8746663c05334da46f9a7978f8b5ec18213bcce)), references [#7](https://ssh.github.com/443/im47cn/awesome-rules/issues/7)
* **feedback:** 适配节点越界收口 + 账本 SHA 语义缺口（superseded 判定） ([8f47df7](https://ssh.github.com/443/im47cn/awesome-rules/commit/8f47df7a93efbdf5417de77b50a9b8c34469c308)), references [etf-radar#71](https://ssh.github.com/443/im47cn/awesome-rules/issues/71) [etf-radar#66](https://ssh.github.com/443/im47cn/awesome-rules/issues/66) [66/#71](https://ssh.github.com/443/im47cn/awesome-rules/issues/71) [66/#71](https://ssh.github.com/443/im47cn/awesome-rules/issues/71) [etf-radar#57](https://ssh.github.com/443/im47cn/awesome-rules/issues/57)
* **git:** 覆盖基线增量修正与多模块jacoco适配 ([6c79490](https://ssh.github.com/443/im47cn/awesome-rules/commit/6c79490771cba2a30bdfd1a831dae00da29c6936))
* **hooks:** load-steering 单文件容错，坏文件不再阻断索引生成 ([3f07086](https://ssh.github.com/443/im47cn/awesome-rules/commit/3f07086d8e2a526b44c95989aa2e4e94961971db))
* **impact-guard:** 补齐 Python 3.9 兼容 ([8ae5003](https://ssh.github.com/443/im47cn/awesome-rules/commit/8ae5003521e797aae98ae4aabadb73722afb37b0))
* **mutations:** killpg 断言与杀组容忍 macOS 僵尸窗口 EPERM ([8bb356f](https://ssh.github.com/443/im47cn/awesome-rules/commit/8bb356fa32af013e5d5b201df90f45bc4b96b1a3)), references [#33](https://ssh.github.com/443/im47cn/awesome-rules/issues/33)
* **mutations:** 审查修复——EPERM 吞掉点显式化前提+诊断、docstring 两处过时 ([3cbe7da](https://ssh.github.com/443/im47cn/awesome-rules/commit/3cbe7da10470084b408021a85302990d7e73628a)), references [#36](https://ssh.github.com/443/im47cn/awesome-rules/issues/36)
* **scripts:** 链产物死链误报推送门 ([6228fd9](https://ssh.github.com/443/im47cn/awesome-rules/commit/6228fd9d2dd9930e77c0c2d7622ea22a91b18140))
* **state:** sync --all 并入 open PR 的 closingIssues——零标签 issue 也可收敛 ([dd08466](https://ssh.github.com/443/im47cn/awesome-rules/commit/dd0846692d1b10b23abd43548c654e58310b6075))
* **tools:** .factory shell 三层门封 feedback 逃逸 ([4ff7363](https://ssh.github.com/443/im47cn/awesome-rules/commit/4ff7363a6ad990a7959fd41e188ec5e47fa38a00))
* **tools:** badcase 期望模型双通道——脚本检出与人工补充分离 ([411be7d](https://ssh.github.com/443/im47cn/awesome-rules/commit/411be7d4f7caa5ddf9ccfc8e96047f4be475a6ea))
* **tools:** PR[#18](https://ssh.github.com/443/im47cn/awesome-rules/issues/18) 审查评论2/3/4 修复 ([fbf1028](https://ssh.github.com/443/im47cn/awesome-rules/commit/fbf10286ff2f4f2f5fa77b569cc31624cd56c2bc))
* **tools:** PR[#9](https://ssh.github.com/443/im47cn/awesome-rules/issues/9) 审查评论1/3 修复 ([93047d3](https://ssh.github.com/443/im47cn/awesome-rules/commit/93047d3502a91317f7c1303e1002cb76e827c0bf))
* **tools:** 审查修复——K2 识别 raises(expected_exception=PLE) 关键字形式 ([a3d70df](https://ssh.github.com/443/im47cn/awesome-rules/commit/a3d70dfb00d6e6a479ae63f244a3eeb06c714a0d)), references [#38](https://ssh.github.com/443/im47cn/awesome-rules/issues/38) [#37](https://ssh.github.com/443/im47cn/awesome-rules/issues/37)
* **tools:** 检查器词法盲区修复——转义/注释/heredoc后缀/||边界 ([8d2b20f](https://ssh.github.com/443/im47cn/awesome-rules/commit/8d2b20f05bae681f383f7e47256eed05bd530ad2)), references [#32](https://ssh.github.com/443/im47cn/awesome-rules/issues/32)
* **tools:** 清残留 head 非末位管道两处（同形审计） ([95c4e65](https://ssh.github.com/443/im47cn/awesome-rules/commit/95c4e65b85d47527580b85b7130d097571a19c67)), references [#30](https://ssh.github.com/443/im47cn/awesome-rules/issues/30)
* **tools:** 版本门禁审查修复——解析加固/顶层验证/发布面=tracked + NC9d/e ([7bf0ad1](https://ssh.github.com/443/im47cn/awesome-rules/commit/7bf0ad1666386ce715a669026b6245687766b1e5))
* **tools:** 移除 manifest 重复 hooks 声明，修复插件加载失败 ([9a32584](https://ssh.github.com/443/im47cn/awesome-rules/commit/9a32584ff55478090b29fe4a1b50b4db3af8660f))
* **tools:** 覆盖率红线 95→80 对齐 steering（[#3](https://ssh.github.com/443/im47cn/awesome-rules/issues/3)） ([9fa5814](https://ssh.github.com/443/im47cn/awesome-rules/commit/9fa581428fc5ffe668e771d505e837ab3b0b27d3))
* **tools:** 门禁扫描面统一 tracked 面原则 ([67c2965](https://ssh.github.com/443/im47cn/awesome-rules/commit/67c2965b36cc8180a897db187ef34f3493fede81))
* 套件测试密封化——import 期剥 GIT_* 根治 GIT_DIR 劫持 ([9024926](https://ssh.github.com/443/im47cn/awesome-rules/commit/902492615992beee8329024d32fe209e2d0f2b0a))

### ⚡ 性能

* **doc-gen:** blame 归属按文件批量——子进程数从行数级降到文件数级 ([32a3e8c](https://ssh.github.com/443/im47cn/awesome-rules/commit/32a3e8cbf1123b27ee57180ad068632a0d821185))

### ♻️ 重构

* **factory:** cron */10 换 dispatch --watch 常驻，删 cron 包装器 ([98bdabb](https://ssh.github.com/443/im47cn/awesome-rules/commit/98bdabbc833b21c3300cc46b481808ab8e1d7833))
* **factory:** 同步模板对账吸收——锁全局化/REPO_SLUG链式/bash3.2/suites双布局 ([b550c1b](https://ssh.github.com/443/im47cn/awesome-rules/commit/b550c1b6f12c67166c9a98afef8fcfe7edd43bc7))
* **factory:** 标记中和下沉到 issue 评论唯一出口 issue_comment() ([#21](https://ssh.github.com/443/im47cn/awesome-rules/issues/21)) ([58cf221](https://ssh.github.com/443/im47cn/awesome-rules/commit/58cf221242cb580fc5e241c34b83ddb2eea1525d)), references [#20](https://ssh.github.com/443/im47cn/awesome-rules/issues/20)
* **factory:** 标记中和下沉到 issue 评论唯一出口 issue_comment() ([#68](https://ssh.github.com/443/im47cn/awesome-rules/issues/68)) ([9ad9ea5](https://ssh.github.com/443/im47cn/awesome-rules/commit/9ad9ea5620d156e61dad01f160002c9eb634ae34))
* 抽 guard 共享库 skills/_shared/guard_lib.py ([a324297](https://ssh.github.com/443/im47cn/awesome-rules/commit/a324297c054b0d49ca4020db679bfce3e4262496))

### 📝 文档

* **api-guard:** 规则表路径命名行对齐脚本真实检查项，补畸形短横线语义 ([81a67ad](https://ssh.github.com/443/im47cn/awesome-rules/commit/81a67ad5969eb131f3ef8f60fa5afbb119fd90a0)), closes [#5](https://ssh.github.com/443/im47cn/awesome-rules/issues/5)
* **arch-guard:** GTSP 试点 ArchUnit 接入经验沉淀 ([0a9081c](https://ssh.github.com/443/im47cn/awesome-rules/commit/0a9081cea3a6b38f9642fbd00686b11ce4aa0ba0))
* **arch-hawkeye:** CI 治理管线接线样例（scan→gate 三段式收官） ([8f2487e](https://ssh.github.com/443/im47cn/awesome-rules/commit/8f2487ec867e9a2ccf2acff271729f88917c27c9))
* **arch-hawkeye:** 契约明确聚合产物豁免 per-project 校验 ([9cc853d](https://ssh.github.com/443/im47cn/awesome-rules/commit/9cc853db00362fbc44891eeb8c3c702eecf3144b))
* **arch-hawkeye:** 清理 requirements.md 死引用 ([fde491e](https://ssh.github.com/443/im47cn/awesome-rules/commit/fde491ed98c02deb01b4b526b30c381432ffe00e))
* **code-review:** README 记录上游参考源与定期对齐约定 ([742bb0e](https://ssh.github.com/443/im47cn/awesome-rules/commit/742bb0ef47d36f8b18b8d52dc1a76b7820bfe5a7))
* **factory:** kill-rate ≥80% 判据已证收口（S1→L3） ([d863c74](https://ssh.github.com/443/im47cn/awesome-rules/commit/d863c742a5c0c6ac15efeb9088485f58e8aea6d6))
* **factory:** Popen 安全审计落档——argv 闭集无注入通道 ([87c491f](https://ssh.github.com/443/im47cn/awesome-rules/commit/87c491f5380f2affd06801362e9f527d78b8a598)), references [#33](https://ssh.github.com/443/im47cn/awesome-rules/issues/33)
* **factory:** 判据b doc-only 零投影措辞（[#24](https://ssh.github.com/443/im47cn/awesome-rules/issues/24)） ([f0dcc74](https://ssh.github.com/443/im47cn/awesome-rules/commit/f0dcc74a7b81547953e308b42199b33a0f91a72a))
* **factory:** 协议补一条——历史重写后 fsck 盘点孤儿、人工鉴定再丢弃 ([c1ef09f](https://ssh.github.com/443/im47cn/awesome-rules/commit/c1ef09f34d4b4c59c38ce635b64c4b3417bbeac6))
* **factory:** 铁律4修宪与单实例假设退役 ([10f7183](https://ssh.github.com/443/im47cn/awesome-rules/commit/10f7183cb85b10a61917bc5c41d4539ef3779863))
* gtsp 跨文档引用改为可解析相对路径 ([4af9a42](https://ssh.github.com/443/im47cn/awesome-rules/commit/4af9a423a87cf09ef77d8c0a0bf7a626a418a18e))
* README 目录树与索引同步（skill-evo/hooks/审查规范/三份设计文档） ([f779f42](https://ssh.github.com/443/im47cn/awesome-rules/commit/f779f42b6a76d47de162d4b079af2f9e80b01b94))
* **skill-evo:** 应用提案 20260820-1532（审核决策路径沉淀） ([dde12e2](https://ssh.github.com/443/im47cn/awesome-rules/commit/dde12e2801d8a7459945625855da848160885358))
* **skill-evo:** 补充 README（修复索引死链） ([8152f0a](https://ssh.github.com/443/im47cn/awesome-rules/commit/8152f0ae8ac1191d235217ac08b57f0e4678e026))
* **skill-evo:** 门禁引用同步合并后命名与节号修正 ([2bac57a](https://ssh.github.com/443/im47cn/awesome-rules/commit/2bac57a37eb0e523242d19afebd5666bddf98ff0))
* **skills:** 四技能 SKILL.md 渐进式加载重构 ([55d6616](https://ssh.github.com/443/im47cn/awesome-rules/commit/55d6616bfa71053f6545a96b6f32d15c9f349182))
* **skills:** 新增 tokensave-mcp 技能（mcporter 代理模式） ([ef4b66b](https://ssh.github.com/443/im47cn/awesome-rules/commit/ef4b66b5e668f485da16c0f32a2f7783f2fb8519))
* **steering:** 历史泄漏整改与 PR 协作经验固化 ([da7e6b1](https://ssh.github.com/443/im47cn/awesome-rules/commit/da7e6b16a2a012e83f6de41d2d1f9ff9a9f76cb5))
* **steering:** 审查修复——同步纪律明确同步对象与分叉处置 ([6bda529](https://ssh.github.com/443/im47cn/awesome-rules/commit/6bda5299eb3b065de70b7e2ec3af2da67986ed83)), references [#39](https://ssh.github.com/443/im47cn/awesome-rules/issues/39)
* **steering:** 应用 skill-evo 提案 20260819/20260820（6 lessons） ([c8384ed](https://ssh.github.com/443/im47cn/awesome-rules/commit/c8384ed207e99bef8d1df45521590aa7a62bbe91))
* **steering:** 新增同步纪律——fetch 先于状态判断、开工先 pull --ff-only ([1a3709e](https://ssh.github.com/443/im47cn/awesome-rules/commit/1a3709e41d6b079645a1ab0a54a1227971a41415))
* **testing:** 审查修复——探活 rc=0 语义不跨平台等同真活成员 ([fe35bb7](https://ssh.github.com/443/im47cn/awesome-rules/commit/fe35bb738a9fc58457afd90400438a93d17bf78b)), references [#37](https://ssh.github.com/443/im47cn/awesome-rules/issues/37) [#36](https://ssh.github.com/443/im47cn/awesome-rules/issues/36)
* **testing:** 进程组信号平台语义约定——探活容忍 macOS 僵尸窗口 EPERM ([d2addf8](https://ssh.github.com/443/im47cn/awesome-rules/commit/d2addf8a8d64867f510b241855dfe8d434886276)), references [#36](https://ssh.github.com/443/im47cn/awesome-rules/issues/36) [#36](https://ssh.github.com/443/im47cn/awesome-rules/issues/36)
* 修 GTSP 规范三处内部矛盾 ([c4d7513](https://ssh.github.com/443/im47cn/awesome-rules/commit/c4d75139240de5faf64ad5005e46fe7a1d3d9574))
* 修正插件分发语义并补版本发布纪律——快照加载/版本门控实证 ([ec7d8d1](https://ssh.github.com/443/im47cn/awesome-rules/commit/ec7d8d1cb7f015eb011d2d44a1a0845218dc9961))
* 修正表格格式以提高可读性 ([296b35e](https://ssh.github.com/443/im47cn/awesome-rules/commit/296b35e936f02057ee91c1d9e395d9579a982843))
* 全量文档同步——需求规格重建 + 能力落地状态 ([f1329bd](https://ssh.github.com/443/im47cn/awesome-rules/commit/f1329bd6888bc060672bc9890842b506353d5693))
* 根 README 同步现状 ([95b480d](https://ssh.github.com/443/im47cn/awesome-rules/commit/95b480d4873b79c8c65381420cfecd23b0c7e392))
* 补 archify 再对比结论（§9：借鉴点 5/5 收口，演进分道扬镳） ([8945421](https://ssh.github.com/443/im47cn/awesome-rules/commit/894542121b78026f1c3d4076d2a7b94b5165b218))
* 补充覆盖率统计范围与排除实践 ([d0dafee](https://ssh.github.com/443/im47cn/awesome-rules/commit/d0dafee2e577c2f7fc9d90c77921ace5335279fc))

### ✅ 测试

* **api-guard:** README 规则表路径命名行一致性测试，防文档漂移复发（issue [#5](https://ssh.github.com/443/im47cn/awesome-rules/issues/5)） ([5b5ac33](https://ssh.github.com/443/im47cn/awesome-rules/commit/5b5ac3360d256b4939e30c63413f0e9098099298))
* **api-guard:** 断言失败消息附当前规则行便于定位 ([ce35d0c](https://ssh.github.com/443/im47cn/awesome-rules/commit/ce35d0c6b467525b450ae5468f0795ab0b9bfcab)), references [#5](https://ssh.github.com/443/im47cn/awesome-rules/issues/5)
* **api-guard:** 补强畸形短横线测试断言与测试类文档同步 ([e1f8e11](https://ssh.github.com/443/im47cn/awesome-rules/commit/e1f8e11288d429f3a0cc22207ca4aa9e7020ad97))
* **arch-hawkeye:** builder.astro 依赖守护——封住跨工程渲染依赖的缝 ([a79b26a](https://ssh.github.com/443/im47cn/awesome-rules/commit/a79b26a5c3fc663150c525486fb63128366eca6a))
* **ddl-guard:** 联合索引字段数规则补测试并修正 badcase 误记 ([5b11e5d](https://ssh.github.com/443/im47cn/awesome-rules/commit/5b11e5deb012131bdf241e7d4f637d33819a57a0))
* doc-gen↔鹰眼交接验证 + JS 冒烟防线 + 生态注册 ([fdd0d63](https://ssh.github.com/443/im47cn/awesome-rules/commit/fdd0d638c9560fdbbfaff18e7857a84d4cfc5157))
* **doc-gen:** test_delta 补 Python 3.9 future import ([7a3c435](https://ssh.github.com/443/im47cn/awesome-rules/commit/7a3c435ab47fc6eee0ab56ba16226a857ecea83c))
* **factory:** feedback 测试入 tests 进全量门禁（[#16](https://ssh.github.com/443/im47cn/awesome-rules/issues/16)） ([4cf8ac6](https://ssh.github.com/443/im47cn/awesome-rules/commit/4cf8ac6f3d6420224371aaa5ff61bf66754dc0db))
* **factory:** 仲裁层 schema 行为测试（24 用例真 PG） ([8ed8bc5](https://ssh.github.com/443/im47cn/awesome-rules/commit/8ed8bc59d19e8ede1cf8fec72def25fb9bf54e3b))
* **skill-evo:** repo_root 假红根除——目录名断言改结构不变量锚 ([db01fc9](https://ssh.github.com/443/im47cn/awesome-rules/commit/db01fc9e8c8aabedd70f727b372e719b47b54cdd))
* **skill-evo:** repo_root 断言去环境耦合——目录名随 worktree 变化 ([d26b2cd](https://ssh.github.com/443/im47cn/awesome-rules/commit/d26b2cd0530dff5e5e7d905f899a27458d5faf53))
* **skill-evo:** repo_root 负例断言——非根祖先不含根 marker ([d4f121f](https://ssh.github.com/443/im47cn/awesome-rules/commit/d4f121f73d5ce96f44b15428a967d96469834d13))
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
