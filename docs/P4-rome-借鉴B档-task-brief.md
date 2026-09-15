# 任务书:P4-rome-借鉴B档落地-开发工程师Sam

> 背景:rome-os/rome 四轮代码级验证已完成（docs/research/rome.md，零代码变更零 commit）。用户 2026-09-15 晨间裁决借鉴范围 = **B 档**：A 档（frontmatter 解析器做法）+ skills 清单门禁；**不做 C 档系统性移植**。本任务把验证结论转化为最小、可独立回退的实现。

# Target
- 依据:docs/research/rome.md 四轮验证结论中 frontmatter 解析与 skills 清单治理两部分（落点以其指认为准，本任务书不代答）
- 范围:仅 awesome-rules 本仓；不重构既有 guard 架构；不动消费仓（downstream.json 各仓）
- 非目标:C 档系统性移植；分发套件改造（P3 范畴）；审查报告标准（另行治理）

# Change
1. A 档——frontmatter 解析器对齐:按调研报告指认的做法收敛到单一解析路径，消灭旁路解析
2. B 档——skills 清单门禁:清单文件为唯一真相源，漂移可机械检测，本地 + CI 双入口
3. 移植面最小化:每个借鉴点独立 commit，可独立 revert；不与无关重构混提

# Acceptance
- 负控制一:新增未登记 skill → 门禁报警（非静默通过）
- 负控制二:删除已登记 skill → 门禁报警
- frontmatter 解析唯一性有测试佐证（旁路解析负控制被捕获）
- 全量回归绿；零外发（push/PR 需用户显式授权）
- 强制条款:冲突不得以既有架构顺延 spec，必须上报用户裁决
