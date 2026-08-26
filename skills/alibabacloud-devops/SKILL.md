---
name: alibabacloud-devops
description: 阿里云云效 DevOps 平台工具集（165+ 工具）。当用户提到以下任意意图时激活：云效、Yunxiao、Codeup、代码仓库、分支、合并请求、变更请求、流水线、CI/CD、运行部署、项目管理、工作项、需求、缺陷、任务、迭代、工时、制品、应用交付、部署单、发布流程、测试用例、测试计划。通过 mcporter CLI 按需调用，不在 Claude Code 中常驻注册。
---

# 阿里云云效 DevOps（mcporter 代理模式）

**红线：刻意不注册为 MCP server**（165+ 工具 schema 常驻约 15k token/轮）。
所有调用走 mcporter CLI 按需查询与执行，设计论证见 [README](README.md)。

## 前置：访问令牌与变量约定

- 令牌探测顺序：优先检查环境变量 `YUNXIAO_ACCESS_TOKEN`（用户可能在其他终端窗口 export，非交互 shell 中不可见），再查 `~/.yunxiao_token`、`~/.aliyun/` 等本地配置；历史会话的「无令牌」结论不可复用，每次操作前须重新确认。
- 云效 OpenAPI 令牌对 `codeup.aliyun.com/api/v4` 认证无效（返回 302 登录页），不能据此误判为令牌失效，应改走云效 OpenAPI 端点。

```bash
export YUNXIAO_ACCESS_TOKEN=<your-token>   # 云效个人设置中获取
# 下文以 $YX 代指令牌环境、$SRV 代指 server 启动命令：
SRV='npx -y alibabacloud-devops-mcp-server'
YX='--env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN'
```

## 工具调用三件套

```bash
# 1. 查工具（先查后用，不要猜工具名；配合业务域关键词缩小范围）
mcporter list --stdio "$SRV" $YX --schema | grep -i pipeline

# 2. 调工具（参数 key=value，含空格值用 key:"..."）
mcporter call --stdio "$SRV" $YX <tool_name> key1=value1 key2="value 2"
# 若 --env 不生效，改用 shell 前置：YUNXIAO_ACCESS_TOKEN=... mcporter call --stdio "$SRV" <tool> ...

# 3. 可选：daemon 模式（避免每次 npx 冷启动数秒）
mcporter config add yunxiao && mcporter daemon start
mcporter list yunxiao --schema && mcporter call yunxiao.<tool> key=value   # 秒级响应
```

## 业务域导航（缩小查询范围）

先按域定位关键词，再 `mcporter list | grep -i <关键词>` 确认。工具清单随上游版本
变化，**始终以 `mcporter list` 实时结果为准**，不依赖静态清单。

| 业务域 | 关键词 |
| --- | --- |
| 组织 / 身份 | `organization`、`user` |
| 代码仓库 | `repository`、`branch`、`commit`、`file` |
| 合并请求 | `change_request` |
| 项目 / 迭代 / 工作项 | `project`、`sprint`、`work_item` |
| 工时 | `effort` |
| 流水线 | `pipeline` |
| 主机部署 | `vm_deploy` |
| 制品 | `package`、`artifact` |
| 应用交付 | `app`、`orchestration`、`change_order`、`release` |
| 测试 | `testcase`、`test_plan`、`test_result` |

## 典型工作流（模式参考，工具名以实时查询为准）

- PR 评论复核闭环：`git fetch` 对齐远程基线并确认新提交范围 → 逐条按最新代码判定未解决评论（仍成立/已修复/误判）→ 误判评论调更新接口置 `resolved=true` 并追加更正评论给出推翻证据；复核中发现的新问题另行发评论。

```bash
# 代码审查：get_current_organization_info → list_change_requests ... state=opened
#           → create_change_request_comment organizationId=<org> repositoryId=<repo> localId=123 content="LGTM"
# 流水线：  list_pipelines → create_pipeline_run pipelineId=123456 branch=main
#           → get_latest_pipeline_run pipelineId=123456
# 工作项：  search_projects → list_work_item_types → get_work_item_type_field_config
#           → create_work_item（模板必填字段经 customFieldValues 平面对象传）
```

## 工作项操作：MCP 工具优先（官方最佳实践对齐）

官方 server 已把工作项的发现/创建/评论全部工具化，**能用工具就不要直连 REST**
（工具自带字段抽象与错误翻译，直连只在该工具确实缺失时作为兜底）：

| 意图 | 工具（以 `mcporter list` 实时为准） | 说明 |
| --- | --- | --- |
| 找项目空间 | `search_projects` / `get_project` | spaceId = 项目 id |
| 工作项类型 | `list_work_item_types`（项目空间）/ `get_work_item_type` | 拿 workitemTypeId |
| **字段配置** | `get_work_item_type_field_config` | **模板必填字段（如「计划开始时间」）在这里发现**——fieldId、format（date/float/list）、options（含每项 id）、required 一并返回；create 前必查 |
| 创建 | `create_work_item` | 模板必填字段经 customFieldValues 平面对象传：`{"<fieldId>": "<value>"}`；list 类字段传 option **id**（非文本），float 传小数字符串，date 传 ISO 日期 |
| 读/搜 | `get_work_item` / `search_workitems` | |
| 评论 | `list_work_item_comments` / `create_work_item_comment` | |
| 工时 | `list_effort_records` / `create_effort_record` 等 | |

### 直连 REST 的两个正当场景（兜底，非默认）

1. **工具面缺失**：如 MC 评论 resolve（`PUT comments/{id}`）、MR `comments/list`
   批量拉取——工具未覆盖时直连，端点/字段形态见「注意」节。
2. **脚本化集成**（`.factory/forge` 形态）：需要稳定 argv 界面时。完整实测
   知识（字段配置端点形态、value 形态矩阵、assignedTo 24-hex、空体容错）沉淀在
   [.factory/decisions.md ADR-007](../../.factory/decisions.md)，不在此复制——
   实例态数据（fieldId 等）随 space 模板变化，正确位置是代码运行时发现，不是文档。

### 排错信源优先级（黑盒探针成本实证）

1. **MCP server 仓 `docs/*.swagger.json`**（[GitHub](https://github.com/aliyun/alibabacloud-devops-mcp-server)）——字段必填性/类型/枚举一查便知，比帮助文档表格结构化
2. 官方文档 https://help.aliyun.com/zh/yunxiao/
3. 黑盒探针（最后手段——曾实测 13 种键名形态全拒后才发现正解是「先查字段配置拿 fieldId」）

### 令牌权限时效性

403 结论**不可缓存**：个人令牌 scope 变更后同一接口口径可完全反转（工作项评论
曾 403 后全通）。变更后必须复验；诊断时先想「scope 变了吗」再看代码。

## 注意

- **Codeup PR（changeRequest）评论**：`POST /oapi/v1/codeup/organizations/{orgId}/repositories/{repoId}/changeRequests/{localId}/comments`，仓库级 changeRequests 端点会 404，须走组织级；请求体 `comment_type` 必填且仅 `GLOBAL_COMMENT` / `INLINE_COMMENT` 合法（无默认值），`resolved` 不可为 null 须显式传布尔；拉取评论列表用 `POST .../comments/list`（body：`{"patchSetBizIds":[],"commentType":"GLOBAL_COMMENT","state":"OPENED","resolved":<bool>}`，resolved 两态各拉一次取全集）；resolve 已有评论用 `PUT .../comments/{commentBizId}` + `{"resolved": true}`（列表返回的主键字段名是 `comment_biz_id`）。
- **Codeup MR 列表**：组织级端点 `GET /oapi/v1/codeup/organizations/{org}/changeRequests`（**无** `/repositories` 段），URL query 传 `projectIds={repoId}` 过滤（POST/body 形态被拒）；摘要行无 status 字段，开合过滤交给服务端 `state` 参数。
- 默认端点 `openapi.aliyun.com` 为全球单节点，受限网络下 TLS 握手可能被静默丢弃；此时改用中心版端点 `openapi-rdc.aliyuncs.com`（`/oapi/v1/...` 路径一致，认证头同为 `x-yunxiao-token`），勿据此判定令牌失效或 API 不可用。公司网关对快速连续 TLS 握手偶发 RST（SSLEOFError）——握手失败=请求未发出，重试皆安全，建议 3 次退避。
- `devops.cn-hangzhou.aliyuncs.com` RPC 网关（RAM 风格 Action 探测）不含 Codeup 模块，不要在此浪费探测。
- 参数值含空格或特殊字符须加引号；布尔/数字按 API 要求的类型传。
- 官方文档：https://help.aliyun.com/zh/yunxiao/ ；OpenAPI 精确 schema 见 [alibabacloud-devops-mcp-server](https://github.com/aliyun/alibabacloud-devops-mcp-server) 仓 `docs/*.swagger.json`（比帮助文档表格更结构化，字段必填性/类型一查便知）。
