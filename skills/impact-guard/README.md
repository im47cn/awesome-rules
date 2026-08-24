# impact-guard

变更影响分析技能 — 给定变更点，沿图谱计算受影响范围，按「直接/间接」+ GTSP 业务边界分级。

> **状态**：✅ v1 + v2 已实现（quick = Tier 1 import 索引独立可用；graph = Tier 2 Cypher 生成由 Agent 编排执行；v2 = 方法级 diff + 跨服务契约传播）。测试：`pytest skills/impact-guard/scripts/tests -q`；fixture `fixtures/ddd-sample` 覆盖 5 通道边界。

## 架构

| 层级 | 工具 | 精度 | 适用场景 |
|---|---|---|---|
| **Tier 2（主）** | `codebase-memory-mcp` `query_graph` Cypher | 方法级 `qualified_name` | 默认路径、PR 证据链 |
| **Tier 1（fallback）** | `impact_check.py`（import 反向索引） | 文件/类级 | 项目未 index 时降级 |

## 快速使用

### 新项目接入

```bash
# 1. 扫描注解动态生成配置（5 通道边界 + highways，不写死 glob）
python3 scripts/impact_check.py . --init

# 2. 分析本次变更影响（默认对比 origin/master...HEAD；过期图谱自动 reindex）
python3 scripts/impact_check.py . --diff origin/master...HEAD --strict

# 3. 触及 🔴 直接才阻断；间接抵达仅告警
```

### 指定变更点（不依赖 git）

```bash
python3 scripts/impact_check.py . --changed com.example.order.app.OrderCreateExecutor --format mermaid
```

> 完整参数由脚本实时输出：`python3 scripts/impact_check.py --help`

**退出码**：`0` = 无 🔴 直接影响 · `1` = 触及 🔴 直接（`--strict`）· `2` = 运行错误

## 影响方向

| 变更点类型 | 产出 |
|---|---|
| 普通类（Service/Assembler） | inbound 证据链：谁调用了我 |
| 框架入口（Controller/MQ Listener/Job/Callback 实现） | 无法分析 inbound + 下游回归范围建议（不伪装成影响分析） |

## 关键路径分级（直接/间接）

| 级别 | 触发 | 含义 |
|---|---|---|
| 🔴 **直接** | 变更点本身是出站/落点（Feign/Mapper/Redis 写/MQ Producer/`-client`） | 直接动契约/数据，门禁阻断 |
| 🟠 **间接抵达** | 普通类变更，影响链抵达边界 | 潜在波及，告警 + 回归建议 |
| 🟡 Warning | 穿越跨服务边界（本服务内）/ 聚合根 | 需人工确认 |
| 🟢 Info | 仅内部实现 | 低风险 |

**5 通道边界**（HTTP/MQ/DB/缓存/定时）由 `--init` 扫描注解生成，glob 仅手动覆盖。

## 不沉默告警

- **跨服务契约**：变更触及 `@FeignClient`/`-client` → 🔴 直接 + `⚠️ 跨服务影响未分析`
- **过期图谱**：`head_sha` 不一致 → 自动 reindex（`--skip-reindex` 跳过 + 告警）

## Tier 2 深度审查

**前置**：项目已 `index_repository`。

```bash
# 动态生成适配本项目的 Cypher 清单（不手抄，避免漂移）
python3 scripts/impact_check.py --mode graph --config .impact-guard.json
```

输出查询粘贴到 `query_graph` 执行，拿方法级证据链。

## CI 集成

```yaml
- name: 变更影响门禁
  run: |
    python3 skills/impact-guard/scripts/impact_check.py src/ \
      --diff origin/master...HEAD --strict --format json
```

仅触及 🔴 **直接**（直接改了 Feign/Mapper/对外 API）才 exit 1 阻断合并；间接抵达不阻断。

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 技术设计：[`DESIGN.md`](DESIGN.md)
- 完整论证（评审稿，含 grill 决策）：[`../../docs/design/impact-guard-design.md`](../../docs/design/impact-guard-design.md)
- 架构规范：[`../../steering/gtsp/01-project-structure.md`](../../steering/gtsp/01-project-structure.md)
