---
name: arch-guard
description: >
  DDD 架构分层守护，两层架构：(1) 脚本快速巡检（CI 门禁，覆盖 pom 依赖、命名后缀、领域层框架引用），
  (2) 知识图谱深度审查（精确到 qualified_name 的层间逆向依赖证据链）。
  当用户提到：架构审查、架构检查、分层检查、包依赖检查、DDD 规范检查、架构守护、
  依赖方向、领域层纯净度、Maven 模块依赖时激活。
---

# DDD 架构分层守护

Tier 1 脚本巡检（文件级，CI 门禁）+ Tier 2 知识图谱深度审查（方法级证据链）。
接入流程、配置详解、检查覆盖清单、CI 集成样例见 [README](README.md)
（渐进式加载：本文件只保留审查执行所需）。

> Tier 1 正则仅检查 import 语句，无法发现内联全限定名/字段类型/构造器参数的逆向依赖；
> 重要项目建议与 ArchUnit（字节码）生成测试双跑互补。

## 审查工作流

- 被审项目 HEAD 自带坏测试阻塞编译时：不修改用户代码，临时移出编译路径，
  跑完检查后原样恢复，并在报告中注明移出清单
- 接入前先用 `mvn test` 验证项目可独立编译：GTSP 试点实测公共依赖（如 fss-common
  的 lombok）声明为 `provided` 不传递，需先补齐缺失依赖再接入

### Tier 1: 快速巡检（脚本）

```bash
python3 scripts/arch_check.py <项目根目录> [--format json] [--strict] [--config .arch-guard.json]
```

- `--strict` 推荐问题升级为强制；`--init` 自动生成最小配置（从 pom.xml 推断 prefix）
- 退出码：`0`=通过，`1`=有强制问题，`2`=运行错误
- 检查项明细见 README「脚本检查覆盖」；存量项目用基线 ratchet
  （`--refreeze` 冻结 → `--baseline ... --strict --frozen` 只报新增，见 README）

### Tier 2: 深度审查（知识图谱）

前置：项目已通过 `codebase-memory-mcp` 建立索引。**Cypher 查询清单由脚本动态生成**，
文档不手抄副本（脚本是 single source of truth）：

```bash
python3 scripts/arch_check.py --mode graph [--config .arch-guard.json]
```

将输出的任意查询粘贴到 `query_graph` 执行；结果每行一条违规（caller → callee 精确链路），
覆盖 6 个依赖方向。知识图谱天然不索引第三方包，无需配置 prefix。

### 补充人工判断

读取 [`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)
逐项核对自动检查盲区（对照表见 README「需人工补充的规则」）：聚合设计合理性、
值对象不可变性（setter）、应用服务是否含业务逻辑、跨域通信是否偏向事件解耦。

## 报告收据（receipt）

JSON 输出（`--format json`）顶层携带 `receipt` 收据信封，规范见
[`../../docs/design/guard-receipt-spec.md`](../../docs/design/guard-receipt-spec.md)：

- `decision`：`gate`（pass/block）+ 强制问题 `rule_code` 去重列表，CI 可程序化匹配
- `provenance`：扫描量（Java/pom 文件、分类情况）、基线路径与抑制/收缩计数
- `boundary`：降级声明（Tier 1 文件级启发式）+ 未覆盖声明（Tier 2 方法级依赖、聚合设计等）

text 输出在所有路径末尾投影「── 证据边界 ──」段——**报告主动声明自身精度与盲区，
防止被读者当成全面事实**。

## 红线（易踩坑）

- `project_package_prefix` 必须收紧到本项目业务包（如 `com.wanlianyida.gtsp.wop.gateway`），
  禁止公司级全局前缀——全局前缀会把 fss-api 等契约类扫进分层规则产生误报
- 修改 pom.xml 时 XML 注释内禁止出现 `--`（CLI 参数写进注释会破坏 XML 解析），改写为
  `mode archunit` 等无连字符措辞
