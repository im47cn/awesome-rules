# 任务包模板对照实验 — 预注册协议

日期：2026-09-13 ｜ 基线：9a76f276245838db9d682e0c3d32928850335e52

## 设计
- 双臂：FIVE（五要素框架：目标/证据/约束/状态/验收 + 执行前查三类噪声）vs CONTRACT（契约式 4+1：目标+反目标/双层验收/falsifier 中止/状态写协议/约束分级/升级条款）
- 同臂 3 个任务共用一个 clone（文件所有权互不相交）：
  - cloneA = FIVE，cloneB = CONTRACT
- 任务信息与验收标准在两臂间逐字对齐，唯一差异是打包结构
- 6 个 omp headless 并行运行，--max-time 20m

## 任务
- T1: tools/check_frontmatter_fields.py + tests/test_check_frontmatter_fields.py
- T2: tools/check_readme_index.py + tests/test_check_readme_index.py
- T3: tools/gen_frontmatter_report.py + docs/reports/frontmatter-coverage.md + tests/test_gen_frontmatter_report.py

## 预注册验收（两臂同一裁判标准，机械为主）
每任务 5 项硬性检查（由主会话在 clone 内执行）：
1. `python3 -m pytest <testfile> -q` exit 0
2. 测试文件含 4 个（T1/T2）/3 个（T3）独立构造的负控制用例（tmp_path/tempdir，不依赖仓库真实文件）——grep 断言
3. CLI 语义抽查：构造违规样例运行，exit code 与输出符合任务书
4. T3 附加：脚本运行两次输出 byte-identical（diff 验证）
5. 范围合规：`git -C <clone> status --porcelain` 中变更文件仅限任务书声明的所有权清单

## 返工协议
- 首轮交付后主会话逐项跑硬性检查
- 任一失败 → 发 1 轮返工（附失败输出原文），再跑；仍失败发第 2 轮后终止记 FAIL
- 指标：一次通过数 /3、累计返工轮数、范围违规数

## 已知混杂（诚实声明）
- n=3、同族任务（均为 Python+pytest 小型工具），外部效度受限
- 裁判非盲（知晓臂别），但检查项全部机械可执行
- CONTRACT 包 token 数略高（多了反目标/升级条款），信息量差异是设计意图的一部分

## falsifier（推翻"契约式更优"的证据）
- 两臂一次通过率与返工轮数无差异（3:3 或差异 ≤1 轮）→ 模板不敏感，问题在别处
- FIVE 臂全面占优 → 契约式是过度设计，弃
