# api-guard

Open API 设计与规范审查技能。

## 能力

1. **审查 API 定义** — 运行检查脚本自动检查 Controller 中的路径/方法/命名规则，再补充人工判断
2. **设计新 API** — 按规范生成合规的 API 端点定义

## 快速使用

```bash
# 审查所有 Controller 文件
python3 scripts/api_check.py

# 审查指定路径
python3 scripts/api_check.py path/to/controller_or_project/

# JSON 格式输出
python3 scripts/api_check.py path/to/project/ --format json
```

**退出码**：`0` = 通过，`1` = 有强制问题，`2` = 运行错误

## 脚本检查覆盖

| 类别 | 检查项 |
|---|---|
| 路径结构 | `/{domain}/{version}/{resource}/{action}` 四段式结构 |
| HTTP 方法 | 统一 POST，禁止 GET/PUT/DELETE/PATCH |
| 命名规范 | 全小写 kebab-case，禁止 camelCase 和下划线 |
| 动词后置 | action 段在末尾（如 `/waybill/sync` 而非 `/syncWaybill`） |
| 动作收敛 | 末段须在固定动词集内：create/query/update/cancel/sync/confirm/apply/push |
| 路径变量 | 禁止 path 中传 `{id}` 等唯一标识 |
| 版本段 | 第二段须为 `v1`/`v2` 格式 |

## 需人工补充的规则

脚本无法覆盖全部规范，审查时务必逐项核对 [`api-manual-rules.md`](api-manual-rules.md)。

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 检查脚本：[`scripts/api_check.py`](scripts/api_check.py)
- 人工规则：[`api-manual-rules.md`](api-manual-rules.md)
- 设计规范：[`steering/api-standards.md`](../../steering/api-standards.md)
- 审查样例：[`test/`](test/)
