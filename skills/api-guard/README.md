# api-guard

业务接口规范审查技能。

## 能力

1. **审查 API 定义** — 运行检查脚本自动检查 Controller 中的路径命名/路径变量/时间注解，再补充人工判断
2. **设计新 API** — 按规范生成合规的业务接口定义

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

仅检查业务接口通用规范，不检查对外 Open API 四段式规范。

| 类别 | 检查项 |
|---|---|
| 路径命名 | 全小写 kebab-case，禁止 camelCase、下划线及畸形短横线（段首/段尾/连续短横线） |
| 动作收敛 | 末段须在固定动词集内：create/query/update/remove/cancel/sync/confirm/apply/push |
| 路径变量 | 禁止 path 中传 `{id}` 等唯一标识 |
| 时间注解 | DTO 禁 `shape=NUMBER`（须 ISO 8601 pattern）；PO 禁任何日期注解 |

## 需人工补充的规则

脚本无法覆盖全部规范，审查时务必逐项核对 [`api-manual-rules.md`](api-manual-rules.md)。

## 相关文件

- 技能定义：[`SKILL.md`](SKILL.md)
- 检查脚本：[`scripts/api_check.py`](scripts/api_check.py)
- 单元测试：[`scripts/test_api_check.py`](scripts/test_api_check.py)
- 人工规则：[`api-manual-rules.md`](api-manual-rules.md)
- 业务接口规范：[`steering/gtsp/03-api-feign.md`](../../steering/gtsp/03-api-feign.md)
- 时间注解规范：[`steering/gtsp/04-database-mybatis.md`](../../steering/gtsp/04-database-mybatis.md)
- 审查样例：[`test/`](test/)
- Badcase 测试：[`badcase/`](badcase/)
